"""Orchestration tests use a declared test receipt; native runtime has its own smoke."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from hads_next import cli
from hads_next.evidence import IncidentStore
from hads_next.investigation import HERMES_REVISION, ReadGateway
from hads_next.repair import RepairBlocked


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "isolated"
        self.incident = cli.initialize(self.workspace, now=100)
        self.snapshots = cli.read_json(self.workspace / "snapshots.json")
        # This is ONLY a protocol fixture; test does not claim to run Hermes.
        self.receipt = {"engine": "NousResearch/hermes-agent", "revision": HERMES_REVISION,
            "completed": True, "snapshot_sha256": ReadGateway(self.snapshots).snapshot_sha256,
            "execution_authority": "none", "model": "scripted-local-endpoint-no-cost",
            "scope": "offline-container", "read_receipts": [{"source": "automation"}, {"source": "trace"}],
            "model_requests": 3, "summary_cs": "Syntetický protokolový test."}
        self.receipt_path = self.workspace / "test-receipt.json"
        cli.write_json(self.receipt_path, self.receipt)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_offline_workflow_changes_real_fixture_and_stores_report(self):
        plan = cli.prepare(self.workspace, self.receipt_path)
        with self.assertRaises(FileNotFoundError):
            cli.execute(self.workspace)
        cli.decide(self.workspace, "approve")
        cli.execute(self.workspace)
        actual = cli.read_json(self.workspace / "fixtures/automation.json")
        self.assertEqual(actual["action"]["target"]["entity_id"], "light.living_room")
        report = cli.run_fixture_test(self.workspace)
        self.assertEqual(report["classification"], "Vyřešeno a ověřeno")
        self.assertEqual(report["scope"], "offline_isolated_fixture")
        case = IncidentStore(self.workspace / "state.sqlite").case(self.incident["id"])
        self.assertEqual(case["incident"]["status"], "resolved")
        with self.assertRaises(RepairBlocked):
            cli.execute(self.workspace)
        export = (self.workspace / "command-center.html").read_text()
        self.assertNotIn("V místním rozhraní příkazové řádky otevři přesný plán", export)
        token = cli.read_json(self.workspace / "decision.json")["token"]
        self.assertNotIn(token, export)
        self.assertNotIn(token, (self.workspace / "case-export.json").read_text())
        self.assertEqual(plan.plan_id, cli.load_plan(self.workspace).plan_id)

    def test_unfixed_fixture_cannot_pass_functional_runner(self):
        cli.prepare(self.workspace, self.receipt_path)
        cli.decide(self.workspace, "approve")
        cli.execute(self.workspace)
        # Fault injection restores the bad reference; even with a good execution
        # receipt the real fixture runner must fail the functional condition.
        cli.write_json(self.workspace / "fixtures/automation.json", self.snapshots["automation"])
        report = cli.run_fixture_test(self.workspace)
        self.assertEqual(report["classification"], "Oprava selhala")
        self.assertEqual(IncidentStore(self.workspace / "state.sqlite").case(self.incident["id"])["incident"]["status"], "open")

    def test_stale_or_unrelated_runtime_receipt_is_rejected(self):
        self.receipt["snapshot_sha256"] = "unrelated"
        cli.write_json(self.receipt_path, self.receipt)
        with self.assertRaises(RepairBlocked):
            cli.prepare(self.workspace, self.receipt_path)
        self.assertFalse((self.workspace / "plan.json").exists())

    def test_new_failure_reopens_resolved_case_and_deduplicates_repeated_checks(self):
        cli.prepare(self.workspace, self.receipt_path)
        cli.decide(self.workspace, "approve")
        execution = cli.execute(self.workspace)
        cli.run_fixture_test(self.workspace)
        stamp = execution.completed_at + 40
        failure = [{"kind": "functional_failure", "observed_at": stamp,
            "payload": {"entity_id": "light.living_room"}}]
        path = self.workspace / "recurrence.json"
        cli.write_json(path, failure)
        for _ in range(2):
            report = cli.verify(self.workspace, path, now=stamp + 1)
            self.assertEqual(report["classification"], "Problém se opakoval")
            case = IncidentStore(self.workspace / "state.sqlite").case(self.incident["id"])
            self.assertEqual(case["incident"]["status"], "open")
            self.assertEqual(len(case["occurrences"]), 2)
        self.assertNotIn("<h3>Vyřešeno a ověřeno</h3>", (self.workspace / "command-center.html").read_text())

    def test_initialize_never_overwrites_existing_workspace(self):
        with self.assertRaises(FileExistsError):
            cli.initialize(self.workspace)
        self.assertEqual(os.stat(self.workspace).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
