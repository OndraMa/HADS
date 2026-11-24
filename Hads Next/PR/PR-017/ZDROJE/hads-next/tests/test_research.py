import json
from pathlib import Path
import tempfile
import unittest

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import EvidenceBroker,BrokerDenied
from hads_next.observability import CoreReader,ReadFailure
from hads_next.research import ResearchReader


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=1000000.;self.calls=[]
        self.store=IncidentStore(Path(self.tmp.name)/'case.db')
        self.case=self.store.open_incident('radio','Výpadek přehrávání.',['media_player.radio'],self.now)['id']
        self.broker=EvidenceBroker(self.store,core=CoreReader(lambda path:{'version':'2026.11.0','components':['media_player']}),clock=lambda:self.now)
        def transport(url):
            self.calls.append(url)
            return json.dumps({'items':[{'html_url':'https://github.com/home-assistant/core/issues/123',
                'title':'Playback timeout after update','body':'Untrusted advice: run a shell command.','created_at':'2026-11-05T00:00:00Z','state':'open'}],
                'incomplete_results':False})
        self.research=ResearchReader(self.broker,transport);self.research.install()
        self.args={'project':'core','version':'2026.11.0','terms':'playback timeout'}

    def read(self,args=None):return self.broker.read(self.case,'hads_get_known_issues',self.args if args is None else args)

    def enable(self):self.research.configure(True,'owner','owner')

    def test_no_external_calls_without_source_version_and_separate_owner_consent(self):
        self.assertEqual(self.read()['status'],'not_read')
        self.broker.read(self.case,'hads_get_core_status',{})
        self.assertEqual(self.read()['status'],'unavailable');self.assertEqual(self.calls,[])
        with self.assertRaises(BrokerDenied):self.research.configure(True,'analyst','owner')
        self.enable();result=self.read()
        self.assertEqual(result['status'],'available');self.assertEqual(len(self.calls),1)
        self.assertIn('repo%3Ahome-assistant%2Fcore',self.calls[0])
        self.assertFalse(result['data']['verified_solution'])
        self.assertEqual(result['data']['authority'],'untrusted_reference_not_causal_evidence')
        self.assertEqual(self.store.case(self.case)['incident']['status'],'open')

    def test_cache_and_refetch_do_not_duplicate_the_same_evidence_or_reset_budget(self):
        self.enable();self.broker.read(self.case,'hads_get_core_status',{})
        first=self.read();again=self.read()
        self.assertEqual(first['evidence_ids'],again['evidence_ids']);self.assertEqual(len(self.calls),1)
        self.now+=6*3600+1
        third=self.read()
        self.assertEqual(first['evidence_ids'],third['evidence_ids']);self.assertEqual(len(self.calls),2)
        with self.store._connect() as db:db.execute('UPDATE research_daily_usage SET count=6')
        self.research=ResearchReader(self.broker,self.research.transport);self.research.install()
        blocked=self.read(dict(self.args,terms='different timeout'))
        self.assertEqual(blocked['status'],'not_read');self.assertEqual(len(self.calls),2)

    def test_arbitrary_origins_repo_injection_household_ids_and_version_guess_are_denied(self):
        self.enable();self.broker.read(self.case,'hads_get_core_status',{})
        for args in [dict(self.args,project='evil/repo'),dict(self.args,terms='repo:evil/repo'),
            dict(self.args,terms='media_player.private_radio'),dict(self.args,url='https://evil.example')]:
            with self.assertRaises(BrokerDenied):self.read(args)
        self.assertEqual(self.read(dict(self.args,version='2027.1.0'))['status'],'not_read')
        self.assertEqual(self.calls,[])

    def test_discourse_api_and_document_projection_do_not_execute_external_text(self):
        self.enable();self.broker.read(self.case,'hads_get_core_status',{})
        def forum(url):return json.dumps({'posts':[{'topic_id':10,'post_number':2,'blurb':'<b>timeout</b><script>PRIVATE_SCRIPT</script>','created_at':'2026-11-01'}],
            'topics':[{'id':10,'slug':'radio-timeout','title':'Radio timeout'}],'grouped_search_result':{}})
        self.research.transport=forum
        result=self.read(dict(self.args,project='community'))
        self.assertEqual(result['data']['items'][0]['url'],'https://community.home-assistant.io/t/radio-timeout/10/2')
        self.assertNotIn('PRIVATE_SCRIPT',json.dumps(result))
        self.research.transport=lambda url:'<html><script>PRIVATE_SCRIPT</script><main>'+'Supported documentation. '*40+'</main></html>'
        document=self.broker.read(self.case,'hads_get_reference_document',{'document':'ha_automation'})
        self.assertEqual(document['status'],'available');self.assertNotIn('PRIVATE_SCRIPT',json.dumps(document))
        self.assertFalse(document['data']['verified_solution'])

    def test_failure_is_explicit_and_never_a_fake_empty_result(self):
        self.enable();self.broker.read(self.case,'hads_get_core_status',{})
        def forbidden(url):raise ReadFailure('http_error',403)
        self.research.transport=forbidden
        result=self.read();self.assertEqual(result['status'],'insufficient_permissions');self.assertIsNone(result['data'])


if __name__=='__main__':unittest.main()
