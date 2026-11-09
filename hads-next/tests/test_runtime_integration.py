"""Offline runtime integration, not live HAOS acceptance."""
import json
from pathlib import Path
import tempfile
from urllib.parse import urlencode
import unittest

from hads_next.haos_application import Application
from hads_next.observability import CoreReader, CoreWSReader, SupervisorReader
import test_addon_server as ingress_fixture


class SetupAndPrivilegeTests(unittest.TestCase):
    setUp=ingress_fixture.IngressTests.setUp
    tearDown=ingress_fixture.IngressTests.tearDown
    request=ingress_fixture.IngressTests.request
    def test_verified_enrollment_survives_restart_without_yaml(self):
        self.server.owner_user_id = ''
        data = urlencode({'csrf': self.server.csrf})
        self.assertEqual(self.request('POST','/setup/enroll',data)[0],303)
        self.assertEqual(self.app.owner(),'owner-id')
        self.assertEqual(Application(Path(self.temp.name)).owner(),'owner-id')
        self.assertEqual(self.request('GET','/api/status')[0],200)

    def test_non_admin_inactive_and_system_accounts_cannot_enroll(self):
        self.server.owner_user_id = ''
        for variant in ('non_admin','inactive','system','unknown'):
            user={'id':'owner-id','is_active':True,'is_owner':False,'group_ids':['system-admin'],'system_generated':False}
            if variant=='non_admin':user['group_ids']=[]
            elif variant=='inactive':user['is_active']=False
            elif variant=='system':user['system_generated']=True
            else:user['id']='another-id'
            self.app.core_ws = CoreWSReader(lambda _,u=user:[u])
            self.server._auth_cache = None
            with self.subTest(variant=variant):
                self.assertEqual(self.request('POST','/setup/enroll',urlencode({'csrf':self.server.csrf}))[0],403)
                self.assertEqual(self.app.owner(),'')

    def test_missing_auth_source_does_not_trust_manual_owner_id(self):
        self.app.core_ws = None
        self.assertEqual(self.request('GET','/api/status')[0],403)

    def test_admin_revocation_blocks_existing_owner(self):
        self.app.core_ws = CoreWSReader(lambda _:[{'id':'owner-id','is_owner':False,'is_active':True,'system_generated':False,'group_ids':[]}])
        self.server._auth_cache = None
        self.assertEqual(self.request('GET','/api/status')[0],403)

    def test_bootstrap_requires_csrf_and_gateway(self):
        self.server.owner_user_id = ''
        self.assertEqual(self.request('POST','/setup/enroll',urlencode({'csrf':'invented'}))[0],403)
        self.server.ingress_peer = '192.0.2.1'
        self.assertEqual(self.request('POST','/setup/enroll',urlencode({'csrf':self.server.csrf}))[0],403)


class RuntimeSourceTests(unittest.TestCase):
    def test_history_context_can_only_be_enriched_from_the_exact_native_state(self):
        from datetime import datetime,timezone
        at=1794153600.;iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        history=[{'entity_id':'media_player.radio','state':'playing','last_updated':iso(at-10)},
            {'entity_id':'media_player.radio','state':'idle','last_updated':iso(at-1)}]
        for matching in (True,False):
            current={**history[-1],'last_updated':iso(at-1 if matching else at),'context':{'id':'stop-context'}}
            def native(path):return [history] if '/history/' in path else current
            with tempfile.TemporaryDirectory() as tmp:
                app=Application(tmp,CoreReader(native),core_ws=CoreWSReader(lambda cmd:[{'domain':'media_player','service':'media_stop',
                    'when':at-2,'context_id':'stop-context','service_data':{'entity_id':'media_player.radio'}}]),clock=lambda:at)
                case=app.report_incident('Rádio se zastavilo.','media_player.radio','owner')
                result=next(r['content'] for r in case['records'] if r['kind']=='deterministic_investigation')
                self.assertEqual(result['category'],'commanded_stop' if matching else 'insufficient_evidence')
                evidence_count=len(case['evidence'])
                app.report_incident('Rádio se zastavilo.','media_player.radio','owner')
                self.assertEqual(len(app.store.case(case['incident']['id'])['evidence']),evidence_count)

    def test_repeated_dashboard_reads_do_not_leak_database_descriptors(self):
        import gc
        descriptors=Path('/proc/self/fd')
        if not descriptors.exists():self.skipTest('Linux descriptor accounting required')
        with tempfile.TemporaryDirectory() as tmp:
            app=Application(Path(tmp))
            gc.collect();before=len(list(descriptors.iterdir()))
            gc.disable()
            try:
                for _ in range(100):app.snapshot();app.owner()
                self.assertLessEqual(len(list(descriptors.iterdir())),before+2)
            finally:gc.enable()
    def test_past_radio_stop_is_attributed_using_native_action_history_context(self):
        at=1794153600.0
        states=[{'entity_id':'media_player.radio','state':'playing','last_updated':'2026-11-08T15:59:00+00:00'},
                {'entity_id':'media_player.radio','state':'idle','last_updated':'2026-11-08T15:59:59+00:00','context':{'id':'state-1','parent_id':'quiet-hours'}}]
        actions=[{'domain':'media_player','service':'media_stop','when':at-2,'context_id':'quiet-hours',
                  'service_data':{'entity_id':'media_player.radio','code':'NEVER_STORE_THIS'}}]
        calls=[]
        def ws(request):
            calls.append(request)
            return actions
        with tempfile.TemporaryDirectory() as tmp:
            app=Application(Path(tmp),CoreReader(lambda _:[states]),core_ws=CoreWSReader(ws),clock=lambda:at+86400)
            case=app.report_incident('Včera se samo vypnulo rádio','media_player.radio','owner',occurred_at=at)
            result=case['records'][-1]['content']
            self.assertEqual(result['category'],'commanded_stop')
            self.assertEqual(calls[0]['type'],'logbook/get_action_calls')
            self.assertNotIn('NEVER_STORE_THIS',json.dumps(case))
            self.assertEqual(len(case['evidence']),3)

    def test_future_or_nonfinite_incident_time_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=Application(Path(tmp),clock=lambda:100)
            for at in (101,float('nan'),float('inf')):
                with self.assertRaises(ValueError):app.report_incident('Rádio přestalo hrát','media_player.radio','owner',occurred_at=at)

    def test_real_reader_objects_are_used_for_app_investigation_and_dedup(self):
        calls=[]
        def transport(path):
            calls.append(path)
            if path.endswith('/logs'):return '2026-11-09 ERROR provider disconnected password=DO_NOT_STORE'
            if path=='/addons':return {'result':'ok','data':{'addons':[{'slug':'fixture_radio','name':'Radio'}]}}
            return {'result':'ok','data':{'slug':'fixture_radio','state':'stopped','version':'1.0'}}
        with tempfile.TemporaryDirectory() as tmp:
            now=[100.0]
            app=Application(Path(tmp),supervisor=SupervisorReader(transport),clock=lambda:now[0])
            result=app.check_sources()
            self.assertTrue(result['applications']['read_succeeded'])
            self.assertFalse(result['entity_registry']['read_succeeded'])
            self.assertEqual(app.snapshot()['applications'][0]['slug'],'fixture_radio')
            case=app.report_app_incident('Rádio neběží','fixture_radio','owner')
            self.assertEqual(len(case['evidence']),3)
            self.assertNotIn('DO_NOT_STORE',json.dumps(case))
            now[0]+=10
            again=app.report_app_incident('Rádio neběží','fixture_radio','owner')
            self.assertEqual(len(again['evidence']),3)
            self.assertEqual(case['incident']['id'],again['incident']['id'])
            self.assertIn('/addons/fixture_radio/logs',calls)
            self.assertEqual(again['incident']['status'],'open')

    def test_supervisor_error_does_not_become_successful_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader=SupervisorReader(lambda _:{'result':'error','message':'forbidden'})
            app=Application(Path(tmp),supervisor=reader)
            self.assertFalse(app.check_sources()['applications']['read_succeeded'])
            with self.assertRaises(ValueError):app.report_app_incident('Nefunguje rádio','fixture_radio','owner')
