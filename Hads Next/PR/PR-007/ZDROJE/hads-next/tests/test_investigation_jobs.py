from pathlib import Path
import tempfile
import unittest

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import EvidenceBroker
from hads_next.investigation_jobs import InvestigationJobs,JobBlocked


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=IncidentStore(Path(self.tmp.name)/'state.sqlite')
        self.incident=self.store.open_incident('radio','Rádio přestalo hrát.',['media_player.radio'],100)['id']
        self.jobs=InvestigationJobs(self.store,clock=lambda:100)
        self.job=self.jobs.enqueue(self.incident)

    def test_same_evidence_does_not_create_unlimited_new_model_jobs(self):
        self.assertEqual(self.job,self.jobs.enqueue(self.incident))
        self.jobs.claim(self.job)
        with self.assertRaises(JobBlocked):self.jobs.claim(self.job)
        self.assertEqual([x['state'] for x in self.jobs.get(self.job)['steps']],['new','collecting_evidence','investigating'])

    def test_active_job_and_finished_evidence_fingerprint_prevent_reanalysis_loops(self):
        self.jobs.claim(self.job)
        self.store.add_evidence(self.incident,{'source':'test','kind':'state','observed_at':100,'payload':{'state':'idle'}})
        self.assertEqual(self.jobs.enqueue(self.incident),self.job)
        self.jobs.transition(self.job,'hypothesis_ready','Evidence incorporated into conclusion')
        self.assertEqual(self.jobs.enqueue(self.incident),self.job)

    def test_durable_read_survives_restart_without_new_source_read(self):
        self.jobs.claim(self.job)
        broker=EvidenceBroker(self.store)
        first=self.jobs.read(self.job,broker,'hads_get_incident',{})
        restarted=InvestigationJobs(IncidentStore(self.store.db_path),clock=lambda:100)
        restarted.recover();self.assertEqual(restarted.get(self.job)['state'],'reopened')
        restarted.claim(self.job)
        second=restarted.read(self.job,broker,'hads_get_incident',{})
        self.assertTrue(second['cached']);self.assertEqual(second['data'],first['data'])
        restarted.recover()
        with self.assertRaises(JobBlocked):restarted.claim(self.job)

    def test_unknown_metered_call_result_blocks_automatic_replay_after_crash(self):
        self.jobs.claim(self.job)
        self.jobs.model_intent(self.job,{'messages':[]})
        with self.assertRaises(JobBlocked):self.jobs.model_intent(self.job,{'messages':[]})
        self.assertEqual(self.jobs.get(self.job)['model_calls'],1)
        restarted=InvestigationJobs(self.store,clock=lambda:100);restarted.recover()
        self.assertEqual(restarted.get(self.job)['state'],'blocked')
        with self.assertRaises(JobBlocked):restarted.claim(self.job)

    def test_confirmed_model_calls_have_hard_persistent_budget(self):
        self.jobs.claim(self.job)
        for _ in range(8):
            call=self.jobs.model_intent(self.job,{'messages':[]});self.jobs.model_result(call,{'choices':[]})
        with self.assertRaises(JobBlocked):self.jobs.model_intent(self.job,{'messages':[]})

    def test_ai_progress_cannot_resolve_or_approve_an_incident(self):
        for state in ('resolved','awaiting_approval','verifying','repair_plan_ready','hypothesis_ready'):
            with self.assertRaises(JobBlocked):self.jobs.transition(self.job,state,'Model says done')
        self.assertEqual(self.store.case(self.incident)['incident']['status'],'open')

    def test_retention_does_not_reset_paid_call_quota(self):
        self.jobs.claim(self.job)
        call=self.jobs.model_intent(self.job,{},daily_limit=1)
        self.jobs.model_result(call,{})
        self.store.archive(self.incident,at=101)
        self.assertEqual(self.store.prune(archived_before=102),1)
        new=self.store.open_incident('radio','Nový případ.',['media_player.radio'],105)['id']
        identity=self.jobs.enqueue(new);self.jobs.claim(identity)
        with self.assertRaises(JobBlocked):self.jobs.model_intent(identity,{},daily_limit=1)


if __name__=='__main__':unittest.main()
