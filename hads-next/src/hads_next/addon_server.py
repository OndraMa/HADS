"""HA ingress controller for the read-only development application."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import time
import stat
import threading
from urllib.parse import parse_qs, urlsplit

from .haos_application import Application, VERSION
from .observability import CoreReader, CoreWSReader, NativeHTTP, NativeWebSocket, SupervisorReader


class SupervisorTransport:
    def __init__(self, token):
        self._http = NativeHTTP('http://supervisor', token, allow_local_http=True)

    def __call__(self, path):
        import re
        if path not in {'/supervisor/info','/os/info','/addons'} and not re.fullmatch(r'/addons/[a-z0-9_]+/(info|stats|logs)',path):
            raise ValueError('Unsupported Supervisor read')
        return self._http(path, raw=path.endswith('/logs'))


class SupervisorCoreTransport:
    """Fixed Supervisor origin and GET catalog; never an arbitrary HA proxy."""
    def __init__(self, token):
        self._http = NativeHTTP("http://supervisor", token, allow_local_http=True)

    def __call__(self, path):
        import re
        if path not in {"/api/config", "/api/states"} and not path.startswith("/api/history/period/") \
                and not re.fullmatch(r'/api/states/[a-z][a-z0-9_]*\.[a-z0-9_]+', path) \
                and not re.fullmatch(r'/api/config/automation/config/[A-Za-z0-9_-]{1,128}',path):
            raise ValueError("Unsupported Core read")
        return self._http("/core" + path)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, app, *, ingress_peer="172.30.32.2", owner_user_id=""):
        self.app, self.ingress_peer, self.owner_user_id = app, ingress_peer, owner_user_id
        self.csrf = secrets.token_urlsafe(32)
        self._auth_lock = threading.Lock()
        self._auth_cache = None
        self._slots = threading.BoundedSemaphore(4)
        super().__init__(address, Handler)

    def verified_admin(self, user_id):
        if not user_id or self.app.core_ws is None:
            return False
        with self._auth_lock:
            now = time.monotonic()
            if self._auth_cache and self._auth_cache[0] == user_id and now-self._auth_cache[1] < 15:
                return self._auth_cache[2]
            users = self.app.core_ws.auth_users()
            valid = isinstance(users,list) and len(users) <= 1000 and any(
                isinstance(u,dict) and u.get('id') == user_id and u.get('is_active') is True
                and u.get('system_generated') is False and (u.get('is_owner') is True
                or (isinstance(u.get('group_ids'),list) and 'system-admin' in u['group_ids'])) for u in (users or []))
            self._auth_cache = (user_id,now,bool(valid))
            return bool(valid)

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
        user = self.headers.get('X-Remote-User-Id')
        owner = self.server.app.owner() or self.server.owner_user_id
        return (self.client_address[0] == self.server.ingress_peer and bool(owner) and user == owner
                and self.server.verified_admin(user))

    def setup_page(self):
        user = self.headers.get('X-Remote-User-Id')
        admin = self.server.verified_admin(user)
        message = 'Oprávnění správce bylo ověřeno přímo v Home Assistantu.' if admin else 'Oprávnění správce zatím nelze potvrdit. Ověř přihlášení správce a dostupnost Core WebSocket API; přístup k datům zůstává uzamčený.'
        form = ('<form method="post" action="setup/enroll"><input type="hidden" name="csrf" value="' + self.server.csrf
                + '"><button>Potvrdit správu HADS a zahájit kontrolu zdrojů</button></form>') if admin else ''
        return '<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Průvodce HADS</title><h1>Vítej v HADS Next</h1><p>' + message + '</p>' + form + '<p>Žádná změna domácnosti ani placené volání AI se tím neschvaluje.</p></html>'

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            return self.send_body(200, json.dumps({"service": "hads-next", "version": VERSION, "mode": "read_only_development"}), "application/json")
        if path in {'/','/identity'} and self.client_address[0] == self.server.ingress_peer and not (self.server.app.owner() or self.server.owner_user_id):
            return self.send_body(200,self.setup_page())
        if not self.authorized():
            return self.send_body(403, "Přístup je povolen pouze přes přihlášený Home Assistant ingress.")
        if path == "/api/status":
            return self.send_body(200, json.dumps(self.server.app.snapshot(), ensure_ascii=False), "application/json")
        if path == '/setup/ai':
            settings=self.server.app.investigations.provider.public_status()
            return self.send_body(200,'<h1>Poskytovatel AI pro Hermes</h1><p>Přístupový klíč zůstává v controlleru. Hermes dostává pouze redigované důkazy. Volání může být zpoplatněné; ChatGPT Plus není univerzální API přístup. OAuth zde není podporovaný.</p>'
                +'<form method="post" action="ai"><input type="hidden" name="csrf" value="'+self.server.csrf+'">'
                +'<label>HTTPS chat/completions endpoint<input name="endpoint" required value="'+escape(settings['endpoint'],quote=True)+'"></label>'
                +'<label>Model<input name="model" required maxlength="128" value="'+escape(settings['model'],quote=True)+'"></label>'
                +'<label>API klíč<input type="password" name="api_key" maxlength="2048" autocomplete="new-password" placeholder="Při zachování endpointu a modelu lze existující klíč ponechat prázdný."></label>'
                +'<label><input type="checkbox" name="consent" value="yes" '+('checked' if settings['enabled'] else '')+'> Výslovně povoluji modelová volání a předání redigovaných diagnostických údajů tomuto poskytovateli.</label>'
                +'<p>Nejvýše 8 požadavků na případ, 12 denně, 1024 výstupních tokenů na požadavek. Změna nastavení sama vyšetřování nespouští.</p><button>Uložit nastavení AI</button></form><a href="../../">Přehled</a>')
        if path == '/setup':
            sources = self.server.app.snapshot()['sources']
            rows = ''.join('<li>' + escape(k) + ': ' + ('Čtení proběhlo' if v['read_succeeded'] else 'Čtení není dostupné: ' + escape(str(v['status'].get('last_error')))) + '</li>' for k,v in sources.items())
            if self.server.app.snapshot()['source_job']['state']=='running':
                rows='<li>Kontrola právě probíhá. Obnov stránku pro průběžné výsledky.</li>'+rows
            runtime=self.server.app.investigations.status()
            return self.send_body(200,'<h1>Průvodce připraveností</h1><ul>' + rows + '</ul><p>Izolovaný Hermes launcher: '+('dostupný; izolace se ověří před prvním modelovým voláním' if runtime['runtime_installed'] else 'v tomto image není dostupný')+'</p><p>Živá HAOS a reálná modelová přejímka čekají. Živé opravy jsou vypnuté.</p><a href="setup/ai">Nastavit poskytovatele AI</a><form method="post" action="setup/check"><input type="hidden" name="csrf" value="' + self.server.csrf + '"><button>Ověřit skutečná čtení zdrojů</button></form><a href="./">Přehled domácnosti</a>')
        if path.startswith("/case/"):
            try:
                case = self.server.app.store.case(path.removeprefix("/case/"))
            except KeyError:
                return self.send_body(404, "Spis nebyl nalezen.")
            investigations=[r['content'] for r in case['records'] if r['kind'] in {'deterministic_investigation','investigation'}]
            result=investigations[-1] if investigations else {}
            jobs=self.server.app.investigations.for_case(case['incident']['id'])
            if jobs and jobs[0]['conclusion']:result=jobs[0]['conclusion']
            progress=''.join('<li>'+escape(step['reason'])+'</li>' for job in jobs[:1] for step in job['steps'])
            reads=''.join('<li>'+escape(row['name'])+': '+escape(row['result']['status'])+'</li>' for job in jobs[:1] for row in job['reads'])
            acknowledge='<label><input type="checkbox" name="ack_unknown" value="yes"> Povolím další pokus i v případě, že předchozí nedokončené modelové volání mohlo být účtováno.</label>' if jobs and jobs[0]['state']=='blocked' else ''
            return self.send_body(200,'<!doctype html><html lang="cs"><meta charset="utf-8"><h1>' + escape(case['incident']['symptom'])
                +'</h1><h2>Průběh vyšetřování</h2><ul>'+progress+'</ul><details><summary>Čtení a dostupnost zdrojů</summary><ul>'+reads+'</ul></details><form method="post" action="../investigate"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><input type="hidden" name="incident_id" value="'+escape(case['incident']['id'],quote=True)+'">'+acknowledge+'<button>Spustit nebo obnovit čtecí vyšetřování Hermes</button></form><a href="../setup/ai">Nastavení AI</a>'
                + '<h2>Pracovní závěr</h2><p>' + escape(result.get('summary_cs','Vyšetřování ještě nemá závěr.'))
                + '</p><h2>Další potřebné důkazy</h2><ul>' + ''.join('<li>'+escape(str(x))+'</li>' for x in result.get('needed',[]))
                + '</ul><h2>Další krok</h2><p>'+escape(result.get('next_test_cs','Doplň chybějící důkazy nebo spusť vyšetřování.'))+'</p><p>Žádná oprava nebyla provedena a incident zůstává otevřený.</p><details><summary>Technické důkazy spisu</summary><pre>'
                + escape(json.dumps(case,ensure_ascii=False,indent=2)) + '</pre></details></html>')
        if path not in {"/", "/index.html"}:
            return self.send_body(404, "Stránka nebyla nalezena.")
        value = self.server.app.snapshot()
        core = value["core"]
        text = "Čtení Core funguje." if core["available"] else core["last_error"] or "Čtení Core čeká."
        cases = "".join('<article><h3>' + escape(c["symptom"]) + '</h3><p>Výskytů: ' + str(c["occurrence_count"]) +
            '</p><a href="case/' + escape(c["id"], quote=True) + '">Otevřít důkazy spisu</a></article>' for c in value["cases"])
        options = "".join('<option value="' + escape(e["entity_id"], quote=True) + '"></option>' for e in value["entities"])
        applications = ''.join('<option value="' + escape(a['slug'],quote=True) + '">' + escape(a['name']) + '</option>' for a in value['applications'])
        body = '''<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HADS Next</title><style>body{font:17px/1.6 system-ui;margin:2rem auto;padding:0 1rem;max-width:960px;color:#182638;background:#f3f5f7}article,form{background:white;padding:1rem;margin:1rem 0;border:1px solid #ccd6df;border-radius:6px}input,textarea,button{font:inherit;padding:.5rem;box-sizing:border-box;max-width:100%}input,textarea{width:100%}button{background:#12695f;color:white;border:0;border-radius:4px;cursor:pointer}.notice{border-left:4px solid #b36b12;padding:1rem;background:#fff7e8}a{color:#12695f}</style>
<h1>HADS Next</h1><p class="notice">Vývojová verze ''' + VERSION + '''. Hermes vyžaduje izolovaný runtime a výslovně povoleného poskytovatele AI. Živé opravy jsou vypnuté; HAOS přejímka čeká.</p>
<nav><a href="./">Moje domácnost</a> · <a href="#investigation">Vyšetřování</a> · <a href="#waiting">Čeká na mě</a> · <a href="#resolved">Opraveno</a> · <a href="#recurring">Opakující se problémy</a> · <a href="setup">Agenti a zdroje</a> · <a href="#investigation">Historie</a></nav>
<h2>Co je dostupné</h2><p>''' + escape(text) + '</p><p>Načtených entit: ' + str(core["entity_count"]) + ". Samotná nedostupnost entity neurčuje příčinu závady.</p>" + '''
<form method="post" action="read"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''"><button>Obnovit čtení Core</button><p>Nejvýše jednou za minutu.</p></form>
<h2 id="investigation">Co nefunguje a co HADS vyšetřuje</h2>''' + (cases or "<p>Zatím nebyl nahlášen žádný funkční incident.</p>") + '''
<h2>Nahlásit problém</h2><form method="post" action="incident"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''">
<label>Co se stalo?<textarea name="symptom" maxlength="1000" required placeholder="Rádio se právě samo vypnulo."></textarea></label>
<label>Kdy se to stalo? Časové pásmo ''' + escape(value['timezone']) + '''. Pro právě probíhající problém nechej prázdné.<input type="datetime-local" name="occurred_at"></label>
<label>Dotčená entita<input name="entity_id" list="entities" maxlength="200" required placeholder="media_player.radio"></label><datalist id="entities">''' + options + '''</datalist><button>Uložit incident a přečíst historii</button></form>
<h2>Vyšetřit aplikaci HAOS</h2><form method="post" action="incident/app"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''"><label>Aplikace<select name="slug" required>''' + applications + '''</select></label><label>Co nefunguje?<input name="symptom" required maxlength="1000"></label><button>Načíst stav, statistiky a protokol aplikace</button></form>
<h2 id="waiting">Co ode mě potřebuje</h2><p>Spis obsahuje dostupné důkazy a chybějící údaje. Tato verze nevytváří živě proveditelné opravy.</p>
<h2 id="resolved">Co se podařilo vyřešit</h2><p>Žádná živá náprava nebyla touto verzí ověřena.</p>
<h2 id="recurring">Co se opakuje</h2><p>Opakované ruční hlášení stejného problému a entity se ukládá do společného spisu.</p>
<details><summary>Technický stav čtení</summary><pre>''' + escape(json.dumps(core, ensure_ascii=False, indent=2)) + "</pre></details></html>"
        self.send_body(200, body)

    def do_POST(self):
        if urlsplit(self.path).path == '/setup/enroll':
            if self.client_address[0] != self.server.ingress_peer or not self.server.verified_admin(self.headers.get('X-Remote-User-Id')):
                return self.send_body(403,'Oprávnění správce nelze ověřit.')
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 1024: raise ValueError()
                form=parse_qs(self.rfile.read(size).decode(),max_num_fields=1)
                if form.get('csrf') != [self.server.csrf]: return self.send_body(403,'Formulář vypršel.')
                self.server.app.enroll_owner(self.headers['X-Remote-User-Id'])
                self.server.app.request_source_check()
            except ValueError:
                return self.send_body(409,'Registraci nelze dokončit. Obnov stránku.')
            self.send_response(303);self.send_header('Location','../setup');self.send_header('Content-Length','0');self.end_headers();return
        if not self.authorized():
            return self.send_body(403, "Chybí ověřený ingress uživatel.")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return self.send_body(415, "Nepodporovaný formát.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                raise ValueError()
            form = parse_qs(self.rfile.read(size).decode(), max_num_fields=8, strict_parsing=True)
            if form.get("csrf") != [self.server.csrf]:
                return self.send_body(403, "Formulář vypršel. Obnov stránku.")
            path = urlsplit(self.path).path
            if path == "/read":
                self.server.app.refresh()
            elif path == '/setup/ai':
                self.server.app.investigations.provider.configure(endpoint=form.get('endpoint',[''])[0],model=form.get('model',[''])[0],
                    api_key=form.get('api_key',[''])[0],consent=form.get('consent')==['yes'],principal=self.headers['X-Remote-User-Id'])
                self.send_response(303);self.send_header('Location','ai');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/investigate':
                identity=form.get('incident_id',[''])[0]
                self.server.app.investigations.start(identity,self.headers['X-Remote-User-Id'],ack_unknown=form.get('ack_unknown')==['yes'])
                self.send_response(303);self.send_header('Location','case/'+identity);self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/check':
                self.server.app.request_source_check()
            elif path == '/incident/app':
                self.server.app.report_app_incident(form.get('symptom',[''])[0],form.get('slug',[''])[0],self.headers['X-Remote-User-Id'])
            elif path == "/incident":
                stamp=None
                if form.get('occurred_at',[''])[0]:
                    from datetime import datetime
                    from zoneinfo import ZoneInfo
                    date=datetime.fromisoformat(form['occurred_at'][0])
                    if date.tzinfo is None:
                        zone=ZoneInfo(self.server.app.snapshot()['timezone'])
                        if date.replace(tzinfo=zone,fold=0).utcoffset() != date.replace(tzinfo=zone,fold=1).utcoffset():raise ValueError('Nejednoznačný čas.')
                        date=date.replace(tzinfo=zone)
                    stamp=date.timestamp()
                self.server.app.report_incident(form.get("symptom", [""])[0], form.get("entity_id", [""])[0], self.headers["X-Remote-User-Id"],occurred_at=stamp)
            else:
                return self.send_body(404, "Tato operace není dostupná.")
        except (ValueError, UnicodeError):
            return self.send_body(400, "Neplatné hlášení nebo dosažený limit. Zkontroluj popis a entity_id.")
        self.send_response(303)
        self.send_header("Location", "../" if path.count('/') > 1 else "./")
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
    launcher=None
    if Path('/opt/hermes-root/opt/hermes/HADS_PINNED_REVISION').is_file():
        from .runtime_launcher import RuntimeLauncher
        try:launcher=RuntimeLauncher()
        except (OSError,RuntimeError,EOFError):pass
    path = prepare_data_directory(os.environ.get("HADS_DATA_DIR", "/data/hads-next"))
    core = CoreReader(SupervisorCoreTransport(token)) if token else None
    ws = CoreWSReader(NativeWebSocket('ws://supervisor/core/websocket',token,supervisor_proxy=True)) if token else None
    supervisor = SupervisorReader(SupervisorTransport(token)) if token else None
    app = Application(path, core, core_ws=ws, supervisor=supervisor,launcher=launcher)
    threading.Thread(target=app.refresh, daemon=True).start()
    try:Server(("0.0.0.0", 8099), app, owner_user_id=owner).serve_forever()
    finally:
        if launcher:launcher.close()


if __name__ == "__main__":
    main()
