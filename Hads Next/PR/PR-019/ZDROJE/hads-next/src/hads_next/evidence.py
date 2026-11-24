"""Persistent incident files. Event identity is independent of collection time."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any
import uuid

from .observability import redact


SCHEMA_VERSION = 1
MAX_EVIDENCE_BYTES = 65536
MAX_CASE_EVIDENCE = 1000
MAX_CASE_BYTES = 4 * 1024 * 1024


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalize_evidence(value: dict) -> dict:
    """Reject malformed evidence; omit read timestamps from event identity."""
    if not isinstance(value, dict):
        raise ValueError("Evidence must be a JSON object")
    for field in ("source", "kind"):
        if not isinstance(value.get(field), str) or not 0 < len(value[field]) <= 200:
            raise ValueError(f"Invalid evidence {field}")
    stamp = value.get("observed_at")
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
        raise ValueError("observed_at must be a finite UTC timestamp")
    if not isinstance(value.get("payload"), dict):
        raise ValueError("payload must be an object")
    event_id = value.get("event_id")
    if event_id is not None and (not isinstance(event_id, str) or not 0 < len(event_id) <= 500):
        raise ValueError("Invalid event_id")
    result = {key: value[key] for key in ("source", "kind", "observed_at", "payload")}
    result["observed_at"] = float(stamp)
    result["payload"] = redact(result["payload"])
    if len(canonical(result).encode()) > MAX_EVIDENCE_BYTES:
        raise ValueError("Evidence exceeds byte budget")
    result["event_id"] = event_id or digest(result)
    return result


class IncidentStore:
    """Small SQLite store; separate metadata namespace permits shared DB files.

    Callers provide supported correlation identifiers, never free-text guesses.
    No AI dependency exists in collection, recurrence, export or retention.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        if self.db_path == ":memory:":
            raise ValueError("Persistent incident storage requires a file path")
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS evidence_schema(version INTEGER NOT NULL)")
            row = db.execute("SELECT version FROM evidence_schema").fetchone()
            if row is not None and row[0] != SCHEMA_VERSION:
                raise ValueError(f"Unsupported incident schema {row[0]}")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS incidents(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, symptom TEXT NOT NULL,
                    components TEXT NOT NULL, correlation_key TEXT UNIQUE,
                    first_seen REAL NOT NULL, last_seen REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open', archived_at REAL);
                CREATE TABLE IF NOT EXISTS occurrences(
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    event_id TEXT NOT NULL, observed_at REAL NOT NULL,
                    PRIMARY KEY(incident_id,event_id));
                CREATE TABLE IF NOT EXISTS evidence(
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, event_id TEXT NOT NULL,
                    observed_at REAL NOT NULL, content_hash TEXT NOT NULL, content TEXT NOT NULL,
                    UNIQUE(source,event_id));
                CREATE TABLE IF NOT EXISTS incident_evidence(
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    evidence_id TEXT NOT NULL REFERENCES evidence(id),
                    PRIMARY KEY(incident_id,evidence_id));
                CREATE TABLE IF NOT EXISTS analyses(
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    fingerprint TEXT NOT NULL, status TEXT NOT NULL, result TEXT,
                    PRIMARY KEY(incident_id,fingerprint));
                CREATE TABLE IF NOT EXISTS case_records(
                    id INTEGER PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL, recorded_at REAL NOT NULL, content TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS evidence_time ON evidence(observed_at);
                CREATE INDEX IF NOT EXISTS records_case ON case_records(incident_id,id);
            """)
            if row is None:
                db.execute("INSERT INTO evidence_schema VALUES (?)", (SCHEMA_VERSION,))

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def open_incident(self, kind: str, symptom: str, components: list[str], at: float,
                      *, correlation_key: str | None = None, occurrence_id: str | None = None) -> dict:
        if not kind or not symptom or not math.isfinite(at):
            raise ValueError("Incident requires kind, symptom and a finite timestamp")
        symptom = redact(symptom)
        components = sorted(set(redact(components)))
        occurrence_id = occurrence_id or digest([kind, symptom, components, at])
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM incidents WHERE correlation_key=?", (correlation_key,)).fetchone() if correlation_key else None
            if row is None:
                incident_id = str(uuid.uuid4())
                db.execute("INSERT INTO incidents(id,kind,symptom,components,correlation_key,first_seen,last_seen) VALUES (?,?,?,?,?,?,?)",
                           (incident_id, kind, symptom, canonical(components), correlation_key, at, at))
            else:
                incident_id = row["id"]
                if row["kind"] != kind:
                    raise ValueError("Correlation key already belongs to another problem kind")
            inserted = db.execute("INSERT OR IGNORE INTO occurrences VALUES(?,?,?)", (incident_id, occurrence_id, at)).rowcount
            if inserted:
                previous_components = json.loads(row["components"]) if row else []
                db.execute("UPDATE incidents SET first_seen=min(first_seen,?),last_seen=max(last_seen,?),status='open',archived_at=NULL,components=? WHERE id=?",
                           (at, at, canonical(sorted(set(previous_components + components))), incident_id))
            result = dict(db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone())
            result["components"] = json.loads(result["components"])
            return result

    def add_evidence(self, incident_id: str, value: dict) -> bool:
        event = normalize_evidence(value)
        content_hash = digest(event)
        evidence_id = digest([event["source"], event["event_id"]])
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM incidents WHERE id=?", (incident_id,)).fetchone():
                raise KeyError(incident_id)
            existing = db.execute("SELECT content_hash FROM evidence WHERE id=?", (evidence_id,)).fetchone()
            if existing and existing[0] != content_hash:
                raise ValueError("Source reused event identity for different evidence")
            if db.execute("SELECT 1 FROM incident_evidence WHERE incident_id=? AND evidence_id=?", (incident_id,evidence_id)).fetchone():
                return False
            if db.execute("SELECT count(*) FROM incident_evidence WHERE incident_id=?", (incident_id,)).fetchone()[0] >= MAX_CASE_EVIDENCE:
                raise ValueError("Incident evidence budget exceeded; export/archive required")
            used_bytes = db.execute("SELECT coalesce(sum(length(CAST(e.content AS BLOB))),0) FROM evidence e JOIN incident_evidence l ON e.id=l.evidence_id WHERE l.incident_id=?", (incident_id,)).fetchone()[0]
            if used_bytes + len(canonical(event).encode()) > MAX_CASE_BYTES:
                raise ValueError("Incident byte budget exceeded; export/archive required")
            db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?)",
                       (evidence_id,event["source"],event["event_id"],event["observed_at"],content_hash,canonical(event)))
            db.execute("INSERT INTO incident_evidence VALUES(?,?)", (incident_id,evidence_id))
            return True

    def case(self, incident_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
            if row is None:
                raise KeyError(incident_id)
            incident = dict(row)
            incident["components"] = json.loads(incident["components"])
            evidence = [dict(json.loads(r["content"]), evidence_id=r["id"]) for r in db.execute(
                "SELECT e.* FROM evidence e JOIN incident_evidence l ON e.id=l.evidence_id WHERE l.incident_id=? ORDER BY e.observed_at,e.id", (incident_id,))]
            occurrences = [dict(r) for r in db.execute("SELECT event_id,observed_at FROM occurrences WHERE incident_id=? ORDER BY observed_at,event_id", (incident_id,))]
            analyses = [dict(r) for r in db.execute("SELECT fingerprint,status,result FROM analyses WHERE incident_id=? ORDER BY rowid", (incident_id,))]
            for analysis in analyses:
                analysis["result"] = json.loads(analysis["result"]) if analysis["result"] else None
            records = [{"kind":r["kind"],"recorded_at":r["recorded_at"],"content":json.loads(r["content"])} for r in db.execute(
                "SELECT * FROM case_records WHERE incident_id=? ORDER BY id", (incident_id,))]
            return {"schema_version":SCHEMA_VERSION,"incident":incident,"evidence":evidence,"occurrences":occurrences,"analyses":analyses,"records":records}

    def begin_analysis(self, incident_id: str) -> str | None:
        """Claim each evidence set once, including across crashes and workers.

        A claim left running after restart is never automatically retried. New
        evidence is required; operators can record the interruption in the case.
        This intentionally favours a visible pending case over an endless loop.
        """
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM incidents WHERE id=?", (incident_id,)).fetchone():
                raise KeyError(incident_id)
            hashes = [r[0] for r in db.execute("SELECT e.content_hash FROM evidence e JOIN incident_evidence l ON e.id=l.evidence_id WHERE l.incident_id=? ORDER BY e.id", (incident_id,))]
            if not hashes:
                return None
            fingerprint = digest(hashes)
            inserted = db.execute("INSERT OR IGNORE INTO analyses VALUES(?,?,'running',NULL)", (incident_id,fingerprint)).rowcount
            return fingerprint if inserted else None

    def finish_analysis(self, incident_id: str, fingerprint: str, result: dict, *, failed: bool = False) -> None:
        with self._connect() as db:
            changed = db.execute("UPDATE analyses SET status=?,result=? WHERE incident_id=? AND fingerprint=? AND status='running'",
                                ("failed" if failed else "done",canonical(redact(result)),incident_id,fingerprint)).rowcount
            if not changed:
                raise ValueError("No running analysis matches this evidence fingerprint")

    def record(self, incident_id: str, kind: str, content: dict, *, at: float | None = None) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO case_records(incident_id,kind,recorded_at,content) VALUES(?,?,?,?)", (incident_id,kind,time.time() if at is None else at,canonical(redact(content))))

    def archive(self, incident_id: str, *, at: float) -> None:
        with self._connect() as db:
            if not db.execute("UPDATE incidents SET status='archived',archived_at=? WHERE id=?", (at,incident_id)).rowcount:
                raise KeyError(incident_id)

    def mark_resolved(self, incident_id: str, report: dict) -> None:
        """Trusted isolated-test application API; never expose as an AI tool.

        FunctionalVerifier supplies the persisted report. This method validates
        its scope and outcome; it does not authenticate a HAOS collector or user.
        Real Core lab reports must also match the persisted verifier report in
        this same database. No production/live HAOS scope is accepted.
        Live resolution requires the pending live acceptance/authentication gate.
        """
        if (report.get("classification") != "Vyřešeno a ověřeno"
                or report.get("scope") not in {"offline_isolated_fixture", "actual_core_container", "actual_core_managed_reference", "actual_core_native_lighting", "provider_tool_functional_observations"}
                or report.get("incident_id") != incident_id):
            raise ValueError("Only a matching verified isolated-test report can resolve this case")
        serialized = canonical(redact(report))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._validate_core_lab_report(db, report, {"verified"})
            if not db.execute("UPDATE incidents SET status='resolved',archived_at=NULL WHERE id=?", (incident_id,)).rowcount:
                raise KeyError(incident_id)
            db.execute("INSERT INTO case_records(incident_id,kind,recorded_at,content) VALUES(?, 'verified_resolution',?,?)",
                       (incident_id,time.time(),serialized))

    @staticmethod
    def _validate_core_lab_report(db, report, statuses):
        if report.get('scope') not in {'actual_core_container','actual_core_managed_reference','actual_core_native_lighting','provider_tool_functional_observations'}:
            return
        try:
            row = db.execute('''SELECT r.document,e.status,p.document FROM repair_reports r
                JOIN repair_executions e ON e.id=r.execution_id
                JOIN repair_plans p ON p.id=e.plan_id
                WHERE r.execution_id=? AND r.document=? ORDER BY r.id DESC LIMIT 1''',
                (report.get('execution_id'), canonical(redact(report)))).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is None or row[1] not in statuses:
            raise ValueError('Real Core report must match a persisted functional verification')
        plan = json.loads(row[2])
        if plan.get('incident_id') != report.get('incident_id') or plan.get('operation') not in ({'tool.approved'} if report.get('scope')=='provider_tool_functional_observations' else {'core.enable_lighting_automation'} if report.get('scope')=='actual_core_native_lighting' else {'core_managed.replace_entity_reference','core.enable_lighting_automation'} if report.get('scope')=='actual_core_managed_reference' else {'core_lab.replace_entity_reference'}):
            raise ValueError('Report belongs to another case or operation')

    def reopen_for_report(self, incident_id: str, report: dict) -> None:
        """Trusted offline recurrence transition; dedup repeated verification."""
        if (report.get("classification") not in {"Oprava selhala", "Problém se opakoval"}
                or report.get("scope") not in {"offline_isolated_fixture", "actual_core_container", "actual_core_managed_reference", "actual_core_native_lighting", "provider_tool_functional_observations"}
                or report.get("incident_id") != incident_id or not report.get("execution_id")):
            raise ValueError("Only a matching failed offline report can reopen this case")
        failures = [item for item in report.get("evidence", []) if item.get("kind") == "functional_failure"]
        if not failures:
            raise ValueError("Recurrence requires functional failure evidence")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._validate_core_lab_report(db, report, {"failed", "recurred"})
            previous = db.execute("SELECT status FROM incidents WHERE id=?", (incident_id,)).fetchone()
            if previous is None:
                raise KeyError(incident_id)
            inserted = 0
            for item in failures:
                stamp = item["observed_at"]
                if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
                    raise ValueError("Recurrence timestamp must be finite")
                event_id = digest([report["execution_id"], redact(item)])
                inserted += db.execute("INSERT OR IGNORE INTO occurrences VALUES(?,?,?)", (incident_id,event_id,stamp)).rowcount
                db.execute("UPDATE incidents SET first_seen=min(first_seen,?),last_seen=max(last_seen,?) WHERE id=?",
                           (stamp,stamp,incident_id))
            db.execute("UPDATE incidents SET status='open',archived_at=NULL WHERE id=?", (incident_id,))
            if inserted or previous[0] != "open":
                db.execute("INSERT INTO case_records(incident_id,kind,recorded_at,content) VALUES(?, 'reopened_after_repair',?,?)",
                           (incident_id,time.time(),canonical(redact(report))))

    def export(self, incident_id: str) -> str:
        return canonical(self.case(incident_id))

    def prune(self, *, archived_before: float, limit: int = 100) -> int:
        """Retention never deletes active cases. Caller must export beforehand."""
        if not 1 <= limit <= 1000:
            raise ValueError("Retention batch must be between 1 and 1000")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ids = [r[0] for r in db.execute("SELECT id FROM incidents WHERE status='archived' AND archived_at<? ORDER BY archived_at LIMIT ?", (archived_before,limit))]
            for incident_id in ids:
                db.execute("DELETE FROM incidents WHERE id=?", (incident_id,))
            db.execute("DELETE FROM evidence WHERE NOT EXISTS(SELECT 1 FROM incident_evidence l WHERE l.evidence_id=evidence.id)")
            return len(ids)
