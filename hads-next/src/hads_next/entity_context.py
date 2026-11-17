"""Autonomous, bounded follow-up of actual Watchman targets and manual cases.

Uses the same native snapshot as provider inventory; no model, shell, arbitrary
service, source-file guessing, repair authority or manufactured physical result.
"""
from datetime import datetime,timezone
import hashlib
import json
import re
import time
from .evidence import canonical

ENTITY = re.compile(r'[a-z][a-z0-9_]*\.[a-z0-9_]{1,128}')
ID = re.compile(r'[A-Za-z0-9_-]{1,128}')


def safe_id(value):
    return value if isinstance(value,str) and ID.fullmatch(value) else None


def registry_rows(value):
    if not isinstance(value,list) or len(value)>10000 or any(not isinstance(r,dict) for r in value):
        return None
    result={}
    for row in value:
        entity=row.get('entity_id')
        if not isinstance(entity,str) or not ENTITY.fullmatch(entity):continue
        disabled=row.get('disabled_by')
        result[entity]={'entity_id':entity,'device_id':safe_id(row.get('device_id')),
            'platform':safe_id(row.get('platform')),
            'disabled_by':disabled if disabled is None or isinstance(disabled,str) and disabled in {'user','integration','config_entry'} else 'unclassified',
            'name':str(row.get('name') or row.get('original_name') or entity)[:120]}
    return result


class EntityContext:
    SCHEMA=1
    def __init__(self,app):
        self.app=app;self.toolkit=None;self.cursor=0
        with app.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS entity_context_schema(version INTEGER PRIMARY KEY)')
            versions=[r[0] for r in db.execute('SELECT version FROM entity_context_schema')]
            if versions and versions!=[self.SCHEMA]:raise RuntimeError('unsupported_entity_context_schema')
            db.execute('INSERT OR IGNORE INTO entity_context_schema VALUES(?)',(self.SCHEMA,))
            db.execute('CREATE TABLE IF NOT EXISTS entity_context_reports(entity_id TEXT PRIMARY KEY,checked_at REAL NOT NULL,document TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS entity_context_device_episodes(key TEXT PRIMARY KEY,active INTEGER NOT NULL,episode INTEGER NOT NULL)')
        schema={'name':'hads_get_entity_diagnosis','description':'Přečte poslední konkrétní stav, registr a dostupné ZHA/Toolkit důkazy cíle tohoto incidentu. Neprovádí opravu.',
                'parameters':{'type':'object','properties':{'entity_id':{'type':'string','maxLength':160}},'required':['entity_id'],'additionalProperties':False}}
        app.investigations.broker.extensions[schema['name']]={'schema':schema,'read':self.broker_read}

    def update(self,values,states):
        app=self.app;now=app.clock()
        deadline=time.monotonic()+25
        registry=registry_rows(values.get('entity_registry'))
        states_ok=isinstance(states,list) and len(states)<=10000 and all(isinstance(r,dict) for r in states)
        current={r['entity_id']:r for r in states if isinstance(r.get('entity_id'),str) and ENTITY.fullmatch(r['entity_id'])} if states_ok else {}
        watchman=next((r.get('diagnostic_read') for r in app.providers.snapshot() if r['provider_id']=='watchman'),None)
        findings=watchman.get('findings',[]) if isinstance(watchman,dict) else []
        watchman_targets={r['id'] for r in findings if r['kind']=='missing_entities' and r['id'].split('.')[0] not in {'lovelace','logger'} and r['id'] not in {'light.is_on','script.execute'}}
        targets=set(watchman_targets)
        cases=app.snapshot()['cases']
        for case in cases:
            if case['kind']=='manual_functional' and case['status']=='open':targets.update(x for x in case['components'] if ENTITY.fullmatch(x))
        catalog={entity:{'entity_id':entity,'name':str((r['attributes'] if isinstance(r.get('attributes'),dict) else {}).get('friendly_name',entity))[:120],
                         'state':str(r.get('state','unknown'))[:128]} for entity,r in current.items()}
        for entity,r in (registry or {}).items():catalog.setdefault(entity,{'entity_id':entity,'name':r['name'],'state':'není v aktuálních stavech'})
        for entity in targets:catalog.setdefault(entity,{'entity_id':entity,'name':entity,'state':'odkaz hlásí Watchman'})
        with app._lock:app._entity_catalog=list(catalog.values())[:12000]
        components=(values.get('core_config') or {}).get('components',[]) if isinstance(values.get('core_config'),dict) else []
        components_ok=isinstance(components,list) and all(isinstance(c,str) for c in components)
        self.toolkit={'component_loaded':'zha_toolkit' in components if components_ok else None,'read_succeeded':False,'devices':[],
                      'checked_at':now,'scope':'existing_zha_cache_only_no_RF_scan','writes_enabled':False}
        ws=app.core_ws;toolkit=[];native=[]
        if self.toolkit['component_loaded'] and ws:
            result=getattr(ws,'toolkit_devices',lambda:None)()
            valid=isinstance(result,dict) and isinstance(result.get('devices'),list)
            self.toolkit['read_succeeded']=valid
            self.toolkit['devices']=result['devices'] if valid else []
            self.toolkit['version']=result.get('version') if valid else None
            self.toolkit['last_error']=None if valid else 'ZHA Toolkit neposkytl platnou odpověď; HADS použije dostupné nativní ZHA čtení.'
            toolkit=self.toolkit['devices']
        needs_zha=any((registry or {}).get(t,{}).get('platform')=='zha' for t in targets)
        if needs_zha and ws:
            result=getattr(ws,'zha_devices',lambda:None)()
            native=result if isinstance(result,list) else None
        selected=sorted(targets)
        # At most eight direct state/history reads each pass; rotate so large
        # reports cannot starve a later target. A pass always remains finite.
        if selected:
            offset=self.cursor%len(selected);selected=(selected[offset:]+selected[:offset])[:8];self.cursor+=len(selected)
        for entity in selected:
            row=(registry or {}).get(entity);raw=current.get(entity);gaps=[];direct_missing=False
            if registry is None:gaps.append('entity_registry_unavailable')
            if not states_ok:gaps.append('core_states_unavailable')
            if raw is None and app.core and time.monotonic()<deadline:
                raw=app.core.states(entity)
                direct_missing=raw is None and app.core.status.last_response_status==404
                if raw is None and not direct_missing:gaps.append('target_state_read_failed')
            elif raw is None and app.core:gaps.append('read_budget_exhausted')
            state=raw.get('state') if isinstance(raw,dict) and raw.get('entity_id')==entity else None
            state=state if isinstance(state,str) and state in {'on','off','unavailable','unknown','playing','idle','paused','standby'} else 'other' if isinstance(state,str) else None
            device_id=row.get('device_id') if row else None
            radio=next((r for r in native or [] if device_id and r.get('device_id')==device_id),None)
            extra=next((r for r in toolkit if device_id and r.get('device_id')==device_id),None)
            if row and row['platform']=='zha' and radio is None:gaps.append('zha_device_not_read')
            if row and row['disabled_by']:
                classification='disabled';summary='Entita je v registru zakázaná. Samotný odkaz neurčuje, zda ji chceš zapnout.'
                next_step='Před jakýmkoli návrhem zapnutí je potřeba tvůj záměr. HADS zakázané entity automaticky nezapíná.'
            elif state=='unavailable':
                classification='unavailable';summary='Aktuální Home Assistant potvrzuje nedostupnost této entity.'
                if radio and radio.get('available') is False:summary+=' Také ZHA hlásí zařízení jako nedostupné.'
                elif radio and radio.get('available') is True:summary+=' ZHA zařízení uvádí jako dostupné; je potřeba odlišit stav entity od spojení zařízení.'
                next_step='HADS sám znovu přečte stav a dostupnou ZHA diagnostiku. Bez doložené příčiny nenabízí přepárování, restart ani změnu kanálu.'
            elif state=='unknown':
                classification='unknown';summary='Entita existuje, ale její aktuální hodnota není známá. To samo neprokazuje ztrátu Zigbee spojení.'
                next_step='HADS porovná další stav, historii a dostupné údaje zařízení. Chybějící hodnota není důvod k mazání či přepárování.'
            elif state is not None:
                classification='state_available';summary='Entita nyní poskytuje stav. Dřívější nález ani nahlášená funkční porucha tím nejsou automaticky vyřešené.'
                next_step='HADS sleduje další čtení; funkční výsledek vyžaduje předem určenou podmínku nebo jednoduchý fyzický test.'
            elif direct_missing:
                classification='missing';summary='Přímé čtení Core vrátilo 404: pod tímto identifikátorem nyní stav není.'
                next_step='HADS porovná registr a související entity stejného zařízení. Bez potvrzené náhrady nesmí přepsat odkaz podle podobného názvu.'
            else:
                classification='unverified';summary='Aktuální stav cíle se nepodařilo ověřit. HADS tento výsledek nepovažuje za chybějící zařízení.'
                next_step='Další automatické čtení zkusí stejný cíl znovu. Výpadek diagnostiky neopravňoval zásah do zařízení.'
            history=None
            if state in {'unavailable','unknown'} and app.core and time.monotonic()<deadline:
                iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
                raw_history=app.core.history(iso(now-900),entity,iso(now))
                if isinstance(raw_history,list):
                    history=[{'state':r['state'],'last_updated':r['last_updated']} for group in raw_history if isinstance(group,list) for r in group
                             if isinstance(r,dict) and r.get('entity_id')==entity and r.get('state') in {'on','off','unknown','unavailable'} and isinstance(r.get('last_updated'),str)][:32]
                else:gaps.append('history_unavailable')
            elif state in {'unavailable','unknown'} and app.core:gaps.append('history_read_deferred_budget')
            document={'entity_id':entity,'classification':classification,'state':state,'registry':row,
                      'zha':radio,'toolkit':extra,'history':history,'gaps':gaps,'summary_cs':summary,'next_test_cs':next_step,
                      'root_cause_proven':False,'repair_performed':False,
                      'repair':{'approval_available':False,'operation':None,
                                'reason_cs':('Nejprve je potřeba potvrdit, že entita má být povolená. Automatický zápis do registru tento katalog zatím neprovádí.' if classification=='disabled' else 'Zatím nic nepovoluj k opravě: chybí potvrzená náhrada identifikátoru. Podobný název není bezpečný cíl.' if classification=='missing' else 'Zatím nic nepovoluj k opravě: příčina ani konkrétní bezpečná změna nejsou doložené. Obecné Zigbee zásahy tento katalog zatím neprovádí.')}}
            with app.store._connect() as db:
                old=db.execute('SELECT document FROM entity_context_reports WHERE entity_id=?',(entity,)).fetchone()
                serialized=canonical(document)
                db.execute('INSERT OR REPLACE INTO entity_context_reports VALUES(?,?,?)',(entity,now,serialized))
                db.execute('DELETE FROM entity_context_reports WHERE entity_id IN (SELECT entity_id FROM entity_context_reports ORDER BY checked_at DESC LIMIT -1 OFFSET 256)')
            linked=[c['id'] for c in cases if entity in c['components']]
            if entity in watchman_targets and watchman.get('incident_id'):linked.append(watchman['incident_id'])
            owner_case=any(c['kind']=='manual_functional' and c['status']=='open' and entity in c['components'] for c in cases)
            if classification=='unavailable' and not owner_case and entity.startswith(('binary_sensor.','sensor.','light.','switch.')):
                key='device:'+(device_id or entity)
                with app.store._connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    previous=db.execute('SELECT active,episode FROM entity_context_device_episodes WHERE key=?',(key,)).fetchone()
                    episode=1 if previous is None else previous['episode']+(not previous['active'])
                    db.execute('INSERT OR REPLACE INTO entity_context_device_episodes VALUES(?,1,?)',(key,episode))
                incident=app.store.open_incident('device_unavailable','Zařízení má doloženou nedostupnou entitu: '+entity,
                    [entity]+([device_id] if device_id else []),now,correlation_key='native:'+key,occurrence_id=key+':'+str(episode))
                linked.append(incident['id'])
            for identity in set(linked):
                event=hashlib.sha256(canonical(['entity_context',document]).encode()).hexdigest()
                with app.store._connect() as db:before=db.execute("SELECT observed_at FROM evidence WHERE source='native_entity_context' AND event_id=?",(event,)).fetchone()
                added=app.store.add_evidence(identity,{'source':'native_entity_context','kind':'entity_context','event_id':event,
                    'observed_at':before[0] if before else now,'payload':document})
                if added and (not watchman or identity!=watchman.get('incident_id')):
                    app.store.record(identity,'deterministic_investigation',{'summary_cs':summary,'next_test_cs':next_step,'root_cause_proven':False,
                                     'needed':[],'repair':document['repair']},at=now)
        groups={}
        for report in self.reports():
            key='device:'+((report.get('registry') or {}).get('device_id') or report['entity_id'])
            groups.setdefault(key,[]).append(report)
        with app.store._connect() as db:
            for key,reports in groups.items():
                if all(r['classification']=='state_available' and now-r['checked_at']<=600 for r in reports):
                    db.execute('UPDATE entity_context_device_episodes SET active=0 WHERE key=?',(key,))

    def reports(self,case=None):
        with self.app.store._connect() as db:rows=db.execute('SELECT * FROM entity_context_reports ORDER BY entity_id').fetchall()
        targets=set(case['incident']['components']) if case else None
        aggregate=case and case['incident'].get('correlation_key')=='provider:watchman:references'
        if aggregate:
            snapshots=[e['payload'] for e in case['evidence'] if e['source']=='watchman_native']
            if snapshots:targets.update(x['id'] for x in snapshots[-1].get('findings',[]))
        return [{**json.loads(r['document']),'checked_at':r['checked_at']} for r in rows if targets is None or r['entity_id'] in targets]

    def broker_read(self,incident_id,args):
        from .evidence_broker import BrokerDenied
        if not isinstance(args,dict) or set(args)!={'entity_id'} or not isinstance(args['entity_id'],str) or not ENTITY.fullmatch(args['entity_id']):
            raise BrokerDenied('Neplatný cíl diagnostiky.')
        case=self.app.store.case(incident_id)
        report=next((r for r in self.reports(case) if r['entity_id']==args['entity_id']),None)
        if report is None:raise BrokerDenied('Cíl nemá diagnostický důkaz v tomto spisu.')
        stale=self.app.clock()-report['checked_at']>600
        return {'tool':'hads_get_entity_diagnosis','source':'native_entity_context','status':'not_read' if stale else 'available',
                'data':report,'evidence_ids':[e['evidence_id'] for e in case['evidence'] if e['source']=='native_entity_context' and e['payload'].get('entity_id')==args['entity_id']],
                'read_at':report['checked_at'],'detail_cs':'Čtení je starší než deset minut; čeká na obnovení.' if stale else 'Konkrétní nativní čtení cíle, nikoli oprava.'}
