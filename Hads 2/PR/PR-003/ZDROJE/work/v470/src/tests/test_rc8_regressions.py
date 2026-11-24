import datetime as dt
import io
import shutil
import threading
import time
import unittest
import urllib.error
import uuid
from pathlib import Path
from unittest import mock

import hads4
from tool_adapters import ToolAdapterBus
from repair_engine import RepairEngine, canonical_json_hash


class RC8RegressionTests(unittest.TestCase):
    def setUp(self):
        self.network_guard = mock.patch('urllib.request.urlopen', side_effect=urllib.error.URLError('Test network is disabled'))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)
        test_root = Path.cwd() / ".test-tmp"
        test_root.mkdir(exist_ok=True)
        root = test_root / str(uuid.uuid4())
        root.mkdir()
        self.test_root = root
        hads4.DATA_DIR = root / "data"
        hads4.DB_PATH = hads4.DATA_DIR / "hads4.db"
        hads4.OPTIONS_PATH = hads4.DATA_DIR / "options.json"
        hads4.OUT_DIR = root / "share" / "hads4"
        hads4.COMPAT_OUT_DIR = root / "share" / "hads"
        hads4.RAW_DIR = hads4.OUT_DIR / "raw"
        hads4.EXPORT_DIR = hads4.OUT_DIR / "exports"
        hads4.REPAIR_PRIVATE_DIR = hads4.DATA_DIR / "repair_private"
        hads4.REPORT_SNAPSHOT_PATH = hads4.DATA_DIR / "snapshot.json"
        hads4.DASHBOARD_CARD_EXPORT = hads4.OUT_DIR / "card.yaml"
        hads4._tool_bus_instance = None
        hads4.supervisor_read_cache.clear()
        hads4.runtime["supervisor_reads"] = {}
        hads4.init_db()

    def tearDown(self):
        hads4._tool_bus_instance = None
        shutil.rmtree(self.test_root, ignore_errors=True)

    def _case_and_plan(self):
        occurred = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with hads4.db() as conn:
            hads4.ingest_event(conn, {
                "logger": "custom_components.meross_lan.api",
                "source_ref": "meross",
                "integration": "meross_lan",
                "occurred_at": occurred,
                "level": "WARNING",
                "message": "HomeAssistantError(mqtt_not_setup_cannot_publish) in async_poll",
                "source_name": "core",
            })
            case_id = int(conn.execute("SELECT id FROM cases").fetchone()["id"])
            now = hads4.now_utc()
            cursor = conn.execute(
                """INSERT INTO repair_plans(case_id,title,rationale,risk_level,status,actions_json,preview_json,
                   verification_json,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (case_id, "Restart Meross", "test", "low", "pending_approval",
                 '[{"type":"addon_restart","addon":"meross"}]', '[]', '{}', "test", now, now),
            )
            plan_id = int(cursor.lastrowid)
        hads4.first_officer().rebuild_root_cases()
        with hads4.db() as conn:
            root = conn.execute("SELECT id FROM root_cases").fetchone()
            root_id = int(root["id"])
            conn.execute(
                "UPDATE root_cases SET repair_plan_id=?,decision_state='awaiting_decision' WHERE id=?",
                (plan_id, root_id),
            )
        return case_id, plan_id, root_id

    def test_captain_approval_waits_for_writer_and_is_atomic_idempotent(self):
        _, plan_id, root_id = self._case_and_plan()
        entered = threading.Event()

        def writer():
            with hads4.db() as conn:
                conn.execute("INSERT INTO settings(key,value) VALUES('busy','1')")
                entered.set()
                time.sleep(0.25)

        thread = threading.Thread(target=writer)
        thread.start()
        self.assertTrue(entered.wait(2))
        result = hads4.first_officer_decide(root_id, {"decision": "approve"})
        thread.join(2)
        self.assertEqual("approved", result["decision_state"])
        hads4.first_officer_decide(root_id, {"decision": "approve"})
        with hads4.db() as conn:
            self.assertEqual("approved", conn.execute("SELECT status FROM repair_plans WHERE id=?", (plan_id,)).fetchone()["status"])
            self.assertEqual(1, conn.execute("SELECT count(*) n FROM captain_decisions WHERE root_case_id=?", (root_id,)).fetchone()["n"])
            self.assertEqual(1, conn.execute("SELECT count(*) n FROM repair_audit WHERE plan_id=? AND event_type='approved'", (plan_id,)).fetchone()["n"])

    def test_manual_intervention_cancels_batch_plan_and_becomes_watching(self):
        _, plan_id, root_id = self._case_and_plan()
        hads4.first_officer_decide(root_id, {"decision": "approve"})
        hads4.first_officer_decide(root_id, {"decision": "manual", "reason": "Opravím fyzicky"})
        view = hads4.first_officer_command_center()
        with hads4.db() as conn:
            self.assertEqual("cancelled", conn.execute("SELECT status FROM repair_plans WHERE id=?", (plan_id,)).fetchone()["status"])
        self.assertEqual(0, view["approved_plans"])
        self.assertFalse(any(root["id"] == root_id for root in view["root_cases"]))
        self.assertTrue(any(root["id"] == root_id for root in view["watching_cases"]))

    def test_inconsistent_rc7_approval_is_repaired_on_start(self):
        _, plan_id, root_id = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("UPDATE repair_plans SET status='approved',approved_at=? WHERE id=?", (hads4.now_utc(), plan_id))
            conn.execute("UPDATE root_cases SET decision_state='investigating' WHERE id=?", (root_id,))
        result = hads4.reconcile_repair_queue()
        self.assertEqual(1, result["approvals_reset"])
        with hads4.db() as conn:
            row = conn.execute("SELECT status,approved_at FROM repair_plans WHERE id=?", (plan_id,)).fetchone()
            self.assertEqual("pending_approval", row["status"])
            self.assertIsNone(row["approved_at"])

    def test_upload_ack_cannot_open_gate_without_independent_verifier(self):
        archive = self.test_root / "rescue.zip"
        archive.write_bytes(b"unique rescue")
        with mock.patch.object(hads4, "upload_onedrive_to", return_value={"ok": True, "response": []}), \
             mock.patch.object(hads4, "_onedrive_verifier_services", return_value=[]), \
             mock.patch.object(hads4, "options", return_value={"rescue_accept_upload_ack": True}):
            result = hads4.upload_and_verify_rescue(str(archive), "HADS/Repairs")
        self.assertFalse(result["verified"])
        self.assertEqual("none", result["method"])

    def test_empty_captain_queue_does_not_count_investigating_p2_as_action(self):
        occurred = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with hads4.db() as conn:
            hads4.ingest_event(conn, {
                "logger": "test.integration", "source_ref": "test", "integration": "test",
                "occurred_at": occurred, "level": "ERROR", "message": "functional failure",
                "source_name": "core", "analysis": {"priority": "P2", "title": "Test P2", "cause": "unknown"},
            })
        hads4.first_officer().rebuild_root_cases()
        snapshot = hads4.dashboard_snapshot()
        self.assertEqual(0, snapshot["captain_actions"])
        self.assertEqual(0, snapshot["pending_approvals"])
        self.assertGreaterEqual(snapshot["open_alerts"], 1)

    def test_core_137_wrappers_have_one_semantic_identity(self):
        variants = [
            '"title": "WARNING [supervisor.homeassistant.core] Watchdog found Home Assistant exited with code 137, restarting..."',
            '"normalized_message": "WARNING [supervisor.homeassistant.core] Watchdog found Home Assistant exited with code 137, restarting..."',
            '"sample": "WARNING [supervisor.homeassistant.core] Watchdog found Home Assistant exited with code 137, restarting..."',
        ]
        keys = {
            hads4.semantic_fingerprint("supervisor.homeassistant.core", "legacy", hads4.normalize(value), "home_assistant", {"title": value})
            for value in variants
        }
        self.assertEqual(1, len(keys))

    def test_integration_root_key_keeps_unrelated_causes_separate(self):
        base = {"category": "home_assistant", "integration": "demo", "source_ref": "", "logger": "demo"}
        first = hads4.first_officer()._group_key({**base, "probable_cause": "network timeout", "normalized_message": "network timeout", "title": "A"})
        second = hads4.first_officer()._group_key({**base, "probable_cause": "invalid authentication", "normalized_message": "invalid authentication", "title": "B"})
        self.assertNotEqual(first, second)

    def test_ha_mcp_discovers_generated_secret_from_addon_log(self):
        def supervisor(path, **kwargs):
            if path == "/addons":
                return {"addons": [{"slug": "81f33d0f_ha_mcp"}]}
            if path.endswith("/info"):
                return {"hostname": "81f33d0f-ha-mcp", "options": {"secret_path": ""}}
            if "/logs" in path:
                return "MCP Server URL: http://192.168.1.2:9583/private_generatedSecret123"
            raise AssertionError(path)

        bus = ToolAdapterBus(hads4.db, hads4.now_utc, supervisor, lambda command: [], lambda: None)
        self.assertEqual(
            "http://81f33d0f-ha-mcp:9583/private_generatedSecret123",
            bus._discover_ha_mcp_url(),
        )

    def test_ha_mcp_normalizes_underscore_hostname_returned_by_supervisor(self):
        def supervisor(path, **kwargs):
            if path == "/addons":
                return {"addons": [{"slug": "81f33d0f_ha_mcp"}]}
            if path.endswith("/info"):
                return {"hostname": "81f33d0f_ha_mcp", "options": {"secret_path": "private_generatedSecret123"}}
            raise AssertionError(path)

        bus = ToolAdapterBus(hads4.db, hads4.now_utc, supervisor, lambda command: [], lambda: None)
        self.assertEqual(
            "http://81f33d0f-ha-mcp:9583/private_generatedSecret123",
            bus._discover_ha_mcp_url(),
        )

    def test_hamster_can_list_tools_without_initialize(self):
        bus = ToolAdapterBus(hads4.db, hads4.now_utc, lambda path, **kwargs: {}, lambda command: [], lambda: None)

        def rpc(adapter_id, url, method, params=None):
            if method == "initialize":
                raise RuntimeError("{'code': -32601, 'message': 'Method not found: initialize'}")
            if method == "tools/list":
                return {"tools": [{"name": "search", "description": "read only", "inputSchema": {}}]}
            raise AssertionError(method)

        with mock.patch.object(bus, "_mcp_rpc", side_effect=rpc):
            result = bus._mcp_initialize("hamster_mcp", "http://supervisor/core/api/hamster_mcp")
        self.assertEqual("search", result["tools"][0]["name"])

    def test_generic_connector_imports_issue_bucket_and_provider_remediation(self):
        payload = {
            "schema_version": 2,
            "inspection": {
                "issues": [{
                    "automation_id": "arrival",
                    "issue": "Automation will not run: unknown service notify.mobile_app_ondrej_old",
                    "recommendation": "Replace it with notify.mobile_app_ondrej",
                }]
            },
        }
        findings = ToolAdapterBus._generic_json_findings("automation_inspector", payload)
        self.assertEqual(1, len(findings))
        self.assertEqual("P2", findings[0]["priority"])
        self.assertIn("notify.mobile_app_ondrej", findings[0]["solution"])

    def test_entity_availability_imports_stale_entities_from_summary_attributes(self):
        findings = ToolAdapterBus._entity_availability_findings([{
            "entity_id": "sensor.entity_availability_hads_group_summary",
            "state": "1",
            "attributes": {"stale_entities": ["sensor.old_temperature"]},
        }])
        self.assertEqual(1, len(findings))
        self.assertIn("sensor.old_temperature", findings[0]["title"])
        self.assertEqual("stale_entities", findings[0]["evidence"]["problem_kind"])

    def test_similar_mobile_notify_name_requires_identity_or_choice(self):
        occurred = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with hads4.db() as conn:
            hads4.ingest_event(conn, {
                "logger": "adapter.findings.automation_inspector", "source_ref": "ai:arrival", "integration": "Automation Inspector",
                "occurred_at": occurred, "level": "ERROR", "message": "unknown notify service",
                "source_name": "adapter_finding_automation_inspector",
            })
            case_id = int(conn.execute("SELECT id FROM cases").fetchone()["id"])
        before = {"alias": "Arrival", "action": [{"service": "notify.mobile_app_ondrej_old", "data": {"message": "Home"}}]}

        def supervisor(path, **kwargs):
            if path == "/core/api/states":
                return [{"entity_id": "automation.arrival", "state": "on", "attributes": {"id": "arrival"}}]
            if path == "/core/api/services":
                return [{"domain": "notify", "services": {"mobile_app_ondrej": {}}}]
            if path.endswith("/core/api/config/automation/config/arrival"):
                return before
            raise AssertionError(path)

        adapter_result = {"evidence": [{"payload": {"findings": [{
            "source_ref": "automation-inspector:arrival",
            "evidence": {"issue": {"automation_id": "arrival", "message": "automation.arrival uses notify.mobile_app_ondrej_old"}},
        }]}}]}
        with mock.patch.object(hads4, "supervisor_request", side_effect=supervisor), mock.patch.object(hads4, "ha_ws_read", return_value=[]):
            result = hads4.derive_verified_repair_actions(case_id, adapter_result)
        self.assertEqual("needs_information", result["status"])
        self.assertEqual([], result["repair_actions"])
        choice = next(d for d in result["decisions"] if d.get("status") == "needs_choice")
        self.assertEqual("notify.mobile_app_ondrej", choice["candidates"][0]["entity_id"])

    def test_batch_launch_control_remains_visible_without_approved_plan(self):
        html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<footer class="batchbar">', html)
        self.assertNotIn("classList.toggle('hidden',!approved&&!activeBatch)", html)

    def test_automation_repair_creates_backup_before_write_and_runs_core_check(self):
        calls = []
        before = {"alias": "Arrival", "action": [{"service": "notify.mobile_app_old"}]}
        after = {"alias": "Arrival", "action": [{"service": "notify.mobile_app_new"}]}
        live = dict(before)
        backup_name = ''

        def supervisor(path, method="GET", body=None, **kwargs):
            nonlocal live, backup_name
            calls.append((method, path, body))
            if path == "/backups/new/full":
                backup_name = body['name']
                return {"slug": "backup-before-change"}
            if path == '/backups/backup-before-change/info':
                return {'slug':'backup-before-change','name':backup_name,'type':'full','size':25,'homeassistant':'2026.8','homeassistant_exclude_database':False,'addons':[]}
            if path == "/core/api/config/automation/config/arrival" and method == "GET":
                return live
            if path == "/core/api/config/automation/config/arrival" and method == "POST":
                live = dict(body)
                return {"result": "ok"}
            if path == "/core/check":
                return {"result": "valid"}
            raise AssertionError((method, path))

        engine = RepairEngine(
            supervisor,
            lambda: None,
            self.test_root / "repair-private",
            lambda: {"first_officer_enabled": True, "repair_mode_open": True, "backup_before_repairs": True},
        )
        with mock.patch("repair_engine.os.chmod"), mock.patch.object(engine, "_write_private_json"):
            result = engine.execute(77, [{
                "type": "automation_update", "automation_id": "arrival", "before": before, "after": after,
                "expected_sha256": canonical_json_hash(before),
            }])
        self.assertTrue(result["ok"])
        backup_index = next(index for index, call in enumerate(calls) if call[1] == "/backups/new/full")
        write_index = next(index for index, call in enumerate(calls) if call[0] == "POST" and call[1].endswith("/arrival"))
        check_index = next(index for index, call in enumerate(calls) if call[1] == "/core/check")
        self.assertLess(backup_index, write_index)
        self.assertLess(write_index, check_index)
        self.assertEqual("backup-before-change", result["backup"]["slug"])

    def test_czech_decision_reason_is_not_sent_in_an_http_header(self):
        html = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("'X-HADS4-Reason':reason", html)
        self.assertIn("JSON.stringify(value)", html)
        self.assertNotIn("X-HADS4-Reason", html)

    def test_removed_digest_is_pruned_from_persisted_adapter_status(self):
        with hads4.db() as conn:
            conn.execute(
                """INSERT INTO tool_adapters(adapter_id,title,available,active,capabilities_json,discovery_json,last_ok_at,last_error,updated_at)
                   VALUES('homeassistant_digest','Home Assistant Digest',1,0,'[]','{}',NULL,'',?)""",
                (hads4.now_utc(),),
            )
        hads4.tool_bus().init_schema()
        with hads4.db() as conn:
            self.assertEqual(0, conn.execute("SELECT count(*) n FROM tool_adapters WHERE adapter_id='homeassistant_digest'").fetchone()["n"])

    def test_completed_p2_without_write_plan_enters_review_and_can_be_accepted(self):
        occurred = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with hads4.db() as conn:
            hads4.ingest_event(conn, {
                "logger": "custom_components.meross_lan.api", "source_ref": "meross-review", "integration": "meross_lan",
                "occurred_at": occurred, "level": "ERROR", "message": "MQTT is not ready and command cannot publish",
                "source_name": "core", "analysis": {"priority": "P2", "title": "Meross MQTT", "cause": "MQTT není připravené", "confidence": 85},
            })
        officer = hads4.first_officer()
        officer.rebuild_root_cases()
        with hads4.db() as conn:
            conn.execute("UPDATE root_cases SET priority='P2',confidence=85")

        class NativeOnlyBus:
            @staticmethod
            def collect(case, root_case_id):
                return {"used": ["native_ha"], "evidence": [], "native_fallback": True}

        result = officer.automatic_repair_planner(
            lambda actions: self.fail("preview must not run without actions"),
            lambda case_id, payload: self.fail("plan must not be created without actions"),
            lambda case_id, question, adapter: {"review_disposition": "review_ready", "summary": "Závěr k posouzení, bezpečný automatický zápis neexistuje.", "deterministic_planner": {"repair_actions": [], "decisions": [], "missing_evidence": []}},
            NativeOnlyBus(),
        )
        self.assertEqual("review_ready", result["results"][0]["status"])
        view = officer.command_center()
        root = next(item for item in view["root_cases"] if item["decision_state"] == "review_ready")
        accepted = hads4.first_officer_decide(root["id"], {"decision": "accept_analysis", "reason": "Souhlasím"})
        self.assertEqual("watching", accepted["decision_state"])
        self.assertEqual(0, officer.command_center()["approved_plans"])

    def test_repair_conclusion_watching_and_history_are_separate(self):
        _, _, repair_root_id = self._case_and_plan()
        occurred = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with hads4.db() as conn:
            hads4.ingest_event(conn, {
                "logger": "demo.conclusion", "source_ref": "demo", "integration": "demo conclusion",
                "occurred_at": occurred, "level": "ERROR", "message": "diagnostic conclusion",
                "source_name": "core", "analysis": {"priority": "P2", "title": "Závěr", "cause": "Ověřený závěr", "confidence": 90},
            })
        officer = hads4.first_officer()
        officer.rebuild_root_cases()
        with hads4.db() as conn:
            conclusion_id = int(conn.execute("SELECT id FROM root_cases WHERE id!=? ORDER BY id DESC", (repair_root_id,)).fetchone()["id"])
            conn.execute("UPDATE root_cases SET decision_state='review_ready',planner_state='review_ready' WHERE id=?", (conclusion_id,))
        view = officer.command_center()
        self.assertTrue(any(item["id"] == repair_root_id for item in view["repair_cases"]))
        self.assertTrue(any(item["id"] == conclusion_id for item in view["conclusion_cases"]))
        officer.decide(conclusion_id, "accept_analysis", "sledovat")
        restarted = hads4.first_officer().command_center()
        self.assertTrue(any(item["id"] == conclusion_id for item in restarted["watching_cases"]))
        self.assertEqual(0, restarted["approved_plans"])
        officer.decide(repair_root_id, "reject", "Návrh není správný")
        history = officer.command_center()["history_cases"]
        self.assertTrue(any(item["id"] == repair_root_id for item in history))

    def test_approval_populates_only_executable_approved_and_batch_checklist(self):
        _, _, root_id = self._case_and_plan()
        hads4.first_officer_decide(root_id, {"decision": "approve"})
        with mock.patch.object(hads4, "hads_health_breakdown", return_value={"score": 100, "components": {}}):
            view = hads4.first_officer_command_center()
        self.assertEqual(1, view["approved_plans"])
        self.assertEqual(1, view["batch_checklist"]["approved_plans"])
        self.assertTrue(view["batch_checklist"]["runnable"])
        self.assertEqual("locked", view["batch_checklist"]["write_gate"])

    def test_empty_plan_is_not_an_executable_repair(self):
        _, plan_id, root_id = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("UPDATE repair_plans SET actions_json='[]' WHERE id=?", (plan_id,))
        with self.assertRaises((ValueError, hads4.RepairError)):
            hads4.first_officer_decide(root_id, {"decision": "approve"})

    def test_conflicting_plans_are_blocked_before_rescue(self):
        first = {"id": 1, "actions": [{"type": "automation_update", "automation_id": "arrival", "before": {}, "after": {"alias": "A"}}]}
        second = {"id": 2, "actions": [{"type": "automation_update", "automation_id": "arrival", "before": {}, "after": {"alias": "B"}}]}
        result = hads4.first_officer().plan_batch([first, second])
        self.assertTrue(result["blocked"])
        self.assertEqual("object_update_conflict", result["conflicts"][0]["type"])

    def test_rescue_verification_failure_keeps_write_gate_locked(self):
        _, _, root_id = self._case_and_plan()
        hads4.first_officer_decide(root_id, {"decision": "approve"})
        rescue = self.test_root / "rescue.zip"
        rescue.write_bytes(b"rescue")
        with mock.patch.object(hads4.FirstOfficer, "prepare_rescue", return_value={"path": str(rescue), "sha256": "a" * 64}), \
             mock.patch.object(hads4, "upload_and_verify_rescue", return_value={"verified": False, "message": "remote existence not verified"}), \
             self.assertRaisesRegex(hads4.RepairError, "OneDrive hard gate"):
            hads4.execute_approved_batch_sync()
        self.assertEqual("locked", hads4.get_setting("repair_write_gate"))
        with hads4.db() as conn:
            self.assertEqual("blocked_remote_verify", conn.execute("SELECT status FROM repair_batches ORDER BY id DESC LIMIT 1").fetchone()["status"])

    def test_supervisor_502_retries_then_uses_last_valid_read(self):
        class Response:
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"data":{"state":"running"}}'

        error = lambda: urllib.error.HTTPError("http://supervisor/core/info", 502, "Bad Gateway", {}, io.BytesIO(b"temporary"))
        with mock.patch("hads4.urllib.request.urlopen", return_value=Response()):
            self.assertEqual("running", hads4.supervisor_request("/core/info")["state"])
        with mock.patch("hads4.urllib.request.urlopen", side_effect=[error(), error(), error(), error()]), mock.patch("hads4.time.sleep"):
            cached = hads4.supervisor_request("/core/info", allow_stale=True)
        self.assertEqual("running", cached["state"])
        self.assertEqual("temporarily_unavailable", hads4.runtime["supervisor_reads"]["/core/info"]["status"])
        self.assertTrue(hads4.runtime["supervisor_reads"]["/core/info"]["stale"])

    def test_log_source_overview_reports_lines_findings_and_temporary_failure(self):
        hads4.update_collector_source("core", True, required=True, line_count=120, findings_count=3)
        hads4.update_collector_source("core", False, required=True, error="HTTP 502")
        row = next(item for item in hads4.log_source_overview() if item["name"] == "core")
        self.assertEqual(120, row["line_count"])
        self.assertEqual(3, row["findings_count"])
        self.assertEqual("temporarily_unavailable", row["status"])

    def test_ui_names_conclusions_and_repairs_without_ambiguity(self):
        html = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Přijmout závěr a dále sledovat", html)
        self.assertIn("Nejde o opravu", html)
        self.assertIn("Připravené opravy", html)
        self.assertIn("Přijaté závěry a ověřování oprav", html)
        self.assertIn("Otestovat sběr protokolů", html)
        self.assertNotIn(">Schvaluji závěr<", html)


if __name__ == "__main__":
    unittest.main()
