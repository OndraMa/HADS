from pathlib import Path
import tempfile
import time
import unittest

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import BrokerDenied,EvidenceBroker
from hads_next.investigation_jobs import InvestigationJobs
from hads_next.investigator_roles import RoleBroker,ROLES
from hads_next.observability import CoreReader


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=IncidentStore(Path(self.tmp.name)/'case.db')
        self.case=self.store.open_incident('automation_reference','Automatizace nereaguje.',['automation.fixture'],time.time())['id']
        self.calls=[]
        def native(path):self.calls.append(path);return {'id':'fixture','actions':[]}
        self.native=EvidenceBroker(self.store,core=CoreReader(native))
        self.jobs=InvestigationJobs(self.store);self.job=self.jobs.enqueue(self.case);self.jobs.claim(self.job)
        self.broker=RoleBroker(self.native,self.job,self.case)

    def read(self,name,args):return self.jobs.read(self.job,self.broker,name,args)

    def test_cited_handoff_changes_actual_authorization_and_survives_restart(self):
        self.assertEqual(self.broker.role,'automation')
        config=self.read('hads_get_automation_config',{'automation_id':'fixture'})
        with self.assertRaises(BrokerDenied):self.read('hads_get_supervisor_status',{})
        selected={'role':'supervisor','task':'Prověř stav aplikace.',
            'handoff':{'summary_cs':'Konfigurace byla načtena, příčina zatím neznámá.','evidence_ids':config['evidence_ids'],'uncertainties':['Chybí stav aplikace.']}}
        self.read('hads_select_investigator',selected)
        self.assertEqual(self.read('hads_get_supervisor_status',{})['status'],'unavailable')
        with self.assertRaises(BrokerDenied):self.read('hads_get_automation_config',{'automation_id':'fixture'})
        self.read('hads_select_investigator',{'role':'root_cause','task':'Porovnej důkazy.'})
        cached=self.read('hads_get_automation_config',{'automation_id':'fixture'})
        self.assertTrue(cached['cached']);self.assertEqual(len(self.calls),1)
        self.broker=RoleBroker(self.native,self.job,self.case)
        self.assertEqual(self.broker.role,'root_cause')
        self.assertTrue(self.read('hads_select_investigator',selected)['cached'])
        self.assertEqual(self.broker.role,'supervisor')
        with self.assertRaises(BrokerDenied):self.read('hads_get_automation_config',{'automation_id':'fixture'})
        findings=[r['content'] for r in self.store.case(self.case)['records'] if r['kind']=='investigator_finding']
        self.assertEqual(len(findings),1);self.assertEqual(findings[0]['role'],'automation')
        self.assertEqual(findings[0]['authority'],'model_assessment_not_verified_fact')

    def test_all_specializations_keep_write_and_unknown_evidence_denied(self):
        for role in ROLES:
            self.broker.read(self.case,'hads_select_investigator',{'role':role,'task':'Vyšetři dostupná data.'})
            self.assertTrue(self.broker.allowed())
            for name in ('terminal','execute_code','hads_approve_repair','hads_mark_resolved'):
                with self.assertRaises(BrokerDenied):self.broker.read(self.case,name,{})
            with self.assertRaises(BrokerDenied):self.broker.finding({'summary_cs':'Jistá příčina.',
                'evidence_ids':['0'*64],'uncertainties':[]})
        self.assertEqual(self.store.case(self.case)['incident']['status'],'open')


if __name__=='__main__':unittest.main()
