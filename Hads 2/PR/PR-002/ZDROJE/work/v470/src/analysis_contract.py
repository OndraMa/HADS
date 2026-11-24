"""Untrusted analysis -> bounded, reviewable configuration proposals.

No IO or execution here. Every patch is tied to a case owner and an exact
live value. The caller must still run RepairEngine preview, approval, backup,
concurrency checks and post-write verification. Never compile prose or SQL.
"""
from __future__ import annotations

import copy
import json
import re


class ProposalError(ValueError):
    pass


def apply_scalar_changes(before: dict, changes: list[dict]) -> dict:
    if not changes or len(changes) > 12:
        raise ProposalError("Návrh musí obsahovat 1–12 přesných změn.")
    after = copy.deepcopy(before)
    seen = set()
    for change in changes:
        pointer = change.get("path")
        if not isinstance(pointer, str) or not pointer.startswith("/") or len(pointer) > 500:
            raise ProposalError("Chybí přesná JSON Pointer cesta.")
        parts = pointer[1:].split("/")
        if any(re.search(r"~(?![01])", part) for part in parts):
            raise ProposalError("Neplatné escapování JSON Pointer.")
        parts = [p.replace("~1", "/").replace("~0", "~") for p in parts]
        if parts[0] not in {"trigger", "triggers", "condition", "conditions", "action", "actions", "sequence", "variables", "mode", "max"}:
            raise ProposalError("Změna není uvnitř podporované konfigurace automatizace/skriptu.")
        if pointer in seen:
            raise ProposalError("Dva návrhy mění stejnou hodnotu.")
        seen.add(pointer)
        try:
            def reject_constant(value):
                raise ValueError(value)
            old = json.loads(change["old_json"], parse_constant=reject_constant)
            new = json.loads(change["new_json"], parse_constant=reject_constant)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProposalError("Původní a nová hodnota musí být platné JSON skaláry.") from exc
        if isinstance(old, (list, dict)) or isinstance(new, (list, dict)) or new is None:
            raise ProposalError("AI smí navrhnout jen náhradu skaláru, nikoli mazání nebo přestavbu bloků.")
        if old == new and type(old) is type(new):
            raise ProposalError("Návrh neobsahuje změnu.")
        node = after
        try:
            for part in parts[:-1]:
                if isinstance(node, list):
                    if not re.fullmatch(r"0|[1-9][0-9]*", part):
                        raise ValueError("index")
                    node = node[int(part)]
                else:
                    node = node[part]
            key = parts[-1]
            if isinstance(node, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", key):
                    raise ValueError("index")
                key = int(key)
            current = node[key]
            if type(current) is not type(old) or current != old:
                raise ProposalError("Živá hodnota neodpovídá návrhu; nutné nové vyšetření.")
            node[key] = new
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ProposalError):
                raise
            raise ProposalError("Cesta neexistuje v živé konfiguraci; nic nebylo změněno.") from exc
    return after


def plan_readiness(analysis: dict, actions: list, blockers: list) -> dict:
    """Do not turn a confident statement into an executable plan."""
    return {
        "analysis_received": bool(analysis),
        "candidate_steps": len(analysis.get("proposed_actions") or []),
        "exact_changes": len(analysis.get("configuration_changes") or []),
        "executable_actions": len(actions),
        "blockers": list(dict.fromkeys(str(x) for x in blockers)),
        "requires_approval": bool(actions),
        "backup_required": True,
        "execution_started": False,
    }
