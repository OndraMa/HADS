"""Authenticated controller orchestration around the existing guarded executor."""
from contextlib import closing
import json
import threading
import time
from datetime import datetime
from .managed_repair import ManagedReferenceEngine,MISSING,TARGET
from .repair import ApprovalAuthority,RepairBlocked,RepairPlan,connect
from .verification import FunctionalVerifier

class RepairService:
    def __init__(self,app):
        self.app=app;self.root=app.data_dir/'managed-repair';self.root.mkdir(mode=0o700,exist_ok=True)
        self.companion_checked_at=None;self.enabled=False;self.last_error=None;self.stop=threading.Event();self.thread=None
        self.state_breaks={};self.observations=[];self.lock=threading.RLock();self.trigger_coverage=None;self.trigger_heartbeat=None
        self.verification_checked_at=None;self.verification_cursor=0
        with app.store._connect() as db:db.execute('CREATE TABLE IF NOT EXISTS managed_repair_settings(id INTEGER PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0)');db.execute('INSERT OR IGNORE INTO managed_repair_settings VALUES(1,0)')
        with app.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS automation_intents(entity_id TEXT PRIMARY KEY,expected_enabled INTEGER NOT NULL,confirmed_at REAL NOT NULL,principal TEXT NOT NULL)')
        connect(app.store.db_path).close()

    def owner_only(self,principal):
        if not principal or principal!=self.app.owner():raise RepairBlocked('Tuto operaci smí potvrdit pouze vlastník.')

    def allow_automation(self,entity_id,principal):
        self.owner_only(principal)
        from .native_repair import AutomationEnableEngine
        with self.app._read_lock:
            engine=AutomationEnableEngine(self.app.store.db_path,self.root,self.app,entity_id)
            engine._read(engine.filename)
        with self.app.store._connect() as db:
            db.execute('INSERT OR REPLACE INTO automation_intents VALUES(?,1,?,?)',(entity_id,self.app.clock(),principal))
        self.start()

    def native_engine(self,plan):
        from .native_repair import AutomationEnableEngine
        entity=plan.document['target']['entity_id']
        with self.app.store._connect() as db:allowed=db.execute('SELECT expected_enabled FROM automation_intents WHERE entity_id=?',(entity,)).fetchone()
        if not allowed or not allowed[0]:raise RepairBlocked('Chybí aktuální záměr vlastníka, že automatizace má být zapnutá.')
        return AutomationEnableEngine(self.app.store.db_path,self.root,self.app,entity)

    def prepare_native(self,incident_id,entity,principal,*,exclusive=False):
        if exclusive is not True:raise RepairBlocked("Potvrď, že cílovou automatizaci nyní nikdo současně neupravuje.")
        self.owner_only(principal)
        if self.app.automation_writer is None:raise RepairBlocked('Nativní stavový vykonavatel není připojený.')
        with self.app.store._connect() as db:allowed=db.execute('SELECT expected_enabled FROM automation_intents WHERE entity_id=?',(entity,)).fetchone()
        case=self.app.store.case(incident_id)
        if not allowed or not allowed[0] or entity not in case['incident']['components']:raise RepairBlocked('Nejprve potvrď zamýšlené chování a načti důkazy tohoto cíle.')
        from .native_repair import AutomationEnableEngine
        with self.app._read_lock:
            engine=AutomationEnableEngine(self.app.store.db_path,self.root,self.app,entity)
            return engine.prepare_enable(incident_id,[e['evidence_id'] for e in case['evidence']])

    def engine(self):
        if not self.status()['enabled'] or self.app.core_ws is None:raise RepairBlocked('Nejprve povol izolovaný testovací katalog a ověř companion.')
        return ManagedReferenceEngine(self.app.store.db_path,self.root,self.app.core_ws.transport,owner=self.app.owner())

    def configure(self,enabled,principal):
        self.owner_only(principal)
        if type(enabled) is not bool:raise RepairBlocked('Neplatný souhlas.')
        if enabled:
            if self.app.core_ws is None:raise RepairBlocked('Core není dostupný.')
            try:value=self.app.core_ws.transport({'type':'hads_reference/read'})
            except Exception:raise RepairBlocked('Companion není dostupný nebo odmítl přístup. Katalog se nepovolil.') from None
            ManagedReferenceEngine._entity(value)
            self.companion_checked_at=self.app.clock()
        with self.app.store._connect() as db:db.execute('UPDATE managed_repair_settings SET enabled=? WHERE id=1',(int(enabled),))
        if enabled:self.start()

    def status(self):
        with self.app.store._connect() as db:
            enabled=bool(db.execute('SELECT enabled FROM managed_repair_settings WHERE id=1').fetchone()[0]);native_count=db.execute('SELECT count(*) FROM automation_intents WHERE expected_enabled=1').fetchone()[0]
            provider_pending=db.execute("SELECT count(*) FROM repair_executions e JOIN repair_plans p ON p.id=e.plan_id WHERE e.status='applied_verification_pending' AND json_extract(p.document,'$.operation')='tool.approved'").fetchone()[0]
        return {'enabled':enabled,'catalog':'owned_reference_and_selected_lighting','native_automation_writes':False,'native_state_targets':native_count,'native_config_writes':False,
            'provider_pending_verifications':provider_pending,
            'last_error':self.last_error,'companion_checked_at':self.companion_checked_at,'backup':'Ověřený snapshot jediné reference; není to záloha HAOS/OneDrive.',
            'one_drive_risky_operations':'blocked_no_independent_restore_proof'}

    def plans(self,incident_id):
        with closing(connect(self.app.store.db_path)) as db:
            rows=db.execute("SELECT p.id,p.document,e.status,e.id AS execution_id,(SELECT decision FROM repair_decisions d WHERE d.plan_id=p.id ORDER BY d.rowid DESC LIMIT 1) AS decision FROM repair_plans p LEFT JOIN repair_executions e ON e.plan_id=p.id WHERE json_extract(p.document,'$.incident_id')=? ORDER BY p.created_at DESC LIMIT 100",(incident_id,)).fetchall()
        result=[]
        for r in rows:
            document=json.loads(r['document'])
            if document['incident_id']==incident_id and document['operation'] in {'core_managed.replace_entity_reference','core.enable_lighting_automation','tool.approved'}:
                result.append({'plan_id':r['id'],'document':document,'status':r['status'],'execution_id':r['execution_id'],'decision':r['decision']})
        return result

    def plan(self,identity):
        with closing(connect(self.app.store.db_path)) as db:row=db.execute('SELECT document FROM repair_plans WHERE id=?',(identity,)).fetchone()
        if not row:raise RepairBlocked('Plán neexistuje.')
        return RepairPlan(row[0])

    def prepare(self,incident_id,principal):
        # Preserve the status of each native read across concurrent diagnostics.
        with self.app._read_lock:return self._prepare_locked(incident_id,principal)

    def _prepare_locked(self,incident_id,principal):
        self.owner_only(principal);case=self.app.store.case(incident_id)
        ids=[e['evidence_id'] for e in case['evidence']]
        if not ids:raise RepairBlocked('Nejprve získej důkazy funkční poruchy.')
        # This independent validator supports one exact managed test resource.
        engine=self.engine();original=json.loads(engine._read(engine.FILENAME))
        if engine._entity(original)!=MISSING:raise RepairBlocked('Testovací reference již není chybná.')
        old=self.app.core.states(MISSING) if self.app.core else None
        if old is not None or self.app.core is None or self.app.core.status.last_response_status!=404:raise RepairBlocked('Původní reference není doložená jako chybějící. Chyba připojení nebo oprávnění není důkaz neexistence.')
        state=self.app.core.states(TARGET) if self.app.core else None
        if not isinstance(state,dict) or state.get('state') not in {'off','on'}:raise RepairBlocked('Virtuální cíl není čitelný.')
        if 'input_boolean.hads_next_test_target' not in case['incident']['components'] and 'automation.hads_next_reference_test' not in case['incident']['components']:raise RepairBlocked('Tento spis se netýká podporované testovací automatizace.')
        jobs=self.app.investigations.for_case(incident_id)
        suggestion=(jobs[0].get('conclusion') or {}).get('repair_suggestion') if jobs else None
        if suggestion and suggestion.get('status')=='supported_managed_candidate':
            from .repair_suggestions import RepairSuggestion,prepare_reference_plan
            from .repair import canonical
            plan=prepare_reference_plan(RepairSuggestion(canonical(suggestion)),engine,engine.FILENAME,watch_seconds=10)
        else:
            plan=engine.prepare_entity_reference(incident_id,engine.FILENAME,MISSING,TARGET,ids,'Doložená vlastní testovací reference ukazuje na neexistující virtuální cíl.',watch_seconds=10)
        self.app.store.record(incident_id,'repair_plan_prepared',{'plan_id':plan.plan_id,'scope':'owned_virtual_reference'})
        return plan

    def decide(self,identity,decision,principal):
        self.owner_only(principal);plan=self.plan(identity)
        if plan.document.get('operation')=='tool.approved':raise RepairBlocked('Použij samostatné schválení nástroje s potvrzením výlučné práce s cílem.')
        authority=ApprovalAuthority(self.app.store.db_path,owner=self.app.owner())
        engine=None
        if decision=='approve':
            if self.trigger_coverage is None or self.app.clock()-(self.trigger_heartbeat or 0)>15:raise RepairBlocked('Neprobíhá ověřený odběr automatizace; oprava není připravená.')
            engine=self.native_engine(plan) if plan.document['operation']=='core.enable_lighting_automation' else self.engine()
            with self.app._read_lock:
                from .repair import digest
                if digest(engine._read(plan.document['target']['filename']))!=plan.document['original_sha256']:raise RepairBlocked('Předpoklady se změnily. Připrav nový plán a znovu jej schval.')
        token=authority.decide(plan,principal=principal,decision=decision)
        self.app.store.record(plan.document['incident_id'],'repair_decision',{'plan_id':identity,'decision':decision,'principal':principal})
        if decision!='approve':return None
        with self.app._read_lock:execution=engine.execute(plan,token,principal=principal)
        self.app.store.record(plan.document['incident_id'],'repair_applied',{'plan_id':identity,'execution_id':execution.execution_id,'summary_cs':('Stav automatizace změněn nativní službou. Konfigurace se nepřepisovala; funkční a fyzický výsledek čeká na test.' if plan.document['operation']=='core.enable_lighting_automation' else 'Reference změněna přes atomické CAS. Stiskni testovací tlačítko. Ověření čeká.')})
        return execution

    def confirm_physical(self,identity,principal):
        self.owner_only(principal);plan=self.plan(identity)
        if plan.document['operation']=='tool.approved':return self.app.approved_tools.confirm_physical(identity,principal)
        if plan.document['operation']!='core.enable_lighting_automation':raise RepairBlocked('Tento plán nevyžaduje potvrzení světla.')
        execution=self.native_engine(plan).execution(identity)
        if not execution or execution.status!='applied_verification_pending':raise RepairBlocked('Oprava nečeká na funkční potvrzení.')
        value={'kind':'owner_functional_confirmation','observed_at':self.app.clock(),'payload':{'entity_id':plan.document['verification']['entity_id'],'confirmed':True,'authority':'authenticated_owner'}}
        # Persist before restart; model output never reaches this path.
        FunctionalVerifier(self.app.store.db_path).evaluate(plan,execution,[value])
        with self.lock:self.observations.append(value)

    def rollback(self,identity,principal):
        self.owner_only(principal);plan=self.plan(identity)
        if plan.document['operation']=='tool.approved':raise RepairBlocked('Návrat nástroje potřebuje samostatný plán a nové potvrzení výlučné práce s cílem.')
        case=self.app.store.case(plan.document['incident_id']);evidence=[e['evidence_id'] for e in case['evidence']]
        if plan.document['operation']=='core.enable_lighting_automation':
            engine=self.native_engine(plan)
            execution=engine.execution(identity)
            if not execution or execution.status not in {'applied_verification_pending','verified','failed','recurred'}:raise RepairBlocked('Návrat vyžaduje doložený původní zásah bez neznámého výsledku.')
            with self.app._read_lock:
                if not engine._readback_matches(plan.document['proposed'],json.loads(engine._read(engine.filename))):raise RepairBlocked('Stav se od zásahu změnil; automatický návrat není připravený.')
                rollback=engine.prepare_enable(plan.document['incident_id'],evidence,rollback_of=plan.plan_id)
        else:rollback=self.engine().prepare_rollback(plan,evidence)
        self.app.store.record(plan.document['incident_id'],'rollback_prepared',{'plan_id':rollback.plan_id,'summary_cs':'Návrat aktivace vypne příjem dalších triggerů. Již rozsvícené světlo nevrací. Potřebuje nové schválení; neobnovuje HAOS.' if plan.document['operation']=='core.enable_lighting_automation' else 'Návrat vlastní reference vyžaduje samostatné nové schválení. Neobnovuje HAOS.'})
        return rollback

    def on_trigger(self,event):
        entity=event.get('data',{}).get('entity_id')
        tracked={'automation.hads_next_reference_test'}
        with self.app.store._connect() as db:tracked.update(r[0] for r in db.execute('SELECT entity_id FROM automation_intents WHERE expected_enabled=1'))
        with self.app.store._connect() as db:
            for row in db.execute("SELECT document FROM repair_plans WHERE json_extract(document,'$.operation')='tool.approved'"):
                d=json.loads(row[0])
                if d['binding']['tool']=='ha_config_set_automation':tracked.add(d['parameters']['entity_id'])
        if entity not in tracked:return
        try:stamp=datetime.fromisoformat(event['time_fired']).timestamp();context=event['context']['id']
        except (ValueError,KeyError,TypeError):return
        automation_id=entity.split('.',1)[1]
        with closing(connect(self.app.store.db_path)) as db:
            for row in db.execute('SELECT document FROM repair_plans ORDER BY created_at DESC LIMIT 100'):
                d=json.loads(row[0])
                if d['target'].get('entity_id')==entity and 'automation_id' in d['verification']:automation_id=d['verification']['automation_id'];break
        with self.lock:
            self.observations.append({'kind':'automation_triggered','observed_at':stamp,'payload':{'automation_id':automation_id,'automation_entity_id':entity,'context_id':context}});self.observations=self.observations[-256:]

    def observe_state(self,state,stamp):
        if hasattr(self.app,'approved_tools'):self.app.approved_tools.observe_state(state,stamp)
        if not state['entity_id'].startswith('light.') and state['entity_id']!=TARGET:return
        context=state.get('context',{}).get('id')
        with self.lock:
            if state['state']!='on':self.state_breaks[state['entity_id']]=stamp
            self.observations.append({'kind':'target_state','observed_at':stamp,'payload':{'entity_id':state['entity_id'],'state':state['state'],'context_id':context}});self.observations=self.observations[-256:]
        # A later legitimate off alone is not recurrence. A failed new trigger
        # is detected by the functional monitor, not by arbitrary state changes.

    def verify_pending(self):
        now=self.app.clock();detector=self.app.detection.health
        if detector['state']!='listening' or now-(detector['heartbeat_at'] or 0)>15:return
        if self.verification_checked_at is not None and now-self.verification_checked_at<10:return
        self.verification_checked_at=now
        with closing(connect(self.app.store.db_path)) as db:
            rows=db.execute("SELECT p.id,p.document FROM repair_plans p JOIN repair_executions e ON e.plan_id=p.id WHERE e.status='applied_verification_pending' ORDER BY e.started_at").fetchall()
        if rows:
            offset=self.verification_cursor%len(rows);rows=(rows[offset:]+rows[:offset])[:2];self.verification_cursor+=len(rows)
        for row in rows:
            plan=RepairPlan(row['document'])
            if plan.document['operation']=='tool.approved':
                try:self.app.approved_tools.verify(row['id'])
                except (ValueError,KeyError,TypeError,OSError,RuntimeError):pass
                continue
            if self.trigger_coverage is None or now-(self.trigger_heartbeat or 0)>15:continue
            if plan.document['operation'] not in {'core_managed.replace_entity_reference','core.enable_lighting_automation'}:continue
            engine=self.native_engine(plan) if plan.document['operation']=='core.enable_lighting_automation' else self.engine();execution=engine.execution(row['id'])
            if plan.document['rollback']['rollback_of']:
                # Exact readback is configuration rollback evidence, not a
                # functional success of the deliberately broken old reference.
                filename=plan.document['target']['filename']
                if engine._readback_matches(plan.document['proposed'],json.loads(engine._read(filename))):
                    with closing(connect(self.app.store.db_path)) as db:db.execute("UPDATE repair_executions SET status='rollback_reference_restored' WHERE id=?",(execution.execution_id,))
                    self.app.store.record(plan.document['incident_id'],'rollback_report',{'classification':'Návrat reference ověřen čtením; funkční problém trvá','plan_id':plan.plan_id,'haos_restored':False})
                continue
            with self.lock:observations=list(self.observations)
            target=plan.document['verification']['entity_id']
            current=self.app.core.states(target) if self.app.core else None
            if not isinstance(current,dict) or current.get('state')!=plan.document['verification']['state']:continue
            observations.append({'kind':'monitoring_checkpoint','observed_at':now,'payload':{'entity_id':target,'continuous_since':max(execution.completed_at,detector['continuous_since'] or now,self.trigger_coverage,self.state_breaks.get(target,0)),'healthy':True}})
            report=FunctionalVerifier(self.app.store.db_path).evaluate(plan,execution,observations)
            if report['classification']=='Vyřešeno a ověřeno':self.app.store.mark_resolved(plan.document['incident_id'],report)

    def on_functional_failure(self,incident_id,entity,stamp,identity):
        with closing(connect(self.app.store.db_path)) as db:
            rows=db.execute("SELECT p.id,p.document,e.id AS execution_id,e.status,e.completed_at FROM repair_plans p JOIN repair_executions e ON e.plan_id=p.id WHERE e.status='verified' OR (e.status='applied_verification_pending' AND json_extract(p.document,'$.operation')='tool.approved')").fetchall()
        for row in rows:
            plan=RepairPlan(row['document'])
            if plan.document['incident_id']!=incident_id or plan.document['verification']['entity_id']!=entity:continue
            if plan.document['operation']=='tool.approved':
                if row['completed_at'] is None or stamp<=row['completed_at']:continue
                status,classification=('recurred','Problém se opakoval') if row['status']=='verified' else ('failed','Oprava selhala')
                failure={'kind':'functional_failure','observed_at':stamp,'payload':{'entity_id':entity,'event_id':identity}}
                from .tool_registry import fingerprint
                with closing(connect(self.app.store.db_path)) as db:
                    db.execute('UPDATE repair_executions SET status=? WHERE plan_id=?',(status,row['id']))
                    db.execute('INSERT OR IGNORE INTO repair_observations VALUES(?,?,?)',(row['execution_id'],fingerprint(failure),json.dumps(failure,sort_keys=True)))
                self.app.store.record(incident_id,'functional_failure_after_provider_repair',{'plan_id':row['id'],'entity_id':entity,'observed_at':stamp,'event_id':identity})
                report=self.app.approved_tools.report(plan,row['execution_id'],classification,observations=[failure])
                self.app.store.reopen_for_report(incident_id,report)
                continue
            if plan.document['operation'] not in {'core_managed.replace_entity_reference','core.enable_lighting_automation'}:continue
            engine=self.native_engine(plan) if plan.document['operation']=='core.enable_lighting_automation' else self.engine();execution=engine.execution(row['id'])
            report=FunctionalVerifier(self.app.store.db_path).evaluate(plan,execution,[{'kind':'functional_failure','observed_at':stamp,'payload':{'entity_id':entity,'event_id':identity}}])
            self.app.store.reopen_for_report(incident_id,report)

    def start(self):
        transport=getattr(self.app.core_ws,'transport',None)
        if not callable(getattr(transport,'automation_events',None)):return False
        if self.thread and self.thread.is_alive():return True
        self.stop.clear()
        def ready():self.trigger_coverage=self.app.clock();self.trigger_heartbeat=self.app.clock()
        def heartbeat():
            now=self.app.clock()
            if self.trigger_heartbeat is not None and now-self.trigger_heartbeat>15:self.trigger_coverage=now
            self.trigger_heartbeat=now
        def run():
            while not self.stop.is_set():
                try:transport.automation_events(self.stop,self.on_trigger,ready,heartbeat)
                except Exception:self.last_error='Odběr spuštění automatizace není dostupný.'
                self.trigger_coverage=None
                if self.stop.wait(10):break
        self.thread=threading.Thread(target=run,daemon=True,name='hads-repair-verification');self.thread.start();return True

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=3)
