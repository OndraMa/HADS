"""Bounded installation health inspection over existing supported native readers."""
import hashlib,json,time,resource,os
from datetime import datetime
from .evidence import canonical
from .observability import project_supervisor_read

class SystemDiagnostics:
    def __init__(self,app):
        self.app=app;self.last=None;self.last_error=None;self.capabilities={}
        with app.store._connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS health_observations(key TEXT PRIMARY KEY,document TEXT NOT NULL,changed_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS health_episodes(key TEXT PRIMARY KEY,active INTEGER NOT NULL,episode INTEGER NOT NULL,incident_id TEXT);
            CREATE TABLE IF NOT EXISTS resource_samples(at REAL PRIMARY KEY,document TEXT NOT NULL);''')
        self._cpu=(time.monotonic(),time.process_time());self._scan_cursor=0
    def status(self):
        with self.app.store._connect() as db:
            active=db.execute('SELECT count(*) FROM health_episodes WHERE active=1').fetchone()[0]
            sample=db.execute('SELECT document FROM resource_samples ORDER BY at DESC LIMIT 1').fetchone()
        return {'last_check_at':self.last,'last_error':self.last_error,'capabilities':dict(self.capabilities),'core_read_latency_ms':getattr(self,'core_latency_ms',None),'active_findings':active,'resources':json.loads(sample[0]) if sample else None,'host_metrics':getattr(self,'host_metrics',None),'ai_required':False,'restart_proof':'Only explicit supported source evidence; a disconnected socket is not a restart.'}
    def _finding(self,key,kind,symptom,components,data,*,active=True):
        now=self.app.clock();serialized=canonical(data);fingerprint=hashlib.sha256(serialized.encode()).hexdigest()
        with self.app.store._connect() as db:
            row=db.execute('SELECT * FROM health_episodes WHERE key=?',(key,)).fetchone()
            old=db.execute('SELECT document FROM health_observations WHERE key=?',(key,)).fetchone()
            if not active:
                if row:db.execute('UPDATE health_episodes SET active=0 WHERE key=?',(key,))
                return
            changed=old is None or old[0]!=serialized
            episode=1 if row is None else row['episode']+(not row['active'])
            db.execute('INSERT OR REPLACE INTO health_observations VALUES(?,?,?)',(key,serialized,now))
            if row and row['active'] and not changed:return
        incident=self.app.store.open_incident(kind,symptom,components,now,correlation_key='health:'+key,occurrence_id=hashlib.sha256((key+':'+str(episode)).encode()).hexdigest())
        event_id=hashlib.sha256((key+':'+str(episode)+':'+fingerprint).encode()).hexdigest()
        with self.app.store._connect() as db:
            old=db.execute('SELECT observed_at FROM evidence WHERE source=? AND event_id=?',('native_system_health',event_id)).fetchone()
            db.execute('INSERT OR REPLACE INTO health_episodes VALUES(?,1,?,?)',(key,episode,incident['id']))
        self.app.store.add_evidence(incident['id'],{'source':'native_system_health','kind':kind,'event_id':event_id,'observed_at':old[0] if old else now,'payload':data})
        self.app.store.record(incident['id'],'deterministic_investigation',{'summary_cs':symptom+' Příčinu je potřeba ověřit cíleným čtením.','root_cause_proven':False})
        with self.app.store._connect() as db:update=db.execute("SELECT document,changed_at FROM health_observations WHERE key='last-update'").fetchone()
        if update and 0<=now-update[1]<=86400:
            self.app.store.record(incident['id'],'version_correlation',{'version_change':json.loads(update[0]),'changed_at':update[1],'causality_proven':False})
        if kind not in {'automation_reference','source_unavailable','application_failure'} and self.app.detection.snapshot()['autonomous_ai']:
            try:self.app.investigations.start(incident['id'],self.app.owner())
            except ValueError:pass
    def sample_resources(self):
        from .readiness import memory_available
        current=time.monotonic();cpu=time.process_time();elapsed=current-self._cpu[0]
        usage={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in __import__('pathlib').Path('/proc/self/status').read_text().splitlines() if ':' in line}
        data={'controller_rss_bytes':int(usage.get('VmRSS','0 kB').split()[0])*1024,'controller_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'available_bytes':memory_available(),'controller_cpu_percent':round(100*(cpu-self._cpu[1])/elapsed,2) if elapsed>0 else None,'worker_reserve_bytes':576*1024*1024,'raspberry_pi_measured':False}
        self._cpu=(current,cpu)
        with self.app.store._connect() as db:
            rows=db.execute("SELECT content FROM case_records WHERE kind='hermes_worker_runtime' ORDER BY id DESC LIMIT 20").fetchall()
            peaks=[json.loads(r[0]).get('peak_rss_bytes') for r in rows]
            data['worker_peak_rss_bytes']=max((x for x in peaks if type(x) is int),default=None)
            data['controller_scope']='current_controller_hosting_process'
            data['source']='Linux_proc_and_cgroup_plus_persisted_native_worker_receipts'
        with self.app.store._connect() as db:
            db.execute('INSERT OR REPLACE INTO resource_samples VALUES(?,?)',(self.app.clock(),canonical(data)))
            db.execute('DELETE FROM resource_samples WHERE at IN (SELECT at FROM resource_samples ORDER BY at DESC LIMIT -1 OFFSET 240)')
        return data
    def inspect(self):
        now=self.app.clock();resources=self.sample_resources();deadline=time.monotonic()+25
        available=resources['available_bytes']
        if type(available) is int:self._finding('memory-reserve','system_resource_pressure','Zbývá méně paměti než bezpečná rezerva pro Hermes. AI se nespustí; základní diagnostika pokračuje.',['hads_runtime'],{'worker_admission':'insufficient_memory_reserve','reserve_bytes':resources['worker_reserve_bytes']},active=available<resources['worker_reserve_bytes'])
        if self.app.core is None:
            self.last=now;self.last_error='Core není nakonfigurovaný; funkční poruchu z toho nelze dovodit.';return
        with self.app._read_lock:
            start=time.monotonic();config=self.app.core.config() if self.app.core else None
            config_ok=isinstance(config,dict) and isinstance(config.get('version'),str)
            failures=[] if config_ok else ['core_config']
            self.capabilities['core_config']='read' if config_ok else 'read_failed'
            if config_ok:
                with self.app.store._connect() as db:
                    old=db.execute("SELECT document FROM health_observations WHERE key='core-version'").fetchone()
                    previous=json.loads(old[0]) if old else None
                    db.execute("INSERT OR REPLACE INTO health_observations VALUES('core-version',?,?)",(canonical({'version':config['version']}),now))
                if previous and previous['version']!=config['version']:
                    # A version change is context, not a failure by itself.
                    with self.app.store._connect() as db:db.execute("INSERT OR REPLACE INTO health_observations VALUES('last-update',?,?)",(canonical({'from':previous['version'],'to':config['version']}),now))
            self.core_latency_ms=round((time.monotonic()-start)*1000,2)
            if self.app.supervisor:
                info=self.app.supervisor.info()
                if not isinstance(info,dict):failures.append('supervisor_info')
                self.capabilities['supervisor_info']='read' if isinstance(info,dict) else 'read_failed'
                host=self.app.supervisor.host_info() if hasattr(self.app.supervisor,'host_info') else None
                self.capabilities['host_metrics']='read' if isinstance(host,dict) else 'unavailable'
                if isinstance(host,dict):
                    import math
                    self.host_metrics={key:host[key] for key in ('disk_free','disk_total','disk_used') if type(host.get(key)) in {int,float} and math.isfinite(host[key]) and host[key]>=0}
                    self.host_metrics['unit']='GiB'
                    free,total=host.get('disk_free'),host.get('disk_total')
                    if type(free) in {int,float} and type(total) in {int,float} and math.isfinite(free) and math.isfinite(total) and 0<=free<=total and total>0:self._finding('disk-pressure','system_resource_pressure','Datový disk má méně než 1 GiB nebo 5 % volného místa.',['supervisor','recorder'],{'low_disk_space':True,'unit':'GiB'},active=free<1 or free/total<.05)
                apps=self.app.supervisor.apps()
                if isinstance(apps,dict) and isinstance(apps.get('addons'),list):
                    for item in apps['addons'][:64]:
                        if not isinstance(item,dict) or not isinstance(item.get('slug'),str):continue
                        slug=item['slug'];state=item.get('state')
                        # Even error/failed may follow an intentional stop. Preserve the
                        # observation; it alone neither proves impact nor authorizes AI.
                        self._finding('app:'+slug,'application_failure','Aplikace hlásí neúspěšný běh.',['supervisor',slug],{'slug':slug,'state':state,'version':item.get('version')},active=state in {'error','failed'})
            self._finding('native-api-access','source_unavailable','Nativní diagnostická API neposkytují ověřitelné údaje.',['homeassistant','supervisor'] if len(failures)>1 else failures,{'failed_sources':failures,'common_root_cause_proven':False},active=bool(failures))
            if self.app.core_ws:
                repairs=self.app.core_ws.repairs()
                if isinstance(repairs,dict) and isinstance(repairs.get('issues'),list):
                    seen=set()
                    for issue in repairs['issues'][:100]:
                        if not isinstance(issue,dict):continue
                        domain=issue.get('domain');identity=issue.get('issue_id');severity=str(issue.get('severity','')).lower()
                        if not isinstance(domain,str) or not isinstance(identity,str):continue
                        key='repair:'+domain+':'+identity;seen.add(key)
                        self._finding(key,'integration_repair','Home Assistant požaduje opravu integrace.',['integration:'+domain],{'domain':domain,'issue_id':identity,'severity':severity,'is_fixable':issue.get('is_fixable')},active=severity in {'error','critical'})
                    with self.app.store._connect() as db:
                        for row in db.execute("SELECT key FROM health_episodes WHERE key LIKE 'repair:%' AND active=1").fetchall():
                            if row[0] not in seen:db.execute('UPDATE health_episodes SET active=0 WHERE key=?',(row[0],))
                health=self.app.core_ws.system_health()
                domains=health.get('domains',{}) if isinstance(health,dict) else {}
                self.capabilities['system_health']='read' if isinstance(health,dict) and health.get('complete') else 'partial_or_unavailable'
                self.capabilities['recorder_health']='read' if 'recorder' in domains else 'not_exposed'
                for domain,value in list(domains.items())[:64]:
                    info=value.get('info',{}) if isinstance(value,dict) else {}
                    errors=[str(key)[:80] for key,result in info.items() if isinstance(result,dict) and result.get('error')]
                    self._finding('health:'+domain,'system_health_failure','System Health hlásí neúspěšný diagnostický výsledek.',['integration:'+domain],{'domain':domain,'failed_fields':errors},active=bool(errors))
                logs=self.app.core_ws.system_log()
                if isinstance(logs,list):
                    for row in logs[:100]:
                        if not isinstance(row,dict) or not str(row.get('name','')).startswith('homeassistant.components.recorder'):continue
                        stamp=row.get('timestamp',0)
                        if type(stamp) not in {int,float}:continue
                        active=str(row.get('level','')).upper() in {'ERROR','CRITICAL'} and type(row.get('count')) is int and row['count']>=2 and now-600<=stamp<=now+5
                        if active:self._finding('recorder-errors','recorder_failure','Recorder opakovaně hlásí čerstvou chybu.',['recorder'],{'component':'recorder','count':row['count'],'last_error_at':stamp,'database_failure_proven':False})
            # Explicit expected-on intent turns a disabled automation into a functional case.
            with self.app.store._connect() as db:targets=[r[0] for r in db.execute('SELECT entity_id FROM automation_intents WHERE expected_enabled=1 LIMIT 32')]
            for entity in targets:
                state=self.app.core.states(entity) if self.app.core else None
                if isinstance(state,dict):
                    self._finding('automation:'+entity,'automation_disabled','Očekávaná světelná automatizace je vypnutá.',[entity],{'entity_id':entity,'state':state.get('state'),'state_context':state.get('context',{}).get('id'),'expected_enabled':True},active=state.get('state')=='off')
            # Inspect configuration references in a rotating bounded batch; no log scanning.
            states=self.app.core.states() if self.app.core else None
            if isinstance(states,list):
                automations=[r for r in states if isinstance(r,dict) and str(r.get('entity_id','')).startswith('automation.')]
                batch=(automations[self._scan_cursor:]+automations[:self._scan_cursor])[:12]
                self._scan_cursor=(self._scan_cursor+len(batch))%max(1,len(automations))
                known={r.get('entity_id') for r in states if isinstance(r,dict)}
                for row in batch:
                    if time.monotonic()>deadline:break
                    identity=row.get('attributes',{}).get('id')
                    if not isinstance(identity,str):continue
                    config=self.app.core.automation_config(identity)
                    if not isinstance(config,dict):continue
                    for action in config.get('actions',[])[:8]:
                        target=action.get('target',{}).get('entity_id') if isinstance(action,dict) else None
                        if not isinstance(target,str) or not __import__('re').fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+',target):continue
                        if target in known:missing=False
                        else:
                            value=self.app.core.states(target);missing=value is None and self.app.core.status.last_response_status==404
                        self._finding('reference:'+identity+':'+target,'automation_reference','Automatizace odkazuje na entitu bez aktuálního stavu.',[row['entity_id'],target],{'automation_id':identity,'entity_id':target,'native_status':404},active=missing)
        zha=self.app.investigations.zha
        with self.app.store._connect() as db:status=db.execute('SELECT last_error,authenticated FROM zha_collector_status WHERE id=1').fetchone()
        self.capabilities['zha_capture']='read' if zha.capture is not None else 'unavailable'
        if status and status[0] and status[1]:self._finding('zha-subscription','diagnostic_capture_gap','Odběr ZHA událostí má doloženou mezeru.',['zha'],{'capture_gap':True,'physical_press_failure_proven':False})
        reader=self.app.investigations.broker.music
        if reader and reader.mapping:
            entity=next(iter(reader.mapping))
            try:
                result=reader.diagnostics(entity,'health',now-60,now)
                self.capabilities['music_assistant']='read' if result is not None else 'read_failed'
                if result and isinstance(result.get('data'),dict):
                    errors=result['data'].get('providers_error',0)
                    if type(errors) is int:self._finding('music-providers','music_provider_failure','Music Assistant hlásí nedostupné providery.',[entity],{'providers_error':errors},active=errors>0)
            except Exception:self.capabilities['music_assistant']='unavailable'
        else:self.capabilities['music_assistant']='not_configured'
        self.last=now;self.last_error=None
