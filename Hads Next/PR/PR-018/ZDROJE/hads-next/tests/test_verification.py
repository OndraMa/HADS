from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from hads_next.repair import ApprovalAuthority, ExecutionResult, RepairBlocked, RepairEngine
from hads_next.verification import FunctionalVerifier


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "automation.json").write_text(json.dumps({"id": "button", "action": {
            "service": "light.turn_on", "target": {"entity_id": "light.old"}}}))
        self.db = root / "case.sqlite"
        engine = RepairEngine(self.db, root, allowed_files={"automation.json"}, clock=lambda: 100)
        self.plan = engine.prepare_entity_reference("incident", "automation.json", "light.old", "light.kitchen",
            ["trace-1"], "Reference prokazatelně neexistuje", watch_seconds=30)
        token = ApprovalAuthority(self.db, clock=lambda: 100).approve(self.plan, principal="owner")
        self.execution = engine.execute(self.plan, token, principal="owner")
        self.verifier = FunctionalVerifier(self.db)
        self.good = [
            {"kind": "automation_triggered", "observed_at": 101, "payload": {"automation_id": "button", "context_id": "ctx-1"}},
            {"kind": "target_state", "observed_at": 102, "payload": {"entity_id": "light.kitchen", "state": "on", "context_id": "ctx-1"}},
            {"kind": "monitoring_checkpoint", "observed_at": 133, "payload": {"entity_id": "light.kitchen", "continuous_since": 101, "healthy": True}},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_context_bound_functional_result_and_watch_interval(self):
        report = self.verifier.evaluate(self.plan, self.execution, self.good, now=133)
        self.assertEqual(report["classification"], "Vyřešeno a ověřeno")
        self.assertEqual(self.verifier.reports(self.execution.execution_id)[0], report)

    def test_fake_fix_disappearing_log_does_not_resolve(self):
        report = self.verifier.evaluate(self.plan, self.execution, [
            {"kind": "http_200", "observed_at": 102, "payload": {}},
            {"kind": "errors_disappeared", "observed_at": 133, "payload": {}},
        ], now=133)
        self.assertNotEqual(report["classification"], "Vyřešeno a ověřeno")

    def test_no_fresh_functional_data(self):
        report = self.verifier.evaluate(self.plan, self.execution, [], now=133)
        self.assertEqual(report["classification"], "Není dostatek důkazů")

    def test_old_future_wrong_context_and_wrong_entity_do_not_verify(self):
        for variant in ("old", "future", "context", "entity"):
            data = json.loads(json.dumps(self.good))
            if variant == "old":
                for item in data:
                    item["observed_at"] -= 100
            elif variant == "future":
                for item in data:
                    item["observed_at"] += 100
            elif variant == "context":
                data[1]["payload"]["context_id"] = "unrelated"
            else:
                data[1]["payload"]["entity_id"] = "light.other"
            report = self.verifier.evaluate(self.plan, self.execution, data, now=133)
            self.assertNotEqual(report["classification"], "Vyřešeno a ověřeno", variant)

    def test_monitoring_gap_or_short_interval_does_not_verify(self):
        for variant in ("gap", "short", "unhealthy", "missing"):
            data = json.loads(json.dumps(self.good))
            if variant == "gap":
                data[2]["payload"]["continuous_since"] = 103
            elif variant == "short":
                data[2]["observed_at"] = 110
            elif variant == "unhealthy":
                data[2]["payload"]["healthy"] = False
            else:
                data.pop()
            report = self.verifier.evaluate(self.plan, self.execution, data, now=133)
            self.assertNotEqual(report["classification"], "Vyřešeno a ověřeno", variant)

    def test_recurrence_reopens_incident_and_failure_remains_open(self):
        failure = {"kind": "functional_failure", "observed_at": 134, "payload": {"entity_id": "light.kitchen"}}
        report = self.verifier.evaluate(self.plan, self.execution, [failure], now=134)
        self.assertEqual(report["classification"], "Oprava selhala")
        report = self.verifier.evaluate(self.plan, self.execution, self.good + [failure], now=134)
        self.assertEqual(report["classification"], "Problém se opakoval")

    def test_forged_execution_and_mutated_plan_cannot_verify(self):
        forged = replace(self.execution, execution_id="invented")
        with self.assertRaises(RepairBlocked):
            self.verifier.evaluate(self.plan, forged, self.good, now=133)
        plan = replace(self.plan, serialized=self.plan.serialized + " ")
        with self.assertRaises(RepairBlocked):
            self.verifier.evaluate(plan, self.execution, self.good, now=133)


if __name__ == "__main__":
    unittest.main()
