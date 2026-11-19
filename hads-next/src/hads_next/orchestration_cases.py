"""Finite autonomous evidence work over the current tool catalog, without AI.

Plans are acquisition tasks, not hardcoded diagnoses. Actual schema-checked
results are available to the original Hermes loop, including dependency reads.
"""
import json
import re
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
        tools=self.app.tools
        available=tools.registry.tools(include_blocked=False)
        for incident in cases:
            if budget<=0:break
            case=self.app.store.case(incident['id']);targets=tools._scope(case,{})
            requests=[]
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
                elif provider=='hamster_mcp' and name=='hass/config/entity_registry/get':
                    for entity in sorted(t for t in targets if isinstance(t,str) and '.' in t)[:2]:
                        requests.append({'provider':provider,'tool':name,'arguments':{'entity_id':entity}})
                elif provider=='core' and name=='statistics':
                    for entity in sorted(t for t in targets if isinstance(t,str) and t.startswith('sensor.'))[:2]:
                        requests.append({'provider':provider,'tool':name,'arguments':{'entity_id':entity}})
                elif provider=='music_assistant':
                    for entity in sorted(t for t in targets if isinstance(t,str) and t.startswith('media_player.'))[:1]:
                        from datetime import datetime,timezone
                        iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
                        requests.append({'provider':provider,'tool':name,'arguments':{'entity_id':entity,'start':iso(incident['first_seen']-300),'end':iso(min(self.app.clock(),incident['last_seen']+300))}})
                elif provider=='ha_mcp':
                    for entity in sorted(t for t in targets if isinstance(t,str) and re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+',t))[:4]:
                        if name in {'ha_get_state','ha_get_device'} or name=='ha_config_get_automation' and entity.startswith('automation.'):
                            requests.append({'provider':provider,'tool':name,'arguments':{'entity_id':entity}})
                        elif name=='ha_config_get_script' and entity.startswith('script.'):
                            requests.append({'provider':provider,'tool':name,'arguments':{'script_id':entity}})
            for request in requests:
                if budget<=0:break
                report=tools.reports.get((request['provider'],request['tool']),{})
                report_data = report.get('data')
                if request['provider'] == 'zha_toolkit' and report_data:
                    # The refresh timestamp changes even when the cache contents do not.
                    report_data = {key: value for key, value in report_data.items() if key != 'checked_at'}
                request_id=fingerprint([request,fingerprint(report_data) if report else int(self.app.clock()//600)])
                with self.app.store._connect() as db:
                    previous=db.execute('SELECT * FROM orchestration_reads WHERE incident_id=? AND request_hash=?',(incident['id'],request_id)).fetchone()
                    if previous and (previous['state']=='available' or previous['attempts']>=2 or self.app.clock()-previous['checked_at']<300):continue
                budget-=1
                try:result=tools.diagnostic_read(incident['id'],request)
                except (ValueError,KeyError,TypeError):result={'status':'not_read','evidence_ids':[]}
                with self.app.store._connect() as db:
                    db.execute('INSERT OR REPLACE INTO orchestration_reads VALUES(?,?,?,?,?,?,?,?)',(incident['id'],request_id,request['provider'],request['tool'],result['status'],1 if previous is None else previous['attempts']+1,self.app.clock(),canonical({k:v for k,v in result.items() if k!='data'})))
                if result['status']=='available' and request['tool'] in {'core_logs','supervisor_logs'}:
                    self._log_lines(incident['id'],request['provider'],request['tool'],result.get('data',{}))
                if result['status']=='available' and request['provider']=='automation_inspector':self._dependencies(incident['id'],targets,result.get('data',{}))
            self.prepare_candidates(incident['id'])
            self.app.store.record(incident['id'],'orchestration_checkpoint',self.summary(incident['id']))
            with self.app.store._connect() as db:
                for kind in ('orchestration_checkpoint','orchestration_repair_blocked','orchestration_repair_ready'):
                    db.execute('DELETE FROM case_records WHERE incident_id=? AND kind=? AND id NOT IN (SELECT id FROM case_records WHERE incident_id=? AND kind=? ORDER BY id DESC LIMIT 20)',(incident['id'],kind,incident['id'],kind))
                db.execute('DELETE FROM orchestration_reads WHERE incident_id=? AND request_hash NOT IN (SELECT request_hash FROM orchestration_reads WHERE incident_id=? ORDER BY checked_at DESC LIMIT 512)',(incident['id'],incident['id']))
        with self.app.store._connect() as db:
            db.execute('DELETE FROM orchestration_reads WHERE rowid IN (SELECT rowid FROM orchestration_reads ORDER BY checked_at DESC LIMIT -1 OFFSET 10000)')
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
        if case['incident']['kind']=='manual_functional' and any(r['provider']=='spook' and r['name']=='homeassistant.enable_entity' for r in catalog):
            for report in self.app.entity_context.reports(case)[:2]:
                if report['classification']!='disabled' or (report.get('registry') or {}).get('disabled_by')!='user':continue
                try:
                    self.app.approved_tools.prepare(identity,'spook','homeassistant.enable_entity',{'entity_id':report['entity_id']},evidence,
                        'U nahlášeného funkčního problému je doložené zakázání uživatelem. Schválením tohoto přesného plánu vlastník výslovně potvrzuje, že entita má být povolená; nejde o automaticky zjištěnou poruchu Zigbee.',exclusive=True)
                except (ValueError,KeyError,TypeError) as error:
                    self.app.store.record(identity,'orchestration_repair_blocked',{'provider':'spook','tool':'homeassistant.enable_entity','reason_cs':str(error)[:700]})
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
            events.append({'source':'core' if name=='core_logs' else 'supervisor','observed_at':when,'component':component[1] if component else provider,'message':line})
        groups=self.correlate(events)
        if groups:
            self.app.store.record(incident_id,'cross_source_correlation',{'groups':groups[:4],'root_cause_proven':False})

    def grouped_children(self):
        with self.app.store._connect() as db:return {r[0] for r in db.execute("SELECT child FROM incident_links l JOIN incidents i ON i.id=l.parent WHERE i.status='open'")}
