"""Pinned Hermes AIAgent, one reasoning step, no native tools or HA secrets."""
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import urlsplit

PHASE = "vstup"


def check_confinement():
    # This public OS file normally is readable by nobody; rejecting it proves
    # a filesystem boundary, not merely a root-to-nobody permission change.
    try:
        Path("/etc/passwd").read_bytes()
    except (PermissionError, FileNotFoundError):
        pass
    else:
        raise RuntimeError("Confinement read check failed")
    try:
        subprocess.run([sys.executable, "-c", "pass"], check=True)
    except PermissionError:
        pass
    else:
        raise RuntimeError("Confinement execution check failed")
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            socket.socket(family)
        except PermissionError:
            pass
        else:
            raise RuntimeError('Confinement socket-creation check failed')
    for path in ('/data/options.json', '/homeassistant/configuration.yaml', '/share/hads-secret-canary', '/proc/1/environ'):
        try:
            Path(path).read_bytes()
        except (PermissionError, FileNotFoundError):
            pass
        else:
            raise RuntimeError('Confinement HA-data check failed')


def restrict_network(url):
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
        raise ValueError("Invalid local model broker")
    port = parsed.port
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def permitted(address):
        return isinstance(address, tuple) and address[0] == "127.0.0.1" and address[1] == port

    def connect(sock, address):
        if not permitted(address):
            raise PermissionError("Hermes network access outside HADS model broker is disabled")
        return original(sock, address)

    def connect_ex(sock, address):
        if not permitted(address):
            raise PermissionError("Hermes outbound network is disabled")
        return original_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex


def run(payload):
    global PHASE
    PHASE = "izolace chroot + UID + seccomp"
    from hermes_sandbox import confine, install_broker_socket_adapter
    confine(os.environ["HERMES_HOME"], urlsplit(payload["url"]).port)
    check_confinement()
    install_broker_socket_adapter(urlsplit(payload['url']).port)
    # Interpreter and dependencies are now resolved exclusively inside the jail.
    import site
    sys.path[:] = ['/app', '/opt/hermes', '/usr/local/lib/python3.14', '/usr/local/lib/python3.14/lib-dynload']
    site.addsitedir('/opt/hermes/.venv/lib/python3.14/site-packages')
    sys.executable = '/opt/hermes/.venv/bin/python'
    sys.prefix = sys.exec_prefix = '/opt/hermes/.venv'
    class NullWriter(io.TextIOBase):
        def write(self, value):
            return len(value)
    sink = NullWriter()
    # Redirect even initialization logs: stdout is an explicit result protocol.
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        PHASE = "načtení Hermes a jeho závislostí"
        from run_agent import AIAgent
        PHASE = "inicializace agenta bez přímých nástrojů"
        agent = AIAgent(base_url=payload["url"], api_key=payload["token"],
                        provider="custom", api_mode="chat_completions", model=payload["model"],
                        enabled_toolsets=[], max_iterations=1, max_tokens=payload["max_tokens"],
                        save_trajectories=False, quiet_mode=True, skip_memory=True,
                        skip_context_files=True, skip_background_review=True,
                        checkpoints_enabled=False, run_budget_seconds=220)
        try:
            if agent.tools:
                raise RuntimeError("Hermes unexpectedly enabled native tools; refusing to run")
            agent.compression_enabled = False
            PHASE = "vyhodnocení přes účtovanou HADS bránu"
            result = agent.run_conversation(payload["prompt"])
            if not isinstance(result, dict) or result.get("completed") is not True:
                raise RuntimeError("Hermes conversation did not complete")
            import resource
            return {"completed": True, "tool_count": 0, "isolation_verified": True,
                    "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                    "final_response": result.get("final_response", "")}
        finally:
            agent.close()


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise ValueError("Input too large")
        outcome = run(json.loads(raw))
    except BaseException as exc:
        # Do not echo exception messages: upstream errors can contain prompts.
        outcome = {"completed": False, "tool_count": 0, "error": PHASE + ": " + type(exc).__name__}
    print(json.dumps(outcome, ensure_ascii=False))
