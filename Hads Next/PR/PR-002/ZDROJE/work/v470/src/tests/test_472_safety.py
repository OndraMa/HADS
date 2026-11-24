import unittest
from unittest import mock
import hads4
import incident_workflow
from tool_adapters import ToolAdapterBus
import test_rc8_regressions as legacy


class SafetyContractTests(unittest.TestCase):
    def test_dhcp_start_is_not_error(self):
        events = hads4.parse_raw('2026-09-13 10:00:00 host NetworkManager[1]: <info> activation: beginning transaction (timeout in 45 seconds)', 'host')
        self.assertEqual([], events)

    def test_negative_and_ambiguous_rescue(self):
        for value in [
            {"exists": False, "filename": "rescue.zip"},
            {"error": "rescue.zip not found"},
            {"exists": True}, "rescue.zip.failed",
            {"exists": True, "filename": "rescue.zip", "error": "denied"},
            {"exists": True, "filename": "other.zip"},
        ]:
            self.assertFalse(hads4._response_confirms_remote_file(value, "rescue.zip"))

    def test_exact_object_identity(self):
        self.assertTrue(hads4._response_confirms_remote_file({"exists": True, "filename": "rescue.zip"}, "rescue.zip"))

    def test_repairs_not_all_entity_errors(self):
        for issue in ["drive_almost_full", "server_start_failed", "automatic_backup_failed", "future_unknown"]:
            found = ToolAdapterBus._repair_findings([{"domain": "homeassistant", "issue_id": issue}])[0]
            self.assertNotIn("nahraďte", found["solution"])
            self.assertNotIn("potvrzuje neplatný", found["cause"])
            self.assertNotEqual(99, found["confidence"])

    def test_explicit_uncapped_mode_does_not_access_db(self):
        self.assertEqual(8, incident_workflow.remaining_calls(None, None, {"ai_call_limits_enabled": False}, 1))


class PersistenceTests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown
    _case_and_plan = legacy.RC8RegressionTests._case_and_plan

    def test_core_outage_bounds_dashboard_requests(self):
        with mock.patch.object(hads4, "dashboard_snapshot", return_value={}), mock.patch.object(hads4, "dashboard_entity_payloads", return_value={f"sensor.test_{i}": {} for i in range(12)}), mock.patch.object(hads4, "supervisor_request", side_effect=OSError("HTTP 502 Bad Gateway")) as request, mock.patch.object(hads4.time, "sleep"):
            result = hads4.publish_ha_dashboard()
        self.assertFalse(result["ok"])
        self.assertEqual(3, request.call_count)
        self.assertEqual(12, result["deferred"])
        self.assertEqual(0, result["published"])

    def test_remote_verifier_requires_scope_and_hash(self):
        import hashlib
        archive = self.test_root / "rescue.zip"
        archive.write_bytes(b"test fixture")
        valid = {"exists": True, "filename": archive.name, "config_entry_id": "account",
                 "destination_folder": "HADS/Repairs", "size": archive.stat().st_size,
                 "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "verification_version": 1}
        for alteration, expected in [({}, True), ({"exists": False}, False),
                                     ({"config_entry_id": "other"}, False),
                                     ({"sha256": "wrong"}, False), ({"size": 1}, False),
                                     ({"destination_folder": "other"}, False),
                                     ({"verification_version": 0}, False)]:
            with mock.patch.object(hads4, "upload_onedrive_to", return_value={"ok": True}), mock.patch.object(hads4, "resolve_onedrive_config_entry", return_value={"entry_id": "account"}), mock.patch.object(hads4, "_onedrive_verifier_services", return_value=["onedrive.verify"]), mock.patch.object(hads4, "supervisor_request", return_value={**valid, **alteration}):
                result = hads4.upload_and_verify_rescue(str(archive), "HADS/Repairs")
            self.assertEqual(expected, result["verified"])

    def test_silence_without_telemetry_is_not_success(self):
        case, plan, root = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("UPDATE cases SET status='monitoring' WHERE id=?", (case,))
            conn.execute("UPDATE repair_plans SET status='monitoring' WHERE id=?", (plan,))
            conn.execute("INSERT INTO fix_attempts(case_id,applied_at,watch_until,description,baseline_count,outcome) VALUES(?,?,?,'test',0,'monitoring')",
                         (case, "2090-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00"))
        result = hads4.update_recurrence_and_fixes()
        self.assertEqual(0, result["fixes_verified"])
        with hads4.db() as conn:
            self.assertEqual("verification_blocked", conn.execute("SELECT outcome FROM fix_attempts").fetchone()[0])
            self.assertEqual("verification_blocked", conn.execute("SELECT status FROM repair_plans WHERE id=?", (plan,)).fetchone()[0])
            self.assertEqual("monitoring", conn.execute("SELECT status FROM cases WHERE id=?", (case,)).fetchone()[0])
