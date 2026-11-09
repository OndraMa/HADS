# Výsledky HADS Next, 2026-11-09

## P3: nativní zdroje a volitelný Music Assistant

**OVĚŘENO PROTI SKUTEČNÉMU CORE V AMD64 BUILD KONTEJNERU:** vedle předchozí
Hermes smyčky prošly System Health (včetně dokončení streamu), Repairs, System
Log, Recorder REST historie, Action history a autentizovaný živý odběr
`zha_event`. Virtuální rádiová entita reagovala na skutečnou službu
`media_player.media_stop`; čtecí diagnostika spojila příkaz se změnou pomocí
kontextu. Chybějící historický kontext smí doplnit pouze aktuální stav se stejnou
entitou, hodnotou a přesným časem změny. Negativní test pozdější stav odmítá.

Vložená ZHA událost skutečným Core event busem spustila skutečnou automatizaci;
broker načetl událost, trace a nový stav virtuálního cíle. Je to softwarový
řetězec; fyzický stisk, koordinátor ani rádiový stream test neobsahuje.
Původní Hermes opět provedl šest čtení / sedm požadavků na skriptovaný HTTPS
model / pět nových důkazů. Znovu prošel SIGKILL, obnovení bez opakování čtení
a negativní shell/Python/write scénáře. [Úplný protokol a hashe vstupů](evidence/hermes-core-sources.json).

**IMPLEMENTOVÁNO A KONTRAKTNĚ TESTOVÁNO:** volitelné FastMCP čtení MA přes
pevný katalog a ověření read-only schémat, privátní konfigurace vlastníka,
rozlišení vypnutého bufferu, redakce stream URL. ZHA žurnál má retenci,
deduplikaci, detekci mezer a evidenci chyby připojení. Supervisor data jsou
omezena výběrem polí; aplikační `options` se do důkazů nepředávají.

**ČEKÁ:** skutečný Supervisor, Music Assistant server, fyzické ZHA/radio,
autorizovaný reálný LLM, ARM64/RPi a HAOS. Není vydán nový instalační archiv.
P4–P6 (výzkum, role, předávání opravných návrhů a finální instalační cesta)
ještě nejsou dokončené. Historické checkpointy níže mají svůj vlastní rozsah.

## P0–P2: skutečný vyšetřovací broker a provozní controller

**HOTOVO A PROKAZATELNĚ FUNGUJE, AMD64 build container:** originální Hermes
`d923a5e` řídí čtení přes pojmenovaný Evidence Broker a skutečné Core 2026.11.0.
Produkční controller zpracoval ověření HA admin identity, registraci vlastníka,
explicitní opt-in, skutečné HTTPS volání místního skriptovaného modelu, frontu,
šest čtení a pět nových důkazů, včetně skutečného 404 pro chybějící entitu.
Závěr je uložen v češtině; incident se pouze analýzou neuzavírá. Worker s UID
65534 je izolovaný chroot/NNP/seccomp, controller má UID 65532 a drží tokeny.

Prošel skutečný SIGKILL workeru a pokračování novým procesem ve stejném
vyšetřování z perzistentního čtení bez opakovaného požadavku na Core.
Negativní scénáře původního agenta odmítají shell, Python čtení tokenů a write
parametr. Chybějící Supervisor se vykáže jako nedostupný; vymyšlená jistá
příčina bez důkazů se nepřijímá. Viz [protokol](evidence/hermes-controller-core.json)
a [popis runtime](hermes.md). Model je skriptovaný a ingress peer simulovaný.

**IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST:** provozní start izolovaného launcheru,
modelová konfigurace v souboru 0600 mimo worker, persistentní fronta, metering,
resume a webové ovládání. HAOS výchozí instalační cesta se ještě dokončuje;
obecné produkční zápisy jsou vypnuté.

**STAV TOHOTO HISTORICKÉHO P0–P2 CHECKPOINTU:** tehdy chyběl P3 Music Assistant a ZHA sběr, P4 výzkum a specializace,
P5 úplné předávání návrhů, P6 ARM64/HAOS přejímka a instalační kandidát.
Autorizovaný reálný modelový endpoint ani testovací HAOS nejsou v cloudu
dostupné. Toto není výsledek autonomního úsudku reálného LLM ani živé domácnosti.
Nový release nebo instalační archiv zatím nevzniká. Níže jsou starší checkpointy.

## Nově: skutečná oprava v odpojeném Home Assistant Core

Uživatel zatím nemá testovací HAOS. V cloudu byl proto skutečně sestaven a
spuštěn Home Assistant Core `2026.11.0` z PyPI. Nativní HA autentizace, validace,
registry, automation trace, služby a event bus v tomto testu nejsou mocky.

**HOTOVO A PROKAZATELNĚ FUNGUJE — pouze Core container:** nefunkční virtuální
automatizace → spis s konfigurací, stavem a skutečným trace → přesný plán
jediné reference → simulované místní schválení → skutečné Core config API →
skutečný trigger a změna virtuálního cíle se společným kontextem → dvě reálné
sekundy aktivního sledování → uložený český report a uzavření spisu.
Řízeně vložená skutečná změna cíle na `off` potom znovu otevřela tentýž spis;
vynechání staršího důkazu v dalším ověření úspěch neobnovilo.
Odmítnuty byly zápisy bez souhlasu, cizí principal, nevirtuální cíl a opakované
vykonání po znovuvytvoření vykonavatele nad stejnou databází. Samotné potvrzení
zápisu nechalo opravu čekat na funkční ověření.

Reprodukce: [lab/README_CS.md](../lab/README_CS.md).
Přesné vstupy, image, naměřené RSS a výsledky: [core-lab.json](evidence/core-lab.json).
Tento běh neobsahuje Hermes a není splněním celého autonomního workflow.
Neprokazuje procesový restart celého HAOS ani stabilitu fyzického zařízení.

**IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST:** provozní čtecí propojení a průvodce
popsané níže. Laboratorní zapisovač je oddělen v `lab/` a do instalačního
payloadu se nebalí; v provozní HAOS aplikaci zůstávají opravy vypnuté.

**NEDOKONČENO / BLOKOVÁNO:** bezpečná produkční Hermes integrace a živý writer,
modelový poskytovatel s výslovným opt-in, HAOS/Supervisor/Ingress přejímka,
OneDrive restore důkaz, MA FastMCP, ZHA, fyzické funkční zkoušky a ARM64/RPi.
Core config API nemá CAS/ETag, zapisuje celý soubor a může doplnit ID ostatním
automatizacím; bezpečný souběh s HA UI není vyřešen. Laboratorní úspěch tyto
mezery neuzavírá. Nový instalátor ani hotové vydání se z této práce nepublikuje.

## Pracovní architektonická oprava — není dokončený produkt

Větev `codex/hads-next-correction` navazuje na neúplnou 0.1.0-dev1.
Nový instalátor ani další hotové vydání se z této práce zatím nepublikuje.

**HOTOVO A PROKAZATELNĚ FUNGUJE:** izolovaný síťový průchod skutečnými
HTTP/WebSocket klienty: průvodce → ověření HA admin identity → trvalá registrace
vlastníka → Supervisor čtení stavu/statistik/logů aplikace → incident rádia
s historickým časem a kontextově svázanou HA akcí → český detail spisu.
Backend HA je v této zkoušce fixture, nikoli živý HAOS. Negativní zkoušky
blokují chybějící či cizí identitu, neaktivní/systémové účty, neadmina, neplatné
CSRF a přístup mimo ingress. Opravený životní cyklus SQLite zavírá spojení
explicitně i bez garbage collectoru; opakované čtení nezvyšuje počet descriptorů.

**IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST:** provozní zapojení Core WS a
Supervisor klientů, průvodce bez ručního ID v YAML, asynchronní kontrola
konkrétních čtení a schémat, čtení logů konkrétní aplikace, Action history
s pozitivní projekcí citlivých dat, vyšetření dřívějšího incidentu a český detail.
Konfigurace pracovního zdroje potřebuje Supervisor roli `manager`; tato role
umí i zápis, proto se neoznačuje za read-only token. HTTP katalog povoluje jen
vyjmenovaná GET čtení. AI ani obecný shell/proxy k němu nejsou připojené.

**NEDOKONČENO / BLOKOVÁNO:** produkční Hermes broker a izolovaný native tool-loop,
AI konfigurace a souhlas s placeným poskytovatelem, bezpečný živý HA writer,
OneDrive restore důkaz, první skutečná oprava a funkční HAOS přejímka, MA FastMCP,
ZHA odběry, specializované agentní workflow, automatický výzkum, souvislý
monitoring, úplné Command Center a upgrade instalace. Tyto položky jsou stále
nedokončené. Nejsou nahrazeny úspěchem fixture ani počtem testů.

Cloud nemá připojený autentizovaný testovací HAOS ani modelového poskytovatele.
Přímé zapnutí stávajícího `native_hermes_investigation` není bezpečná integrace:
vstup vyžaduje izolovaný test worker bez sítě, kdežto HAOS controller drží HA
token a komunikuje s Core/Supervisorem. RC3 broker navíc vynucuje jeden modelový
požadavek a nepřenáší nový native tool katalog. Jeho přepnutí na více kroků bez
nového evidence protokolu a negativních zkoušek není dokončené řešení.

Ověřené kontrakty identity: Core tag `2026.11.0`,
`components/config/auth.py` blob `75b0c88b916dbc8970afbf4041e1e463690029a8`,
`auth/const.py` blob `05b9e6d7ad6f0bdb4db2e0b0ecfb69af42dbbe21`.
Supervisor `/supervisor/info`: `supervisor/api/__init__.py`
blob `a9de70ae25e383b3d6ba22e0d5936dcf0b47eab2`, handler
`supervisor/api/supervisor.py` blob `384f9631da7c20bfe04fd556c9916a65417a1033`.
To dokládá zdrojový kontrakt, nikoli dostupnost v konkrétní domácnosti.

Níže zůstává historický protokol předchozího izolovaného základu a vydání.

Tento strom je funkční **izolovaný vývojový základ**, nikoli hotová autonomní
HAOS platforma. Následně byl přidán samostatný vývojový HAOS instalátor popsaný
níže. Produkční RC3 ani vydané archivy nebyly změněny. Výchozí commit
je `c491893bd433fa0e17dcd852a3eaa610eb3148ad`, nová větev `codex/hads-next`.

## Co bylo skutečně provedeno

1. Bajtová kontrola a rekonstrukce RC3: shoda 133 souborů zdrojového ZIPu,
   vloženého payloadu a CI ZIPu, včetně dokumentů. Samostatný chybějící Rescue
   ZIP nebyl nezávisle ověřen. Viz audit.md a provenance.json.
2. Online četba všech zadaných upstream zdrojů; HA kontrakty ověřeny v tagu
   2026.11.0. Není to autentizovaný integrační test skutečné domácnosti.
3. Samostatné datové, čtecí, vyšetřovací, opravné a ověřovací/reportovací moduly.
   SQLite spis přežije restart, nové načtení logu nepřidává důkaz a AI nemůže
   donekonečna opakovat stejný otisk vstupu.
4. Originální Hermes `d923a5e`, skutečná `AIAgent.run_conversation` native loop,
   dvě čtení a tři modelové požadavky proti místnímu skriptovanému endpointu.
   `hermes-native.json` a `hermes-vertical.json` jsou skutečné kontejnerové účtenky.
5. Propojený scénář používá konkrétní snapshoty z `vertical-snapshots.json`.
   Po návratu Hermes byl připraven přesný plán, provedeno **simulované místní
   schválení testovacího objektu**, změněn jediný odkaz a skutečně vykonána
   izolovaná testovací automatizace nad registry/stavy fixture.
6. Verifier navázal trigger na změnu správného cíle a checkpoint sledování.
   Výsledek a kompletní spis jsou v `vertical-report.json`, `vertical-case.json`
   a `command-center.html`. Testovací hodiny simulují interval; skutečných
   30 sekund provozu domácnosti tím nebylo ověřeno.

Kontejner běžel AMD64/Python 3.14.10 s limitem 512 MiB RAM, bez sítě, HA mountů,
tokenů a write nástrojů, jako UID 65534 bez capabilities. Full vertical peak RSS
byl 182 038 528 B. To je RSS workeru, nikoli součet paměti celé HAOS domácnosti
nebo měření na Raspberry Pi. Závislosti a image ID jsou uložené s účtenkami;
freeze je inventář skutečného image, není to otestovaný multiplatformní lock.
Finální AMD64 image byl znovu sestaven i s těmito dependency constraints a
pozitivní, vertikální i negativní native test byly nad ním zopakovány.

## Povinné scénáře a skutečný rozsah

| Test | Výsledek a hranice |
| --- | --- |
| A rádio | Offline fixtures rozlišují kontextově navázaný stop, stream, odpojení, provider, síť i nedostatek/konflikt důkazů. Živý MA FastMCP adaptér čeká |
| B Zigbee | Offline událost → trace/podmínka/reference/akce → stav s kontextem; absence události nedokazuje absenci fyzického stisku. Živý odběr čeká |
| C DNS | Jeden explicitně doložený outage ID slučuje více projevů i opakovaných probe logů. Podobnost textu sama neprokáže DNS příčinu |
| D plán | Přesná jediná změna testovací `action.target.entity_id`, snapshot, důkazy, hash, riziko, preconditions, funkční podmínka, rollback a ruční alternativa |
| E provedení | Kompletní offline průchod včetně skutečného native Hermes a fixture runneru, uložený report; není to HA automation API write |
| F zákaz zápisu | Bez souhlasu, cizí identita, fake/expired/revoked token, změněný plán/cíl a replay odmítnuty. Nepovolené reads/tools/path odmítnuty; žádné veřejné REST/MCP write cesty neexistují |
| G restart | Intent před zápisem; pád před/po zápisu nezpůsobí replay, ambiguous intent zablokuje další plán stejného cíle. Dva rozdílné plány nemohou přepsat souběžně ověřený původní stav |
| H AI nedostupná | Deterministická diagnostika a ukládání fungují bez modelu. Stejná rozběhnutá analýza se po pádu automaticky neopakuje |
| I falešná oprava | HTTP 200, zmizení logu, cizí kontext/cíl, stará data, monitoring gap a vynechání dřívější recurrence nestačí k uzavření |
| J HAOS | **ČEKÁ**. Přesný budoucí postup v haos-acceptance.md, žádný živý test nebyl proveden |

Aktuální počty, platforma a SHA-256 vstupních souborů offline sady jsou v
`evidence/offline-tests.json`. Testy sady používají syntetická anonymizovaná data.
Kontejnerový model je skriptovaný; test nesmí být citován jako ověření správnosti
autonomního úsudku skutečného LLM nebo úspěšná náprava domácí závady.

## Stav gates a blokery

| Milník | Stav |
| --- | --- |
| M0 | Audit, rešerše, ADR, reuse mapa, bezpečnost a migrační hranice dokončeny |
| M1 | Offline základ dokončen; REST loopback kontrakt testován. WS kontrakty podle zdroje + testovací transport; skutečné WSS čtení HA čeká |
| M2 | Native container proof-of-contract dokončen. HAOS sandbox/broker a opt-in skutečný model čekají; produkční aktivace zakázaná |
| M3 | Izolovaný opravný katalog a místní approval boundary dokončeny. HA uživatelská autentizace a skutečný HA writer čekají |
| M4 | Offline funkční verifier, report, export a statický český přehled dokončeny. Živé funkční sledování čeká |
| M5 | **Nesplněn**, žádný HAOS RC nevydán |

ARM64 nelze v tomto executor ověřit: BuildKit poskytuje jen linux/amd64 (v2/v3/v4),
`binfmt_misc` nemá ARM64 emulátor a další ARM executor není připojen. ARM64 ani
RPi 4/2 GB nejsou označeny jako otestované. Není připojena autentizovaná testovací
HAOS instalace. Chybí tedy live identity, ingression, observability permissions,
OneDrive restore a fyzická přejímka. V těchto oblastech se neaktivuje žádný zápis.

První build narazil na plný 7.9GB VFS filesystem: vrstvy opakovaly celý rootfs.
Odstraněny byly jen vlastní konkrétně určené build artefakty a Dockerfile byl
zmenšen na jediný instalační RUN. Po uvolnění kapacity byly testy zopakovány;
neúspěšné ENOSPC běhy nejsou prezentované jako úspěch produktu.

Dosud neimplementováno: kompletní Music Assistant MCP discovery/transport,
živé ZHA odběry, System Health stream collector, log stream/PSI collector,
automatický externí výzkum s citations, osm specialistických workflow,
dlouhodobý scheduler/watchdog/resource admission, bezpečné nové skills,
RC3 DB importer a živý opravný katalog.
Osm názvů rolí v kontraktu samo o sobě neznamená jejich hotovou implementaci.

## Doplnění: instalační balíček 0.1.0-dev1

V `releases/0.1.0-dev1` je samostatný self-contained shell instalátor, zdrojový
tar.gz a SHA256SUMS. Balíček se reprodukuje `python scripts/build_haos_installer.py`.
Nová aplikace používá vlastní slug `local_hads_next_dev`, privátní SQLite spisy,
omezené Core GET čtení a ruční cílený incident. Ingress vyžaduje Supervisor peer,
explicitně nastaveného vlastníka a CSRF pro lokální změny spisů. Proces po startu
odloží UID na 65532; AI a živý vykonavatel nejsou aktivovány.

AMD64 build, start bez capabilities po odložení UID, nepřímý přístup 403,
persistence po restartu kontejneru a instalační sekvence s **falešným Supervisorem**
prošly; účtenka `evidence/haos-package.json`. Browser test formuláře a obnovení
stránky proti místnímu serveru s umělou ingress identitou také prošel, viz
`evidence/haos-browser.json`. Konkrétní aktuální počet unit/integration testů
je v `evidence/offline-tests.json`. Nejde o živou HAOS instalaci; Core/Supervisor
autorizace, skutečný ingress a ARM64/RPi přejímka zůstávají čekající.

## Další povolený technický krok

Přenést ověřenou native Hermes loop do HAOS chroot/UID/seccomp workeru přes
omezený evidence/model broker; ponechat AI bez HA tokenů, shellu a vykonavatele.
Potom ARM64 a testovací HAOS read-only přejímka, identity adapter a nezávisle
ověřená obnovitelnost záloh. Až po splnění těchto gates zavést jedinou přesnou
živou opravu do katalogu a zopakovat celý funkční acceptance test. Dosavadní
OneDrive guard nesmí být nahrazen existencí souboru nebo upload ACK.
