import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hads_next.observability import (
    CoreReader, CoreWSReader, NativeHTTP, NativeWebSocket,
    ReadFailure, SupervisorReader, redact,
)


class ReadContractTests(unittest.TestCase):
    def test_admin_identity_read_cannot_overwrite_diagnostic_error_status(self):
        def transport(command):
            if command['type']=='config/auth/list':return [{'id':'owner','is_owner':True}]
            raise ReadFailure('forbidden',403)
        reader=CoreWSReader(transport)
        self.assertIsNone(reader.traces('automation','fixture'))
        self.assertEqual(reader.status.last_response_status,403)
        self.assertTrue(reader.auth_users())
        self.assertEqual(reader.status.last_response_status,403)
        self.assertFalse(reader.status.read_succeeded)

    def test_native_contracts_and_redaction(self):
        calls = []
        def read(request):
            calls.append(request)
            return [{"context_id": "ctx-1", "service_data": {"code": "1234", "entity_id": "media_player.radio"}, "context_message": "1234"}]
        ws = CoreWSReader(read)
        result = ws.action_history("2026-11-08T12:00:00+00:00", "2026-11-08T12:01:00+00:00")
        self.assertEqual(calls[-1]["type"], "logbook/get_action_calls")
        self.assertNotIn("1234", json.dumps(result))
        self.assertEqual(result[0]["targets"], {"entity_id": ["media_player.radio"]})
        ws.traces("automation", "radio_button")
        self.assertEqual(calls[-1], {"type": "trace/list", "domain": "automation", "item_id": "radio_button"})
        self.assertIsNone(ws.status.installed)
        self.assertIsNone(ws.status.running)
        self.assertTrue(ws.status.read_succeeded)
        self.assertIsNone(ws.status.relevant)

    def test_failed_read_not_successful_diagnosis_or_uninstalled(self):
        def read(_):
            raise ReadFailure("http_error", 403)
        reader = SupervisorReader(read)
        self.assertIsNone(reader.apps())
        self.assertFalse(reader.status.authenticated)
        self.assertFalse(reader.status.read_succeeded)
        self.assertIsNone(reader.status.installed)
        # Continue by a supported, separately authenticated Core route.
        core = CoreReader(lambda path: {"entity_id": "media_player.radio", "state": "idle"})
        self.assertEqual(core.states("media_player.radio")["state"], "idle")

    def test_read_of_old_state_does_not_refresh_evidence_age(self):
        reader = CoreReader(lambda _: {"last_updated": "2026-11-08T12:00:00+00:00", "state": "idle"})
        reader.states("media_player.radio")
        observed = reader.status.last_evidence_at
        self.assertEqual(reader.status.snapshot(now=observed + 3600)["evidence_age_seconds"], 3600)
        reader.states("media_player.radio")
        self.assertEqual(reader.status.last_evidence_at, observed)
        self.assertGreater(reader.status.last_read_at, observed)

    def test_supervisor_envelope_and_no_write_surface(self):
        calls = []
        def read(path):
            calls.append(path)
            return {"result": "ok", "data": {"state": "started"}}
        reader = SupervisorReader(read)
        self.assertEqual(reader.app_info("core_mosquitto")["state"], "started")
        reader.app_stats("core_mosquitto")
        self.assertEqual(calls, ["/addons/core_mosquitto/info", "/addons/core_mosquitto/stats"])
        self.assertFalse(hasattr(reader, "write"))
        bad = SupervisorReader(lambda path: {"result": "error", "message": "Bearer secret"})
        self.assertIsNone(bad.apps())
        self.assertEqual(bad.status.last_error, "supervisor_read_rejected")
        with self.assertRaises(ValueError):
            reader.app_info("../restart")
        with self.assertRaises(ValueError):
            CoreWSReader(read).traces("config", "x")

    def test_real_http_transport_auth_json_and_redirect_isolation(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                received.append((self.path, self.headers.get("Authorization")))
                if self.path == "/api/config":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps({"version": "2026.11.0"}).encode())
                else:
                    self.send_response(302)
                    self.send_header("Location", "/stolen")
                    self.end_headers()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            http = NativeHTTP(f"http://127.0.0.1:{server.server_port}", "fixture-token", allow_local_http=True)
            reader = CoreReader(http)
            self.assertEqual(reader.config()["version"], "2026.11.0")
            self.assertIsNone(reader.states())
            self.assertEqual(reader.status.last_error, "redirect_refused")
            self.assertEqual(received, [("/api/config", "Bearer fixture-token"), ("/api/states", "Bearer fixture-token")])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_unsafe_origins_and_secret_exception(self):
        for origin in ["http://ha.local", "https://user:pass@ha.local", "https://ha.local/api", "https://ha.local?token=x"]:
            with self.assertRaises(ValueError):
                NativeHTTP(origin, "secret")
        with self.assertRaises(ValueError):
            NativeWebSocket("wss://ha.local/other", "secret")
        def failed(_):
            raise RuntimeError("Bearer SUPERSECRET")
        reader = CoreReader(failed)
        reader.config()
        self.assertNotIn("SUPERSECRET", json.dumps(reader.status.snapshot()))
        self.assertEqual(redact({"password": "x", "message": "Bearer abc"}),
                         {"password": "[skryto]", "message": "Bearer [skryto]"})


if __name__ == "__main__":
    unittest.main()
