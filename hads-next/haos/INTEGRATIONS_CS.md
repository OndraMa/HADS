# Co obsahuje HADS Next RC3 a co vyžaduje připojení

| Součást | V balíčku HADS | Stav ověření a potřebné nastavení |
|---|---|---|
| Home Assistant Core | Nativní REST/WebSocket adaptéry: stavy, registry, historie, traces, Action history, System Health, System Log a Repairs | Integrační test se skutečným Core 2026.11.0. Uživatel doložil devět čtení RC2 s Core 2026.11.1; RC3 zatím nemá živou přejímku. |
| Supervisor / HAOS / aplikace | Nativní omezené čtení informací, seznamu aplikací, logů a metrik | Ověřené zdrojové kontrakty a izolované testy. Dostupnost v konkrétním HAOS se ukáže ve Zdroje a připravenost. |
| Původní NousResearch Hermes Agent | Ano, přímo ve výsledné image aplikace, pin `d923a5eb487a17c0a68801bba9ef0f56c81040a8`, původní AIAgent a skutečná smyčka nástrojů | Při stavbě se stáhne připnutý upstream a constraints. Není třeba instalovat druhou HA aplikaci Hermes. Runtime má izolaci, vlastní UID, zákaz shellu/socketů a jediný read-only broker. |
| Model pro Hermes | Konfigurace a zabezpečený zprostředkovatel | Model ani API účet nejsou přiložené. Poskytovatel a náklady vyžadují výslovný souhlas. Test s původním agentem a skriptovaným endpointem neprokazuje úsudek běžného LLM. |
| MCP pro Music Assistant | Přiložený Streamable HTTP klient a pět pevných read-only diagnostických čtení přes broker | FastMCP server musí poskytovat Music Assistant. Připojení, token a mapování přehrávače jsou volitelné privátní nastavení. HTTPS `/mcp/v1`; kompatibilita odpovídá ověřeným schématům v `music_assistant.py`, nikoli libovolnému MCP serveru. Živé připojení dosud nebylo prokázané. |
| Obecný HA-MCP nebo neomezený Hermes MCP klient | Není povinná externí závislost ani volná zapisovací cesta | Srovnatelná dostupná data se čtou nativním HA API. Obecný MCP, shell nebo Python nesmí obejít schválení. Hermes dostává pouze schválený katalog diagnostických čtení brokeru. |
| ZHA / Zigbee | Omezený žurnál softwarových událostí, vazby na registry a traces | Vlastní ZHA integrace a rádio zůstávají v HA. Fyzické zařízení a nezaznamenaný stisk nelze ověřit offline. |
| Spook | Použití jeho nálezů dostupných přes nativní HA Repairs | Spook se do HA automaticky neinstaluje. Pokud není přítomen, nativní Repairs zůstávají dostupné bez něj. |
| Watchman | Kontrola doložených přímých referencí nativními čteními | Watchman se automaticky neinstaluje. Úplná shoda jeho vlastního reportu se netvrdí; nepřečtený výstup se nevydává za ověřený. |
| CAS companion | Přiložená volitelná custom integrace a virtuální testovací okruh | Potřebná pouze pro vlastní demonstrační CAS referenci. Praktická nativní světelná aktivace companion nepotřebuje. |
| Opravy a schvalování | Nezávislý planner, Approval Authority, executor, funkční verifier, report a podporovaný návrat | Pouze pozitivní katalog. AI nemá HA klíč ani zapisovací nástroje. Obecné konfigurace, restartování aplikací a rizikové zásahy bez příslušné zálohy nejsou automaticky povolené. |

Adaptér není důkaz živého připojení. Vypnutá nebo nenastavená integrace zůstává
viditelně neověřená. HADS neinstaluje externí aplikace, nepovoluje placený model
a nezvyšuje oprávnění kvůli tomu, aby položka v seznamu zezelenala.

Při aktuálně doloženém nedostatku paměti nech AI vypnutou. Rezerva 576 MiB
zůstává povinná; její pouhé těsné překročení není přejímka při zátěži.

## RC4: automatické pokračování bez klíče AI

Core a Supervisor statistiky se čtou přímo přes dokumentované GET `/core/stats`
a `/supervisor/stats`, běžící aplikace přes `/addons/{slug}/stats`. Kontrakty
ověřeny v Supervisor 2026.11.0, commit c1c6f0a754c0656eb1af189f11009f1cfc4b3e28.
Jde o vlastní nativní API, není třeba instalovat HA-MCP, Spook nebo další server
jen kvůli těmto údajům. Fronta je trvalá, sériová, omezená na 24 aplikací,
failed read se nejvýše jednou zopakuje s odstupem a neznámý údaj není nula.
Veřejný HEAD smí pouze na pevné `https://github.com/`, bez auth, cookies,
redirectů, obsahu odpovědi nebo dat domácnosti v URL. Jeho síťový kontext je
aplikace HADS; úspěch nedokazuje přístup integrace v Core.

Po prvním sběru paměti následuje po pěti minutách ještě jedno automatické
porovnání Core, Supervisora a nejvýše tří aplikací. Další měřicí smyčka se
neopakuje bez nového skutečného výskytu. Po úvodní instalaci/přihlášení HADS
sám ověří nativní zdroje a pokusí se ověřit izolovaný Hermes bez modelu;
paměťová brána stále platí.
