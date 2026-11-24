import unittest
from unittest import mock
import hads4
from tool_adapters import ToolAdapterBus


class Audit462Tests(unittest.TestCase):
    def test_zigbee_frame_is_not_a_camera(self):
        analysis = hads4.rule_analysis("zigpy_znp.api", "Received an exception while passing frame to api", "ERROR", "integration")
        self.assertIn("Zigbee", analysis["title"])
        self.assertNotIn("Video/kamera", analysis["title"])

    def test_known_failures_get_specific_explanations(self):
        for logger, message, title in (
            ("kernel", "NETDEV WATCHDOG transmit queue timed out", "síťové"),
            ("onedrive", "quotaLimitReached", "kvótě"),
            ("recorder", "FOREIGN KEY constraint failed statistics", "statistik"),
            ("meross_lan", "HTTP JSONDecodeError", "JSON"),
        ):
            self.assertIn(title, hads4.rule_analysis(logger, message, "ERROR", "system")["title"])

    def test_kernel_timeouts_are_not_discarded(self):
        for message in (
            "bcmgenet fd580000.ethernet end0: NETDEV WATCHDOG: CPU: 3: transmit queue 0 timed out 5300 ms",
            "nvme0: I/O timeout",
            "Out of memory: Killed process 123",
        ):
            with self.subTest(message=message):
                events = hads4.parse_raw("2026-09-08 02:52:38 homeassistant kernel: " + message, "host")
                self.assertEqual(1, len(events))
                self.assertEqual("ERROR", events[0]["level"])
                self.assertEqual("2026-09-08 02:52:38", events[0]["occurred_at"])

    def test_journal_info_and_explicit_info_are_not_errors(self):
        for message in ("Started service successfully", 'level=info msg="configured timeout 30"'):
            self.assertEqual([], hads4.parse_raw("2026-09-08 02:52:38 homeassistant service: " + message, "host"))

    def test_closed_peer_is_not_written_twice(self):
        for error in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            handler = object.__new__(hads4.Handler)
            handler._send_bytes_connected = mock.Mock(side_effect=error())
            handler.send_json(200, {"ok": True})
            handler.send_json(500, {"error": "must not retry"})
            self.assertTrue(handler.close_connection)
            handler._send_bytes_connected.assert_called_once()

    def test_unrelated_response_failure_is_not_hidden(self):
        handler = object.__new__(hads4.Handler)
        handler._send_bytes_connected = mock.Mock(side_effect=ValueError("invalid response"))
        with self.assertRaises(ValueError):
            handler.send_json(200, {})

    def test_watchman_files_are_not_entities_and_line_movement_is_stable(self):
        first = ToolAdapterBus._watchman_findings([{"path": "watchman_report.txt", "content": "sensor.missing | automations.yaml | scripts.yaml"}])
        second = ToolAdapterBus._watchman_findings([{"path": "watchman_report.txt", "content": "\n\n sensor.missing | automations.yaml"}])
        self.assertEqual(1, len(first))
        self.assertEqual(first[0]["external_id"], second[0]["external_id"])
        self.assertEqual(first[0]["source_ref"], second[0]["source_ref"])

    def test_watchman_repeated_reference_is_single_fallback_finding(self):
        result = ToolAdapterBus._watchman_findings([{"path": "report.txt", "content": "sensor.missing\nsensor.missing"}])
        self.assertEqual(1, len(result))
