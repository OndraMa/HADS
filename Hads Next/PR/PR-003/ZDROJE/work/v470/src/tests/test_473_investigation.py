import json
import unittest
from contextlib import closing
from unittest import mock
from urllib.parse import urlparse, parse_qs

import hads4
import investigation as inv
import test_rc8_regressions as legacy

START = "2026-09-13T00:00:00+02:00"
END = "2026-09-14T00:00:00+02:00"


class ReadOnlyTests(unittest.TestCase):
    def reader(self, get=None, ws=None):
        return inv.Investigator(get or mock.Mock(), ws or mock.Mock(), None, lambda: END)

    def test_invalid_entity_cannot_become_request_path(self):
        get = mock.Mock()
        for value in ["../services/homeassistant/restart", "light.lamp?x=y", "light.lamp/", "LIGHT.lamp", "http://attacker"]:
            with self.assertRaises(ValueError):
                self.reader(get).live_state(value)
        get.assert_not_called()

    def test_live_read_never_uses_observer_cache(self):
        get = mock.Mock(return_value={"entity_id": "light.lamp", "state": "on", "attributes": {"access_token": "private"}})
        result = self.reader(get).live_state("light.lamp")
        self.assertEqual("ok", result["status"])
        self.assertEqual("on", result["data"]["state"])
        self.assertNotIn("access_token", result["data"]["attributes"])
        self.assertFalse(get.call_args.kwargs["allow_stale"])

    def test_wrong_entity_response_is_unavailable(self):
        result = self.reader(mock.Mock(return_value={"entity_id": "light.other", "state": "on"})).live_state("light.lamp")
        self.assertEqual("unavailable", result["status"])

    def test_api_failure_does_not_mean_healthy(self):
        result = self.reader(mock.Mock(side_effect=OSError("502"))).live_state("light.lamp")
        self.assertEqual("unavailable", result["status"])
        self.assertNotIn("data", result)

    def test_window_requires_timezone_and_bounds(self):
        for a, b in [("2026-09-13", "2026-09-14"), (END, START), (START, "2026-09-17T00:00:00+02:00")]:
            with self.assertRaises(ValueError):
                inv.window(a, b)
        self.assertEqual("2026-09-12T22:00:00+00:00", inv.window(START, END)[0])

    def test_unknown_incident_time_is_not_now(self):
        with self.assertRaises(ValueError):
            inv.case_window({})

    def test_empty_history_is_missing_coverage(self):
        get = mock.Mock(return_value=[])
        result = self.reader(get).history("light.lamp", START, END)
        self.assertEqual("no_records_unknown_coverage", result["data"]["coverage"])
        query = parse_qs(urlparse(get.call_args.args[0]).query)
        self.assertEqual(["light.lamp"], query["filter_entity_id"])
        self.assertEqual(["2026-09-13T22:00:00+00:00"], query["end_time"])

    def test_history_truncation_is_explicit(self):
        get = mock.Mock(return_value=[[{"state": "on", "last_changed": START}] * 300])
        result = self.reader(get).history("light.lamp", START, END)["data"]
        self.assertEqual(180, result["omitted"])
        self.assertEqual(120, len(result["records"]))

    def test_same_device_battery_not_similar_name(self):
        registry = [{"entity_id": "light.lamp", "device_id": "one", "platform": "zha"},
                    {"entity_id": "sensor.random_battery", "device_id": "one"},
                    {"entity_id": "sensor.lamp_battery", "device_id": "two"}]
        def get(path, **kwargs):
            if "/history/" in path:
                return []
            return {"entity_id": path.rsplit("/", 1)[-1], "state": "20", "attributes": {}}
        ws = mock.Mock(side_effect=[registry, [{"id": "one", "model": "lamp"}]])
        result = self.reader(get, ws).device("light.lamp", START, END)
        self.assertEqual(["sensor.random_battery"], [r["entity_id"] for r in result["related_telemetry"]])

    def test_disabled_sensor_not_enabled_or_queried(self):
        registry = [{"entity_id": "light.lamp", "device_id": "one"}, {"entity_id": "sensor.battery", "device_id": "one", "disabled_by": "user"}]
        get = mock.Mock(side_effect=[{"entity_id": "light.lamp", "state": "on"}, []])
        result = self.reader(get, mock.Mock(side_effect=[registry, [{"id": "one"}]])).device("light.lamp", START, END)
        self.assertEqual("disabled_not_enabled_by_diagnosis", result["related_telemetry"][0]["coverage"])
        self.assertEqual(2, get.call_count)

    def test_missing_registry_does_not_infer_association(self):
        get = mock.Mock(side_effect=[{"entity_id": "light.lamp", "state": "on"}, []])
        result = self.reader(get, mock.Mock(side_effect=OSError("offline"))).device("light.lamp", START, END)
        self.assertTrue(result["coverage_gaps"])
        self.assertEqual([], result["related_telemetry"])

    def test_missing_addon_is_not_installed(self):
        get = mock.Mock(return_value={"addons": []})
        result = self.reader(get).addon_log("codex_terminal")
        self.assertEqual("unavailable", result["status"])
        self.assertEqual(1, get.call_count)

    def test_zigbee_log_reads_only_discovered_addon(self):
        get = mock.Mock(side_effect=[{"addons": [{"slug": "test_zigbee2mqtt"}]}, "\n".join(str(x) for x in range(200))])
        result = self.reader(get).addon_log("test_zigbee2mqtt")
        self.assertEqual("ok", result["status"])
        self.assertEqual(50, result["data"]["omitted_lines"])
        self.assertEqual("/addons/test_zigbee2mqtt/logs", get.call_args.args[0])
        self.assertNotIn("method", get.call_args.kwargs)

    def test_log_source_is_not_arbitrary_url(self):
        get = mock.Mock()
        with self.assertRaises(ValueError):
            self.reader(get).source_log("/addons/self/restart")
        get.assert_not_called()

    def test_tool_json_is_valid_even_when_oversized(self):
        result = json.loads(hads4._officer_tool_output({"text": "ž" * 40000}))
        self.assertEqual("truncated", result["status"])
        self.assertIn("coverage_warning", result)

    def test_context_compaction_preserves_reasoning_and_call_pairs(self):
        reasoning = {"type": "reasoning", "encrypted_content": "must-remain-intact"}
        items = [reasoning]
        for n in range(8):
            items += [{"type": "function_call", "call_id": str(n), "name": "hads_get_case", "arguments": "{}"},
                      {"type": "function_call_output", "call_id": str(n), "output": json.dumps({"text": "x"*10000})}]
        result = hads4._fit_officer_context({}, items)
        self.assertEqual(reasoning, result[0])
        self.assertEqual(17, len(result))
        self.assertLess(len(json.dumps(result).encode()), 58000)
        self.assertEqual("context_compacted", json.loads(result[2]["output"])["status"])
        self.assertEqual("x"*10000, json.loads(items[2]["output"])["text"])

    def test_questions_need_reason_cannot_be_read(self):
        base = {"summary": "Ovladač nebyl použit?", "decision_kind": "needs_user_input"}
        self.assertEqual("investigating", inv.disposition(base))
        base["user_question"] = {"question": "Rozsvítila se fyzicky lampička?", "why_readonly_cannot_answer": "Zařízení neposkytuje nezávislé potvrzení skutečného světla."}
        self.assertEqual("needs_information", inv.disposition(base))

    def test_model_verified_boolean_is_not_proof(self):
        self.assertEqual("investigating", inv.disposition({"summary": "Vše zdravé", "conclusion_verified": True}))

    def test_plan_selection_does_not_include_other_approvals(self):
        with mock.patch.object(hads4, "_approved_plans_raw", return_value=[{"id": 1}, {"id": 2}]):
            self.assertEqual([{"id": 2}], hads4._select_approved_plans([2]))
            for ids in [[3], [1, 1], [True], [], "1"]:
                with self.assertRaises(hads4.RepairError):
                    hads4._select_approved_plans(ids)

    def test_hardware_advice_can_be_reviewed_but_not_executed(self):
        analysis = {"summary": "Posoudit rozšíření RAM", "decision_kind": "advisory", "functional_impact": "Core opakovaně ukončen OOM",
                    "next_test": "Ověřit host kapacitu a opakování po skončení importu", "hypotheses": [{"evidence_for": ["Kernel OOM záznam"]}]}
        self.assertEqual("review_ready", inv.disposition(analysis))
        self.assertNotIn("repair_actions", analysis)


class DatabaseEvidenceTests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown
    _case_and_plan = legacy.RC8RegressionTests._case_and_plan

    def test_one_step_approval_launches_only_exact_plan(self):
        case, plan, root = self._case_and_plan()
        with mock.patch.object(hads4, "launch_approved_batch", return_value={"status": "starting"}) as launch:
            result = hads4.approve_and_launch_repair(plan, {"confirmation": f"SCHVALUJI HADS4-{plan:04d}", "execution_confirmation": f"EXECUTE HADS4-{plan:04d}"})
        launch.assert_called_once_with([plan])
        self.assertEqual("starting", result["status"])
        self.assertEqual("approved", hads4.repair_plan_detail(plan)["status"])
        with mock.patch.object(hads4, "launch_approved_batch") as launch:
            with self.assertRaises(hads4.RepairError):
                hads4.approve_and_launch_repair(plan, {"confirmation": f"SCHVALUJI HADS4-{plan:04d}", "execution_confirmation": f"EXECUTE HADS4-{plan:04d}"})
            launch.assert_not_called()

    def test_approval_without_execution_consent_does_not_start(self):
        case, plan, root = self._case_and_plan()
        with mock.patch.object(hads4, "launch_approved_batch") as launch:
            with self.assertRaises(hads4.RepairError):
                hads4.approve_and_launch_repair(plan, {"confirmation": f"SCHVALUJI HADS4-{plan:04d}"})
            launch.assert_not_called()
        self.assertEqual("pending_approval", hads4.repair_plan_detail(plan)["status"])

    def test_recorder_rescue_contains_consistent_database(self):
        import sqlite3
        import zipfile
        config = self.test_root / "recorder_config"
        config.mkdir()
        source = config / "history.db"
        with closing(sqlite3.connect(source)) as conn, conn:
            conn.execute("CREATE TABLE states(id INTEGER)")
            conn.execute("CREATE TABLE events(id INTEGER)")
            conn.execute("INSERT INTO states VALUES(42)")
        cfg = {"recorder_maintenance_enabled": True, "recorder_sqlite_path": "history.db"}
        with mock.patch.object(hads4, "config_root", return_value=config), mock.patch.object(hads4, "options", return_value=cfg):
            rescue = hads4.first_officer().prepare_rescue(123, [{"id": 1, "title": "Purge", "actions": [{"type": "recorder_purge"}]}], {})
        with zipfile.ZipFile(rescue["path"]) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn("originals/recorder-before.db", archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual("ok", manifest["recorder_snapshot"]["quick_check"])
            self.assertEqual(manifest["recorder_snapshot"]["sha256"], __import__('hashlib').sha256(archive.read("originals/recorder-before.db")).hexdigest())
        with closing(sqlite3.connect(source)) as conn:
            self.assertEqual(42, conn.execute("SELECT id FROM states").fetchone()[0])

    def test_memory_has_container_scope_and_lifecycle(self):
        with hads4.db() as conn:
            conn.execute("INSERT INTO metrics(measured_at,source,name,value,unit) VALUES(?,?,?,?,?)", (START, "core", "core.memory_percent", 96, "%"))
        addons = [{"slug": f"addon_{i}", "state": "started"} for i in range(12)]
        def get(path, **kwargs):
            self.assertFalse(kwargs["allow_stale"])
            return {"addons": addons} if path == "/addons" else {"memory_usage": 100, "memory_limit": 200}
        reader = inv.Investigator(get, mock.Mock(), hads4.db, hads4.now_utc)
        result = reader.resources(START, END)
        self.assertEqual(8, len(result["containers"]))
        self.assertEqual(1, result["next_page"])
        self.assertEqual(96, result["metric_history"]["series"][0]["maximum"])
        self.assertTrue(result["coverage_gaps"])
        second = reader.resources(START, END, 1)
        self.assertEqual(4, len(second["containers"]))
        self.assertIsNone(second["next_page"])

    def test_failed_repair_is_reinvestigated_not_executed(self):
        case, plan, root = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("UPDATE repair_plans SET status='failed' WHERE id=?", (plan,))
            conn.execute("UPDATE root_cases SET decision_state='repair_failed' WHERE id=?", (root,))
        bus = mock.Mock()
        bus.collect.return_value = {"used": [], "evidence": []}
        research = mock.Mock(return_value={"summary": "Je třeba načíst stav po selhání"})
        result = hads4.first_officer().automatic_repair_planner(
            lambda *_: self.fail("No executable action"), lambda *_: self.fail("No new plan"), research, bus, root_ids=[root])
        self.assertEqual(1, result["processed"])
        self.assertEqual(1, research.call_count)
        detail = hads4.first_officer().root_case(root)
        self.assertEqual("repair_failed", detail["decision_state"])
        self.assertEqual(plan, detail["repair_plan_id"])
        with hads4.db() as conn:
            self.assertEqual("failed", conn.execute("SELECT status FROM repair_plans WHERE id=?", (plan,)).fetchone()[0])

    def test_old_verified_flag_alone_does_not_complete_investigation(self):
        case, plan, root = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("UPDATE root_cases SET repair_plan_id=NULL,decision_state='investigating' WHERE id=?", (root,))
        bus = mock.Mock()
        bus.collect.return_value = {"used": [], "evidence": []}
        result = hads4.first_officer().automatic_repair_planner(lambda *_: None, lambda *_: None,
            lambda *_: {"summary": "Trust me", "conclusion_verified": True}, bus, root_ids=[root])
        self.assertEqual("investigating", result["results"][0]["status"])

    def test_real_agent_loop_collects_evidence_then_synthesizes(self):
        case, _, _ = self._case_and_plan()
        cfg = {"openai_enabled": True, "openai_api_key": "test-only", "ai_call_limits_enabled": False,
               "ai_tool_max_rounds": 3, "openai_web_search_enabled": False}
        analysis = {"summary": "Zařízení nyní odpovídá, minulý výpadek není vysvětlen", "functional_impact": "Historický dopad nezjištěn",
                    "decision_kind": "investigate", "hypotheses": [], "missing_evidence": ["trace"], "next_test": "Načíst trace", "proposed_actions": [], "configuration_changes": [],
                    "user_question": {"question": "", "why_readonly_cannot_answer": ""}}
        first = {"status": "completed", "output": [{"type": "function_call", "name": "hads_get_live_state", "call_id": "call1", "arguments": json.dumps({"entity_id": "light.lamp"})}]}
        final = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(analysis)}]}]}
        calls = []
        def api(key, body):
            calls.append(json.loads(json.dumps(body)))
            return first if len(calls) == 1 else final
        with mock.patch.object(hads4, "options", return_value=cfg), mock.patch.object(hads4, "_openai_post", side_effect=api), mock.patch.object(hads4, "supervisor_request", return_value={"entity_id": "light.lamp", "state": "on"}) as transport:
            result = hads4.research_case(case, {})
        self.assertEqual(2, len(calls))
        outputs = [item for item in calls[1]["input"] if item.get("type") == "function_call_output"]
        self.assertEqual("call1", outputs[0]["call_id"])
        self.assertEqual("on", json.loads(outputs[0]["output"])["data"]["state"])
        self.assertEqual(1, result["tool_calls"])
        self.assertEqual("investigate", result["analysis"]["decision_kind"])
        self.assertTrue(all(c.kwargs.get("method", "GET") == "GET" for c in transport.call_args_list))
        with hads4.db() as conn:
            self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM ai_calls WHERE case_id=?", (case,)).fetchone()[0])
            observation = conn.execute("SELECT result_json FROM research_observations WHERE case_id=?", (case,)).fetchone()
            self.assertEqual("on", json.loads(observation[0])["data"]["state"])
