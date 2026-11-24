import json
from pathlib import Path
import tempfile
import time
import unittest

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import BrokerDenied, EvidenceBroker, project_automation, project_trace
from hads_next.observability import CoreReader, CoreWSReader, ReadFailure, SupervisorReader


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now=time.time()
        self.store=IncidentStore(Path(self.tmp.name)/'case.sqlite')
        self.case=self.store.open_incident('radio','Rádio se vypnulo.',['media_player.radio'],self.now)['id']
        self.calls=[]
        def transport(path):
            self.calls.append(path)
            return {'entity_id':'media_player.radio','state':'idle','last_updated':'2026-11-09T00:00:00+00:00',
                    'attributes':{'access_token':'NEVER_EXPORT'}}
        self.broker=EvidenceBroker(self.store,core=CoreReader(transport),clock=lambda:self.now)

    def test_catalog_denies_code_paths_writes_and_unrelated_entities(self):
        for name,args in [('shell',{}),('hads_get_entity_state',{'entity_id':'sensor.secret'}),
            ('hads_get_entity_state',{'entity_id':'media_player.radio','method':'POST'}),
            ('hads_get_addon_logs',{'slug':'../options.json'}),
            ('hads_get_entity_history',{'entity_id':'media_player.radio','start':'2000-01-01','end':'2099-01-01'})]:
            with self.assertRaises(BrokerDenied):self.broker.read(self.case,name,args)
        self.assertEqual(self.calls,[])

    def test_real_reader_invoked_and_secrets_omitted_before_persistence(self):
        result=self.broker.read(self.case,'hads_get_entity_state',{'entity_id':'media_player.radio'})
        self.assertEqual(self.calls,['/api/states/media_player.radio'])
        self.assertEqual(result['status'],'available')
        self.assertNotIn('NEVER_EXPORT',json.dumps(result)+self.store.export(self.case))
        self.assertEqual(len(result['evidence_ids']),1)
        self.assertEqual(result['evidence_ids'][0],self.store.case(self.case)['evidence'][0]['evidence_id'])
        self.broker.read(self.case,'hads_get_entity_state',{'entity_id':'media_player.radio'})
        self.assertEqual(len(self.store.case(self.case)['evidence']),1)

    def test_missing_permission_failure_and_genuine_empty_are_distinct(self):
        result=self.broker.read(self.case,'hads_get_supervisor_status',{})
        self.assertEqual(result['status'],'unavailable');self.assertIsNone(result['data'])
        def forbidden(path):raise ReadFailure('http_error',403)
        self.broker.supervisor=SupervisorReader(forbidden)
        self.assertEqual(self.broker.read(self.case,'hads_get_supervisor_status',{})['status'],'insufficient_permissions')
        def outage(path):raise ReadFailure('read_failed')
        self.broker.supervisor.transport=outage
        self.assertEqual(self.broker.read(self.case,'hads_get_supervisor_status',{})['status'],'read_failed')
        self.broker.ws=CoreWSReader(lambda cmd:[])
        empty=self.broker.read(self.case,'hads_get_automation_traces',{'automation_id':'known'})
        self.assertEqual(empty['status'],'no_relevant_data');self.assertEqual(empty['data'],[])

    def test_reading_case_itself_does_not_create_new_evidence(self):
        for _ in range(3):self.broker.read(self.case,'hads_get_incident',{})
        self.assertEqual(self.store.case(self.case)['evidence'],[])

    def test_wrong_source_schema_is_not_an_empty_successful_read(self):
        self.broker.ws=CoreWSReader(lambda command:{'unexpected':'object'})
        result=self.broker.read(self.case,'hads_get_automation_traces',{'automation_id':'known'})
        self.assertEqual(result['status'],'read_failed')

    def test_old_source_event_does_not_gain_a_new_observation_time(self):
        result=self.broker.read(self.case,'hads_get_entity_state',{'entity_id':'media_player.radio'})
        event=self.store.case(self.case)['evidence'][0]
        self.assertEqual(event['observed_at'],result['source_event_at'])
        self.assertLess(event['observed_at'],result['read_at'])

    def test_native_not_found_is_a_negative_observation_not_a_fabricated_state(self):
        def absent(path):raise ReadFailure('http_error',404)
        self.broker.core=CoreReader(absent)
        result=self.broker.read(self.case,'hads_get_entity_state',{'entity_id':'media_player.radio'})
        self.assertEqual(result['status'],'no_relevant_data')
        self.assertFalse(result['data']['exists']);self.assertTrue(result['evidence_ids'])
        self.assertNotIn('state',result['data'])

    def test_positive_projection_excludes_arbitrary_service_data_and_trace_variables(self):
        auto=project_automation({'id':'known','actions':[{'action':'alarm_control_panel.alarm_disarm',
            'target':{'entity_id':'alarm_control_panel.home'},'data':{'pin':'NEVER_EXPORT'}}]})
        trace=project_trace({'trace':{'action/0':[{'changed_variables':{'pin':'NEVER_EXPORT'},
            'result':{'params':{'service_data':{'entity_id':'light.target','pin':'NEVER_EXPORT'}}}}]}})
        self.assertNotIn('NEVER_EXPORT',json.dumps([auto,trace]))
        self.assertIn('light.target',json.dumps(trace))

    def test_payload_budget_fails_visibly_instead_of_successful_empty_data(self):
        self.broker.supervisor=SupervisorReader(lambda path:{'result':'ok','data':{'huge':'x'*20000}})
        result=self.broker.read(self.case,'hads_get_supervisor_status',{})
        self.assertEqual(result['status'],'read_failed');self.assertIsNone(result['data'])

    def test_supervisor_options_never_cross_into_model_evidence(self):
        self.broker.supervisor=SupervisorReader(lambda path:{'result':'ok','data':{
            'slug':'music','state':'started','version':'1','options':{'unusual_field':'PRIVATE_APP_KEY'}}})
        result=self.broker.read(self.case,'hads_get_addon_info',{'slug':'music'})
        self.assertEqual(result['status'],'available')
        self.assertNotIn('PRIVATE_APP_KEY',json.dumps(result)+self.store.export(self.case))


if __name__=='__main__':unittest.main()
