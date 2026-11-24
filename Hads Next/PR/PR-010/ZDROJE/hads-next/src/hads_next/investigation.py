"""Read-only evidence boundary and integration with the original Hermes runtime.

This module gives Hermes data, never an HA client or executor. The native runtime
entry point is a test worker: production activation awaits the audited OS jail.
Tool allowlists alone are not a security boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

HERMES_REVISION = "d923a5eb487a17c0a68801bba9ef0f56c81040a8"
ROLES = (
    "Event Investigator", "System Investigator", "Device Investigator",
    "Integration Investigator", "Research Investigator", "Root Cause Investigator",
    "Repair Planner", "Verification Investigator",
)


class ReadDenied(ValueError):
    pass


def redact_snapshot(value, depth=0):
    """Defense in depth; observability must also redact before persistence."""
    if depth > 16:
        raise ValueError("Evidence nesting limit exceeded")
    if isinstance(value, dict):
        return {str(k): ("[redacted]" if re.search(
            r"password|authorization|access_token|api_key|secret|^token$", str(k), re.I)
            else redact_snapshot(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_snapshot(v, depth + 1) for v in value]
    if isinstance(value, str):
        return re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", value)
    return value


class ReadGateway:
    """Bounded snapshot readers; a source can be read once per investigation.

    Readers must be credential-free, read-only snapshots prepared by observability.
    This object is deliberately not extensible through model-provided URLs/code.
    """
    def __init__(self, snapshots: dict[str, object], *, max_reads: int = 4,
                 max_bytes: int = 32768):
        if not snapshots or len(snapshots) > 32 or not 1 <= max_reads <= 8:
            raise ValueError("Invalid evidence catalog/budget")
        if any(not isinstance(k, str) or not k.isidentifier() for k in snapshots):
            raise ValueError("Invalid evidence source name")
        self._snapshots = redact_snapshot(snapshots)
        self.snapshot_sha256 = hashlib.sha256(json.dumps(
            self._snapshots, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest()
        self._max_reads = max_reads
        self._max_bytes = max_bytes
        self.receipts: list[dict] = []

    @property
    def schema(self) -> dict:
        return {"name": "hads_read_evidence",
                "description": "Přečte jeden dostupný zdroj důkazů. Nic nemění.",
                "parameters": {"type": "object", "properties": {
                    "source": {"type": "string", "enum": sorted(self._snapshots)}},
                    "required": ["source"], "additionalProperties": False}}

    def read(self, arguments: dict) -> str:
        if not isinstance(arguments, dict) or set(arguments) != {"source"}:
            raise ReadDenied("Invalid read arguments")
        source = arguments["source"]
        if not isinstance(source, str) or source not in self._snapshots:
            raise ReadDenied("Unknown evidence source")
        if any(r["source"] == source for r in self.receipts):
            raise ReadDenied("No new evidence: repeated read denied")
        if len(self.receipts) >= self._max_reads:
            raise ReadDenied("Evidence budget exhausted")
        payload = json.dumps(self._snapshots[source], ensure_ascii=False)
        if len(payload.encode()) > self._max_bytes:
            raise ReadDenied("Evidence too large; narrow collection first")
        self.receipts.append({"source": source, "bytes": len(payload.encode())})
        return payload


def native_hermes_investigation(gateway: ReadGateway, *, base_url: str,
                                model: str = "hads-offline", max_iterations: int = 4,
                                prompt: str = "Vyšetři incident. Nejprve čti automation, potom trace. Neprováděj žádné změny.") -> dict:
    """Run unmodified upstream AIAgent's native multi-turn/tool-execution loop.

    Only an explicitly isolated, credential-free offline smoke worker may call
    this entry point. It is not a production runtime launcher or a fake agent.
    """
    from urllib.parse import urlsplit
    parsed = urlsplit(base_url)
    if (os.environ.get("HADS_ISOLATED_TEST") != "1" or parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1" or not parsed.port):
        raise RuntimeError("Hermes production launch disabled: isolated worker required")
    if not 2 <= max_iterations <= 6:
        raise ValueError("Invalid investigation budget")
    status = Path('/proc/self/status').read_text()
    flags = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    interfaces = {p.name for p in Path('/sys/class/net').iterdir()}
    readonly_root = any(line.split()[1] == '/' and 'ro' in line.split()[3].split(',')
                        for line in Path('/proc/mounts').read_text().splitlines())
    if (os.geteuid() == 0 or flags.get('NoNewPrivs', '').strip() != '1'
            or int(flags.get('CapEff', '1').strip(), 16) != 0
            or interfaces != {'lo'} or not readonly_root):
        raise RuntimeError("Offline worker OS isolation is not active")
    if Path('/opt/hermes/HADS_PINNED_REVISION').read_text().strip() != HERMES_REVISION:
        raise RuntimeError("Hermes runtime revision does not match the audited pin")
    from tools.registry import registry
    from run_agent import AIAgent

    def read_handler(args, **_):
        try:
            return gateway.read(args)
        except ReadDenied as exc:
            return json.dumps({"error": str(exc)})

    registry.register(name="hads_read_evidence", toolset="hads_evidence",
                      schema=gateway.schema, handler=read_handler)
    agent = AIAgent(base_url=base_url, api_key="offline-test-only", provider="custom",
                    api_mode="chat_completions", model=model,
                    enabled_toolsets=["hads_evidence"], max_iterations=max_iterations,
                    max_tokens=512, save_trajectories=False, quiet_mode=True,
                    skip_memory=True, skip_context_files=True, skip_background_review=True,
                    checkpoints_enabled=False, run_budget_seconds=90)
    try:
        actual = {t["function"]["name"] for t in agent.tools}
        if actual != {"hads_read_evidence"}:
            raise RuntimeError("Unexpected Hermes tools: refusing execution: " + ",".join(sorted(actual)))
        agent.compression_enabled = False
        agent._disable_streaming = True
        agent._skip_mcp_refresh = True
        agent._api_max_retries = 1
        agent._auto_recovery_cycles = 0
        agent._try_recover_primary_transport = lambda *a, **k: False
        agent._try_activate_fallback = lambda *a, **k: False
        agent._persist_disabled = True
        result = agent.run_conversation(prompt)
        if not isinstance(result, dict) or result.get("completed") is not True:
            raise RuntimeError("Hermes investigation did not complete")
        return {"engine": "NousResearch/hermes-agent", "revision": HERMES_REVISION,
                "completed": True, "read_receipts": gateway.receipts,
                "snapshot_sha256": gateway.snapshot_sha256,
                "summary_cs": result.get("final_response", ""),
                "execution_authority": "none", "scope": "offline-container"}
    finally:
        agent.close()
