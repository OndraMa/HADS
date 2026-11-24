import concurrent.futures
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from hads_next.repair import ApprovalAuthority, RepairBlocked, RepairEngine, RepairPlan, canonical


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = self.root / "automation.json"
        self.original = {"id": "test_button", "action": {"service": "light.turn_on",
            "target": {"entity_id": "light.old"}}, "enabled": True}
        self.fixture.write_text(json.dumps(self.original))
        self.db = self.root / "case.sqlite"
        self.now = 1000.0
        self.engine = RepairEngine(self.db, self.root, allowed_files={"automation.json"}, clock=lambda: self.now)
        self.authority = ApprovalAuthority(self.db, clock=lambda: self.now)
        self.plan = self.prepare()

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, **kwargs):
        return self.engine.prepare_entity_reference("incident-1", "automation.json", "light.old", "light.kitchen",
            ["evidence-1", "evidence-2"], "Ověřený starý odkaz neexistuje; nový cíl je doložen registry.", **kwargs)

    def approve(self, plan=None):
        return self.authority.approve(plan or self.plan, principal="owner")

    def test_approved_write_changes_only_the_reference(self):
        result = self.engine.execute(self.plan, self.approve(), principal="owner")
        self.assertEqual(result.status, "applied_verification_pending")
        expected = json.loads(json.dumps(self.original))
        expected["action"]["target"]["entity_id"] = "light.kitchen"
        self.assertEqual(json.loads(self.fixture.read_text()), expected)
        # A write receipt alone is never a functional-success status.
        self.assertNotEqual(result.status, "verified")

    def test_no_approval_or_invented_token(self):
        for token in ("", "approve", "guessed-token", None):
            with self.subTest(token=token), self.assertRaises(RepairBlocked):
                self.engine.execute(self.plan, token, principal="owner")
        self.assertEqual(json.loads(self.fixture.read_text()), self.original)

    def test_only_owner_may_approve_and_execute(self):
        for principal in ("model", "", "admin"):
            with self.assertRaises(RepairBlocked):
                self.authority.approve(self.plan, principal=principal)
            with self.assertRaises(RepairBlocked):
                self.engine.execute(self.plan, self.approve(), principal=principal)

    def test_reject_and_manual_do_not_authorize_write(self):
        for decision in ("reject", "manual"):
            token = self.authority.decide(self.plan, principal="owner", decision=decision)
            with self.assertRaises(RepairBlocked):
                self.engine.execute(self.plan, token, principal="owner")

    def test_rejection_revokes_earlier_approval(self):
        token = self.approve()
        self.authority.decide(self.plan, principal="owner", decision="reject")
        with self.assertRaises(RepairBlocked):
            self.engine.execute(self.plan, token, principal="owner")

    def test_expired_and_invalid_ttl(self):
        for ttl in (0, -1, 1000, float("nan")):
            with self.assertRaises(RepairBlocked):
                self.authority.approve(self.plan, principal="owner", ttl=ttl)
        token = self.authority.approve(self.plan, principal="owner", ttl=1)
        self.now += 1
        with self.assertRaises(RepairBlocked):
            self.engine.execute(self.plan, token, principal="owner")

    def test_changed_plan_cannot_use_original_approval(self):
        token = self.approve()
        doc = self.plan.document
        doc["proposed"]["enabled"] = False
        changed = RepairPlan(canonical(doc))
        with self.assertRaises(RepairBlocked):
            self.engine.execute(changed, token, principal="owner")
        with self.assertRaises(RepairBlocked):
            self.authority.approve(changed, principal="owner")

    def test_plan_document_is_a_defensive_copy(self):
        snapshot = self.plan.serialized
        self.plan.document["risk"] = "high"
        self.assertEqual(self.plan.serialized, snapshot)

    def test_changed_target_invalidates_plan(self):
        token = self.approve()
        changed = dict(self.original, enabled=False)
        self.fixture.write_text(json.dumps(changed))
        with self.assertRaises(RepairBlocked):
            self.engine.execute(self.plan, token, principal="owner")
        self.assertEqual(json.loads(self.fixture.read_text()), changed)

    def test_token_is_bound_to_exact_plan_and_stored_only_hashed(self):
        token = self.approve()
        second = self.engine.prepare_entity_reference("incident-2", "automation.json", "light.old", "light.other",
            ["evidence-3"], "Jiný doložený cíl")
        with self.assertRaises(RepairBlocked):
            self.engine.execute(second, token, principal="owner")
        self.assertNotIn(token.encode(), self.db.read_bytes())

    def test_path_traversal_symlink_hardlink_are_blocked(self):
        for name in ("../automation.json", "/tmp/automation.json", "other.json"):
            with self.assertRaises(RepairBlocked):
                self.engine.prepare_entity_reference("i", name, "light.old", "light.kitchen", ["e"], "reason")
        self.fixture.rename(self.root / "other.json")
        self.fixture.symlink_to(self.root / "other.json")
        with self.assertRaises(RepairBlocked):
            self.prepare()
        self.fixture.unlink()
        os.link(self.root / "other.json", self.fixture)
        with self.assertRaises(RepairBlocked):
            self.prepare()

    def test_shared_directory_rejected(self):
        self.root.chmod(0o755)
        with self.assertRaises(RepairBlocked):
            RepairEngine(self.db, self.root, allowed_files={"automation.json"})
        self.root.chmod(0o700)

    def test_duplicate_execution_and_two_concurrent_workers(self):
        token = self.approve()
        def execute():
            try:
                return self.engine.execute(self.plan, token, principal="owner").status
            except RepairBlocked:
                return "blocked"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: execute(), range(2)))
        self.assertCountEqual(results, ["applied_verification_pending", "blocked"])

    def test_restart_during_intent_never_replays(self):
        token = self.approve()
        def crash():
            raise SystemExit("simulated power loss")
        with self.assertRaises(SystemExit):
            self.engine.execute(self.plan, token, principal="owner", after_intent=crash)
        self.assertEqual(json.loads(self.fixture.read_text()), self.original)
        restarted = RepairEngine(self.db, self.root, allowed_files={"automation.json"}, clock=lambda: self.now)
        self.assertEqual(restarted.execution(self.plan.plan_id).status, "intent_recorded")
        with self.assertRaises(RepairBlocked):
            restarted.execute(self.plan, token, principal="owner")
        # A fresh approval also cannot replay an ambiguous intent.
        with self.assertRaises(RepairBlocked):
            restarted.execute(self.plan, self.approve(), principal="owner")

    def test_restart_after_write_before_receipt_never_replays(self):
        token = self.approve()
        replace = self.engine._replace
        def crash_after_write(filename, content):
            replace(filename, content)
            raise SystemExit("power loss after atomic replace")
        self.engine._replace = crash_after_write
        with self.assertRaises(SystemExit):
            self.engine.execute(self.plan, token, principal="owner")
        restarted = RepairEngine(self.db, self.root, allowed_files={"automation.json"}, clock=lambda: self.now)
        with self.assertRaises(RepairBlocked):
            restarted.execute(self.plan, self.approve(), principal="owner")

    def test_rollback_requires_its_own_approval(self):
        token = self.approve()
        self.engine.execute(self.plan, token, principal="owner")
        rollback = self.engine.prepare_rollback(self.plan, ["verification-failed"])
        with self.assertRaises(RepairBlocked):
            self.engine.execute(rollback, token, principal="owner")
        self.engine.execute(rollback, self.approve(rollback), principal="owner")
        self.assertEqual(json.loads(self.fixture.read_text()), self.original)

    def test_risky_operation_and_unverified_backup_fail_closed(self):
        document = self.plan.document
        document["backup"]["onedrive_required"] = True
        document["risk"] = "high"
        risky = RepairPlan(canonical(document))
        # Even a trusted planner registration cannot enable unsupported risky ops.
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO repair_plans VALUES(?,?,?,?)", (risky.plan_id, risky.serialized,
                self.fixture.read_bytes(), self.now))
        with self.assertRaises(RepairBlocked):
            self.engine.execute(risky, self.approve(risky), principal="owner")


if __name__ == "__main__":
    unittest.main()
