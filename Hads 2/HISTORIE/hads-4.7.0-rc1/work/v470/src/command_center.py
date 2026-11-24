#!/usr/bin/env python3
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

try:
    import websocket
except ImportError:  # pragma: no cover - image contains websocket-client
    websocket = None


EVENT_TYPES = (
    "state_changed",
    "automation_triggered",
    "homeassistant_start",
    "homeassistant_stop",
    "entity_registry_updated",
    "device_registry_updated",
    "area_registry_updated",
    "repairs_issue_registry_updated",
)


def _receive_json(socket: Any) -> dict[str, Any]:
    value = json.loads(socket.recv())
    if not isinstance(value, dict):
        raise RuntimeError("Home Assistant WebSocket vrátil neplatnou zprávu.")
    return value


def authenticated_socket(url: str, token: str, timeout: int = 20) -> Any:
    if websocket is None:
        raise RuntimeError("Python modul websocket-client není dostupný.")
    socket = websocket.create_connection(url, timeout=timeout, enable_multithread=True)
    hello = _receive_json(socket)
    if hello.get("type") != "auth_required":
        socket.close()
        raise RuntimeError(f"Neočekávaná úvodní WS zpráva: {hello.get('type')}")
    socket.send(json.dumps({"type": "auth", "access_token": token}))
    auth = _receive_json(socket)
    if auth.get("type") != "auth_ok":
        socket.close()
        raise RuntimeError(str(auth.get("message") or "WebSocket autentizace selhala."))
    return socket


def websocket_command(url: str, token: str, command: dict[str, Any], timeout: int = 30) -> Any:
    """Execute a read-only HA WebSocket command in a short authenticated session."""
    socket = authenticated_socket(url, token, timeout)
    try:
        request = dict(command)
        request["id"] = 1
        socket.send(json.dumps(request, ensure_ascii=False))
        while True:
            response = _receive_json(socket)
            if response.get("id") != 1:
                continue
            if not response.get("success"):
                error = response.get("error") or {}
                raise RuntimeError(str(error.get("message") or error or "WS příkaz selhal."))
            return response.get("result")
    finally:
        socket.close()


class HAObserver:
    """Persistent, read-only observer for selected Home Assistant events."""

    def __init__(
        self,
        url: str,
        token: str,
        on_event: Callable[[dict[str, Any]], None],
        on_status: Callable[[dict[str, Any]], None],
        reconnect_seconds: int = 10,
    ) -> None:
        self.url = url
        self.token = token
        self.on_event = on_event
        self.on_status = on_status
        self.reconnect_seconds = max(3, reconnect_seconds)
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run_forever(self) -> None:
        while not self.stop_event.is_set():
            socket = None
            try:
                self.on_status({"connected": False, "connecting": True, "error": ""})
                socket = authenticated_socket(self.url, self.token, 30)
                request_id = 1
                for event_type in EVENT_TYPES:
                    socket.send(json.dumps({"id": request_id, "type": "subscribe_events", "event_type": event_type}))
                    request_id += 1
                self.on_status({"connected": True, "connecting": False, "error": "", "connected_at": time.time()})
                socket.settimeout(60)
                while not self.stop_event.is_set():
                    try:
                        message = _receive_json(socket)
                    except Exception as exc:
                        if exc.__class__.__name__ in {"WebSocketTimeoutException", "TimeoutError"}:
                            socket.ping()
                            continue
                        raise
                    if message.get("type") == "event" and isinstance(message.get("event"), dict):
                        self.on_event(message["event"])
            except Exception as exc:
                self.on_status({"connected": False, "connecting": False, "error": str(exc)[:1000]})
            finally:
                if socket is not None:
                    try:
                        socket.close()
                    except Exception:
                        pass
            self.stop_event.wait(self.reconnect_seconds)
