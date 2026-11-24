"""Adversarial regression cases from an independent boundary review."""
import json
import unittest

from hads_next.observability import CoreReader, NativeHTTP, ReadFailure, redact


class EvidenceRedactionReview(unittest.TestCase):
    def test_structured_credentials_never_cross_read_boundary(self):
        marker = 'ONLY_TEST_CREDENTIAL_6984'
        payload = {'api-key': marker, 'credentials': {'opaque': marker},
                   'private_key': marker, 'nested': [{'client_secret': marker}],
                   'entity_id': 'media_player.radio', 'context_id': 'ctx-123'}
        result = CoreReader(lambda _: payload).config()
        self.assertNotIn(marker, json.dumps(result))
        self.assertEqual(result['entity_id'], 'media_player.radio')
        self.assertEqual(result['context_id'], 'ctx-123')

    def test_log_credentials_are_not_exported_as_plaintext(self):
        for text in [
            'authentication failed password=ONLY_TEST_CREDENTIAL_6984',
            'request https://stream.invalid/radio?token=ONLY_TEST_CREDENTIAL_6984',
            'client api-key: ONLY_TEST_CREDENTIAL_6984',
        ]:
            with self.subTest(text=text):
                result = redact({'log': text})
                self.assertNotIn('ONLY_TEST_CREDENTIAL_6984', json.dumps(result))

    def test_allowlist_rejects_path_and_entity_injection(self):
        # No service call or write request may be smuggled through an entity ID.
        calls = []
        reader = CoreReader(lambda path: calls.append(path))
        for entity in ['../../services/light/turn_on', 'light.x?token=x',
                       'light.x\r\nAuthorization: stolen', 'https://external.invalid']:
            with self.subTest(entity=entity), self.assertRaises(ValueError):
                reader.states(entity)
        self.assertEqual(calls, [])
        transport = NativeHTTP('https://ha.invalid', 'not-a-real-token')
        for path in ['//external.invalid/api', 'https://external.invalid', '/\\external.invalid']:
            with self.subTest(path=path), self.assertRaises(ReadFailure):
                transport(path)


class RepairBoundaryReview(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from hads_next.repair import ApprovalAuthority, RepairEngine
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = self.root / 'automation.json'
        self.fixture.write_text(json.dumps({'id': 'test_button', 'action': {
            'service': 'light.turn_on', 'target': {'entity_id': 'light.old'}}}))
        self.db = self.root / 'case.sqlite'
        self.engine = RepairEngine(self.db, self.root, allowed_files={'automation.json'}, clock=lambda: 100)
        self.authority = ApprovalAuthority(self.db, clock=lambda: 100)
        self.plan = self.prepare('light.kitchen')
        self.second_plan = self.prepare('light.bedroom')

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self, target):
        return self.engine.prepare_entity_reference('case-1', 'automation.json', 'light.old', target,
            ['trace-1'], 'Ověřená oprava testovacího odkazu', watch_seconds=30)

    def execute(self, plan, **kwargs):
        token = self.authority.approve(plan, principal='owner')
        return self.engine.execute(plan, token, principal='owner', **kwargs)

    def test_distinct_approved_plans_cannot_overwrite_after_stale_preflight(self):
        import concurrent.futures
        import threading
        from hads_next.repair import RepairBlocked
        first_intent, release_first, second_started, second_intent = (
            threading.Event() for _ in range(4))
        def pause_first():
            first_intent.set()
            if not release_first.wait(5):
                raise AssertionError('Test did not release first executor')
        def run_second():
            second_started.set()
            try:
                return self.execute(self.second_plan, after_intent=second_intent.set).status
            except RepairBlocked:
                return 'blocked'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.execute, self.plan, after_intent=pause_first)
            try:
                self.assertTrue(first_intent.wait(5))
                second = pool.submit(run_second)
                self.assertTrue(second_started.wait(5))
                second_intent.wait(0.2)
            finally:
                release_first.set()
            self.assertEqual(first.result(timeout=5).status, 'applied_verification_pending')
            self.assertEqual(second.result(timeout=5), 'blocked')
        self.assertEqual(json.loads(self.fixture.read_text())['action']['target']['entity_id'], 'light.kitchen')

    def test_restart_with_ambiguous_intent_blocks_another_plan_for_same_target(self):
        from hads_next.repair import RepairBlocked, RepairEngine
        def crash():
            raise KeyboardInterrupt('fixture crash injection')
        with self.assertRaises(KeyboardInterrupt):
            self.execute(self.plan, after_intent=crash)
        restarted = RepairEngine(self.db, self.root, allowed_files={'automation.json'}, clock=lambda: 101)
        token = self.authority.approve(self.second_plan, principal='owner')
        with self.assertRaises(RepairBlocked):
            restarted.execute(self.second_plan, token, principal='owner')
        self.assertEqual(json.loads(self.fixture.read_text())['action']['target']['entity_id'], 'light.old')

    def test_omitting_prior_recurrence_cannot_resurrect_verified_status(self):
        from hads_next.verification import FunctionalVerifier
        execution = self.execute(self.plan)
        verifier = FunctionalVerifier(self.db)
        failure = {'kind': 'functional_failure', 'observed_at': 101,
                   'payload': {'entity_id': 'light.kitchen'}}
        first = verifier.evaluate(self.plan, execution, [failure], now=101)
        self.assertEqual(first['classification'], 'Oprava selhala')
        good = [
            {'kind': 'automation_triggered', 'observed_at': 102,
             'payload': {'automation_id': 'test_button', 'context_id': 'ctx-1'}},
            {'kind': 'target_state', 'observed_at': 103,
             'payload': {'entity_id': 'light.kitchen', 'state': 'on', 'context_id': 'ctx-1'}},
            {'kind': 'monitoring_checkpoint', 'observed_at': 134,
             'payload': {'entity_id': 'light.kitchen', 'continuous_since': 102, 'healthy': True}},
        ]
        report = verifier.evaluate(self.plan, execution, good, now=134)
        self.assertNotEqual(report['classification'], 'Vyřešeno a ověřeno')
        self.assertEqual(report['recurrences'], 1)
        repeated = verifier.evaluate(self.plan, execution, good, now=135)
        self.assertEqual(repeated['recurrences'], 1)
        self.assertEqual(repeated['functional_successes'], 1)
        self.assertEqual(len(repeated['evidence']), 4)

    def test_renamed_automation_cannot_bypass_ambiguous_file_intent(self):
        from hads_next.repair import RepairBlocked
        def crash():
            raise KeyboardInterrupt('fixture crash injection')
        with self.assertRaises(KeyboardInterrupt):
            self.execute(self.plan, after_intent=crash)
        changed = json.loads(self.fixture.read_text())
        changed['id'] = 'renamed_automation'
        self.fixture.write_text(json.dumps(changed))
        new_plan = self.engine.prepare_entity_reference('case', 'automation.json', 'light.old',
            'light.office', ['fresh-trace'], 'New explicitly approved fixture plan')
        token = self.authority.approve(new_plan, principal='owner')
        with self.assertRaises(RepairBlocked):
            self.engine.execute(new_plan, token, principal='owner')
        self.assertEqual(json.loads(self.fixture.read_text())['action']['target']['entity_id'], 'light.old')


if __name__ == '__main__':
    unittest.main()
