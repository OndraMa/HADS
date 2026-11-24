import json
from pathlib import Path
import tempfile
import unittest
import time

from hads_next.haos_application import Application
from hads_next.observability import CoreReader, ReadFailure


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1794153600.0
        self.calls = []
        self.rows = [
            {"entity_id": "media_player.radio", "state": "playing", "last_updated": "2026-11-08T15:59:00+00:00", "attributes": {"private": "DO_NOT_EXPORT"}},
            {"entity_id": "media_player.radio", "state": "idle", "last_updated": "2026-11-08T15:59:59+00:00", "context": {"id": "state-1"}},
        ]
        def read(path):
            self.calls.append(path)
            if path == "/api/config":
                return {"version": "2026.11.0"}
            if path == "/api/states":
                return self.rows[-1:]
            if path.startswith("/api/history/period/"):
                return [self.rows]
            raise AssertionError(path)
        self.app = Application(Path(self.temp.name), CoreReader(read), clock=lambda: self.now)

    def tearDown(self):
        self.temp.cleanup()

    def test_read_only_refresh_is_cached_and_does_not_create_incidents(self):
        result = self.app.refresh()
        self.assertTrue(result["core"]["available"])
        self.app.refresh()
        self.assertEqual(self.calls, ["/api/config", "/api/states"])
        self.assertEqual(result["cases"], [])
        self.assertFalse(result["hermes_enabled"])
        self.assertFalse(result["live_repairs_enabled"])
        self.assertNotIn("DO_NOT_EXPORT", json.dumps(result))

    def test_automatic_source_check_populates_core_overview_after_read_contention(self):
        self.app._read_lock.acquire()
        try:
            self.assertTrue(self.app.request_source_check())
            time.sleep(.05)
            self.assertEqual(self.calls,[])
        finally:self.app._read_lock.release()
        for _ in range(300):
            state=self.app.snapshot()['source_job']['state']
            if state in {'finished','failed'}:break
            time.sleep(.02)
        self.assertEqual(state,'finished')
        snapshot=self.app.snapshot()
        self.assertTrue(snapshot['core']['available'])
        self.assertEqual(snapshot['core']['entity_count'],1)
        self.assertEqual(snapshot['core']['version'],'2026.11.0')

    def test_manual_radio_report_persists_real_history_without_fake_root_cause(self):
        self.app.refresh()
        case = self.app.report_incident("Rádio se právě samo vypnulo.", "media_player.radio", "owner-id")
        self.assertEqual(len(case["evidence"]), 2)
        conclusion = case["records"][-1]["content"]
        self.assertEqual(conclusion["category"], "insufficient_evidence")
        self.assertNotIn("DO_NOT_EXPORT", json.dumps(case))
        self.now += 1
        again = self.app.report_incident("Rádio se právě samo vypnulo.", "media_player.radio", "owner-id")
        self.assertEqual(case["incident"]["id"], again["incident"]["id"])
        self.assertEqual(len(again["evidence"]), 2)
        self.assertEqual(len(again["occurrences"]), 2)
        restarted = Application(Path(self.temp.name), None)
        self.assertEqual(restarted.snapshot()["cases"][0]["id"], case["incident"]["id"])

    def test_missing_core_preserves_user_incident_and_exposes_limit(self):
        app = Application(Path(self.temp.name), None)
        app.refresh()
        case = app.report_incident("Světlo nereaguje", "light.kitchen", "owner")
        self.assertEqual(case["evidence"], [])
        self.assertEqual(case["incident"]["status"], "open")
        self.assertFalse(app.snapshot()["core"]["available"])

    def test_invalid_entity_cannot_inject_a_proxy_or_service_call(self):
        for entity in ["../../services/light/turn_on", "light.x?x=y", "https://external.invalid"]:
            with self.subTest(entity=entity), self.assertRaises(ValueError):
                self.app.report_incident("Test problému", entity, "owner")
        self.assertEqual(self.calls, [])
