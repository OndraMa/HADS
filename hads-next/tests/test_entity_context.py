"""Reported Watchman→registry→ZHA gap, isolated contracts, never live HAOS."""
import json,tempfile,unittest
from datetime import datetime,timezone
from hads_next.addon_server import SupervisorTransport
from hads_next.haos_application import Application
from hads_next.observability import CoreReader,CoreWSReader,ReadFailure,SupervisorReader
from hads_next.dashboard import render_dashboard
from hads_next.entity_context_ui import render_context
from hads_next.evidence_broker import BrokerDenied
from hads_next.zigbee_reads import toolkit_request
from test_collector_contracts import watchman_fixture

class EntityContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=1800000000.;self.calls=[]
        self.target='binary_sensor.storage_presence'
        self.registry,self.states=watchman_fixture()
        self.registry.append({'entity_id':self.target,'platform':'zha','unique_id':'fixture-only','device_id':'device_fixture','original_name':'Senzor skladu'})
        self.states[0]['state']='1';self.states[0]['attributes']={'entities':[{'id':self.target,'state':'unavail','occurrences':'📄 .storage/lovelace.fixture:120'}]}
        self.states.append({'entity_id':self.target,'state':'unavailable','last_updated':'2026-11-17T10:50:00+00:00','attributes':{'friendly_name':'Senzor skladu'}})
        self.device={'ieee':'00:11:22:33:44:55:66:77','device_reg_id':'device_fixture','available':False,'lqi':30,'rssi':-84,'last_seen':1794910000.,'network_key':'NEVER_COPY','private_token':'NEVER_COPY'}
        self.device_registry=[]
        self.toolkit_ok=True
        self.app=Application(self.tmp.name,CoreReader(self.http),core_ws=CoreWSReader(self.ws),clock=lambda:self.now)
        self.addCleanup(self.app.detection.close)
    def http(self,path):
        self.calls.append(path)
        if path=='/api/config':return {'version':'2026.11.1','components':['watchman','zha','zha_toolkit']}
        if path=='/api/states':return self.states
        if path.startswith('/api/history/period/'):return [[self.states[-1]]]
        if path=='/api/states/'+self.target:raise ReadFailure('not_found',404)
        raise AssertionError(path)
    def ws(self,request):
        self.calls.append(request)
        kind=request['type']
        if kind=='config/entity_registry/list':return self.registry
        if kind=='config/device_registry/list':return self.device_registry
        if kind=='repairs/list_issues':return {'issues':[]}
        if kind=='system_log/list':return []
        if kind=='system_health/info':return {'domains':{},'complete':True}
        if kind=='zha/devices':return [self.device]
        if kind=='call_service':
            self.assertEqual(request,toolkit_request())
            return {'context':{'token':'NEVER_COPY'},'response':{'success':self.toolkit_ok,'errors':[] if self.toolkit_ok else ['PRIVATE_EXCEPTION'],
                    'command':'zha_devices','zha_toolkit_version':'v1.1.35','devices':[self.device]}}
        raise AssertionError(kind)
    def test_actual_native_snapshot_follows_watchman_to_device_without_model_or_rf_scan(self):
        self.app.check_sources();reports=self.app.entity_context.reports();self.assertEqual(len(reports),1)
        report=reports[0]
        self.assertEqual(report['classification'],'unavailable');self.assertEqual(report['registry']['device_id'],'device_fixture')
        self.assertFalse(report['zha']['available']);self.assertEqual(report['toolkit']['lqi'],30)
        self.assertFalse(report['repair']['approval_available']);self.assertFalse(report['root_cause_proven'])
        self.assertIn('Senzor skladu',render_context(self.app))
        self.assertFalse(any(x in json.dumps(self.calls) for x in ['zha/topology/update','reconfigure','change_channel','permit_join']))
        exported=''.join(self.app.store.export(c['id']) for c in self.app.snapshot()['cases'])
        self.assertNotIn('NEVER_COPY',exported);self.assertNotIn('network_key',exported)
        self.assertEqual(sum(c['kind']=='device_unavailable' for c in self.app.snapshot()['cases']),1)
        with self.app.store._connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM investigation_model_calls').fetchone()[0],0)
    def test_toolkit_error_is_visible_and_native_fallback_still_works(self):
        self.toolkit_ok=False;self.app.check_sources()
        provider=next(r for r in self.app.providers.snapshot() if r['provider_id']=='zha_toolkit')
        self.assertFalse(provider['diagnostic_read']['read_succeeded']);self.assertTrue(provider['last_error'])
        report=self.app.entity_context.reports()[0];self.assertIsNotNone(report['zha']);self.assertIsNone(report['toolkit'])
        self.assertNotIn('PRIVATE_EXCEPTION',json.dumps(provider))
    def test_case_lists_only_registry_siblings_and_marks_the_reported_entity(self):
        self.device_registry=[{'id':'device_fixture','name':'Výrobní název','name_by_user':'<Komora>','secret':'NEVER_COPY'}]
        self.registry.extend([
            {'entity_id':'sensor.fixture_battery','device_id':'device_fixture','disabled_by':'user'},
            {'entity_id':'sensor.fixture_temperature','device_id':'device_fixture'},
            {'entity_id':'sensor.same_name_other_device','device_id':'device_other'},
        ])
        self.app.check_sources()
        case=next(c for c in self.app.snapshot()['cases'] if c['kind']=='device_unavailable')
        page=render_context(self.app,self.app.store.case(case['id']))
        self.assertIn('&lt;Komora&gt;',page)
        self.assertIn('href="/config/devices/device/device_fixture"',page)
        self.assertIn(f'<code>{self.target}</code> <strong>(hlášená entita)</strong> · Nedostupná',page)
        self.assertIn('<code>sensor.fixture_battery</code> · Zakázaná',page)
        self.assertIn('<code>sensor.fixture_temperature</code> · Chybí v seznamu stavů Core',page)
        self.assertNotIn('sensor.same_name_other_device',page)
        self.assertNotIn('NEVER_COPY',page)
        self.now+=601
        self.assertNotIn('/config/devices/device/',render_context(self.app,self.app.store.case(case['id'])))
    def test_toolkit_request_cannot_accept_file_event_or_command_overrides(self):
        for args in ({'command':'leave'},{'json_out':'/config/file'},{'event_done':'alarm_arm'},{'command_data':['network_key']}):
            with self.assertRaises(TypeError):self.app.core_ws.toolkit_devices(**args)
        self.assertEqual(self.calls,[])
    def test_unavail_watchman_alias_and_registry_missing_from_live_states_stays_selectable(self):
        self.states.pop();self.app.check_sources()
        provider=next(r for r in self.app.providers.snapshot() if r['provider_id']=='watchman')
        self.assertEqual(provider['diagnostic_read']['findings'][0]['state'],'unavailable')
        self.assertIn(self.target,{r['entity_id'] for r in self.app.snapshot()['entities']})
        self.assertEqual(self.app.entity_context.reports()[0]['classification'],'missing')
    def test_disabled_entity_is_not_automatically_enabled(self):
        self.registry[-1]['disabled_by']='user';self.states.pop();self.app.check_sources()
        report=self.app.entity_context.reports()[0];self.assertEqual(report['classification'],'disabled')
        self.assertFalse(any(c['kind']=='device_unavailable' for c in self.app.snapshot()['cases']))
        self.assertFalse(report['repair']['approval_available'])
    def test_repeat_reads_deduplicate_and_recovery_does_not_fake_functional_repair(self):
        self.app.check_sources();case=next(c for c in self.app.snapshot()['cases'] if c['kind']=='device_unavailable')
        self.assertIn('Otevřené funkční případy</span><strong>1',render_dashboard(self.app,'fixture'))
        first=self.app.store.case(case['id']);self.now+=300;self.app.check_sources()
        again=self.app.store.case(case['id'])
        self.assertEqual(first['evidence'],again['evidence']);self.assertEqual(len(again['occurrences']),1)
        self.states[-1]['state']='off';self.app.check_sources()
        self.states[0]['state']='0';self.states[0]['attributes']={'entities':[]}
        self.now+=300;self.app.check_sources()
        self.assertEqual(self.app.entity_context.reports()[0]['classification'],'state_available')
        self.assertEqual(self.app.store.case(case['id'])['incident']['status'],'open')
        html=render_dashboard(self.app,'fixture')
        self.assertIn('Otevřené funkční případy</span><strong>0',html)
        self.assertIn('Ověřené výsledky</span><strong>0',html)
        self.assertIn('Nedostupnost se při posledním čtení nepotvrdila (1)',html)
        self.now+=601
        self.assertNotIn('id="restored-entity-states"',render_dashboard(self.app,'fixture'))
        self.states[-1]['state']='unavailable';self.now+=300;self.app.check_sources()
        self.assertEqual(len(self.app.store.case(case['id'])['occurrences']),2)
        self.assertIn('Otevřené funkční případy</span><strong>1',render_dashboard(self.app,'fixture'))
    def test_scoped_hermes_read_uses_collected_evidence_and_rejects_other_entities(self):
        self.app.check_sources();case=next(c for c in self.app.snapshot()['cases'] if c['kind']=='device_unavailable')
        result=self.app.investigations.broker.read(case['id'],'hads_get_entity_diagnosis',{'entity_id':self.target})
        self.assertEqual(result['status'],'available');self.assertTrue(result['evidence_ids'])
        with self.assertRaises(BrokerDenied):self.app.investigations.broker.read(case['id'],'hads_get_entity_diagnosis',{'entity_id':'sensor.other'})
        self.now+=601
        self.assertEqual(self.app.investigations.broker.read(case['id'],'hads_get_entity_diagnosis',{'entity_id':self.target})['status'],'not_read')
    def test_recovered_case_automatically_reads_history_and_logs_without_repair(self):
        self.app.check_sources()
        incident=next(c for c in self.app.snapshot()['cases'] if c['kind']=='device_unavailable')
        when=incident['last_seen']
        iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        self.app.store.open_incident('device_unavailable','Nedostupnost jiného snímače',['binary_sensor.other'],when)
        self.now+=400
        self.states[-1]['state']='off'
        def history(path):
            if path.startswith('/api/history/period/'):
                self.calls.append(path)
                return [[{'entity_id':self.target,'state':'unavailable','last_updated':iso(when-20)}]]
            return self.http(path)
        def supervisor(path,*,raw=False):
            self.calls.append(path)
            self.assertEqual(raw,path.endswith('/logs'))
            if path=='/core/logs':return iso(when-10)+' INFO [homeassistant.setup] Starting Home Assistant'
            if path=='/supervisor/logs':return iso(when+10000)+' ERROR unrelated DNS error'
            if path=='/host/logs':return iso(when-12)+' ERROR host connection reset'
            return {'result':'ok','data':{'version':'2026.11.1','addons':[]}}
        self.app.core.transport=history
        transport=SupervisorTransport('fixture-token')
        transport._http=supervisor
        self.app.supervisor=SupervisorReader(transport)
        self.app.check_sources()
        self.app.orchestration.cycle(budget=40)
        case=self.app.store.case(incident['id'])
        followup=self.app.orchestration.device_followup(case)
        self.assertTrue(followup['state_restored'])
        self.assertIn('Historie Home Assistantu potvrzuje',followup['summary_cs'])
        self.assertIn('další případy nedostupnosti (1)',followup['summary_cs'])
        self.assertIn('síťové nebo startovací události (2)',followup['summary_cs'])
        self.assertEqual(followup['statuses'][('supervisor','supervisor_logs')],'available')
        self.assertIn('/core/logs',self.calls)
        self.assertIn('/supervisor/logs',self.calls)
        self.assertIn('/host/logs',self.calls)
        self.assertEqual(case['incident']['status'],'open')
        self.assertEqual(self.app.repairs.plans(incident['id']),[])
    def test_collection_failures_are_diagnostics_and_disabled_ai_is_not_a_repair_approval(self):
        for key,kind in [('zha-subscription','diagnostic_capture_gap'),('native-api-access','source_unavailable')]:
            self.app.system._finding(key,kind,'Fixture collector gap',['zha'],{'gap':True})
            self.app.system.followup.collection(key,True,'Čtení je obnovené; fyzická porucha nebyla prokázaná.')
        case=self.app.store.open_incident('provider_diagnostic','Fixture Watchman',['watchman'],self.now,correlation_key='provider:watchman:references')
        job=self.app.investigations.jobs.enqueue(case['id'])
        self.app.investigations.jobs.transition(job,'waiting_for_user','AI je vypnutá.')
        html=render_dashboard(self.app,'fixture')
        self.assertIn('Dřívější diagnostické nálezy (2)',html)
        self.assertIn('Žádná čekající rozhodnutí.',html)
        self.assertIn('Otevřené funkční případy</span><strong>0',html)
    def test_malformed_states_or_components_cannot_enable_toolkit_or_crash_collection(self):
        self.states[0]['attributes']['entities'][0]['state']=['unavail']
        self.states[-1]['state']={'private':'NEVER_COPY'};self.states[-1]['attributes']='NEVER_COPY'
        self.http_config={'components':'zha_toolkit'}
        values={'core_config':self.http_config,'entity_registry':self.registry}
        self.app.providers.update(values,self.states)
        self.app.entity_context.update(values,self.states)
        self.assertIsNone(self.app.entity_context.toolkit['component_loaded'])
        self.assertFalse(any(isinstance(c,dict) and c.get('type')=='call_service' for c in self.calls))
        self.assertEqual(self.app.entity_context.reports()[0]['classification'],'unverified')
        self.assertNotIn('NEVER_COPY',json.dumps(self.app.entity_context.reports()))
    def test_full_evidence_budget_does_not_stop_collection_or_fabricate_evidence(self):
        from unittest.mock import patch
        original=self.app.store.add_evidence
        def limited(incident,event):
            if event['source'] in {'native_entity_context','watchman_native'}:raise ValueError('Incident evidence budget exceeded; export/archive required')
            return original(incident,event)
        with patch.object(self.app.store,'add_evidence',side_effect=limited):self.app.check_sources()
        report=self.app.entity_context.reports()[0];self.assertIn('case_evidence_budget',report['gaps'])
        case=next(c for c in self.app.snapshot()['cases'] if c['kind']=='device_unavailable')
        result=self.app.investigations.broker.read(case['id'],'hads_get_entity_diagnosis',{'entity_id':self.target})
        self.assertEqual(result['status'],'not_read');self.assertEqual(result['evidence_ids'],[])
