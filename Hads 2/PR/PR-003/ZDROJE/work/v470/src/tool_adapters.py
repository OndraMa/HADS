from __future__ import annotations

import hashlib
import datetime as dt
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


ADAPTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_adapters (
    adapter_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    available INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 0,
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    discovery_json TEXT NOT NULL DEFAULT '{}',
    last_ok_at TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adapter_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adapter_id TEXT NOT NULL,
    root_case_id INTEGER,
    case_id INTEGER,
    evidence_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    confidence INTEGER NOT NULL DEFAULT 50,
    collected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_adapter_evidence_case ON adapter_evidence(case_id,collected_at DESC);
"""


SPECS = {
    "native_ha": {"title": "Home Assistant / Supervisor", "patterns": (), "potential": ("states", "services", "repairs", "registries", "addons", "logs", "yaml")},
    "ha_mcp": {"title": "HA-MCP", "patterns": ("ha-mcp", "ha_mcp", "hamcp"), "potential": ("llm_api", "system_health", "repairs", "automation_trace", "registries")},
    "haghs": {"title": "Home Assistant Global Health Score", "patterns": ("haghs", "global health score", "ha-pulse"), "potential": ("health_score", "hardware_score", "application_score", "pressure_trends")},
    "hadocs": {"title": "HADocs", "patterns": ("hadocs",), "potential": ("root_causes", "recommendations", "potential_health", "dependency_explorer")},
    "hamster_mcp": {"title": "Hamster MCP", "patterns": ("hamster", "hamster_mcp"), "potential": ("llm_api", "system_health", "repairs", "automation_trace", "entity_dependencies")},
    "spook": {"title": "Spook", "patterns": ("spook",), "potential": ("repairs", "entity_references", "automation_references", "scene_references")},
    "watchman": {"title": "Watchman", "patterns": ("watchman",), "potential": ("entity_references", "service_references", "yaml_reference_audit")},
    "automation_inspector": {"title": "Automation Inspector", "patterns": ("automation inspector", "automation_inspector"), "potential": ("automation_audit", "script_audit", "dependency_map", "automation_trace", "native_validation")},
    "entity_availability": {"title": "Entity Availability", "patterns": ("entity availability", "entity_availability"), "potential": ("offline_entities", "stale_entities", "availability_history", "mtbf", "mttr", "signal", "battery")},
    "codex_terminal_pro": {"title": "Codex Terminal Pro", "patterns": ("codex terminal pro", "codex_terminal_pro"), "potential": ("manual_recovery_workspace", "change_desk", "developer_tools")},
}

SENSITIVE_KEY = re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key|credential|authorization|private[_-]?key)")


def _sanitize(value: Any, key: str = "") -> Any:
    if SENSITIVE_KEY.search(key):
        return "**REDACTED**"
    if isinstance(value, dict):
        return {str(child_key): _sanitize(child, str(child_key)) for child_key, child in value.items()}
    if isinstance(value, list):
        return [_sanitize(child, key) for child in value]
    if isinstance(value, str):
        return re.sub(r"https?://[^\s\"']+", "[URL REDACTED]", value) if any(token in value.lower() for token in ("private_", "token=", "access_token")) else value
    return value


def _safe_error(value: Any) -> str:
    text = str(value)
    text = re.sub(r"https?://[^\s]+", "[URL REDACTED]", text)
    return text[:500]


def _json(value: Any, default: Any) -> Any:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return default if parsed is None else parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _row(value: Any) -> dict[str, Any]:
    return {key: value[key] for key in value.keys()}


def _strings(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            result.extend(_strings(child))
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            result.extend(_strings(child))
    elif value is not None:
        text = str(value).strip()
        if text:
            result.append(text)
    return result


class ToolAdapterBus:
    """Bridge only to diagnostics that Home Assistant demonstrably exposes.

    ``available`` means installed/found, ``connector_ready`` means queryable,
    and ``active`` means concrete data were consumed. Potential capabilities
    are never shown as already-used capabilities.
    """

    def __init__(
        self,
        db: Callable[[], Any],
        now: Callable[[], str],
        supervisor_request: Callable[..., Any],
        ha_ws_read: Callable[[str], Any],
        config_root: Callable[[], Path | None],
        options: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.db = db
        self.now = now
        self.supervisor_request = supervisor_request
        self.ha_ws_read = ha_ws_read
        self.config_root = config_root
        self.options = options or (lambda: {})
        self._runtime: dict[str, Any] | None = None
        self._public_snapshot: dict[str, Any] | None = None
        self._mcp_sessions: dict[str, str] = {}
        self._http_last_good: dict[str, tuple[Any, dict[str, str], str]] = {}
        self._http_transport: dict[str, dict[str, Any]] = {}
        self._refresh_lock = threading.RLock()
        self._background_refresh_started = False
        self._last_refresh_monotonic = 0.0

    def init_schema(self) -> None:
        with self.db() as conn:
            conn.executescript(ADAPTER_SCHEMA)
            # The captain explicitly removed Home Assistant Digest.  Delete its
            # persisted status/evidence as well, otherwise an old DB row would
            # keep the card visible after an upgrade.
            conn.execute("DELETE FROM adapter_evidence WHERE adapter_id='homeassistant_digest'")
            conn.execute("DELETE FROM tool_adapters WHERE adapter_id='homeassistant_digest'")

    @staticmethod
    def _service_names(services: Any) -> set[str]:
        result: set[str] = set()
        if not isinstance(services, list):
            return result
        for domain in services:
            if not isinstance(domain, dict):
                continue
            name = str(domain.get("domain") or "")
            raw_services = domain.get("services") or {}
            for service in raw_services.keys() if isinstance(raw_services, dict) else []:
                result.add(f"{name}.{service}".lower())
        return result

    @staticmethod
    def _state_index(states: Any) -> list[dict[str, Any]]:
        return [item for item in states if isinstance(item, dict) and item.get("entity_id")] if isinstance(states, list) else []

    @staticmethod
    def _issue_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            value = value.get("issues")
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _api_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            value = value.get("apis")
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def _watchman_reports(self) -> list[dict[str, Any]]:
        root = self.config_root()
        reports: list[dict[str, Any]] = []
        if not root:
            return reports
        for name in ("watchman_report.txt", ".watchman_report.txt", "watchman_report.json", "watchman_report.yaml"):
            path = root / name
            try:
                if path.is_file() and not path.is_symlink() and path.stat().st_size <= 2_000_000:
                    stamp = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
                    age = (dt.datetime.fromisoformat(self.now()) - stamp).total_seconds()
                    reports.append({"path": name, "content": path.read_text(encoding="utf-8", errors="replace")[:200_000], "observed_at": stamp.isoformat(timespec="seconds"), "stale": age > 86400})
            except OSError:
                continue
        return reports

    @staticmethod
    def _watchman_service_payload(value: Any) -> dict[str, Any] | None:
        """Locate Watchman 0.8.4 detailed service data in HA response wrappers."""
        if isinstance(value, dict):
            if isinstance(value.get("missing_entities"), list) and isinstance(value.get("missing_actions"), list):
                return value
            for child in value.values():
                found = ToolAdapterBus._watchman_service_payload(child)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = ToolAdapterBus._watchman_service_payload(child)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _matches(patterns: tuple[str, ...], text: str) -> bool:
        normalized = text.lower().replace("-", "_")
        return bool(patterns) and any(pattern.replace("-", "_") in normalized for pattern in patterns)

    def _http_json(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        token: str = "",
        extra_headers: dict[str, str] | None = None,
        timeout: int = 20,
    ) -> tuple[Any, dict[str, str]]:
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("Konektor vyžaduje HTTP(S) URL.")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if extra_headers:
            headers.update(extra_headers)
        safe_read = method.upper() == "GET" and payload is None
        delays = (0.0, 0.20, 0.65, 1.40) if safe_read else (0.0,)
        last_error: Exception | None = None
        raw = ""
        response_headers: dict[str, str] = {}
        for attempt, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            request = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read(5_000_000).decode("utf-8", errors="replace")
                    response_headers = {key.lower(): value for key, value in response.headers.items()}
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if not safe_read or exc.code not in {502, 503, 504}:
                    raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if not safe_read:
                    raise
        else:
            cached = self._http_last_good.get(url)
            self._http_transport[url] = {
                "status": "temporarily_unavailable", "last_success_at": cached[2] if cached else None,
                "last_error": _safe_error(last_error or "transport error"), "stale": bool(cached),
            }
            if cached:
                value, cached_headers, _ = cached
                return json.loads(json.dumps(value)), {**cached_headers, "x-hads-stale": "true"}
            raise RuntimeError(f"Dočasně nedostupné: {_safe_error(last_error or 'transport error')}") from last_error
        if response_headers.get("content-type", "").split(";", 1)[0].strip() == "text/event-stream":
            candidates = []
            for line in raw.splitlines():
                if line.startswith("data:"):
                    candidates.append(line[5:].strip())
            raw = next((item for item in reversed(candidates) if item and item != "[DONE]"), "{}")
        value = json.loads(raw or "{}")
        if safe_read:
            observed = self.now()
            self._http_last_good[url] = (value, response_headers, observed)
            self._http_transport[url] = {"status": "ok", "last_success_at": observed, "last_error": "", "stale": False}
        return value, response_headers

    def _mcp_rpc(
        self, adapter_id: str, url: str, method: str,
        params: dict[str, Any] | None = None, *, notification: bool = False,
    ) -> Any:
        cfg = self.options()
        token = str(cfg.get(f"{adapter_id}_token") or cfg.get("homeassistant_token") or os.environ.get("SUPERVISOR_TOKEN") or "").strip()
        if adapter_id == "ha_mcp" and ":9583/" in url and not cfg.get("ha_mcp_token"):
            token = ""
        headers: dict[str, str] = {}
        if self._mcp_sessions.get(adapter_id):
            headers["Mcp-Session-Id"] = self._mcp_sessions[adapter_id]
        request_id = int(hashlib.sha256(f"{adapter_id}:{method}:{self.now()}".encode()).hexdigest()[:8], 16)
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            payload["id"] = request_id
        timeout = max(5, min(int(cfg.get("external_connector_timeout_seconds") or 30), 120))
        value, response_headers = self._http_json(url, method="POST", payload=payload, token=token, extra_headers=headers, timeout=timeout)
        session = response_headers.get("mcp-session-id")
        if session:
            self._mcp_sessions[adapter_id] = session
        if isinstance(value, dict) and value.get("error"):
            raise RuntimeError(str(value["error"])[:1000])
        return value.get("result") if isinstance(value, dict) else value

    def _mcp_initialize(self, adapter_id: str, url: str) -> dict[str, Any]:
        result: Any = {}
        try:
            result = self._mcp_rpc(adapter_id, url, "initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "HADS First Officer", "version": "1"},
            })
            try:
                # JSON-RPC notifications MUST NOT contain an id.  HA-MCP rejects
                # the request otherwise even when the later tool list happens to
                # work, which used to make the card falsely look healthy.
                self._mcp_rpc(adapter_id, url, "notifications/initialized", {}, notification=True)
            except Exception:
                pass
        except Exception as exc:
            # Hamster's HA endpoint implements the useful MCP tool methods but
            # some releases intentionally omit the optional initialize method.
            # A -32601 response must not discard a working tool catalogue.
            if "-32601" not in str(exc) and "method not found" not in str(exc).lower():
                raise
        catalog = self._mcp_rpc(adapter_id, url, "tools/list", {})
        tools = catalog.get("tools") if isinstance(catalog, dict) else []
        return {"server": result or {}, "tools": [item for item in tools if isinstance(item, dict)] if isinstance(tools, list) else []}

    @staticmethod
    def _safe_mcp_tools(catalog: dict[str, Any]) -> list[dict[str, Any]]:
        denied = ("delete", "remove", "create", "update", "set_", "write", "restore", "restart", "reload", "call_service", "auth", "user", "password", "credential", "token", "secret", "config")
        allowed = ("get", "list", "search", "diagn", "trace", "log", "health", "overview", "status", "explain", "schema")
        result = []
        for item in catalog.get("tools") or []:
            name = str(item.get("name") or "").lower()
            # Do not run a tool merely because its name contains 'repair' or
            # 'get'. Prefer explicit readOnlyHint, otherwise exact known reads.
            readonly = (item.get("annotations") or {}).get("readOnlyHint") is True
            known_read = name in {"search", "ha_search", "explain", "schema", "list_resources", "get_state", "get_states", "list_entities", "get_entity", "get_history"}
            if name and (readonly or known_read) and any(token in name for token in allowed) and not any(token in name for token in denied):
                result.append(item)
        return result

    def _mcp_probe(self, adapter_id: str, url: str) -> dict[str, Any]:
        catalog = self._mcp_initialize(adapter_id, url)
        safe = self._safe_mcp_tools(catalog)
        return {
            "url_configured": True,
            "server_info": catalog.get("server") or {},
            "tool_count": len(catalog.get("tools") or []),
            "read_only_tool_count": len(safe),
            "tools": [str(item.get("name") or "") for item in safe[:100]],
            "catalog": catalog,
        }

    def _mcp_case_evidence(self, adapter_id: str, query: str) -> dict[str, Any]:
        cfg = self.options()
        # Reuse exactly the same discovery path as the capability probe. Earlier
        # builds could mark a connector ready and then fail to use it for a case
        # because case research fell back to a different hard-coded URL.
        url = self._auto_mcp_urls(cfg).get(adapter_id, "")
        if not url:
            return {}
        probe = self._mcp_probe(adapter_id, url)
        catalog = probe.get("catalog") or {}
        safe_tools = self._safe_mcp_tools(catalog)
        candidates = []
        words = set(re.findall(r"[a-z0-9_]{3,}", query.lower()))
        for item in safe_tools:
            name = str(item.get("name") or "")
            description = str(item.get("description") or "")
            score = sum(1 for word in words if word in f"{name} {description}".lower())
            if name in {"search", "ha_search"}:
                score += 20
            candidates.append((score, item))
        candidates.sort(key=lambda pair: (-pair[0], str(pair[1].get("name") or "")))
        outputs = []
        for _, item in candidates[:3]:
            schema = item.get("inputSchema") if isinstance(item.get("inputSchema"), dict) else {}
            properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            required = schema.get("required") if isinstance(schema.get("required"), list) else []
            arguments: dict[str, Any] = {}
            supported = True
            for name in required:
                prop = properties.get(name) if isinstance(properties.get(name), dict) else {}
                if prop.get("type") == "string" and name.lower() in {"query", "text", "keyword", "search", "command", "name"}:
                    arguments[name] = "hass/get_states" if adapter_id == "hamster_mcp" else query[:1000]
                elif prop.get("type") == "string" and name.lower() == "path" and re.fullmatch(r"[a-z0-9_./-]{3,200}", query.strip().lower()):
                    arguments[name] = query.strip().lower()
                elif prop.get("default") is not None:
                    arguments[name] = prop["default"]
                else:
                    supported = False
                    break
            if not supported:
                continue
            try:
                result = self._mcp_rpc(adapter_id, url, "tools/call", {"name": item.get("name"), "arguments": arguments})
                outputs.append({"tool": item.get("name"), "arguments": _sanitize(arguments), "result": _sanitize(result)})
            except Exception as exc:
                outputs.append({"tool": item.get("name"), "error": _safe_error(exc)})
        # Hamster exposes a meta catalogue: search first, then schema/explain,
        # and finally execute only a narrowly allow-listed HA read.  Generic
        # ``call`` stays excluded from _safe_mcp_tools so annotations cannot
        # silently turn a write into an investigation step.
        if adapter_id == "hamster_mcp":
            discovered: list[str] = []
            for output in outputs:
                discovered.extend(self._mcp_paths(output.get("result")))
            path = next((item for item in discovered if self._safe_hamster_read_path(item)), "")
            names = {str(item.get("name") or ""): item for item in (catalog.get("tools") or []) if isinstance(item, dict)}
            if path:
                for tool_name in ("schema", "explain"):
                    if tool_name in names:
                        try:
                            result = self._mcp_rpc(adapter_id, url, "tools/call", {"name": tool_name, "arguments": {"path": path}})
                            outputs.append({"tool": tool_name, "arguments": {"path": path}, "result": _sanitize(result)})
                        except Exception as exc:
                            outputs.append({"tool": tool_name, "arguments": {"path": path}, "error": _safe_error(exc)})
                if "call" in names:
                    try:
                        result = self._mcp_rpc(adapter_id, url, "tools/call", {"name": "call", "arguments": {"path": path, "arguments": {}}})
                        outputs.append({"tool": "call", "arguments": {"path": path, "arguments": {}}, "result": _sanitize(result)})
                    except Exception as exc:
                        outputs.append({"tool": "call", "arguments": {"path": path, "arguments": {}}, "error": _safe_error(exc)})
        return {"probe": {key: value for key, value in probe.items() if key != "catalog"}, "query": query, "outputs": outputs}

    @staticmethod
    def _mcp_paths(value: Any) -> list[str]:
        paths: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"path", "command", "name"} and isinstance(child, str):
                    paths.append(child.strip().lower())
                paths.extend(ToolAdapterBus._mcp_paths(child))
        elif isinstance(value, list):
            for child in value:
                paths.extend(ToolAdapterBus._mcp_paths(child))
        elif isinstance(value, str):
            paths.extend(re.findall(r"\b(?:hass|supervisor)/[a-z0-9_./-]+", value.lower()))
        return list(dict.fromkeys(item for item in paths if item))[:20]

    @staticmethod
    def _safe_hamster_read_path(path: str) -> bool:
        normalized = str(path or "").strip().lower()
        # An MCP command without a dangerous-looking word is not necessarily
        # read-only (fire_event, automation/trigger, etc.). Enumerate reads.
        return normalized in {
            "hass/get_states", "hass/get_services", "hass/get_config",
            "hass/config/entity_registry/list", "hass/config/device_registry/list",
            "hass/config/area_registry/list", "hass/config_entries/get",
            "hass/repairs/list_issues", "hass/system_log/list",
        }

    def _json_connector(self, url: str, token: str = "") -> Any:
        timeout = max(5, min(int(self.options().get("external_connector_timeout_seconds") or 30), 120))
        value, headers = self._http_json(url, token=token, timeout=timeout)
        if headers.get("x-hads-stale") == "true" or headers.get("x-automation-inspector-stale") == "true":
            raise RuntimeError("Dočasně nedostupné; poslední data jsou historická, spojení nebylo ověřeno.")
        return value

    def _addon_json_candidates(self, adapter_id: str) -> list[str]:
        """Return private in-network API candidates for an installed HA app.

        Automation Inspector and HADocs expose their useful JSON through their
        app web process. Their host port may deliberately be unpublished; a
        manager app can still use the Supervisor-reported container address and
        ingress port without weakening authentication or exposing a LAN port.
        """
        paths = {
            "automation_inspector": (1234, ("api/v1/inspection", "dependency_map.json")),
            "hadocs": (8099, ("api/summary", "api/status", "api/health")),
        }
        if adapter_id not in paths:
            return []
        try:
            addons = self.supervisor_request("/addons", timeout=20)
            data = addons.get("data", addons) if isinstance(addons, dict) else addons
            rows = data.get("addons", data) if isinstance(data, dict) else data
            rows = rows if isinstance(rows, list) else []
            patterns = tuple(SPECS[adapter_id]["patterns"])
            candidate = next((item for item in rows if isinstance(item, dict) and self._matches(patterns, " ".join(str(item.get(key) or "") for key in ("slug", "name", "description")))), None)
            if not candidate:
                return []
            slug = str(candidate.get("slug") or "")
            info = self.supervisor_request(f"/addons/{urllib.parse.quote(slug)}/info", timeout=20)
            payload = info.get("data", info) if isinstance(info, dict) else {}
            payload = payload if isinstance(payload, dict) else {}
            default_port, suffixes = paths[adapter_id]
            port = int(payload.get("ingress_port") or default_port)
            hosts = []
            for raw in (payload.get("ip_address"), payload.get("hostname"), slug):
                host = str(raw or "").strip().replace("_", "-")
                if host and host not in hosts:
                    hosts.append(host)
            return [f"http://{host}:{port}/{suffix}" for host in hosts for suffix in suffixes]
        except Exception:
            return []

    def _auto_json_connector(self, adapter_id: str, explicit_url: str, token: str) -> tuple[Any, str]:
        candidates = [explicit_url] if explicit_url else self._addon_json_candidates(adapter_id)
        errors: list[str] = []
        for url in candidates:
            try:
                value = self._json_connector(url, token)
                diagnostic_keys = {"inspection", "issues", "findings", "problems", "warnings", "errors", "recommendations", "root_causes", "automations", "dependency_map", "entities", "analysis"}
                if not any(diagnostic_keys.intersection(item) for _, item in self._walk_json(value)):
                    raise ValueError("Rozhraní odpovídá, ale nevrací rozpoznaný diagnostický výstup. Health endpoint není report nálezů.")
                return value, ""
            except Exception as exc:
                errors.append(_safe_error(exc))
        return None, (errors[-1] if errors else "")

    def _discover_ha_mcp_url(self) -> str:
        """Discover HA-MCP add-on locally; never expose its secret path in public status."""
        try:
            addons = self.supervisor_request("/addons", timeout=20)
            # supervisor_request() normally unwraps the outer {data: ...}.
            # Accept both wrapped and already-unwrapped shapes; the previous
            # double unwrap turned a valid {addons: [...]} response into None.
            data = addons.get("data", addons) if isinstance(addons, dict) else addons
            rows = data.get("addons", data) if isinstance(data, dict) else data
            rows = rows if isinstance(rows, list) else []
            candidate = next((item for item in rows if isinstance(item, dict) and "ha_mcp" in str(item.get("slug") or "").lower()), None)
            if not candidate:
                return ""
            slug = str(candidate.get("slug") or "")
            info = self.supervisor_request(f"/addons/{slug}/info", timeout=20)
            payload = info.get("data") if isinstance(info, dict) and isinstance(info.get("data"), dict) else info
            options_value = payload.get("options") if isinstance(payload, dict) else {}
            secret_path = str((options_value or {}).get("secret_path") or "").strip().strip("/")
            if not secret_path:
                # Current HA-MCP often auto-generates the secret into its data
                # directory without reflecting it in Supervisor options.  Its
                # own documentation tells users to obtain the URL from logs;
                # use the same read-only fallback and never publish the path.
                log_text = ""
                for endpoint in (
                    f"/addons/{urllib.parse.quote(slug)}/logs/latest?lines=800&no_colors",
                    f"/addons/{urllib.parse.quote(slug)}/logs",
                ):
                    try:
                        log_text = str(self.supervisor_request(endpoint, raw=True, timeout=20) or "")
                        if log_text:
                            break
                    except Exception:
                        continue
                log_text = re.sub(r"\x1b\[[0-9;]*m", "", log_text)
                match = re.search(r"/(private_[A-Za-z0-9_-]{8,})", log_text)
                if match:
                    secret_path = match.group(1)
            if not secret_path:
                return ""
            # Home Assistant's internal app DNS supports the generated app name/alias,
            # including host-network apps. DNS names replace underscores with dashes.
            # Supervisor may return the repository slug (with underscores) in
            # ``hostname``. Underscores are not valid in the internal DNS host
            # label used by Home Assistant apps; the actual alias uses dashes.
            hostname = str(payload.get("hostname") or slug).strip().replace("_", "-")
            return f"http://{hostname}:9583/{secret_path}"
        except Exception:
            return ""

    def _auto_mcp_urls(self, cfg: dict[str, Any]) -> dict[str, str]:
        # Hamster is a HA integration with a documented /api/hamster_mcp endpoint.
        # Going through Supervisor's Core proxy lets the app use SUPERVISOR_TOKEN.
        hamster = str(cfg.get("hamster_mcp_url") or "").strip() or "http://supervisor/core/api/hamster_mcp"
        ha_mcp = str(cfg.get("ha_mcp_url") or "").strip() or self._discover_ha_mcp_url()
        return {"ha_mcp": ha_mcp, "hamster_mcp": hamster}

    def _persist_adapter_rows(self, rows: list[tuple[Any, ...]]) -> str:
        """Short write transaction with bounded retry; UI must not 500 on SQLite contention."""
        if not rows:
            return ""
        error = ""
        for delay in (0.0, 0.15, 0.4, 0.8, 1.5, 2.5):
            if delay:
                time.sleep(delay)
            try:
                with self.db() as conn:
                    conn.executemany(
                        """INSERT INTO tool_adapters(adapter_id,title,available,active,capabilities_json,discovery_json,last_ok_at,last_error,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(adapter_id) DO UPDATE SET title=excluded.title,available=excluded.available,
                           active=excluded.active,capabilities_json=excluded.capabilities_json,discovery_json=excluded.discovery_json,
                           last_ok_at=COALESCE(excluded.last_ok_at,tool_adapters.last_ok_at),last_error=excluded.last_error,updated_at=excluded.updated_at""", rows
                    )
                return ""
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                error = str(exc)
        return error or "database is locked"

    def refresh(self, force: bool = False) -> dict[str, Any]:
        with self._refresh_lock:
            return self._refresh_unlocked(force)

    @staticmethod
    def _watchman_request_body(service_rows: Any) -> dict[str, Any]:
        for domain in service_rows if isinstance(service_rows, list) else []:
            if not isinstance(domain, dict) or domain.get("domain") != "watchman":
                continue
            report = (domain.get("services") or {}).get("report") or {}
            fields = report.get("fields") if isinstance(report, dict) else {}
            fields = fields if isinstance(fields, dict) else {}
            # Negotiate the installed service, not a version guessed from docs.
            key = "force_parsing" if "force_parsing" in fields else "parse_config" if "parse_config" in fields else ""
            if key:
                return {"create_file": False, key: True}
        raise ValueError("Watchman nezveřejnil podporovaný parametr nového parsování; čerstvé parsování nebylo potvrzeno.")

    def _refresh_unlocked(self, force: bool = False) -> dict[str, Any]:
        if self._runtime is not None and self._public_snapshot is not None and not force and time.monotonic() - self._last_refresh_monotonic < 120:
            return self._public_snapshot
        errors: dict[str, str] = {}
        try:
            states = self._state_index(self.supervisor_request("/core/api/states", timeout=45))
            states_ok = True
        except Exception as exc:
            states, states_ok = [], False
            errors["states"] = str(exc)[:500]
        try:
            service_rows = self.supervisor_request("/core/api/services", timeout=45)
            services = self._service_names(service_rows)
            services_ok = True
        except Exception as exc:
            services, services_ok = set(), False
            errors["services"] = str(exc)[:500]
        try:
            issues = self._issue_list(self.ha_ws_read("repairs/list_issues"))
            repairs_ok = True
        except Exception as exc:
            issues, repairs_ok = [], False
            errors["repairs"] = str(exc)[:500]
        active_issues = [item for item in issues if not bool(item.get("ignored"))]
        try:
            loaded = self.supervisor_request("/core/api/components", timeout=20)
            loaded_components = {str(item) for item in loaded} if isinstance(loaded, list) else set()
        except Exception as exc:
            loaded_components = set()
            errors["components"] = _safe_error(exc)
        try:
            llm_apis = self._api_list(self.ha_ws_read("llm/api/list"))
        except Exception as exc:
            llm_apis = []
            errors["llm_api"] = str(exc)[:500]
        try:
            entity_registry_raw = self.ha_ws_read("config/entity_registry/list")
            entity_registry = [item for item in entity_registry_raw if isinstance(item, dict)] if isinstance(entity_registry_raw, list) else []
        except Exception as exc:
            entity_registry = []
            errors["entity_registry"] = str(exc)[:500]
        structured_watchman: dict[str, Any] | None = None
        if force and "watchman.report" in services:
            try:
                response = self.supervisor_request(
                    "/core/api/services/watchman/report?return_response",
                    method="POST",
                    body=self._watchman_request_body(service_rows),
                    timeout=90,
                )
                structured_watchman = self._watchman_service_payload(response)
                if structured_watchman is None:
                    errors["watchman_report"] = "Watchman odpověděl bez podrobného service_response."
            except Exception as exc:
                errors["watchman_report"] = str(exc)[:500]
        reports = self._watchman_reports()
        if structured_watchman is not None:
            reports.insert(0, {
                "path": "service_response", "structured": structured_watchman,
                "observed_at": self.now(), "stale": False,
            })
        # A fresh service response and the report TXT describe the same Watchman
        # defects in two representations. Prefer the typed response for findings;
        # keep the file only as connector/provenance evidence when no typed result
        # is available, otherwise one missing reference would become two cases.
        current_reports = [report for report in reports if not report.get("stale")]
        structured_reports = [report for report in current_reports if isinstance(report.get("structured"), dict)]
        watchman_analysis_reports = structured_reports or current_reports
        cfg = self.options()
        explicit_mcp_urls = {
            "ha_mcp": str(cfg.get("ha_mcp_url") or "").strip(),
            "hamster_mcp": str(cfg.get("hamster_mcp_url") or "").strip(),
        }
        connector_data: dict[str, Any] = {}
        connector_errors: dict[str, str] = {}
        # Auto-discover local diagnostic runtimes first; explicit URLs still win.
        # This is an orchestrator: if a tool is installed and queryable, HADS should
        # use it without forcing the captain to manually duplicate its endpoint.
        mcp_urls = self._auto_mcp_urls(cfg)
        for adapter_id, url in mcp_urls.items():
            if not url:
                continue
            try:
                connector_data[adapter_id] = self._mcp_probe(adapter_id, url)
            except Exception as exc:
                connector_errors[adapter_id] = _safe_error(exc)
        json_connectors = {
            "automation_inspector": (
                str(cfg.get("automation_inspector_api_url") or "").strip(),
                str(cfg.get("automation_inspector_token") or "").strip(),
            ),
            "hadocs": (
                str(cfg.get("hadocs_api_url") or "").strip(),
                str(cfg.get("hadocs_token") or "").strip(),
            ),
        }
        for adapter_id, (url, token) in json_connectors.items():
            value, error = self._auto_json_connector(adapter_id, url, token)
            if value is not None:
                connector_data[adapter_id] = value
            elif error:
                connector_errors[adapter_id] = error

        with self.db() as conn:
            inventory = [_row(row) for row in conn.execute("SELECT * FROM inventory").fetchall()]
            previous_adapters = {str(row["adapter_id"]): _row(row) for row in conn.execute("SELECT * FROM tool_adapters").fetchall()}
        inventory_text = [" ".join(str(item.get(key) or "") for key in ("item_key", "item_type", "name", "metadata_json")).lower() for item in inventory]
        # Installed inventory is not a functional probe. Fetch current app states
        # independently; integration sensors cannot prove an app is running.
        try:
            addon_payload = self.supervisor_request("/addons", timeout=20)
            live_addons = addon_payload.get("addons", []) if isinstance(addon_payload, dict) else []
        except Exception as exc:
            live_addons = []
            errors["addons"] = _safe_error(exc)
        state_hay = {str(item["entity_id"]).lower(): " ".join((str(item["entity_id"]), str((item.get("attributes") or {}).get("friendly_name") or ""))).lower() for item in states}
        api_hay = {str(item.get("id") or ""): f"{item.get('id', '')} {item.get('name', '')}".lower() for item in llm_apis}
        results: dict[str, Any] = {}
        persistence_rows: list[tuple[Any, ...]] = []

        for adapter_id, spec in SPECS.items():
            patterns = tuple(spec["patterns"])
            inventory_hit_rows = [item for item, value in zip(inventory, inventory_text) if self._matches(patterns, value)]
            inventory_hits = [value for value in inventory_text if self._matches(patterns, value)]
            entity_hits = [entity_id for entity_id, value in state_hay.items() if self._matches(patterns, value)]
            if adapter_id == "haghs":
                haghs_registry_ids = {
                    str(row.get("entity_id") or "").lower() for row in entity_registry
                    if str(row.get("platform") or "").lower() == "haghs"
                }
                entity_hits = [entity_id for entity_id in state_hay if entity_id in haghs_registry_ids or entity_id == "sensor.system_ha_global_health_score" or entity_id.startswith("sensor.haghs_")]
            elif adapter_id == "entity_availability":
                entity_hits = [entity_id for entity_id in state_hay if entity_id.startswith(("sensor.entity_availability_", "binary_sensor.entity_availability_"))]
            service_hits = [service for service in services if self._matches(patterns, service)]
            api_hits = [api_id for api_id, value in api_hay.items() if self._matches(patterns, value)]
            repair_hits = [item for item in active_issues if adapter_id == "spook" and str(item.get("domain") or "").lower() == "spook"]
            report_hits = watchman_analysis_reports if adapter_id == "watchman" else []
            connected_payload = connector_data.get(adapter_id)
            configured = bool(explicit_mcp_urls.get(adapter_id) or (json_connectors.get(adapter_id) or ("", ""))[0])
            # Inventory contains historic log sources as well as the current HA
            # inventory.  It therefore cannot prove that a companion add-on is
            # still installed; it previously made a removed Codex Terminal Pro
            # look current.  Keep it as provenance, but claim current presence
            # only when there is a live HA/API signal.
            matched_addons = [
                addon for addon in live_addons
                if isinstance(addon, dict) and self._matches(patterns, f"{addon.get('slug', '')} {addon.get('name', '')}")
            ]
            historical_seen = bool(inventory_hits)
            component_hit = adapter_id in loaded_components
            live_signals = bool(component_hit or matched_addons or entity_hits or service_hits or api_hits or repair_hits or report_hits or connected_payload is not None)
            if adapter_id == "codex_terminal_pro":
                # An orphaned update entity is not proof an add-on still exists.
                live_signals = bool(matched_addons)
            installed = adapter_id == "native_ha" or live_signals
            connector_ready = False
            data_used = False
            actual: list[str] = []
            findings_count = 0
            if adapter_id == "native_ha":
                connector_ready = states_ok or services_ok or repairs_ok
                data_used = connector_ready
                if states_ok:
                    actual.append("states")
                if services_ok:
                    actual.append("services")
                if repairs_ok:
                    actual.append("repairs/list_issues")
                findings_count = sum(1 for item in active_issues if str(item.get("domain") or "").lower() != "spook")
            elif adapter_id == "spook":
                connector_ready = installed and repairs_ok
                findings_count = len(repair_hits)
                # A fresh, empty Repairs result is still real diagnostic data.
                data_used = connector_ready
                if connector_ready:
                    actual.append("repairs/list_issues")
            elif adapter_id == "watchman":
                connector_ready = bool(report_hits)
                known_entities = set(state_hay) | {str(item.get("entity_id") or "").lower() for item in entity_registry}
                findings_count = len(self._watchman_findings(report_hits, known_entities, services))
                data_used = bool(report_hits)
                actual.extend(f"report:{item['path']}" for item in report_hits)
                actual.extend(f"service:{name}" for name in service_hits)
            elif adapter_id in {"ha_mcp", "hamster_mcp"}:
                connector_ready = isinstance(connected_payload, dict) and int(connected_payload.get("tool_count") or 0) > 0
                data_used = False
                findings_count = 0
                actual.extend(f"mcp_tool:{name}" for name in (connected_payload or {}).get("tools", [])[:100])
            elif adapter_id in {"automation_inspector", "hadocs"}:
                connector_ready = connected_payload is not None
                data_used = connector_ready
                findings_count = len(self._automation_inspector_findings(connected_payload) if adapter_id == "automation_inspector" else self._generic_json_findings(adapter_id, connected_payload)) if connector_ready else 0
                if connector_ready:
                    actual.append("json_api")
            else:
                usable_hits = [item for item in states if str(item.get("entity_id") or "").lower() in entity_hits and not str(item.get("entity_id") or "").startswith("update.") and str(item.get("state") or "").lower() not in {"", "unknown", "unavailable"}]
                connector_ready = bool(usable_hits)
                data_used = bool(usable_hits)
                actual.extend(f"entity:{name}" for name in entity_hits)
                actual.extend(f"service:{name}" for name in service_hits)
                actual.extend(f"llm_api:{name}" for name in api_hits)
                if adapter_id == "haghs":
                    numeric = 0
                    for item in states:
                        if str(item.get("entity_id") or "").lower() not in entity_hits:
                            continue
                        try:
                            float(item.get("state"))
                            numeric += 1
                        except (TypeError, ValueError):
                            pass
                    data_used = numeric > 0
                    findings_count = numeric
                elif adapter_id == "entity_availability":
                    finding_entities = self._entity_availability_findings(states)
                    findings_count = len(finding_entities)
                    data_used = bool(usable_hits)
                    connector_ready = bool(usable_hits)
                    if connector_ready:
                        actual.append("entity_state_attributes")
                elif adapter_id == "codex_terminal_pro":
                    # These are useful companion/developer applications, but
                    # they expose no verified machine-readable feed to HADS.
                    data_used = False
                    connector_ready = False
            adapter_error = connector_errors.get(adapter_id, "")
            if adapter_id == "spook" and installed and not repairs_ok:
                adapter_error = errors.get("repairs", "")
            elif adapter_id == "ha_mcp" and installed and not mcp_urls.get("ha_mcp"):
                adapter_error = "HA-MCP běží, ale secret path nebyl nalezen v options ani v logu add-onu."
            previous = previous_adapters.get(adapter_id, {})
            live_states = []
            for addon in matched_addons:
                try:
                    info = self.supervisor_request(f"/addons/{urllib.parse.quote(str(addon['slug']), safe='')}/info", timeout=20)
                    live_states.append(str(info.get("state") or ""))
                except Exception as exc:
                    adapter_error = _safe_error(exc)
            running = all(s == "started" for s in live_states) if live_states and len(live_states) == len(matched_addons) else None
            last_success_at = self.now() if connector_ready else previous.get("last_ok_at")
            if adapter_id == "watchman" and report_hits:
                last_success_at = max(str(r.get("observed_at") or "") for r in report_hits) or last_success_at
            last_used_at = self.now() if data_used else (_json(previous.get("discovery_json"), {}).get("last_used_at") if previous else None)
            discovery = {
                "installed": installed,
                "current_presence": "confirmed" if installed else "not_confirmed",
                "historical_seen": historical_seen,
                "loaded_component": component_hit,
                "running": running,
                "connector_ready": connector_ready,
                "connection_verified": connector_ready,
                "last_success_at": last_success_at,
                "last_used_at": last_used_at,
                "data_used": data_used,
                "findings_count": findings_count,
                "functional_state": "findings_present" if findings_count else ("no_findings_reported" if connector_ready else "unverified"),
                "status_note": "Spojení se zdrojem není důkaz bezchybné funkce doplňku. Nulový počet nálezů znamená pouze nulový výstup dostupného rozhraní.",
                "ignored_findings_count": sum(1 for item in issues if bool(item.get("ignored")) and (adapter_id != "spook" or str(item.get("domain") or "").lower() == "spook")),
                "inventory_matches": len(inventory_hits),
                "entities": entity_hits[:50],
                "services": service_hits[:50],
                "llm_apis": api_hits[:50],
                "verified_capabilities": actual[:100],
                "potential_capabilities": list(spec["potential"]),
                "configured": configured,
                "fallback": "native_ha" if not data_used and adapter_id != "native_ha" else None,
            }
            persistence_rows.append((adapter_id, spec["title"], int(installed), int(data_used), json.dumps(actual, ensure_ascii=False), json.dumps(discovery, ensure_ascii=False), last_success_at, adapter_error, self.now()))
            results[adapter_id] = {"available": installed, "active": data_used, "capabilities": actual, **discovery, "last_error": adapter_error}
        persistence_error = self._persist_adapter_rows(persistence_rows)
        if persistence_error:
            # Runtime result is still valid; only persistence is deferred.
            errors["adapter_persistence"] = persistence_error
        errors.update({f"connector:{key}": value for key, value in connector_errors.items()})
        self._runtime = {"states": states, "services": services, "issues": issues, "llm_apis": llm_apis, "entity_registry": entity_registry, "watchman_reports": watchman_analysis_reports, "connector_data": connector_data, "errors": errors}
        self._public_snapshot = {"adapters": results, "states": len(states), "services": len(services), "repairs": len(issues), "errors": errors}
        self._last_refresh_monotonic = time.monotonic()
        return self._public_snapshot

    def status(self) -> list[dict[str, Any]]:
        try:
            with self.db() as conn:
                rows = conn.execute("SELECT * FROM tool_adapters ORDER BY CASE adapter_id WHEN 'native_ha' THEN 0 ELSE 1 END,title").fetchall()
            result = []
            for row in rows:
                item = _row(row)
                item["available"] = bool(item["available"])
                item["active"] = bool(item["active"])
                item["capabilities"] = _json(item.pop("capabilities_json", "[]"), [])
                item["discovery"] = _json(item.pop("discovery_json", "{}"), {})
                checked_at = item.get("updated_at")
                try:
                    expired = (dt.datetime.fromisoformat(self.now()) - dt.datetime.fromisoformat(str(checked_at))).total_seconds() > 180
                except (ValueError, TypeError):
                    expired = True
                if expired:
                    item["discovery"].update(connection_verified=False, connector_ready=False, data_used=False, current_presence="not_confirmed", running=None, functional_state="unverified", stale=True)
                    item["active"] = False
                result.append(item)
            if result:
                return result
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
        snapshot = (self._public_snapshot or {}).get("adapters") or {}
        return [{"adapter_id": key, "title": SPECS.get(key, {}).get("title", key), **value} for key, value in snapshot.items()]

    def _matched_states(self, adapter_id: str, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        patterns = tuple(SPECS[adapter_id]["patterns"])
        registered_haghs = {
            str(row.get("entity_id") or "").lower()
            for row in ((self._runtime or {}).get("entity_registry") or [])
            if str(row.get("platform") or "").lower() == "haghs"
        }
        result = []
        for item in states:
            attrs = item.get("attributes") or {}
            entity_id = str(item.get("entity_id") or "").lower()
            text = " ".join((entity_id, str(attrs.get("friendly_name") or ""))).lower()
            exact = (
                adapter_id == "haghs" and (entity_id in registered_haghs or entity_id == "sensor.system_ha_global_health_score" or entity_id.startswith("sensor.haghs_"))
            ) or (
                adapter_id == "entity_availability" and entity_id.startswith(("sensor.entity_availability_", "binary_sensor.entity_availability_"))
            )
            if exact or self._matches(patterns, text):
                result.append({"entity_id": item.get("entity_id"), "state": item.get("state"), "attributes": attrs, "last_changed": item.get("last_changed")})
        return result[:100]

    @staticmethod
    def _issue_title(issue: dict[str, Any], adapter_id: str) -> tuple[str, str, list[str]]:
        placeholders = issue.get("translation_placeholders") if isinstance(issue.get("translation_placeholders"), dict) else {}
        data = issue.get("data") if isinstance(issue.get("data"), dict) else {}
        issue_id = str(issue.get("issue_id") or issue.get("translation_key") or "unknown")
        kind = f"{issue.get('translation_key', '')} {issue_id}".lower()
        values = _strings(placeholders) + _strings(data)
        identifiers: list[str] = []
        for value in values + [issue_id]:
            identifiers.extend(re.findall(r"\b[a-z_][a-z0-9_]*\.[a-z0-9_]+\b", value.lower()))
        identifiers = list(dict.fromkeys(identifiers))[:30]
        affected = str(placeholders.get("name") or placeholders.get("automation") or placeholders.get("script") or placeholders.get("scene") or placeholders.get("entity_id") or data.get("name") or issue_id)
        source = SPECS.get(adapter_id, {}).get("title", str(issue.get("domain") or "Home Assistant Repairs"))
        if "unknown_entity" in kind:
            title, noun = f"Neznámá entita použitá v: {affected}", "entitu"
        elif "unknown_device" in kind:
            title, noun = f"Neznámé zařízení použité v: {affected}", "zařízení"
        elif "unknown_service" in kind or "unknown_action" in kind:
            title, noun = f"Neznámá služba použitá v: {affected}", "službu"
        elif "orphan" in kind and ("statistic" in kind or "recorder" in kind):
            title, noun = f"Osiřelé dlouhodobé statistiky: {affected}", "statistiky bez odpovídající entity"
        elif "unused" in kind:
            title, noun = f"Pravděpodobně nepoužívaný objekt: {affected}", "nepoužívaný objekt"
        else:
            title, noun = f"{source} Repairs: {affected}", "problém"
        refs = ", ".join(identifiers) if identifiers else issue_id
        return title[:500], f"{source} hlásí {noun}: {refs}. Nález pochází přímo z Home Assistant Repairs ({issue_id})."[:12_000], identifiers

    @classmethod
    def _repair_findings(cls, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for issue in issues:
            if bool(issue.get("ignored")):
                continue
            domain = str(issue.get("domain") or "homeassistant").lower()
            adapter_id = "spook" if domain == "spook" else (domain if domain in SPECS else "native_ha")
            issue_id = str(issue.get("issue_id") or issue.get("translation_key") or hashlib.sha256(json.dumps(issue, sort_keys=True, default=str).encode()).hexdigest()[:16])
            title, message, identifiers = cls._issue_title(issue, adapter_id)
            kind = f"{issue.get('translation_key', '')} {issue_id}".lower()
            severity = str(issue.get("severity") or "warning").lower()
            priority = "P2" if severity in {"critical", "error"} else "P3"
            source_title = SPECS.get(adapter_id, {}).get("title", domain)
            cause = f"{source_title} nahlásil problém typu {issue_id}. Konkrétní příčina zatím není určena."
            solution = "Načíst podrobnosti tohoto Repairs nálezu a ověřit aktuální stav jeho vlastníka. Bez důkazů nepřipravovat změny odkazů ani mazání."
            if "drive_almost_full" in kind:
                cause = "Repairs hlásí nedostatek místa na lokálním úložišti; nejde automaticky o kvótu OneDrive."
                solution = "Ověřit konkrétní filesystem, volné místo a velikosti dat. Před úklidem připravit přesný seznam a zálohu."
            elif "server_start_failed" in kind:
                cause = "Repairs hlásí selhání startu serveru. Fáze a příčina vyžadují úplný startovací log."
                solution = "Zjistit službu, verzi, port a poslední výjimku. Nezaměňovat import, obsazený port a autentizaci."
            elif "automatic_backup_failed" in kind:
                cause = "Automatická záloha selhala; příčinu určuje konkrétní úloha a cílové úložiště."
                solution = "Ověřit ID zálohovací úlohy, lokální místo, cloudovou kvótu a oprávnění odděleně."
            elif "unknown_entity" in kind or "unknown_service" in kind:
                cause = f"{source_title} hlásí neznámý odkaz; jeho aktivní použití a identitu je třeba ověřit."
                solution = "Ověřit aktivní konfiguraci a registry; navrhnout náhradu pouze s jednoznačně doloženou identitou."
            if "orphan" in kind and ("statistic" in kind or "recorder" in kind):
                cause = "Recorder uchovává dlouhodobé statistiky pro identifikátor, ke kterému už Home Assistant nemá odpovídající entitu. Neznamená to samo o sobě poškozenou databázi."
                solution = "Nejdříve ověřit, že entita nebyla pouze přejmenována nebo dočasně nedostupná. Teprve potom připravit cílené odstranění konkrétní osiřelé statistiky přes podporované nástroje Statistik, nikdy plošné mazání databáze."
            elif "unused" in kind:
                cause = f"{source_title} označil objekt jako nepoužívaný; jde o kandidáta k úklidu, nikoli automatický pokyn ke smazání."
                solution = "Před návrhem deaktivace nebo odstranění ověřit reference v automatizacích, skriptech, scénách, dashboardech a historii použití."
            findings.append({
                "adapter_id": adapter_id,
                "integration": source_title,
                "external_id": issue_id,
                "source_ref": f"repairs:{domain}:{issue_id}",
                "title": title,
                "message": message,
                "level": "ERROR" if priority == "P2" else "WARNING",
                "priority": priority,
                "confidence": 50,
                "cause": cause,
                "solution": solution,
                "verification": "Nové čtení Repairs a pozitivní funkční test postižené komponenty; samotné zmizení issue nestačí.",
                "evidence": {"provider": source_title, "api": "repairs/list_issues", "identifiers": identifiers, "issue": issue},
            })
        return findings

    @staticmethod
    def _watchman_findings(
        reports: list[dict[str, Any]],
        known_entities: set[str] | None = None,
        known_services: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        seen: set[str] = set()
        known = {item.lower() for item in (known_entities or set())} | {item.lower() for item in (known_services or set())}
        for report in reports:
            detailed = report.get("structured") if isinstance(report.get("structured"), dict) else None
            if detailed is not None:
                for problem_kind, rows, noun in (
                    ("missing_entity", detailed.get("missing_entities"), "entita"),
                    ("missing_action", detailed.get("missing_actions"), "akce"),
                ):
                    for row in rows if isinstance(rows, list) else []:
                        if not isinstance(row, dict):
                            continue
                        identifier = str(row.get("id") or "").strip().lower()
                        if not identifier:
                            continue
                        state = str(row.get("state") or "missing").strip().lower()
                        if identifier in known and state not in {"missing", "unknown", "unavailable"}:
                            continue
                        owner = str(row.get("file") or "")
                        line = row.get("line")
                        context = str(row.get("context") or "").strip()
                        scope_uncertain = bool(re.search(r"(^|/)(?:esphome|archive|archives|backup|backups|custom_components)(/|$)", owner.lower().replace("\\", "/")))
                        role_uncertain = bool(re.fullmatch(r"condition\s*:\s*" + re.escape(identifier), context))
                        # The source location is an observation, not the identity
                        # of the defect; line movement must not create a new case.
                        canonical = f"{problem_kind}:{identifier}:{owner.lower()}"
                        if canonical in seen:
                            continue
                        seen.add(canonical)
                        findings.append({
                            "adapter_id": "watchman", "integration": "Watchman",
                            "external_id": hashlib.sha256(canonical.encode()).hexdigest()[:20],
                            "source_ref": f"watchman:{problem_kind}:{identifier}:{owner}",
                            "title": f"Watchman: {identifier} – {state}",
                            "message": f"Watchman potvrzuje stav {state}; použití je v {owner}:{line or '?'}.",
                            "level": "WARNING", "priority": "P4" if scope_uncertain or role_uncertain or state == "disabled" else ("P2" if problem_kind == "missing_action" else "P3"), "confidence": 60 if scope_uncertain or role_uncertain else 90,
                            "cause": "Heuristický nález Watchmanu. Nejde ještě o potvrzenou příčinu selhání; ověřit roli odkazu a aktivní zdroj konfigurace.",
                            "solution": ("Nejprve ověřit, zda HA tento soubor skutečně načítá; ESPHome/archiv nemusí patřit do aktivní HA konfigurace." if scope_uncertain else "Ověřit roli YAML podmínky oproti entitě; token domain.name není automaticky entity_id." if role_uncertain else "Ověřit vlastníka a přesnou referenci; náhradu připravit až s doloženým cílem. Disabled není totéž co smazané."),
                            "verification": "Čerstvý strukturovaný Watchman report už odkaz neobsahuje a dotčená funkce projde kontrolou.",
                            "evidence": {"provider": "Watchman", "problem_kind": problem_kind, "identifier": identifier, "state": state, "owner": owner, "line": line, "context": row.get("context"), "last_parse_date": detailed.get("last_parse_date"), "scope_uncertain": scope_uncertain, "role_uncertain": role_uncertain},
                        })
                continue
            for line_no, line in enumerate(str(report.get("content") or "").splitlines(), 1):
                identifiers = re.findall(r"\b[a-z_][a-z0-9_]*\.[a-z0-9_]+\b", line.lower())
                if not identifiers or len(line.strip()) < 3:
                    continue
                for identifier in identifiers:
                    # TXT reports also contain configuration filenames, not entities.
                    if identifier.rsplit(".", 1)[-1] in {"yaml", "yml", "json", "txt", "log", "py", "md"}:
                        continue
                    if identifier in known:
                        continue
                    key = f"watchman:reference:{identifier}"
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append({
                        "adapter_id": "watchman", "integration": "Watchman",
                        "external_id": hashlib.sha256(key.encode()).hexdigest()[:20],
                        "source_ref": key,
                        "title": f"Watchman: neplatný odkaz {identifier}",
                        "message": f"Watchman report {report.get('path')} řádek {line_no}: {line.strip()[:3000]}",
                        "level": "WARNING", "priority": "P3", "confidence": 92,
                        "cause": "Watchman nalezl odkaz na entitu nebo službu, která není v aktuálním runtime dostupná.",
                        "solution": "Ověřte uvedené místo konfigurace a odkaz nahraďte existující entitou/službou nebo jej odstraňte.",
                        "verification": "Po novém Watchman reportu a Deep Analysis se odkaz již neobjeví.",
                        "evidence": {"provider": "Watchman", "report": report.get("path"), "line": line_no, "identifier": identifier, "raw": line[:3000]},
                    })
                    if len(findings) >= 300:
                        return findings
        return findings

    @staticmethod
    def _walk_json(value: Any, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
        result: list[tuple[str, dict[str, Any]]] = []
        if isinstance(value, dict):
            result.append((path, value))
            for key, child in value.items():
                result.extend(ToolAdapterBus._walk_json(child, f"{path}.{key}"))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                result.extend(ToolAdapterBus._walk_json(child, f"{path}[{index}]"))
        return result

    @classmethod
    def _generic_json_findings(cls, adapter_id: str, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        source = SPECS[adapter_id]["title"]
        findings: list[dict[str, Any]] = []
        seen: set[str] = set()
        problem_path = re.compile(r"(?i)(issues?|findings?|problems?|warnings?|errors?|invalid|missing|unknown|unused|stale|orphan|recommendations?|root_?causes?|broken|unavailable)")
        healthy_statuses = {"ok", "healthy", "success", "passed", "valid", "available", "enabled", "active", "online", "resolved"}
        problem_statuses = {"error", "failed", "failure", "critical", "high", "degraded", "missing", "unavailable", "unknown", "invalid", "warning", "warn", "unused", "stale", "orphaned", "broken"}
        parent_roots: list[str] = []
        for path, item in cls._walk_json(value):
            if any(path.startswith(parent + ".") or path.startswith(parent + "[") for parent in parent_roots):
                continue
            status = str(item.get("status") or item.get("state") or item.get("severity") or item.get("level") or "").lower()
            problem = bool(item.get("problem") or item.get("needs_attention") or item.get("failed"))
            if status in problem_statuses:
                problem = True
            if status not in healthy_statuses and problem_path.search(path):
                problem = True
            messages = [str(item.get(key) or "").strip() for key in (
                "title", "name", "message", "summary", "recommendation", "remediation", "reason", "error",
                "description", "issue", "problem", "rule", "entity_id", "automation_id", "script_id",
            )]
            messages = [message for message in messages if message]
            if not problem or not messages:
                continue
            raw = " | ".join(messages)[:8000]
            stable_id = str(item.get("id") or item.get("issue_id") or item.get("fingerprint") or item.get("rule_id") or item.get("entity_id") or item.get("automation_id") or item.get("script_id") or "")
            subject = str(item.get("entity_id") or item.get("automation_id") or item.get("script_id") or item.get("device_id") or "")
            fingerprint = hashlib.sha256(f"{adapter_id}:{stable_id or path}:{subject}".encode()).hexdigest()[:24]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            if adapter_id == "hadocs" and re.search(r"(?i)root_?causes?\[\d+\]$", path):
                # One root includes its children/recommendations as evidence;
                # don't recursively re-ingest them as independent incidents.
                parent_roots.append(path)
            functional = bool(re.search(r"(?i)(automation|script|invalid target|unknown (?:entity|service|device)|will not run|cannot run|broken reference)", raw))
            priority = "P2" if status in {"critical", "error", "failed", "failure", "high"} or functional else "P3"
            recommendation = str(item.get("recommendation") or item.get("remediation") or item.get("suggestion") or "")
            findings.append({
                "adapter_id": adapter_id,
                "integration": source,
                "external_id": fingerprint,
                "source_ref": f"{adapter_id}:api:{fingerprint}",
                "title": f"{source}: {messages[0]}"[:500],
                "message": f"{source} API ({path}) hlásí: {raw}"[:12_000],
                "level": "ERROR" if priority == "P2" else "WARNING",
                "priority": priority,
                "confidence": 92,
                "cause": f"Nález poskytl přímo diagnostický engine {source}; HADS jej nekonstruoval z názvu instalace.",
                "solution": recommendation or "HADS doplní závislosti, živý stav a bezpečný opravný plán před předáním kapitánovi.",
                "verification": f"Nový výstup {source} už nález neobsahuje a dotčená funkce projde následnou kontrolou.",
                "evidence": {"provider": source, "api_path": path, "payload": _sanitize(item)},
            })
            if len(findings) >= 300:
                break
        return findings

    @staticmethod
    def _entity_availability_findings(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_problem: dict[str, dict[str, Any]] = {}
        problem_tokens = ("any_offline", "any_stale", "any_poor_signal", "any_low_battery")
        for item in states:
            entity_id = str(item.get("entity_id") or "").lower()
            if not entity_id.startswith(("sensor.entity_availability_", "binary_sensor.entity_availability_")):
                continue
            # Historical/recovered/non-essential groups do not prove an active
            # fault. Their full source snapshots remain in connector evidence.
            if any(token in entity_id for token in ("recently_", "recovered", "non_essential")):
                continue
            if str(item.get("state") or "").lower() in {"unknown", "unavailable"}:
                continue
            if entity_id.startswith("binary_sensor.") and str(item.get("state")).lower() not in {"on", "true", "1"}:
                continue
            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            buckets = {
                "offline_entities": "nedostupná",
                "stale_entities": "dlouhodobě nečinná",
                "poor_signal_entities": "má slabý signál",
                "low_battery_entities": "má nízkou baterii",
            }
            # Dedicated v0.5.0 sensors use generic ``entities`` or ``devices``
            # attributes.  Infer their typed meaning from the provider entity,
            # while group_summary continues to use the explicit bucket names.
            dedicated_key = next((key for key in buckets if key.replace("_entities", "") in entity_id), "")
            if dedicated_key and dedicated_key not in attrs:
                generic = attrs.get("entities")
                if not isinstance(generic, (list, dict)):
                    generic = attrs.get("devices")
                if isinstance(generic, (list, dict)):
                    buckets = {dedicated_key: buckets[dedicated_key], **buckets}
                    attrs = {**attrs, dedicated_key: list(generic) if isinstance(generic, dict) else generic}
            emitted = False
            for key, problem_label in buckets.items():
                raw_affected = attrs.get(key)
                affected = [str(value) for value in raw_affected] if isinstance(raw_affected, (list, dict)) else []
                for affected_entity in list(dict.fromkeys(affected))[:100]:
                    canonical = f"{key}:{affected_entity.lower()}"
                    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()[:24]
                    observation = {"entity_id": entity_id, "attributes": attrs}
                    if canonical in by_problem:
                        by_problem[canonical]["evidence"]["observations"].append(observation)
                        emitted = True
                        continue
                    by_problem[canonical] = {
                        "adapter_id": "entity_availability", "integration": "Entity Availability",
                        "external_id": fingerprint, "source_ref": f"entity_availability:{entity_id}:{key}:{affected_entity}",
                        "title": f"Entity Availability: {affected_entity} – {problem_label}"[:500],
                        "message": f"Zdroj {entity_id} potvrzuje, že {affected_entity} {problem_label}.",
                        "level": "WARNING", "priority": "P3", "confidence": 98,
                        "cause": f"Entity Availability zařadila {affected_entity} do {key}; nejde pouze o odhad podle názvu entity.",
                        "solution": "Ověřit vlastníka, stáří skutečných reportů, nastavení staleness a historii. Neměnná hodnota neznamená nefunkční ani nepoužívanou entitu. Mazání není řešením výpadku; vyžaduje zvláštní zdůvodnění a schválení.",
                        "verification": "Entita se vrátí do zdravého stavu, nebo je po schváleném úklidu odstraněna bez rozbitých referencí.",
                        "evidence": {"provider": "Entity Availability", "entity_id": entity_id, "affected_entity": affected_entity, "problem_kind": key, "attributes": attrs, "observations": [observation]},
                    }
                    emitted = True
            is_problem_binary = entity_id.startswith("binary_sensor.") and any(token in entity_id for token in problem_tokens) and str(item.get("state") or "").lower() in {"on", "true", "1"}
            if is_problem_binary and not emitted:
                fingerprint = hashlib.sha256(entity_id.encode()).hexdigest()[:24]
                label = str(attrs.get("friendly_name") or entity_id)
                by_problem[f"binary:{entity_id}"] = {
                    "adapter_id": "entity_availability", "integration": "Entity Availability",
                    "external_id": fingerprint, "source_ref": f"entity_availability:{entity_id}",
                    "title": f"Entity Availability: {label}"[:500],
                    "message": f"{entity_id} potvrzuje aktivní problém; konkrétní entity jsou v atributech zdroje.",
                    "level": "WARNING", "priority": "P3", "confidence": 96,
                    "cause": "Entity Availability potvrdila aktuální výpadek, zastaralá data, slabý signál nebo nízkou baterii ve sledované skupině.",
                    "solution": "Dohledat konkrétní zařízení a historii; bez jednoznačného vlastníka se nic nemaže ani nerestartuje.",
                    "verification": "Příslušný binary_sensor se vrátí do off a nedojde k regresi během ověřovacího okna.",
                    "evidence": {"provider": "Entity Availability", "entity_id": entity_id, "attributes": attrs},
                }
        return list(by_problem.values())

    @staticmethod
    def _haghs_findings(states: list[dict[str, Any]], entity_registry: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        flag_labels = {
            "rec_cpu": "vysoké zatížení CPU",
            "rec_memory": "tlak na operační paměť",
            "rec_disk": "nedostatek nebo tlak na úložiště",
            "rec_database": "zvýšené zatížení databáze",
            "rec_entities": "problémy s entitami",
            "rec_integrations": "problémy integrací",
            "rec_automations": "problémy automatizací",
            "rec_network": "problémy sítě",
        }
        registered = {
            str(row.get("entity_id") or "").lower()
            for row in (entity_registry or [])
            if str(row.get("platform") or "").lower() == "haghs"
        }
        for item in states:
            entity_id = str(item.get("entity_id") or "").lower()
            if entity_id not in registered and entity_id != "sensor.system_ha_global_health_score" and not entity_id.startswith("sensor.haghs_"):
                continue
            try:
                score = float(item.get("state"))
            except (TypeError, ValueError):
                continue
            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            flags = {key: value for key, value in attrs.items() if key.startswith("rec_") and value is True}
            if score >= 90 and not flags:
                continue
            active_kinds = list(flags) or ["score"]
            for flag in active_kinds:
                label = flag_labels.get(flag, str(attrs.get("recommendations") or "snížené zdravotní skóre"))
                canonical = f"{entity_id}:{flag}"
                findings.append({
                    "adapter_id": "haghs", "integration": "Home Assistant Global Health Score",
                    "external_id": hashlib.sha256(canonical.encode()).hexdigest()[:24],
                    "source_ref": f"haghs:{entity_id}:{flag}",
                    "title": f"HAGHS: {label} ({score:.0f}/100)"[:500],
                    "message": f"HAGHS {entity_id}={score:.0f}/100; aktivní signál {flag}: {label}.",
                    "level": "WARNING", "priority": "P3", "confidence": 95,
                    "cause": "HAGHS potvrdil konkrétní doporučující příznak. HADS jej používá jako nezávislý signál a musí jej potvrdit autoritativní metrikou nebo funkčním dopadem.",
                    "solution": f"Prověřit {label} a spojit příznak s aktuálními metrikami, logy a postiženou funkcí; samotné skóre není oprávnění k zásahu.",
                    "verification": f"Příznak {flag} zmizí a současně jsou autoritativní metriky i dotčená funkce zdravé.",
                    "evidence": {"provider": "HAGHS", "entity_id": entity_id, "score": score, "recommendation_flag": flag, "attributes": attrs},
                })
        return findings

    @classmethod
    def _automation_inspector_findings(cls, value: Any) -> list[dict[str, Any]]:
        """Preserve owner/path/current/replacement from Inspector schema v2."""
        if not isinstance(value, dict):
            return []
        findings: list[dict[str, Any]] = []
        for section in ("automations", "scripts"):
            objects = value.get(section)
            if not isinstance(objects, dict):
                continue
            for object_key, item in objects.items():
                if not isinstance(item, dict):
                    continue
                domain = "automation" if section == "automations" else "script"
                raw_owner = str(item.get("entity_id") or object_key or "").lower()
                owner = raw_owner if raw_owner.startswith(domain + ".") else f"{domain}.{raw_owner.split('.', 1)[-1]}"
                problems: list[dict[str, Any]] = []
                # Schema v2 carries missing entity/service references in
                # item.entities, not compatibility_issues. Previously lost.
                for dependency in item.get("entities") or []:
                    if not isinstance(dependency, dict):
                        continue
                    dependency_status = str(dependency.get("status") or "").lower()
                    identifier = str(dependency.get("id") or "")
                    if dependency_status not in {"missing", "unavailable", "unknown", "disabled"} or not identifier:
                        continue
                    problems.append({"code": "dependency_" + dependency_status,
                        "severity": "error" if dependency_status == "missing" else "warning",
                        "message": f"{owner}: odkaz {identifier} má stav {dependency_status}.",
                        "path": str(dependency.get("sources") or dependency.get("source") or "$.entities"),
                        "current": identifier, "replacement": None, "dependency": dependency,
                        "dependency_status": dependency_status})
                if item.get("loaded") is False or str(item.get("status") or "") == "not_loaded":
                    problems.append({"code": "not_loaded", "severity": "error", "message": f"{owner} není načtená v Home Assistantu.", "path": "$", "current": "not_loaded", "replacement": None})
                for issue in item.get("compatibility_issues") or []:
                    if isinstance(issue, dict) and str(issue.get("severity") or "").lower() in {"error", "warning"}:
                        problems.append(issue)
                trace = item.get("trace") if isinstance(item.get("trace"), dict) else {}
                if trace.get("error") or trace.get("template_errors") or trace.get("script_execution") in {"error", "failed_max_runs"}:
                    problems.append({"code": "trace_failure", "severity": "error", "message": str(trace.get("error") or trace.get("template_errors") or trace.get("script_execution")), "path": "$.trace", "current": None, "replacement": None})
                for issue in problems:
                    code = str(issue.get("code") or "inspector_issue")
                    path = str(issue.get("path") or "$")
                    message = str(issue.get("message") or code)
                    canonical = f"{owner}:{code}:{path}:{issue.get('current')}"
                    normalized_issue = {**issue, "automation_id" if domain == "automation" else "script_id": owner, "owner": owner}
                    if issue.get("current") is not None:
                        normalized_issue["current_value"] = issue.get("current")
                    if issue.get("replacement") is not None:
                        normalized_issue["recommended_value"] = issue.get("replacement")
                    findings.append({
                        "adapter_id": "automation_inspector", "integration": "Automation Inspector",
                        "external_id": hashlib.sha256(canonical.encode()).hexdigest()[:24],
                        "source_ref": f"automation_inspector:{owner}:{code}:{path}",
                        "title": f"Automation Inspector: {owner} – {message}"[:500],
                        "message": message[:12_000], "level": "ERROR" if str(issue.get("severity")) == "error" else "WARNING",
                        "priority": "P4" if item.get("enabled") is False and item.get("loaded") is not False else ("P3" if issue.get("dependency_status") in {"unknown", "disabled"} else "P2"), "confidence": 98,
                        "cause": f"Inspector spojil nález s {owner} a cestou {path}.",
                        "solution": (f"Ověřit a navrhnout změnu {issue.get('current')} → {issue.get('replacement')}." if issue.get("replacement") is not None else "Ověřit konfiguraci, závislosti a poslední trace této automatizace."),
                        "verification": "Nový Inspector snapshot nemá tento nález a kontrolovaný scénář automatizace projde.",
                        "evidence": {"provider": "Automation Inspector", "owner": owner, "payload": normalized_issue, "generated_at": value.get("generated_at"), "schema_version": value.get("schema_version"),
                            "enabled": item.get("enabled"), "restored": item.get("restored"), "configuration_available": item.get("configuration_available"), "configuration_source": item.get("configuration_source"), "config_hash": item.get("config_hash")},
                    })
        return findings

    def global_findings(self) -> list[dict[str, Any]]:
        self.refresh()
        runtime = self._runtime or {}
        connector_data = runtime.get("connector_data") or {}
        known_entities = {str(item.get("entity_id") or "").lower() for item in runtime.get("states") or []}
        known_entities |= {str(item.get("entity_id") or "").lower() for item in runtime.get("entity_registry") or []}
        known_services = {str(item).lower() for item in runtime.get("services") or set()}
        findings: list[dict[str, Any]] = []
        for finding in self._repair_findings(runtime.get("issues") or []):
            evidence = finding.get("evidence") if isinstance(finding.get("evidence"), dict) else {}
            issue = evidence.get("issue") if isinstance(evidence.get("issue"), dict) else {}
            kind = f"{issue.get('translation_key', '')} {issue.get('issue_id', '')}".lower()
            refs = [str(item).lower() for item in evidence.get("identifiers") or []]
            refs = [item for item in refs if not item.startswith(("automation.", "script.", "scene."))]
            if "unknown_entity" in kind and refs and all(item in known_entities for item in refs):
                continue
            if ("unknown_service" in kind or "unknown_action" in kind) and refs and all(item in known_services for item in refs):
                continue
            evidence["corroboration"] = {
                "live_registry_checked": True,
                "missing_references": [item for item in refs if item not in known_entities and item not in known_services],
            }
            finding["confidence"] = 96 if evidence["corroboration"]["missing_references"] else min(90, int(finding.get("confidence") or 90))
            findings.append(finding)
        findings += self._watchman_findings(runtime.get("watchman_reports") or [], known_entities, known_services)
        findings += self._haghs_findings(runtime.get("states") or [], runtime.get("entity_registry") or [])
        findings += self._entity_availability_findings(runtime.get("states") or [])
        if "automation_inspector" in connector_data:
            findings += self._automation_inspector_findings(connector_data["automation_inspector"])
        if "hadocs" in connector_data:
            findings += self._generic_json_findings("hadocs", connector_data["hadocs"])
        return findings

    @staticmethod
    def _finding_matches_case(item: dict[str, Any], case: dict[str, Any]) -> bool:
        """Provider identity alone never makes two findings the same defect."""
        source = str(item.get("source_ref") or "").strip().lower()
        target = str(case.get("source_ref") or "").strip().lower()
        if source and target:
            return source == target
        text = " ".join(str(case.get(key) or "") for key in ("title", "sample", "normalized_message")).lower()
        identifiers = (item.get("evidence") or {}).get("identifiers") or []
        return any(isinstance(identifier, str) and re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", identifier.lower())
                   and re.search(r"(?<![\w.])" + re.escape(identifier.lower()) + r"(?![\w.])", text)
                   for identifier in identifiers)

    def collect(self, case: dict[str, Any], root_case_id: int | None = None) -> dict[str, Any]:
        """Attach only adapter evidence demonstrably related to this case."""
        self.refresh()
        runtime = self._runtime or {}
        states = runtime.get("states") or []
        findings = self.global_findings()
        case_text = " ".join(str(case.get(key) or "") for key in ("title", "source_ref", "integration", "sample", "normalized_message")).lower()
        evidence: list[dict[str, Any]] = []
        used: list[str] = []
        for adapter in self.status():
            adapter_id = adapter["adapter_id"]
            connector_ready = bool((adapter.get("discovery") or {}).get("connector_ready"))
            if adapter_id == "native_ha" or (not adapter["active"] and not (adapter_id in {"ha_mcp", "hamster_mcp"} and connector_ready)):
                continue
            matched_states = self._matched_states(adapter_id, states)
            matched_findings = [item for item in findings if item["adapter_id"] == adapter_id and self._finding_matches_case(item, case)]
            payload: dict[str, Any] = {}
            if adapter_id in {"ha_mcp", "hamster_mcp"} and adapter.get("discovery", {}).get("connector_ready"):
                try:
                    mcp_payload = self._mcp_case_evidence(adapter_id, case_text)
                    if mcp_payload.get("outputs"):
                        payload["mcp_research"] = mcp_payload
                except Exception as exc:
                    payload["mcp_error"] = str(exc)[:1000]
            if matched_states:
                payload["matched_states"] = matched_states
            if matched_findings:
                payload["findings"] = matched_findings[:100]
            if payload:
                used.append(adapter_id)
                evidence.append({"adapter": adapter_id, "confidence": 90 if matched_findings else 78, "payload": payload})
                if payload.get("mcp_research"):
                    with self.db() as conn:
                        row = conn.execute("SELECT discovery_json,capabilities_json FROM tool_adapters WHERE adapter_id=?", (adapter_id,)).fetchone()
                        discovery = _json(row["discovery_json"], {}) if row else {}
                        discovery["data_used"] = True
                        discovery["last_case_query_at"] = self.now()
                        conn.execute(
                            "UPDATE tool_adapters SET active=1,discovery_json=?,last_ok_at=?,updated_at=? WHERE adapter_id=?",
                            (json.dumps(discovery, ensure_ascii=False), self.now(), self.now(), adapter_id),
                        )
        native = {"case": {key: case.get(key) for key in ("id", "title", "logger", "source_ref", "integration", "category", "priority", "sample", "probable_cause", "solution", "verification")}, "fallback_used": not bool(used)}
        evidence.append({"adapter": "native_ha", "confidence": 65 if used else 75, "payload": native})
        with self.db() as conn:
            for item in evidence:
                conn.execute(
                    "INSERT INTO adapter_evidence(adapter_id,root_case_id,case_id,evidence_type,payload_json,confidence,collected_at) VALUES(?,?,?,?,?,?,?)",
                    (item["adapter"], root_case_id, case.get("id"), "repair_research", json.dumps(item["payload"], ensure_ascii=False, default=str), item["confidence"], self.now()),
                )
        return {"used": used or ["native_ha"], "evidence": evidence, "native_fallback": not bool(used)}

    def health_scores(self) -> dict[str, Any]:
        """Consume cached real HAGHS numeric states; dashboard reads never force a DB write."""
        if self._runtime is None:
            # First page renders immediately; at most one background worker fills
            # the cache. Repeated dashboard GETs must never create a refresh storm.
            with self._refresh_lock:
                if not self._background_refresh_started:
                    self._background_refresh_started = True
                    def worker() -> None:
                        try:
                            self.refresh(force=True)
                        except Exception:
                            pass
                        finally:
                            with self._refresh_lock:
                                self._background_refresh_started = False
                    threading.Thread(target=worker, daemon=True).start()
            return {}
        matched = self._matched_states("haghs", (self._runtime or {}).get("states") or [])
        scores: dict[str, Any] = {}
        for item in matched:
            entity_id = str(item.get("entity_id") or "")
            try:
                number = float(item.get("state"))
            except (TypeError, ValueError):
                continue
            key = "health"
            lowered = entity_id.lower()
            if "hardware" in lowered:
                key = "hardware"
            elif "application" in lowered or "software" in lowered:
                key = "application"
            elif "reliab" in lowered:
                key = "reliability"
            scores[key] = max(0, min(100, round(number)))
            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            for attribute, target in (("hardware_score", "hardware"), ("application_score", "application")):
                try:
                    scores[target] = max(0, min(100, round(float(attrs[attribute]))))
                except (KeyError, TypeError, ValueError):
                    pass
        return scores
