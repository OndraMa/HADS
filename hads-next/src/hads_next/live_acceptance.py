"""Owner-driven, persistent acceptance. Reports are allowlisted and pseudonymized."""
import hashlib,hmac,json,secrets,threading,time,uuid
from .evidence import canonical
from .repair import RepairBlocked

STEPS=[('installation','Instalace a první spuštění'),('identity','Přihlášení administrátora'),('sources','Core a Supervisor'),('logs','Skutečný protokol vybrané aplikace'),('runtime','Původní Hermes bez modelu'),('model','Jednorázový test poskytovatele'),('manual','Ručně nahlášený incident'),('automatic','Automaticky zachycený incident'),('device','Music Assistant nebo ZHA'),('repair','Podporovaný opravný zásah'),('verification','Funkční výsledek a report'),('restart','Restart a persistence')]
REASONS={'waiting':'Čeká na konkrétní test.','observed':'Konkrétní čtení nebo funkční důkaz byl ověřen.','missing_source':'Zdroj není připojený nebo neposkytuje potřebná data.','read_failed':'Zdroj odmítl čtení. Ověř připojení a oprávnění; ostatní diagnostika pokračuje.','needs_case':'Vyber existující skutečný spis odpovídajícího typu.','needs_effect':'Nejprve schval podporovanou opravu a proveď požadovaný funkční test.','same_instance':'Restart zatím nebyl doložen novou instancí aplikace.','model_not_authorized':'Model vyžaduje vlastní nastavení a explicitní souhlas s jedním možným placeným voláním.','model_unknown':'Výsledek modelového volání nebo jeho účtování není jistý. Automatické opakování je zakázané.','busy':'Jiná kontrola právě probíhá.','failed':'Test selhal. Otevři odpovídající zdroj a zkontroluj jeho skutečný stav.'}

class LiveAcceptance:
    def __init__(self,app):
        self.app=app;self.instance=uuid.uuid4().hex;self.lock=threading.Lock()
        with app.store._connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS acceptance_sessions(id TEXT PRIMARY KEY,created_at REAL NOT NULL,instance TEXT NOT NULL,operator_scope TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS acceptance_steps(session_id TEXT NOT NULL,step TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,at REAL,details TEXT NOT NULL,PRIMARY KEY(session_id,step));
            CREATE TABLE IF NOT EXISTS acceptance_model_tests(session_id TEXT PRIMARY KEY,state TEXT NOT NULL,fingerprint TEXT NOT NULL);''')
            key=db.execute("SELECT value FROM application_settings WHERE key='acceptance_export_key'").fetchone()
            if not key:db.execute("INSERT INTO application_settings VALUES('acceptance_export_key',?)",(secrets.token_hex(32),))
    def _owner(self,principal):
        if not principal or principal!=self.app.owner():raise RepairBlocked('Přejímku může řídit pouze ověřený vlastník.')
    def create(self,principal,*,isolated_confirmed=False):
        self._owner(principal)
        if isolated_confirmed is not True:raise RepairBlocked('Potvrď oddělené testovací prostředí.')
        identity=uuid.uuid4().hex
        with self.app.store._connect() as db:
            if db.execute('SELECT count(*) FROM acceptance_sessions').fetchone()[0]>=30:raise RepairBlocked('Limit 30 přejímek. Nejprve exportuj a archivuj starší protokoly.')
            db.execute('INSERT INTO acceptance_sessions VALUES(?,?,?,?)',(identity,self.app.clock(),self.instance,'operator_declared_isolated_environment'))
            for step,_ in STEPS:db.execute('INSERT INTO acceptance_steps VALUES(?,?,\'pending\',\'waiting\',NULL,\'{}\')',(identity,step))
        return identity
    def session(self,identity):
        with self.app.store._connect() as db:
            row=db.execute('SELECT * FROM acceptance_sessions WHERE id=?',(identity,)).fetchone()
            if not row:raise RepairBlocked('Přejímka neexistuje.')
            steps={r['step']:dict(r) for r in db.execute('SELECT * FROM acceptance_steps WHERE session_id=?',(identity,))}
        return {'session':dict(row),'steps':[{**steps[s],'label':label,'explanation':REASONS.get(steps[s]['reason'],REASONS['failed'])} for s,label in STEPS]}
    def _set(self,identity,step,status,reason,details=None):
        if status not in {'passed','failed','unavailable','pending'}:raise ValueError('Neplatný stav.')
        with self.app.store._connect() as db:db.execute('UPDATE acceptance_steps SET status=?,reason=?,at=?,details=? WHERE session_id=? AND step=?',(status,reason,self.app.clock(),canonical(details or {}),identity,step))
    def run(self,identity,step,principal,arguments=None):
        self._owner(principal);self.session(identity)
        if step not in dict(STEPS):raise RepairBlocked('Nepodporovaný krok.')
        if not self.lock.acquire(blocking=False):raise RepairBlocked('Přejímkový test právě běží.')
        if step=='model':
            with self.app.store._connect() as db:used=db.execute('SELECT 1 FROM acceptance_model_tests WHERE session_id=?',(identity,)).fetchone()
            if used:
                self.lock.release();raise RepairBlocked('Tato přejímka již modelový test zahájila. Výsledek se automaticky neopakuje; nový vědomý pokus vyžaduje novou přejímku.')
        arguments=arguments or {};self._set(identity,step,'pending','waiting')
        def work():
            try:self._exercise(identity,step,arguments)
            except Exception:self._set(identity,step,'failed','failed')
            finally:self.lock.release()
        threading.Thread(target=work,daemon=True,name='hads-live-acceptance').start()
    def _exercise(self,identity,step,args):
        app=self.app
        if step in {'installation','identity'}:
            if step=='installation':
                from pathlib import Path
                try:manifest=json.loads(Path('/app/PACKAGE_MANIFEST.json').read_text());ok=manifest.get('version')==app.snapshot()['version']
                except (OSError,ValueError):ok=False
            else:ok=True
            self._set(identity,step,'passed' if ok else 'unavailable','observed' if ok else 'missing_source',{'private_storage':app.data_dir.is_dir(),'owner_authenticated':True,'instance':self.instance});return
        if step=='sources':
            sources=app.check_sources();ok=all(sources.get(k,{}).get('read_succeeded') for k in ('core_config','supervisor','haos'))
            self._set(identity,step,'passed' if ok else 'unavailable','observed' if ok else 'missing_source',{'reads':{k:bool(v['read_succeeded']) for k,v in sources.items()}});return
        if step=='logs':
            slug=args.get('slug','')
            if slug not in {a['slug'] for a in app.snapshot()['applications']} or app.supervisor is None:self._set(identity,step,'unavailable','missing_source');return
            with app._read_lock:data=app.supervisor.app_logs(slug)
            self._set(identity,step,'passed' if isinstance(data,str) and bool(data.strip()) else 'unavailable','observed' if data else 'read_failed',{'application':slug,'characters':len(data) if isinstance(data,str) else 0});return
        if step=='runtime':
            app.investigations.request_probe(app.owner())
            for _ in range(180):
                value=app.investigations.status()['runtime_probe']
                if value['state']!='running':break
                time.sleep(1)
            ok=value['state']=='ready';self._set(identity,step,'passed' if ok else 'unavailable','observed' if ok else 'missing_source',{'native_runtime_ready':ok});return
        if step=='model':self._model_test(identity,args);return
        if step in {'manual','automatic'}:
            key=args.get('incident_id');case=app.store.case(key)
            allowed=case['incident']['kind']=='manual_functional' if step=='manual' else case['incident']['kind'] not in {'manual_functional','imported_history'}
            ok=allowed and any(not x['source'].startswith('import:') for x in case['evidence'])
            self._set(identity,step,'passed' if ok else 'pending','observed' if ok else 'needs_case',{'incident':key,'native_evidence_count':len(case['evidence'])});return
        if step=='device':
            zha=app.investigations.zha;reader=app.investigations.music.reader();ok=False;source='zha'
            if zha.capture is not None:
                with app.store._connect() as db:ok=bool(db.execute('SELECT 1 FROM zha_observations WHERE observed_at>=? LIMIT 1',(self.session(identity)['session']['created_at'],)).fetchone())
            if not ok and reader:
                mapping=app.investigations.music.public_status()['mapping']
                if mapping:
                    entity=next(iter(mapping));value=reader.diagnostics(entity,'health',app.clock()-60,app.clock());ok=value is not None;source='music_assistant'
            self._set(identity,step,'passed' if ok else 'unavailable','observed' if ok else 'missing_source',{'source':source,'physical_result_verified':False});return
        if step in {'repair','verification'}:
            plans=app.repairs.plans(args.get('incident_id',''))
            valid=[p for p in plans if p['document']['operation']=='core.enable_lighting_automation' and p['status'] is not None]
            ok=any(p['status']=='verified' for p in valid) if step=='verification' else any(p['status'] in {'applied_verification_pending','verified'} for p in valid)
            self._set(identity,step,'passed' if ok else 'pending','observed' if ok else 'needs_effect',{'native_operation':'core.enable_lighting_automation','plan_count':len(valid)});return
        if step=='restart':
            session=self.session(identity)['session'];ok=session['instance']!=self.instance
            self._set(identity,step,'passed' if ok else 'pending','observed' if ok else 'same_instance',{'new_instance_observed':ok});return
    def _model_test(self,identity,args):
        if args.get('cost_consent') is not True:self._set(identity,'model','unavailable','model_not_authorized');return
        provider=self.app.investigations.provider
        try:model,sender=provider.sender()
        except ValueError:self._set(identity,'model','unavailable','model_not_authorized');return
        fingerprint=hashlib.sha256(canonical(provider.public_status()).encode()).hexdigest()
        with self.app.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM acceptance_model_tests WHERE session_id=?',(identity,)).fetchone():raise RepairBlocked('Modelový test už byl zahájen.')
            day=int(self.app.clock()//86400);count=db.execute('SELECT count FROM investigation_daily_usage WHERE day=?',(day,)).fetchone()
            if count and count[0]>=12:raise RepairBlocked('Denní limit modelu.')
            db.execute('INSERT INTO investigation_daily_usage VALUES(?,1) ON CONFLICT(day) DO UPDATE SET count=count+1',(day,))
            db.execute("INSERT INTO acceptance_model_tests VALUES(?,'intent',?)",(identity,fingerprint))
        try:
            result=sender({'messages':[{'role':'user','content':'Odpověz krátce česky, že komunikační test proběhl. Nemáš data domácnosti, neurčuj žádnou diagnózu ani nevolej nástroje.'}]})
            ok=bool(result.get('choices'))
            with self.app.store._connect() as db:db.execute("UPDATE acceptance_model_tests SET state='response' WHERE session_id=?",(identity,))
            self._set(identity,'model','passed' if ok else 'failed','observed' if ok else 'failed',{'provider_fingerprint':fingerprint,'requests':1,'hermes_reasoning_proven':False})
        except Exception:
            with self.app.store._connect() as db:db.execute("UPDATE acceptance_model_tests SET state='unknown' WHERE session_id=?",(identity,))
            self._set(identity,'model','failed','model_unknown',{'requests':1,'retry_automatic':False})
    def export(self,identity):
        session=self.session(identity)
        with self.app.store._connect() as db:key=db.execute("SELECT value FROM application_settings WHERE key='acceptance_export_key'").fetchone()[0].encode()
        opaque=lambda v:hmac.new(key,str(v).encode(),hashlib.sha256).hexdigest()[:16]
        # No raw logs, prompts, summaries, endpoints, entities, user IDs or settings.
        steps=[{'step':r['step'],'status':r['status'],'reason_code':r['reason'],'explanation_cs':r['explanation'],'at':r['at']} for r in session['steps']]
        resources=self.app.system.status()['resources']
        return {'schema':1,'scope':session['session']['operator_scope'],'independent_live_HAOS_proof':False,'session':opaque(identity),'steps':steps,'resources':resources,'model_test_proves':'connectivity_only','real_model_investigation':'requires_actual_case_and_citation_review','all_steps_passed':all(s['status']=='passed' for s in steps),'tokens_or_raw_household_content_included':False}
