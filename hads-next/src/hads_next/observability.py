"""Explicit, bounded native HA read adapters. No generic proxy or write method.

Credentials stay inside transports; data crossing into evidence/AI is redacted.
WS commands are pinned to contracts inspected in HA Core 2026.11.0.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 1024 * 1024
_SECRET = re.compile(r"token|password|secret|authorization|api[-_]?key|access[-_]?key|private[-_]?key|credential|code", re.I)
_BEARER = re.compile(r"Bearer\s+[^\s\"']+", re.I)
_ASSIGNMENT = re.compile(r"((?:token|password|secret|api[-_]?key|access[-_]?key|authorization)\s*[=:]\s*)[^\s&\"'<>]+", re.I)
_URL_CREDENTIAL = re.compile(r"(https?://)[^/@\s]+:[^/@\s]+@", re.I)


def redact(value):
    """Action payloads are excluded wholesale: they may include alarm PINs."""
    if isinstance(value, dict):
        return {k: "[skryto]" if _SECRET.search(k) or k in {"service_data", "action_data"}
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _URL_CREDENTIAL.sub(r"\1[skryto]@", _ASSIGNMENT.sub(r"\1[skryto]", _BEARER.sub("Bearer [skryto]", value)))
    return value


def project_action_calls(value):
    """HA2026.11 processor.py contract; retain provenance, never action secrets.

    Generic log redaction is best effort. This stricter projection is mandatory
    for action history because arbitrary service data can contain alarm PINs.
    """
    import math
    if not isinstance(value, list):
        raise ReadFailure("invalid_action_history")
    result = []
    for row in value:
        if not isinstance(row, dict):
            raise ReadFailure("invalid_action_history")
        projected = {}
        for key in ("domain", "service", "context_id", "context_user_id", "context_domain",
                    "context_service", "context_event_type", "context_entity_id"):
            item = row.get(key)
            if isinstance(item, str) and re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}", item):
                projected[key] = item
        when = row.get("when")
        if isinstance(when, (int, float)) and not isinstance(when, bool) and math.isfinite(when):
            projected["when"] = when
        data = row.get("service_data")
        if isinstance(data, dict):
            targets = {}
            for key in ("entity_id", "device_id", "area_id"):
                items = data.get(key)
                if isinstance(items, str):
                    items = [items]
                if isinstance(items, list) and len(items) <= 256 and all(
                    isinstance(x, str) and re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}", x) for x in items):
                    targets[key] = items
            if targets:
                projected["targets"] = targets
        result.append(projected)
    return result


@dataclass
class SourceStatus:
    source: str
    installed: bool | None = None
    running: bool | None = None
    interface_available: bool | None = None
    authenticated: bool | None = None
    read_succeeded: bool = False
    relevant: bool | None = None
    last_error: str | None = None
    last_evidence_at: float | None = None

    def snapshot(self, now=None):
        result = asdict(self)
        result["evidence_age_seconds"] = (None if self.last_evidence_at is None else
            max(0, (time.time() if now is None else now) - self.last_evidence_at))
        return result


class ReadFailure(RuntimeError):
    def __init__(self, code, status=None):
        super().__init__(code)
        self.status = status


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ReadFailure("redirect_refused")


class NativeHTTP:
    """Single origin GET transport. Never follow a token-bearing redirect."""
    def __init__(self, base_url: str, token: str, *, allow_local_http=False):
        parsed = urlsplit(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("invalid origin")
        if parsed.path not in {"", "/"} or not parsed.hostname:
            raise ValueError("origin only")
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1", "supervisor"}
        if parsed.scheme != "https" and not (allow_local_http and local and parsed.scheme == "http"):
            raise ValueError("HTTPS required outside explicit local transport")
        self._origin, self._token = base_url.rstrip("/"), token
        self._opener = build_opener(_NoRedirect)

    def __call__(self, path):
        if not path.startswith("/") or path.startswith("//") or "\\" in path:
            raise ReadFailure("invalid_path")
        request = Request(self._origin + path, headers={"Authorization": "Bearer " + self._token})
        try:
            with self._opener.open(request, timeout=10) as response:
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ReadFailure("response_too_large")
                return json.loads(data)
        except HTTPError as exc:
            raise ReadFailure("http_error", exc.code) from None
        except ReadFailure:
            raise
        except Exception:
            # Never include remote exception bodies/URLs/headers in evidence.
            raise ReadFailure("read_failed") from None


class NativeWebSocket:
    """Optional real websocket transport; opens one bounded authenticated read.

    Requires websockets>=15,<16, installed only for native WS use. No subscription,
    service call or arbitrary command is exposed by CoreReader.
    """
    def __init__(self, url, token):
        p = urlsplit(url)
        if p.scheme != "wss" or p.path != "/api/websocket" or p.username or p.password or p.query or p.fragment:
            raise ValueError("explicit secure HA websocket URL required")
        self._url, self._token = url, token

    def __call__(self, command):
        from websockets.sync.client import connect
        try:
            with connect(self._url, open_timeout=10, close_timeout=2, max_size=MAX_BYTES) as ws:
                if json.loads(ws.recv(timeout=10)).get("type") != "auth_required":
                    raise ReadFailure("auth_protocol")
                ws.send(json.dumps({"type": "auth", "access_token": self._token}))
                if json.loads(ws.recv(timeout=10)).get("type") != "auth_ok":
                    raise ReadFailure("authentication_failed", 401)
                ws.send(json.dumps({**command, "id": 1}))
                # system_health/info uses subscription messages; intentionally not
                # exposed here until a streaming transport is integration-tested.
                result = json.loads(ws.recv(timeout=10))
                if result.get("id") != 1 or result.get("type") != "result":
                    raise ReadFailure("unexpected_result")
                if not result.get("success"):
                    raise ReadFailure("command_rejected")
                return result.get("result")
        except ReadFailure:
            raise
        except Exception:
            raise ReadFailure("websocket_read_failed") from None


class _Reader:
    def __init__(self, source, transport: Callable):
        self.transport = transport
        self.status = SourceStatus(source)

    def _read(self, request, *, relevant=None):
        self.status.relevant = None
        try:
            result = self.transport(request)
            self.status.interface_available = True
            self.status.authenticated = True
            self.status.read_succeeded = True
            self.status.relevant = relevant(result) if relevant else None
            self.status.last_evidence_at = time.time()
            self.status.last_error = None
            return redact(result)
        except Exception as exc:
            status = exc.status if isinstance(exc, ReadFailure) else None
            if status in {401, 403}:
                self.status.authenticated = False
                self.status.interface_available = True
            # Transport outage does not prove uninstalled/stopped.
            self.status.read_succeeded = False
            self.status.last_error = str(exc) if isinstance(exc, ReadFailure) else "read_failed"
            return None


class CoreReader(_Reader):
    def __init__(self, transport):
        super().__init__("ha_core", transport)

    def config(self):
        return self._read("/api/config")

    def states(self, entity_id=None):
        if entity_id is not None and not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id):
            raise ValueError("invalid entity ID")
        return self._read("/api/states" + ("/" + entity_id if entity_id else ""))

    def history(self, start_iso, entity_id, end_iso):
        from datetime import datetime
        for value in (start_iso, end_iso):
            if datetime.fromisoformat(value).tzinfo is None:
                raise ValueError("timezone required")
        if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id):
            raise ValueError("invalid entity ID")
        from urllib.parse import quote
        return self._read("/api/history/period/" + quote(start_iso, safe="") + "?" + urlencode({
            "filter_entity_id": entity_id, "end_time": end_iso}))


class CoreWSReader(_Reader):
    def __init__(self, transport):
        super().__init__("ha_core_ws", transport)

    def entity_registry(self):
        return self._read({"type": "config/entity_registry/list"})

    def device_registry(self):
        return self._read({"type": "config/device_registry/list"})

    def traces(self, domain, item_id):
        if domain not in {"automation", "script"}:
            raise ValueError("trace domain")
        return self._read({"type": "trace/list", "domain": domain, "item_id": item_id})

    def trace(self, domain, item_id, run_id):
        if domain not in {"automation", "script"}:
            raise ValueError("trace domain")
        return self._read({"type": "trace/get", "domain": domain, "item_id": item_id, "run_id": run_id})

    def action_history(self, start_iso, end_iso):
        from datetime import datetime
        for value in (start_iso, end_iso):
            if datetime.fromisoformat(value).tzinfo is None:
                raise ValueError("timezone required")
        shadow = _Reader("ha_core_ws", lambda request: project_action_calls(self.transport(request)))
        shadow.status = self.status
        return shadow._read({"type": "logbook/get_action_calls", "start_time": start_iso, "end_time": end_iso})


class SupervisorReader(_Reader):
    def __init__(self, transport):
        super().__init__("supervisor", transport)

    def _supervised(self, path):
        original = self.transport
        # No mutable transport swap: supports concurrent readers safely.
        shadow = _Reader("supervisor", lambda request: _unwrap(original(request)))
        shadow.status = self.status
        return shadow._read(path)

    def apps(self):
        return self._supervised("/addons")

    def app_info(self, slug):
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            raise ValueError("invalid app slug")
        return self._supervised(f"/addons/{slug}/info")

    def app_stats(self, slug):
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            raise ValueError("invalid app slug")
        return self._supervised(f"/addons/{slug}/stats")


def _unwrap(value):
    if not isinstance(value, dict) or value.get("result") != "ok" or "data" not in value:
        raise ReadFailure("supervisor_read_rejected")
    return value["data"]
