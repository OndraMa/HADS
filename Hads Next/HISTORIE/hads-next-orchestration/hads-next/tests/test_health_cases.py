"""Offline regressions for reported Marketplace/github_web and 373 MiB gates."""
import json,tempfile,unittest
from unittest.mock import patch
from hads_next.haos_application import Application
from hads_next.observability import CoreReader,CoreWSReader
from hads_next.health_cases import explain_health_case,project_health_errors
from hads_next.dashboard import render_dashboard


class HealthCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=100.;self.logs=[];self.issues={'issues':[]};self.health={'complete':True,'domains':{'marketplace':{'info':{'github_web':{'error':'unreachable'}}}}}
        def http(path):
            if path=='/api/config':return {'version':'2026.11.1'}
            if path=='/api/states':return []
            raise AssertionError(path)
        def ws(command):
            if command['type']=='system_health/info':return self.health
            if command['type']=='repairs/list_issues':return self.issues
            if command['type']=='system_log/list':return self.logs
            raise AssertionError(command)
        self.app=Application(self.temp.name,CoreReader(http),core_ws=CoreWSReader(ws),clock=lambda:self.now)
        self.app.enroll_owner('fixture-owner');self.addCleanup(self.app.detection.close)
    def scan(self,memory=768):
        with patch('hads_next.readiness.memory_available',return_value=memory*1024*1024):self.app.system.inspect()
        self.now+=30
    def case(self,kind):
        case=next(c for c in self.app.snapshot()['cases'] if c['kind']==kind)
        return self.app.store.case(case['id'])
    def test_native_failure_keeps_safe_code_and_specific_noncausal_explanation(self):
        self.scan();case=self.case('system_health_failure');payload=case['evidence'][0]['payload']
        self.assertEqual(payload['errors'],[{'field':'github_web','error':'unreachable'}])
        result=next(r['content'] for r in case['records'] if r['kind']=='deterministic_investigation')
        self.assertIn('Marketplace',result['summary_cs']);self.assertIn('github_web',result['summary_cs'])
        self.assertFalse(result['root_cause_proven']);self.assertTrue(result['needed'])
        self.assertIn('Windows',result['next_test_cs']);self.assertEqual(case['incident']['status'],'open')
    def test_arbitrary_remote_error_text_is_not_persisted(self):
        secret='https://private.invalid/?token=DO_NOT_STORE'
        self.health['domains']['marketplace']['info']['github_web']['error']=secret
        self.scan();case=self.case('system_health_failure')
        self.assertNotIn('DO_NOT_STORE',json.dumps(case));self.assertNotIn('private.invalid',json.dumps(case))
        self.assertEqual(case['evidence'][0]['payload']['errors'][0]['error'],'unclassified')
        self.assertEqual(project_health_errors({'<script>':{'error':'timeout'}}),[])
    def test_targeted_log_followup_is_time_scoped_deduplicated_and_has_no_private_prose(self):
        self.logs=[{'name':'custom_components.marketplace','level':'ERROR','timestamp':100.,
                    'message':['ClientConnectorDNSError: https://private.invalid/?token=NEVER_COPY'],
                    'exception':'TimeoutError: household private details'},
                   {'name':'custom_components.other','level':'ERROR','timestamp':100.,'message':['SSLError']},
                   {'name':'custom_components.marketplace','level':'ERROR','timestamp':-1000.,'message':['SSLError']}]
        self.scan();case=self.case('system_health_failure')
        logs=[e for e in case['evidence'] if e['kind']=='system_health_log'];self.assertEqual(len(logs),1)
        self.assertEqual(logs[0]['payload']['exception_types'],['ClientConnectorDNSError','TimeoutError'])
        for private in ('private.invalid','NEVER_COPY','household private details','SSLError'):
            self.assertNotIn(private,json.dumps(case))
        self.assertIn('vodítko',case['records'][-1]['content']['summary_cs'])
        self.scan();self.assertEqual(case,self.case('system_health_failure'))
    def test_repeated_reads_deduplicate_and_partial_stream_cannot_clear_failure(self):
        self.scan();before=self.case('system_health_failure');self.scan()
        self.assertEqual(before,self.case('system_health_failure'))
        self.health={'complete':False,'domains':{'marketplace':{'info':{}}}};self.scan()
        self.assertEqual(self.app.system.status()['active_findings'],1)
        self.health['complete']=True;self.scan()
        self.assertEqual(self.app.system.status()['active_findings'],0)
        self.assertEqual(self.case('system_health_failure')['incident']['status'],'open')
    def test_memory_measurement_is_preserved_without_jitter_occurrences_or_AI(self):
        calls=[];self.app.investigations.start=lambda *args,**kwargs:calls.append(args)
        self.app.detection.consent(True,'fixture-owner')
        self.scan(373);before=self.case('system_resource_pressure')
        self.assertEqual(before['evidence'][0]['payload']['available_bytes'],373*1024*1024)
        result=explain_health_case(before)
        for number in ('373 MiB','576 MiB','203 MiB'):self.assertIn(number,result['summary_cs'])
        self.scan(372);self.assertEqual(before,self.case('system_resource_pressure'));self.assertEqual(calls,[])
        self.scan(768);self.scan(371)
        reopened=self.case('system_resource_pressure')
        self.assertEqual(len(reopened['occurrences']),2);self.assertEqual(len(reopened['evidence']),2)
        self.assertEqual(reopened['evidence'][-1]['payload']['available_bytes'],371*1024*1024)
    def test_legacy_case_gets_specific_explanation_without_invented_error_or_memory(self):
        old={'incident':{'kind':'system_health_failure','components':['integration:marketplace']},
             'evidence':[{'kind':'system_health_failure','source':'native_system_health','observed_at':100,
                          'payload':{'domain':'marketplace','failed_fields':['github_web']}}]}
        result=explain_health_case(old)
        self.assertIn('neobsahuje konkrétní chybový kód',result['summary_cs'])
        self.assertNotIn('unreachable',result['summary_cs']);self.assertFalse(result['root_cause_proven'])
        result=explain_health_case({'incident':{'kind':'system_resource_pressure','components':['hads_runtime']},'evidence':[]})
        self.assertIn('neobsahuje změřenou',result['summary_cs']);self.assertNotIn('373',result['summary_cs'])
    def test_hassio_cloud_reads_report_actual_status_without_model_or_new_occurrences(self):
        self.health={'complete':True,'domains':{d:{'info':{'connection':{'error':'timeout'}}} for d in ['hassio','cloud']}}
        self.app.investigations.start=lambda *a,**k:self.fail('Native continuation must not call AI')
        self.scan();cases=self.app.snapshot()['cases']
        before={c['id']:self.app.store.case(c['id']) for c in cases}
        reports={c['id']:self.app.system.followup.report(c['id']) for c in cases}
        self.scan()
        for c in cases:
            self.assertEqual(before[c['id']],self.app.store.case(c['id']))
            report=self.app.system.followup.report(c['id'])
            self.assertEqual(report['state'],'still_failing')
            self.assertGreater(report['checked_at'],reports[c['id']]['checked_at'])
        html=render_dashboard(self.app,'csrf')
        self.assertIn('Znovu přečteno; nález trvá',html);self.assertIn('connection (timeout)',html)
        self.assertNotIn('Čeká na vyšetření',html)
    def test_passed_partial_and_absent_health_are_distinguished_without_closing_incident(self):
        self.scan();identity=self.case('system_health_failure')['incident']['id']
        self.health={'complete':False,'domains':{'marketplace':{'info':{}}}};self.scan()
        self.assertEqual(self.app.system.followup.report(identity)['state'],'unavailable')
        self.health['complete']=True;self.scan()
        self.assertEqual(self.app.system.followup.report(identity)['state'],'check_passed')
        self.assertEqual(self.app.store.case(identity)['incident']['status'],'open')
        self.health['domains']={};self.scan()
        self.assertEqual(self.app.system.followup.report(identity)['state'],'unavailable')
    def test_repairs_are_specific_diagnostic_observations_and_collect_only_matching_safe_logs(self):
        self.issues={'issues':[{'domain':'fixture','issue_id':'repair_needed','severity':'error','is_fixable':True}]}
        self.logs=[{'name':'homeassistant.components.fixture','level':'ERROR','timestamp':100.,'message':['TimeoutError private-token']},
                   {'name':'homeassistant.components.other','level':'ERROR','timestamp':100.,'message':['SSLError']}]
        self.scan();case=self.case('integration_repair');identity=case['incident']['id']
        report=self.app.system.followup.report(identity)
        self.assertIn('repair_needed',report['summary_cs']);self.assertEqual(report['state'],'still_failing')
        self.assertEqual(len([e for e in case['evidence'] if e['kind']=='system_health_log']),1)
        self.assertNotIn('private-token',json.dumps(case));self.assertNotIn('SSLError',json.dumps(case))
        html=render_dashboard(self.app,'csrf');self.assertIn('fixture: požadavek Home Assistantu',html)
        functional=html[html.index('id="investigation"'):html.index('id="diagnostic-observations"')]
        self.assertNotIn('class="case-card"',functional)
        self.issues=None;self.scan();self.assertEqual(self.app.system.followup.report(identity)['state'],'unavailable')
        self.issues={'issues':[]};self.scan();self.assertEqual(self.app.system.followup.report(identity)['state'],'check_passed')
        self.assertEqual(self.app.store.case(identity)['incident']['status'],'open')
    def test_followup_survives_restart_and_unavailable_log_is_visible(self):
        self.logs=None;self.scan();identity=self.case('system_health_failure')['incident']['id']
        before=self.app.system.followup.report(identity)
        self.assertIn('system_log_unavailable',before['gaps'])
        from hads_next.native_followup import NativeFollowup
        self.assertEqual(NativeFollowup(self.app).report(identity),before)
        result=self.app.investigations.broker.read(identity,'hads_get_incident',{})
        self.assertEqual(result['data']['native_followup'],before)
    def test_diagnostics_remain_visible_but_do_not_count_as_household_function_failures(self):
        self.scan(373);before=[self.app.store.export(c['id']) for c in self.app.snapshot()['cases']]
        html=render_dashboard(self.app,'csrf')
        functional=html[html.index('id="investigation"'):html.index('id="diagnostic-observations"')]
        self.assertNotIn('class="case-card"',functional)
        self.assertIn('Diagnostika a připravenost (2)',html)
        self.assertIn('Marketplace: neúspěšná diagnostická kontrola',html)
        self.assertNotIn('Funkční případ',html)
        self.assertEqual(before,[self.app.store.export(c['id']) for c in self.app.snapshot()['cases']])
        self.app.store.open_incident('manual_functional','Marketplace neaktualizuje aplikace.',['integration:marketplace'],self.now)
        html=render_dashboard(self.app,'csrf')
        self.assertIn('Marketplace neaktualizuje aplikace.',html[:html.index('id="diagnostic-observations"')])
