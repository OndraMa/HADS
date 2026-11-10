import copy,json,tempfile,time,unittest
from pathlib import Path
from datetime import datetime,timezone
from hads_next.haos_application import Application
from hads_next.native_repair import lighting_policy,AutomationStateTransport,AutomationEnableEngine
from hads_next.repair import RepairBlocked

class NativePolicyTests(unittest.TestCase):
    def setUp(self):self.config={'id':'123456789','triggers':[{'trigger':'state','entity_id':'binary_sensor.hall_motion','to':'on'}],'actions':[{'action':'light.turn_on','target':{'entity_id':'light.hall'}}]}
    def test_useful_non_HADS_lighting_policy_and_risky_actions_are_rejected(self):
        self.assertEqual(lighting_policy(self.config),('binary_sensor.hall_motion','light.hall'))
        for changes in [ {'action':'lock.unlock','target':{'entity_id':'lock.door'}},{'action':'switch.turn_on','target':{'entity_id':'switch.heater'}},{'action':'light.turn_on','target':{'entity_id':'{{ secret }}'}},{'action':'light.turn_on','target':{'area_id':'bedroom'}},{'action':'light.turn_on','target':{'entity_id':'light.hall'},'data':{'brightness':255}}]:
            config=copy.deepcopy(self.config);config['actions']=[changes]
            with self.assertRaises(RepairBlocked):lighting_policy(config)
        config=copy.deepcopy(self.config);config['initial_state']=False
        with self.assertRaises(RepairBlocked):lighting_policy(config)
    def test_state_writer_is_not_a_general_service_or_url_proxy(self):
        writer=AutomationStateTransport('https://ha.example','not-a-real-token')
        for target in ('light.hall','automation.hall/../../restart','http://evil','automation.hall?x=1'):
            with self.assertRaises(RepairBlocked):writer.set_enabled(target,True)
        with self.assertRaises(ValueError):AutomationStateTransport('http://remote.example','test')

class MonitoringReviewTests(unittest.TestCase):
    def test_already_satisfied_response_and_wrong_trigger_edge_are_not_failures(self):
        with tempfile.TemporaryDirectory() as d:
            now=[100.];app=Application(d,clock=lambda:now[0]);app.enroll_owner('owner');engine=app.detection;engine.ready()
            engine.configure({'entity_id':'light.hall','kind':'response','trigger_entity':'binary_sensor.motion','trigger_state':'on','expected':'on','grace_seconds':5},'owner')
            def event(entity,old,new):return {'event_type':'state_changed','time_fired':datetime.fromtimestamp(now[0],timezone.utc).isoformat(),'data':{'entity_id':entity,'old_state':{'state':old},'new_state':{'entity_id':entity,'state':new,'last_updated':'now','context':{}}}}
            engine.ingest(event('binary_sensor.motion','on','off'));now[0]+=6;engine.heartbeat();engine.tick();self.assertEqual(app.snapshot()['cases'],[])
            engine.ingest(event('light.hall','off','on'));engine.ingest(event('binary_sensor.motion','off','on'));now[0]+=6;engine.heartbeat();engine.tick();self.assertEqual(app.snapshot()['cases'],[])
            app.detection.close()
    def test_heartbeat_stall_cannot_extend_verifiable_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            now=[100.];app=Application(d,clock=lambda:now[0]);app.enroll_owner('owner');engine=app.detection;engine.ready();engine.configure({'entity_id':'light.hall','kind':'state','expected':'on','grace_seconds':30},'owner')
            event={'event_type':'state_changed','time_fired':datetime.fromtimestamp(100,timezone.utc).isoformat(),'data':{'entity_id':'light.hall','old_state':{'state':'on'},'new_state':{'entity_id':'light.hall','state':'off','context':{}}}}
            engine.ingest(event);now[0]=140;engine.heartbeat();engine.tick()
            self.assertEqual(app.snapshot()['cases'],[]);self.assertEqual(engine.health['continuous_since'],140);app.detection.close()

class AcceptanceTests(unittest.TestCase):
    def test_export_never_contains_raw_household_details_or_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            app=Application(d);app.enroll_owner('owner@example.invalid');session=app.acceptance.create(app.owner(),isolated_confirmed=True)
            with app.store._connect() as db:db.execute("UPDATE acceptance_steps SET details=? WHERE session_id=?",(json.dumps({'api_key':'VERY_PRIVATE_TOKEN','entity_id':'light.private_room','endpoint':'https://private.local','logs':'sensitive household'}),session))
            value=json.dumps(app.acceptance.export(session));self.assertNotIn('VERY_PRIVATE_TOKEN',value);self.assertNotIn('private_room',value);self.assertNotIn('private.local',value);self.assertNotIn(app.owner(),value);self.assertFalse(app.acceptance.export(session)['all_steps_passed']);app.detection.close()
    def test_single_model_probe_requires_consent_and_shared_daily_budget_and_cannot_replay(self):
        with tempfile.TemporaryDirectory() as d:
            app=Application(d);app.enroll_owner('owner');session=app.acceptance.create('owner',isolated_confirmed=True);calls=[]
            class Provider:
                def sender(self):return 'test-model',lambda body:calls.append(body) or {'choices':[{'message':{'content':'test'}}]}
                def public_status(self):return {'configured':True,'enabled':True,'model':'test-model'}
            app.investigations.provider=Provider()
            app.acceptance._model_test(session,{'cost_consent':False});self.assertEqual(calls,[])
            app.acceptance._model_test(session,{'cost_consent':True});self.assertEqual(len(calls),1)
            with self.assertRaises(RepairBlocked):app.acceptance.run(session,'model','owner',{'cost_consent':True})
            with app.store._connect() as db:self.assertEqual(db.execute('SELECT sum(count) FROM investigation_daily_usage').fetchone()[0],1)
            app.detection.close()

class NativeExecutionReviewTests(unittest.TestCase):
    def test_initial_unknown_button_is_valid_but_unavailable_is_blocked_and_changed_plan_cannot_execute(self):
        from hads_next.repair import ApprovalAuthority
        with tempfile.TemporaryDirectory() as d:
            app=Application(d);app.enroll_owner('owner');calls=[]
            class Core:
                state='off';button='unknown';changed='original'
                def states(self,entity):
                    if entity=='automation.entry':return {'state':self.state,'attributes':{'id':'173100000001','current':0},'last_changed':self.changed,'context':{'id':self.changed}}
                    return {'state':self.button if entity=='input_button.entry' else 'off'}
                def automation_config(self,identity):return {'id':'173100000001','triggers':[{'trigger':'state','entity_id':'input_button.entry'}],'actions':[{'action':'light.turn_on','target':{'entity_id':'light.entry'}}]}
            core=Core();app.core=core
            class Writer:
                def set_enabled(self,entity,enabled):calls.append((entity,enabled));core.state='on' if enabled else 'off';core.changed='written'
            app.automation_writer=Writer();engine=AutomationEnableEngine(app.store.db_path,app.repairs.root,app,'automation.entry')
            plan=engine.prepare_enable('case',['evidence'])
            self.assertFalse(plan.document['original']['enabled']);self.assertTrue(plan.document['non_atomic_state_service'])
            core.button='unavailable'
            with self.assertRaises(RepairBlocked):engine._read(engine.filename)
            core.button='unknown';authority=ApprovalAuthority(app.store.db_path,owner='owner')
            with self.assertRaises(RepairBlocked):engine.execute(plan,'forged-token',principal='owner')
            self.assertEqual(calls,[])
            token=authority.approve(plan,principal='owner');core.changed='changed-after-approval'
            with self.assertRaises(RepairBlocked):engine.execute(plan,token,principal='owner')
            self.assertEqual(calls,[])
            fresh=engine.prepare_enable('case',['evidence']);token=authority.approve(fresh,principal='owner');execution=engine.execute(fresh,token,principal='owner')
            self.assertEqual(execution.status,'applied_verification_pending');self.assertEqual(calls,[('automation.entry',True)])
            restarted=AutomationEnableEngine(app.store.db_path,app.repairs.root,app,'automation.entry')
            with self.assertRaises(RepairBlocked):restarted.execute(fresh,token,principal='owner')
            self.assertEqual(len(calls),1);app.detection.close()

class SystemInspectionReviewTests(unittest.TestCase):
    def test_repeated_health_reads_do_not_create_occurrences_and_recovery_reopens_same_case(self):
        with tempfile.TemporaryDirectory() as d:
            now=[100.];app=Application(d,clock=lambda:now[0]);app.enroll_owner('owner')
            system=app.system
            system._finding('dns','network_failure','Doložený výpadek DNS',['dns'],{'reachable':False})
            case=app.snapshot()['cases'][0];first=app.store.case(case['id'])
            now[0]+=30;system._finding('dns','network_failure','Doložený výpadek DNS',['dns'],{'reachable':False})
            self.assertEqual(app.store.case(case['id'])['occurrences'],first['occurrences']);self.assertEqual(len(app.store.case(case['id'])['evidence']),1)
            system._finding('dns','network_failure','Doložený výpadek DNS',['dns'],{},active=False)
            now[0]+=30;system._finding('dns','network_failure','Doložený výpadek DNS',['dns'],{'reachable':False})
            self.assertEqual(len(app.snapshot()['cases']),1);self.assertEqual(len(app.store.case(case['id'])['evidence']),2);app.detection.close()
    def test_changed_model_settings_invalidate_green_connectivity_result(self):
        with tempfile.TemporaryDirectory() as d:
            app=Application(d);app.enroll_owner('owner');session=app.acceptance.create('owner',isolated_confirmed=True)
            provider=app.investigations.provider;before=provider.fingerprint()
            app.acceptance._set(session,'model','passed','observed',{'provider_fingerprint':before})
            provider.configure(endpoint='https://provider.invalid/v1/chat/completions',model='test',api_key='PRIVATE_TEST_KEY',consent=True,principal='owner')
            self.assertEqual(app.acceptance.session(session)['steps'][5]['status'],'pending');app.detection.close()

class CoverageConfirmationReviewTests(unittest.TestCase):
    def test_confirmation_from_before_a_gap_cannot_confirm_a_new_functional_attempt(self):
        from hads_next.repair import RepairEngine,ApprovalAuthority
        from hads_next.verification import FunctionalVerifier
        class PhysicalEngine(RepairEngine):
            def _register_plan(self,document,raw):
                document['verification']['physical_confirmation_required']=True
                return super()._register_plan(document,raw)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'automation.json').write_text(json.dumps({'id':'button','action':{'service':'light.turn_on','target':{'entity_id':'light.old'}}}))
            engine=PhysicalEngine(root/'case.sqlite',root,allowed_files={'automation.json'},clock=lambda:100)
            plan=engine.prepare_entity_reference('case','automation.json','light.old','light.entry',['proof'],'Exact supported fixture',watch_seconds=30)
            token=ApprovalAuthority(engine.db_path,clock=lambda:100).approve(plan,principal='owner');execution=engine.execute(plan,token,principal='owner');verifier=FunctionalVerifier(engine.db_path)
            observations=[]
            for trigger,target,context in [(101,102,'before-gap'),(120,121,'after-gap')]:
                observations.extend([{'kind':'automation_triggered','observed_at':trigger,'payload':{'automation_id':'button','context_id':context}},{'kind':'target_state','observed_at':target,'payload':{'entity_id':'light.entry','state':'on','context_id':context}}])
            confirmation=lambda stamp:{'kind':'owner_functional_confirmation','observed_at':stamp,'payload':{'entity_id':'light.entry','confirmed':True,'authority':'authenticated_owner'}}
            checkpoint=lambda stamp:{'kind':'monitoring_checkpoint','observed_at':stamp,'payload':{'entity_id':'light.entry','continuous_since':120,'healthy':True}}
            report=verifier.evaluate(plan,execution,observations+[confirmation(103),checkpoint(152)],now=152)
            self.assertNotEqual(report['classification'],'Vyřešeno a ověřeno')
            report=verifier.evaluate(plan,execution,[confirmation(153),checkpoint(154)],now=154)
            self.assertEqual(report['classification'],'Vyřešeno a ověřeno')

class ScopedAutomationIdentityTests(unittest.TestCase):
    def test_native_numeric_id_is_resolved_from_scoped_entity_and_unrelated_trace_is_denied(self):
        from hads_next.observability import CoreReader,CoreWSReader
        from hads_next.evidence_broker import BrokerDenied
        with tempfile.TemporaryDirectory() as d:
            app=Application(d);calls=[]
            def read(path):
                calls.append(path)
                if path=='/api/states/automation.entry':return {'entity_id':'automation.entry','state':'off','attributes':{'id':'173100000001'}}
                if path=='/api/config/automation/config/173100000001':return {'id':'173100000001','triggers':[],'actions':[]}
                raise AssertionError(path)
            app.investigations.broker.core=CoreReader(read)
            case=app.store.open_incident('automation_disabled','Světlo nereaguje',['automation.entry'],time.time())['id'];broker=app.investigations.broker
            with self.assertRaises(BrokerDenied):broker.read(case,'hads_get_automation_traces',{'automation_id':'other'})
            self.assertEqual(calls,[])
            result=broker.read(case,'hads_get_automation_config',{'automation_id':'entry'})
            self.assertEqual(result['data']['id'],'173100000001');self.assertIn('/api/config/automation/config/173100000001',calls)
            app.detection.close()
