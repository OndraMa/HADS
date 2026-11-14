"""Regression contracts from actual upstream schemas, not live HAOS results."""
import json
import tempfile
import unittest
from hads_next.addon_server import SupervisorTransport
from hads_next.haos_application import Application
from hads_next.observability import SupervisorReader, is_app_slug
from hads_next.provider_ui import render_providers
from hads_next.watchman_contract import read_watchman, locations


def watchman_fixture():
    # Renamed sensors prove selection by registry identity rather than UI name.
    values = {'missing_entities': ('4', {'entities': [
        {'id': 'switch.fixture_disabled', 'state': 'disabled', 'occurrences': '📄 /config/automations.yaml:15,20'},
        {'id': 'light.is_on', 'state': 'missing', 'occurrences': '📄 automations.yaml:30'},
        {'id': 'logger.log', 'state': 'missing', 'occurrences': '📄 fixture-esphome.yaml:51'},
        {'id': 'script.execute', 'state': 'missing', 'occurrences': '📄 fixture-esphome.yaml:63,473'},
    ]}), 'missing_actions': ('0', {'services': []}),
        'last_updated': ('2026-11-14T21:05:36+01:00', {}),
        'last_parse': ('2026-11-14T21:05:35+01:00', {}), 'status': ('idle', {})}
    registry = [{'platform': 'watchman', 'unique_id': 'watchman_' + key,
                 'entity_id': 'sensor.renamed_' + key} for key in values]
    states = [{'entity_id': r['entity_id'], 'state': values[key][0],
               'attributes': values[key][1], 'last_updated': '2026-11-14T21:10:00+01:00'}
              for key, r in zip(values, registry)]
    return registry, states


class CollectorContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(self.tmp.name, clock=lambda: 1800000000.)
        self.addCleanup(self.app.detection.close)

    def test_supervisor_accepts_hyphens_at_reader_and_transport_and_rejects_path_injection(self):
        calls = []
        transport = SupervisorTransport('fixture-token')
        transport._http = lambda path, **kw: calls.append(path) or {'result': 'ok', 'data': {'slug': 'abc_sqlite-web'}}
        reader = SupervisorReader(transport)
        self.assertEqual(reader.app_info('abc_sqlite-web')['slug'], 'abc_sqlite-web')
        reader.app_logs('abc_sqlite-web')
        reader.app_stats('abc_sqlite-web')
        self.assertEqual(calls, ['/addons/abc_sqlite-web/info', '/addons/abc_sqlite-web/logs', '/addons/abc_sqlite-web/stats'])
        for slug in ('..', '.', '../other', 'abc%2fother', 'abc?x=y', 'abc#x', '', 'x'*129):
            self.assertFalse(is_app_slug(slug))
            with self.assertRaises(ValueError): reader.app_info(slug)
            with self.assertRaises(ValueError): transport('/addons/' + slug + '/info')
        self.assertEqual(len(calls), 3)

    def test_inventory_bad_row_does_not_discard_inspector_hadocs_or_memory_reads(self):
        inventory = {'addons': [
            {'slug': 'abc_automation-inspector', 'name': 'Automation Inspector', 'state': 'started'},
            {'slug': 'abc_hadocs', 'name': 'HADocs', 'state': 'started'},
            {'slug': 'abc_sqlite-web', 'name': 'SQLite Web', 'state': 'started'},
            {'slug': '../refuse', 'state': 'started'}, None]}
        self.app.providers.update({'applications': inventory}, [])
        providers = {x['provider_id']: x for x in self.app.providers.snapshot()}
        self.assertTrue(providers['hadocs']['presence_confirmed'])
        self.assertTrue(providers['automation_inspector']['presence_confirmed'])
        self.assertIn('application_inventory_invalid_rows', providers['hadocs']['gaps'])
        calls = []
        def http(path):
            calls.append(path)
            return {'result': 'ok', 'data': inventory if path == '/addons' else {'memory_usage': 1024, 'memory_limit': 2048}}
        self.app.supervisor = SupervisorReader(http)
        incident = self.app.store.open_incident('system_resource_pressure', 'fixture memory', ['hads_runtime'], 1800000000.)
        self.app.system.automatic.schedule_memory(incident['id'])
        for _ in range(12):
            if not self.app.system.automatic.run_one(): break
        self.assertIn('/addons/abc_sqlite-web/stats', calls)
        self.assertFalse(any('../' in x for x in calls))
        self.assertEqual(self.app.system.automatic.report(incident['id'])['state'], 'completed_with_gaps')

    def test_existing_watchman_details_become_one_diagnostic_case_without_any_write_or_model(self):
        registry, states = watchman_fixture()
        values = {'core_config': {'components': ['watchman']}, 'applications': {'addons': []},
                  'entity_registry': registry, 'repairs': {'issues': []}}
        for _ in range(3): self.app.providers.update(values, states)
        watchman = next(x for x in self.app.providers.snapshot() if x['provider_id'] == 'watchman')
        native = watchman['diagnostic_read']
        self.assertTrue(native['read_verified'])
        self.assertFalse(watchman['functional_verified'])
        case = self.app.store.case(native['incident_id'])
        self.assertEqual(len(case['occurrences']), 1)
        self.assertEqual(len(case['evidence']), 1)
        self.assertEqual(len(case['records']), 1)
        self.assertEqual(native['findings'][0]['locations'][0]['lines'], [15, 20])
        self.assertTrue(native['findings'][2]['possible_other_configuration_language'])
        self.assertEqual(case['incident']['status'], 'open')
        from hads_next.health_cases import diagnostic_observation
        self.assertTrue(diagnostic_observation(case['incident']))
        self.assertIn('switch.fixture_disabled', render_providers(self.app, 'fixture'))
        states[0]['state'] = '0'; states[0]['attributes'] = {'entities': []}
        self.app.providers.update(values, states)
        self.assertEqual(self.app.store.case(native['incident_id'])['incident']['status'], 'open')

    def test_counter_five_and_four_details_are_incomplete_and_no_new_scan_is_invented(self):
        registry, states = watchman_fixture()
        states[0]['state'] = '5'
        report = read_watchman(registry, {r['entity_id']: r for r in states})
        self.assertFalse(report['read_verified'])
        self.assertIn('missing_entities_count_or_details_incomplete', report['gaps'])
        self.assertEqual(len(report['findings']), 4)
        self.assertEqual(report['last_update_at'], 1794686736.)

    def test_spoofed_registry_missing_attributes_and_busy_scan_never_claim_verified(self):
        registry, states = watchman_fixture()
        for r in registry: r['platform'] = 'other'
        report = read_watchman(registry, {r['entity_id']: r for r in states})
        self.assertFalse(report['read_verified']);self.assertEqual(report['findings'], [])
        registry, states = watchman_fixture()
        states[0]['attributes'] = {'token': 'PRIVATE', 'entities': [{'id': 'sensor.fixture', 'friendly_name': 'PRIVATE', 'occurrences': 'https://private.invalid/key'}]}
        states[0]['state'] = '1';states[-1]['state'] = 'parsing'
        report = read_watchman(registry, {r['entity_id']: r for r in states})
        self.assertFalse(report['read_verified']);self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertNotIn('private.invalid', json.dumps(report))
        self.assertEqual(locations('📄 /config/../secrets.yaml:1'), [])
        self.assertEqual(locations('📄 /root/secrets.yaml:1'), [])

    def test_read_failures_do_not_overwrite_last_findings_as_empty_verified_report(self):
        registry, states = watchman_fixture()
        values = {'entity_registry': registry}
        self.app.providers.update(values, states)
        watchman = next(x for x in self.app.providers.snapshot() if x['provider_id'] == 'watchman')
        self.app.providers.update({}, None)
        case = self.app.store.case(watchman['diagnostic_read']['incident_id'])
        self.assertEqual(case['incident']['status'], 'open')
        self.assertFalse(case['evidence'][-1]['payload']['read_verified'])
        self.assertEqual(len(case['evidence']), 2)
        self.assertEqual(len(case['occurrences']), 1)
