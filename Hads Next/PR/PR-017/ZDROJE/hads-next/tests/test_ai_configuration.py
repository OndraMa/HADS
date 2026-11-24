import json
from pathlib import Path
import tempfile
import unittest

from hads_next.ai_provider import AIProvider,ProviderDisabled
from hads_next.haos_application import Application
from hads_next.investigation_jobs import JobBlocked


class AIConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.provider=AIProvider(self.root)
        self.settings={'endpoint':'https://model.invalid/v1/chat/completions','model':'test-model',
            'api_key':'SYNTHETIC_TEST_KEY','consent':False,'principal':'owner'}

    def test_default_off_and_persisted_explicit_opt_in(self):
        with self.assertRaises(ProviderDisabled):self.provider.sender()
        self.provider.configure(**self.settings)
        with self.assertRaises(ProviderDisabled):self.provider.sender()
        self.provider.configure(**dict(self.settings,consent=True))
        reloaded=AIProvider(self.root)
        self.assertTrue(reloaded.public_status()['enabled'])
        self.assertNotIn('SYNTHETIC_TEST_KEY',json.dumps(reloaded.public_status()))
        self.assertEqual(reloaded.path.stat().st_mode & 0o777,0o600)

    def test_key_cannot_follow_an_endpoint_change_or_redirect_configuration(self):
        self.provider.configure(**self.settings)
        original=self.provider.path.read_bytes()
        with self.assertRaises(ProviderDisabled):
            self.provider.configure(**dict(self.settings,endpoint='https://other.invalid/v1/chat/completions',api_key=''))
        for endpoint in ('http://supervisor/core/restart','https://user:secret@model.invalid/v1/chat/completions',
                         'https://model.invalid/v1/chat/completions?token=x'):
            with self.assertRaises(ProviderDisabled):self.provider.configure(**dict(self.settings,endpoint=endpoint))
        self.assertEqual(self.provider.path.read_bytes(),original)

    def test_corrupt_or_insecure_ai_settings_do_not_disable_incident_collection(self):
        path=self.root/'ai-provider.json'
        path.write_text('{broken');path.chmod(0o600)
        provider=AIProvider(self.root)
        self.assertFalse(provider.public_status()['enabled']);self.assertTrue(provider.public_status()['last_error'])
        app=Application(self.root)
        case=app.report_incident('Rádio se samo vypnulo.','media_player.radio','owner')
        self.assertEqual(case['incident']['status'],'open')

    def test_missing_ai_and_runtime_are_visible_and_no_calls_are_queued_to_provider(self):
        app=Application(self.root);app.enroll_owner('owner')
        incident=app.report_incident('Rádio přestalo hrát.','media_player.radio','owner')['incident']['id']
        identity=app.investigations.start(incident,'owner')
        job=app.investigations.jobs.get(identity)
        self.assertEqual(job['state'],'waiting_for_user');self.assertEqual(job['model_calls'],0)
        self.assertFalse(app.snapshot()['hermes_enabled'])
        self.assertEqual(len(app.snapshot()['cases']),1)
        with self.assertRaises(JobBlocked):app.investigations.start(incident,'someone-else')


if __name__=='__main__':unittest.main()
