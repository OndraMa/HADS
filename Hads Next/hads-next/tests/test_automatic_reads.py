"""The owner never supplies diagnostic commands; all transport IO is synthetic."""
import json,tempfile,time,unittest,socket
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import URLError
from hads_next.haos_application import Application
from hads_next.observability import SupervisorReader,CoreReader,CoreWSReader,ReadFailure,NativeHTTP
from hads_next.automatic_reads import probe_github

class AutomaticReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.calls=[]
        self.inventory=[{'slug':'local_hads_next_practical','name':'HADS Next','state':'started'},{'slug':'fixture_player','name':'Player','state':'started'},{'slug':'old_stopped','state':'error'}]
        self.block_app=False
        def supervisor(path):
            self.calls.append(path)
            if path=='/supervisor/info':data={'version':'2026.11.0'}
            elif path=='/host/info':data={'disk_free':20,'disk_total':100}
            elif path=='/addons':data={'addons':self.inventory}
            elif path in {'/core/stats','/supervisor/stats','/addons/local_hads_next_practical/stats','/addons/fixture_player/stats'}:
                if self.block_app and path.endswith('fixture_player/stats'):raise ReadFailure('http_error',403)
                memory=862142464 if path=='/core/stats' else 43352064
                data={'memory_usage':memory,'memory_limit':1931440128,'cpu_percent':None,'options':{'password':'NEVER_PERSIST'}}
            else:raise AssertionError(path)
            return {'result':'ok','data':data}
        def core(path):return {'version':'2026.11.1'} if path=='/api/config' else []
        self.app=Application(self.tmp.name,CoreReader(core),supervisor=SupervisorReader(supervisor))
        self.app.enroll_owner('fixture-owner');self.addCleanup(self.app.detection.close);self.addCleanup(self.app.system.automatic.close)
    def wait(self,case_id):
        for _ in range(100):
            report=self.app.system.automatic.report(case_id)
            if report and report['state'].startswith('completed'):return report
            time.sleep(.05)
        self.fail('Automatic read did not finish')
    def inspect(self):
        with patch('hads_next.readiness.memory_available',return_value=373*1024*1024):self.app.system.inspect()
        return next(c['id'] for c in self.app.snapshot()['cases'] if c['kind']=='system_resource_pressure')
    def test_incident_automatically_collects_all_running_apps_without_model_or_shell(self):
        identity=self.inspect();report=self.wait(identity)
        self.assertEqual(report['state'],'completed');self.assertEqual(len(report['measured']),4)
        self.assertEqual(report['measured'][0]['label'],'Home Assistant Core')
        self.assertEqual(report['measured'][0]['memory_usage'],862142464)
        self.assertFalse(report['root_cause_proven']);self.assertFalse(report['repair_performed']);self.assertFalse(report['shell_used'])
        self.assertEqual(report['model_calls'],0);self.assertNotIn('/addons/old_stopped/stats',self.calls)
        broker=self.app.investigations.broker.read(identity,'hads_get_incident',{})
        self.assertEqual(broker['data']['automatic_diagnostics']['measured'][0]['memory_usage'],862142464)
        self.assertNotIn('NEVER_PERSIST',self.app.store.export(identity))
        count=len([x for x in self.calls if x.endswith('/stats')]);before=self.app.store.case(identity)['evidence']
        self.inspect();time.sleep(.1)
        self.assertEqual(count,len([x for x in self.calls if x.endswith('/stats')]))
        self.assertEqual(before,self.app.store.case(identity)['evidence'])
        self.assertEqual(self.app.store.case(identity)['incident']['status'],'open')
    def test_missing_permission_is_gap_and_not_zero_or_unavailable_AI(self):
        self.block_app=True;identity=self.inspect();report=self.wait(identity)
        self.assertEqual(report['state'],'completed_with_gaps');self.assertEqual(len(report['gaps']),1)
        self.assertFalse(any(x['target']=='fixture_player' for x in report['measured']))
        case=self.app.store.case(identity)
        failed=next(e for e in case['evidence'] if e['source']=='automatic_native_reads' and e['payload']['target']=='fixture_player')
        self.assertFalse(failed['payload']['read_succeeded']);self.assertEqual(failed['payload']['http_status'],403)
    def test_restart_requeues_interrupted_get_with_bounded_attempts(self):
        engine=self.app.system.automatic
        engine.start=lambda:None
        identity=self.inspect()
        with self.app.store._connect() as db:
            db.execute("UPDATE automatic_read_tasks SET state='reading',attempts=2 WHERE kind='core_stats'")
        from hads_next.automatic_reads import AutomaticReads
        engine=AutomaticReads(self.app)
        while engine.run_one():pass
        report=engine.report(identity);self.assertEqual(report['state'],'completed_with_gaps')
        self.assertNotIn('/core/stats',self.calls)
        self.assertTrue(any(x['source']=='core_stats' for x in report['gaps']))
    def test_fixed_public_probe_sends_no_authorization_and_labels_application_scope(self):
        class Opener:
            def open(inner,request,timeout):
                self.assertEqual(request.full_url,'https://github.com/');self.assertEqual(request.get_method(),'HEAD')
                self.assertIsNone(request.get_header('Authorization'));self.assertIsNone(request.data)
                raise URLError(socket.gaierror('PRIVATE_LOOKUP_TEXT'))
        with patch('hads_next.automatic_reads.build_opener',return_value=Opener()):result=probe_github()
        self.assertEqual(result['phase'],'dns');self.assertFalse(result['reachable']);self.assertNotIn('PRIVATE_LOOKUP_TEXT',json.dumps(result))
        self.assertEqual(result['scope'],'HADS_application_network_not_Core')
    def test_marketplace_failure_schedules_its_own_followup_without_owner_command(self):
        def ws(command):
            if command['type']=='system_health/info':return {'complete':True,'domains':{'marketplace':{'info':{'github_web':{'error':'unreachable'}}}}}
            if command['type']=='repairs/list_issues':return {'issues':[]}
            if command['type']=='system_log/list':return []
            raise AssertionError(command)
        self.app.core_ws=CoreWSReader(ws)
        with patch('hads_next.automatic_reads.probe_github',return_value={'reachable':True,'http_status':200,'phase':'http','scope':'HADS_application_network_not_Core'}):
            self.inspect();identity=next(c['id'] for c in self.app.snapshot()['cases'] if c['kind']=='system_health_failure')
            report=self.wait(identity)
        self.assertIn('nepotvrzuje stejné připojení',report['summary_cs']);self.assertEqual(report['model_calls'],0)
        self.assertEqual(self.app.store.case(identity)['incident']['status'],'open')
    def test_large_inventory_is_bounded_and_explicitly_incomplete(self):
        self.inventory=[{'slug':'fixture_'+str(i),'state':'started'} for i in range(40)]
        self.app.system.automatic.start=lambda:None
        identity=self.inspect()
        while self.app.system.automatic.run_one():pass
        report=self.app.system.automatic.report(identity)
        self.assertTrue(report['inventory_truncated']);self.assertEqual(report['state'],'completed_with_gaps')
        self.assertEqual(len([c for c in self.calls if c.startswith('/addons/') and c.endswith('/stats')]),24)
    def test_second_measurement_is_automatic_bounded_and_reports_comparison(self):
        now=[100.];self.app.clock=lambda:now[0]
        self.app.system.automatic.start=lambda:None
        identity=self.inspect()
        while self.app.system.automatic.run_one():pass
        now[0]=401.;self.inspect()
        while self.app.system.automatic.run_one():pass
        report=self.app.system.automatic.report(identity)
        self.assertEqual(len(report['comparison']),4)
        self.assertTrue(all(r['change_bytes']==0 and r['elapsed_seconds']==301 for r in report['comparison']))
        count=len(self.calls);now[0]=1000.;self.inspect()
        while self.app.system.automatic.run_one():pass
        self.assertEqual(len([x for x in self.calls[count:] if x.endswith('/stats')]),0)
    def test_real_HTTP_transport_uses_only_verified_GET_catalog(self):
        from hads_next.addon_server import SupervisorTransport
        paths=[];owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                owner.assertEqual(self.headers.get('Authorization'),'Bearer SYNTHETIC_TOKEN');paths.append(self.path)
                value={'addons':owner.inventory} if self.path=='/addons' else {'memory_usage':43352064,'memory_limit':1931440128,'cpu_percent':None}
                data=json.dumps({'result':'ok','data':value}).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def do_POST(self):paths.append('FORBIDDEN_WRITE');self.send_error(403)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            transport=SupervisorTransport('SYNTHETIC_TOKEN');transport._http=NativeHTTP('http://127.0.0.1:'+str(server.server_port),'SYNTHETIC_TOKEN',allow_local_http=True)
            self.app.supervisor=SupervisorReader(transport)
            incident=self.app.store.open_incident('system_resource_pressure','Paměť je pod rezervou.',['hads_runtime'],self.app.clock())
            self.app.system.automatic.schedule_memory(incident['id']);report=self.wait(incident['id'])
            self.assertEqual(report['state'],'completed');self.assertEqual(len(paths),5)
            self.assertTrue({'/core/stats','/supervisor/stats','/addons'}<=set(paths));self.assertNotIn('FORBIDDEN_WRITE',paths)
            for path in ('/core/restart','/supervisor/restart','https://external.invalid','/addons/../stop'):
                with self.assertRaises(ValueError):transport(path)
        finally:self.app.system.automatic.close();server.shutdown();server.server_close();thread.join()
    def test_deep_analysis_requires_extended_consent_autonomy_and_memory(self):
        calls=[];self.app.investigations.start=lambda *args,**kwargs:calls.append((args,kwargs))
        p=self.app.investigations.provider
        settings={'endpoint':'https://model.invalid/v1/chat/completions','model':'test','api_key':'SYNTHETIC_KEY','consent':True,'principal':'fixture-owner'}
        engine=self.app.system.automatic
        p.configure(**settings,mode='bounded');engine._maybe_deep('fixture-case');self.assertEqual(calls,[])
        self.app.detection.consent(True,'fixture-owner')
        with patch('hads_next.readiness.memory_available',return_value=373*1048576):engine._maybe_deep('fixture-case')
        self.assertEqual(calls,[])
        with patch('hads_next.readiness.memory_available',return_value=700*1048576):engine._maybe_deep('fixture-case')
        self.assertEqual(len(calls),1);self.assertTrue(calls[0][1]['automatic'])
        p.configure(**settings,mode='trial');engine._maybe_deep('fixture-case');self.assertEqual(len(calls),1)
