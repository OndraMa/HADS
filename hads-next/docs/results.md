# Výsledky HADS Next, 2026-11-08

Tento strom je funkční **izolovaný vývojový základ**, nikoli hotová autonomní
HAOS aplikace. Produkční RC3 ani vydané archivy nebyly změněny. Výchozí commit
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
RC3 DB importer, HAOS instalátor/ingress identity a živý opravný katalog.
Osm názvů rolí v kontraktu samo o sobě neznamená jejich hotovou implementaci.

## Další povolený technický krok

Přenést ověřenou native Hermes loop do HAOS chroot/UID/seccomp workeru přes
omezený evidence/model broker; ponechat AI bez HA tokenů, shellu a vykonavatele.
Potom ARM64 a testovací HAOS read-only přejímka, identity adapter a nezávisle
ověřená obnovitelnost záloh. Až po splnění těchto gates zavést jedinou přesnou
živou opravu do katalogu a zopakovat celý funkční acceptance test. Dosavadní
OneDrive guard nesmí být nahrazen existencí souboru nebo upload ACK.
