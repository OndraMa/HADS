import unittest
from unittest import mock
import hads4
import incident_workflow
import test_rc8_regressions as legacy


class Budget463Tests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown

    def test_cap_does_not_send_another_request(self):
        case_id, _, _ = legacy.RC8RegressionTests._case_and_plan(self)
        send = mock.Mock(return_value={"status": "completed"})
        cfg = {"ai_daily_call_limit": 1}
        incident_workflow.metered_call(hads4.db, hads4.now_utc, cfg, case_id, "", {}, send)
        with self.assertRaises(incident_workflow.AIBudgetExhausted):
            incident_workflow.metered_call(hads4.db, hads4.now_utc, cfg, case_id, "", {}, send)
        self.assertEqual(1, send.call_count)

    def test_budget_preserves_local_evidence(self):
        evidence = {"used": ["watchman"], "evidence": [{"adapter": "watchman", "payload": {"missing": "light.test"}}]}
        with mock.patch.object(hads4, "case_detail", return_value={}), mock.patch.object(hads4, "derive_verified_repair_actions", return_value={"decisions": [{"status": "needs_choice"}]}), mock.patch.object(hads4, "options", return_value={"ai_background_research": True}), mock.patch.object(hads4, "research_case", side_effect=incident_workflow.AIBudgetExhausted("limit")):
            result = hads4.planner_research(1, "inspect", evidence)
        self.assertEqual("local_budget_limited", result["mode"])
        self.assertEqual("limit", result["ai_deferred_reason"])
        self.assertEqual(["watchman"], result["adapter_ids"])
        self.assertEqual("needs_choice", result["deterministic_planner"]["decisions"][0]["status"])
        self.assertNotIn("repair_actions", result)

    def test_other_failures_are_not_suppressed(self):
        with mock.patch.object(hads4, "case_detail", return_value={}), mock.patch.object(hads4, "derive_verified_repair_actions", return_value={}), mock.patch.object(hads4, "options", return_value={"ai_background_research": True}), mock.patch.object(hads4, "research_case", side_effect=RuntimeError("real error")):
            with self.assertRaises(RuntimeError):
                hads4.planner_research(1, "inspect", {})
