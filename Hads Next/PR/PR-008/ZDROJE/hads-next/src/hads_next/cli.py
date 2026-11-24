"""Local operator CLI. No HTTP service, HA credentials or production writes."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import time

from .evidence import IncidentStore
from .investigation import HERMES_REVISION, ReadGateway
from .repair import ApprovalAuthority, ExecutionResult, RepairBlocked, RepairEngine, RepairPlan
from .reporting import export_center
from .verification import FunctionalVerifier


def write_json(path, value):
    path = Path(path)
    # Operator artifacts may contain private household evidence.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def read_json(path):
    return json.loads(Path(path).read_text())


def initialize(workspace: Path, *, now=None):
    """Create a fresh private fixture. Existing paths are never overwritten."""
    now = time.time() if now is None else now
    workspace.mkdir(mode=0o700, parents=False, exist_ok=False)
    fixture = workspace / "fixtures"
    fixture.mkdir(mode=0o700)
    automation = {"id": "radio_button", "action": {"service": "light.turn_on",
        "target": {"entity_id": "light.old_lamp"}}}
    trace = {"kind": "target_not_found", "automation_id": "radio_button",
        "entity_id": "light.old_lamp", "context_id": "offline-button-1",
        "observed_at": now - 1,
        "fixture_registry": {"light.living_room": {"device_id": "fixture-lamp-1", "state": "off"}},
        "fixture_expected_target": "light.living_room",
        "scope": "synthetic_isolated_not_live_HA"}
    snapshots = {"automation": automation, "trace": trace}
    write_json(fixture / "automation.json", automation)
    write_json(workspace / "snapshots.json", snapshots)
    store = IncidentStore(workspace / "state.sqlite")
    incident = store.open_incident("automation_target_failure", "Tlačítko nezapnulo světlo.",
        ["radio_button", "light.old_lamp"], now, correlation_key="fixture:radio_button")
    for source, payload in snapshots.items():
        store.add_evidence(incident["id"], {"source": source, "kind": source,
            "observed_at": now - 1, "payload": payload, "event_id": "fixture-" + source})
    write_json(workspace / "case.json", {"incident_id": incident["id"], "scope": "offline_isolated_fixture"})
    refresh_center(workspace)
    return incident


def validate_hermes_receipt(snapshots, receipt):
    """Protocol/freshness check, NOT a cryptographic runtime attestation or approval."""
    if (receipt.get("engine") != "NousResearch/hermes-agent" or
        receipt.get("revision") != HERMES_REVISION or receipt.get("completed") is not True or
        receipt.get("snapshot_sha256") != ReadGateway(snapshots).snapshot_sha256 or
        receipt.get("execution_authority") != "none" or
        receipt.get("model") != "scripted-local-endpoint-no-cost" or
        receipt.get("scope") != "offline-container" or
        [x.get("source") for x in receipt.get("read_receipts", [])] != ["automation", "trace"] or
        receipt.get("model_requests") != 3):
        raise RepairBlocked("Účtenka neodpovídá izolovanému Hermes testu a tomuto souboru důkazů.")


def engine(workspace, *, clock=time.time):
    return RepairEngine(workspace / "state.sqlite", workspace / "fixtures",
        allowed_files={"automation.json"}, owner=f"uid:{os.getuid()}", clock=clock)


def prepare(workspace, receipt_path):
    snapshots, receipt = read_json(workspace / "snapshots.json"), read_json(receipt_path)
    validate_hermes_receipt(snapshots, receipt)
    store = IncidentStore(workspace / "state.sqlite")
    incident_id = read_json(workspace / "case.json")["incident_id"]
    fingerprint = store.begin_analysis(incident_id)
    if fingerprint is not None:
        store.finish_analysis(incident_id, fingerprint, receipt)
    trace = snapshots["trace"]
    # Deterministic planner uses the fixture's explicit registry/expected target;
    # it does not execute model text or accept arbitrary suggested parameters.
    target = trace["fixture_expected_target"]
    if target not in trace["fixture_registry"] or trace["kind"] != "target_not_found":
        raise RepairBlocked("Chybí přesný důkaz nového cíle.")
    plan = engine(workspace).prepare_entity_reference(incident_id, "automation.json",
        "light.old_lamp", target, [x["evidence_id"] for x in store.case(incident_id)["evidence"]],
        "Izolovaný trace dokládá chybějící odkaz; testovací registry určuje konkrétní náhradu.")
    write_json(workspace / "plan.json", plan.document)
    store.record(incident_id, "repair_plan", plan.document)
    refresh_center(workspace)
    return plan


def load_plan(workspace):
    from .repair import canonical
    return RepairPlan(canonical(read_json(workspace / "plan.json")))


def decide(workspace, decision):
    plan = load_plan(workspace)
    authority = ApprovalAuthority(workspace / "state.sqlite", owner=f"uid:{os.getuid()}")
    token = authority.decide(plan, principal=f"uid:{os.getuid()}", decision=decision)
    # Opaque credential is never printed or exported to the AI/report.
    write_json(workspace / "decision.json", {"token": token, "decision": decision, "plan_id": plan.plan_id})
    incident_id = read_json(workspace / "case.json")["incident_id"]
    IncidentStore(workspace / "state.sqlite").record(incident_id, "user_decision",
        {"decision": decision, "plan_id": plan.plan_id})
    refresh_center(workspace)


def execute(workspace, *, clock=time.time):
    result = engine(workspace, clock=clock).execute(load_plan(workspace),
        read_json(workspace / "decision.json")["token"], principal=f"uid:{os.getuid()}")
    write_json(workspace / "execution.json", asdict(result))
    refresh_center(workspace)
    return result


def verify(workspace, observations_path, *, now=None):
    plan = load_plan(workspace)
    result = ExecutionResult(**read_json(workspace / "execution.json"))
    report = FunctionalVerifier(workspace / "state.sqlite").evaluate(plan, result,
        read_json(observations_path), now=now)
    store = IncidentStore(workspace / "state.sqlite")
    incident_id = read_json(workspace / "case.json")["incident_id"]
    store.record(incident_id, "verification", report)
    if report["classification"] == "Vyřešeno a ověřeno":
        store.mark_resolved(incident_id, report)
    elif report["classification"] in {"Oprava selhala", "Problém se opakoval"}:
        store.reopen_for_report(incident_id, report)
    write_json(workspace / "report.json", report)
    refresh_center(workspace)
    return report


def run_fixture_test(workspace):
    """Isolated functional fixture; logical clock, no physical result claimed.

    Read the actual repaired object and evaluate its target against the fixture
    registry. With the original bad reference no target_state is produced.
    """
    execution = read_json(workspace / "execution.json")
    completed = execution["completed_at"]
    automation = read_json(workspace / "fixtures" / "automation.json")
    states = read_json(workspace / "snapshots.json")["trace"]["fixture_registry"]
    target = automation["action"]["target"]["entity_id"]
    context = "offline-after-repair-" + execution["execution_id"]
    observations = [{"kind": "automation_triggered", "observed_at": completed + 1,
        "payload": {"automation_id": automation["id"], "context_id": context}}]
    if target in states and automation["action"]["service"] == "light.turn_on":
        states[target]["state"] = "on"
        observations += [{"kind": "target_state", "observed_at": completed + 2,
            "payload": {"entity_id": target, "state": states[target]["state"], "context_id": context}},
            {"kind": "monitoring_checkpoint", "observed_at": completed + 33,
            "payload": {"entity_id": target, "healthy": True, "continuous_since": completed}}]
    else:
        observations.append({"kind": "functional_failure", "observed_at": completed + 2,
            "payload": {"entity_id": "light.living_room", "symptom": "target_not_found"}})
    path = workspace / "observations.json"
    write_json(path, observations)
    return verify(workspace, path, now=completed + 34)


def refresh_center(workspace):
    incident_id = read_json(workspace / "case.json")["incident_id"]
    case = IncidentStore(workspace / "state.sqlite").case(incident_id)
    plans = [read_json(workspace / "plan.json")] if (workspace / "plan.json").exists() and not (workspace / "decision.json").exists() else []
    reports = [read_json(workspace / "report.json")] if (workspace / "report.json").exists() else []
    export_center(workspace / "command-center.html", [case], plans=plans, reports=reports)
    write_json(workspace / "case-export.json", case)


def main(argv=None):
    parser = argparse.ArgumentParser(description="HADS Next: pouze místní izolovaný scénář")
    parser.add_argument("command", choices=["init", "plan", "approve", "reject", "manual", "execute", "verify", "test-fixture", "export"])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--observations", type=Path)
    args = parser.parse_args(argv)
    workspace = args.workspace.absolute()
    if args.command == "init":
        initialize(workspace)
    elif args.command == "plan":
        if not args.receipt:
            parser.error("plan vyžaduje --receipt z reálného izolovaného Hermes smoke")
        plan = prepare(workspace, args.receipt)
        print(json.dumps({"plan_id": plan.plan_id, "plan": plan.document}, ensure_ascii=False, indent=2))
    elif args.command in {"approve", "reject", "manual"}:
        decide(workspace, args.command)
    elif args.command == "execute":
        print(json.dumps(asdict(execute(workspace)), ensure_ascii=False))
    elif args.command == "verify":
        if not args.observations:
            parser.error("verify vyžaduje --observations od důvěryhodného sběrače")
        print(json.dumps(verify(workspace, args.observations), ensure_ascii=False))
    elif args.command == "test-fixture":
        print(json.dumps(run_fixture_test(workspace), ensure_ascii=False))
    else:
        refresh_center(workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
