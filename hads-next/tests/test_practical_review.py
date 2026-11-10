import copy,json,tempfile,time,unittest
from pathlib import Path
from datetime import datetime,timezone
from hads_next.haos_application import Application
from hads_next.native_repair import lighting_policy,AutomationStateTransport
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
