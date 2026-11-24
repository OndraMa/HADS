"""A deliberately narrow, local-only repair executor.

This module is NOT a Home Assistant writer or an HAOS approval identity adapter.
The approval authority belongs in a trusted user process, never an AI tool set.
The target is a private fixture directory controlled by this process, not /config.
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from typing import Callable


class RepairBlocked(ValueError):
    """A precondition, identity or authorization failed; nothing may be written."""


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


@dataclass(frozen=True)
class RepairPlan:
    """Immutable serialized plan. document always returns a defensive copy."""
    serialized: str

    @property
    def plan_id(self):
        return digest(self.serialized)

    @property
    def document(self):
        return json.loads(self.serialized)


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    plan_id: str
    status: str
    started_at: float
    completed_at: float | None


def connect(db_path):
    conn = sqlite3.connect(db_path, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS repair_schema(version INTEGER NOT NULL);
      INSERT INTO repair_schema SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM repair_schema);
      CREATE TABLE IF NOT EXISTS repair_plans(
        id TEXT PRIMARY KEY, document TEXT NOT NULL, snapshot BLOB NOT NULL,
        created_at REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS repair_decisions(
        token_hash TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES repair_plans(id),
        principal TEXT NOT NULL, decision TEXT NOT NULL, expires_at REAL NOT NULL,
        consumed_at REAL);
      CREATE TABLE IF NOT EXISTS repair_executions(
        id TEXT PRIMARY KEY, plan_id TEXT UNIQUE NOT NULL REFERENCES repair_plans(id),
        status TEXT NOT NULL, started_at REAL NOT NULL, completed_at REAL,
        error TEXT);
      CREATE TABLE IF NOT EXISTS repair_reports(
        id INTEGER PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES repair_executions(id),
        created_at REAL NOT NULL, classification TEXT NOT NULL, document TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS repair_observations(
        execution_id TEXT NOT NULL REFERENCES repair_executions(id),
        fingerprint TEXT NOT NULL, document TEXT NOT NULL,
        PRIMARY KEY(execution_id,fingerprint));
    """)
    if conn.execute("SELECT version FROM repair_schema").fetchone()[0] != 1:
        conn.close()
        raise RepairBlocked("Nepodporovaná verze schématu oprav.")
    return conn


class ApprovalAuthority:
    """Trusted local-user boundary; do not expose this object to the investigator.

    principal must come from an authenticated caller in a future HAOS adapter.
    Here an OS-local operator owns the fixture and is the only authority.
    Tokens have 256 bits of entropy; only hashes are persisted.
    """
    def __init__(self, db_path, *, owner="owner", clock: Callable = time.time):
        self.db_path, self.owner, self.clock = db_path, owner, clock
        connect(db_path).close()

    def decide(self, plan: RepairPlan, *, principal: str, decision: str, ttl=300) -> str:
        if principal != self.owner:
            raise RepairBlocked("Schválení smí vydat pouze určený uživatel.")
        if decision not in {"approve", "reject", "manual"}:
            raise RepairBlocked("Neznámé rozhodnutí.")
        if not isinstance(ttl, (float, int)) or not math.isfinite(ttl) or not 0 < ttl <= 900:
            raise RepairBlocked("Neplatná doba schválení.")
        token = secrets.token_urlsafe(32)
        conn = connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT document FROM repair_plans WHERE id=?", (plan.plan_id,)).fetchone()
            if row is None or row[0] != plan.serialized:
                raise RepairBlocked("Tato přesná verze plánu není registrována.")
            # Every new user decision invalidates outstanding approvals of this plan.
            conn.execute("UPDATE repair_decisions SET consumed_at=? WHERE plan_id=? AND consumed_at IS NULL",
                         (self.clock(), plan.plan_id))
            conn.execute("INSERT INTO repair_decisions VALUES(?,?,?,?,?,NULL)",
                         (digest(token), plan.plan_id, principal, decision, self.clock() + ttl))
            conn.execute("COMMIT")
            return token
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def approve(self, plan: RepairPlan, *, principal: str, ttl=300) -> str:
        return self.decide(plan, principal=principal, decision="approve", ttl=ttl)


class RepairEngine:
    """No network, shell, service invocation or arbitrary-path repair capability."""
    # The installed catalog remains fixture-only. A separate, non-installed
    # real-Core laboratory specializes these hooks while reusing the exact
    # durable approval/intent/replay boundary below.
    _operation = "fixture.replace_entity_reference"
    _risk = "low_isolated_fixture_only"
    _snapshot_scope = "single_fixture_not_HAOS"
    _preconditions = ("exact_original_sha256", "private_fixture_directory", "unexpired_owner_approval")

    def __init__(self, db_path, isolated_root, *, allowed_files, owner="owner", clock: Callable = time.time):
        root = Path(isolated_root).absolute()
        # A protected directory prevents another user from replacing files between checks.
        if root.resolve() != root or not root.is_dir():
            raise RepairBlocked("Kořen oprav musí být skutečný izolovaný adresář bez symlinků.")
        info = root.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise RepairBlocked("Testovací adresář musí vlastnit proces a mít práva 0700.")
        if str(root) in {"/", "/config", "/workspace"}:
            raise RepairBlocked("Produkční ani obecný kořen nelze použít jako fixture.")
        self.root = root
        self.allowed_files = frozenset(allowed_files)
        if not self.allowed_files or any(not re.fullmatch(r"[a-zA-Z0-9_-]+\.json", name) for name in self.allowed_files):
            raise RepairBlocked("Povoleny jsou jen explicitně vyjmenované JSON fixtures.")
        self.db_path, self.owner, self.clock = db_path, owner, clock
        connect(db_path).close()

    def _read(self, filename):
        if filename not in self.allowed_files:
            raise RepairBlocked("Cíl není na seznamu testovacích souborů.")
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
                    raise RepairBlocked("Cíl musí být malý samostatný běžný soubor.")
                return os.read(fd, 65537)
            finally:
                os.close(fd)
        except OSError as error:
            raise RepairBlocked("Testovací cíl nelze bezpečně přečíst.") from error
        finally:
            os.close(directory)

    @staticmethod
    def _entity(document):
        try:
            entity = document["action"]["target"]["entity_id"]
            if not isinstance(document["id"], str) or not isinstance(document["action"]["service"], str):
                raise KeyError("invalid fixture")
            if not isinstance(entity, str):
                raise KeyError("scalar entity required")
            return entity
        except (KeyError, TypeError) as error:
            raise RepairBlocked("Fixture nemá podporovaný tvar automatizace.") from error

    @staticmethod
    def _change_entity(document, new_entity_id):
        changed = json.loads(canonical(document))
        changed["action"]["target"]["entity_id"] = new_entity_id
        return changed

    def _manual_alternative(self, filename, expected_old, new_entity_id):
        return f"V izolovaném souboru {filename} změň pouze action.target.entity_id " \
               f"z {expected_old} na {new_entity_id}; potom proveď funkční test."

    def _target_metadata(self, filename, original):
        return {"root": str(self.root), "filename": filename, "automation_id": original["id"]}

    def prepare_entity_reference(self, incident_id, filename, expected_old, new_entity_id,
                                 evidence_ids, reason, *, watch_seconds=30, target_state="on",
                                 rollback_of=None) -> RepairPlan:
        if not re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z0-9_]+", new_entity_id):
            raise RepairBlocked("Neplatné nové entity_id.")
        if expected_old == new_entity_id or not reason or not evidence_ids:
            raise RepairBlocked("Plán musí obsahovat skutečnou změnu, důvod a důkazy.")
        if not isinstance(watch_seconds, (int, float)) or not math.isfinite(watch_seconds) or watch_seconds < 1:
            raise RepairBlocked("Ověření musí mít kladnou sledovací dobu.")
        raw = self._read(filename)
        try:
            original = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise RepairBlocked("Fixture není platný JSON.") from error
        if self._entity(original) != expected_old:
            raise RepairBlocked("Původní odkaz se změnil; plán je nutné připravit znovu.")
        changed = self._change_entity(original, new_entity_id)
        document = {
            "schema": 1, "operation": self._operation, "incident_id": incident_id,
            "target": self._target_metadata(filename, original),
            "original": original, "proposed": changed, "original_sha256": digest(raw),
            "reason": reason, "evidence_ids": sorted(set(evidence_ids)), "risk": self._risk,
            "backup": {"required": "verified_local_snapshot", "scope": self._snapshot_scope,
                       "onedrive_required": False},
            "preconditions": list(self._preconditions),
            "expected_result": f"Automatizace {original['id']} po spuštění nastaví {new_entity_id} na {target_state}.",
            "verification": {"automation_id": original["id"], "entity_id": new_entity_id,
                             "state": target_state, "watch_seconds": watch_seconds},
            "rollback": {"supported": True, "separate_approval_required": True,
                         "scope": self._snapshot_scope, "rollback_of": rollback_of},
            "manual_alternative": self._manual_alternative(filename, expected_old, new_entity_id),
        }
        return self._register_plan(document,raw)

    def _register_plan(self, document, raw):
        plan = RepairPlan(canonical(document))
        conn = connect(self.db_path)
        try:
            conn.execute("INSERT OR IGNORE INTO repair_plans VALUES(?,?,?,?)",
                         (plan.plan_id, plan.serialized, raw, self.clock()))
            stored = conn.execute("SELECT snapshot FROM repair_plans WHERE id=?", (plan.plan_id,)).fetchone()[0]
            if digest(stored) != document["original_sha256"]:
                raise RepairBlocked("Lokální zálohu se nepodařilo nezávisle přečíst.")
        finally:
            conn.close()
        return plan

    def _validate_plan(self, plan, row):
        if row is None or row["document"] != plan.serialized:
            raise RepairBlocked("Plán nebyl připraven tímto katalogem nebo byl pozměněn.")
        document = plan.document
        if document["operation"] != self._operation or document["target"]["root"] != str(self.root):
            raise RepairBlocked("Operace nebo kořen nemá oprávnění.")
        if document["backup"]["onedrive_required"] or document["risk"] != self._risk:
            raise RepairBlocked("Rizikový zásah vyžaduje nezávisle ověřenou obnovitelnou OneDrive zálohu; není podporován.")
        if not self._valid_transition(document["original"],document["proposed"]) or digest(row["snapshot"]) != document["original_sha256"]:
            raise RepairBlocked("Plán obsahuje změny mimo jediný podporovaný odkaz nebo neplatnou zálohu.")
        return document

    def _readback_matches(self,proposed,current):
        return current==proposed

    def _valid_transition(self,original,proposed):
        return self._change_entity(original,self._entity(proposed))==proposed

    def execute(self, plan: RepairPlan, token: str, *, principal: str, after_intent=None) -> ExecutionResult:
        # Keep a process-safe filesystem lock through preflight, intent and readback.
        # SQLite's intent commit alone does not serialize two distinct approved
        # plans for the same original file. flock is released by the OS on crash.
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fd = os.open(".repair.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_nlink != 1:
                    raise RepairBlocked("Zámek izolovaného vykonávání není bezpečný.")
                fcntl.flock(fd, fcntl.LOCK_EX)
                return self._execute_locked(plan, token, principal=principal, after_intent=after_intent)
            finally:
                os.close(fd)
        finally:
            os.close(directory)

    def _execute_locked(self, plan: RepairPlan, token: str, *, principal: str, after_intent=None) -> ExecutionResult:
        if principal != self.owner or not isinstance(token, str):
            raise RepairBlocked("Chybí oprávnění určeného uživatele.")
        conn = connect(self.db_path)
        now, execution_id = self.clock(), secrets.token_hex(16)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM repair_plans WHERE id=?", (plan.plan_id,)).fetchone()
            document = self._validate_plan(plan, row)
            approval = conn.execute("SELECT * FROM repair_decisions WHERE token_hash=?", (digest(token),)).fetchone()
            if approval is None or approval["plan_id"] != plan.plan_id or approval["principal"] != principal \
                    or approval["decision"] != "approve" or approval["expires_at"] <= now or approval["consumed_at"] is not None:
                raise RepairBlocked("Schválení chybí, vypršelo, bylo zamítnuto nebo už bylo použito.")
            if digest(self._read(document["target"]["filename"])) != document["original_sha256"]:
                raise RepairBlocked("Cíl se po přípravě změnil; je třeba nový plán a schválení.")
            if conn.execute("SELECT 1 FROM repair_executions WHERE plan_id=?", (plan.plan_id,)).fetchone():
                raise RepairBlocked("Tento plán již byl zahájen. Po restartu se automaticky neopakuje.")
            ambiguous = conn.execute("SELECT p.document FROM repair_executions e JOIN repair_plans p ON p.id=e.plan_id "
                                     "WHERE e.status IN ('intent_recorded','blocked_requires_review')").fetchall()
            if any(all(json.loads(item[0])["target"][key] == document["target"][key]
                       for key in ("root", "filename")) for item in ambiguous):
                raise RepairBlocked("Dřívější zásah tohoto cíle má neznámý výsledek; další změny čekají na ruční kontrolu.")
            conn.execute("UPDATE repair_decisions SET consumed_at=? WHERE token_hash=?", (now, digest(token)))
            conn.execute("INSERT INTO repair_executions VALUES(?,?,?, ?,NULL,NULL)",
                         (execution_id, plan.plan_id, "intent_recorded", now))
            conn.execute("COMMIT")
            # This hook permits process-crash fault injection in isolated tests only.
            if after_intent:
                after_intent()
            self._replace(document["target"]["filename"], canonical(document["proposed"]).encode())
            if not self._readback_matches(document["proposed"],json.loads(self._read(document["target"]["filename"]))):
                raise RepairBlocked("Zápis nesplnil kontrolu přesného obsahu.")
            done = self.clock()
            conn.execute("UPDATE repair_executions SET status='applied_verification_pending',completed_at=? WHERE id=?",
                         (done, execution_id))
            return ExecutionResult(execution_id, plan.plan_id, "applied_verification_pending", now, done)
        except BaseException as error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            # Intent stays durably unknown after a crash; never replay it.
            if isinstance(error, Exception):
                conn.execute("UPDATE repair_executions SET status='blocked_requires_review',error=? WHERE id=?",
                             (type(error).__name__, execution_id))
            raise
        finally:
            conn.close()

    def _replace(self, filename, content):
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        name = ".repair-" + secrets.token_hex(16)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, filename, src_dir_fd=directory, dst_dir_fd=directory)
                os.fsync(directory)
            finally:
                try:
                    os.unlink(name, dir_fd=directory)
                except FileNotFoundError:
                    pass
        finally:
            os.close(directory)

    def prepare_rollback(self, plan: RepairPlan, evidence_ids, *, reason="Návrat neúspěšné lokální opravy"):
        # A rollback is a new immutable plan and requires an entirely new approval.
        document = plan.document
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM repair_plans WHERE id=?", (plan.plan_id,)).fetchone()
            self._validate_plan(plan, row)
            execution = conn.execute("SELECT status FROM repair_executions WHERE plan_id=?", (plan.plan_id,)).fetchone()
            if execution is None:
                raise RepairBlocked("Plán nebyl proveden; rollback není připraven.")
        finally:
            conn.close()
        return self.prepare_entity_reference(document["incident_id"], document["target"]["filename"],
            self._entity(document["proposed"]), self._entity(document["original"]), evidence_ids, reason,
            watch_seconds=document["verification"]["watch_seconds"], rollback_of=plan.plan_id)

    def execution(self, plan_id):
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM repair_executions WHERE plan_id=?", (plan_id,)).fetchone()
            if row is None:
                return None
            return ExecutionResult(row["id"], plan_id, row["status"], row["started_at"], row["completed_at"])
        finally:
            conn.close()
