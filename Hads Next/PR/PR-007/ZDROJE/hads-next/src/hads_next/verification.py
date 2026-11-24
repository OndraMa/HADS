"""Functional evidence, never a successful HTTP response, closes a repair."""
from __future__ import annotations

from bisect import bisect_left
import json
import math
import time
from .repair import RepairBlocked, canonical, connect, digest
from .observability import redact


class FunctionalVerifier:
    """Evidence is supplied by a trusted collector, not by model-generated claims.

    Observation contract: kind, observed_at, payload; automation_triggered has
    automation_id/context_id, target_state has entity_id/state/context_id.
    monitoring_checkpoint has entity_id/continuous_since/healthy. Checkpoints
    attest continuous collector coverage, not merely the absence of error logs.
    """
    def __init__(self, db_path, *, clock=time.time):
        self.db_path, self.clock = db_path, clock
        connect(db_path).close()

    def evaluate(self, plan, execution, observations, *, now=None):
        supplied_clock = now is not None
        now = self.clock() if now is None else now
        conn = connect(self.db_path)
        try:
            # Reading the execution and merging evidence belongs in the same
            # transaction as updating it; concurrent verification must serialize.
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM repair_executions WHERE id=? AND plan_id=?",
                               (execution.execution_id, plan.plan_id)).fetchone()
            stored = conn.execute("SELECT document FROM repair_plans WHERE id=?", (plan.plan_id,)).fetchone()
            if row is None or stored is None or stored[0] != plan.serialized:
                raise RepairBlocked("Nelze ověřit neregistrované provedení nebo změněný plán.")
            if row["status"] not in {"applied_verification_pending", "verified", "failed", "recurred"} or row["completed_at"] is None:
                raise RepairBlocked("Zásah nemá potvrzený zápis; je třeba ruční kontrola.")
            condition = plan.document["verification"]
            completed = row["completed_at"]
            if len(observations) > 512:
                raise RepairBlocked("Dávka funkčních důkazů překročila povolený limit.")
            for item in observations:
                stamp = item.get("observed_at")
                if isinstance(stamp, (float, int)) and math.isfinite(stamp) and completed < stamp <= now:
                    serialized = canonical(redact(item))
                    if len(serialized.encode()) > 16384:
                        raise RepairBlocked("Jednotlivý funkční důkaz překročil povolenou velikost.")
                    conn.execute("INSERT OR IGNORE INTO repair_observations VALUES(?,?,?)",
                                 (execution.execution_id, digest(serialized), serialized))
            count = conn.execute("SELECT COUNT(*) FROM repair_observations WHERE execution_id=?",
                                 (execution.execution_id,)).fetchone()[0]
            if count > 2048:
                raise RepairBlocked("Spis ověření dosáhl limitu; vyžaduje archivaci a ruční kontrolu.")
            # An omitted earlier failure cannot turn the same execution into
            # success. Persist a deduplicated corpus instead of trusting subsets.
            corpus = [json.loads(item[0]) for item in conn.execute(
                "SELECT document FROM repair_observations WHERE execution_id=?",
                (execution.execution_id,))]
            fresh = [item for item in corpus if item["observed_at"] <= now]
            trigger_times = {}
            for item in fresh:
                payload = item.get("payload", {})
                if item.get("kind") == "automation_triggered" and payload.get("automation_id") == condition["automation_id"]:
                    context = payload.get("context_id")
                    if isinstance(context, str) and context:
                        trigger_times[context] = min(trigger_times.get(context, float("inf")), item["observed_at"])
            successes = [x for x in fresh if x.get("kind") == "target_state"
                    and x.get("payload", {}).get("entity_id") == condition["entity_id"]
                    and x["payload"].get("state") == condition["state"]
                    and isinstance(x["payload"].get("context_id"), str)
                    and x["observed_at"] >= trigger_times.get(x["payload"]["context_id"], float("inf"))]
            recurrences = [x for x in fresh if x.get("kind") == "functional_failure"
                           and x.get("payload", {}).get("entity_id") == condition["entity_id"]]
            covered = []
            success_times = sorted(item["observed_at"] for item in successes)
            for item in fresh:
                payload = item.get("payload", {})
                since = payload.get("continuous_since")
                if item.get("kind") == "monitoring_checkpoint" and payload.get("entity_id") == condition["entity_id"] \
                        and payload.get("healthy") is True and isinstance(since, (int, float)) \
                        and math.isfinite(since) and completed <= since:
                    index = bisect_left(success_times, since)
                    if index < len(success_times) and item["observed_at"] - success_times[index] >= condition["watch_seconds"]:
                        covered.append(item)
            if recurrences:
                classification = "Problém se opakoval" if successes or row["status"] == "verified" else "Oprava selhala"
                status = "recurred" if classification == "Problém se opakoval" else "failed"
            elif covered:
                classification, status = "Vyřešeno a ověřeno", "verified"
            elif successes:
                classification, status = "Oprava provedena, ověření čeká", "applied_verification_pending"
            elif not fresh:
                classification, status = "Není dostatek důkazů", "applied_verification_pending"
            else:
                classification, status = "Oprava provedena, ověření čeká", "applied_verification_pending"
            actual_core_lab = plan.document['operation'] == 'core_lab.replace_entity_reference' and not supplied_clock
            managed_core = plan.document['operation'] == 'core_managed.replace_entity_reference' and not supplied_clock
            report = {
                "language": "cs", "scope": "actual_core_managed_reference" if managed_core else "actual_core_container" if actual_core_lab else "offline_isolated_fixture", "plan_id": plan.plan_id,
                "clock_mode": "caller_supplied_offline_clock" if supplied_clock else "system_utc",
                "incident_id": plan.document["incident_id"], "execution_id": execution.execution_id,
                "classification": classification, "created_at": now,
                "summary": self._summary(classification),
                "functional_successes": len(successes), "coverage_checkpoints": len(covered),
                "recurrences": len(recurrences), "evidence": fresh,
                "limitation": ("Ověřena je virtuální automatizace ve skutečném odpojeném HA Core. Živý HAOS ani fyzické zařízení nebyly testovány."
                    if actual_core_lab else "Ověřena je pouze izolovaná testovací automatizace. Živý HAOS nebyl testován.")
                    + (" Sledovací interval používá testovací hodiny; nedokládá skutečnou dobu sledování domácnosti." if supplied_clock else ""),
            }
            conn.execute("UPDATE repair_executions SET status=? WHERE id=?", (status, execution.execution_id))
            conn.execute("INSERT INTO repair_reports(execution_id,created_at,classification,document) VALUES(?,?,?,?)",
                         (execution.execution_id, now, classification, canonical(report)))
            conn.execute("COMMIT")
            return report
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            conn.close()

    @staticmethod
    def _summary(classification):
        return {
            "Vyřešeno a ověřeno": "Po opravě se automatizace spustila, správné zařízení změnilo stav a během sledování se závada neopakovala.",
            "Oprava provedena, ověření čeká": "Odkaz byl změněn. Ještě chybí úplný funkční test nebo souvislá sledovací doba.",
            "Není dostatek důkazů": "Změna souboru je potvrzena, ale chybí nové funkční důkazy. Incident zůstává otevřený.",
            "Oprava selhala": "Původní funkční závada po změně pokračuje. Další zásahy jsou zastaveny; návrat změny potřebuje nové schválení.",
            "Problém se opakoval": "Funkce se obnovila jen dočasně. Incident je znovu otevřený a vyžaduje další vyšetření.",
        }[classification]

    def reports(self, execution_id):
        conn = connect(self.db_path)
        try:
            return [json.loads(row[0]) for row in conn.execute(
                "SELECT document FROM repair_reports WHERE execution_id=? ORDER BY id", (execution_id,))]
        finally:
            conn.close()
