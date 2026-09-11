import copy
from contextlib import ExitStack
import datetime as dt
import unittest
from unittest import mock

import hads4
import test_rc8_regressions as legacy
import test_430_workflow as workflow
from tool_adapters import ToolAdapterBus


class Audit461Tests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown
    _case_and_plan = legacy.RC8RegressionTests._case_and_plan
    no_plan_root = workflow.Workflow430Tests.no_plan_root

    def plan(self, **kwargs):
        bus = mock.Mock()
        bus.collect.return_value = {"used": [], "evidence": []}
        return hads4.first_officer().automatic_repair_planner(mock.Mock(), mock.Mock(), mock.Mock(return_value={"summary": "Insufficient evidence"}), bus, **kwargs)

    def test_log_test_reports_partial_and_does_not_infer_success_from_rows(self):
        with mock.patch.dict(hads4.runtime, {"log_collection_test": {"job_id": "test", "status": "running"}}), mock.patch.object(hads4, "run_quick_scan", return_value={"collection_state": "partial", "failed_sources": [{"name": "host"}]}):
            hads4._run_log_collection_test("test")
            result = hads4.log_collection_test_status("test")
            self.assertEqual("partial", result["status"])
            self.assertEqual("host", result["failed_sources"][0]["name"])
            self.assertEqual("unknown", hads4.log_collection_test_status("other")["status"])

    def test_log_test_busy_and_exception_are_not_success(self):
        with mock.patch.dict(hads4.runtime, {"running": True}):
            self.assertFalse(hads4.start_log_collection_test()["ok"])
        with mock.patch.dict(hads4.runtime, {"log_collection_test": {"job_id": "test", "status": "running"}}), mock.patch.object(hads4, "run_quick_scan", side_effect=RuntimeError("failure")):
            hads4._run_log_collection_test("test")
            self.assertEqual("failed", hads4.log_collection_test_status("test")["status"])

    def test_quick_scan_runs_local_planner_and_respects_disable_option(self):
        for enabled in (True, False):
            with ExitStack() as stack:
                for name in ("capture_metrics", "refresh_new_occurrence_contexts", "update_recurrence_and_fixes", "recalculate_smart_priorities", "build_correlations", "verify_recoveries", "cleanup", "notify_urgent_cases", "end_task", "log"):
                    stack.enter_context(mock.patch.object(hads4, name, return_value={}))
                stack.enter_context(mock.patch.object(hads4, "begin_task", return_value=True))
                stack.enter_context(mock.patch.object(hads4, "options", return_value={"periodic_investigation": enabled}))
                stack.enter_context(mock.patch.object(hads4, "run_log_pass", return_value={"ok": True}))
                stack.enter_context(mock.patch.object(hads4.threading, "Thread"))
                external = stack.enter_context(mock.patch.object(hads4, "collect_external_diagnostics", return_value={}))
                rebuild = stack.enter_context(mock.patch.object(hads4, "rebuild_first_officer", return_value={}))
                result = hads4.run_quick_scan("scheduler")
                self.assertTrue(result["ok"])
                rebuild.assert_called_once_with(enabled)
                self.assertEqual(enabled, external.called)

    def test_automatic_watching_is_investigated(self):
        root = self.no_plan_root()
        with hads4.db() as conn:
            conn.execute("UPDATE root_cases SET decision_state='watching' WHERE id=?", (root,))
        self.assertEqual(1, self.plan()["processed"])

    def test_explicit_acceptance_still_blocks_automatic_research(self):
        root = self.no_plan_root()
        hads4.first_officer().decide(root, "accept_analysis", "I accept the conclusion")
        self.assertEqual(0, self.plan()["processed"])

    def test_latest_decision_not_old_acceptance_controls_monitoring(self):
        root = self.no_plan_root()
        officer = hads4.first_officer()
        officer.decide(root, "accept_analysis", "Old decision")
        officer.decide(root, "reinvestigate", "New evidence")
        with hads4.db() as conn:
            conn.execute("UPDATE root_cases SET decision_state='watching' WHERE id=?", (root,))
        self.assertEqual("automatic", officer.root_case(root)["state_origin"])
        self.assertEqual(1, self.plan()["processed"])

    def test_cooldown_and_explicit_reinvestigation(self):
        root = self.no_plan_root()
        self.assertEqual(1, self.plan()["processed"])
        self.assertEqual(0, self.plan()["processed"])
        self.assertEqual(1, self.plan(root_ids=[root])["processed"])

    def test_unresearched_case_is_not_starved_by_first_case(self):
        first = self.no_plan_root()
        officer = hads4.first_officer()
        roots = officer.list_roots()
        second = {**roots[0], "id": first + 1000}
        with hads4.db() as conn:
            conn.execute("INSERT INTO root_cases(id,fingerprint,title,decision_state,first_seen,last_seen,created_at,updated_at) VALUES(?,?,?,'investigating',?,?,?,?)",
                         (second["id"], "second-test-root", "Second case", *([hads4.now_utc()] * 4)))
        # The selector is tested against a real planner history and two roots;
        # details are reused because only fair selection matters here.
        self.plan(root_ids=[first])
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
        with hads4.db() as conn:
            conn.execute("UPDATE planner_runs SET finished_at=?", (old,))
        selected = []
        original = officer.root_case
        def detail(root_id):
            selected.append(root_id)
            return original(first)
        bus = mock.Mock()
        bus.collect.return_value = {"used": [], "evidence": []}
        with mock.patch.object(officer, "list_roots", return_value=[roots[0], second]), mock.patch.object(officer, "root_case", side_effect=detail):
            officer.automatic_repair_planner(mock.Mock(), mock.Mock(), mock.Mock(return_value={}), bus, limit=1)
        self.assertEqual([second["id"]], selected)

    def test_provider_name_never_links_unrelated_findings(self):
        case = {"source_ref": "inspector:one", "integration": "Automation Inspector", "title": "automation.one"}
        other = {"source_ref": "inspector:two", "integration": "Automation Inspector", "evidence": {"identifiers": ["automation.one"]}}
        self.assertFalse(ToolAdapterBus._finding_matches_case(other, case))
        self.assertTrue(ToolAdapterBus._finding_matches_case({**other, "source_ref": "inspector:one"}, case))
        self.assertFalse(ToolAdapterBus._finding_matches_case({"evidence": {"identifiers": [""]}}, {}))

    def test_identifier_match_is_not_substring_match(self):
        item = {"evidence": {"identifiers": ["light.room"]}}
        self.assertFalse(ToolAdapterBus._finding_matches_case(item, {"title": "light.room_2"}))
        self.assertTrue(ToolAdapterBus._finding_matches_case(item, {"title": "Error for light.room.".rstrip(".")}))

    def test_selector_uses_exact_path_even_with_repeated_values(self):
        before = {"alias": "any", "actions": [{"options": {"behavior": "any"}}, {"options": {"behavior": "any"}}]}
        original = copy.deepcopy(before)
        after, ok = hads4._edit_exact_provider_path(before, "$.actions[1].options.behavior", "any", "each")
        self.assertTrue(ok)
        self.assertEqual("each", after["actions"][1]["options"]["behavior"])
        self.assertEqual("any", after["actions"][0]["options"]["behavior"])
        self.assertEqual(original, before)

    def test_stale_invalid_or_ambiguous_provider_path_never_changes_config(self):
        before = {"actions": [{"behavior": "all"}]}
        for path in ("$.actions[0].behavior", "$.actions[*].behavior", "$.actions[100].behavior", "$..behavior", "$.missing"):
            after, ok = hads4._edit_exact_provider_path(before, path, "any", "each")
            self.assertFalse(ok)
            self.assertEqual(before, after)

    def test_loaded_spook_with_zero_repairs_is_detected(self):
        def supervisor(path, **kwargs):
            if path == "/core/api/components":
                return ["spook"]
            if path == "/addons":
                return {"addons": []}
            return []
        bus = ToolAdapterBus(hads4.db, hads4.now_utc, supervisor, lambda command: [], lambda: None)
        with mock.patch.object(bus, "_auto_mcp_urls", return_value={}), mock.patch.object(bus, "_auto_json_connector", return_value=(None, "")):
            result = bus.refresh(force=True)["adapters"]["spook"]
        self.assertTrue(result["installed"])
        self.assertTrue(result["connection_verified"])
        self.assertEqual(0, result["findings_count"])

    def test_trace_queries_use_internal_automation_id_and_are_read_only(self):
        rows = [{"run_id": "run1", "timestamp": {"start": "2026-09-07T10:00:00Z"}}]
        with mock.patch.object(hads4, "supervisor_request", return_value={"entity_id": "automation.renamed", "state": "on", "attributes": {"id": "123456"}}), mock.patch.object(hads4, "ha_ws_read", side_effect=[rows, {"error": "Unknown service"}]) as ws:
            result = hads4.automation_trace_context("automation.renamed")
        self.assertEqual("live_trace_api", result["source"])
        self.assertFalse(result["historical"])
        self.assertEqual("123456", ws.call_args_list[0].kwargs["item_id"])
        self.assertEqual(["trace/list", "trace/get"], [call.args[0] for call in ws.call_args_list])

    def test_absent_automation_id_is_not_guessed(self):
        with mock.patch.object(hads4, "supervisor_request", return_value={"attributes": {}}), mock.patch.object(hads4, "ha_ws_read") as ws:
            result = hads4.automation_trace_context("automation.renamed")
        self.assertFalse(result["available"])
        ws.assert_not_called()

    def test_empty_trace_list_is_not_claimed_as_successful_automation(self):
        with mock.patch.object(hads4, "supervisor_request", return_value={"attributes": {"id": "123"}}), mock.patch.object(hads4, "ha_ws_read", return_value=[]):
            result = hads4.automation_trace_context("automation.test")
        self.assertTrue(result["available"])
        self.assertEqual([], result["traces"])
        self.assertIn("nedokazuje", result["note"])

    def test_orphaned_codex_update_entity_is_not_installed_addon(self):
        def supervisor(path, **kwargs):
            if path == "/core/api/states":
                return [{"entity_id": "update.codex_terminal_pro", "state": "off", "attributes": {}}]
            if path == "/addons":
                return {"addons": []}
            return []
        bus = ToolAdapterBus(hads4.db, hads4.now_utc, supervisor, lambda command: [], lambda: None)
        with mock.patch.object(bus, "_auto_mcp_urls", return_value={}), mock.patch.object(bus, "_auto_json_connector", return_value=(None, "")):
            result = bus.refresh(force=True)["adapters"]["codex_terminal_pro"]
        self.assertFalse(result["installed"])


if __name__ == "__main__":
    unittest.main()
