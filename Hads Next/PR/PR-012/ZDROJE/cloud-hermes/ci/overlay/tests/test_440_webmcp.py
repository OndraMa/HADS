import json
import time
import unittest
from pathlib import Path
from unittest import mock

import hads4
import site_tools
import test_rc8_regressions as legacy


class WebMCP440Tests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown
    _case_and_plan = legacy.RC8RegressionTests._case_and_plan

    def setUp(self):
        legacy.RC8RegressionTests.setUp(self)
        hads4.runtime["running"] = False
        hads4.runtime["active_task"] = None
        hads4.runtime["site_tool_task"] = None

    def test_version_and_database_contract(self):
        self.assertEqual("2.0.0-rc2", hads4.VERSION)
        with hads4.db() as conn:
            self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='site_tool_runs'").fetchone())

    def test_incident_list_is_bounded_and_filtered(self):
        roots = [
            {"id": index, "public_id": f"R-{index:03d}", "title": "x" * 700, "lifecycle": "ACTIVE", "decision_state": "investigating"}
            for index in range(1, 150)
        ]
        value = site_tools.list_incidents(roots, "investigating", 999)
        self.assertEqual(100, value["count"])
        self.assertLessEqual(len(value["incidents"][0]["title"]), 500)
        with self.assertRaises(ValueError):
            site_tools.list_incidents(roots, "approved_repairs", 10)

    def test_incident_detail_redacts_and_limits_untrusted_evidence(self):
        root = {
            "id": 1, "public_id": "R-001", "title": "Evidence", "lifecycle": "ACTIVE",
            "evidence": [{"case_id": 2, "state": "open", "sample": "token=SECRET " + "x" * 3000}] * 30,
            "symptoms": [{"title": "sample", "source": "core", "occurrences": 1}] * 40,
            "decisions": [{"decision": "watch", "reason": "token=SECRET"}] * 30,
        }
        value = site_tools.incident_detail(root, lambda text: text.replace("SECRET", "***"))
        incident = value["incident"]
        self.assertEqual(20, len(incident["evidence"]))
        self.assertEqual(30, len(incident["symptoms"]))
        self.assertNotIn("SECRET", json.dumps(value))
        self.assertLessEqual(len(incident["evidence"][0]["sample"]), 1200)

    def test_fix_plan_never_exposes_actions_or_confirmation_phrases(self):
        raw = {
            "id": 9, "title": "Plan", "status": "approved", "risk_level": "low",
            "actions": [{"type": "yaml_replace", "before": "secret", "after": "changed"}],
            "confirmation_phrase": "SCHVALUJI HADS4-0009", "rollback_phrase": "VRATIT HADS4-0009",
            "preview": [{"type": "yaml_replace", "target": "configuration.yaml", "description": "safe"}],
        }
        encoded = json.dumps(site_tools.fix_plan(raw), ensure_ascii=False)
        self.assertNotIn("actions", encoded)
        self.assertNotIn("before", encoded)
        self.assertNotIn("after", encoded)
        self.assertNotIn("SCHVALUJI", encoded)
        self.assertNotIn("VRATIT", encoded)

    def test_public_root_id_parser_is_strict(self):
        self.assertEqual(21, hads4.site_tool_root_id("R-021"))
        self.assertEqual(21, hads4.site_tool_root_id("r-021"))
        self.assertIsNone(hads4.site_tool_root_id("21"))
        self.assertIsNone(hads4.site_tool_root_id("R-1/decision"))

    def test_acceptance_snapshot_has_canonical_contract(self):
        self._case_and_plan()
        snapshot = hads4.site_tool_acceptance_snapshot()
        self.assertEqual(9, snapshot["contract"]["tool_count"])
        self.assertEqual(set(hads4.SITE_TOOL_NAMES), set(snapshot["contract"]["tools"]))
        self.assertTrue(snapshot["incidents"])
        self.assertEqual("2.0.0-rc2", snapshot["hads_version"])

    def test_diagnostic_requires_exact_visible_confirmation_marker(self):
        for payload in ({}, {"source": "webmcp"}, {"source": "other", "confirmation": "CAPTAIN_CONFIRMED_IN_HADS_UI"}):
            with self.assertRaises(Exception):
                hads4.launch_site_tool_diagnostic("quick", payload)
        with hads4.db() as conn:
            self.assertEqual(0, conn.execute("SELECT count(*) n FROM site_tool_runs").fetchone()["n"])

    def test_confirmed_quick_diagnostic_is_audited(self):
        completed = mock.Mock(return_value={"sources": 2, "parsed_events": 4, "new_occurrences": 1})
        with mock.patch.object(hads4, "run_quick_scan", completed):
            accepted = hads4.launch_site_tool_diagnostic("quick", {
                "source": "webmcp", "confirmation": "CAPTAIN_CONFIRMED_IN_HADS_UI",
            })
            deadline = time.time() + 3
            while time.time() < deadline:
                with hads4.db() as conn:
                    row = conn.execute("SELECT * FROM site_tool_runs WHERE id=?", (accepted["run_id"],)).fetchone()
                if row and row["finished_at"]:
                    break
                time.sleep(0.01)
        self.assertEqual("completed", row["status"])
        self.assertEqual(2, json.loads(row["result_json"])["sources"])
        completed.assert_called_once_with("webmcp")

    def test_config_check_records_invalid_without_modifying_configuration(self):
        with mock.patch.object(hads4, "supervisor_request", return_value={"result": "invalid", "errors": "bad yaml"}) as call:
            accepted = hads4.launch_site_tool_diagnostic("config-check", {
                "source": "webmcp", "confirmation": "CAPTAIN_CONFIRMED_IN_HADS_UI",
            })
            deadline = time.time() + 3
            while time.time() < deadline:
                with hads4.db() as conn:
                    row = conn.execute("SELECT * FROM site_tool_runs WHERE id=?", (accepted["run_id"],)).fetchone()
                if row and row["finished_at"]:
                    break
                time.sleep(0.01)
        self.assertEqual("failed", row["status"])
        self.assertIn("bad yaml", row["last_error"])
        call.assert_called_once_with("/core/check", method="POST", body={}, timeout=240)

    def test_webmcp_source_exposes_no_repair_mutation_tool(self):
        source = (Path(__file__).parents[1] / "web" / "webmcp.js").read_text(encoding="utf-8")
        for forbidden in ("hads_approve", "hads_execute", "hads_restart", "hads_rollback", "hads_shell"):
            self.assertNotIn(forbidden, source)
        self.assertIn("document.modelContext", source)
        self.assertIn("CAPTAIN_CONFIRMED_IN_HADS_UI", source)

    def test_ui_has_machine_readable_incident_contract(self):
        root = Path(__file__).parents[1]
        app = (root / "web" / "app.js").read_text(encoding="utf-8")
        page = (root / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-hads-root", app)
        self.assertIn("data-hads-public-id", app)
        self.assertIn("data-hads-state", app)
        self.assertIn("webmcp.js", page)
        self.assertIn("2.0.0-rc2", page)


if __name__ == "__main__":
    unittest.main()
