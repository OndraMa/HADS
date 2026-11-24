# Aktuální kandidát 4.7.0-rc2

Aktuální změny a otevřené bezpečnostní/provozní brány: [RELEASE_4.7.0-rc2.md](RELEASE_4.7.0-rc2.md). Upload ACK nestačí. Bez pozitivního funkčního testu není oprava potvrzena. Níže zachovaný starší obsah nesmí rozšiřovat tuto smlouvu.

# HADS 4.5.0 — ověření a hranice důkazů

Testy se spouštějí z kořene zdroje:

```sh
python -m unittest discover -s tests -p 'test_*.py'
node --check web/app.js
node --check web/webmcp.js
node tests/test_webmcp_contract.mjs
```

## Automatické regresní testy

93 testů na Windows s dostupným PyYAML. Supervisor, HA WebSocket, OneDrive a OpenAI
jsou nahrazené testovacími odpověďmi; skutečná zařízení ani služby se nemění.

| Oblast | Co testy ověřují |
|---|---|
| Schvalování | Oprava versus závěr, schválení přežije restart, ignorování/zamítnutí/sledování nepřepíše planner |
| Souběh | Změna rozhodnutí během výzkumu, dvojí chat/volba, přerušený job bez automatického opakování |
| Přesný plán | Neplatné/prázdné akce, přesný notify rename, volba mezi dvěma telefony, odmítnutí neexistující náhrady |
| Konflikty | Zastaralý YAML hash, konfliktní automatizace, duplicitní cíl, samostatná DB dávka |
| Zálohy | Povinnost plné zálohy, ID/rozsah/DB metadata, backup před zápisem, nemožnost vypnout write gate |
| Rollback | Odmítnutí přepisu novější cizí změny a přímé obnovy živé DB |
| SQLite | Opt-in, bezpečná cesta, konzistentní kopie, quick_check, rozsah retence, obě zálohy před purge |
| Konektory | Spook/Watchman/Inspector importy, Hamster handshake, neověřená aktualizační entita, expirace snapshotu, odmítnutí health-only JSON |
| Transport | Bezpečné GET retry, cache pouze explicitně; 401 a stale data nejsou úspěšné živé ověření |
| API chat | Unicode v JSON, trvalá historie, limity volání/vstupu/výstupu, skutečné usage, neúplná odpověď není plán |
| Protokoly | Přehled Core/Supervisor/host/add-on zdrojů a výsledků sběru |
| WebMCP | 9 nástrojů, omezení odpovědí, redakce, přísná ID, audit běhů, potvrzovací marker a zákaz mutací oprav |
| Kontrakty 4.5 | MCP notifikace, bezpečné Hamster čtení, strukturovaný Watchman, Entity Availability deduplikace, HAGHS příznaky, Inspector replacement, sémantika Spook a idempotentní výsledek dávky |

## Prohlížeč

`tests/serve_preview.py` spouští skutečný HTTP handler, databázi a panel nad
izolovanými syntetickými incidenty. Externí operace jsou testovací náhražky.
Kontroluje se schválení → aktivní tlačítko → dávka/záloha → sledování a zamčený
zápis, česká zpráva v konverzaci a dohledatelné rozhodnutí. Tento postup není
testem kompatibility se skutečným Ingressem ani instalovanými doplňky.

Samostatný Node test spouští `webmcp.js` proti modelu browserového API, ověřuje
registraci všech devíti nástrojů, JSON schémata, zrušení nepotvrzeného úkonu,
potvrzený diagnostický POST a UI × backend kontrolní snímek. Nejde o důkaz, že
konkrétní browser a nadřazený iframe Home Assistantu WebMCP skutečně povolí.

Všechny vložené Python bloky instalátoru prošly kompilací. Binární modul
Tree-sitter Bash není dostupný pro zdejší Python 3.14 a Git Bash zde není
dostupný, takže samotný shellový instalační tok ani Bash parser nebyly spuštěny.
Payload a source ZIP se porovnávají bajt po bajtu se zdrojem; kontroluje se
SHA-256 a unikátní klíče ve všech YAML konfiguracích. Přesný stav obsahuje
release verification JSON.

## Co tím prokázáno není

- Instalace, Docker build a běh na vašem HAOS / konkrétní architektuře.
- Obnovitelnost plné zálohy; kontrolují se metadata, nikoli restore test.
- Živé endpointy všech verzí Spook/Hamster/Inspector/HADocs.
- Skutečná funkce opravené automatizace nebo dokončení asynchronního purge.
- Reálné placené OpenAI volání, cena incidentu či spolehlivost webových závěrů.
- Reálná registrace WebMCP a kompletní UI tok v konkrétním HA Ingressu; ten se
  provede po instalaci podle samostatného akceptačního scénáře.

Před provozním nasazením postupujte podle kontrolního seznamu v
[RELEASE_4.5.0.md](RELEASE_4.5.0.md). Žádný stav v UI není zárukou bezchybnosti.
