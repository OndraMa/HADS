"""Persistent incident conversation and metered, read-only research.

This module never executes HA repairs. Messages and connector payloads are
evidence, not executable instructions or implicit authorization.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any


class AIBudgetExhausted(ValueError):
    """Expected local spending cap; no request was sent."""


def remaining_calls(db, now, cfg, case_id: int) -> int:
    if cfg.get("ai_call_limits_enabled") is False:
        return 8  # Per-investigation bound remains; no daily monetary/call cap.
    cutoff = (dt.datetime.fromisoformat(now()) - dt.timedelta(hours=24)).isoformat(timespec="seconds")
    with db() as conn:
        total = conn.execute("SELECT count(*) FROM ai_calls WHERE created_at>=?", (cutoff,)).fetchone()[0]
        count = conn.execute("SELECT count(*) FROM ai_calls WHERE created_at>=? AND case_id=?", (cutoff, case_id)).fetchone()[0]
    return max(0, min(max(1, min(int(cfg.get("ai_daily_call_limit", 20)), 200)) - total,
                      max(1, min(int(cfg.get("ai_case_daily_call_limit", 6)), 30)) - count))

SCHEMA = """
CREATE TABLE IF NOT EXISTS root_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 root_case_id INTEGER NOT NULL REFERENCES root_cases(id),
 role TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS root_messages_root ON root_messages(root_case_id,id);
CREATE TABLE IF NOT EXISTS root_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 root_case_id INTEGER NOT NULL REFERENCES root_cases(id),
 status TEXT NOT NULL, kind TEXT NOT NULL, last_error TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, finished_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS root_jobs_active ON root_jobs(root_case_id) WHERE status='running';
CREATE TABLE IF NOT EXISTS ai_calls (
 id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL,
 model TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
 input_bytes INTEGER NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
 reasoning_tokens INTEGER, web_calls INTEGER, response_id TEXT
);
CREATE TABLE IF NOT EXISTS root_choices (
 root_case_id INTEGER NOT NULL REFERENCES root_cases(id),
 owner TEXT NOT NULL, old_value TEXT NOT NULL, new_value TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(root_case_id,owner,old_value)
);
"""


def initialize(db, now) -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        conn.execute("UPDATE root_jobs SET status='interrupted',last_error='HADS byl restartován; rozpracovanou analýzu spusťte znovu.',finished_at=? WHERE status='running'", (now(),))
        conn.execute("UPDATE ai_calls SET status='unknown_after_restart' WHERE status='running'")


def context(db, root_id: int) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM root_messages WHERE root_case_id=? ORDER BY id DESC LIMIT 100", (root_id,)).fetchall()
        job = conn.execute("SELECT * FROM root_jobs WHERE root_case_id=? ORDER BY id DESC LIMIT 1", (root_id,)).fetchone()
        usage = conn.execute("""SELECT count(*) calls,COALESCE(sum(input_tokens),0) input_tokens,
            COALESCE(sum(output_tokens),0) output_tokens,COALESCE(sum(reasoning_tokens),0) reasoning_tokens,
            COALESCE(sum(web_calls),0) web_calls,sum(CASE WHEN input_tokens IS NULL THEN 1 ELSE 0 END) unknown_calls
            FROM ai_calls WHERE case_id IN (SELECT case_id FROM root_case_members WHERE root_case_id=?)""", (root_id,)).fetchone()
    return {"messages": [dict(r) for r in reversed(rows)], "job": dict(job) if job else None, "usage": dict(usage)}


def start_job(db, now, root_id: int, body: str, kind: str) -> int:
    if kind not in {"chat", "reinvestigate"} or not body.strip() or len(body) > 6000:
        raise ValueError("Zpráva musí mít 1–6000 znaků a platný typ.")
    with db() as conn:
        if not conn.execute("SELECT 1 FROM root_cases WHERE id=?", (root_id,)).fetchone():
            raise ValueError("Incident neexistuje.")
        # Unique index makes double clicks/retries fail without a second API call.
        job = conn.execute("INSERT INTO root_jobs(root_case_id,status,kind,created_at) VALUES(?,'running',?,?)", (root_id, kind, now()))
        conn.execute("INSERT INTO root_messages(root_case_id,role,body,created_at) VALUES(?,'user',?,?)", (root_id, body.strip(), now()))
        return int(job.lastrowid)


def finish_job(db, now, root_id: int, job_id: int, answer: str, error: str = "") -> None:
    with db() as conn:
        conn.execute("INSERT INTO root_messages(root_case_id,role,body,created_at) VALUES(?,'assistant',?,?)", (root_id, answer[:30000], now()))
        conn.execute("UPDATE root_jobs SET status=?,last_error=?,finished_at=? WHERE id=?", ("failed" if error else "completed", error[:2000], now(), job_id))


def metered_call(db, now, cfg: dict[str, Any], case_id: int, key: str, body: dict[str, Any], send) -> dict[str, Any]:
    """Persistent call caps, bounded input bytes/output tokens, actual usage.

    No dollar guarantee: server-side web content may add input tokens. Failed
    requests consume a call slot because billing may have occurred remotely.
    """
    body = dict(body)
    body["max_output_tokens"] = max(512, min(int(cfg.get("ai_max_output_tokens", 4000)), 12000))
    size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    if size > 64000:
        raise ValueError("Výzkum dosáhl limitu 64 kB kontextu. Zúžte otázku; další placený požadavek nebyl odeslán.")
    cutoff = (dt.datetime.fromisoformat(now()) - dt.timedelta(hours=24)).isoformat(timespec="seconds")
    with db() as conn:
        # db() serializes writers; reserve before leaving the transaction.
        total = conn.execute("SELECT count(*) FROM ai_calls WHERE created_at>=?", (cutoff,)).fetchone()[0]
        count = conn.execute("SELECT count(*) FROM ai_calls WHERE created_at>=? AND case_id=?", (cutoff, case_id)).fetchone()[0]
        if cfg.get("ai_call_limits_enabled", True) and (total >= max(1, min(int(cfg.get("ai_daily_call_limit", 20)), 200)) or count >= max(1, min(int(cfg.get("ai_case_daily_call_limit", 6)), 30))):
            raise AIBudgetExhausted("Dosažen limit AI požadavků za 24 hodin. Diagnostika bez AI pokračuje.")
        call_id = int(conn.execute("INSERT INTO ai_calls(case_id,model,status,created_at,input_bytes) VALUES(?,?,'running',?,?)", (case_id, str(body.get("model")), now(), size)).lastrowid)
    try:
        value = send(key, body)
        usage = value.get("usage") or {}
        with db() as conn:
            conn.execute("UPDATE ai_calls SET status=?,input_tokens=?,output_tokens=?,reasoning_tokens=?,web_calls=?,response_id=? WHERE id=?", (
                str(value.get("status") or "completed"), usage.get("input_tokens"), usage.get("output_tokens"),
                (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
                sum(i.get("type") == "web_search_call" for i in value.get("output", []) if isinstance(i, dict)), value.get("id"), call_id))
        if value.get("status") == "incomplete":
            raise ValueError("AI odpověď je neúplná (limit výstupu); nelze ji použít jako hotový opravný plán.")
        return value
    except Exception:
        with db() as conn:
            conn.execute("UPDATE ai_calls SET status='unknown_or_failed' WHERE id=? AND status='running'", (call_id,))
        raise
