"""HA ingress controller for the read-only development application."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ctypes
import os
from pathlib import Path
import secrets
import time
import stat
import threading
from urllib.parse import parse_qs, urlsplit

from .haos_application import Application, VERSION
from .observability import CoreReader, CoreWSReader, NativeHTTP, NativeWebSocket, SupervisorReader
from .investigation_jobs import JobBlocked
from .repair import RepairBlocked


class SupervisorTransport:
    def __init__(self, token):
        self._http = NativeHTTP('http://supervisor', token, allow_local_http=True)

    def __call__(self, path):
        import re
        if path not in {'/supervisor/info','/os/info','/host/info','/addons'} and not re.fullmatch(r'/addons/[a-z0-9_]+/(info|stats|logs)',path):
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

    def server_close(self):
        self.app.investigations.zha_observer.close()
        self.app.detection.close()
        self.app.repairs.close()
        super().server_close()

    def verified_admin(self, user_id, *, fresh=False):
        if not user_id or self.app.core_ws is None:
            return False
        with self._auth_lock:
            now = time.monotonic()
            if not fresh and self._auth_cache and self._auth_cache[0] == user_id and now-self._auth_cache[1] < 15:
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
        if kind.startswith("text/html"):
            from .command_center import page
            body=page(body,urlsplit(self.path).path)
        data = body if isinstance(body,bytes) else body.encode()
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
        if path == '/setup/research':
            enabled=self.server.app.investigations.research.enabled()
            return self.send_body(200,'<h1>Veřejný výzkum známých problémů</h1><p>Volitelné čtení GitHub Issues a vybrané oficiální dokumentace. Předává veřejnému serveru ověřenou verzi a vyhledávací slova. Neposílá celý spis ani přístupové klíče. Žádná placená vyhledávací služba se nezapíná. Nejvýše šest nových veřejných požadavků denně; výsledky jsou nedůvěryhodné podklady.</p>'
                +'<form method="post" action="research"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><label><input type="checkbox" name="enabled" value="yes" '+('checked' if enabled else '')+'>Souhlasím s veřejnými dotazy z vyšetřování</label><button>Uložit souhlas s výzkumem</button></form><a href="../setup">Zdroje</a>')
        if path == '/setup/music':
            settings=self.server.app.investigations.music.public_status()
            return self.send_body(200,'<h1>Čtecí diagnostika Music Assistantu</h1><p>Volitelné FastMCP připojení. Povol pouze čtecí diagnostiku; přehrávání, hlasitost, reload a konfigurace nejsou dostupné nástroje HADS. Události existují pouze od zapnutí bufferu. Token zůstává v controlleru.</p>'
                +'<form method="post" action="music"><input type="hidden" name="csrf" value="'+self.server.csrf+'">'
                +'<label>HTTPS endpoint /mcp/v1<input name="endpoint" required value="'+escape(settings['endpoint'],quote=True)+'"></label>'
                +'<label>Revokovatelný MA token<input type="password" name="token" maxlength="2048" autocomplete="new-password"></label>'
                +'<label>Vazby přehrávačů v JSON: HA entity_id na MA player_id<textarea name="mapping" maxlength="4096">'+escape(json.dumps(settings['mapping'],ensure_ascii=False))+'</textarea></label>'
                +'<label><input type="checkbox" name="enabled" value="yes" '+('checked' if settings['enabled'] else '')+'>Povolit cílená diagnostická čtení</label><button>Uložit připojení</button></form><a href="../setup">Zdroje</a>')
        if path == '/setup/ai':
            settings=self.server.app.investigations.provider.public_status()
            return self.send_body(200,'<h1>Poskytovatel AI pro Hermes</h1><p>Přístupový klíč zůstává v controlleru. Hermes dostává pouze redigované důkazy. Volání může být zpoplatněné; ChatGPT Plus není univerzální API přístup. OAuth zde není podporovaný.</p>'
                +'<form method="post" action="ai"><input type="hidden" name="csrf" value="'+self.server.csrf+'">'
                +'<label>HTTPS chat/completions endpoint<input name="endpoint" required value="'+escape(settings['endpoint'],quote=True)+'"></label>'
                +'<label>Model<input name="model" required maxlength="128" value="'+escape(settings['model'],quote=True)+'"></label>'
                +'<label>API klíč<input type="password" name="api_key" maxlength="2048" autocomplete="new-password" placeholder="Při zachování endpointu a modelu lze existující klíč ponechat prázdný."></label>'
                +'<label><input type="checkbox" name="consent" value="yes" '+('checked' if settings['enabled'] else '')+'> Výslovně povoluji modelová volání a předání redigovaných diagnostických údajů tomuto poskytovateli.</label>'
                +'<p>Nejvýše 8 požadavků na případ, 12 denně, 1024 výstupních tokenů na požadavek. Změna nastavení sama vyšetřování nespouští.</p><button>Uložit nastavení AI</button></form><a href="../">Přehled</a>')
        if path == '/setup':
            sources = self.server.app.snapshot()['sources']
            rows = ''.join('<li>' + escape(k) + ': ' + ('Čtení proběhlo' if v['read_succeeded'] else 'Čtení není dostupné: ' + escape(str(v['status'].get('last_error')))) + '</li>' for k,v in sources.items())
            rows+='<li><a href="setup/music">Nastavit volitelnou diagnostiku Music Assistantu</a></li>'
            rows+='<li><a href="setup/research">Nastavit veřejný výzkum</a></li>'
            if self.server.app.snapshot()['source_job']['state']=='running':
                rows='<li>Kontrola právě probíhá. Obnov stránku pro průběžné výsledky.</li>'+rows
            runtime=self.server.app.investigations.status()
            from .readiness import checklist
            gates=''.join('<article><h3>'+escape(g['label'])+' — '+('Ověřeno' if g['passed'] else 'Čeká / omezeno')+'</h3><p>'+escape(g['detail'])+'</p></article>' for g in checklist(self.server.app))
            return self.send_body(200,'<h1>Průvodce připraveností</h1>'+gates+'<ul>' + rows + '</ul><p>Izolovaný Hermes launcher: '+('dostupný; izolace se ověří před prvním modelovým voláním' if runtime['runtime_installed'] else 'není dostupný; AI je zablokovaná')+'</p><p>'+escape(runtime['runtime_probe']['summary_cs'])+'</p><form method="post" action="setup/runtime"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><button>Ověřit Hermes bez volání modelu</button></form><p>Živá HAOS a reálná modelová přejímka čekají. Obecné zásahy jsou zakázané. Dostupný je vlastní CAS test a zvlášť povolená jednoduchá světelná aktivace.</p><a href="setup/ai">Nastavit poskytovatele AI</a><form method="post" action="setup/check"><input type="hidden" name="csrf" value="' + self.server.csrf + '"><button>Ověřit skutečná čtení zdrojů</button></form><a href="./">Přehled domácnosti</a>')
        if path == '/setup/lighting':
            entities=[s for s in self.server.app.snapshot()['entities'] if s['entity_id'].startswith('automation.')]
            options=''.join('<option value="'+escape(s['entity_id'],quote=True)+'">'+escape(s.get('name',s['entity_id']))+' — '+escape(s['state'])+'</option>' for s in entities)
            return self.send_body(200,'<h1>Praktická oprava světelné automatizace</h1><p>Po potvrzení záměru mohu navrhnout opětovné zapnutí jednoduché automatizace s jedinou akcí light.turn_on na jednom světle. Konfiguraci nepřepisuji. Senzor musí spouštět jen při přechodu na on. Šablony, zámky, spínače a jiné služby katalog nepovolí.</p><p>Aktivací začnou fungovat budoucí triggery. Po dobu schválení nesmí stejný cíl upravovat jiný editor; nativní stavová služba není config CAS. Návrat vypne jen budoucí triggery, nevrací fyzické účinky světla.</p><form method="post" action="lighting"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><label>Automatizace<select name="entity_id" required>'+options+'</select></label><label><input type="checkbox" name="expected" value="yes" required>Potvrzuji, že má být zapnutá a že ovládá pouze určené bezpečné světlo.</label><button>Ověřit konfiguraci a uložit můj záměr</button></form><p>Obnov čtení Core, pokud v seznamu cíl chybí. Bez skutečně přečtené konfigurace nelze katalog povolit.</p>')
        if path == '/acceptance':
            identity=__import__('urllib.parse',fromlist=['parse_qs']).parse_qs(urlsplit(self.path).query).get('session',[''])[0]
            if not identity:
                return self.send_body(200,'<h1>Živá přejímka krok za krokem</h1><p>Tento režim sám neoznačuje HAOS za ověřený. Zaznamená skutečná čtení, zásah a funkční výsledek. Modelový komunikační test má zvláštní souhlas a nejvýše jedno volání na tuto přejímku.</p><form method="post" action="acceptance/create"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><label><input type="checkbox" name="isolated" value="yes" required>Pracuji v odděleném bezpečném testovacím prostředí.</label><button>Založit přejímkový protokol</button></form>')
            try:acceptance=self.server.app.acceptance.session(identity)
            except RepairBlocked:return self.send_body(404,'Přejímka neexistuje. Vytvoř nový protokol přes Živou přejímku.')
            rows=''
            status_names={'passed':'Prošlo','failed':'Selhalo','unavailable':'Nedostupné','pending':'Čeká na test'}
            choices=''.join('<option value="'+c['id']+'">'+escape(c['symptom'])+'</option>' for c in self.server.app.snapshot()['cases'])
            apps=''.join('<option value="'+escape(a['slug'],quote=True)+'">'+escape(a['name'])+'</option>' for a in self.server.app.snapshot()['applications'])
            for step in acceptance['steps']:
                rows+='<article><h2>'+escape(step['label'])+' — '+status_names[step['status']]+'</h2><p>'+escape(step['explanation'])+'</p><form method="post" action="acceptance/run"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><input type="hidden" name="session_id" value="'+identity+'"><input type="hidden" name="step" value="'+step['step']+'">'
                if step['step']=='logs':rows+='<label>Aplikace<select name="slug">'+apps+'</select></label>'
                if step['step'] in {'manual','automatic','repair','verification'}:rows+='<label>Spis<select name="incident_id">'+choices+'</select></label>'
                if step['step']=='model':rows+='<label><input type="checkbox" name="cost_consent" value="yes" required>Výslovně povoluji jedno skutečné modelové volání a případnou cenu. Nejde o důkaz diagnostického úsudku.</label>'
                rows+='<button>Provést tento test</button></form></article>'
            return self.send_body(200,'<h1>Živá přejímka</h1><p>Průběh obnovíš znovunačtením stránky. Reálný Hermes se testuje samostatným vyšetřováním vybraného skutečného incidentu.</p>'+rows+'<a download="HADS-anonymized-acceptance.json" href="acceptance/export?session='+identity+'">Stáhnout anonymizovaný report</a>')
        if path == '/acceptance/export':
            identity=__import__('urllib.parse',fromlist=['parse_qs']).parse_qs(urlsplit(self.path).query).get('session',[''])[0]
            try:value=self.server.app.acceptance.export(identity)
            except RepairBlocked:return self.send_body(404,'Přejímka neexistuje. Otevři svůj protokol.')
            return self.send_body(200,json.dumps(value,ensure_ascii=False,indent=2),'application/json; charset=utf-8')
        if path == '/setup/monitors':
            monitor=self.server.app.detection.snapshot()
            rows=''.join('<li>'+escape(r['entity_id'])+' — '+escape(r['kind'])+'; očekáváno '+escape(r['expected'])+'; '+str(r['grace_seconds'])+' s</li>' for r in monitor['rules'])
            return self.send_body(200,'<h1>Sledované funkce</h1><p>Pravidlo popisuje očekávání uživatele. Chyba v logu sama incident nevytváří. Přehrávání sleduji až po skutečném přechodu z hraní; při mezeře v odběru začíná pokrytí znovu.</p><p>'+escape(monitor['last_error'] or ('Odběr funguje.' if monitor['state']=='listening' else 'Odběr dosud není potvrzený.'))+'</p><ul>'+rows+'</ul><form method="post" action="monitors"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><label>Entita<input name="entity_id" required></label><label>Podmínka<select name="kind"><option value="unavailable">Zůstává nedostupná</option><option value="state">Nedosáhne očekávaného stavu</option><option value="playback">Přehrávání se zastaví</option><option value="response">Po spouštěcí události chybí odezva</option></select></label><label>Očekávaný stav<input name="expected" value="on" required></label><label>Doba v sekundách<input type="number" name="grace_seconds" value="30" min="1" max="3600"></label><label>Spouštěcí entita pro odezvu<input name="trigger_entity"></label><label>Požadovaný nový stav spouštěče (např. on; prázdné pro tlačítko)<input name="trigger_state"></label><label>Související automatizace (volitelné)<input name="automation_entity" placeholder="automation.hads_next_reference_test"></label><button>Uložit monitorovací pravidlo</button></form><form method="post" action="autonomy"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><label><input type="checkbox" name="enabled" value="yes" '+('checked' if monitor['autonomous_ai'] else '')+'>Povoluji automaticky zahájit AI vyšetřování nových funkčních incidentů v rámci limitu poskytovatele. Může být zpoplatněné.</label><button>Uložit souhlas s autonomním vyšetřováním</button></form>')
        if path == '/download/companion':
            import io,zipfile
            root=Path('/app/companion')
            if not root.is_dir():return self.send_body(404,'Companion balíček není v tomto image dostupný.')
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name in ('custom_components/hads_reference/__init__.py','custom_components/hads_reference/manifest.json','test-automation.yaml','README_CS.md'):
                    content=(root/name).read_bytes()
                    if len(content)>65536:raise ValueError('Neplatný companion balíček.')
                    archive.writestr(name,content)
            return self.send_body(200,stream.getvalue(),'application/zip')
        if path == '/setup/repair':
            state=self.server.app.repairs.status()
            return self.send_body(200,'<h1>Bezpečně podporované opravy</h1><p><a href="../download/companion" download="HADS_companion.zip">Stáhnout integraci, testovací YAML a přesný postup</a></p><p>Jediná zapisovací operace mění vlastní referenci izolované virtuální testovací automatizace přes atomické CAS companion integrace. Běžné automatizace se nepřepisují. Companion musí být zvlášť instalovaný na testovacím HA.</p><p>'+escape(state['backup'])+'</p><p>Rizikové zásahy a OneDrive restore: nepodporované, blokované.</p><form method="post" action="repair"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><label><input type="checkbox" name="enabled" value="yes" '+('checked' if state['enabled'] else '')+'>Potvrzuji oddělené virtuální testovací prostředí a povoluji tento úzký katalog. Každá změna stále vyžaduje zvláštní schválení.</label><button>Ověřit companion a uložit katalog</button></form><details><summary>Technický stav</summary><pre>'+escape(json.dumps(state,ensure_ascii=False,indent=2))+'</pre></details>')
        if path == '/setup/history':
            return self.send_body(200,'<h1>Historie a migrace</h1><p>Export spisu je dostupný v jeho detailu. Import Next schema 1 přenese pouze historické incidenty, výskyty a redigované důkazy. Schválení, tokeny, rozpracované zásahy a tvrzení o vyřešení nezískají platnost. RC3 databáze se nemění; přímý import jejího neověřeného schématu není povolený.</p><form method="post" action="import"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><label>JSON export jednoho spisu Next<textarea name="document" required maxlength="500000"></textarea></label><button>Importovat neautorizující historii</button></form>')
        if path.startswith('/export/'):
            try:document=self.server.app.store.export(path.removeprefix('/export/'))
            except KeyError:return self.send_body(404,'Spis neexistuje.')
            return self.send_body(200,document,'application/json; charset=utf-8')
        if path.startswith("/case/"):
            try:
                case = self.server.app.store.case(path.removeprefix("/case/"))
            except KeyError:
                return self.send_body(404, "Spis nebyl nalezen.")
            investigations=[r['content'] for r in case['records'] if r['kind'] in {'deterministic_investigation','investigation'}]
            result=investigations[-1] if investigations else {}
            jobs=self.server.app.investigations.for_case(case['incident']['id'])
            if jobs and jobs[0]['conclusion']:result=jobs[0]['conclusion']
            suggestion=result.get('repair_suggestion')
            suggestion_html=''
            if isinstance(suggestion,dict):
                suggestion_html='<h2>Návrh dalšího postupu</h2><p>'+escape(suggestion['summary_cs'])+'</p>'
                if suggestion.get('change'):
                    suggestion_html+='<p>Automatizace '+escape(suggestion['target'])+': '+escape(suggestion['change']['from'])+' → '+escape(suggestion['change']['to'])+'.</p>'
                suggestion_html+='<p>'+('Přesný plán připrav samostatným tlačítkem níže. Návrh modelu sám nic nemění.' if suggestion.get('status')=='supported_native_candidate' else 'Podle postupu zkontroluj nastavení ručně. Návrh sám nic nemění.')+'</p><ol>'+''.join('<li>'+escape(x)+'</li>' for x in suggestion['manual_steps_cs'])+'</ol>'
                decisions=[r['content'] for r in case['records'] if r['kind']=='repair_suggestion_decision' and r['content'].get('suggestion_id')==suggestion['suggestion_id']]
                if decisions:
                    suggestion_html+='<p>'+('Tento návrh jsi zamítl. HADS nic neprovedl.' if decisions[-1]['decision']=='reject' else 'Zvolil jsi ruční kontrolu. Ověření výsledku stále čeká.')+'</p>'
                else:
                    suggestion_html+='<form method="post" action="../repair/preference"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><input type="hidden" name="incident_id" value="'+escape(case['incident']['id'],quote=True)+'"><input type="hidden" name="suggestion_id" value="'+escape(suggestion['suggestion_id'],quote=True)+'"><button name="decision" value="manual">Chci postupovat ručně</button><button name="decision" value="reject">Zamítnout tento návrh</button></form>'
                suggestion_html+='<p>Tato volba nepotvrzuje provedení ani úspěch opravy. Incident čeká na funkční ověření.</p>'
            progress=''.join('<li>'+escape(step['reason'])+'</li>' for job in jobs[:1] for step in job['steps'])
            from .investigator_roles import ROLE_LABELS
            progress+=''.join('<li>'+escape(ROLE_LABELS.get(r['content'].get('role'),'Vyšetřování'))+': '+escape(r['content'].get('task',''))+'</li>'
                for r in case['records'] if r['kind']=='investigator_selected' and jobs and r['content'].get('job_id')==jobs[0]['id'])
            from .command_center import repair_cards
            suggestion_html+=repair_cards(self.server.app,case['incident']['id'],self.server.csrf)
            if self.server.app.repairs.status()['enabled']:
                suggestion_html+='<form method="post" action="../repair/prepare"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><input type="hidden" name="incident_id" value="'+case['incident']['id']+'"><button>Připravit přesnou opravu vlastní testovací reference</button></form>'
            for target in case['incident']['components']:
                if target.startswith('automation.'):
                    suggestion_html+='<form method="post" action="../repair/native_prepare"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><input type="hidden" name="incident_id" value="'+case['incident']['id']+'"><input type="hidden" name="entity_id" value="'+escape(target,quote=True)+'"><label><input type="checkbox" name="exclusive" value="yes" required>Potvrzuji, že tuto světelnou automatizaci nyní nikdo současně neupravuje.</label><button>Připravit ověřené opětovné zapnutí světelné automatizace</button></form>'
            suggestion_html+='<a href="../setup/lighting">Ověřit a vybrat bezpečný světelný cíl</a>'
            suggestion_html+='<a href="../export/' +case['incident']['id']+'">Exportovat spis JSON</a>'
            stop_form=('<form method="post" action="../investigate/cancel"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><input type="hidden" name="job_id" value="'+escape(jobs[0]['id'],quote=True)+'"><button>Zastavit vyšetřování</button></form>') if jobs and jobs[0]['state']=='investigating' else ''
            reads=''.join('<li>'+escape(row['name'])+': '+escape(row['result']['status'])+'</li>' for job in jobs[:1] for row in job['reads'])
            acknowledge='<label><input type="checkbox" name="ack_unknown" value="yes"> Povolím další pokus i v případě, že předchozí nedokončené modelové volání mohlo být účtováno.</label>' if jobs and jobs[0]['state']=='blocked' else ''
            return self.send_body(200,'<!doctype html><html lang="cs"><meta charset="utf-8"><h1>' + escape(case['incident']['symptom'])
                +'</h1><h2>Průběh vyšetřování</h2><ul>'+progress+'</ul>'+stop_form+'<details><summary>Čtení a dostupnost zdrojů</summary><ul>'+reads+'</ul></details><form method="post" action="../investigate"><input type="hidden" name="csrf" value="'+self.server.csrf+'"><input type="hidden" name="incident_id" value="'+escape(case['incident']['id'],quote=True)+'">'+acknowledge+'<button>Spustit nebo obnovit čtecí vyšetřování Hermes</button></form><a href="../setup/ai">Nastavení AI</a>'
                + '<h2>Pracovní závěr</h2><p>' + escape(result.get('summary_cs','Vyšetřování ještě nemá závěr.'))
                + '</p><h2>Další potřebné důkazy</h2><ul>' + ''.join('<li>'+escape(str(x))+'</li>' for x in result.get('needed',[]))
                + '</ul><h2>Další krok</h2><p>'+escape(result.get('next_test_cs','Doplň chybějící důkazy nebo spusť vyšetřování.'))+'</p>'+suggestion_html+'<p>'+('Funkční podmínka byla ověřena; report je v historii.' if case['incident']['status']=='resolved' else 'Případ zůstává otevřený do ověření funkční podmínky.')+'</p><details><summary>Technické důkazy spisu</summary><pre>'
                + escape(json.dumps(case,ensure_ascii=False,indent=2)) + '</pre></details></html>')
        if path not in {"/", "/index.html"}:
            return self.send_body(404, "Stránka nebyla nalezena.")
        value = self.server.app.snapshot()
        core = value["core"]
        health=value["system_health"]
        health_text=("Celkový stav zatím není ověřený." if health["last_check_at"] is None else "Prověřuji "+str(health["active_findings"])+" podložených systémových nálezů. Nepřečtené zdroje zůstávají neověřené." if health["active_findings"] else "Poslední dostupná strukturovaná čtení neukazují aktivní systémový nález. Neověřené zdroje tím nejsou potvrzené jako zdravé.")
        text = "Čtení Core funguje." if core["available"] else core["last_error"] or "Čtení Core čeká."
        cases = "".join('<article><h3>' + escape(c["symptom"]) + '</h3><p>Výskytů: ' + str(c["occurrence_count"]) +
            '</p><a href="case/' + escape(c["id"], quote=True) + '">Otevřít důkazy spisu</a></article>' for c in value["cases"] if c["status"]=="open")
        def case_cards(rows):
            return ''.join('<article><h3>'+escape(c['symptom'])+'</h3><p>Výskytů: '+str(c['occurrence_count'])+'</p><a href="case/'+c['id']+'">Otevřít spis a reporty</a></article>' for c in rows)
        resolved=case_cards([c for c in value['cases'] if c['status']=='resolved'])
        recurring=case_cards([c for c in value['cases'] if c['occurrence_count']>1])
        waiting=[]
        for c in value['cases']:
            plans=self.server.app.repairs.plans(c['id'])
            jobs=self.server.app.investigations.for_case(c['id'])
            if any((p['status'] is None and p.get('decision') not in {'reject','manual'}) or p['status']=='applied_verification_pending' for p in plans) or (jobs and jobs[0]['state'] in {'waiting_for_user','blocked','waiting_for_source'}):waiting.append(c)
        waiting_html=case_cards(waiting)
        options = "".join('<option value="' + escape(e["entity_id"], quote=True) + '"></option>' for e in value["entities"])
        applications = ''.join('<option value="' + escape(a['slug'],quote=True) + '">' + escape(a['name']) + '</option>' for a in value['applications'])
        body = '''<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HADS Next</title><style>body{font:17px/1.6 system-ui;margin:2rem auto;padding:0 1rem;max-width:960px;color:#182638;background:#f3f5f7}article,form{background:white;padding:1rem;margin:1rem 0;border:1px solid #ccd6df;border-radius:6px}input,textarea,button{font:inherit;padding:.5rem;box-sizing:border-box;max-width:100%}input,textarea{width:100%}button{background:#12695f;color:white;border:0;border-radius:4px;cursor:pointer}.notice{border-left:4px solid #b36b12;padding:1rem;background:#fff7e8}a{color:#12695f}</style>
<h1>HADS Next</h1><p class="notice">Vývojová verze ''' + VERSION + '''. Hermes vyžaduje izolovaný runtime a výslovně povoleného poskytovatele AI. Obecné zásahy jsou zakázané. Katalog vlastní testovací reference má samostatné schvalování; HAOS přejímka čeká.</p>
<nav><a href="./">Moje domácnost</a> · <a href="#investigation">Vyšetřování</a> · <a href="#waiting">Čeká na mě</a> · <a href="#resolved">Opraveno</a> · <a href="#recurring">Opakující se problémy</a> · <a href="setup">Agenti a zdroje</a> · <a href="#investigation">Historie</a></nav>
<h2>Jak zdravý je Home Assistant</h2><p>'''+escape(health_text)+'''</p><h2>Co je dostupné</h2><p>''' + escape(text) + '</p><p>Načtených entit: ' + str(core["entity_count"]) + ". Samotná nedostupnost entity neurčuje příčinu závady.</p>" + '''
<form method="post" action="read"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''"><button>Obnovit čtení Core</button><p>Nejvýše jednou za minutu.</p></form>
<h2 id="investigation">Co nefunguje a co HADS vyšetřuje</h2>''' + (cases or "<p>Zatím nebyl nahlášen žádný funkční incident.</p>") + '''
<h2>Nahlásit problém</h2><form method="post" action="incident"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''">
<label>Co se stalo?<textarea name="symptom" maxlength="1000" required placeholder="Rádio se právě samo vypnulo."></textarea></label>
<label>Kdy se to stalo? Časové pásmo ''' + escape(value['timezone']) + '''. Pro právě probíhající problém nechej prázdné.<input type="datetime-local" name="occurred_at"></label>
<label>Dotčená entita<input name="entity_id" list="entities" maxlength="200" required placeholder="media_player.radio"></label><datalist id="entities">''' + options + '''</datalist><button>Uložit incident a přečíst historii</button></form>
<h2>Vyšetřit aplikaci HAOS</h2><form method="post" action="incident/app"><input type="hidden" name="csrf" value="''' + self.server.csrf + '''"><label>Aplikace<select name="slug" required>''' + applications + '''</select></label><label>Co nefunguje?<input name="symptom" required maxlength="1000"></label><button>Načíst stav, statistiky a protokol aplikace</button></form>
<h2 id="waiting">Co ode mě potřebuje</h2><p>Ve spisu najdeš přesný plán, chybějící souhlas nebo požadovaný funkční test.</p>''' + (waiting_html or "<p>Žádná čekající rozhodnutí.</p>") + '''
<h2 id="resolved">Co se podařilo vyřešit</h2><p>Zobrazují se pouze spisy uzavřené funkčním ověřením.</p>''' + (resolved or "<p>Dosud žádný ověřený výsledek.</p>") + '''
<h2 id="recurring">Co se opakuje</h2><p>Skutečné další výskyty mají vlastní čas; opakované načtení stejného důkazu je nepřidává.</p>''' + (recurring or "<p>Zatím nejsou opakované případy.</p>") + '''
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
        if (urlsplit(self.path).path.startswith(('/repair/','/acceptance/')) or urlsplit(self.path).path=='/setup/lighting') and not self.server.verified_admin(self.headers.get('X-Remote-User-Id'),fresh=True):
            return self.send_body(403,'Aktuální oprávnění vlastníka nelze potvrdit.')
        if self.headers.get("Content-Type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return self.send_body(415, "Nepodporovaný formát.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= (2*1024*1024 if urlsplit(self.path).path=='/setup/import' else 8192):
                raise ValueError()
            form = parse_qs(self.rfile.read(size).decode(), max_num_fields=10, strict_parsing=True)
            if form.get("csrf") != [self.server.csrf]:
                return self.send_body(403, "Formulář vypršel. Obnov stránku.")
            path = urlsplit(self.path).path
            if path == "/read":
                self.server.app.refresh()
            elif path == '/setup/ai':
                self.server.app.investigations.provider.configure(endpoint=form.get('endpoint',[''])[0],model=form.get('model',[''])[0],
                    api_key=form.get('api_key',[''])[0],consent=form.get('consent')==['yes'],principal=self.headers['X-Remote-User-Id'])
                self.send_response(303);self.send_header('Location','ai');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/music':
                service=self.server.app.investigations
                with self.server.app._read_lock:
                    service.music.configure(endpoint=form.get('endpoint',[''])[0],token=form.get('token',[''])[0],
                        mapping=json.loads(form.get('mapping',['{}'])[0]),enabled=form.get('enabled')==['yes'],principal=self.headers['X-Remote-User-Id'])
                    service.broker.music=service.music.reader()
                self.send_response(303);self.send_header('Location','music');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/research':
                self.server.app.investigations.research.configure(form.get('enabled')==['yes'],self.headers['X-Remote-User-Id'],self.server.app.owner())
                self.send_response(303);self.send_header('Location','research');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/investigate':
                identity=form.get('incident_id',[''])[0]
                self.server.app.investigations.start(identity,self.headers['X-Remote-User-Id'],ack_unknown=form.get('ack_unknown')==['yes'])
                self.send_response(303);self.send_header('Location','case/'+identity);self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/investigate/cancel':
                service=self.server.app.investigations;job_id=form.get('job_id',[''])[0]
                job=service.jobs.get(job_id)
                service.cancel(job_id,self.headers['X-Remote-User-Id'])
                self.send_response(303);self.send_header('Location','../case/'+job['incident_id']);self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/repair/preference':
                identity=form.get('incident_id',[''])[0];choice=form.get('decision',[''])[0]
                jobs=self.server.app.investigations.for_case(identity)
                proposal=(jobs[0].get('conclusion') or {}).get('repair_suggestion') if jobs else None
                if choice not in {'manual','reject'} or not proposal or not secrets.compare_digest(proposal['suggestion_id'],form.get('suggestion_id',[''])[0]):
                    raise ValueError('Tato verze návrhu již není aktuální.')
                self.server.app.store.record(identity,'repair_suggestion_decision',{'job_id':jobs[0]['id'],'suggestion_id':proposal['suggestion_id'],
                    'decision':choice,'principal':self.headers['X-Remote-User-Id'],'approval_granted':False,'functional_result':'not_verified'})
                self.send_response(303);self.send_header('Location','../case/'+identity);self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/lighting':
                if form.get('expected')!=['yes']:raise RepairBlocked('Potvrď zamýšlené bezpečné chování.')
                self.server.app.repairs.allow_automation(form.get('entity_id',[''])[0],self.headers['X-Remote-User-Id'])
                self.send_response(303);self.send_header('Location','lighting');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/repair/native_prepare':
                self.server.app.repairs.prepare_native(form.get('incident_id',[''])[0],form.get('entity_id',[''])[0],self.headers['X-Remote-User-Id'],exclusive=form.get('exclusive')==['yes'])
            elif path == '/repair/physical':
                self.server.app.repairs.confirm_physical(form.get('plan_id',[''])[0],self.headers['X-Remote-User-Id'])
            elif path == '/acceptance/create':
                identity=self.server.app.acceptance.create(self.headers['X-Remote-User-Id'],isolated_confirmed=form.get('isolated')==['yes'])
                self.send_response(303);self.send_header('Location','../acceptance?session='+identity);self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/acceptance/run':
                identity=form.get('session_id',[''])[0]
                self.server.app.acceptance.run(identity,form.get('step',[''])[0],self.headers['X-Remote-User-Id'],{'incident_id':form.get('incident_id',[''])[0],'slug':form.get('slug',[''])[0],'cost_consent':form.get('cost_consent')==['yes']})
                self.send_response(303);self.send_header('Location','../acceptance?session='+identity);self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/monitors':
                self.server.app.detection.configure({'entity_id':form.get('entity_id',[''])[0],'kind':form.get('kind',[''])[0],
                    'expected':form.get('expected',['on'])[0],'grace_seconds':int(form.get('grace_seconds',['30'])[0]),'trigger_entity':form.get('trigger_entity',[''])[0],'automation_entity':form.get('automation_entity',[''])[0],'trigger_state':form.get('trigger_state',[''])[0]},self.headers['X-Remote-User-Id'])
                self.server.app.detection.start()
                self.send_response(303);self.send_header('Location','monitors');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/autonomy':
                self.server.app.detection.consent(form.get('enabled')==['yes'],self.headers['X-Remote-User-Id'])
                self.send_response(303);self.send_header('Location','monitors');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/repair':
                self.server.app.repairs.configure(form.get('enabled')==['yes'],self.headers['X-Remote-User-Id'])
                self.send_response(303);self.send_header('Location','repair');self.send_header('Content-Length','0');self.end_headers();return
            elif path == '/setup/import':
                from .migration import import_case
                value=json.loads(form.get('document',[''])[0]);import_case(self.server.app.store,value)
            elif path == '/repair/prepare':
                self.server.app.repairs.prepare(form.get('incident_id',[''])[0],self.headers['X-Remote-User-Id'])
            elif path == '/repair/decide':
                self.server.app.repairs.decide(form.get('plan_id',[''])[0],form.get('decision',[''])[0],self.headers['X-Remote-User-Id'])
            elif path == '/repair/rollback':
                self.server.app.repairs.rollback(form.get('plan_id',[''])[0],self.headers['X-Remote-User-Id'])
            elif path == '/setup/check':
                self.server.app.request_source_check()
            elif path == '/setup/runtime':
                self.server.app.investigations.request_probe(self.headers['X-Remote-User-Id'])
                self.send_response(303);self.send_header('Location','../setup');self.send_header('Content-Length','0');self.end_headers();return
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
        except (JobBlocked,RepairBlocked) as error:
            return self.send_body(409,escape(str(error)))
        except (ValueError, KeyError, UnicodeError):
            return self.send_body(400, "Neplatné hlášení nebo dosažený limit. Zkontroluj popis a entity_id.")
        self.send_response(303)
        self.send_header("Location", "../" if path.count('/') > 1 else "./")
        self.send_header("Content-Length", "0")
        self.end_headers()


def prepare_data_directory(path):
    if ctypes.CDLL(None).prctl(38,1,0,0,0)!=0:raise RuntimeError('Cannot enforce controller no-new-privileges')
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
    runtime_error=None
    if Path('/opt/hermes-root/opt/hermes/HADS_PINNED_REVISION').is_file():
        from .runtime_launcher import RuntimeLauncher
        try:launcher=RuntimeLauncher()
        except (OSError,RuntimeError,EOFError) as error:runtime_error='launcher_initialization_'+type(error).__name__
    else:runtime_error='pinned_runtime_not_installed'
    path = prepare_data_directory(os.environ.get("HADS_DATA_DIR", "/data/hads-next"))
    core = CoreReader(SupervisorCoreTransport(token)) if token else None
    ws = CoreWSReader(NativeWebSocket('ws://supervisor/core/websocket',token,supervisor_proxy=True)) if token else None
    supervisor = SupervisorReader(SupervisorTransport(token)) if token else None
    from .native_repair import AutomationStateTransport
    writer=AutomationStateTransport('http://supervisor',token,supervisor=True) if token else None
    app = Application(path, core, core_ws=ws, supervisor=supervisor,launcher=launcher,runtime_error=runtime_error,automation_writer=writer)
    if app.owner():
        app.investigations.zha_observer.start();app.detection.start()
        if app.repairs.status()['enabled'] or app.repairs.status()['native_state_targets']:app.repairs.start()
    threading.Thread(target=app.refresh, daemon=True).start()
    try:Server(("0.0.0.0", 8099), app, owner_user_id=owner).serve_forever()
    finally:
        app.investigations.zha_observer.close()
        app.detection.close();app.repairs.close()
        if launcher:launcher.close()


if __name__ == "__main__":
    main()
