"""No real AI requests; restart/concurrency/cost-unknown outcomes stay bounded."""
import concurrent.futures,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from hads_next.ai_provider import AIProvider,ProviderDisabled
from hads_next.ai_budget import BudgetExceeded

class Response(io.BytesIO):status=200
class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.calls=[]
        self.provider=AIProvider(self.root);self.settings={'endpoint':'https://model.invalid/v1/chat/completions','model':'test','api_key':'SYNTHETIC_TEST_KEY','consent':True,'principal':'owner'}
        self.provider.configure(**self.settings)
    def opener(self,*handlers):
        owner=self
        class Opener:
            def open(self,request,timeout):
                owner.calls.append(json.loads(request.data))
                return Response(json.dumps({'choices':[{'message':{'content':'fixture'}}]}).encode())
        return Opener()
    def test_trial_limit_is_shared_persistent_and_not_reset_by_key_change(self):
        with patch('hads_next.ai_provider.build_opener',self.opener):
            _,send=self.provider.sender()
            for _ in range(3):send({'messages':[{'role':'user','content':'fixture'}],'max_tokens':999999})
            with self.assertRaises(BudgetExceeded):send({'messages':[]})
            reloaded=AIProvider(self.root);reloaded.configure(**dict(self.settings,api_key='NEW_SYNTHETIC_TEST_KEY'))
            with self.assertRaises(BudgetExceeded):reloaded.sender()[1]({'messages':[]})
        self.assertEqual(len(self.calls),3);self.assertTrue(all(c['max_tokens']==512 for c in self.calls))
        self.assertEqual(reloaded.public_status()['rolling_24h_calls_remaining'],0)
    def test_concurrent_callers_cannot_overrun_three_requests(self):
        with patch('hads_next.ai_provider.build_opener',self.opener):
            _,send=self.provider.sender()
            def call(_):
                try:send({'messages':[]});return True
                except BudgetExceeded:return False
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(call,range(8)))
        self.assertEqual(sum(results),3);self.assertEqual(len(self.calls),3)
    def test_unknown_outcome_is_counted_and_input_overflow_is_not_sent(self):
        class Timeout:
            def open(self,*args,**kwargs):raise TimeoutError('SYNTHETIC_PRIVATE_TOKEN')
        with patch('hads_next.ai_provider.build_opener',return_value=Timeout()):
            _,send=self.provider.sender()
            for _ in range(3):
                with self.assertRaises(ProviderDisabled):send({'messages':[]})
            with self.assertRaises(BudgetExceeded):send({'messages':[]})
        with patch('hads_next.ai_provider.build_opener',self.opener):
            _,send=self.provider.sender()
            with self.assertRaises(ProviderDisabled):send({'messages':[{'role':'user','content':'x'*49000}]})
        self.assertEqual(len(self.calls),0)
    def test_legacy_consent_does_not_enable_new_unattended_test(self):
        self.provider.path.write_text(json.dumps(self.settings));self.provider.path.chmod(0o600)
        legacy=AIProvider(self.root)
        self.assertFalse(legacy.public_status()['enabled']);self.assertEqual(legacy.public_status()['mode'],'trial')
        with self.assertRaises(ProviderDisabled):legacy.sender()
    def test_limit_is_rolling_not_reset_at_midnight(self):
        now=[86399.];self.provider.budget.clock=lambda:now[0]
        for _ in range(3):self.provider.budget.reserve(3,10,512)
        now[0]=86401
        self.assertEqual(self.provider.budget.remaining(3),0)
        now[0]+=86400
        self.assertEqual(self.provider.budget.remaining(3),3)
    def test_trial_consent_never_enables_automatic_model_work(self):
        from hads_next.haos_application import Application
        app=Application(self.root);app.enroll_owner('owner');self.addCleanup(app.detection.close)
        case=app.store.open_incident('manual_functional','Automatický test.',['light.fixture'],100)
        self.assertIsNone(app.investigations.start(case['id'],'owner',automatic=True))
        with app.store._connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM investigation_jobs').fetchone()[0],0)
        self.assertEqual(app.investigations.provider.public_status()['rolling_24h_calls_remaining'],3)
    def test_corrupt_budget_blocks_model_but_keeps_native_incidents_available(self):
        from hads_next.haos_application import Application
        self.provider.budget.path.write_bytes(b'invalid isolated fixture')
        app=Application(self.root)
        self.assertFalse(app.investigations.provider.public_status()['enabled'])
        case=app.report_incident('Lokální detekce pokračuje.','light.fixture','owner')
        self.assertEqual(case['incident']['status'],'open')
