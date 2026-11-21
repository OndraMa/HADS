"""Finite autonomous evidence work over the current tool catalog, without AI.

Plans are acquisition tasks, not hardcoded diagnoses. Actual schema-checked
results are available to the original Hermes loop, including dependency reads.
"""
import json
import re
from datetime import datetime,timezone
from .evidence import canonical
from .tool_registry import fingerprint,ToolDenied
from .provider_reports import stamp

class OrchestrationCases:
    def __init__(self,app):
        self.app=app;self.cursor=0
        with app.store._connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS orchestration_schema(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO orchestration_schema VALUES(1);
                CREATE TABLE IF NOT EXISTS incident_links(parent TEXT NOT NULL,child TEXT NOT NULL,kind TEXT NOT NULL,PRIMARY KEY(parent,child));
                CREATE TABLE IF NOT EXISTS orchestration_reads(
                incident_id TEXT NOT NULL,request_hash TEXT NOT NULL,provider TEXT NOT NULL,tool TEXT NOT NULL,
                state TEXT NOT NULL,attempts INTEGER NOT NULL,checked_at REAL NOT NULL,result TEXT,
                PRIMARY KEY(incident_id,request_hash));
                CREATE TABLE IF NOT EXISTS orchestration_log_events(
                fingerprint TEXT PRIMARY KEY,observed_at REAL NOT NULL,document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS orchestration_correlations(
                id TEXT PRIMARY KEY,document TEXT NOT NULL,checked_at REAL NOT NULL);''')
            if [r[0] for r in db.execute('SELECT version FROM orchestration_schema')]!=[1]:raise ToolDenied('Neznámé schéma orchestrace.')
    def cycle(self,budget=6):
        cases=[c for c in self.app.snapshot()['cases'] if c['status']=='open']
        if not cases:return
        offset=self.cursor%len(cases);cases=cases[offset:]+cases[:offset];self.cursor+=1
        with self.app.store._connect() as db:
            pending={r['incident_id']:json.loads(r['content'])['message_id'] for r in db.execute(
                """SELECT m.incident_id,m.content FROM case_records m
                WHERE m.kind='owner_message'
                AND m.id=(SELECT max(id) FROM case_records WHERE incident_id=m.incident_id AND kind='owner_message')
                AND NOT EXISTS(SELECT 1 FROM case_records d WHERE d.incident_id=m.incident_id AND d.kind='owner_diagnostic_reply'
                    AND d.id>m.id AND json_extract(d.content,'$.message_id')=json_extract(m.content,'$.message_id'))""")}
        cases.sort(key=lambda incident:incident['id'] not in pending)
        tools=self.app.tools
        available=tools.registry.tools(include_blocked=False)
        ai=self.app.investigations.provider.public_status()
        autonomous=(ai['enabled'] and ai.get('mode')=='bounded' and self.app.investigations.launcher is not None
                    and self.app.detection.snapshot()['autonomous_ai'])
        case_budget=max(3,budget//min(3,len(cases)))
        for incident in cases:
            if budget<=0:break
            case=self.app.store.case(incident['id']);targets=tools._scope(case,{})
            message_id=pending.get(incident['id'])
            attempted=[]
            evidence_acquired=False
            requests=[]
            device_outage=incident['kind']=='device_unavailable'
            if device_outage:
                requests.extend(self._device_requests(case,available))
            registry = tools.snapshot_values.get('entity_registry')
            if isinstance(registry, list) and any(
                isinstance(row, dict) and row.get('platform') == 'zha' and row.get('entity_id') in targets
                for row in registry
            ) and any(row['provider'] == 'zha_toolkit' and row['name'] == 'diagnostics' for row in available):
                requests.append({'provider':'zha_toolkit','tool':'diagnostics','arguments':{}})
            if incident['kind']=='system_resource_pressure' and any(r['provider']=='core' and r['name']=='hads_get_runtime_health' for r in available):
                requests.append({'provider':'core','tool':'hads_get_runtime_health','arguments':{}})
            if incident['kind'] in {'system_resource_pressure','application_failure','system_health_failure','manual_functional'}:
                for provider,name in [('core','core_logs'),('supervisor','supervisor_logs')]:
                    if any(r['provider']==provider and r['name']==name for r in available):requests.append({'provider':provider,'tool':name,'arguments':{}})
            # Available providers choose possible acquisition routes; no route
            # claims a cause merely from a type label or an app's presence.
            for row in available:
                provider,name=row['provider'],row['name']
                if row['effect']!='read':continue
                if provider in {'automation_inspector','hadocs','watchman','haghs','entity_availability','spook'} and name in {'dependency_report','analysis_report','diagnostics'}:
                    requests.append({'provider':provider,'tool':name,'arguments':{}})
                elif provider=='core' and name=='statistics':
                    for entity in sorted(t for t in targets if isinstance(t,str) and t.startswith('sensor.'))[:2]:
                        requests.append({'provider':provider,'tool':name,'arguments':{'entity_id':entity}})
                elif provider=='music_assistant':
                    for entity in sorted(t for t in targets if isinstance(t,str) and t.startswith('media_player.'))[:1]:
                        from datetime import datetime,timezone
                        iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
                        requests.append({'provider':provider,'tool':name,'arguments':{'entity_id':entity,'start':iso(incident['first_seen']-300),'end':iso(min(self.app.clock(),incident['last_seen']+300))}})
                elif provider=='ha_mcp':
                    if device_outage:continue
                    for entity in sorted(t for t in targets if isinstance(t,str) and re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+',t))[:4]:
                        if name in {'ha_get_state','ha_get_device','ha_get_entity'} or name=='ha_config_get_automation' and entity.startswith('automation.'):
                            requests.append({'provider':provider,'tool':name,'arguments':{'entity_id':entity}})
                        elif name=='ha_config_get_script' and entity.startswith('script.'):
                            requests.append({'provider':provider,'tool':name,'arguments':{'script_id':entity}})
            for request in requests:
                if budget<=0 or len(attempted)>=case_budget:break
                report=tools.reports.get((request['provider'],request['tool']),{})
                report_data = report.get('data')
                if request['provider'] == 'zha_toolkit' and report_data:
                    # The refresh timestamp changes even when the cache contents do not.
                    report_data = {key: value for key, value in report_data.items() if key != 'checked_at'}
                per_occurrence=device_outage and request['tool'] in {
                    'hads_get_entity_history','core_logs','supervisor_logs','host_logs','ha_get_state','ha_get_entity','ha_get_device','ha_get_history'}
                freshness=incident['last_seen'] if per_occurrence else int(self.app.clock()//600)
                request_id=fingerprint([request,fingerprint(report_data) if report else freshness,message_id]) if message_id else fingerprint([request,fingerprint(report_data) if report else freshness])
                with self.app.store._connect() as db:
                    previous=db.execute('SELECT * FROM orchestration_reads WHERE incident_id=? AND request_hash=?',(incident['id'],request_id)).fetchone()
                    if previous and (previous['state'] in {'available','no_relevant_data'} or previous['attempts']>=2 or self.app.clock()-previous['checked_at']<300):continue
                budget-=1
                try:result=tools.diagnostic_read(incident['id'],request)
                except (ValueError,KeyError,TypeError):result={'status':'not_read','evidence_ids':[]}
                attempted.append((request['provider'],request['tool'],result['status']))
                evidence_acquired |= result['status']=='available' and bool(result.get('evidence_ids'))
                with self.app.store._connect() as db:
                    db.execute('INSERT OR REPLACE INTO orchestration_reads VALUES(?,?,?,?,?,?,?,?)',(incident['id'],request_id,request['provider'],request['tool'],result['status'],1 if previous is None else previous['attempts']+1,self.app.clock(),canonical({k:v for k,v in result.items() if k!='data'})))
                if result['status']=='available' and request['tool'] in {'core_logs','supervisor_logs','host_logs'}:
                    self._log_lines(incident['id'],request['provider'],request['tool'],result.get('data',{}))
                if result['status']=='available' and request['provider']=='automation_inspector':self._dependencies(incident['id'],targets,result.get('data',{}))
            if not device_outage or not self._restored(case,self._outage_entity(case)):
                self.prepare_candidates(incident['id'])
            if message_id:
                completed=[provider+' / '+tool for provider,tool,status in attempted if status in {'available','no_relevant_data'}]
                text=('Po tvém doplnění jsem přečetl: '+', '.join(completed)+'.' if completed else
                      'Po tvém doplnění se nepodařilo získat nový ověřený výsledek z dostupných zdrojů.')
                if device_outage:text+=' '+self.device_followup(self.app.store.case(incident['id']))['summary_cs']
                self.app.store.record(incident['id'],'owner_diagnostic_reply',{'message_id':message_id,'summary_cs':text,
                    'attempted':attempted,'paid_model_calls':0})
            elif autonomous and evidence_acquired and incident['kind'] in {
                    'device_unavailable','automation_reference','provider_diagnostic','manual_functional','network_correlation'}:
                last_seen=incident['last_seen']
                prior=any(row['kind']=='autonomous_orchestration_attempt' and row['content'].get('occurrence_at')==last_seen for row in case['records'])
                if not prior:
                    self.app.store.record(incident['id'],'autonomous_orchestration_attempt',{'occurrence_at':last_seen})
                    try:self.app.investigations.start(incident['id'],self.app.owner(),automatic=True)
                    except ValueError:
                        self.app.store.record(incident['id'],'automatic_investigation_deferred',{
                            'summary_cs':'Hermes nyní nelze spustit. Čtecí důkazy zůstávají ve spisu pro pozdější pokračování.'})
            self.app.store.record(incident['id'],'orchestration_checkpoint',self.summary(incident['id']))
            with self.app.store._connect() as db:
                for kind in ('orchestration_checkpoint','orchestration_repair_blocked','orchestration_repair_ready'):
                    db.execute('DELETE FROM case_records WHERE incident_id=? AND kind=? AND id NOT IN (SELECT id FROM case_records WHERE incident_id=? AND kind=? ORDER BY id DESC LIMIT 20)',(incident['id'],kind,incident['id'],kind))
                db.execute('DELETE FROM orchestration_reads WHERE incident_id=? AND request_hash NOT IN (SELECT request_hash FROM orchestration_reads WHERE incident_id=? ORDER BY checked_at DESC LIMIT 512)',(incident['id'],incident['id']))
        with self.app.store._connect() as db:
            db.execute('DELETE FROM orchestration_reads WHERE rowid IN (SELECT rowid FROM orchestration_reads ORDER BY checked_at DESC LIMIT -1 OFFSET 10000)')

    def _device_requests(self,case,available):
        incident=case['incident']
        entity=self._outage_entity(case)
        if entity is None:return []
        when=incident['last_seen']
        # Keep the first look stable while an event is recent so retries deduplicate.
        end=when+300 if self.app.clock()>=when+300 else when
        iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        window={'start_time':iso(when-300),'end_time':iso(end)}
        reads=[('core','hads_get_entity_history',{'entity_id':entity,'start':window['start_time'],'end':window['end_time']}),
               ('ha_mcp','ha_get_entity',{'entity_id':entity}),('ha_mcp','ha_get_state',{'entity_id':entity}),
               ('ha_mcp','ha_get_device',{'entity_id':entity}),
               ('ha_mcp','ha_get_history',{'entity_ids':entity,**window,'source':'history','minimal_response':True,'limit':32}),
               ('core','core_logs',{}),('supervisor','supervisor_logs',{}),('haos','host_logs',{}),
               ]
        supported={(row['provider'],row['name']) for row in available if row['effect']=='read'}
        return [{'provider':provider,'tool':tool,'arguments':args}
                for provider,tool,args in reads if (provider,tool) in supported]

    @staticmethod
    def _outage_entity(case):
        # Legacy device cases store the observed entity in this fixed symptom.
        incident=case['incident']
        for evidence in reversed(case['evidence']):
            entity=evidence['payload'].get('entity_id')
            if (evidence['source']=='native_entity_context' and evidence['payload'].get('classification')=='unavailable'
                    and isinstance(entity,str) and entity in incident['components']
                    and re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+',entity)):
                return entity
        entity=incident['symptom'].rpartition(': ')[2]
        if entity in incident['components'] and re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+',entity):
            return entity
        return None

    def _restored(self,case,entity):
        reports=self.app.entity_context.reports(case)
        now=self.app.clock()
        return any(row['entity_id']==entity for row in reports) and all(
            row['classification']=='state_available' and row['checked_at']>=case['incident']['last_seen']
            and 0<=now-row['checked_at']<=600 for row in reports)

    def device_followup(self,case):
        incident=case['incident']
        if incident['kind']!='device_unavailable':return None
        entity=self._outage_entity(case)
        when=incident['last_seen']
        restored=self._restored(case,entity)
        with self.app.store._connect() as db:
            rows=db.execute('SELECT provider,tool,state FROM orchestration_reads WHERE incident_id=? AND checked_at>=? ORDER BY checked_at',
                            (incident['id'],when)).fetchall()
            events=[json.loads(row[0]) for row in db.execute(
                'SELECT document FROM orchestration_log_events WHERE observed_at BETWEEN ? AND ? ORDER BY observed_at LIMIT 100',
                (when-300,when+300))]
        statuses={(row['provider'],row['tool']):row['state'] for row in rows}
        related=sum(1 for other in self.app.snapshot()['cases'] if other['kind']=='device_unavailable'
                    and other['id']!=incident['id'] and abs(other['last_seen']-when)<=120)
        corroborated=any(
            r.get('entity_id')==entity and r.get('state')=='unavailable'
            and (t:=stamp(r.get('last_updated') or r.get('last_changed'))) is not None and abs(t-when)<=300
            for ev in case['evidence'] if ev['kind']=='hads_get_entity_history'
            for group in (ev['payload'].get('data') or []) if isinstance(group,list)
            for r in group if isinstance(r,dict))
        nearby_signals=sum(e['kind'] in {'dns','network','restart'} for e in events)
        if restored:
            summary='Poslední čtení potvrdilo návrat stavu entity. HADS nyní nenavrhuje změnu zařízení.'
        else:
            summary='HADS ověřuje dostupnost entity a dohledává průběh výpadku.'
        if related:summary+=f' Ve stejném časovém okně HADS zaznamenal další případy nedostupnosti ({related}). Společná příčina zatím není doložená.'
        if corroborated:summary+=' Historie Home Assistantu potvrzuje nedostupnost v době nálezu.'
        if nearby_signals:summary+=f' V protokolech z tohoto okna jsou síťové nebo startovací události ({nearby_signals}). Jejich souvislost s výpadkem není doložená.'
        elif any(statuses.get(key)=='available' for key in [('core','core_logs'),('supervisor','supervisor_logs'),('haos','host_logs')]):
            summary+=' Dostupné výřezy protokolů neobsahují časově přiřaditelný síťový výpadek ani start v tomto okně.'
        return {'summary_cs':summary,'state_restored':restored,'statuses':statuses}
    def _dependencies(self,identity,targets,data):
        found=[]
        for row in data.get('items',[]):
            if not isinstance(row,dict):continue
            refs={r.get('id') for r in row.get('entities',[]) if isinstance(r,dict)}
            if refs&targets and isinstance(row.get('entity_id'),str) and re.fullmatch(r'(automation|script)\.[a-z0-9_]+',row['entity_id']):found.append(row['entity_id'])
        if found:
            with self.app.store._connect() as db:
                old=db.execute('SELECT components FROM incidents WHERE id=?',(identity,)).fetchone()
                components=sorted(set(json.loads(old[0]))|set(found[:20]));db.execute('UPDATE incidents SET components=? WHERE id=?',(canonical(components),identity))
    def summary(self,identity):
        with self.app.store._connect() as db:rows=[dict(r) for r in db.execute('SELECT provider,tool,state,checked_at FROM orchestration_reads WHERE incident_id=? ORDER BY checked_at DESC LIMIT 20',(identity,))]
        return {'reads':rows,'root_cause_proven':False,'paid_model_calls':0,
            'summary_cs':'HADS vybírá dostupná čtení společného katalogu a ukládá skutečné výsledky do spisu. Získané shody jsou podklady pro další vyšetřování, nikoli automatický důkaz příčiny.'}
    def correlate(self,events):
        """Normalize a central log corpus; DNS groups are hypotheses, not proof."""
        from datetime import datetime,timezone
        projected=[]
        for event in events[:512]:
            if not isinstance(event,dict) or event.get('source') not in {'core','supervisor','haos','application','system_log','zha','music_assistant'}:continue
            when=event.get('observed_at');message=event.get('message')
            if isinstance(when,str):when=stamp(when)
            if type(when) not in {int,float} or not isinstance(message,str):continue
            text=message.lower()
            component=str(event.get('component','unknown'))[:128]
            if component.startswith(('hads_next','custom_components.hads','homeassistant.components.hads')):
                continue  # Our reports are outputs, never new independent incidents.
            kind='dns' if any(s in text for s in ('name resolution','dns','getaddrinfo','gaierror')) else 'network' if any(s in text for s in ('connection reset','connection refused','cannot connect','timed out')) else 'restart' if any(s in text for s in ('restarting','started home assistant','starting home assistant')) else 'exception'
            from .observability import redact
            row={'source':event['source'],'observed_at':when,'component':str(event.get('component','unknown'))[:128],'kind':kind,'message':redact(message)[:1000]}
            identity=fingerprint(row)
            with self.app.store._connect() as db:db.execute('INSERT OR IGNORE INTO orchestration_log_events VALUES(?,?,?)',(identity,when,canonical(row)))
            projected.append(row)
        with self.app.store._connect() as db:
            db.execute('DELETE FROM orchestration_log_events WHERE observed_at<?',(self.app.clock()-7*86400,))
            db.execute('DELETE FROM orchestration_log_events WHERE fingerprint IN (SELECT fingerprint FROM orchestration_log_events ORDER BY observed_at DESC LIMIT -1 OFFSET 2000)')
            corpus=[json.loads(r[0]) for r in db.execute('SELECT document FROM orchestration_log_events ORDER BY observed_at')]
        groups=[];claimed=set()
        for dns in [r for r in corpus if r['kind']=='dns']:
            if fingerprint(dns) in claimed:continue
            linked=[r for r in corpus if dns['observed_at']<=r['observed_at']<=dns['observed_at']+120 and r['kind'] in {'dns','network'}]
            components=sorted({r['component'] for r in linked})
            if len(components)<2:continue
            claimed.update(fingerprint(r) for r in linked if r['kind']=='dns')
            doc={'hypothesis':'Společná chyba DNS mohla způsobit následné chyby připojení.','root_cause_proven':False,'components':components,'events':linked[:32],'first_seen':dns['observed_at']}
            identity=fingerprint(['dns_window',dns])
            with self.app.store._connect() as db:db.execute('INSERT OR REPLACE INTO orchestration_correlations VALUES(?,?,?)',(identity,canonical(doc),self.app.clock()))
            incident=self.app.store.open_incident('network_correlation','Více připojení selhalo v časovém okně chyby DNS.',components,dns['observed_at'],correlation_key='correlation:'+identity,occurrence_id=identity)
            event={'source':'central_log_correlation','kind':'network_correlation_hypothesis','event_id':fingerprint([identity,doc]),'observed_at':dns['observed_at'],'payload':doc}
            try:self.app.store.add_evidence(incident['id'],event)
            except ValueError:pass  # Collection continues; no missing proof authorizes repair.
            self.app.store.record(incident['id'],'deterministic_investigation',{'summary_cs':doc['hypothesis'],'root_cause_proven':False,'next_test_cs':'HADS porovná dostupné nativní systémové údaje a další zdrojové časy. Časová návaznost není důvod k restartu nebo změně DNS.'})
            for case in self.app.snapshot()['cases']:
                if case['id']==incident['id'] or abs(case['first_seen']-dns['observed_at'])>120:continue
                related={c.removeprefix('integration:') for c in case['components']}
                related|={'homeassistant.components.'+c for c in related}
                if related&set(components):
                    with self.app.store._connect() as db:db.execute('INSERT OR IGNORE INTO incident_links VALUES(?,?,?)',(incident['id'],case['id'],'possible_common_cause_not_proven'))
            groups.append({**doc,'incident_id':incident['id']})
        return groups

    def prepare_candidates(self,identity):
        """Choose actual implemented repair tools; never authorize a write."""
        case=self.app.store.case(identity);evidence=[e['evidence_id'] for e in case['evidence']]
        if not evidence:return
        tools=self.app.tools
        catalog=tools.registry.tools(include_blocked=False)
        # An analyst request is still inert; reconstruct it independently here.
        for record in [r for r in case['records'] if r['kind']=='tool_repair_proposal'][-2:]:
            request=record['content']
            try:
                row=tools.registry.get(request['provider'],request['tool'],effect='write')
                if row['schema_hash']!=request['schema_hash']:raise ToolDenied('Návrh používá staré schéma; je potřeba nový návrh.')
                self.app.approved_tools.prepare(identity,request['provider'],request['tool'],request['parameters'],request['evidence_ids'],request['reason'],exclusive=True)
            except (ValueError,KeyError,TypeError) as error:
                self.app.store.record(identity,'orchestration_repair_blocked',{'provider':request.get('provider'),'tool':request.get('tool'),'reason_cs':str(error)[:700]})
        # Disabled registry entries are not assumed broken. Only an actual
        # owner-reported functional case can offer enabling as an explicit
        # intended-behavior choice in the immutable approval plan.
        supported={(r['provider'],r['name']) for r in catalog if r['executor']=='entity_enabled'}
        if case['incident']['kind']=='manual_functional':
            for report in self.app.entity_context.reports(case)[:2]:
                if report['classification']!='disabled' or (report.get('registry') or {}).get('disabled_by')!='user':continue
                params={'entity_id':report['entity_id']}
                if ('spook','homeassistant.enable_entity') in supported:
                    provider,tool='spook','homeassistant.enable_entity'
                elif ('ha_mcp','ha_set_entity') in supported and report['entity_id'].startswith(('sensor.','binary_sensor.')):
                    provider,tool='ha_mcp','ha_set_entity'
                    params['enabled']=True
                else:continue
                try:
                    self.app.approved_tools.prepare(identity,provider,tool,params,evidence,
                        'U nahlášeného funkčního problému je doložené zakázání uživatelem. Schválením tohoto přesného plánu vlastník výslovně potvrzuje, že entita má být povolená; nejde o automaticky zjištěnou poruchu Zigbee.',exclusive=True)
                except (ValueError,KeyError,TypeError) as error:
                    self.app.store.record(identity,'orchestration_repair_blocked',{'provider':provider,'tool':tool,'reason_cs':str(error)[:700]})
        candidates=[r for r in catalog if r['effect']=='write' and r.get('executor')=='replace_automation_reference']
        for row in candidates:
            client=tools.connections.clients.get(row['provider'])
            if not client:continue
            for entity in case['incident']['components']:
                if not entity.startswith('automation.'):continue
                try:
                    value=client.call('ha_config_get_automation',{'entity_id':entity})
                    config=value['config'];key='actions' if 'actions' in config else 'action';actions=config[key]
                    if not isinstance(actions,list) or len(actions)!=1:continue
                    old=actions[0]['target']['entity_id']
                    with self.app.store._connect() as db:renames=db.execute('SELECT new_id FROM entity_renames WHERE old_id=? ORDER BY at DESC LIMIT 2',(old,)).fetchall()
                    if len(renames)!=1:continue
                    import copy
                    proposed=copy.deepcopy(config);proposed[key][0]['target']['entity_id']=renames[0][0]
                    params={'entity_id':entity,'config':proposed,'config_hash':value['config_hash'],'wait':True,'run_actions':False}
                    # Preparation records exact preconditions; exclusivity is
                    # explicitly affirmed only with the final owner approval.
                    plan=self.app.approved_tools.prepare(identity,row['provider'],row['name'],params,evidence,
                        'Stejné zařízení a unique_id byly pozorované před i po změně entity_id; automatizace stále používá doloženě chybějící starý identifikátor.',exclusive=True)
                    self.app.store.record(identity,'orchestration_repair_ready',{'plan_id':plan.plan_id,'provider':row['provider'],'tool':row['name'],'approval_granted':False})
                except (ValueError,KeyError,TypeError) as error:
                    self.app.store.record(identity,'orchestration_repair_blocked',{'provider':row['provider'],'tool':row['name'],
                        'reason_cs':str(error)[:700] if isinstance(error,(ToolDenied,)) else 'Konkrétní plán zatím neprošel kontrolou cíle, změny nebo obnovitelnosti zálohy.',
                        'manual_alternative_cs':'Změna se neprovedla. Pro danou automatizaci porovnej přesnou původní a novou identitu v návrhu; nedoloženou náhradu nepoužívej. HADS dál získává důkazy automaticky.'})

    def _log_lines(self,incident_id,provider,name,data):
        # Preserve timestamps only when they are explicitly parseable. Do not
        # replace an undated line's event time with its most recent fetch time.
        text=data.get('text','');events=[]
        for line in text.splitlines()[-100:]:
            match=re.search(r"(\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d))",line)
            if not match:continue
            when=stamp(match[1])
            if when is None:continue
            component=re.search(r'\[(homeassistant\.[A-Za-z0-9_.]+)\]',line)
            events.append({'source':provider,'observed_at':when,'component':component[1] if component else provider,'message':line})
        groups=self.correlate(events)
        incident=self.app.store.case(incident_id)['incident']
        if incident['kind']=='device_unavailable':
            groups=[g for g in groups if abs(g['first_seen']-incident['last_seen'])<=300]
        if groups:
            self.app.store.record(incident_id,'cross_source_correlation',{'groups':groups[:4],'root_cause_proven':False})

    def grouped_children(self):
        with self.app.store._connect() as db:return {r[0] for r in db.execute("SELECT child FROM incident_links l JOIN incidents i ON i.id=l.parent WHERE i.status='open'")}
