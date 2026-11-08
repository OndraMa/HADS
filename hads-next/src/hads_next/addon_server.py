"""HA ingress controller for the read-only development application."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import stat
import threading
from urllib.parse import parse_qs, urlsplit

from .haos_application import Application, VERSION
from .observability import CoreReader, NativeHTTP


class SupervisorCoreTransport:
    """Fixed Supervisor origin and GET catalog; never an arbitrary HA proxy."""
    def __init__(self, token):
        self._http = NativeHTTP("http://supervisor", token, allow_local_http=True)

    def __call__(self, path):
        if path not in {"/api/config", "/api/states"} and not path.startswith("/api/history/period/"):
            raise ValueError("Unsupported Core read")
        return self._http("/core" + path)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, app, *, ingress_peer="172.30.32.2", owner_user_id=""):
        self.app, self.ingress_peer, self.owner_user_id = app, ingress_peer, owner_user_id
        self.csrf = secrets.token_urlsafe(32)
        self._slots = threading.BoundedSemaphore(4)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass  # URLs and form content can contain private household information.

    def send_body(self, status, body, kind="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return (self.client_address[0] == self.server.ingress_peer and bool(self.server.owner_user_id)
                and self.headers.get("X-Remote-User-Id") == self.server.owner_user_id)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            return self.send_body(200, json.dumps({"service": "hads-next", "version": VERSION, "mode": "read_only_development"}), "application/json")
        if path in {"/", "/identity"} and self.client_address[0] == self.server.ingress_peer and self.headers.get("X-Remote-User-Id") and (not self.server.owner_user_id or path == "/identity"):
            return self.send_body(200, '<!doctype html><html lang="cs"><meta charset="utf-8"><h1>Nastavení vlastníka HADS Next</h1><p>V konfiguraci této aplikace nastav owner_user_id na své ID zobrazené níže a aplikaci znovu spusť. Přístup musí nastavit správce HA.</p><pre>' + escape(self.headers["X-Remote-User-Id"]) + '</pre><p>Dokud vlastník není nastavený, diagnostická data nejsou přístupná.</p></html>')
        if not self.authorized():
            return self.send_body(403, "Přístup je povolen pouze přes přihlášený Home Assistant ingress.")
        if path == "/api/status":
            return self.send_body(200, json.dumps(self.server.app.snapshot(), ensure_ascii=False), "application/json")
        if path.startswith("/case/"):
            try:
                case = self.server.app.store.case(path.removeprefix("/case/"))
            except KeyError:
                return self.send_body(404, "Spis nebyl nalezen.")
            return self.send_body(200, json.dumps(case, ensure_ascii=False), "application/json")
        if path not in {"/", "/index.html"}:
            return self.send_body(404, "Stránka nebyla nalezena.")
        value = self.server.app.snapshot()
        core = value["core"]
        text = "Čtení Core funguje." if core["available"] else core["last_error"] or "Čtení Core čeká."
        cases = "".join('<article><h3>' + escape(c["symptom"]) + '</h3><p>Výskytů: ' + str(c["occurrence_count"]) +
            '</p><a href="case/' + escape(c["id"], quote=True) + '">Otevřít důkazy spisu</a></article>' for c in value["cases"])
        options = "".join('<option value="' + escape(e["entity_id"], quote=True) + '"></option>' for e in value["entities"])
        body = '''<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HADS Next</title><style>body{font:17px/1.6 system-ui;margin:2rem auto;padding:0 1rem;max-width:960px;color:#182638;background:#f3f5f7}article,form{background:white;padding:1rem;margin:1rem 0;border:1px solid #ccd6df;border-radius:6px}input,textarea,button{font:inherit;padding:.5rem;box-sizing:border-box;max-width:100%}input,textarea{width:100%}button{background:#12695f;color:white;border:0;border-radius:4px;cursor:pointer}.notice{border-left:4px solid #b36b12;padding:1rem;background:#fff7e8}a{color:#12695f}</style>
<h1>HADS Next</h1><p class="notice">Vývojová verze ''' + VERSION + '''. Hermes a živé opravy nejsou aktivní. Tato aplikace nepředstavuje dokončenou HAOS platformu.</p>
<h2>Co je dostupné</h2><p>''' + escape(text) + '</p><p>Načtených entit: ' + str(core["entity_count"]) + ". Samotná nedostupnost entity neurčuje příčinu závady.</p>" + '''
<form method="post" action="read"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''"><button>Obnovit čtení Core</button><p>Nejvýše jednou za minutu.</p></form>
<h2>Co nefunguje a co HADS vyšetřuje</h2>''' + (cases or "<p>Zatím nebyl nahlášen žádný funkční incident.</p>") + '''
<h2>Nahlásit problém</h2><form method="post" action="incident"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''">
<label>Co se stalo?<textarea name="symptom" maxlength="1000" required placeholder="Rádio se právě samo vypnulo."></textarea></label>
<label>Dotčená entita<input name="entity_id" list="entities" maxlength="200" required placeholder="media_player.radio"></label><datalist id="entities">''' + options + '''</datalist><button>Uložit incident a přečíst historii</button></form>
<h2>Co ode mě potřebuje</h2><p>Spis obsahuje dostupné důkazy a chybějící údaje. Tato verze nevytváří živě proveditelné opravy.</p>
<h2>Co se podařilo vyřešit</h2><p>Žádná živá náprava nebyla touto verzí ověřena.</p>
<h2>Co se opakuje</h2><p>Opakované ruční hlášení stejného problému a entity se ukládá do společného spisu.</p>
<details><summary>Technický stav čtení</summary><pre>''' + escape(json.dumps(core, ensure_ascii=False, indent=2)) + "</pre></details></html>"
        self.send_body(200, body)

    def do_POST(self):
        if not self.authorized():
            return self.send_body(403, "Chybí ověřený ingress uživatel.")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return self.send_body(415, "Nepodporovaný formát.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError()
            form = parse_qs(self.rfile.read(size).decode(), max_num_fields=4, strict_parsing=True)
            if form.get("csrf") != [self.server.csrf]:
                return self.send_body(403, "Formulář vypršel. Obnov stránku.")
            path = urlsplit(self.path).path
            if path == "/read":
                self.server.app.refresh()
            elif path == "/incident":
                self.server.app.report_incident(form.get("symptom", [""])[0], form.get("entity_id", [""])[0], self.headers["X-Remote-User-Id"])
            else:
                return self.send_body(404, "Tato operace není dostupná.")
        except (ValueError, UnicodeError):
            return self.send_body(400, "Neplatné hlášení nebo dosažený limit. Zkontroluj popis a entity_id.")
        self.send_response(303)
        self.send_header("Location", "./")
        self.send_header("Content-Length", "0")
        self.end_headers()


def prepare_data_directory(path):
    path = Path(path)
    if str(path) != "/data/hads-next":
        raise ValueError("Production data path must be /data/hads-next")
    if path.is_symlink():
        raise ValueError("Data directory cannot be a symlink")
    path.mkdir(mode=0o700, exist_ok=True)
    if os.geteuid() == 0:
        os.chown(path, 65532, 65532)
        os.setgroups([])
        os.setgid(65532)
        os.setuid(65532)
    # chmod after dropping UID works even without CAP_FOWNER, including restart
    # with an existing directory already owned by the unprivileged worker.
    os.chmod(path, 0o700)
    return path


def main():
    os.umask(0o077)
    options_path = Path("/data/options.json")
    options = json.loads(options_path.read_text()) if options_path.exists() and options_path.stat().st_size <= 8192 else {}
    owner = options.get("owner_user_id", "")
    if not isinstance(owner, str) or len(owner) > 128 or owner.strip() != owner:
        raise ValueError("Invalid owner_user_id")
    token = os.environ.pop("SUPERVISOR_TOKEN", "")
    path = prepare_data_directory(os.environ.get("HADS_DATA_DIR", "/data/hads-next"))
    core = CoreReader(SupervisorCoreTransport(token)) if token else None
    app = Application(path, core)
    threading.Thread(target=app.refresh, daemon=True).start()
    Server(("0.0.0.0", 8099), app, owner_user_id=owner).serve_forever()


if __name__ == "__main__":
    main()
