import concurrent.futures
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from hads_next.evidence import IncidentStore


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "incidents.sqlite"
        self.store = IncidentStore(self.path)
        self.incident = self.store.open_incident("radio", "Rádio se samo vypnulo.", ["media_player.kitchen_radio"], 100,
                                                 correlation_key="radio:kitchen", occurrence_id="occ-1")
        self.case_id = self.incident["id"]
        self.event = {"source":"ha/core","kind":"player_state","observed_at":100,
                      "event_id":"state-1","payload":{"entity_id":"media_player.kitchen_radio","from":"playing","to":"idle"}}

    def tearDown(self):
        self.temp.cleanup()

    def test_reload_of_same_event_is_not_new_evidence_or_occurrence(self):
        self.assertTrue(self.store.add_evidence(self.case_id,self.event))
        self.assertFalse(self.store.add_evidence(self.case_id,dict(self.event,read_at=200)))
        self.store.open_incident("radio","Rádio se samo vypnulo.",["media_player.kitchen_radio"],100,correlation_key="radio:kitchen",occurrence_id="occ-1")
        case = self.store.case(self.case_id)
        self.assertEqual(len(case["evidence"]),1)
        self.assertEqual(len(case["occurrences"]),1)

    def test_content_identity_without_upstream_id_ignores_collection_time(self):
        event = {k:v for k,v in self.event.items() if k != "event_id"}
        self.assertTrue(self.store.add_evidence(self.case_id,event))
        self.assertFalse(self.store.add_evidence(self.case_id,dict(event,read_at=999)))

    def test_conflicting_source_event_is_not_silently_overwritten(self):
        self.store.add_evidence(self.case_id,self.event)
        altered = dict(self.event,payload={"state":"playing"})
        with self.assertRaises(ValueError):
            self.store.add_evidence(self.case_id,altered)
        self.assertEqual(self.store.case(self.case_id)["evidence"][0]["payload"]["to"],"idle")

    def test_crash_recovery_and_ai_unavailable_preserve_incident(self):
        self.store.add_evidence(self.case_id,self.event)
        claim = self.store.begin_analysis(self.case_id)
        restarted = IncidentStore(self.path)
        self.assertIsNone(restarted.begin_analysis(self.case_id))
        restarted.finish_analysis(self.case_id,claim,{"summary":"AI je nedostupná; lokální diagnostika pokračuje."},failed=True)
        self.assertEqual(len(restarted.case(self.case_id)["evidence"]),1)
        self.assertIsNone(restarted.begin_analysis(self.case_id))
        restarted.add_evidence(self.case_id,dict(self.event,event_id="state-2",observed_at=101))
        self.assertIsNotNone(restarted.begin_analysis(self.case_id))

    def test_concurrent_workers_claim_evidence_once(self):
        self.store.add_evidence(self.case_id,self.event)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as workers:
            claims = list(workers.map(lambda _:IncidentStore(self.path).begin_analysis(self.case_id),range(4)))
        self.assertEqual(sum(c is not None for c in claims),1)

    def test_recurrence_reopens_same_case_but_old_log_does_not(self):
        self.store.archive(self.case_id,at=110)
        old = self.store.open_incident("radio","Rádio se samo vypnulo.",[],100,correlation_key="radio:kitchen",occurrence_id="occ-1")
        self.assertEqual(old["status"],"archived")
        new = self.store.open_incident("radio","Rádio se samo vypnulo.",[],120,correlation_key="radio:kitchen",occurrence_id="occ-2")
        self.assertEqual(new["id"],self.case_id)
        self.assertEqual(new["status"],"open")
        self.assertEqual(len(self.store.case(self.case_id)["occurrences"]),2)

    def test_archive_retention_is_bounded_and_preserves_active_cases(self):
        self.store.add_evidence(self.case_id,self.event)
        second = self.store.open_incident("zigbee","Ovladač nereaguje.",["zha"],100)
        self.store.archive(self.case_id,at=120)
        exported = json.loads(self.store.export(self.case_id))
        self.assertEqual(exported["schema_version"],1)
        self.assertEqual(self.store.prune(archived_before=121,limit=1),1)
        self.assertEqual(self.store.case(second["id"])["incident"]["status"],"open")
        with self.assertRaises(KeyError):
            self.store.case(self.case_id)

    def test_schema_version_is_fail_closed(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE evidence_schema SET version=999")
        with self.assertRaises(ValueError):
            IncidentStore(self.path)

    def test_secrets_are_redacted_before_database_export_or_analysis(self):
        event = dict(self.event,payload={"password":"do-not-store","message":"Authorization: Bearer secret-value"})
        self.store.add_evidence(self.case_id,event)
        fingerprint = self.store.begin_analysis(self.case_id)
        self.store.finish_analysis(self.case_id,fingerprint,{"api_key":"do-not-store","summary":"Bearer secret-value"})
        self.store.record(self.case_id,"research",{"token":"do-not-store"})
        exported = self.store.export(self.case_id)
        self.assertNotIn("do-not-store",exported)
        self.assertNotIn("secret-value",exported)
        self.assertIn("[skryto]",exported)

    def test_nonfinite_or_oversized_payload_is_refused(self):
        with self.assertRaises(ValueError):
            self.store.add_evidence(self.case_id,dict(self.event,observed_at=float("nan")))
        with self.assertRaises(ValueError):
            self.store.add_evidence(self.case_id,dict(self.event,payload={"log":"x"*70000}))

    def test_only_matching_verified_offline_report_resolves_case(self):
        report = {"incident_id":self.case_id,"scope":"offline_isolated_fixture","classification":"Vyřešeno a ověřeno"}
        for invalid in (dict(report,classification="Oprava provedena, ověření čeká"),
                        dict(report,scope="live"),dict(report,incident_id="another-case")):
            with self.assertRaises(ValueError):
                self.store.mark_resolved(self.case_id,invalid)
        self.assertEqual(self.store.case(self.case_id)["incident"]["status"],"open")
        self.store.mark_resolved(self.case_id,report)
        self.assertEqual(self.store.case(self.case_id)["incident"]["status"],"resolved")
        reopened = self.store.open_incident("radio","Rádio se samo vypnulo.",[],150,correlation_key="radio:kitchen",occurrence_id="occ-new")
        self.assertEqual(reopened["status"],"open")
        self.assertEqual(self.store.case(self.case_id)["records"][-1]["kind"],"verified_resolution")

    def test_claim_of_real_core_success_without_persisted_verifier_is_rejected(self):
        report = {"incident_id": self.case_id, "scope": "actual_core_container",
                  "classification": "Vyřešeno a ověřeno", "execution_id": "invented"}
        for scope in ('actual_core_container','actual_core_managed_reference','actual_core_native_lighting'):
            with self.assertRaises(ValueError):
                self.store.mark_resolved(self.case_id,dict(report,scope=scope))
        self.assertEqual(self.store.case(self.case_id)["incident"]["status"], "open")
        self.assertEqual(self.store.case(self.case_id)["records"], [])


if __name__ == "__main__":
    unittest.main()
