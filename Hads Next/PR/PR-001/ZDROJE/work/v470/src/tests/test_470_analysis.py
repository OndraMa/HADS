import copy
import json
import unittest
from unittest import mock

import analysis_contract as contract
import hads4
import incident_workflow
import test_rc8_regressions as legacy
from tool_adapters import ToolAdapterBus


def change(**kwargs):
    return {"owner": "automation.lights", "path": "/actions/0/action", "old_json": '"notify.old_phone"',
            "new_json": '"notify.new_phone"', "reason": "Explicit owner and replacement", "verification": "Validate configuration and controlled notification", **kwargs}


class PureContractTests(unittest.TestCase):
    def test_watchman_uses_installed_service_schema(self):
        for fields, expected in [({"force_parsing": {}, "parse_config": {}}, "force_parsing"), ({"parse_config": {}}, "parse_config")]:
            self.assertEqual({"create_file": False, expected: True}, ToolAdapterBus._watchman_request_body([{"domain": "watchman", "services": {"report": {"fields": fields}}}]))
        with self.assertRaises(ValueError):
            ToolAdapterBus._watchman_request_body([])

    def test_real_user_failures_get_specific_explanation(self):
        for message, fragment in [
            ("wrong # of entries in index ix_statistics_short_term_statistic_id_start_ts", "indexu"),
            ("Orphaned long-term statistics found", "statistiky"),
            ("Inspection refresh failed; retaining last-known-good data", "obnovit"),
            ("Stream error /api/first-officer Cannot write to closing transport", "spojení"),
            ("Can't find backup folder addons/local", "složka"),
        ]:
            self.assertIn(fragment, hads4.rule_analysis("test", message, "ERROR", "system")["title"])

    def test_exact_patch_preserves_other_fields_and_input(self):
        before = {"id": "123", "actions": [{"action": "notify.old_phone", "data": {"message": "Hello"}}]}
        original = copy.deepcopy(before)
        result = contract.apply_scalar_changes(before, [change()])
        self.assertEqual(original, before)
        self.assertEqual("notify.new_phone", result["actions"][0]["action"])
        self.assertEqual({"message": "Hello"}, result["actions"][0]["data"])

    def test_fail_closed_pointers_types_and_blocks(self):
        before = {"actions": [{"action": "notify.old_phone", "enabled": True}], "id": "123"}
        for patch in [change(path="/id"), change(path="/actions/-1/action"), change(path="/actions/9/action"),
                      change(old_json='"different"'), change(new_json='{}'), change(new_json='null'),
                      change(new_json='NaN'), change(path="/actions/0/enabled", old_json='1', new_json='false')]:
            with self.subTest(patch=patch), self.assertRaises(contract.ProposalError):
                contract.apply_scalar_changes(before, [patch])
        with self.assertRaises(contract.ProposalError):
            contract.apply_scalar_changes(before, [change(), change()])

    def test_each_any_is_path_specific_not_global(self):
        before = {"triggers": [{"options": {"behavior": "any"}}], "conditions": [{"options": {"behavior": "any"}}]}
        after = contract.apply_scalar_changes(before, [change(path="/triggers/0/options/behavior", old_json='"any"', new_json='"each"')])
        self.assertEqual("each", after["triggers"][0]["options"]["behavior"])
        self.assertEqual("any", after["conditions"][0]["options"]["behavior"])

    def test_prose_is_not_executable(self):
        result = contract.plan_readiness({"proposed_actions": [{"description": "Repair database"}]}, [], ["No supported plan"])
        self.assertEqual(0, result["executable_actions"])
        self.assertFalse(result["execution_started"])

    def test_inspector_missing_dependency_is_not_lost(self):
        value = {"schema_version": 2, "automations": {"automation.lights": {"enabled": True, "loaded": True,
            "entities": [{"id": "notify.old_phone", "kind": "service", "status": "missing", "sources": ["actions[0].action"]}]}}}
        findings = ToolAdapterBus._automation_inspector_findings(value)
        self.assertEqual(1, len(findings))
        self.assertEqual("P2", findings[0]["priority"])
        self.assertEqual("notify.old_phone", findings[0]["evidence"]["payload"]["current_value"])

    def test_restored_inspector_owner_context_retained(self):
        value = {"automations": {"automation.radar": {"loaded": False, "restored": True, "configuration_available": False, "configuration_source": "attributes"}}}
        finding = ToolAdapterBus._automation_inspector_findings(value)[0]
        self.assertTrue(finding["evidence"]["restored"])
        self.assertFalse(finding["evidence"]["configuration_available"])

    def test_watchman_scope_and_condition_are_investigation_not_proven_fault(self):
        for row in [dict(id="assist_satellite.start", file="esphome/archive/voice.yaml", state="missing"),
                    dict(id="light.is_on", file="automations.yaml", context="condition: light.is_on", state="missing")]:
            value = ToolAdapterBus._watchman_findings([{"structured": {"missing_entities": [row]}}])
            self.assertEqual("P4", value[0]["priority"])
        # The same token in a real entity role must remain visible.
        value = ToolAdapterBus._watchman_findings([{"structured": {"missing_entities": [dict(id="light.is_on", file="automations.yaml", context="entity_id", state="missing")]}}])
        self.assertEqual("P3", value[0]["priority"])

    def test_ea_recovered_and_nonessential_are_not_active_failures(self):
        for suffix in ("recently_offline", "offline_entities_non_essential", "recently_recovered"):
            self.assertEqual([], ToolAdapterBus._entity_availability_findings([{"entity_id": "sensor.entity_availability_room_" + suffix, "state": "Lamp", "attributes": {"entities": ["light.lamp"]}}]))
        self.assertEqual([], ToolAdapterBus._entity_availability_findings([{"entity_id": "binary_sensor.entity_availability_room_any_offline", "state": "off", "attributes": {"offline_entities": ["light.lamp"]}}]))

    def test_hadocs_root_not_recursively_ingested(self):
        value = {"root_causes": [{"id": "network-1", "title": "Device offline", "status": "degraded", "recommendations": [{"title": "Check router"}], "issues": [{"id": "child", "title": "Entity missing"}]}]}
        result = ToolAdapterBus._generic_json_findings("hadocs", value)
        self.assertEqual(1, len(result))
        self.assertIn("issues", result[0]["evidence"]["payload"])
        value["root_causes"][0]["title"] = "Device still offline"
        self.assertEqual(result[0]["external_id"], ToolAdapterBus._generic_json_findings("hadocs", value)[0]["external_id"])

    def test_hamster_meta_write_never_enters_read_pipeline(self):
        for path in ("hass/fire_event", "hass/automation/trigger", "hass/auth/list", "supervisor/backups/new/full", "hass/repairs/ignore_issue"):
            self.assertFalse(ToolAdapterBus._safe_hamster_read_path(path), path)
        self.assertTrue(ToolAdapterBus._safe_hamster_read_path("hass/repairs/list_issues"))
        self.assertIn("hass/config/entity_registry/list", ToolAdapterBus._mcp_paths("Read hass/config/entity_registry/list"))


class IntegrationContractTests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown

    def test_model_last_budget_slot_is_synthesis_not_unfinished_tools(self):
        case_id, _, _ = legacy.RC8RegressionTests._case_and_plan(self)
        cfg = {"openai_enabled": True, "openai_api_key": "test-only", "ai_case_daily_call_limit": 1, "ai_daily_call_limit": 20, "ai_tool_max_rounds": 8, "openai_web_search_enabled": False}
        analysis = {"summary": "Need more evidence", "functional_impact": "Unknown", "decision_kind": "investigate", "hypotheses": [], "missing_evidence": ["trace"], "next_test": "Read trace", "proposed_actions": [], "configuration_changes": []}
        response = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(analysis)}]}]}
        with mock.patch.object(hads4, "options", return_value=cfg), mock.patch.object(hads4, "_openai_post", return_value=response) as post:
            result = hads4.research_case(case_id, {})
        self.assertEqual("Need more evidence", result["analysis"]["summary"])
        self.assertEqual("none", post.call_args.args[1]["tool_choice"])
        self.assertIn("reasoning.encrypted_content", post.call_args.args[1]["include"])
        self.assertEqual(0, incident_workflow.remaining_calls(hads4.db, hads4.now_utc, cfg, case_id))

    def test_compile_does_not_write_and_binds_owner(self):
        live = {"owner": "automation.lights", "domain": "automation", "object_id": "123", "configuration": {"actions": [{"action": "notify.old_phone"}]}}
        with mock.patch.object(hads4, "read_automation_configuration", return_value=live), mock.patch.object(hads4, "repair_engine") as engine:
            result = hads4.compile_analysis_changes({"configuration_changes": [change()]}, {"automation.lights"})
            self.assertEqual(1, len(result["repair_actions"]))
            engine.return_value.execute.assert_not_called()
            engine.return_value.preview.assert_called_once()
            result = hads4.compile_analysis_changes({"configuration_changes": [change(owner="automation.other")]}, {"automation.lights"})
            self.assertEqual([], result["repair_actions"])
            self.assertTrue(result["blockers"])

    def test_restored_placeholder_cannot_compile(self):
        with mock.patch.object(hads4, "supervisor_request", return_value={"entity_id": "automation.lights", "attributes": {"id": "123", "restored": True}}):
            with self.assertRaises(hads4.RepairError):
                hads4.read_automation_configuration("automation.lights")

    def test_structured_analysis_survives_readable_response(self):
        analysis = {"summary": "Actual cause", "proposed_actions": [{"description": "Repair reference"}], "configuration_changes": []}
        with mock.patch.object(hads4, "case_detail", return_value={}), mock.patch.object(hads4, "derive_verified_repair_actions", return_value={}), mock.patch.object(hads4, "options", return_value={"ai_background_research": True}), mock.patch.object(hads4, "research_case", return_value={"response_text": "Readable text, not JSON", "analysis": analysis}):
            result = hads4.planner_research(1, "explain", {})
        self.assertEqual(analysis, result["analysis"])
        self.assertEqual(0, result["plan_readiness"]["executable_actions"])
        self.assertTrue(result["plan_readiness"]["blockers"])
