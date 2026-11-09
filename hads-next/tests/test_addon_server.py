import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import urlencode
import unittest

from hads_next.addon_server import Server, SupervisorCoreTransport
from hads_next.haos_application import Application
from hads_next.observability import CoreWSReader


class IngressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Application(Path(self.temp.name))
        self.app.core_ws = CoreWSReader(lambda _: [{'id':'owner-id','is_active':True,'is_owner':True,'system_generated':False,'group_ids':[]}])
        self.server = Server(("127.0.0.1", 0), self.app, ingress_peer="127.0.0.1", owner_user_id="owner-id")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, body=None, owner="owner-id"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if owner:
            headers["X-Remote-User-Id"] = owner
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read().decode()
        connection.close()
        return result

    def test_health_has_no_household_data_and_private_routes_require_identity_and_peer(self):
        status, data = self.request("GET", "/health", owner=None)
        self.assertEqual(status, 200)
        self.assertNotIn("cases", data)
        for owner in (None, "someone-else"):
            self.assertEqual(self.request("GET", "/api/status", owner=owner)[0], 403)
        self.server.ingress_peer = "192.0.2.1"
        self.assertEqual(self.request("GET", "/api/status")[0], 403)

    def test_first_run_shows_only_identity_until_owner_is_explicitly_configured(self):
        self.server.owner_user_id = ""
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Vítej v HADS", page)
        self.assertNotIn("Načtených entit", page)
        self.assertEqual(self.request("GET", "/api/status")[0], 403)

    def test_csrf_and_unknown_write_routes_fail_closed(self):
        data = {"entity_id": "light.kitchen", "symptom": "Nefunguje světlo", "csrf": "forged"}
        self.assertEqual(self.request("POST", "/incident", urlencode(data))[0], 403)
        self.assertEqual(self.app.snapshot()["cases"], [])
        data["csrf"] = self.server.csrf
        for path in ("/repair", "/execute", "/api/services/light/turn_on"):
            self.assertEqual(self.request("POST", path, urlencode(data))[0], 404)
        self.assertEqual(self.app.snapshot()["cases"], [])

    def test_valid_manual_report_and_escaped_html(self):
        data = {"entity_id": "light.kitchen", "symptom": '<script>alert("x")</script>', "csrf": self.server.csrf}
        self.assertEqual(self.request("POST", "/incident", urlencode(data))[0], 303)
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Hermes vyžaduje izolovaný runtime", page)
        self.assertIn("Živé opravy jsou vypnuté", page)

    def test_transport_is_a_fixed_read_catalog(self):
        transport = SupervisorCoreTransport("NOT_A_REAL_TOKEN")
        requests = []
        transport._http = lambda path: requests.append(path)
        transport("/api/config")
        transport("/api/states")
        self.assertEqual(requests, ["/core/api/config", "/core/api/states"])
        for path in ("/api/services", "https://external.invalid", "/addons", "/api/config/core/check_config"):
            with self.assertRaises(ValueError):
                transport(path)


if __name__ == "__main__":
    unittest.main()
