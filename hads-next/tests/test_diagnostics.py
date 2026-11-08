import copy
import json
from pathlib import Path
import tempfile
import unittest

from hads_next.diagnostics import correlate_dns, ingest_dns_incidents, investigate_radio, investigate_zigbee
from hads_next.evidence import IncidentStore


FIXTURES = Path(__file__).parent / "fixtures"


class DiagnosticTests(unittest.TestCase):
    def test_A_radio_distinguishes_command_stream_disconnect_and_unknown(self):
        fixture = json.loads((FIXTURES/"radio.json").read_text())
        expected = {"stop_command":"commanded_stop","stream_failure":"stream_failure",
                    "player_disconnected":"player_disconnected","unknown":"insufficient_evidence"}
        for scenario, category in expected.items():
            with self.subTest(scenario=scenario):
                result = investigate_radio(fixture[scenario],fixture["entity_id"],fixture["incident_at"])
                self.assertEqual(result["category"],category)
                self.assertTrue(result["summary_cs"])

    def test_radio_stop_without_context_remains_hypothesis(self):
        fixture = json.loads((FIXTURES/"radio.json").read_text())
        events = fixture["stop_command"]
        events[0]["payload"]["context"]["id"] = "unrelated-context"
        result = investigate_radio(events,fixture["entity_id"],fixture["incident_at"])
        self.assertEqual(result["category"],"insufficient_evidence")
        self.assertIn("possible_stop_command",result["hypotheses"])

    def test_radio_ignores_wrong_player_and_old_errors(self):
        fixture = json.loads((FIXTURES/"radio.json").read_text())
        events = fixture["stream_failure"]
        events[0]["payload"]["entity_id"] = "media_player.bedroom"
        self.assertEqual(investigate_radio(events,fixture["entity_id"],fixture["incident_at"])["category"],"insufficient_evidence")
        events[0]["payload"]["entity_id"] = fixture["entity_id"]
        events[0]["observed_at"] -= 600
        self.assertEqual(investigate_radio(events,fixture["entity_id"],fixture["incident_at"])["category"],"insufficient_evidence")

    def test_multiple_radio_candidates_do_not_produce_false_root_cause(self):
        fixture = json.loads((FIXTURES/"radio.json").read_text())
        events = fixture["stream_failure"] + fixture["player_disconnected"][:1]
        result = investigate_radio(events,fixture["entity_id"],fixture["incident_at"])
        self.assertEqual(result["category"],"insufficient_evidence")
        self.assertEqual(set(result["hypotheses"]),{"stream_failure","player_disconnected"})

    def test_later_stream_error_is_not_reported_as_preceding_cause(self):
        fixture = json.loads((FIXTURES/"radio.json").read_text())
        events = fixture["stream_failure"]
        events[0]["observed_at"] = fixture["incident_at"] + 1
        self.assertEqual(investigate_radio(events,fixture["entity_id"],fixture["incident_at"])["category"], "insufficient_evidence")

    def _zigbee(self, events):
        fixture = json.loads((FIXTURES/"zigbee.json").read_text())
        return investigate_zigbee(events,fixture["device_id"],fixture["automation_id"],fixture["target_entity_id"],fixture["incident_at"])

    def test_B_zigbee_identifies_chain_stage(self):
        events = json.loads((FIXTURES/"zigbee.json").read_text())["events"]
        self.assertEqual(self._zigbee([])["category"],"physical_press_not_observed")
        self.assertEqual(self._zigbee(events[:1])["category"],"event_received_no_trace")
        for outcome,category in (("condition_failed","automation_condition_failed"),("invalid_entity_reference","invalid_entity_reference"),("action_error","automation_action_failed")):
            sample = copy.deepcopy(events)
            sample[1]["payload"]["result"] = outcome
            self.assertEqual(self._zigbee(sample)["category"],category)
        self.assertEqual(self._zigbee(events[:2])["category"],"action_completed_verification_pending")
        self.assertEqual(self._zigbee(events)["category"],"target_state_mismatch")
        events[2]["payload"]["state"] = "on"
        self.assertEqual(self._zigbee(events)["category"],"chain_observed_success")

    def test_unrelated_trace_is_not_evidence_that_button_triggered_automation(self):
        events = json.loads((FIXTURES/"zigbee.json").read_text())["events"]
        events[1]["payload"]["trigger_context_id"] = "other-button"
        self.assertEqual(self._zigbee(events)["category"],"event_received_no_trace")

    def test_unrelated_target_change_is_not_proof_of_chain_success(self):
        events = json.loads((FIXTURES/"zigbee.json").read_text())["events"]
        events[2]["payload"]["state"] = "on"
        events[2]["payload"]["context"] = {"id":"another-automation"}
        self.assertEqual(self._zigbee(events)["category"],"action_completed_verification_pending")

    def test_C_one_dns_outage_one_incident_many_symptoms_and_no_duplicate_reads(self):
        events = json.loads((FIXTURES/"dns.json").read_text())["events"]
        groups = correlate_dns(events)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0]["symptoms"]),3)
        self.assertNotIn("unrelated-1",[e["event_id"] for e in groups[0]["symptoms"]])
        with tempfile.TemporaryDirectory() as temp:
            store = IncidentStore(Path(temp)/"cases.sqlite")
            cases = ingest_dns_incidents(store,events)
            repeated = ingest_dns_incidents(store,events)
            self.assertEqual(cases[0]["id"],repeated[0]["id"])
            case = store.case(cases[0]["id"])
            self.assertEqual(len(case["evidence"]),4)
            self.assertEqual(len(case["occurrences"]),1)

    def test_dns_text_similarity_alone_is_not_a_cause(self):
        events = json.loads((FIXTURES/"dns.json").read_text())["events"]
        self.assertEqual(correlate_dns(events[1:]),[])

    def test_repeated_dns_probes_are_one_outage_occurrence(self):
        events = json.loads((FIXTURES/"dns.json").read_text())["events"]
        events.append(dict(events[0],observed_at=1794139405,event_id="dns-probe-2"))
        self.assertEqual(len(correlate_dns(events)),1)
        with tempfile.TemporaryDirectory() as temp:
            store = IncidentStore(Path(temp)/"cases.sqlite")
            case_id = ingest_dns_incidents(store,events)[0]["id"]
            self.assertEqual(len(store.case(case_id)["occurrences"]),1)
            self.assertEqual(len(store.case(case_id)["evidence"]),5)

    def test_H_deterministic_diagnosis_has_no_model_dependency(self):
        fixture = json.loads((FIXTURES/"radio.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            store = IncidentStore(Path(temp)/"offline.sqlite")
            incident = store.open_incident("radio","Rádio se vypnulo.",[fixture["entity_id"]],fixture["incident_at"])
            for event in fixture["stream_failure"]:
                store.add_evidence(incident["id"],event)
            result = investigate_radio(store.case(incident["id"])["evidence"],fixture["entity_id"],fixture["incident_at"])
            self.assertEqual(result["category"],"stream_failure")
            self.assertEqual(len(IncidentStore(Path(temp)/"offline.sqlite").case(incident["id"])["evidence"]),2)


if __name__ == "__main__":
    unittest.main()
