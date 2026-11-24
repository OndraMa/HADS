"""Explicit, bounded native HA read adapters. No generic proxy or write method.

Credentials stay inside transports; data crossing into evidence/AI is redacted.
WS commands are pinned to contracts inspected in HA Core 2026.11.0.
"""
from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
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

SUPERVISOR_FIELDS={
    'info':('version','version_latest','update_available','healthy','supported','arch','channel'),
    'os_info':('version','version_latest','update_available','board','boot','data_disk'),
    'app_info':('slug','name','version','version_latest','state','update_available','boot','startup','watchdog','healthy','available','arch'),
    'app_stats':('cpu_percent','memory_usage','memory_limit','memory_percent','network_tx','network_rx','blk_read','blk_write'),
}


def project_supervisor_read(kind,value):
    """Shared positive projection; never persist an application's options."""
    import math
    if kind not in SUPERVISOR_FIELDS or not isinstance(value,dict):raise ValueError('invalid_supervisor_contract')
    result={key:value[key] for key in SUPERVISOR_FIELDS[kind] if key in value}
    if kind=='app_stats' and result.get('cpu_percent','missing') is None:result.pop('cpu_percent')
    if not result:raise ValueError('missing_supervisor_fields')
    if kind=='app_stats' and any(type(x) not in {int,float} or not math.isfinite(x) or x<0 for x in result.values()):
        raise ValueError('invalid_supervisor_statistics')
    return redact(result)


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
    last_read_at: float | None = None
    last_evidence_at: float | None = None
    last_response_status: int | None = None

    def snapshot(self, now=None):
        result = asdict(self)
        result["evidence_age_seconds"] = (None if self.last_evidence_at is None else
            max(0, (time.time() if now is None else now) - self.last_evidence_at))
        return result


class ReadFailure(RuntimeError):
    def __init__(self, code, status=None):
        super().__init__(code)
        self.status = status


def bounded_chunks(response,limit,seconds):
    """HTTPResponse.read1 returns available data; a trickle cannot reset budget.

    A socket read may still take the configured transport timeout. The wall
    budget is checked between reads, independently of per-socket inactivity.
    """
    deadline=time.monotonic()+seconds;size=0
    while True:
        if time.monotonic()>deadline:raise ReadFailure('response_time_budget')
        chunk=response.read1(min(16384,limit+1-size))
        if not chunk:return
        size+=len(chunk)
        if size>limit:raise ReadFailure('response_too_large')
        yield chunk


def bounded_body(response,limit,seconds=10):
    return b''.join(bounded_chunks(response,limit,seconds))


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

    def __call__(self, path, *, raw=False):
        if not path.startswith("/") or path.startswith("//") or "\\" in path:
            raise ReadFailure("invalid_path")
        request = Request(self._origin + path, headers={"Authorization": "Bearer " + self._token})
        try:
            with self._opener.open(request, timeout=10) as response:
                data = bounded_body(response,MAX_BYTES)
                return data.decode('utf-8', errors='replace')[-65536:] if raw else json.loads(data)
        except HTTPError as exc:
            raise ReadFailure("http_error", exc.code) from None
        except ReadFailure:
            raise
        except Exception:
            # Never include remote exception bodies/URLs/headers in evidence.
            raise ReadFailure("read_failed") from None


class NativeWebSocket:
    """Optional real websocket transport; opens one bounded authenticated read.

    Requires websockets>=16,<17. The only event subscription is zha_event;
    no service calls or general subscriptions are exposed to investigators.
    """
    def __init__(self, url, token, *, supervisor_proxy=False, allow_loopback=False):
        p = urlsplit(url)
        internal = supervisor_proxy and url == 'ws://supervisor/core/websocket'
        local = allow_loopback and p.scheme=='ws' and p.hostname=='127.0.0.1' and p.path=='/api/websocket'
        if (not internal and not local and (p.scheme != "wss" or p.path != "/api/websocket")) or p.username or p.password or p.query or p.fragment:
            raise ValueError("explicit secure HA websocket URL required")
        self._url, self._token = url, token

    @contextmanager
    def _connection(self):
        from websockets.sync.client import connect
        try:
            with connect(self._url, open_timeout=10, close_timeout=2, max_size=MAX_BYTES) as ws:
                if json.loads(ws.recv(timeout=10)).get("type") != "auth_required":
                    raise ReadFailure("auth_protocol")
                ws.send(json.dumps({"type": "auth", "access_token": self._token}))
                if json.loads(ws.recv(timeout=10)).get("type") != "auth_ok":
                    raise ReadFailure("authentication_failed", 401)
                yield ws
        except ReadFailure:
            raise
        except Exception:
            raise ReadFailure("websocket_read_failed") from None

    def __call__(self, command):
        with self._connection() as ws:
            ws.send(json.dumps({**command, 'id': 1}))
            result = json.loads(ws.recv(timeout=10))
            if result.get('id') != 1 or result.get('type') != 'result':
                raise ReadFailure('unexpected_result')
            if not result.get('success'):
                error=result.get('error',{}).get('code')
                raise ReadFailure('command_rejected',403 if error in {'unauthorized','auth_required'} else None)
            if command.get('type') != 'system_health/info':
                return result.get('result')
            domains={}; size=0; deadline=time.monotonic()+15
            for _ in range(128):
                remaining=deadline-time.monotonic()
                if remaining<=0:break
                try:message=ws.recv(timeout=remaining)
                except TimeoutError:break
                size+=len(message)
                if size>MAX_BYTES:raise ReadFailure('response_too_large')
                message=json.loads(message)
                if message.get('id')!=1 or message.get('type')!='event':raise ReadFailure('unexpected_health_event')
                event=message.get('event',{})
                if event.get('type')=='initial':
                    domains=event.get('data')
                    if not isinstance(domains,dict):raise ReadFailure('invalid_health_initial')
                elif event.get('type')=='update':
                    domain=domains.get(event.get('domain'))
                    if isinstance(domain,dict):
                        domain.setdefault('info',{})[event['key']]=event.get('data') if event.get('success') else {'error':event.get('error')}
                elif event.get('type')=='finish':return {'domains':domains,'complete':True}
            return {'domains':domains,'complete':False,'limitation':'health_stream_incomplete'}

    def zha_events(self, stop, on_event, on_ready, on_heartbeat):
        return self._events("zha_event",stop,on_event,on_ready,on_heartbeat)

    def state_events(self,stop,on_event,on_ready,on_heartbeat):
        return self._events("state_changed",stop,on_event,on_ready,on_heartbeat)

    def automation_events(self,stop,on_event,on_ready,on_heartbeat):
        return self._events("automation_triggered",stop,on_event,on_ready,on_heartbeat)

    def _events(self,event_type,stop,on_event,on_ready,on_heartbeat):
        """Trusted collector only. No model parameters, credentials in transport."""
        with self._connection() as ws:
            ws.send(json.dumps({'id':1,'type':'subscribe_events','event_type':event_type}))
            ack=json.loads(ws.recv(timeout=10))
            if ack.get('id')!=1 or ack.get('type')!='result' or not ack.get('success'):
                raise ReadFailure('zha_subscription_rejected',403 if ack.get('error',{}).get('code')=='unauthorized' else None)
            on_ready(); next_ping=time.monotonic()+5; ping_id=1; awaiting=None
            while not stop.is_set():
                try:message=json.loads(ws.recv(timeout=1))
                except TimeoutError:message={}
                if message.get('id')==1 and message.get('type')=='event':
                    event=message.get('event',{})
                    if event.get('event_type')!=event_type:raise ReadFailure('unexpected_zha_event')
                    on_event(event);on_heartbeat()
                elif awaiting is not None and message.get('id')==awaiting and message.get('type')=='pong':
                    awaiting=None;on_heartbeat()
                if time.monotonic()>=next_ping:
                    if awaiting is not None:raise ReadFailure('zha_heartbeat_timeout')
                    ping_id+=1;awaiting=ping_id
                    ws.send(json.dumps({'id':ping_id,'type':'ping'}));next_ping=time.monotonic()+5


class _Reader:
    def __init__(self, source, transport: Callable):
        self.transport = transport
        self.status = SourceStatus(source)

    def _read(self, request, *, relevant=None, evidence_time=None):
        self.status.relevant = None
        try:
            result = self.transport(request)
            self.status.interface_available = True
            self.status.authenticated = True
            self.status.read_succeeded = True
            self.status.relevant = relevant(result) if relevant else None
            self.status.last_read_at = time.time()
            # A fresh read of an old event must never rejuvenate its evidence.
            self.status.last_evidence_at = evidence_time(result) if evidence_time else None
            self.status.last_error = None
            self.status.last_response_status = None
            return redact(result)
        except Exception as exc:
            status = exc.status if isinstance(exc, ReadFailure) else None
            self.status.last_response_status = status
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

    def automation_config(self, automation_id):
        if not isinstance(automation_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', automation_id):
            raise ValueError('invalid automation ID')
        return self._read('/api/config/automation/config/' + automation_id)

    def states(self, entity_id=None):
        if entity_id is not None and not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id):
            raise ValueError("invalid entity ID")
        def observed(value):
            from datetime import datetime
            if not isinstance(value, dict) or not value.get("last_updated"):
                return None
            try:
                stamp = datetime.fromisoformat(value["last_updated"])
                return stamp.timestamp() if stamp.tzinfo else None
            except (ValueError, TypeError):
                return None
        return self._read("/api/states" + ("/" + entity_id if entity_id else ""), evidence_time=observed)

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
        self._auth_reader=_Reader('ha_admin_identity',transport)

    def entity_registry(self):
        return self._read({"type": "config/entity_registry/list"})

    def auth_users(self):
        # Ingress identity checks may overlap a diagnostic read. Their status
        # must not overwrite a trace/registry failure in the shared reader.
        return self._auth_reader._read({"type": "config/auth/list"})

    def owned_reference(self):
        return self._read({"type":"hads_reference/read"})

    def repairs(self):
        return self._read({"type": "repairs/list_issues"})

    def system_log(self):
        return self._read({"type": "system_log/list"})

    def system_health(self):
        return self._read({'type':'system_health/info'})

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
        return shadow._read({"type": "logbook/get_action_calls", "start_time": start_iso, "end_time": end_iso},
            evidence_time=lambda rows: max((row["when"] for row in rows if "when" in row), default=None))


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

    def info(self):
        return self._supervised('/supervisor/info')

    def os_info(self):
        return self._supervised('/os/info')

    def host_info(self):
        return self._supervised('/host/info')

    def core_stats(self):
        return self._supervised('/core/stats')

    def supervisor_stats(self):
        return self._supervised('/supervisor/stats')

    def app_logs(self, slug):
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            raise ValueError('invalid app slug')
        return self._read(f'/addons/{slug}/logs')

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
