"""Read-only HAOS development application. No AI or repair executor imports."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time

from .diagnostics import investigate_radio
from .evidence import IncidentStore
from .observability import redact

VERSION = "0.1.0-dev1"
ENTITY = re.compile(r"[a-z][a-z0-9_]*\.[a-z0-9_]+")


def project_state(row):
    if not isinstance(row, dict) or not ENTITY.fullmatch(str(row.get("entity_id", ""))):
        return None
    context = row.get("context")
    return {"entity_id": row["entity_id"], "state": str(row.get("state", "unknown"))[:256],
            "last_updated": str(row.get("last_updated", ""))[:80],
            "context": {k: str(context[k])[:128] for k in ("id", "parent_id") if context.get(k)}
                if isinstance(context, dict) else {}}


class Application:
    def __init__(self, data_dir, core=None, *, clock=time.time):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.store = IncidentStore(self.data_dir / "incidents.sqlite")
        self.core, self.clock = core, clock
        self._lock = threading.RLock()
        self._read_lock = threading.Lock()
        self._last_attempt = None
        self._entities = []
        self._summary = {"available": False, "version": None, "entity_count": 0,
                         "unavailable_count": 0, "last_refresh_at": None,
                         "last_error": "Čtení Core ještě neproběhlo.", "source_status": None}

    def refresh(self):
        if not self._read_lock.acquire(blocking=False):
            return self.snapshot()
        try:
            now = self.clock()
            if self._last_attempt is not None and now - self._last_attempt < 60:
                return self.snapshot()
            self._last_attempt = now
            if self.core is None:
                with self._lock:
                    self._summary["last_error"] = "Chybí přístup k HA Core. Incidenty lze nadále uložit."
                return self.snapshot()
            config = self.core.config()
            states = self.core.states()
            valid = isinstance(states, list) and len(states) <= 10000
            projected = [s for row in states if (s := project_state(row))] if valid else []
            status = self.core.status.snapshot(now)
            with self._lock:
                self._entities = projected
                self._summary = {"available": valid and status["read_succeeded"],
                    "version": config.get("version") if isinstance(config, dict) else None,
                    "entity_count": len(projected),
                    "unavailable_count": sum(s["state"] == "unavailable" for s in projected),
                    "last_refresh_at": now, "source_status": status,
                    "last_error": None if valid else "Stavy Core se nepodařilo přečíst v povoleném rozsahu."}
            return self.snapshot()
        finally:
            self._read_lock.release()

    def snapshot(self):
        with self.store._connect() as db:
            rows = db.execute("SELECT i.*, (SELECT count(*) FROM occurrences o WHERE o.incident_id=i.id) AS occurrence_count "
                              "FROM incidents i ORDER BY last_seen DESC LIMIT 50").fetchall()
        cases = []
        for row in rows:
            item = dict(row)
            item["components"] = json.loads(item["components"])
            cases.append(item)
        with self._lock:
            return {"version": VERSION, "mode": "read_only_development", "core": dict(self._summary),
                    "entities": list(self._entities), "cases": cases,
                    "hermes_enabled": False, "live_repairs_enabled": False,
                    "limitations_cs": "Vývojová přejímka: Hermes a živé opravy nejsou aktivní. Nedostupnost entity sama nedokazuje příčinu závady."}

    def report_incident(self, symptom, entity_id, principal):
        symptom = " ".join(str(symptom).split())
        if not 3 <= len(symptom) <= 1000 or not ENTITY.fullmatch(str(entity_id)) or not principal:
            raise ValueError("Vyplň popis problému a platné entity_id, například media_player.radio.")
        now = self.clock()
        with self.store._connect() as db:
            total = db.execute("SELECT count(*) FROM incidents").fetchone()[0]
            occurrences = db.execute("SELECT count(*) FROM occurrences").fetchone()[0]
        if total >= 200 or occurrences >= 2000:
            raise ValueError("Vývojové úložiště dosáhlo limitu. Nejprve exportuj spisy a připrav řízenou archivaci.")
        key = "manual:" + hashlib.sha256((entity_id + "\n" + symptom).encode()).hexdigest()
        incident = self.store.open_incident("manual_functional", redact(symptom), [entity_id], now, correlation_key=key)
        incident_id = incident["id"]
        self.store.record(incident_id, "user_report", {"symptom": redact(symptom), "entity_id": entity_id,
            "principal": principal, "observed_at": now, "scope": "haos_read_only_preview"})
        evidence = []
        with self._read_lock:
            history = None
            if self.core is not None:
                iso = lambda stamp: datetime.fromtimestamp(stamp, timezone.utc).isoformat()
                history = self.core.history(iso(now - 600), entity_id, iso(now))
            if isinstance(history, list):
                rows = [row for group in history if isinstance(group, list) for row in group]
                if len(rows) > 1000:
                    rows = []
                previous = None
                for raw in rows:
                    state = project_state(raw)
                    if state is None or state["entity_id"] != entity_id:
                        continue
                    try:
                        dt = datetime.fromisoformat(state["last_updated"])
                        if dt.tzinfo is None:
                            continue
                        observed = dt.timestamp()
                    except ValueError:
                        continue
                    if not now - 600 <= observed <= now:
                        continue
                    payload = {**state, "from": previous["state"] if previous else None, "to": state["state"]}
                    event = {"source": "ha_core_history", "kind": "player_state" if entity_id.startswith("media_player.") else "entity_state",
                             "observed_at": observed, "payload": payload,
                             "event_id": hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()}
                    # Persist the source state, whose identity does not change
                    # when a later history window begins with a different row.
                    self.store.add_evidence(incident_id, {**event, "kind": "entity_state", "payload": state})
                    evidence.append(event)
                    previous = state
            read_status = self.core.status.snapshot(now) if self.core is not None else {"read_succeeded": False, "last_error": "Core není připojen."}
        conclusion = investigate_radio(evidence, entity_id, now, window=600) if entity_id.startswith("media_player.") else {
            "category": "insufficient_evidence", "summary_cs": "Incident je uložený. Historie stavu sama příčinu nedokazuje.",
            "needed": ["Doplnit související události a funkční test."]}
        self.store.record(incident_id, "deterministic_investigation", {**conclusion,
            "source_status": read_status, "scope": "haos_read_only_preview",
            "limitation": "Hermes, Action history, traces a Music Assistant nejsou v této instalační verzi propojené. Žádná oprava nebyla provedena."})
        return self.store.case(incident_id)
