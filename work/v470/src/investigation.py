"""Bounded read-only evidence collection. No service calls, shell or file writes.

Adapters are injected so the same collector is exercised by offline tests and HA.
Empty history and unavailable telemetry are coverage gaps, never proof of health.
"""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import quote, urlencode


def entity_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+", value) or len(value) > 255:
        raise ValueError("Invalid entity_id")
    return value


def window(start, end):
    values = [dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")) for v in (start, end)]
    if any(v.tzinfo is None for v in values):
        raise ValueError("Evidence window requires explicit timezone")
    a, b = [v.astimezone(dt.timezone.utc) for v in values]
    if not dt.timedelta(0) < b - a <= dt.timedelta(hours=48):
        raise ValueError("Evidence window must be positive and at most 48 hours")
    return a.isoformat(), b.isoformat()


def case_window(case):
    # Never silently turn an unknown incident date into 'today'.
    stamp = dt.datetime.fromisoformat(str(case.get("last_seen") or "").replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Incident time has no timezone")
    return window((stamp - dt.timedelta(hours=12)).isoformat(), (stamp + dt.timedelta(hours=12)).isoformat())


def compact_state(row):
    attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    allowed = ("device_class", "unit_of_measurement", "battery", "battery_level", "linkquality", "rssi", "lqi", "last_seen", "last_triggered", "restored", "current")
    return {**{k: row.get(k) for k in ("entity_id", "state", "last_changed", "last_updated")},
            "attributes": {k: attrs[k] for k in allowed if k in attrs}}


def disposition(analysis):
    """Route a reviewable recommendation without certifying an AI conclusion.

    Execution still requires the separate trusted compiler, approval and backup.
    A question needs both a concrete question and why read-only tools cannot answer.
    """
    if not isinstance(analysis, dict) or not str(analysis.get("summary") or "").strip():
        return "investigating"
    question = analysis.get("user_question")
    if analysis.get("decision_kind") == "needs_user_input" and isinstance(question, dict):
        if all(isinstance(question.get(k), str) and question[k].strip() for k in ("question", "why_readonly_cannot_answer")):
            return "needs_information"
    if analysis.get("decision_kind") in {"conclusion", "advisory"}:
        hypotheses = analysis.get("hypotheses") or []
        evidence = any(isinstance(h, dict) and any(isinstance(e, str) and e.strip() for e in (h.get("evidence_for") or [])) for h in hypotheses)
        if evidence and str(analysis.get("functional_impact") or "").strip() and str(analysis.get("next_test") or "").strip():
            return "review_ready"
    return "investigating"


class Investigator:
    def __init__(self, get, ws, db, now):
        self.get, self.ws, self.db, self.now = get, ws, db, now

    def read(self, source, function):
        try:
            return {"source": source, "status": "ok", "fetched_at": self.now(), "data": function()}
        except Exception as exc:
            return {"source": source, "status": "unavailable", "fetched_at": self.now(), "error": str(exc)[:500]}

    def live_state(self, target):
        target = entity_id(target)
        def fetch():
            value = self.get("/core/api/states/" + quote(target, safe=""), timeout=10, allow_stale=False)
            if not isinstance(value, dict) or value.get("entity_id") != target or "state" not in value:
                raise ValueError("State response does not identify requested entity")
            return compact_state(value)
        return self.read("ha_current_state:" + target, fetch)

    def history(self, target, start, end):
        target = entity_id(target)
        start, end = window(start, end)
        path = "/core/api/history/period/" + quote(start, safe="") + "?" + urlencode({
            "end_time": end, "filter_entity_id": target, "minimal_response": "", "no_attributes": ""})
        def fetch():
            raw = self.get(path, timeout=20, allow_stale=False)
            if not isinstance(raw, list) or any(not isinstance(group, list) for group in raw):
                raise ValueError("Invalid history response")
            rows = [r for group in raw for r in group if isinstance(r, dict)]
            if any(r.get("entity_id", target) != target for r in rows):
                raise ValueError("History response contains unrelated entity")
            # Full first and last edges, with explicit omission instead of false complete history.
            selected = rows if len(rows) <= 120 else rows[:20] + rows[-100:]
            return {"entity_id": target, "start": start, "end": end, "total_returned": len(rows),
                    "omitted": max(0, len(rows) - len(selected)), "coverage": "records_returned" if rows else "no_records_unknown_coverage",
                    "records": [{k: r[k] for k in ("state", "last_changed", "last_updated") if k in r} for r in selected]}
        return self.read("ha_recorder_history:" + target, fetch)

    def device(self, target, start, end):
        target = entity_id(target)
        start, end = window(start, end)
        result = {"entity_id": target, "current": self.live_state(target), "history": self.history(target, start, end),
                  "related_telemetry": [], "coverage_gaps": [],
                  "interpretation": "Current response is not a successful physical action; last_changed is not last contact."}
        registry = self.read("ha_entity_registry", lambda: self.ws("config/entity_registry/list"))
        if registry["status"] != "ok" or not isinstance(registry.get("data"), list):
            result["coverage_gaps"].append("Entity registry unavailable; related battery/signal cannot be associated safely.")
            result["registry_status"] = {k: v for k, v in registry.items() if k != "data"}
            return result
        rows = [r for r in registry["data"] if isinstance(r, dict)]
        owner = next((r for r in rows if r.get("entity_id") == target), {})
        device = owner.get("device_id")
        result["registry"] = {k: owner.get(k) for k in ("entity_id", "device_id", "platform", "disabled_by", "config_entry_id")}
        if not device:
            result["coverage_gaps"].append("No device association; no inferred association by similar name.")
            return result
        def device_info():
            raw = self.ws("config/device_registry/list")
            if not isinstance(raw, list):
                raise ValueError("Invalid device registry response")
            match = next((r for r in raw if isinstance(r, dict) and r.get("id") == device), None)
            if match is None:
                raise ValueError("Associated device absent from registry")
            return {k: match.get(k) for k in ("id", "manufacturer", "model", "sw_version", "hw_version", "via_device_id", "disabled_by")}
        result["device"] = self.read("ha_device_registry:" + str(device), device_info)
        siblings = [r for r in rows if r.get("device_id") == device and r.get("entity_id") != target]
        candidates = [r for r in siblings if r.get("device_class") in ("battery", "signal_strength") or r.get("original_device_class") in ("battery", "signal_strength") or re.search(r"(?:^|_)(battery|batterie|rssi|lqi|linkquality|signal|last_seen)(?:_|$)", str(r.get("entity_id", "")).split(".")[-1])]
        result["telemetry_candidates"] = len(candidates)
        result["telemetry_omitted"] = max(0, len(candidates) - 4)
        for row in candidates[:4]:
            item = {"entity_id": row["entity_id"], "disabled_by": row.get("disabled_by")}
            if row.get("disabled_by"):
                item["coverage"] = "disabled_not_enabled_by_diagnosis"
            else:
                item["current"] = self.live_state(row["entity_id"])
                item["history"] = self.history(row["entity_id"], start, end)
            result["related_telemetry"].append(item)
        if not candidates:
            result["coverage_gaps"].append("No registered battery/signal telemetry found; this does not establish a healthy battery or radio link.")
        return result

    def logs(self, case, start, end):
        start, end = window(start, end)
        with self.db() as conn:
            rows = conn.execute("""SELECT o.id,o.case_id,o.occurred_at,o.source_name,o.level,o.message
                FROM occurrences o WHERE o.case_id=? AND julianday(o.occurred_at) BETWEEN julianday(?) AND julianday(?)
                ORDER BY julianday(o.occurred_at) DESC LIMIT 101""", (int(case["id"]), start, end)).fetchall()
        return {"source": "hads_imported_case_occurrences", "fetched_at": self.now(), "start": start, "end": end,
                "coverage": "imported_findings_only_not_complete_raw_logs", "truncated": len(rows) > 100,
                "records": [{**dict(r), "message": r["message"][:2000]} for r in rows[:100]]}

    def source_log(self, source):
        # No user/model-supplied URL, arbitrary path or addon slug accepted.
        endpoints = {"core": "/core/logs", "supervisor": "/supervisor/logs", "host": "/host/logs"}
        if source not in endpoints:
            raise ValueError("Unknown log source")
        def fetch():
            raw = self.get(endpoints[source], raw=True, timeout=15, allow_stale=False)
            if not isinstance(raw, str):
                raise ValueError("Invalid log response")
            lines = raw.splitlines()
            return {"lines": lines[-150:], "returned_lines": len(lines), "omitted_lines": max(0, len(lines)-150),
                    "coverage": "available_log_tail_not_historical_day"}
        return self.read("supervisor_log:" + source, fetch)

    def addon_log(self, slug):
        if not isinstance(slug, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", slug):
            raise ValueError("Invalid addon slug")
        def fetch():
            raw = self.get("/addons", timeout=10, allow_stale=False)
            addons = raw.get("addons") if isinstance(raw, dict) else raw
            if not isinstance(addons, list) or not any(isinstance(a, dict) and a.get("slug") == slug for a in addons):
                raise ValueError("Addon is not in live installed inventory")
            log = self.get("/addons/" + slug + "/logs", raw=True, timeout=15, allow_stale=False)
            if not isinstance(log, str):
                raise ValueError("Invalid addon log response")
            lines = log.splitlines()
            return {"lines": lines[-150:], "omitted_lines": max(0, len(lines)-150),
                    "coverage": "available_log_tail_not_historical_day", "installed_verified_at": self.now()}
        return self.read("supervisor_addon_log:" + slug, fetch)

    def resources(self, start, end, page=0):
        start, end = window(start, end)
        if type(page) is not int or not 0 <= page <= 100:
            raise ValueError("Invalid addon page")
        result = {"start": start, "end": end, "page": page, "containers": [],
                  "coverage_gaps": ["Container statistics are not a process list. Host RAM pressure and physical hardware capacity require independent host evidence."]}
        if page == 0:
            for label, path in (("core", "/core/stats"), ("supervisor", "/supervisor/stats"), ("host", "/host/info")):
                result[label] = self.read(path, lambda path=path: self.get(path, timeout=10, allow_stale=False))
        inventory = self.read("supervisor_addons", lambda: self.get("/addons", timeout=10, allow_stale=False))
        raw = inventory.get("data", {})
        addons = raw.get("addons") if isinstance(raw, dict) else raw
        if inventory["status"] != "ok" or not isinstance(addons, list):
            result["inventory"] = {k: v for k, v in inventory.items() if k != "data"}
            result["coverage_gaps"].append("Live addon inventory unavailable; no complete memory ranking possible.")
        else:
            addons = sorted([a for a in addons if isinstance(a, dict) and re.fullmatch(r"[a-zA-Z0-9_-]+", str(a.get("slug", "")))], key=lambda a: a["slug"])
            result["total_addons"] = len(addons)
            result["next_page"] = page + 1 if (page+1)*8 < len(addons) else None
            for addon in addons[page*8:(page+1)*8]:
                item = {k: addon.get(k) for k in ("slug", "name", "state", "version")}
                if addon.get("state") == "started":
                    path = "/addons/" + addon["slug"] + "/stats"
                    item["stats"] = self.read(path, lambda path=path: self.get(path, timeout=10, allow_stale=False))
                result["containers"].append(item)
        with self.db() as conn:
            series = conn.execute("""SELECT source,name,unit,COUNT(*) samples,MIN(measured_at) first_sample,MAX(measured_at) last_sample,
                MIN(value) minimum,MAX(value) maximum,AVG(value) average
                FROM metrics WHERE julianday(measured_at) BETWEEN julianday(?) AND julianday(?) AND value IS NOT NULL
                AND (name LIKE '%.memory_%' OR name LIKE '%.cpu_percent') GROUP BY source,name,unit ORDER BY source,name LIMIT 301""", (start, end)).fetchall()
            events = conn.execute("""SELECT event_type,title,occurred_at,source FROM system_events
                WHERE julianday(occurred_at) BETWEEN julianday(?) AND julianday(?) ORDER BY julianday(occurred_at) DESC LIMIT 51""", (start, end)).fetchall()
        result["metric_history"] = {"source": "hads_stored_metrics", "series": [dict(r) for r in series[:300]], "truncated": len(series)>300,
                                    "interpretation": "Sparse samples and min/max/average do not establish continuous pressure or a memory leak."}
        result["lifecycle_events"] = {"records": [dict(r) for r in events[:50]], "truncated": len(events)>50}
        return result
