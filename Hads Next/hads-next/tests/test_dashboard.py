"""Regression for owner-reported RC2 output; no household data or live source."""
import tempfile,unittest
from unittest.mock import patch
from hads_next.haos_application import Application
from hads_next.dashboard import render_dashboard,case_title,plural_findings
from hads_next.command_center import page
from hads_next.readiness import checklist

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=Application(self.tmp.name);self.app.enroll_owner('fixture-owner')
        self.app._apps=[{'slug':'fixture_radio','name':'Stream Player'},{'slug':'fixture_backup','name':'Backup Agent'}]
        self.app._summary.update(available=True,entity_count=837,version='2026.11.1',last_error=None)
        for slug in ('fixture_radio','fixture_backup'):
            self.app.system._finding('app:'+slug,'application_failure','Aplikace hlásí neúspěšný běh.',['supervisor',slug],{'slug':slug,'state':'error'})
        self.app.system.last=100
        self.addCleanup(self.app.detection.close)
    def test_historical_generic_cases_are_distinguishable_without_rewriting_evidence(self):
        before=[self.app.store.export(c['id']) for c in self.app.snapshot()['cases']]
        html=render_dashboard(self.app,'csrf')
        self.assertIn('Stream Player potřebuje kontrolu',html);self.assertIn('Backup Agent potřebuje kontrolu',html)
        self.assertNotIn('Aplikace hlásí neúspěšný běh.',html)
        self.assertIn('2 systémové nálezy ke kontrole',html)
        self.assertEqual(before,[self.app.store.export(c['id']) for c in self.app.snapshot()['cases']])
    def test_no_model_activity_or_whole_home_health_is_inferred_from_source_read(self):
        html=render_dashboard(self.app,'csrf')
        self.assertIn('AI je vypnutá',html);self.assertIn('Stav bez potvrzeného dopadu',html)
        self.assertNotIn('Probíhá čtecí vyšetřování',html)
        self.assertIn('Nepřečtené zdroje zůstávají neověřené',html)
        with self.app.store._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM investigation_jobs').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM investigation_model_calls').fetchone()[0],0)
    def test_basic_reads_are_distinct_from_running_or_incomplete_system_check(self):
        self.app.system.last=None
        self.app._sources={'system_health':{'read_succeeded':True}}
        for state,message in (
            ('idle','Systémová kontrola v tomto běhu zatím nemá výsledek.'),
            ('running','Probíhá systémová kontrola.'),
            ('failed','Systémová kontrola je neúplná.'),
        ):
            with self.subTest(state=state):
                self.app._source_job['state']=state
                html=render_dashboard(self.app,'fixture')
                self.assertIn(message,html)
                self.assertIn('1 z 1 základních zdrojů přečteno',html)
    def test_untrusted_application_names_and_symptoms_are_escaped(self):
        self.app._apps[0]['name']='<img src=x onerror=alert(1)>'
        html=render_dashboard(self.app,'csrf')
        self.assertNotIn('<img src=x',html);self.assertIn('&lt;img',html)
    def test_single_navigation_and_ingress_relative_links(self):
        html=page(render_dashboard(self.app,'csrf'),'/')
        self.assertEqual(html.count('<nav '),1);self.assertNotIn('Agenti a zdroje',html)
        self.assertIn('href="setup"',html)
        nested=page('<h1>Detail</h1>','/case/fixture')
        self.assertIn('href="../setup"',nested);self.assertIn('href=".././"',nested)
        self.assertNotIn('<script',nested)
    def test_unknown_app_uses_real_component_and_manual_symptom_is_preserved(self):
        row={'kind':'application_failure','components':['supervisor','fixture_other'],'symptom':'Přehrávání se přerušuje.'}
        self.assertEqual(case_title(row,[]),'fixture_other: Přehrávání se přerušuje.')
    def test_count_grammar_and_no_claim_about_deduplication(self):
        self.assertEqual(plural_findings(1),'1 systémový nález ke kontrole')
        self.assertEqual(plural_findings(2),'2 systémové nálezy ke kontrole')
        self.assertEqual(plural_findings(5),'5 systémových nálezů ke kontrole')
    def test_small_memory_margin_is_visible_without_changing_worker_admission(self):
        with patch('hads_next.readiness.memory_available',return_value=583*1024*1024):
            row=next(x for x in checklist(self.app) if x['label']=='Volná paměť')
        self.assertTrue(row['passed']);self.assertIn('7 MiB',row['detail']);self.assertIn('nezaručuje',row['detail'])
    def test_memory_gate_case_explains_AI_block_without_claiming_other_apps_crashed_from_OOM(self):
        self.app.system._finding('memory-reserve','system_resource_pressure','Paměť je pod rezervou.',['hads_runtime'],{'reserve_bytes':576*1024*1024})
        html=render_dashboard(self.app,'csrf')
        self.assertIn('Pro spuštění Hermes chyběla paměť',html)
        self.assertIn('Rezerva pro AI nebyla splněná',html)
        self.assertIn('sám nevysvětluje chyby jiných aplikací',html)
    def test_supervisor_error_alone_is_kept_as_observation_not_functional_failure(self):
        html=render_dashboard(self.app,'csrf')
        cases=html[html.index('id="investigation"'):html.index('id="application-observations"')]
        self.assertNotIn('Stream Player potřebuje kontrolu',cases)
        self.assertNotIn('Backup Agent potřebuje kontrolu',cases)
        self.assertIn('Stavy aplikací k ověření (2)',html)
        self.assertIn('záměrným zastavením',html)
        self.assertTrue(all(c['status']=='open' for c in self.app.snapshot()['cases']))
    def test_owner_reported_app_problem_remains_a_functional_case(self):
        self.app.store.open_incident('application_failure','Rádio se přerušuje.',['fixture_radio'],1,correlation_key='app:fixture_radio:manual')
        html=render_dashboard(self.app,'csrf')
        self.assertIn('Stream Player: Rádio se přerušuje.',html[:html.index('id="application-observations"')])
    def test_status_only_app_observation_never_automatically_launches_paid_AI(self):
        calls=[];self.app.investigations.start=lambda *args,**kwargs:calls.append(args)
        self.app.detection.consent(True,'fixture-owner')
        self.app.system._finding('app:fixture_other','application_failure','Aplikace hlásí neúspěšný běh.',['fixture_other'],{'state':'error'})
        self.assertEqual(calls,[])
        self.app.system._finding('automation:fixture','automation_disabled','Očekávaná automatizace je vypnutá.',['automation.fixture'],{'state':'off','expected_enabled':True})
        self.assertEqual(len(calls),1)
