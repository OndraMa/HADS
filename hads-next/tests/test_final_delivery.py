import copy,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from hads_next.haos_application import Application
from hads_next.managed_repair import ManagedReferenceEngine,MISSING,TARGET
from hads_next.repair import RepairBlocked,ApprovalAuthority
from hads_next.migration import import_case

class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=[100.];self.app=Application(self.temp.name,clock=lambda:self.now[0]);self.app.enroll_owner('owner');self.engine=self.app.detection;self.engine.ready()
    def tearDown(self):self.app.detection.close();self.temp.cleanup()
    def event(self,old,new):
        stamp=datetime.fromtimestamp(self.now[0],timezone.utc).isoformat()
        return {'event_type':'state_changed','time_fired':stamp,'data':{'entity_id':'media_player.radio','old_state':{'state':old},'new_state':{'entity_id':'media_player.radio','state':new,'last_updated':stamp,'context':{'id':'context'}}}}
    def test_playback_episode_dedup_recurs_only_after_recovery_and_survives_database_restart(self):
        self.engine.configure({'entity_id':'media_player.radio','kind':'playback','expected':'playing','grace_seconds':5},'owner')
        self.engine.ingest(self.event('off','idle'));self.now[0]+=6;self.engine.heartbeat();self.engine.tick();self.assertEqual(self.app.snapshot()['cases'],[])
        self.engine.ingest(self.event('playing','idle'));self.now[0]+=6;self.engine.heartbeat();self.engine.tick();self.engine.tick()
        case=self.app.snapshot()['cases'][0];self.assertEqual(case['occurrence_count'],1)
        self.engine.ingest(self.event('idle','playing'));self.now[0]+=1;self.engine.ingest(self.event('playing','idle'));self.now[0]+=6;self.engine.heartbeat();self.engine.tick()
        self.assertEqual(self.app.snapshot()['cases'][0]['occurrence_count'],2)
        restarted=Application(self.temp.name,clock=lambda:self.now[0]);self.assertEqual(len(restarted.detection.rules()),1);self.assertEqual(restarted.snapshot()['cases'][0]['occurrence_count'],2);self.assertFalse(restarted.detection.snapshot()['autonomous_ai'])
    def test_gap_never_proves_a_sustained_failure_and_wrong_owner_cannot_enable_paid_work(self):
        self.engine.configure({'entity_id':'media_player.radio','kind':'state','expected':'playing','grace_seconds':5},'owner');self.engine.ingest(self.event('playing','idle'))
        self.engine.gap('test disconnect');self.now[0]+=20;self.engine.ready();self.engine.tick();self.assertEqual(self.app.snapshot()['cases'],[])
        with self.assertRaises(ValueError):self.engine.consent(True,'intruder')

class ManagedExecutorTests(unittest.TestCase):
    def test_existing_authority_exact_snapshot_revision_guard_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'locks';root.mkdir(mode=0o700)
            state={'id':'hads_next_reference_test','revision':0,'scope':'integration_owned_virtual_test_reference','action':{'service':'input_boolean.turn_on','target':{'entity_id':MISSING}}}
            def transport(command):
                if command['type']=='hads_reference/read':return copy.deepcopy(state)
                if command['type']!='hads_reference/cas' or command['expected_revision']!=state['revision'] or command['expected_entity']!=state['action']['target']['entity_id']:raise RepairBlocked('stale')
                state['revision']+=1;state['action']['target']['entity_id']=command['entity_id'];return copy.deepcopy(state)
            engine=ManagedReferenceEngine(Path(tmp)/'db',root,transport,owner='owner')
            plan=engine.prepare_entity_reference('case',engine.FILENAME,MISSING,TARGET,['proof'],'Podložená testovací reference.')
            with self.assertRaises(RepairBlocked):engine.execute(plan,'not-approved',principal='owner')
            authority=ApprovalAuthority(engine.db_path,owner='owner');token=authority.approve(plan,principal='owner')
            self.assertEqual(engine.execute(plan,token,principal='owner').status,'applied_verification_pending')
            with self.assertRaises(RepairBlocked):engine.execute(plan,token,principal='owner')
            self.assertEqual(state['revision'],1)
            rollback=engine.prepare_rollback(plan,['proof']);new_token=authority.approve(rollback,principal='owner');engine.execute(rollback,new_token,principal='owner')
            self.assertEqual(state['action']['target']['entity_id'],MISSING);self.assertEqual(state['revision'],2)
    def test_no_state_without_native_404_cannot_prepare_a_plan(self):
        from hads_next.observability import CoreReader,CoreWSReader
        with tempfile.TemporaryDirectory() as tmp:
            core=CoreReader(lambda _:None)
            reference={'id':'hads_next_reference_test','revision':0,'scope':'integration_owned_virtual_test_reference','action':{'service':'input_boolean.turn_on','target':{'entity_id':MISSING}}}
            app=Application(tmp,core,core_ws=CoreWSReader(lambda _:reference));app.enroll_owner('owner')
            case=app.store.open_incident('functional_monitor','Chybí odezva',[TARGET],1)
            app.store.add_evidence(case['id'],{'source':'offline_fixture','kind':'condition','observed_at':1,'payload':{'failed':True}})
            app.repairs.configure(True,'owner')
            with self.assertRaisesRegex(RepairBlocked,'chybějící'):app.repairs.prepare(case['id'],'owner')
            self.assertEqual(app.repairs.plans(case['id']),[])
            app.detection.close();app.repairs.close()

    def test_companion_scope_cannot_be_changed_to_physical_entities(self):
        with self.assertRaises(RepairBlocked):ManagedReferenceEngine._entity({'id':'hads_next_reference_test','revision':0,'scope':'integration_owned_virtual_test_reference','action':{'service':'light.turn_on','target':{'entity_id':'light.front_door'}}})

class MigrationTests(unittest.TestCase):
    def test_import_is_idempotent_and_never_transfers_approval_or_verified_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=Application(Path(tmp)/'old');old=first.store.open_incident('manual_functional','Test',['light.fixture'],1)
            first.store.add_evidence(old['id'],{'source':'ha_core','kind':'state','observed_at':1,'event_id':'one','payload':{'state':'off'}})
            first.store.record(old['id'],'approval',{'token':'not-a-real-secret','decision':'approve'})
            document=first.store.case(old['id']);document['incident']['status']='resolved'
            second=Application(Path(tmp)/'new');result=import_case(second.store,document);again=import_case(second.store,document)
            self.assertEqual(again['new_evidence'],0);self.assertEqual(result['approvals_imported'],0)
            imported=second.store.case(result['incident_id']);self.assertEqual(imported['incident']['status'],'open');self.assertEqual(len(imported['evidence']),1)
            self.assertTrue(imported['evidence'][0]['payload']['imported_unverified']);self.assertNotIn('token',second.store.export(result['incident_id']))
