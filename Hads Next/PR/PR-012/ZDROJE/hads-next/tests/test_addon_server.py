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
        self.assertIn("Obecné zásahy jsou zakázané", page)

    def test_repair_approval_rechecks_role_instead_of_using_cached_admin(self):
        self.app.enroll_owner('owner-id')
        self.assertEqual(self.request('GET','/')[0],200)
        self.app.core_ws._auth_reader.transport=lambda _:[]
        data={'csrf':self.server.csrf,'incident_id':'unknown'}
        self.assertEqual(self.request('POST','/repair/prepare',urlencode(data))[0],403)

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

    def test_health_case_has_native_read_next_step_and_no_unrelated_lighting_repair(self):
        self.app.enroll_owner('owner-id')
        self.app.system._finding('health:marketplace','system_health_failure','Obecný starý symptom.',
            ['integration:marketplace'],{'domain':'marketplace','failed_fields':['github_web']})
        case=self.app.snapshot()['cases'][0];before=self.app.store.export(case['id'])
        status,page=self.request('GET','/case/'+case['id'])
        self.assertEqual(status,200);self.assertIn('kontrola přístupu k webu GitHubu',page)
        self.assertIn('Zopakovat nativní diagnostiku bez AI',page)
        self.assertNotIn('Ověřit a vybrat bezpečný světelný cíl',page)
        self.assertNotIn('Připravit přesnou opravu',page)
        self.assertEqual(before,self.app.store.export(case['id']))
        self.assertEqual(self.request('POST','/setup/check',urlencode({'csrf':'forged'}))[0],403)
        # Presentation fixture only: preserve the existing catalog even when
        # its supported target is a virtual input_boolean, not automation.*.
        with self.app.store._connect() as db:db.execute('UPDATE managed_repair_settings SET enabled=1 WHERE id=1')
        self.assertNotIn('Připravit přesnou opravu',self.request('GET','/case/'+case['id'])[1])
        owned=self.app.store.open_incident('manual_functional','Vlastní testovací reference nereaguje.',
            ['input_boolean.hads_next_test_target'],1)
        page=self.request('GET','/case/'+owned['id'])[1]
        self.assertIn('Připravit přesnou opravu vlastní testovací reference',page)
        self.assertNotIn('Ověřit a vybrat bezpečný světelný cíl',page)

    def test_public_research_consent_and_cancel_routes_require_owner_and_csrf(self):
        self.app.enroll_owner('owner-id')
        self.assertFalse(self.app.investigations.research.enabled())
        form={'enabled':'yes','csrf':self.server.csrf}
        self.assertEqual(self.request('POST','/setup/research',urlencode(form),owner='other')[0],403)
        self.assertEqual(self.request('POST','/setup/research',urlencode(dict(form,csrf='invented')))[0],403)
        self.assertFalse(self.app.investigations.research.enabled())
        self.assertEqual(self.request('POST','/setup/research',urlencode(form))[0],303)
        self.assertTrue(self.app.investigations.research.enabled())
        self.assertEqual(self.request('POST','/investigate/cancel',urlencode({'csrf':self.server.csrf,'job_id':'unknown'}))[0],409)

    def test_manual_preference_is_bound_to_draft_and_never_approves_a_write(self):
        self.app.enroll_owner('owner-id')
        case=self.app.store.open_incident('automation_reference','Nefunkční odkaz.',['automation.fixture'],1)
        service=self.app.investigations;identity=service.jobs.enqueue(case['id']);service.jobs.claim(identity)
        suggestion={'suggestion_id':'a'*64,'summary_cs':'Je potřeba ruční kontrola.','manual_steps_cs':['Ověř zamýšlený cíl.']}
        service.jobs.transition(identity,'hypothesis_ready','Offline route fixture.',conclusion={'summary_cs':'Pracovní návrh.','repair_suggestion':suggestion})
        data={'csrf':self.server.csrf,'incident_id':case['id'],'decision':'manual','suggestion_id':'b'*64}
        self.assertEqual(self.request('POST','/repair/preference',urlencode(data))[0],400)
        data['suggestion_id']=suggestion['suggestion_id']
        self.assertEqual(self.request('POST','/repair/preference',urlencode(data))[0],303)
        stored=self.app.store.case(case['id'])
        decision=next(r['content'] for r in stored['records'] if r['kind']=='repair_suggestion_decision')
        self.assertFalse(decision['approval_granted']);self.assertEqual(decision['functional_result'],'not_verified')
        self.assertEqual(stored['incident']['status'],'open')
        page=self.request('GET','/case/'+case['id'])[1]
        self.assertIn('Zvolil jsi ruční kontrolu',page);self.assertNotIn('Schválit opravu',page)


if __name__ == "__main__":
    unittest.main()
