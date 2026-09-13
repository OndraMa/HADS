from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable
from repair_engine import executable_actions


FIRST_OFFICER_SCHEMA = """
CREATE TABLE IF NOT EXISTS root_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    root_cause TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'home_assistant',
    priority TEXT NOT NULL DEFAULT 'P3',
    impact_score INTEGER NOT NULL DEFAULT 0,
    potential_health_gain INTEGER NOT NULL DEFAULT 0,
    estimated_effort TEXT NOT NULL DEFAULT 'unknown',
    confidence INTEGER NOT NULL DEFAULT 0,
    lifecycle TEXT NOT NULL DEFAULT 'ACTIVE',
    temporal_state TEXT NOT NULL DEFAULT 'persistent',
    decision_state TEXT NOT NULL DEFAULT 'awaiting_decision',
    decision_reason TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    symptoms_json TEXT NOT NULL DEFAULT '[]',
    dependencies_json TEXT NOT NULL DEFAULT '{}',
    recommendation TEXT NOT NULL DEFAULT '',
    planner_state TEXT NOT NULL DEFAULT 'not_started',
    planner_kind TEXT NOT NULL DEFAULT '',
    research_json TEXT NOT NULL DEFAULT '{}',
    repair_plan_id INTEGER REFERENCES repair_plans(id) ON DELETE SET NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_root_cases_queue ON root_cases(lifecycle,decision_state,priority,impact_score DESC);
CREATE TABLE IF NOT EXISTS root_case_members (
    root_case_id INTEGER NOT NULL REFERENCES root_cases(id) ON DELETE CASCADE,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'symptom',
    confidence INTEGER NOT NULL DEFAULT 50,
    PRIMARY KEY(root_case_id,case_id)
);
CREATE TABLE IF NOT EXISTS captain_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_case_id INTEGER NOT NULL REFERENCES root_cases(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT 'Kapitán',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repair_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'preparing_rescue',
    plan_ids_json TEXT NOT NULL DEFAULT '[]',
    rescue_path TEXT,
    rescue_sha256 TEXT,
    rescue_destination TEXT,
    rescue_verified_at TEXT,
    rw_opened_at TEXT,
    rw_closed_at TEXT,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    results_json TEXT NOT NULL DEFAULT '[]',
    batch_plan_json TEXT NOT NULL DEFAULT '{}',
    conflicts_json TEXT NOT NULL DEFAULT '[]',
    remote_verification_json TEXT NOT NULL DEFAULT '{}',
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measured_at TEXT NOT NULL,
    current_health INTEGER NOT NULL,
    reliability INTEGER NOT NULL,
    coverage INTEGER NOT NULL,
    hads_health INTEGER NOT NULL,
    root_active INTEGER NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_health_snapshots_time ON health_snapshots(measured_at DESC);
CREATE TABLE IF NOT EXISTS planner_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_case_id INTEGER NOT NULL REFERENCES root_cases(id) ON DELETE CASCADE,
    case_id INTEGER,
    status TEXT NOT NULL DEFAULT 'running',
    adapter_ids_json TEXT NOT NULL DEFAULT '[]',
    research_json TEXT NOT NULL DEFAULT '{}',
    actions_json TEXT NOT NULL DEFAULT '[]',
    repair_plan_id INTEGER,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    finished_at TEXT
);
"""


def _json(value: Any, default: Any) -> Any:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if parsed is not None else default
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _row(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120]


class FirstOfficer:
    """Root-cause, captain-decision and rescue-gate orchestration layer."""

    def __init__(
        self,
        db: Callable[[], Any],
        options: Callable[[], dict[str, Any]],
        now: Callable[[], str],
        config_root: Callable[[], Path | None],
        supervisor_request: Callable[..., Any],
        private_root: Path,
    ) -> None:
        self.db = db
        self.options = options
        self.now = now
        self.config_root = config_root
        self.supervisor_request = supervisor_request
        self.private_root = private_root

    def init_schema(self) -> None:
        with self.db() as conn:
            conn.executescript(FIRST_OFFICER_SCHEMA)

    @staticmethod
    def _group_key(case: dict[str, Any]) -> str:
        category = str(case.get("category") or "home_assistant")
        integration = str(case.get("integration") or "").strip().lower()
        source = str(case.get("source_ref") or "").strip().lower()
        logger = str(case.get("logger") or "").strip().lower()
        cause = str(case.get("probable_cause") or "").strip().lower()
        message = str(case.get("normalized_message") or "").strip().lower()
        title = str(case.get("title") or "").strip().lower()
        hay = " ".join((title, cause, message, logger, source))
        # Canonical roots must win over legacy logger/source/category wrappers.
        if (("exit code 137" in hay or "exited with code 137" in hay or "sigkill" in hay)) and "supervisor.homeassistant.core" in hay:
            return "root:homeassistant_core:sigkill137"
        if "mqtt_not_setup_cannot_publish" in hay and "meross" in hay:
            return "root:meross_lan:mqtt_not_setup_cannot_publish"
        if "error loading provider(instance) hass: 502" in hay and "supervisor/core/api/websocket" in hay:
            return "root:music_assistant:ha_websocket_502"
        if "notimplementederror" in hay and "media_stop" in hay and "media_player" in hay:
            if logger.startswith("homeassistant.components.script."):
                return f"root:{logger}:media_stop_not_implemented"
            return "root:media_player:media_stop_not_implemented"
        if category == "configuration" and source:
            return f"configuration:{source.rsplit(':', 1)[0] if source.rsplit(':', 1)[-1].isdigit() else source}"
        if integration:
            # One integration can have several unrelated failures. Keep the
            # explicit cross-log canonical roots above, otherwise include the
            # normalized cause instead of collapsing the whole integration.
            return f"integration:{integration}:{_slug(cause or message or title)[:72]}"
        if source.startswith(("sensor.", "binary_sensor.", "switch.", "light.", "device_tracker.", "automation.", "script.")):
            return "entity:" + source.split(".", 1)[0] + ":" + _slug(cause or message)[:48]
        logger_root = ".".join(part for part in logger.split(".")[:2] if part)
        semantic = _slug(cause or message)[:64]
        return f"{category}:{logger_root}:{semantic}"

    @staticmethod
    def _temporal_state(group: list[dict[str, Any]], now_value: dt.datetime, grace_minutes: int) -> str:
        first = min(dt.datetime.fromisoformat(str(item["first_seen"])) for item in group)
        distinct = max(int(item.get("distinct_days_30d") or 0) for item in group)
        span = max(int(item.get("active_span_days") or 0) for item in group)
        recurrence = [_json(item.get("recurrence_json"), {}) for item in group]
        total_30d = sum(int(item.get("count_30d") or 0) for item in recurrence)
        transient_count = sum(
            round(int(item.get("count_30d") or 0) * float(item.get("transient_ratio") or 0))
            for item in recurrence
        )
        if (now_value - first).total_seconds() < grace_minutes * 60:
            return "grace"
        # A single event tied to boot/restart/update is evidence to watch, not a
        # persistent incident. Escalation begins only after it returns outside
        # the maintenance context or on another day.
        if distinct <= 1 and total_30d <= 1 and transient_count >= total_30d:
            return "transient"
        if distinct >= 7 or span >= 14:
            return "chronic"
        if distinct <= 1 and span <= 1:
            return "transient"
        return "persistent"

    def rebuild_root_cases(self) -> dict[str, int]:
        """Condense symptoms into stable canonical root cases."""
        with self.db() as conn:
            cases = [_row(row) for row in conn.execute(
                """SELECT * FROM cases WHERE status NOT IN ('resolved','ignored')
                   AND category NOT IN ('hads_internal','diagnostic_coverage') ORDER BY priority,last_seen DESC"""
            ).fetchall()]
            plan_rows = conn.execute(
                """SELECT id,case_id,status,actions_json FROM repair_plans WHERE case_id IS NOT NULL AND status IN ('approved','pending_approval','monitoring','running','failed','interrupted')
                   ORDER BY CASE status WHEN 'approved' THEN 0 WHEN 'pending_approval' THEN 1 ELSE 2 END,id DESC"""
            ).fetchall()
            plan_by_case: dict[int, tuple[int, str]] = {}
            for plan in plan_rows:
                # Historical RC3/RC4 pseudo-plans containing only core_check are
                # diagnostic preflights, not repairs. They must never expose a
                # captain Approve button or contribute to the repair batch.
                actions = _json(plan["actions_json"], [])
                if not executable_actions(actions):
                    continue
                plan_by_case.setdefault(int(plan["case_id"]), (int(plan["id"]), str(plan["status"])))

            groups: dict[str, list[dict[str, Any]]] = {}
            for case in cases:
                groups.setdefault(self._group_key(case), []).append(case)

            seen: set[str] = set()
            created = updated = symptoms = 0
            grace = max(1, int(self.options().get("first_officer_grace_minutes", 15)))
            now_dt = dt.datetime.fromisoformat(self.now())
            for key, group in groups.items():
                fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()
                seen.add(fingerprint)
                lead = max(group, key=lambda item: (int(item.get("confidence") or 0), int(item.get("impact_score") or 0)))
                root_cause = str(lead.get("probable_cause") or lead.get("title") or "Příčina se dále vyšetřuje.")
                title = str(lead.get("title") or root_cause)[:500]
                impact = max(int(item.get("impact_score") or 0) for item in group)
                confidence = max(int(item.get("confidence") or 0) for item in group)
                priority = min((str(item.get("priority") or "P4") for item in group), key=lambda p: {"P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(p, 9))
                temporal = self._temporal_state(group, now_dt, grace)
                symptom_values = [{
                    "case_id": int(item["id"]), "title": item["title"], "source": item.get("source_ref") or item.get("logger"),
                    "occurrences": int(item.get("occurrence_count") or 0), "last_seen": item["last_seen"],
                } for item in group]
                diagnostic_sources = sorted({str(item.get("integration") or item.get("logger") or "HADS") for item in group})
                evidence = []
                for item in group[:12]:
                    evidence.append({"case_id": int(item["id"]), "sample": str(item.get("sample") or "")[:1200], "state": item.get("evidence_state") or "unverified"})
                repair_candidates = [plan_by_case[int(item["id"])] for item in group if int(item["id"]) in plan_by_case]
                repair_candidates.sort(key=lambda item: {"approved": 0, "pending_approval": 1, "monitoring": 2}.get(item[1], 9))
                repair_plan_id = repair_candidates[0][0] if repair_candidates else None
                plan_status = repair_candidates[0][1] if repair_candidates else ""
                lifecycle = "VERIFY" if plan_status in {"monitoring", "running"} else "ACTIVE"
                # No repair plan means First Officer keeps investigating. It is NOT
                # a captain question. Captain attention is reserved for a prepared
                # decision, genuinely user-only information or a manual intervention.
                age_hours = max(0.0, (now_dt - dt.datetime.fromisoformat(max(str(item["last_seen"]) for item in group))).total_seconds() / 3600.0)
                # Age is not a completed diagnosis or an observation contract.
                background_state = "investigating"
                decision = "verifying" if lifecycle == "VERIFY" else ("approved" if plan_status == "approved" else ("awaiting_decision" if repair_plan_id else background_state))
                if plan_status in {"failed", "interrupted"}:
                    decision = "repair_failed"
                recommendation = str(lead.get("solution") or "HADS bude případ dál sledovat a doplní návrh až s dostatečnými důkazy.")
                health_gain = 0
                effort = "low" if repair_plan_id and impact < 70 else ("medium" if repair_plan_id else "investigation")
                first_seen = min(str(item["first_seen"]) for item in group)
                last_seen = max(str(item["last_seen"]) for item in group)
                existing = conn.execute("SELECT id,decision_state,decision_reason,planner_state,planner_kind,research_json FROM root_cases WHERE fingerprint=?", (fingerprint,)).fetchone()
                preserved_decision = decision
                preserved_reason = ""
                if existing:
                    existing_state = str(existing["decision_state"] or "")
                    if existing_state == "resolved":
                        last_choice = conn.execute("SELECT decision FROM captain_decisions WHERE root_case_id=? ORDER BY id DESC LIMIT 1", (existing["id"],)).fetchone()
                        if last_choice and last_choice["decision"] == "ignore":
                            existing_state = "ignored"
                    # Reject/manual-derived states were always explicit captain choices.
                    latest_choice = conn.execute("SELECT decision FROM captain_decisions WHERE root_case_id=? ORDER BY id DESC LIMIT 1", (existing["id"],)).fetchone()
                    explicit_watch = existing_state == "watching" and latest_choice and latest_choice["decision"] == "accept_analysis"
                    if existing_state in {"rejected", "known_expected", "deferred", "manual_monitoring", "reinvestigate", "review_ready", "ignored"} or explicit_watch:
                        preserved_decision = existing_state
                        preserved_reason = str(existing["decision_reason"] or "")
                    elif existing_state == "needs_information":
                        # RC3-RC6 also used needs_information as an automatic default,
                        # which created the 100+ fake captain tasks. Preserve it only
                        # when the captain actually clicked Potřebuji vysvětlení.
                        captain_need_info = conn.execute(
                            "SELECT 1 FROM captain_decisions WHERE root_case_id=? AND decision='need_info' ORDER BY id DESC LIMIT 1",
                            (int(existing["id"]),),
                        ).fetchone()
                        if captain_need_info:
                            preserved_decision = "needs_information"
                            preserved_reason = str(existing["decision_reason"] or "")
                planner_state = str(existing["planner_state"] or "not_started") if existing else ("ready" if repair_plan_id else "not_started")
                planner_kind = str(existing["planner_kind"] or "") if existing else ""
                research_json = str(existing["research_json"] or "{}") if existing else "{}"
                payload = (
                    title, root_cause, str(lead.get("category") or "home_assistant"), priority, impact, health_gain,
                    effort, confidence, lifecycle, temporal, preserved_decision, preserved_reason,
                    json.dumps(evidence, ensure_ascii=False), json.dumps(symptom_values, ensure_ascii=False),
                    json.dumps({"group_key": key, "member_count": len(group), "sources": diagnostic_sources}, ensure_ascii=False), recommendation,
                    planner_state, planner_kind, research_json, repair_plan_id, first_seen, last_seen, self.now(),
                )
                if existing:
                    root_id = int(existing["id"])
                    conn.execute(
                        """UPDATE root_cases SET title=?,root_cause=?,category=?,priority=?,impact_score=?,potential_health_gain=?,
                           estimated_effort=?,confidence=?,lifecycle=?,temporal_state=?,decision_state=?,decision_reason=?,evidence_json=?,
                           symptoms_json=?,dependencies_json=?,recommendation=?,planner_state=?,planner_kind=?,research_json=?,repair_plan_id=?,first_seen=?,last_seen=?,updated_at=?,resolved_at=NULL
                           WHERE id=?""", payload + (root_id,),
                    )
                    updated += 1
                else:
                    cursor = conn.execute(
                        """INSERT INTO root_cases(fingerprint,title,root_cause,category,priority,impact_score,potential_health_gain,
                           estimated_effort,confidence,lifecycle,temporal_state,decision_state,decision_reason,evidence_json,symptoms_json,
                           dependencies_json,recommendation,planner_state,planner_kind,research_json,repair_plan_id,first_seen,last_seen,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (fingerprint,) + payload[:-1] + (self.now(), self.now()),
                    )
                    root_id = int(cursor.lastrowid)
                    created += 1
                conn.execute("DELETE FROM root_case_members WHERE root_case_id=?", (root_id,))
                for item in group:
                    conn.execute(
                        "INSERT INTO root_case_members(root_case_id,case_id,relation,confidence) VALUES(?,?,?,?)",
                        (root_id, int(item["id"]), "symptom" if int(item["id"]) != int(lead["id"]) else "primary", int(item.get("confidence") or 50)),
                    )
                    symptoms += 1
            if seen:
                marks = ",".join("?" for _ in seen)
                conn.execute(
                    f"UPDATE root_cases SET lifecycle='RESOLVED',decision_state='resolved',resolved_at=?,updated_at=? WHERE fingerprint NOT IN ({marks}) AND lifecycle!='RESOLVED'",
                    (self.now(), self.now(), *seen),
                )
            else:
                conn.execute("UPDATE root_cases SET lifecycle='RESOLVED',decision_state='resolved',resolved_at=?,updated_at=? WHERE lifecycle!='RESOLVED'", (self.now(), self.now()))
        return {"created": created, "updated": updated, "root_cases": len(groups), "symptoms": symptoms}

    def root_case(self, root_id: int) -> dict[str, Any] | None:
        with self.db() as conn:
            row = conn.execute("SELECT * FROM root_cases WHERE id=?", (root_id,)).fetchone()
            if not row:
                return None
            value = self._serialize_root(_row(row))
            value["members"] = [_row(item) for item in conn.execute(
                """SELECT c.*,m.relation,m.confidence membership_confidence FROM root_case_members m
                   JOIN cases c ON c.id=m.case_id WHERE m.root_case_id=? ORDER BY m.relation,c.last_seen DESC""", (root_id,)
            ).fetchall()]
            value["decisions"] = [_row(item) for item in conn.execute(
                "SELECT * FROM captain_decisions WHERE root_case_id=? ORDER BY id DESC", (root_id,)
            ).fetchall()]
            if value.get("decision_state") == "watching":
                value["state_origin"] = "captain" if value["decisions"] and value["decisions"][0]["decision"] == "accept_analysis" else "automatic"
            return value

    @staticmethod
    def _serialize_root(value: dict[str, Any]) -> dict[str, Any]:
        last_decision = value.pop("_captain_decision", None)
        captain_decision = bool(last_decision)
        value["public_id"] = f"R-{int(value['id']):03d}"
        value["evidence"] = _json(value.pop("evidence_json", "[]"), [])
        value["symptoms"] = _json(value.pop("symptoms_json", "[]"), [])
        value["dependencies"] = _json(value.pop("dependencies_json", "{}"), {})
        value["research"] = _json(value.pop("research_json", "{}"), {})
        value["repair_prepared"] = bool(value.get("repair_plan_id"))
        # The evidence lifecycle also uses "watching" automatically after a
        # case becomes stale. It is not a captain decision unless one is stored.
        value["state_origin"] = "captain" if captain_decision else "hads"
        if value.get("decision_state") == "watching" and last_decision != "accept_analysis":
            value["state_origin"] = "automatic"
        return value

    def list_roots(self, include_resolved: bool = False) -> list[dict[str, Any]]:
        where = "1=1" if include_resolved else "lifecycle!='RESOLVED'"
        with self.db() as conn:
            rows = conn.execute(
                f"""SELECT root_cases.*,
                           (SELECT decision FROM captain_decisions cd WHERE cd.root_case_id=root_cases.id ORDER BY cd.id DESC LIMIT 1) AS _captain_decision
                    FROM root_cases WHERE {where} ORDER BY
                    CASE decision_state WHEN 'awaiting_decision' THEN 0 WHEN 'review_ready' THEN 1 WHEN 'needs_information' THEN 2 WHEN 'approved' THEN 3 ELSE 4 END,
                    CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,impact_score DESC,last_seen DESC"""
            ).fetchall()
        return [self._serialize_root(_row(row)) for row in rows]

    def decide(self, root_id: int, decision: str, reason: str = "") -> dict[str, Any]:
        # Be deliberately tolerant across First Officer UI revisions. RC3-RC5
        # used both action names (approve/manual/need_info) and state names
        # (approved/manual_monitoring/needs_information). A stale Ingress tab
        # must not turn a valid captain click into "Neplatné rozhodnutí".
        raw_decision = str(decision or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "approve": "approve", "approved": "approve", "schvaluji": "approve", "schválit": "approve", "schvalit": "approve",
            "reject": "reject", "rejected": "reject", "zamitam": "reject", "zamítám": "reject", "zamitnout": "reject", "zamítnout": "reject",
            "need_info": "need_info", "needs_information": "need_info", "need_information": "need_info", "explain": "need_info", "explanation": "need_info",
            "manual": "manual", "manual_monitoring": "manual", "manual_intervention": "manual", "manual_action": "manual",
            "accept_analysis": "accept_analysis", "accept_review": "accept_analysis", "acknowledge": "accept_analysis", "accepted": "accept_analysis",
            "ignore": "ignore", "reinvestigate": "reinvestigate",
        }
        decision = aliases.get(raw_decision, "")
        if not decision:
            raise ValueError(f"Neplatné kapitánské rozhodnutí: {raw_decision or 'prázdné'}. Obnovte panel HADS; podporováno je Schvaluji / Zamítám / Potřebuji vysvětlení / Ruční zásah.")
        root = self.root_case(root_id)
        if not root:
            raise ValueError("Root-case nebyl nalezen.")
        reason = str(reason or "").strip()[:2000]
        states = {"approve": "approved", "reject": "rejected", "need_info": "needs_information", "manual": "manual_monitoring", "accept_analysis": "watching", "ignore": "ignored", "reinvestigate": "reinvestigate"}
        state = states[decision]
        if decision in {"ignore", "reinvestigate"} and not reason:
            raise ValueError("Uveďte důvod; HADS jej zachová jako tvrzení kapitána, nikoli ověřený fakt.")
        if decision == "approve" and not root.get("repair_plan_id"):
            raise ValueError("Tento root-case zatím nemá bezpečně připravenou opravu. Zvolte vysvětlení nebo ruční zásah.")
        with self.db() as conn:
            current_root = conn.execute("SELECT decision_state,repair_plan_id FROM root_cases WHERE id=?", (root_id,)).fetchone()
            if not current_root:
                raise ValueError("Root-case už neexistuje.")
            plan_id = current_root["repair_plan_id"]
            plan_status = conn.execute("SELECT status FROM repair_plans WHERE id=?", (plan_id,)).fetchone() if plan_id else None
            if plan_status and plan_status["status"] == "running":
                raise ValueError("Oprava již běží; rozhodnutí nelze změnit uprostřed zápisu.")
            if decision == "accept_analysis" and plan_status and plan_status["status"] in {"approved", "pending_approval"}:
                raise ValueError("Toto je vykonatelná oprava, ne diagnostický závěr. Schvalte, zamítněte nebo zvolte ruční zásah.")
            if decision in {"ignore", "reinvestigate"} and plan_id:
                conn.execute("UPDATE repair_plans SET status='cancelled',approved_at=NULL,updated_at=? WHERE id=? AND status IN ('pending_approval','approved')", (self.now(), plan_id))
                conn.execute("UPDATE root_cases SET repair_plan_id=NULL WHERE id=?", (root_id,))
            if decision == "approve":
                plan = conn.execute("SELECT status,actions_json FROM repair_plans WHERE id=?", (plan_id,)).fetchone()
                if not plan or plan["status"] not in {"pending_approval", "approved"}:
                    raise ValueError("Připravený plán už nelze schválit.")
                actions = _json(plan["actions_json"], [])
                if not executable_actions(actions):
                    raise ValueError("Tento návrh je pouze diagnostický preflight a není opravou. HADS jej přesunul k došetření; není co schvalovat do repair batch.")
                first_approval = str(plan["status"]) != "approved"
                conn.execute("UPDATE repair_plans SET status='approved',approved_at=COALESCE(approved_at,?),updated_at=?,last_error='' WHERE id=?", (self.now(), self.now(), plan_id))
                if first_approval:
                    conn.execute(
                        "INSERT INTO repair_audit(plan_id,event_type,actor,details_json,created_at) VALUES(?,?,?,?,?)",
                        (plan_id, "approved", "Kapitán Ondřej", json.dumps({"workflow": "first_officer_queue", "root_case_id": root_id}, ensure_ascii=False), self.now()),
                    )
            elif decision == "reject":
                lowered = reason.lower()
                if "oček" in lowered:
                    state = "known_expected"
                elif "nechci" in lowered or "odlo" in lowered:
                    state = "deferred"
                elif "špat" in lowered or "nerozum" in lowered:
                    state = "reinvestigate"
                if plan_id:
                    conn.execute(
                        "UPDATE repair_plans SET status='cancelled',last_error=?,updated_at=? WHERE id=? AND status IN ('pending_approval','approved')",
                        ("Kapitán návrh zamítl; plán byl atomicky vyřazen z batch fronty.", self.now(), plan_id),
                    )
            elif decision == "manual" and plan_id:
                conn.execute(
                    "UPDATE repair_plans SET status='cancelled',last_error=?,updated_at=? WHERE id=? AND status IN ('pending_approval','approved')",
                    ("Kapitán zvolil ruční zásah; HADS pouze sleduje výsledek.", self.now(), plan_id),
                )
            elif decision == "need_info" and plan_id:
                conn.execute(
                    "UPDATE repair_plans SET status='pending_approval',approved_at=NULL,updated_at=? WHERE id=? AND status='approved'",
                    (self.now(), plan_id),
                )
            conn.execute("UPDATE root_cases SET decision_state=?,decision_reason=?,updated_at=? WHERE id=?", (state, reason, self.now(), root_id))
            previous = conn.execute(
                "SELECT decision,reason FROM captain_decisions WHERE root_case_id=? ORDER BY id DESC LIMIT 1", (root_id,)
            ).fetchone()
            if not previous or str(previous["decision"]) != decision or str(previous["reason"]) != reason:
                conn.execute(
                    "INSERT INTO captain_decisions(root_case_id,decision,reason,created_at) VALUES(?,?,?,?)",
                    (root_id, decision, reason, self.now()),
                )
        return self.root_case(root_id) or {}

    @staticmethod
    def _repair_actions(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            for key in ("repair_actions", "actions", "proposed_actions"):
                candidate = value.get(key)
                if isinstance(candidate, list) and candidate and all(isinstance(item, dict) for item in candidate):
                    return candidate
        return []

    def automatic_repair_planner(
        self,
        preview: Callable[[Any], dict[str, Any]],
        create_plan: Callable[[int | None, dict[str, Any]], dict[str, Any]],
        research: Callable[[int, str, dict[str, Any]], dict[str, Any]],
        tool_bus: Any,
        limit: int = 25,
        root_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Turn Deep Analysis results into a real Repair Queue.

        A write plan is created only from structured, previewable actions. When
        evidence is insufficient, First Officer keeps investigating in the
        background; it does not create a captain task merely because no patch exists.
        """
        roots = [item for item in self.list_roots() if not item.get("repair_plan_id")
                 and item.get("decision_state") not in {"known_expected", "deferred", "manual_monitoring", "resolved", "rejected", "ignored", "review_ready"}
                 and not (item.get("decision_state") == "watching" and item.get("state_origin") == "captain")]
        if root_ids is not None:
            roots = [item for item in roots if item["id"] in root_ids]
        with self.db() as conn:
            last_runs = {int(row["root_case_id"]): _row(row) for row in conn.execute(
                "SELECT * FROM planner_runs WHERE id IN (SELECT MAX(id) FROM planner_runs GROUP BY root_case_id)"
            )}
        now_dt = dt.datetime.fromisoformat(self.now())
        due = []
        for root in roots:
            last = last_runs.get(int(root["id"]))
            if root_ids is None and last:
                try:
                    stamp = dt.datetime.fromisoformat(str(last.get("finished_at") or last["created_at"]))
                    if (now_dt - stamp).total_seconds() < 1800 and root["decision_state"] != "reinvestigate":
                        continue
                except (ValueError, TypeError):
                    pass
            due.append(root)
        # Serve never-researched, then least recently processed cases. Preserve
        # priority order within a cohort without starving the tail of the queue.
        roots = sorted(due, key=lambda root: int(last_runs.get(int(root["id"]), {}).get("id") or 0))
        eligible_count = len(roots)
        created = needs_info = failed = 0
        results: list[dict[str, Any]] = []
        for root in roots[:max(1, limit)]:
            detail = self.root_case(int(root["id"])) or {}
            members = detail.get("members") or []
            primary = next((item for item in members if item.get("relation") == "primary"), members[0] if members else None)
            if not primary:
                continue
            case_id = int(primary["id"])
            with self.db() as conn:
                run_id = int(conn.execute(
                    "INSERT INTO planner_runs(root_case_id,case_id,status,created_at) VALUES(?,?,?,?)",
                    (root["id"], case_id, "running", self.now()),
                ).lastrowid)
            try:
                adapter_result = tool_bus.collect(primary, int(root["id"]))
                question = (
                    f"Vyšetři root-case {root['public_id']}: {root['title']}. "
                    "Vrať pouze bezpečně doložené konkrétní allowlist akce; pokud chybí přesný patch, výslovně požaduj další informace."
                )
                research_result = research(case_id, question, adapter_result)
                # Providers/logs are evidence, never executable plan sources.
                # Only the trusted compiler/research boundary may return actions.
                actions = self._repair_actions(research_result)
                planner_kind = "repair"
                # A Core config check cannot repair an unknown entity/service.
                # RC3 created one such pseudo-plan for every configuration
                # finding, which looked actionable but changed nothing.
                if not actions:
                    planner_kind = "investigation"
                plan: dict[str, Any] | None = None
                if actions:
                    preview(actions)
                    plan = create_plan(case_id, {
                        "title": f"{root['public_id']} · {root['title']}",
                        "rationale": str(research_result.get("summary") or primary.get("solution") or root["root_cause"]),
                        "verification": str(primary.get("verification") or "Následná Deep Analysis bez regrese."),
                        "actions": actions,
                        "created_by": "HADS Automatic Repair Planner",
                    })
                    planner_state = "pending_approval"
                    created += 1
                else:
                    deterministic = research_result.get("deterministic_planner") if isinstance(research_result, dict) else {}
                    deterministic = deterministic if isinstance(deterministic, dict) else {}
                    choices = deterministic.get("decisions") if isinstance(deterministic.get("decisions"), list) else []
                    user_choice_needed = any(
                        isinstance(item, dict) and item.get("status") == "needs_choice"
                        for item in choices
                    )
                    if research_result.get("ai_deferred_reason"):
                        planner_state = "waiting_budget"
                        next_decision_state = "investigating"
                    elif user_choice_needed:
                        planner_state = "needs_information"
                        next_decision_state = "needs_information"
                        needs_info += 1
                    elif research_result.get("conclusion_verified") is True and research_result.get("summary"):
                        # Investigation is complete enough for a captain review,
                        # but there is no safe automatic write. This is a prepared
                        # decision, not an executable repair and not endless work.
                        planner_state = "review_ready"
                        next_decision_state = "review_ready"
                    else:
                        planner_state = "investigating"
                        next_decision_state = "investigating"
                research_payload = {"adapters": adapter_result.get("used") or [], "research": research_result, "planner_kind": planner_kind}
                with self.db() as conn:
                    # A captain can reject/ignore while network research runs.
                    current = conn.execute("SELECT decision_state,decision_reason FROM root_cases WHERE id=?", (root["id"],)).fetchone()
                    if not current or current["decision_state"] != root["decision_state"] or current["decision_reason"] != root.get("decision_reason", ""):
                        if plan:
                            conn.execute("UPDATE repair_plans SET status='cancelled',updated_at=? WHERE id=?", (self.now(), plan["id"]))
                        conn.execute("UPDATE planner_runs SET status='superseded',finished_at=? WHERE id=?", (self.now(), run_id))
                        continue
                    conn.execute(
                        "UPDATE root_cases SET planner_state=?,planner_kind=?,research_json=?,decision_state=?,repair_plan_id=?,updated_at=? WHERE id=?",
                        (planner_state, planner_kind, json.dumps(research_payload, ensure_ascii=False, default=str), "awaiting_decision" if plan else next_decision_state, plan.get("id") if plan else None, self.now(), root["id"]),
                    )
                    conn.execute(
                        "UPDATE planner_runs SET status=?,adapter_ids_json=?,research_json=?,actions_json=?,repair_plan_id=?,finished_at=? WHERE id=?",
                        ("planned" if plan else planner_state, json.dumps(adapter_result.get("used") or []), json.dumps(research_result, ensure_ascii=False, default=str), json.dumps(actions, ensure_ascii=False), plan.get("id") if plan else None, self.now(), run_id),
                    )
                results.append({"root_case_id": root["id"], "case_id": case_id, "status": planner_state, "plan_id": plan.get("id") if plan else None, "adapters": adapter_result.get("used"), "ai_deferred_reason": research_result.get("ai_deferred_reason")})
            except Exception as exc:
                failed += 1
                with self.db() as conn:
                    previous = conn.execute("SELECT research_json FROM root_cases WHERE id=?", (root["id"],)).fetchone()
                    retained = _json(previous["research_json"], {}) if previous else {}
                    retained["last_error"] = str(exc)
                    retained["last_attempt_at"] = self.now()
                    retained["retained_previous_analysis"] = True
                    conn.execute("UPDATE root_cases SET planner_state='failed',research_json=?,updated_at=? WHERE id=?", (json.dumps(retained, ensure_ascii=False), self.now(), root["id"]))
                    conn.execute("UPDATE planner_runs SET status='failed',error=?,finished_at=? WHERE id=?", (str(exc)[:5000], self.now(), run_id))
                results.append({"root_case_id": root["id"], "status": "failed", "error": str(exc)})
        return {"created": created, "needs_information": needs_info, "failed": failed, "processed": len(results),
                "ai_deferred": sum(bool(item.get("ai_deferred_reason")) for item in results),
                "eligible": eligible_count, "remaining": max(0, eligible_count - created - needs_info - sum(item.get("status") == "review_ready" for item in results)), "results": results}

    def _root_current_penalty(self, row: Any, now_dt: dt.datetime) -> int:
        """Penalty from current demonstrated impact; stale history belongs to Reliability."""
        try:
            last_seen = dt.datetime.fromisoformat(str(row["last_seen"]))
            age_hours = max(0.0, (now_dt - last_seen).total_seconds() / 3600.0)
        except Exception:
            age_hours = 9999.0
        window = max(1.0, float(self.options().get("current_health_window_hours", 24)))
        if age_hours > window:
            return 0
        # Fresh events matter most. Older-but-still-within-window evidence decays.
        freshness = 1.0 if age_hours <= 1 else (0.75 if age_hours <= 3 else (0.45 if age_hours <= 8 else 0.2))
        impact = max(0, min(int(row["impact_score"] or 0), 100))
        priority_factor = {"P1": 1.0, "P2": 0.55, "P3": 0.20, "P4": 0.04}.get(str(row["priority"]), 0.08)
        temporal_factor = {"grace": 0.2, "transient": 0.35, "persistent": 0.75, "chronic": 1.0}.get(str(row["temporal_state"]), 0.5)
        raw = (impact / 10.0) * priority_factor * temporal_factor * freshness
        # A fresh demonstrated functional root should be visible in Current Health
        # even when its fractional penalty would otherwise round to zero.
        if raw > 0 and impact >= 40 and age_hours <= 3 and str(row["priority"]) in {"P1", "P2", "P3"}:
            return max(1, round(raw))
        return max(0, round(raw))

    def health(self) -> dict[str, Any]:
        """HA operational health, reliability, diagnostic coverage and HADS health are separate."""
        now_dt = dt.datetime.fromisoformat(self.now())
        with self.db() as conn:
            roots = conn.execute(
                "SELECT * FROM root_cases WHERE lifecycle!='RESOLVED' "
                "AND decision_state NOT IN ('known_expected','rejected','deferred','manual_monitoring') "
                "AND category NOT IN ('hads_internal','diagnostic_coverage')"
            ).fetchall()
            collectors = conn.execute("SELECT required,status FROM collector_sources").fetchall()
            internal = int(conn.execute("SELECT count(*) n FROM cases WHERE category='hads_internal' AND status NOT IN ('resolved','ignored')").fetchone()["n"])
        penalties = [(int(row["id"]), self._root_current_penalty(row, now_dt)) for row in roots]
        impact_penalty = sum(value for _, value in penalties)
        current = max(0, 100 - min(100, impact_penalty))
        chronic_penalty = 0
        for row in roots:
            impact = max(0, min(int(row["impact_score"] or 0), 100))
            if str(row["temporal_state"]) == "chronic":
                chronic_penalty += max(1, round((impact / 10.0) * {"P1": 1.0, "P2": 0.6, "P3": 0.25, "P4": 0.05}.get(str(row["priority"]), 0.1)))
        reliability = max(0, 100 - min(100, chronic_penalty))
        total = len(collectors)
        ok = sum(1 for row in collectors if row["status"] == "ok")
        coverage = round(ok / total * 100) if total else 0
        required_failed = sum(1 for row in collectors if row["required"] and row["status"] != "ok")
        optional_failed = sum(1 for row in collectors if not row["required"] and row["status"] == "error")
        hads_health = max(0, 100 - required_failed * 20 - optional_failed * 5 - min(60, internal * 3))
        scored = sum(1 for _, penalty in penalties if penalty > 0)
        return {
            "current_health": current, "reliability": reliability, "coverage": coverage, "hads_health": hads_health,
            "root_active": len(roots), "root_scored": scored, "current_penalty": impact_penalty,
            "current_window_hours": int(self.options().get("current_health_window_hours", 24)), "restart_grace": False,
        }

    def snapshot_health(self) -> dict[str, Any]:
        value = self.health()
        with self.db() as conn:
            conn.execute(
                """INSERT INTO health_snapshots(measured_at,current_health,reliability,coverage,hads_health,root_active,details_json)
                   VALUES(?,?,?,?,?,?,?)""",
                (self.now(), value["current_health"], value["reliability"], value["coverage"], value["hads_health"], value["root_active"], json.dumps(value, ensure_ascii=False)),
            )
            history = [_row(row) for row in conn.execute(
                "SELECT measured_at,current_health,reliability,coverage,hads_health,root_active FROM health_snapshots ORDER BY id DESC LIMIT 30"
            ).fetchall()]
        return {**value, "history": list(reversed(history))}

    def command_center(self) -> dict[str, Any]:
        all_roots = self.list_roots()
        roots_with_history = self.list_roots(include_resolved=True)
        health = self.health()
        counts: dict[str, int] = {}
        for root in all_roots:
            counts[root["decision_state"]] = counts.get(root["decision_state"], 0) + 1
        actionable_states = {"awaiting_decision", "review_ready", "approved", "needs_information"}
        captain_roots = [root for root in all_roots if root.get("decision_state") in actionable_states]
        repair_roots = [
            root for root in captain_roots
            if root.get("repair_prepared") and root.get("decision_state") in {"awaiting_decision", "approved", "needs_information"}
        ]
        conclusion_roots = [
            root for root in captain_roots
            if not root.get("repair_prepared") and root.get("decision_state") in {"review_ready", "needs_information"}
        ]
        investigating = [root for root in all_roots if root.get("decision_state") in {"investigating", "reinvestigate"}]
        watching = [root for root in all_roots if root.get("decision_state") in {"watching", "verifying", "manual_monitoring", "repair_failed"}]
        automatic_monitoring = [root for root in watching if root.get("decision_state") == "watching" and root.get("state_origin") == "automatic"]
        captain_watching = [root for root in watching if root not in automatic_monitoring]
        history = [root for root in roots_with_history if root.get("decision_state") in {"rejected", "known_expected", "deferred", "resolved", "ignored"}]
        # Potential gain is the root's actual current-health contribution; never advertise
        # +28 when Current Health is already 100.
        now_dt = dt.datetime.fromisoformat(self.now())
        for root in all_roots:
            root["potential_health_gain"] = self._root_current_penalty(root, now_dt) if root.get("repair_prepared") else 0
        with self.db() as conn:
            batch_row = conn.execute("SELECT * FROM repair_batches ORDER BY id DESC LIMIT 1").fetchone()
            approved_rows = conn.execute(
                """SELECT rp.id,rp.actions_json,rp.case_id,
                          EXISTS(SELECT 1 FROM root_cases rc WHERE rc.repair_plan_id=rp.id AND rc.lifecycle!='RESOLVED' AND rc.decision_state='approved') root_approved
                   FROM repair_plans rp WHERE rp.status='approved'"""
            ).fetchall()
        with self.db() as conn:
            pending_plans = [_row(r) for r in conn.execute("SELECT id,title,status,actions_json,case_id FROM repair_plans WHERE status IN ('pending_approval','approved')")]
        executable_plans = sum(executable_actions(_json(p["actions_json"], [])) for p in pending_plans)
        approved_plans = 0
        blocked_approved = 0
        for plan in approved_rows:
            actions = _json(plan["actions_json"], [])
            executable = executable_actions(actions)
            consistent = plan["case_id"] is None or bool(plan["root_approved"])
            if executable and consistent:
                approved_plans += 1
            else:
                blocked_approved += 1
        batch = self._serialize_batch(_row(batch_row)) if batch_row else None
        return {
            "version": "first-officer", "updated_at": self.now(), "health": health, "counts": counts,
            "approved_plans": approved_plans, "blocked_approved_plans": blocked_approved,
            "executable_plans": executable_plans,
            "standalone_plans": [{k: v for k, v in p.items() if k != "actions_json"} for p in pending_plans if p["case_id"] is None and executable_actions(_json(p["actions_json"], []))],
            "root_cases": captain_roots,
            "repair_cases": repair_roots,
            "conclusion_cases": conclusion_roots,
            "history_cases": history,
            "tracked_root_count": len(all_roots),
            "investigating_count": len(investigating), "watching_count": len(watching),
            "investigating_cases": investigating, "watching_cases": captain_watching,
            "automatic_monitoring_cases": automatic_monitoring, "latest_batch": batch,
        }

    def plan_batch(self, plans: list[dict[str, Any]]) -> dict[str, Any]:
        """Detect conflicts, derive dependencies and rebase approved actions."""
        working = json.loads(json.dumps(plans, ensure_ascii=False))
        by_id = {int(plan["id"]): plan for plan in working}
        conflicts: list[dict[str, Any]] = []
        if len(working) > 1 and any(a.get("type") == "recorder_purge" for p in working for a in p.get("actions", [])):
            conflicts.append({"type": "database_exclusive", "message": "Údržbu databáze spusťte samostatně bez dalších schválených oprav."})
        dependencies: set[tuple[int, int, str]] = set()
        yaml_actions: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        object_actions: dict[str, list[int]] = {}
        addon_keys: dict[tuple[str, str], tuple[int, Any]] = {}
        addon_options_plan: dict[str, int] = {}
        addon_restarts: list[tuple[str, int]] = []
        core_restarts: list[int] = []
        diagnostic_only: list[int] = []
        for plan in working:
            plan_id = int(plan["id"])
            actions = plan.get("actions") or []
            mutation_targets = set()
            if actions and all(action.get("type") == "core_check" for action in actions):
                diagnostic_only.append(plan_id)
            for action in actions:
                kind = action.get("type")
                if kind in {"yaml_replace", "automation_update", "script_update", "addon_options"}:
                    target_key = (kind, str(action.get("path") or action.get("automation_id") or action.get("script_id") or action.get("addon") or ""))
                    if target_key in mutation_targets:
                        conflicts.append({"type": "duplicate_target", "plans": [plan_id], "message": "Jeden plán obsahuje více zápisů do stejného cíle. Sloučte je do jedné přesné změny."})
                    mutation_targets.add(target_key)
                if kind == "yaml_replace":
                    yaml_actions.setdefault(str(action.get("path") or ""), []).append((plan_id, action))
                elif kind in {"automation_update", "script_update"}:
                    object_id = str(action.get("automation_id") or action.get("script_id") or "")
                    target = f"{kind}:{object_id}"
                    object_actions.setdefault(target, []).append(plan_id)
                elif kind == "addon_options":
                    slug = str(action.get("addon") or "")
                    addon_options_plan.setdefault(slug, plan_id)
                    for key, value in (action.get("options_patch") or {}).items():
                        identity = (slug, str(key))
                        previous = addon_keys.get(identity)
                        if previous and previous[1] != value:
                            conflicts.append({"type": "addon_option_conflict", "target": f"{slug}.{key}", "plans": [previous[0], plan_id], "message": "Dva schválené plány nastavují stejnou volbu na různé hodnoty."})
                        else:
                            addon_keys[identity] = (plan_id, value)
                elif kind == "addon_restart":
                    addon_restarts.append((str(action.get("addon") or ""), plan_id))
                elif kind == "core_restart":
                    core_restarts.append(plan_id)

        for target, plan_ids_for_target in object_actions.items():
            if len(set(plan_ids_for_target)) > 1:
                conflicts.append({
                    "type": "object_update_conflict", "target": target,
                    "plans": sorted(set(plan_ids_for_target)),
                    "message": "Dva schválené plány mění stejnou automatizaci nebo skript; musí být znovu sloučeny do jednoho návrhu.",
                })

        cfg_root = self.config_root()
        for relative, items in yaml_actions.items():
            if not cfg_root:
                conflicts.append({"type": "config_unavailable", "target": relative, "plans": sorted({item[0] for item in items}), "message": "Nelze načíst /config pro batch rebase."})
                continue
            target = (cfg_root / relative).resolve()
            try:
                target.relative_to(cfg_root.resolve())
            except ValueError:
                conflicts.append({"type": "unsafe_path", "target": relative, "plans": sorted({item[0] for item in items})})
                continue
            if not target.is_file() or target.is_symlink():
                conflicts.append({"type": "missing_target", "target": relative, "plans": sorted({item[0] for item in items})})
                continue
            simulated = target.read_text(encoding="utf-8")
            original_hash = hashlib.sha256(simulated.encode("utf-8")).hexdigest()
            previous_plan: int | None = None
            for plan_id, action in sorted(items, key=lambda item: item[0]):
                if action.get("expected_sha256") != original_hash:
                    conflicts.append({"type": "stale_approval", "target": relative, "plans": [plan_id], "message": "Soubor se od schválení změnil. Je nutný nový náhled a souhlas."})
                    continue
                before = str(action.get("before") or "")
                after = str(action.get("after") or "")
                count = simulated.count(before) if before else 0
                if count != 1:
                    conflicts.append({"type": "yaml_rebase_conflict", "target": relative, "plans": [plan_id], "message": f"Schválený původní blok se po předchozích změnách vyskytuje {count}×."})
                    continue
                action["expected_sha256"] = hashlib.sha256(simulated.encode("utf-8")).hexdigest()
                simulated = simulated.replace(before, after, 1)
                if previous_plan is not None and previous_plan != plan_id:
                    dependencies.add((previous_plan, plan_id, f"sekvenční změna {relative}"))
                previous_plan = plan_id

        for slug, restart_plan in addon_restarts:
            options_plan = addon_options_plan.get(slug)
            if options_plan and options_plan != restart_plan:
                dependencies.add((options_plan, restart_plan, f"restart {slug} až po změně options"))

        plan_ids = set(by_id)
        for core_restart in core_restarts:
            for other in plan_ids - {core_restart}:
                dependencies.add((other, core_restart, "restart Core musí být poslední"))
        for diagnostic in diagnostic_only:
            for other in plan_ids - set(diagnostic_only):
                dependencies.add((diagnostic, other, "diagnostický preflight před změnami"))

        incoming = {plan_id: set() for plan_id in plan_ids}
        outgoing = {plan_id: set() for plan_id in plan_ids}
        for source, target, _ in dependencies:
            if source in plan_ids and target in plan_ids and source != target:
                incoming[target].add(source)
                outgoing[source].add(target)
        queue = sorted((plan_id for plan_id in plan_ids if not incoming[plan_id]), key=lambda item: item)
        order: list[int] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for target in sorted(outgoing[current]):
                incoming[target].discard(current)
                if not incoming[target] and target not in order and target not in queue:
                    queue.append(target)
            queue.sort()
        if len(order) != len(plan_ids):
            conflicts.append({"type": "dependency_cycle", "plans": sorted(plan_ids), "message": "Pořadí schválených oprav obsahuje cyklus."})
            order = sorted(plan_ids)
        ordered_plans = [by_id[plan_id] for plan_id in order]
        return {
            "blocked": bool(conflicts),
            "order": order,
            "dependencies": [{"before": a, "after": b, "reason": reason} for a, b, reason in sorted(dependencies)],
            "conflicts": conflicts,
            "plans": ordered_plans,
        }

    @staticmethod
    def _serialize_batch(value: dict[str, Any]) -> dict[str, Any]:
        value["plan_ids"] = _json(value.pop("plan_ids_json", "[]"), [])
        value["before"] = _json(value.pop("before_json", "{}"), {})
        value["after"] = _json(value.pop("after_json", "{}"), {})
        value["results"] = _json(value.pop("results_json", "[]"), [])
        value["batch_plan"] = _json(value.pop("batch_plan_json", "{}"), {})
        value["conflicts"] = _json(value.pop("conflicts_json", "[]"), [])
        value["remote_verification"] = _json(value.pop("remote_verification_json", "{}"), {})
        return value

    def create_batch(self, plan_ids: list[int], before: dict[str, Any]) -> int:
        with self.db() as conn:
            cursor = conn.execute(
                "INSERT INTO repair_batches(status,plan_ids_json,before_json,created_at) VALUES(?,?,?,?)",
                ("preparing_rescue", json.dumps(plan_ids), json.dumps(before, ensure_ascii=False), self.now()),
            )
            return int(cursor.lastrowid)

    def update_batch(self, batch_id: int, **fields: Any) -> None:
        allowed = {"status", "rescue_path", "rescue_sha256", "rescue_destination", "rescue_verified_at", "rw_opened_at", "rw_closed_at", "before_json", "after_json", "results_json", "batch_plan_json", "conflicts_json", "remote_verification_json", "last_error", "finished_at"}
        pairs = [(key, fields[key]) for key in fields if key in allowed]
        if not pairs:
            return
        with self.db() as conn:
            conn.execute(f"UPDATE repair_batches SET {','.join(key+'=?' for key, _ in pairs)} WHERE id=?", tuple(value for _, value in pairs) + (batch_id,))

    def prepare_rescue(self, batch_id: int, plans: list[dict[str, Any]], before: dict[str, Any]) -> dict[str, Any]:
        """Build an auditable rescue ZIP before the repair mode can be opened."""
        stamp = dt.datetime.fromisoformat(self.now()).strftime("%Y-%m-%d_%H-%M-%S")
        root = self.private_root / "batches" / f"HADS_REPAIR_{stamp}_B{batch_id:04d}"
        if root.exists():
            raise ValueError("Rescue složka této dávky již existuje; původní důkazy se nesmí přepsat.")
        for name in ("originals", "addon_options", "patches"):
            (root / name).mkdir(parents=True, exist_ok=True)
        cfg_root = self.config_root()
        approvals = []
        manifests = []
        for plan in plans:
            approvals.append({"plan_id": plan["id"], "approved_at": plan.get("approved_at"), "title": plan["title"]})
            for index, action in enumerate(plan.get("actions") or [], start=1):
                kind = action.get("type")
                if kind == "yaml_replace" and cfg_root:
                    relative = str(action.get("path") or "")
                    source = (cfg_root / relative).resolve()
                    try:
                        source.relative_to(cfg_root.resolve())
                    except ValueError as exc:
                        raise ValueError("Rescue balík odmítl cestu mimo /config.") from exc
                    if not source.is_file():
                        raise ValueError(f"Rescue balík nenašel {relative}.")
                    target = root / "originals" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    diff = "".join(difflib.unified_diff(str(action.get("before") or "").splitlines(True), str(action.get("after") or "").splitlines(True), fromfile=relative, tofile=relative + " (navrh)"))
                    (root / "patches" / f"R-{plan['id']:04d}-{index}.diff").write_text(diff, encoding="utf-8")
                elif kind in {"automation_update", "script_update"}:
                    object_id = str(action.get("automation_id") or action.get("script_id") or "")
                    target = root / "originals" / f"{kind}_{_slug(object_id)}.json"
                    target.write_text(json.dumps(action.get("before") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
                    before_text = json.dumps(action.get("before") or {}, ensure_ascii=False, indent=2, sort_keys=True).splitlines(True)
                    after_text = json.dumps(action.get("after") or {}, ensure_ascii=False, indent=2, sort_keys=True).splitlines(True)
                    diff = "".join(difflib.unified_diff(before_text, after_text, fromfile=f"{kind}:{object_id}", tofile=f"{kind}:{object_id} (navrh)"))
                    (root / "patches" / f"R-{plan['id']:04d}-{index}.diff").write_text(diff, encoding="utf-8")
                elif kind in {"addon_options", "addon_restart"}:
                    slug = str(action.get("addon") or "")
                    info = self.supervisor_request(f"/addons/{slug}/info")
                    options = info.get("options") if isinstance(info, dict) else None
                    if options is None:
                        raise ValueError(f"Nelze načíst původní volby doplňku {slug}.")
                    (root / "addon_options" / f"{_slug(slug)}.json").write_text(json.dumps(options, ensure_ascii=False, indent=2), encoding="utf-8")
                manifests.append({"plan_id": plan["id"], "action": kind, "target": action.get("path") or action.get("addon") or "Home Assistant Core"})
        manifest = {"batch_id": batch_id, "created_at": self.now(), "hads_mode": "READ_ONLY", "plans": manifests}
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "captain_approvals.json").write_text(json.dumps(approvals, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "health_before.json").write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "dependencies_before.json").write_text(json.dumps({"root_cases": self.list_roots()}, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# HADS 4 Repair Batch", "", f"Batch: B-{batch_id:04d}", "", "## Schválené opravy"]
        lines.extend(f"- #{plan['id']}: {plan['title']} ({plan.get('risk_level','unknown')})" for plan in plans)
        (root / "repair_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (root / "restore_instructions.txt").write_text("Obnovte soubory z originals/ nebo použijte rollback v HADS. Před restartem vždy spusťte ha core check.\n", encoding="utf-8")
        archive = root.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    output.write(path, path.relative_to(root))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.update_batch(batch_id, rescue_path=str(archive), rescue_sha256=digest)
        return {"path": str(archive), "sha256": digest, "files": len([p for p in root.rglob('*') if p.is_file()])}

    def batch(self, batch_id: int) -> dict[str, Any] | None:
        with self.db() as conn:
            row = conn.execute("SELECT * FROM repair_batches WHERE id=?", (batch_id,)).fetchone()
        return self._serialize_batch(_row(row)) if row else None
