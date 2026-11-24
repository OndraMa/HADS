from pathlib import Path
import socket
import tempfile
import time
import unittest

from hads_next.haos_application import Application
from hads_next.investigation_jobs import JobBlocked
from hads_next.worker_protocol import send,receive
from hads_next.investigation import HERMES_REVISION


class ProbeLauncher:
    """Protocol fixture only. Actual jail/agent readiness has a container test."""
    def __init__(self,*,unexpected_model=False,failure=None):self.calls=[];self.unexpected=unexpected_model;self.failure=failure
    def run(self,**args):
        self.calls.append(args)
        assert args['probe_only'] is True
        if self.unexpected:
            with socket.create_connection(('127.0.0.1',args['port']),timeout=2) as channel:
                send(channel,{'nonce':args['nonce'],'kind':'model','body':{'messages':[]}})
                assert receive(channel)['ok'] is False
        if self.failure:return {'completed':False,'error':self.failure}
        return {'completed':True,'probe_only':True,'native_agent_loaded':True,'model_calls':0,
            'isolation_verified':True,'uid':65534,'execution_authority':'none','revision':HERMES_REVISION}


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)

    def probe(self,launcher):
        app=Application(Path(self.tmp.name),launcher=launcher);app.enroll_owner('owner')
        self.assertFalse(app.investigations.provider.public_status()['enabled'])
        self.assertTrue(app.investigations.request_probe('owner'))
        for _ in range(100):
            status=app.investigations.status()['runtime_probe']
            if status['state']!='running':break
            time.sleep(.02)
        self.assertFalse(app.investigations.provider.public_status()['configured'])
        with app.store._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM investigation_model_calls').fetchone()[0],0)
        return app,status

    def test_probe_needs_no_provider_and_is_not_reused_after_restart(self):
        launcher=ProbeLauncher();app,status=self.probe(launcher)
        self.assertEqual(status['state'],'ready');self.assertEqual(len(launcher.calls),1)
        reconstructed=Application(Path(self.tmp.name),launcher=launcher)
        self.assertEqual(reconstructed.investigations.status()['runtime_probe']['state'],'not_read')
        with self.assertRaises(JobBlocked):reconstructed.investigations.request_probe('another_user')

    def test_model_attempt_or_insufficient_memory_cannot_claim_ready(self):
        for launcher in (ProbeLauncher(unexpected_model=True),ProbeLauncher(failure='insufficient_memory_reserve')):
            app,status=self.probe(launcher)
            self.assertEqual(status['state'],'failed')

    def test_readiness_never_starts_a_previously_queued_investigation(self):
        app=Application(Path(self.tmp.name),launcher=ProbeLauncher());app.enroll_owner('owner')
        case=app.store.open_incident('radio','Čekající incident.',['media_player.fixture'],time.time())
        identity=app.investigations.jobs.enqueue(case['id'])
        app.investigations.request_probe('owner')
        for _ in range(100):
            if app.investigations.status()['runtime_probe']['state']!='running':break
            time.sleep(.02)
        self.assertEqual(app.investigations.jobs.get(identity)['state'],'new')
        self.assertEqual(app.investigations.jobs.get(identity)['model_calls'],0)


if __name__=='__main__':unittest.main()
