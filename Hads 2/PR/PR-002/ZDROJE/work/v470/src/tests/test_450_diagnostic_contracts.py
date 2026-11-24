import datetime as dt
import unittest
from unittest import mock

import hads4
import test_rc8_regressions as legacy
from tool_adapters import ToolAdapterBus


class ProviderContractTests(unittest.TestCase):
    def test_mcp_notification_has_no_jsonrpc_id(self):
        bus = ToolAdapterBus.__new__(ToolAdapterBus)
        bus.options = lambda: {}
        bus.now = lambda: "2026-09-03T10:00:00+00:00"
        bus._mcp_sessions = {}
        captured = {}

        def transport(url, **kwargs):
            captured.update(kwargs["payload"])
            return {}, {}

        bus._http_json = transport
        bus._mcp_rpc("ha_mcp", "http://example.invalid/mcp", "notifications/initialized", {}, notification=True)
        self.assertNotIn("id", captured)

    def test_hamster_discovers_schema_and_dispatches_only_safe_read(self):
        bus = ToolAdapterBus.__new__(ToolAdapterBus)
        bus.options = lambda: {}
        bus._auto_mcp_urls = lambda cfg: {"hamster_mcp": "http://example.invalid/mcp"}
        tools = [
            {"name": "search", "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"name": "schema", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "explain", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            {"name": "call", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "arguments": {"type": "object"}}, "required": ["path"]}},
        ]
        bus._mcp_probe = lambda adapter, url: {"catalog": {"tools": tools}, "tool_count": 4}
        calls = []

        def rpc(adapter, url, method, params, **kwargs):
            calls.append((method, params))
            name = params.get("name")
            return {"matches": [{"path": "hass/get_states"}]} if name == "search" else {"ok": True}

        bus._mcp_rpc = rpc
        result = bus._mcp_case_evidence("hamster_mcp", "find the current entity states")
        called_tools = [params.get("name") for _, params in calls]
        self.assertIn("schema", called_tools)
        self.assertIn("explain", called_tools)
        self.assertIn("call", called_tools)
        self.assertTrue(result["outputs"])
        self.assertFalse(bus._safe_hamster_read_path("hass/restart"))

    def test_watchman_structured_report_retains_owner_without_txt_guessing(self):
        payload = {"service_response": {"last_parse_date": "2026-09-03T10:00:00+00:00", "missing_entities": [
            {"id": "sensor.old_phone", "state": "missing", "file": "automations.yaml", "line": 42, "context": "entity_id"}
        ], "missing_actions": []}}
        detail = ToolAdapterBus._watchman_service_payload(payload)
        rows = ToolAdapterBus._watchman_findings([{"structured": detail, "path": "service_response"}], set(), set())
        self.assertEqual(1, len(rows))
        self.assertEqual("sensor.old_phone", rows[0]["evidence"]["identifier"])
        self.assertEqual("automations.yaml", rows[0]["evidence"]["owner"])
        self.assertNotIn("automations.yaml", rows[0]["title"])

    def test_entity_availability_contract_and_cross_group_deduplication(self):
        states = [
            {"entity_id": "sensor.entity_availability_phone_offline_entities", "state": "Phone", "attributes": {"entities": ["sensor.phone_battery"], "count": 1}},
            {"entity_id": "sensor.entity_availability_second_group_summary", "state": "1", "attributes": {"offline_entities": ["sensor.phone_battery"]}},
        ]
        rows = ToolAdapterBus._entity_availability_findings(states)
        self.assertEqual(1, len(rows))
        self.assertEqual("sensor.phone_battery", rows[0]["evidence"]["affected_entity"])
        self.assertEqual(2, len(rows[0]["evidence"]["observations"]))

    def test_haghs_registry_discovery_survives_entity_rename(self):
        state = {"entity_id": "sensor.health_renamed", "state": "65", "attributes": {"rec_disk_low": True, "recommendations": "Low disk"}}
        registry = [{"entity_id": "sensor.health_renamed", "platform": "haghs", "unique_id": "entry_score"}]
        rows = ToolAdapterBus._haghs_findings([state], registry)
        self.assertEqual(1, len(rows))
        self.assertIn("rec_disk_low", rows[0]["message"])

    def test_haghs_emits_one_case_per_active_recommendation(self):
        state = {"entity_id": "sensor.health", "state": "55", "attributes": {"rec_cpu": True, "rec_memory": True}}
        registry = [{"entity_id": "sensor.health", "platform": "haghs"}]
        rows = ToolAdapterBus._haghs_findings([state], registry)
        self.assertEqual({"rec_cpu", "rec_memory"}, {row["evidence"]["recommendation_flag"] for row in rows})

    def test_spook_orphaned_statistics_is_not_described_as_database_corruption(self):
        issue = {"domain": "spook", "issue_id": "orphaned_statistics_sensor.old", "translation_key": "orphaned_statistics", "severity": "warning", "translation_placeholders": {"entity_id": "sensor.old"}}
        row = ToolAdapterBus._repair_findings([issue])[0]
        self.assertIn("Osiřelé", row["title"])
        self.assertIn("Neznamená to samo o sobě poškozenou databázi", row["cause"])

    def test_inspector_preserves_owner_and_provider_replacement(self):
        value = {"schema_version": 2, "generated_at": "2026-09-03T10:00:00+00:00", "automations": {"automation.lights_off": {
            "entity_id": "automation.lights_off", "loaded": True, "status": "enabled", "trace": None,
            "compatibility_issues": [{"code": "deprecated_target_behavior", "severity": "warning", "path": "$.actions[0].options.behavior", "message": "Deprecated", "current": "any", "replacement": "each"}],
        }}, "scripts": {}}
        rows = ToolAdapterBus._automation_inspector_findings(value)
        self.assertEqual(1, len(rows))
        payload = rows[0]["evidence"]["payload"]
        self.assertEqual("automation.lights_off", payload["owner"])
        self.assertEqual("any", payload["current_value"])
        self.assertEqual("each", payload["recommended_value"])

    def test_inspector_not_loaded_is_functional_finding(self):
        value = {"schema_version": 2, "automations": {"lights_off": {"loaded": False, "status": "not_loaded", "compatibility_issues": [], "trace": None}}, "scripts": {}}
        rows = ToolAdapterBus._automation_inspector_findings(value)
        self.assertEqual(1, len(rows))
        self.assertEqual("P2", rows[0]["priority"])


class HADS450WorkflowTests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown

    def test_functional_rules_demote_transport_noise_and_explain_audio(self):
        subscriber = hads4.rule_analysis("client.events", "Connection error occurred while subscribing to events Traceback aiohttp", "ERROR", "addon")
        audio = hads4.rule_analysis("supervisor.audio", "Can't update PulseAudio data: Failed to connect to pulseaudio server", "ERROR", "system")
        automation = hads4.rule_analysis("homeassistant.components.automation", "Error while executing automation automation.lights_off", "ERROR", "home_assistant")
        self.assertEqual("P4", subscriber["priority"])
        self.assertEqual("P4", audio["priority"])
        self.assertIn("systémové audio", audio["cause"])
        self.assertEqual("P2", automation["priority"])
        self.assertIn("trace", automation["solution"].lower())

    def test_host_logs_do_not_use_nonexistent_latest_route(self):
        with mock.patch.object(hads4, "supervisor_request", return_value="host log") as request:
            self.assertEqual("host log", hads4.fetch_latest_log("/host/logs", 1000))
        self.assertTrue(request.call_args.args[0].startswith("/host/logs?lines="))
        self.assertNotIn("/latest", request.call_args.args[0])

    def test_log_pass_reports_partial_instead_of_false_success(self):
        def sources(limit, include_addons):
            hads4.update_collector_source("core", True, required=True, line_count=1)
            yield "core", "2026-09-03 10:00:00 ERROR test"
            hads4.update_collector_source("audio", False, required=False, error="unavailable")

        with mock.patch.object(hads4, "iter_log_sources", side_effect=sources), mock.patch.object(hads4, "import_text", return_value={"parsed_events": 1, "new_occurrences": 1, "system_events": 0, "unchanged": 0}):
            outcome = hads4.run_log_pass("test", False)
        self.assertFalse(outcome["ok"])
        self.assertEqual("partial", outcome["collection_state"])
        self.assertEqual("audio", outcome["failed_sources"][0]["name"])

    def test_inspector_replacement_becomes_exact_preview_not_direct_write(self):
        occurred = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with hads4.db() as conn:
            hads4.ingest_event(conn, {"logger": "adapter.findings.automation_inspector", "source_ref": "inspector:lights", "integration": "Automation Inspector", "occurred_at": occurred, "level": "ERROR", "message": "deprecated target behavior", "source_name": "adapter_finding_automation_inspector"})
            case_id = int(conn.execute("SELECT id FROM cases").fetchone()["id"])
        before = {"alias": "Lights", "actions": [{"target": {"entity_id": "light.all"}, "options": {"behavior": "any"}}]}
        provider = {"owner": "automation.lights", "automation_id": "automation.lights", "path": "$.actions[0].options.behavior", "current": "any", "replacement": "each", "current_value": "any", "recommended_value": "each"}
        adapter_result = {"evidence": [{"payload": {"findings": [{"source_ref": "automation_inspector:automation.lights:deprecated", "evidence": {"provider": "Automation Inspector", "payload": provider}}]}}]}

        def supervisor(path, **kwargs):
            if path == "/core/api/states":
                return [{"entity_id": "automation.lights", "state": "on", "attributes": {"id": "lights"}}]
            if path == "/core/api/services":
                return []
            if path.endswith("/core/api/config/automation/config/lights"):
                return before
            raise AssertionError(path)

        with mock.patch.object(hads4, "supervisor_request", side_effect=supervisor), mock.patch.object(hads4, "ha_ws_read", return_value=[]):
            result = hads4.derive_verified_repair_actions(case_id, adapter_result)
        self.assertEqual("executable", result["status"])
        action = result["repair_actions"][0]
        self.assertEqual("any", action["before"]["actions"][0]["options"]["behavior"])
        self.assertEqual("each", action["after"]["actions"][0]["options"]["behavior"])

    def test_batch_outcome_is_written_to_case_and_notified_idempotently(self):
        case_id, plan_id, _ = legacy.RC8RegressionTests._case_and_plan(self)
        batch = {"id": 12, "status": "monitoring", "plan_ids": [plan_id], "results": [{"plan_id": plan_id, "status": "monitoring"}], "rescue_destination": "HADS/Repairs", "rescue_verified_at": hads4.now_utc(), "after": {"comparison": {"resolved": [], "new": [], "persistent": ["case"]}}}
        with mock.patch.object(hads4, "supervisor_request", return_value={}) as request:
            hads4.publish_repair_batch_outcome(batch)
            hads4.publish_repair_batch_outcome(batch)
        with hads4.db() as conn:
            messages = conn.execute("SELECT body FROM messages WHERE case_id=? AND author='HADS výsledek opravy'", (case_id,)).fetchall()
        self.assertEqual(1, len(messages))
        message = messages[0]["body"]
        self.assertIn("B-0012", message)
        self.assertIn("není konečné potvrzení", message)
        body = request.call_args.kwargs["body"]
        self.assertEqual("hads4_repair_batch_12", body["notification_id"])

    def test_automatic_watching_is_not_presented_as_captain_acceptance(self):
        occurred = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with hads4.db() as conn:
            hads4.ingest_event(conn, {
                "logger": "demo.stale", "source_ref": "stale", "integration": "demo",
                "occurred_at": occurred, "level": "WARNING", "message": "stale observation",
                "source_name": "core",
            })
        officer = hads4.first_officer()
        officer.rebuild_root_cases()
        with hads4.db() as conn:
            root_id = int(conn.execute("SELECT id FROM root_cases").fetchone()["id"])
            conn.execute("UPDATE root_cases SET decision_state='watching' WHERE id=?", (root_id,))
        view = officer.command_center()
        self.assertTrue(any(item["id"] == root_id for item in view["automatic_monitoring_cases"]))
        self.assertFalse(any(item["id"] == root_id for item in view["watching_cases"]))
        self.assertEqual("automatic", officer.root_case(root_id)["state_origin"])


if __name__ == "__main__":
    unittest.main()
