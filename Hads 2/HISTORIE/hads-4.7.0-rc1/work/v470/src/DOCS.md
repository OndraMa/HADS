# HADS 4 – použití

> Historická dokumentace RC5. Pro 4.5.0 použijte [aktuální průvodce](RELEASE_4.5.0.md).
> Staré popisy UI, vypnutí záloh, partial backup a automatické mazání referencí neplatí.

## Cíl

HADS 4 má být jedno centrální diagnostické a opravné centrum Home Assistantu. Ondřej je **kapitán** a HADS je **první důstojník**: sbírá důkazy, třídí skutečný dopad, vysvětluje skóre, připravuje řešení a hlídá následek změny. Opravu smí provést jen po výslovném schválení kapitánem.

HADS 4 běží pod samostatným slugem `hads4`, takže neodstraní ani nepřepíše HADS 2/3. Při prvním startu převezme dostupný poslední report HADS 2 a až sedm dnů exportů a raw logů HADS 3 ze `/share`. Starší HADS ponechte, dokud neověříte alespoň jeden hluboký audit, denní report a jeho doručení na OneDrive.

## Co se automatizuje

- rychlá kontrola každých 15 minut;
- hluboký audit každý den v 08:10 a doplnění zmeškaného běhu po startu;
- Core, Supervisor, Host, DNS, audio, multicast a logy nainstalovaných addonů;
- inventář verzí, aktualizací a stavů;
- metriky RAM, CPU, disku a Recorder databáze;
- YAML audit, kontrola statických odkazů na entity a oficiální `/core/check`;
- fingerprint, deduplikace, slučování známých variant stejné příčiny a životní cyklus NEW/ACTIVE/MONITORING/RESOLVED/REOPENED;
- korelace s aktualizací, restartem, bootem, zálohou a údržbou;
- Smart Health 0–100 a priority P1–P4 podle dopadu, aktuálnosti, aktivních dnů, délky trvání a zotavení;
- denní TXT/MD report pro ChatGPT a strukturovaný JSON/MD export;
- OneDrive retry, jednotlivý fallback a odložené opakování bez nového auditu;
- sledování výsledku schválené opravy a připravený rollback.
- publikování živého score, spolehlivosti, pokrytí, alertů a kapitánských akcí do Home Assistant dashboardu.
- živý Observer přes Home Assistant WebSocket API s bezpečným polling fallbackem;
- graf závislostí a blast radius před každým opravným plánem;
- lokální znalostní báze výsledků oprav a Change Intelligence;
- plná ručně spustitelná diagnostická mise ve 20 oblastech, která odděluje autoritativně ověřené, částečně pokryté a neověřené oblasti;
- automatické vytvoření Repair Queue a konkrétních čekajících plánů po Deep Analysis;
- runtime diagnostická síť pro HA-MCP, HAGHS, HADocs, Hamster MCP, Spook, Watchman, Automation Inspector a Entity Availability s explicitním nativním fallbackem;
- společný Batch Planner, Rescue Package, logický Repair write gate a post-batch srovnání.

## Command Center a 20 oblastí

Tlačítko **Plná mise 20 oblastí** spustí hluboký audit Core, Supervisoru, HAOS/hosta, CPU a paměti, úložiště, Recorderu, integrací, Repairs, nedostupných entit, automatizací, traces, add-onů, logů, YAML, custom components, sítě, Zigbee/Matter/Bluetooth, grafu závislostí, záloh/aktualizací a historie/AI vrstvy. Výsledek se uloží do `mission_runs` a zobrazí v API `/api/missions/latest`. Oblast bez autoritativního zdroje dostane `unknown`; dílčí kontrola `limited`. Pouhý úspěch Deep Analysis už nikdy neoznačí všech dvacet oblastí jako zkontrolované.

Observer ukládá všechny entity do kompaktního živého modelu, ale do historie událostí zapisuje jen významné přechody. Výpadek WebSocketu není vydáván za poruchu smart home: polling pokračuje a sníží se Diagnostic Confidence.

Health Engine publikuje čtyři nezávislé hodnoty:

- **Current Health** – aktuální stav v konfigurovatelném okně, výchozí 24 hodin;
- **Reliability** – dlouhodobé opakování a regrese;
- **Diagnostic Confidence** – úplnost kolektorů, Observeru a grafu;
- **HADS Health** – vlastní provozní zdraví diagnostického add-onu.

Pokud je k dispozici HAGHS, Command Center přidá pátou hodnotu **Hygiena konfigurace**. Ta nepřepisuje Current Health, protože neplatná reference není totéž jako aktuální výpadek domácnosti.

## Priority a známé omyly

Samotný počet logových řádků neurčuje závažnost.

- **P1:** potvrzený kritický stav nebo dlouhodobě opakovaný problém s významným funkčním dopadem.
- **P2:** významný aktuální nebo perzistentní problém vyžadující zásah.
- **P3:** reálný, ale omezený či krátkodobý problém ke sledování.
- **P4:** informativní/přechodný jev nebo interní chyba HADS.

Kód 137/SIGKILL sám nedokazuje OOM. HADS nejdřív hledá přímý OOM důkaz a časovou vazbu na stop, rebuild, update nebo shutdown. Jednorázový zotavený OOM není automaticky P1. Falešné hlášení o plném disku se porovnává s čerstvou autoritativní metrikou HAOS; údaj 0 GB z addonu nesmí sám vyvolat mazání dat.

Cílená pravidla zahrnují Meross Matter/LAN MQTT, Music Assistant DNS/spojení/rádio 404, automatizace a skripty, WebSocket invalid auth, Bluetooth connection slots, Recorder/SQLite lock, Host healthcheck, HA Alerts 403, Tailscale TPM, interní chyby sběrače a další systémové události.

## First Officer a Repair Queue

Deep Analysis nekončí pouze seznamem chyb. Sloučí související případy do root cases, načte skutečně dostupné důkazy z diagnostické sítě a Automatic Repair Planner připraví přesnou allowlist akci. Každá karta obsahuje kořenovou příčinu, důkazy, výzkum, konkrétní diff, riziko a stav plánu. Bez přesného důkazu planner nevymýšlí YAML ani náhradní entitu; uloží kandidáty a požádá o další informace.

Kapitán má čtyři volby:

- **Schválit** – pouze zařadí plán do dávky, nic neprovede;
- **Odmítnout** – uloží důvod a paměť očekávaného chování, odkladu, reinvestigace nebo ručního sledování;
- **Ruční řešení** – předá případ do pokročilého ručního toku;
- **Další informace** – vrátí případ plánovači bez vykonatelné změny.

Schválené plány provede výhradně tlačítko **SPUSTIT SCHVÁLENÉ OPRAVY**. Batch Planner nejdřív vyřeší pořadí a závislosti a zablokuje rozpory. Potom vytvoří Rescue Package. Teprve nezávisle potvrzený přesný vzdálený archiv na OneDrive dovolí dočasně odemknout Repair write gate. Při chybě se zbytek dávky pozastaví. Následující Deep Analysis uloží health před/po a rozdělení na nové, vyřešené, přetrvávající a regresní root cases.

Ruční vytvoření plánu je dostupné jen v rozbalovací sekci **Advanced · Manual Repair**. I takový plán musí projít kapitánským rozhodnutím a společnou dávkou.

## Opravné centrum

Podporované vykonatelné akce jsou záměrně omezené:

1. **Přesná změna YAML** – relativní cesta v `/config`, původní blok a nový blok. Původní blok musí existovat právě jednou a SHA-256 souboru musí stále souhlasit s náhledem.
2. **Změna voleb addonu** – bezpečné sloučení přes Supervisor API, validace schématu a volitelný restart addonu.
3. **Aktualizace automatizace nebo skriptu** – kanonický objekt načtený z Home Assistant API, celý before/after diff a SHA-256 guard proti souběžné editaci.
4. **Restart addonu** – konkrétní ověřený slug.
5. **Kontrola konfigurace Core** – nedestruktivní oficiální kontrola.
6. **Restart Core** – pouze když je zvlášť povolen v nastavení; nikdy nevzniká automaticky.

HADS 4 nepovoluje shell, Python eval/exec, libovolnou URL, libovolný HA service call, změnu `secrets.yaml`, cestu mimo `/config`, symbolické odkazy ani přepsání celého neznámého souboru.

### Tok dávkové opravy

1. Automatic Repair Planner připraví plán, diff, výzkum a ověření.
2. Kapitán plán schválí; tím jej pouze zařadí do fronty.
3. Kapitán spustí společnou dávku.
4. Batch Planner zkontroluje konflikty, závislosti, SHA rebasing a pořadí restartů.
5. HADS vytvoří Rescue Package a nezávisle ověří jeho přesný vzdálený soubor na OneDrive.
6. HADS odemkne logický Repair write gate a pro každý plán vytvoří požadovanou partial backup a soukromý snapshot.
7. Provede pouze schválené allowlist akce; chyba zastaví zbytek dávky a aktivuje existující rollback hranice.
8. Po YAML změně spustí `/core/check`; při chybě okamžitě obnoví snapshot.
9. Repair write gate se vždy znovu zamkne.
10. Post-batch Deep Analysis porovná health a root cases před/po; dlouhodobé monitorování a rollback zůstávají dostupné.

Plná denní záloha zůstává poslední záchrannou vrstvou. Lokální rollback HADS je rychlejší vrstva pro konkrétní změnu, nikoli náhrada plné zálohy.

## OpenAI a web

Druhá analytická vrstva je volitelná. Po zapnutí `openai_enabled`, nastavení API klíče a modelu odešle HADS pouze redigovaný kontext konkrétního případu do OpenAI Responses API. AI Officer může v omezené smyčce volat read-only funkce pro případ, živý stav, dependency graph, změny, lokální paměť, health, Repairs a automation traces. Webové hledání používá `web_search` a ve výchozím nastavení omezuje zdroje na Home Assistant dokumentaci, Home Assistant web, GitHub a komunitní fórum. Výsledek, počet interních kroků a zdroje se uloží do chatu případu. Když OpenAI zapnuté není, stejné tlačítko provede místní analýzu uložených důkazů a jasně uvede, že web nebyl použit.

AI výsledek je vždy jen doporučení. Nemůže přímo změnit konfiguraci ani obejít kapitánské schválení. API klíč se nezapisuje do logu ani exportu. V UI addonu je typ `password`, přesto jde o tajnou hodnotu uloženou v možnostech Supervisoru; sdílené exporty ji vždy maskují.

## Výstupy

- `/share/hads/HADS_latest.txt` a `.md` – hlavní denní podklad pro ChatGPT/OneDrive;
- `/share/hads/reports/YYYY/MM/` – kompatibilní archiv;
- `/share/hads4/HADS4_latest.json` a `.md` – strukturovaný export;
- `/share/hads4/exports/YYYY/MM/` – archiv exportů;
- `/share/hads4/raw/` – redigované raw logy dle retence;
- `/data/hads4.db` – interní historie;
- `/data/repair_private/` – soukromé snapshoty a rollback manifesty, nikdy se neexportují.
- `/share/hads4/HADS4_dashboard_card.yaml` – hotová nativní Lovelace karta.

## Home Assistant dashboard

HADS každou minutu a také po dokončení kontroly publikuje přes interní Home Assistant REST API tyto entity:

- `sensor.hads4_system_score` – Current Health 0–100, stav a TOP 5 akcí;
- `sensor.hads4_reliability` – dlouhodobá spolehlivost, kterou nesrazí jednorázová zotavená chyba;
- `sensor.hads4_diagnostic_coverage` – podíl právě dostupných diagnostických zdrojů;
- `sensor.hads4_diagnostic_confidence` – jistota důkazů z kolektorů, Observeru a grafu;
- `sensor.hads4_open_alerts` – všechny otevřené skutečné případy;
- `sensor.hads4_captain_actions` – P1/P2 a opravné plány vyžadující rozhodnutí;
- `sensor.hads4_pending_approvals` – opravné plány čekající na přesnou kapitánskou frázi;
- `sensor.hads4_watching`, `sensor.hads4_resolved_today`, `sensor.hads4_internal_health`;
- `binary_sensor.hads4_action_required`.

Vložení karty: otevřete dashboard, zvolte Upravit → Přidat kartu → Ručně a vložte obsah souboru `/share/hads4/HADS4_dashboard_card.yaml`. Top-level karta je `grid`, takže funguje v dashboardu typu Sekce i v klasickém Masonry. Používá pouze vestavěné Markdown, Gauge, Tile a Entities karty. HADS úmyslně nepřepisuje interní Lovelace úložiště, takže nemůže poškodit ostatní dashboardy. Publikaci lze vypnout volbou `ha_dashboard_enabled` nebo změnit interval `ha_dashboard_publish_seconds`.

## Doporučený první start

1. Nainstalujte HADS 4 vedle HADS 3.
2. Nechte výchozí `backup_before_repairs=true`, `allow_repair_without_backup=false` a `allow_core_restart=false`.
3. Spusťte Hluboký audit.
4. Ve Stav systému zkontrolujte pokrytí zdrojů, YAML, disk, RAM a inventář.
5. Vytvořte Report pro ChatGPT a ověřte `HADS_latest.txt/.md`.
6. Spusťte OneDrive vše a ověřte hlavní i HADS4 export.
7. Spusťte **Plná mise 20 oblastí** a ověřte Observer, graf a Diagnostic Confidence.
8. První opravný plán otestujte na neškodné přesné YAML změně, poté ověřte blast radius, auditní stopu a rollback.
9. Starší HADS zastavte až po několika bezchybných rychlých kontrolách a jednom denním běhu. Odinstalace není automatická.

## Zdroje API

Implementace používá oficiální Supervisor endpointy pro logy, addon options/validation, Core check/restart a partial backup. Struktura addonu používá samostatný slug, Ingress, manager roli a RW mapování Home Assistant konfigurace. Aktuální dokumentace: https://developers.home-assistant.io/docs/api/supervisor/endpoints/ a https://developers.home-assistant.io/docs/apps/configuration/.
