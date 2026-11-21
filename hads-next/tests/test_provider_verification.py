import json, os, tempfile, unittest
from pathlib import Path
from hads_next.haos_application import Application
from hads_next.observability import CoreReader, CoreWSReader, SupervisorReader
from hads_next.legacy_connectors import prepare
from hads_next.provider_ui import render_providers
from hads_next.provider_verification import SPECS

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=1800000000.;self.app=Application(self.temp.name,clock=lambda:self.now)
        self.addCleanup(self.app.detection.close)
        self.values={'core_config':{'components':['spook','watchman']},'applications':{'addons':[{'slug':'fixture_hadocs','name':'HADocs','state':'started','version':'1.2','options':{'password':'NEVER_COPY'}}]},
                     'entity_registry':[{'entity_id':'sensor.watchman_status','platform':'watchman'},{'entity_id':'sensor.spook_lookalike','platform':'other'}],
                     'repairs':{'issues':[]}}
        self.states=[{'entity_id':'sensor.watchman_status','state':'1','last_updated':'2026-01-01T00:00:00+00:00','attributes':{'token':'NEVER_COPY'}}]
    def update(self):
        self.app.providers.update(self.values,self.states)
        return {r['provider_id']:r for r in self.app.providers.snapshot()}
    def test_presence_process_native_data_and_function_are_separate(self):
        rows=self.update();self.assertEqual(len(rows),len(SPECS))
        self.assertTrue(rows['spook']['presence_confirmed']);self.assertFalse(rows['spook']['native_state_read_succeeded'])
        self.assertTrue(rows['watchman']['native_state_read_succeeded']);self.assertEqual(rows['watchman']['samples'][0]['state'],1.)
        self.assertEqual(rows['hadocs']['applications'][0]['state'],'started')
        self.assertTrue(all(not r['functional_verified'] and not r['writes_enabled'] and not r['mcp_catalog_verified'] for r in rows.values()))
        self.assertNotIn('NEVER_COPY',json.dumps(rows))
    def test_names_do_not_prove_registry_ownership_or_mcp_connection(self):
        self.values['core_config']['components']=[]
        self.values['entity_registry']=[{'entity_id':'sensor.spook_status','platform':'other'}]
        rows=self.update();self.assertFalse(rows['spook']['presence_confirmed']);self.assertFalse(rows['ha_mcp']['presence_confirmed'])
        self.values['applications']['addons'][0]['name']='HADocs impostor'
        self.values['applications']['addons'][0]['slug']='fixture_impostor'
        self.assertFalse(self.update()['hadocs']['presence_confirmed'])
    def test_failed_native_reads_do_not_prove_uninstalled_or_zero_findings(self):
        self.update();self.values={};self.states=None;rows=self.update()
        self.assertFalse(rows['watchman']['presence_confirmed']);self.assertFalse(rows['watchman']['installation_absence_proven'])
        self.assertIsNone(rows['watchman']['matching_repairs_count']);self.assertTrue(rows['watchman']['gaps']);self.assertTrue(rows['watchman']['last_error'])
    def test_read_time_does_not_rejuvenate_source_scan(self):
        first=self.update()['watchman'];self.now+=1000
        self.assertTrue(self.app.providers.snapshot()[0]['stale'])
        second=self.update()['watchman']
        self.assertGreater(second['samples'][0]['state_age_seconds'],first['samples'][0]['state_age_seconds'])
        self.assertFalse(second['samples'][0]['provider_scan_time_verified'])
    def test_unstructured_state_and_options_are_not_exposed(self):
        for state in ('https://private.invalid/secret',{'token':'private'},[],float('nan')):
            self.states[0]['state']=state
            row=self.update()['watchman'];self.assertIsNone(row['samples'][0]['state'])
            self.assertNotIn('private.invalid',json.dumps(row))
    def test_bounded_samples_and_repeat_checks_do_not_create_incidents(self):
        self.values['entity_registry']=[{'platform':'watchman','entity_id':'sensor.test_'+str(i)} for i in range(20)]
        self.states=[{'entity_id':r['entity_id'],'state':'ok'} for r in self.values['entity_registry']]
        for _ in range(4):row=self.update()['watchman']
        self.assertEqual(len(row['samples']),4);self.assertTrue(row['samples_truncated']);self.assertEqual(self.app.snapshot()['cases'],[])
        with self.app.store._connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM provider_verifications').fetchone()[0],len(SPECS))
    def test_actual_source_check_calls_only_existing_native_reads_and_persists(self):
        calls=[]
        def http(path):
            calls.append(path)
            if path=='/api/config':return {'version':'2026.11.1','components':['watchman']}
            if path=='/api/states':return self.states
            raise AssertionError(path)
        def ws(command):
            calls.append(command['type'])
            return {'config/entity_registry/list':self.values['entity_registry'],'config/device_registry/list':[],
                    'repairs/list_issues':{'issues':[]},'system_log/list':[],
                    'system_health/info':{'domains':{},'complete':True}}[command['type']]
        self.app.core=CoreReader(http);self.app.core_ws=CoreWSReader(ws)
        self.app.check_sources()
        self.assertTrue(next(r for r in self.app.providers.snapshot() if r['provider_id']=='watchman')['native_state_read_succeeded'])
        self.assertNotIn('call_service',json.dumps(calls));self.assertEqual(calls.count('/api/states'),1)
        from hads_next.provider_verification import ProviderVerification
        self.assertEqual(ProviderVerification(self.app).snapshot(),self.app.providers.snapshot())
    def test_czech_page_shows_missing_contract_not_fake_green(self):
        self.update();html=render_providers(self.app,'csrf')
        self.assertIn('HADS zatím neověřil vlastní diagnostiku doplňku',html);self.assertNotIn('HASK',html);self.assertNotIn('Hamster MCP',html)
        self.assertNotIn('NEVER_COPY',html)
    def test_owner_named_health_score_is_read_without_claiming_package_identity(self):
        self.states.append({'entity_id':'sensor.system_ha_global_health_score','state':'87','last_updated':'2026-11-14T00:00:00+00:00'})
        row=self.update()['haghs'];self.assertTrue(row['native_state_read_succeeded'])
        self.assertEqual(row['samples'][0]['state'],87.);self.assertFalse(row['functional_verified'])
        self.assertEqual(row['owned_entity_count'],0);self.assertTrue(row['owner_named_target_read'])

class LegacySettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Application(self.temp.name);self.addCleanup(self.app.detection.close)
        with self.app.store._connect() as db:db.execute("INSERT INTO application_settings VALUES('owner','fixture-owner')")
        self.options={'ha_mcp_url':'https://mcp.invalid/private_PATH_SECRET','ha_mcp_token':'PRIVATE_TOKEN',
                      'ai_api_key':'DO_NOT_MIGRATE','autonomous_ai':True,'approval':'approve','ai_max_output_tokens':4000}
    def test_only_known_connection_fields_are_staged_private_and_inactive(self):
        status=self.app.legacy_connectors.stage({'options':self.options},'fixture-owner')
        path=self.app.legacy_connectors.path;raw=path.read_text();value=json.loads(raw)
        self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertNotIn('DO_NOT_MIGRATE',raw)
        self.assertFalse(value['connections']['ha_mcp']['enabled']);self.assertFalse(value['approval_imported']);self.assertFalse(value['cost_consent_imported'])
        self.assertNotIn('PRIVATE_TOKEN',json.dumps(status));self.assertNotIn('PATH_SECRET',json.dumps(status));self.assertFalse(status['active'])
    def test_historical_status_or_empty_defaults_are_not_configuration(self):
        for doc in ({'adapters':{'spook':{'active':True}}},{'options':{'ha_mcp_url':''}}):
            with self.assertRaises(ValueError):prepare(doc)
        self.assertFalse(self.app.legacy_connectors.path.exists())
    def test_wrong_owner_and_masked_token_cannot_stage(self):
        with self.assertRaises(ValueError):self.app.legacy_connectors.stage(self.options,'other')
        self.options['ha_mcp_token']='[skryto]'
        with self.assertRaises(ValueError):self.app.legacy_connectors.stage(self.options,'fixture-owner')
        self.assertFalse(self.app.legacy_connectors.path.exists())
    def test_invalid_addresses_are_refused_without_persisting(self):
        for endpoint in ['file:///config/secrets.yaml','https://user:pass@mcp.invalid','https://mcp.invalid/?token=secret','http://public.invalid/mcp']:
            self.options['ha_mcp_url']=endpoint
            with self.assertRaises(ValueError):self.app.legacy_connectors.stage(self.options,'fixture-owner')
        self.assertFalse(self.app.legacy_connectors.path.exists())
    def test_existing_unsafe_settings_path_is_not_overwritten(self):
        target=Path(self.temp.name)/'keep';target.write_text('preserve')
        self.app.legacy_connectors.path.symlink_to(target)
        with self.assertRaises(ValueError):self.app.legacy_connectors.stage(self.options,'fixture-owner')
        self.assertEqual(target.read_text(),'preserve')
    def test_previous_app_options_use_one_fixed_private_read_and_no_other_settings(self):
        calls=[]
        def read(path):
            calls.append(path)
            return {'result':'ok','data':{'slug':'local_hads4','version':'2.0.0-rc3','options':self.options}}
        self.app.supervisor=SupervisorReader(read)
        status=self.app.legacy_connectors.stage_previous('fixture-owner')
        self.assertEqual(json.loads(self.app.legacy_connectors.path.read_text())['origin'],'supervisor_Hermes_RC3_options_not_live_connector_verified')
        self.assertEqual(calls,['/addons/local_hads4/info']);self.assertFalse(status['active'])
        self.assertNotIn('DO_NOT_MIGRATE',self.app.legacy_connectors.path.read_text())
        self.assertEqual(self.app.snapshot()['cases'],[])
        with self.assertRaises(ValueError):self.app.legacy_connectors.stage_previous('other')
        self.assertEqual(len(calls),1)
    def test_wrong_previous_version_is_never_imported(self):
        self.app.supervisor=SupervisorReader(lambda p:{'result':'ok','data':{'slug':'local_hads4','version':'4.6.3','options':self.options}})
        with self.assertRaises(ValueError):self.app.legacy_connectors.stage_previous('fixture-owner')
        self.assertFalse(self.app.legacy_connectors.path.exists())
