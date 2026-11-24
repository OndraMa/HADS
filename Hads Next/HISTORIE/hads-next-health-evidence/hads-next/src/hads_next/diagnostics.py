"""Deterministic, bounded analysis of normalized evidence, also without AI.

These are HADS evidence contracts, not invented Home Assistant/MA API schemas.
Adapters must preserve origin and explicitly map verified upstream fields.
"""
from __future__ import annotations

from .evidence import IncidentStore, normalize_evidence


def _window(events: list[dict], incident_at: float, window: float) -> list[dict]:
    if len(events) > 5000 or not 0 < window <= 3600:
        raise ValueError("Diagnostic evidence budget exceeded")
    normalized = [normalize_evidence(e) for e in events]
    return sorted((e for e in normalized if abs(e["observed_at"] - incident_at) <= window), key=lambda e:e["observed_at"])


def _result(category: str, summary: str, evidence: list[dict], *, hypotheses: list[str] | None = None,
            needed: list[str] | None = None) -> dict:
    return {"category":category,"summary_cs":summary,"evidence_ids":[e["event_id"] for e in evidence],
            "hypotheses":hypotheses or [],"needed":needed or [],"certainty":"supported" if category != "insufficient_evidence" else "unknown"}


def _context(event: dict) -> dict:
    context = event["payload"].get("context", {})
    return context if isinstance(context, dict) else {}


def investigate_radio(events: list[dict], entity_id: str, incident_at: float, window: float = 120) -> dict:
    """Attribute only evidence tied to the player and the actual stop interval."""
    events = _window(events, incident_at, window)
    stopped = [e for e in events if e["kind"] == "player_state" and e["payload"].get("entity_id") == entity_id
               and e["payload"].get("from") == "playing" and e["payload"].get("to") in {"idle","paused","off","unavailable"}]
    if not stopped:
        return _result("insufficient_evidence", "Zastavení přehrávání zatím není doloženo změnou stavu přehrávače.", [],
                       needed=["Historie stavu přehrávače v čase nahlášeného zastavení."])
    stop = min(stopped, key=lambda e:abs(e["observed_at"]-incident_at))
    candidates: dict[str, list[dict]] = {}
    unlinked_actions = []
    for event in events:
        payload = event["payload"]
        lag = stop["observed_at"] - event["observed_at"]
        if not 0 <= lag <= 30:
            continue
        tied = payload.get("entity_id") == entity_id
        if event["kind"] == "ha_action" and payload.get("action") in {"media_player.media_stop","media_player.media_pause","media_player.turn_off"} and payload.get("target_entity_id") == entity_id and 0 <= lag <= 10:
            action_context = _context(event).get("id")
            if action_context and action_context in {_context(stop).get("id"),_context(stop).get("parent_id")}:
                candidates.setdefault("commanded_stop", []).append(event)
            else:
                unlinked_actions.append(event)
        if tied and event["kind"] == "ma_playback" and payload.get("event") == "stream_error" and payload.get("reason") in {"stream_timeout","stream_eof","stream_unavailable"}:
            candidates.setdefault("stream_failure", []).append(event)
        if tied and event["kind"] == "ma_player" and payload.get("event") == "disconnected":
            candidates.setdefault("player_disconnected", []).append(event)
        if tied and event["kind"] == "ma_provider" and payload.get("event") == "unavailable":
            candidates.setdefault("provider_unavailable", []).append(event)
        if event["kind"] in {"network_dns_failure","network_outage"} and entity_id in payload.get("affected_entities", []):
            candidates.setdefault("network_failure", []).append(event)
        if tied and event["kind"] == "integration_playback_action" and payload.get("action") in {"stop","pause","off"}:
            action_context = _context(event).get("id")
            if action_context and action_context in {_context(stop).get("id"),_context(stop).get("parent_id")}:
                candidates.setdefault("integration_stop", []).append(event)
    if len(candidates) > 1:
        # A timeout may be downstream of a network outage. No unsupported causal
        # ordering is imposed merely because the two events happened together.
        return _result("insufficient_evidence", "V čase zastavení je více doložených okolností. Hlavní příčinu zatím nelze spolehlivě určit.",
                       [stop] + [e for values in candidates.values() for e in values], hypotheses=sorted(candidates),
                       needed=["Doplňující časová osa streamu, sítě a původu akcí pro rozlišení souběžných příčin."])
    if candidates:
        category, supporting = next(iter(candidates.items()))
        summaries = {
            "commanded_stop":"Zastavení navazuje na příkaz pro tento přehrávač se shodným kontextem. Původce je uveden v důkazech akce.",
            "integration_stop":"Změna přehrávání navazuje na doloženou akci integrace se shodným kontextem.",
            "stream_failure":"Před zastavením je doložena chyba dodávky streamu pro tento přehrávač.",
            "player_disconnected":"V čase zastavení je doloženo odpojení přehrávače.",
            "provider_unavailable":"V čase zastavení je doložena nedostupnost provideru tohoto přehrávače.",
            "network_failure":"V čase zastavení je doložen síťový výpadek zasahující tento přehrávač.",
        }
        return _result(category, summaries[category], [stop] + supporting)
    return _result("insufficient_evidence", "Přehrávání se zastavilo, ale dostupná data příčinu nedokládají.", [stop] + unlinked_actions,
                   hypotheses=["possible_stop_command"] if unlinked_actions else [],
                   needed=["Původ akcí s kontextem a diagnostické události Music Assistantu před zastavením."])


def investigate_zigbee(events: list[dict], device_id: str, automation_id: str, target_entity_id: str,
                       incident_at: float, window: float = 120) -> dict:
    events = _window(events, incident_at, window)
    zha = [e for e in events if e["kind"] == "zha_event" and e["payload"].get("device_id") == device_id]
    if not zha:
        return _result("physical_press_not_observed", "Událost ovladače není v dostupných důkazech. To nedokazuje, že fyzický stisk neproběhl.", [],
                       needed=["Stiskni nyní prostřední tlačítko. Ověřím, kde se ztratí reakce.","Ověřit dostupnost a oprávnění odběru ZHA událostí."])
    press = min(zha, key=lambda e:abs(e["observed_at"]-incident_at))
    context_id = _context(press).get("id")
    traces = [e for e in events if e["kind"] == "automation_trace" and e["payload"].get("automation_id") == automation_id
              and context_id and e["payload"].get("trigger_context_id") == context_id and 0 <= e["observed_at"] - press["observed_at"] <= 15]
    if not traces:
        return _result("event_received_no_trace", "ZHA událost byla přijata. Chybí navázaná trace, takže spuštění automatizace nelze potvrdit.", [press],
                       needed=["Trace dané automatizace a potvrzení úspěšného čtení trace API."])
    trace = traces[-1]
    payload = trace["payload"]
    outcome = payload.get("result")
    if outcome == "condition_failed":
        return _result("automation_condition_failed", "Ovladač událost odeslal a automatizace ji přijala, ale její podmínka nebyla splněna.", [press,trace])
    if outcome == "invalid_entity_reference":
        return _result("invalid_entity_reference", "Událost i spuštění automatizace jsou doložené. Akce odkazuje na neplatnou entitu.", [press,trace])
    if outcome == "action_error":
        return _result("automation_action_failed", "Automatizace událost přijala, ale provedení akce skončilo chybou.", [press,trace])
    if outcome != "completed" or payload.get("target_entity_id") != target_entity_id or "expected_state" not in payload:
        return _result("insufficient_evidence", "Trace je dostupná, ale nedokládá konkrétní očekávaný výsledek pro cílové zařízení.", [press,trace],
                       needed=["Výsledek akce, cílová entita a očekávaný stav."])
    states = [e for e in events if e["kind"] == "target_state" and e["payload"].get("entity_id") == target_entity_id
              and 0 <= e["observed_at"] - trace["observed_at"] <= 15]
    if not states:
        return _result("action_completed_verification_pending", "Akce automatizace skončila, ale chybí následné ověření stavu zařízení.", [press,trace],
                       needed=["Nový stav cílového zařízení nebo jednoduché potvrzení fyzického výsledku."])
    state = states[-1]
    expected = payload["expected_state"]
    if state["payload"].get("state") == expected:
        trace_context = _context(trace).get("id")
        if not trace_context or trace_context not in {_context(state).get("id"),_context(state).get("parent_id")}:
            return _result("action_completed_verification_pending", "Cílový stav odpovídá očekávání, ale jeho kontext není navázán na vyšetřovanou automatizaci.",
                           [press,trace,state],needed=["Kontext změny stavu nebo nezávislý řízený funkční test."])
        return _result("chain_observed_success", "Přijatá událost, automatizace i očekávaný stav zařízení jsou doložené. Fyzický výsledek případně potvrď testem.", [press,trace,state])
    return _result("target_state_mismatch", "Automatizace dokončila akci, ale následný stav zařízení neodpovídá očekávání.", [press,trace,state],
                   needed=["Ověřit dostupnost zařízení a fyzický výsledek; samotné dokončení akce není úspěch."])


def correlate_dns(events: list[dict]) -> list[dict]:
    """Group only explicit outage-linked symptoms; similar log text is ignored."""
    if len(events) > 5000:
        raise ValueError("Correlation evidence budget exceeded")
    events = [normalize_evidence(e) for e in events]
    failures = [e for e in events if e["kind"] == "network_dns_failure" and isinstance(e["payload"].get("outage_id"),str) and e["payload"]["outage_id"]]
    by_outage: dict[str,list[dict]] = {}
    for failure in failures:
        by_outage.setdefault(failure["payload"]["outage_id"], []).append(failure)
    groups = []
    for outage_id, probes in by_outage.items():
        probes.sort(key=lambda e:e["observed_at"])
        failure = probes[0]
        symptoms = [e for e in events if e["kind"] == "integration_error" and e["payload"].get("outage_id") == outage_id
                    and failure["observed_at"] <= e["observed_at"] <= probes[-1]["observed_at"] + 60]
        groups.append({"correlation_key":f"dns:{outage_id}","cause":failure,"additional_failures":probes[1:],"symptoms":symptoms})
    return groups


def ingest_dns_incidents(store: IncidentStore, events: list[dict]) -> list[dict]:
    result = []
    for group in correlate_dns(events):
        cause = group["cause"]
        components = sorted({e["payload"].get("integration", "network") for e in [cause] + group["symptoms"]})
        incident = store.open_incident("dns_outage", "Výpadek DNS ovlivnil více integrací.", components, cause["observed_at"],
                                       correlation_key=group["correlation_key"], occurrence_id=group["correlation_key"])
        for event in [cause] + group["additional_failures"] + group["symptoms"]:
            store.add_evidence(incident["id"], event)
        result.append(incident)
    return result
