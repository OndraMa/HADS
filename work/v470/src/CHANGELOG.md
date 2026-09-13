# Aktuální kandidát 4.7.0-rc2

Aktuální změny a otevřené bezpečnostní/provozní brány: [RELEASE_4.7.0-rc2.md](RELEASE_4.7.0-rc2.md). Upload ACK nestačí. Bez pozitivního funkčního testu není oprava potvrzena. Níže zachovaný starší obsah nesmí rozšiřovat tuto smlouvu.

# Changelog

## 4.7.0-rc1

- Import závislostí Automation Inspector schema v2 z `item.entities` včetně missing služeb; zachování restored/configuration_source.
- Strukturovaná AI analýza se neztrácí převodem na čitelný text. Přesné skalární změny automatizací/skriptů mají kompilátor s kontrolou vlastníka, původní hodnoty a preview. Textové návrhy zůstávají nevykonatelné.
- Čtecí nástroj kanonické konfigurace pro AI. Nejvýše osm modelových kroků, poslední dostupný rozpočtový krok rezervován na syntézu; zachování šifrovaného reasoning kontextu.
- UI zobrazuje analýzu, dopad a konkrétní překážky vzniku plánu; při selhání zůstává starší analýza dohledatelná.
- Watchman: archiv/ESPHome a nejednoznačná role podmínky nejsou potvrzenou aktivní závadou. Entity Availability: recovery a non-essential zdroje nejsou aktivní porucha.
- HADocs: potomci rozpoznaného root-case nejsou další incidenty; stabilní ID nezávisí na změně textu.
- Hamster: přesný allowlist čtení místo blacklistu názvů. Provider payload nemůže přímo vložit opravné akce do plánovače.
- Konkrétní vysvětlení nesouladu SQLite indexu, osiřelých statistik, selhání Inspector refresh, ukončeného Ingress streamu a chybějící backup složky.
- Jde o offline testovaného kandidáta, ne o kompletně ověřeného autonomního opraváře. Živá akceptace je povinná.

## 4.6.0

- Diagnostické zdroje rozlišují aktuálně potvrzenou přítomnost od historické stopy v inventáři. Odinstalovaný Codex Terminal Pro se proto nemá znovu ukázat jako nainstalovaný pouze kvůli starému logu.
- Automatické sledování staršího incidentu je odděleno od závěru přijatého kapitánem; rozhodnutí a historie už se nesmějí vzájemně maskovat.
- Test sběru protokolů čeká v UI na nový výsledek namísto okamžitého zobrazení staré tabulky.
- Prázdná, ale aktuální odpověď Spook Repairs je označena jako použitá diagnostická data, ne jako nečinnost.
- Přidán regresní test pro rozlišení automatického sledování a kapitánského přijetí závěru.

## 4.5.0

- Opraven JSON-RPC handshake HA-MCP: inicializační notifikace už neobsahuje zakázané `id`.
- Watchman 0.8.4 se volá s `parse_config`, používá strukturovaný `service_response` a nesměšuje název YAML souboru s entitou.
- Hamster používá vyhledání → schéma/vysvětlení → pouze allowlistované čtení; obecné zápisy zůstávají zablokované.
- Automation Inspector schema v2 zachovává vlastníka, cestu, původní a doporučenou hodnotu; nenahraná automatizace je funkční P2 nález.
- Entity Availability čte i samostatné `entities`/`devices` atributy a slučuje stejný problém napříč skupinami. HAGHS je dohledán přes registr i po přejmenování.
- HADocs používá `/api/summary`; health/status se nepovažují za nálezový report.
- Host logy nepoužívají neexistující `/host/logs/latest`; sběr hlásí `complete/partial/failed` a neúplná kontrola nepotvrdí opravu.
- Funkční incident automatizace má přednost před obecnou síťovou telemetrií. Meross, PulseAudio, kamera a event-stream mají srozumitelný význam a ověřovací plán.
- AI analýza používá striktní diagnostické schéma; model nemůže přímo otevřít write gate. API klíč zůstává volitelný.
- Po každé opravné dávce vznikne záznam u případu i idempotentní HA oznámení s výsledkem, zálohou a stavem ověření.
- Přidána sada regresních testů kontraktů 4.5.0. Živá funkčnost se potvrzuje až po instalaci do HAOS.

## 4.4.0

- Přidáno devět WebMCP Site Tools nad aktuálním `document.modelContext` s kompatibilním fallbackem pro starší experimentální implementace.
- Čtecí nástroje poskytují omezený stav palubní desky, incidenty, redigované důkazy, bezpečný náhled plánu, metadata logových zdrojů a kontrolní snímek UI × backend.
- Rychlá diagnostika, hluboký audit a kontrola konfigurace vyžadují samostatné viditelné potvrzení v panelu HADS a mají vlastní auditní historii.
- WebMCP úmyslně neumí schvalovat, spouštět ani vracet opravy, restartovat HA/doplňky nebo volat shell. Opravný workflow a povinná plná záloha zůstávají pouze v lidském UI HADS.
- Přidán strojově čitelný kontrakt incidentových karet a acceptance snapshot pro pozdější kompletní test v reálném HA Ingressu.
- Přidán dvoufázový akceptační scénář a lokální kontraktní test registrace, potvrzení, HTTP transportu a UI křížové kontroly.
- 79 Python regresních testů a samostatný Node WebMCP kontraktní test prošly lokálně; skutečný browser/HAOS test musí následovat po instalaci.

## 4.3.0

- Nový panel a incidentový chat, ignorování, rozporování a přesná volba nového odkazu.
- Trvalé oddělení závěrů, oprav a následného ověřování; samostatné plány jsou dostupné.
- Povinná plná HA záloha i při starých nastaveních, čerstvé ověření metadat a stavu.
- Bezpečná opt-in údržba SQLite Recorderu s online backup API a kontrolou kopie.
- Pravdivé stavy konektorů: aktualizační entita a health-only endpoint nejsou diagnostika.
- Omezený read-only AI výzkum s perzistentní spotřebou a limity; bez automatického placeného backgroundu.
- Ochrana proti souběhu, přehrání po restartu, zastaralému souhlasu a nebezpečnému rollbacku.
- 68 lokálních regresních testů, syntetický browser workflow a nový zálohovaný instalátor.
- Podporovaný rozsah a dosud neověřené chování na HAOS viz RELEASE_4.3.0.md.

## 4.2.0-rc5

- Kapitánská fronta je rozdělena na Připravené opravy, Diagnostické závěry, Probíhající vyšetřování, Sledované případy a Zamítnuté/uzavřené.
- Akce `Přijmout závěr a dále sledovat` je výslovně diagnostická: nevytváří schválenou opravu ani neaktivuje repair batch.
- Přijatý závěr zůstává dohledatelný ve sledování a UI zobrazí jeho přesné veřejné ID.
- Spodní repair panel ukazuje vykonatelné a schválené plány, stav rescue a write gate; tlačítko používá serverový příznak `runnable`.
- Detail opravy ukazuje cíl, before/after diff, riziko, rollback a následné ověření.
- Diagnostická síť samostatně ukazuje instalaci, běh, spojení, poslední úspěch, poslední použití dat, počet nálezů a poslední chybu.
- Přidána tabulka sběru protokolů a endpoint pro test Core, Supervisor, host a add-on logů.
- Bezpečné Supervisor GET a JSON konektory opakují 502/503/504 s krátkým odstupem; poslední platná odpověď se při krátkém výpadku zachová.
- Health HADS je vysvětlen osmi složkami: Ingress, WebSocket, planner, SQLite, protokoly, konektory, rescue a stáří analýzy.
- Jednorázový nález v restartovém/údržbovém kontextu zůstává přechodný a neeskaluje bez opakování.
- Regresní sada byla rozšířena na 26 testů schvalovacího toku, restartové perzistence, konfliktů, prázdných plánů, selhání rescue, 502 cache a logového přehledu.

## 4.2.0-rc4

- Spouštěcí pruh opravného batch je vždy viditelný. Bez vykonatelného schváleného plánu je bezpečně deaktivovaný a vysvětluje, proč diagnostický závěr nelze „spustit“.
- Automatická privátní detekce JSON API Automation Inspectoru a HADocs přes Supervisor údaje o kontejneru/Ingress portu; explicitní URL zůstává podporovaná a má přednost.
- Import obecných diagnostických struktur `issues/findings/problems/warnings/errors/invalid/missing/unused/stale/orphan/recommendations/root_causes`, včetně původní nápravy a stabilní identity nálezu.
- Hamster MCP podporuje servery, které vracejí `-32601 Method not found` pro `initialize`, ale korektně poskytují `tools/list`.
- Entity Availability rozbaluje `offline_entities`, `stale_entities`, `poor_signal_entities` a `low_battery_entities` na samostatné srozumitelné případy.
- Deterministický plánovač ověřuje živé HA služby i entity, pozná vlastníka podle strukturovaného `automation_id/script_id`, a u jediné vysoce podobné přejmenované služby připraví přesný `automation_update` ke schválení.
- Strukturovaná a jednoznačná změna selektoru `each/any/all` se připraví pouze pokud se původní hodnota v kanonické konfiguraci vyskytuje právě jednou.
- Přidáno lidské vysvětlení pro `Received an exception while passing frame to API` a chyby čtení Git metadat doplňku.
- Regrese ověřují import nálezů, mobilní notify rename, stale entity, Hamster legacy MCP, trvale viditelný batch pruh a pořadí záloha → zápis → Core check.

## 4.2.0-rc3

- Opraveno ukládání českých důvodů u „Vyžádat vysvětlení“ a „Ruční zásah“. UTF-8 text už není kopírován do HTTP hlavičky omezené na ISO-8859-1; zůstává v JSON těle a URL parametru.
- Opraven interní DNS hostname HA-MCP také v případě, kdy Supervisor vrátí pole `hostname` s podtržítky.
- Přidány regrese pro české kapitánské rozhodnutí a normalizaci HA-MCP DNS.

## 4.2.0-rc2

- Home Assistant Digest byl na výslovný požadavek odstraněn ze specifikací, diagnostické sítě i přetrvávajících databázových řádků
- HA-MCP autodetekce kromě `options.secret_path` bezpečně čte tajnou cestu z logu add-onu, protože ji současné verze při automatickém generování nemusí uložit zpět do options
- diagnostická síť vizuálně rozlišuje aktivně použitá data, připravené spojení bez nálezů, nainstalovanou ale nenačtenou integraci a skutečně chybějící nástroj
- Spook bez aktivních Repairs se správně zobrazuje jako připojený zdroj s nulou nálezů, nikoli jako nefunkční adaptér
- dokončená P1/P2 analýza bez bezpečné automatické opravy přechází do kapitánské fronty jako `review_ready`; schválení závěru pouze zapne sledování a nikdy nevytvoří batch zápis
- skutečně nejednoznačná volba entity/služby přechází do `needs_information`, zatímco nedokončené nízko-prioritní vyšetřování zůstává v práci prvního důstojníka
- i vyšetřovaný případ lze z jeho karty explicitně zamítnout, převést na ruční zásah nebo vyžádat vysvětlení

## 4.2.0-rc1

- všechny přístupy k SQLite jsou v procesu serializované, včetně First Officer, dashboard publisheru, watchdogu a Tool Adapter Bus; kapitánské rozhodnutí už nemůže skončit na `database is locked`
- kapitánské rozhodnutí, stav opravného plánu a audit se ukládají jako jedna atomická a idempotentní transakce
- startovní reconciler opraví nekonzistentní schválení z rc7, vyřadí prázdné a diagnostické pseudo-plány a nikdy je tiše nespustí
- `Ruční zásah` zruší čekající automatický plán a přesune případ do sledování; není započítán jako kapitánský úkol
- hlavní batch lišta je skrytá, pokud neexistuje skutečně vykonatelný schválený plán; samotný starý stav `approved` tlačítko nerozsvítí
- prázdná kapitánská fronta už nepřebírá všechny P1/P2 případy, které First Officer teprve vyšetřuje
- root-case klíč integrace obsahuje i sémantickou příčinu, takže dvě nesouvisející chyby stejné integrace nejsou omylem sloučeny
- Rescue Gate podporuje prakticky ověřitelný režim: unikátní název, lokální SHA-256 a synchronní potvrzení upload služby; instalace s metadata/list endpointem může dál používat přísné vzdálené ověření
- dashboard entity publisher opakuje přechodné HTTP 502/503 a síťové chyby bez zablokování hlavního diagnostického cyklu
- přidána regresní sada pro souběh DB, rozhodnutí, migraci fronty, deduplikaci, rozdělení příčin, dashboard a Rescue Gate

## 4.1.0-rc7

- opraven skutečný Ingress bug kapitánských tlačítek: request body podporuje HTTP chunked a rozhodnutí se posílá redundantně v JSON + query + hlavičce
- `Schvaluji`, `Zamítám`, `Potřebuji vysvětlení` a `Ruční zásah` už nejsou závislé na Content-Length
- First Officer už nevyrábí kapitánský úkol z každého případu bez patche; default je `investigating`, staré případy `watching`
- Kapitánská fronta obsahuje jen skutečná rozhodnutí; background investigation má vlastní kompaktní panel
- canonical fingerprint v2 ignoruje wrapper/source category pro známé stejné root-cause; Core exit 137 se slučuje napříč title/message/sample/report/live
- explicitní RCA pro Meross MQTT, Music Assistant HA WebSocket 502 a `media_stop -> NotImplementedError`
- HADS2/HADS3/HADS4 vlastní runtime logy jsou `hads_internal` a nesnižují HA Current Health
- odstraněna globální restart grace, která mohla zobrazit Current Health 100 i při čerstvých funkčních chybách
- Potential Health gain je jen skutečný aktuální penalty připravené opravy, ne počet symptomů
- Tool Adapter Bus je singleton; dashboard GET už nevytváří nový bus a nespouští zapisující refresh
- adapter persistence používá krátkou transakci s retry; při SQLite locku zůstane runtime snapshot použitelný místo HTTP 500
- Hamster MCP se auto-discoveruje přes Core API proxy; HA-MCP se auto-discoveruje z Supervisor add-on info, pokud má secret_path
- HAGHS se dál čte pouze z reálného `sensor.system_ha_global_health_score`; absence runtime entity není vydávána za použitá data
- upgradem se automaticky odstraní starý automaticky vygenerovaný stav `needs_information`; zachová se pouze tehdy, pokud jej kapitán skutečně zvolil
- Spook do aktivních nálezů nezapočítává Repairs s `ignored=true`; počet ignorovaných zůstává viditelný zvlášť
- OneDrive export z `/share/hads4` se před uploadem bezpečně stageuje do již povolené větve `/share/hads`, takže nepadá na `allowlist_external_dirs` a staging se vždy uklidí
- stejné auto-discovered URL HA-MCP/Hamster se používá jak pro test spojení, tak pro skutečné case evidence; karta už nemůže hlásit konektor připravený a vyšetřování volat jiný endpoint

## 4.1.0-rc6

- opraveno kapitánské rozhodování napříč staršími UI/stavy: backend přijímá `approve/approved`, `need_info/needs_information`, `manual/manual_monitoring` a další bezpečné aliasy; platný klik už nekončí hláškou „Neplatné kapitánské rozhodnutí“;
- diagnostický `core_check` už nikdy není vydáván za opravný plán a nemůže zobrazit tlačítko Schvaluji; staré pseudo-plány se při startu vyřadí z fronty;
- `CONTAINER_LOG_EPOCH` je převeden do `diagnostic_coverage` s nulovou penalizací Current Health;
- Tailscale `src_valid_mark` na `/proc/sys/... read-only file system` je veden jako očekávané omezení kontejneru, ne jako storage P2;
- Core watchdog `exit code 137` z různých reportových reprezentací (`title`, `normalized_message`, `sample`, `message`) používá jeden kanonický fingerprint;
- formátované HADS2/HADS3 latest reporty se už nereingestují jako nové incidenty; jsou pouze provenance, zatímco HADS3 raw logy lze převzít;
- při upgradu se automaticky uzavřou staré YAML nálezy z `esphome/archive/addons/blueprints`, které nejsou živou HA konfigurací;
- Current Health používá funkční dopad a temporal state místo prostého odečtu za počet root-cases; diagnostické/odmítnuté/odložené/ručně sledované položky jej nesnižují.

## 4.1.0-rc5

- dokončen souhrnný First Officer redesign a přidána závazná akceptační matice všech požadavků a ověřených externích projektů;
- přidány skutečné konektory pro Streamable HTTP MCP (HA-MCP a Hamster), čtecí JSON zdroje HADocs/Automation Inspector, HAGHS atributy a Entity Availability;
- instalace, ověřené spojení a skutečné použití dat jsou tři oddělené stavy; chybné spojení ukazuje konkrétní redigovanou chybu;
- Spook a Watchman nálezy se křížově kontrolují proti živým states, entity registry a službám;
- Automatic Repair Planner umí načíst kanonickou automatizaci nebo skript a vytvořit přesný hashovaný before/after diff; nejednoznačný skalární cíl nikdy nehádá;
- Repair Engine podporuje transakční `automation_update` a `script_update` včetně rescue originálu, Core checku a rollbacku;
- detail root-casu před schválením zobrazuje konkrétní cíl, riziko, diff a očekávanou verifikaci;
- HAGHS se zobrazuje jako samostatná hygiena konfigurace a nepřepisuje provozní Current Health;
- mise 20 oblastí už nepředstírá plné pokrytí: vykazuje ověřené, částečné a neověřené oblasti;
- MCP katalog odmítá zapisovací, konfigurační a tajné nástroje; uložené výsledky a chyby konektorů se redigují.

## 4.1.0-rc4

- opraven falešný stav `AKTIVNÍ · data se používají`; instalace, ověřené spojení a skutečně spotřebovaná data jsou nyní tři různé stavy;
- Spook a ostatní Home Assistant Repairs se při Deep Analysis importují jako běžné HADS Cases a vstupují do root-case/First Officer workflow;
- Watchman reporty se převádějí na případy s konkrétní entitou/službou a řádkem zdrojového reportu;
- externí případ se uzavře jen po úspěšném novém čtení zdroje, který už daný nález nevrací;
- YAML audit nekontroluje zdrojové soubory add-onů jako uživatelskou konfiguraci a respektuje entity přítomné v entity registry, i když jsou vypnuté;
- schopnosti v UI už nejsou předem deklarované jako použité; zobrazují se pouze skutečně ověřená runtime rozhraní.

## 4.1.0-rc3

- Deep Analysis končí seskupenou **Repair Queue** místo izolovaných surových nálezů.
- **Automatic Repair Planner** spojuje případ, kořenovou příčinu, lokální výzkum, konkrétní allowlist akce, náhled a čekající opravný plán; při nedostatku důkazů nic nevymýšlí.
- Kapitánské rozhodnutí podporuje schválit, odmítnout, ručně řešit a vyžádat další informace. Schválení pouze zařadí plán do fronty.
- Jediné tlačítko **SPUSTIT SCHVÁLENÉ OPRAVY** zpracuje všechny schválené plány jako řízenou dávku.
- **Batch Planner** detekuje rozporné volby add-onů, rebazuje navazující YAML hashe, sestaví závislosti a pořadí restartů a při konfliktu skončí před jakýmkoli zápisem.
- **Rescue Package** obsahuje původní YAML, volby add-onů, diffy, schválení, health a dependency snapshot, manifest a pokyny k obnově.
- Upload Rescue Package nestačí: před odemčením zápisu musí OneDrive nebo nakonfigurovaná read/verify služba nezávisle potvrdit přesný vzdálený název souboru.
- Logická brána **Repair write gate** je běžně `LOCKED`, otevírá se až po bezpečnostních preflightech a vždy se znovu zamkne.
- Dávka používá transakční Repair Engine, při chybě pozastaví zbytek a zachová rollback audit.
- Post-batch Deep Analysis ukládá health před/po a rozlišuje nové, vyřešené, přetrvávající a regresní příčiny.
- Odmítnutí se ukládá jako zpětná vazba pro další analýzu, včetně očekávaného chování, odkladu, reinvestigace a ručního sledování.
- Ruční opravný formulář je pouze v **Advanced · Manual Repair**.
- **Tool Adapter Layer** za běhu objevuje HA-MCP, HAGHS, HADocs, Hamster MCP, Spook a Watchman; používá jen skutečně dostupná runtime data a jinak výslovně zaznamená nativní HADS fallback.
- Přidány integrační testy plánovače, rozhodnutí, konfliktů, vzdálené verifikace, logické brány a adaptérů.

## 4.1.0-rc2

- Prázdná úspěšná odpověď Supervisoru z `/core/check` se již nechybně nehlásí jako neplatná konfigurace.
- Dashboard karta používá top-level `grid`, takže ji lze vložit i do moderního dashboardu typu Sekce.
- Případ bez doloženého přesného patch plánu nabídne bezpečnou kontrolu konfigurace místo prázdné YAML akce; formulář kontroluje povinná pole před odesláním.
- Čistý `core_check` nevytváří zbytečnou zálohu, netvrdí, že problém opravil, a nenabízí nesmyslný rollback.
- Pokud není OpenAI nakonfigurované, tlačítko provede a uloží místní analýzu důkazů bez webu místo slepé chyby.
- Export případů a report pro ChatGPT se po vytvoření skutečně stáhnou do prohlížeče.
- Výchozí HADS4 export na OneDrive míří pod ověřenou složku `HADS/HADS4`; stávající volba `HADS4` se za běhu bezpečně přesměruje stejně.
- Audit a OneDrive zapisují stručné jednorázové souhrny místo celých výsledkových objektů a opakovaných víceřádkových HTTP chyb.
- Instalační skript podporuje izolovaný test cíle a při neúspěšném přesunu nové verze obnoví původní zdroj.

## 4.1.0-rc1

- Přidán trvalý read-only WebSocket Observer s reconnectem, polling fallbackem a stavy ACTIVE → VERIFYING → RESOLVED.
- Přidán graf závislostí z HA registrů, stavů, YAML, Lovelace a inventáře; opravné plány obsahují blast radius.
- Přidán Health Engine s oddělenými Current Health, Reliability, Diagnostic Confidence, HADS Health a jedenácti subsystémy.
- Přidána lokální znalostní báze oprav a Change Intelligence.
- OpenAI analytika převedena na omezený function-calling loop s read-only HADS nástroji, volitelným webem a limitem kroků.
- Přidána plná diagnostická mise ve 20 oblastech a její API/UI spuštění.
- HA dashboard rozšířen o Diagnostic Confidence a subsystémová skóre; publikuje jedenáct entit.
- Prázdná chatová zpráva je nyní odmítnuta HTTP 400 a už se nenahrazuje obecným dotazem „Co mám udělat dál?“.

## 4.0.0-rc2

- Automatická publikace deseti stavových entit do Home Assistant REST API: Current Health, Reliability, Coverage, otevřené alerty, akce kapitána, čekající schválení, sledování, vyřešeno dnes, vlastní zdraví HADS a binární stav vyžadované akce.
- TOP 5 úkolů kapitána se publikuje jako atribut pro dashboard kartu.
- Přidána nativní Lovelace karta bez závislosti na HACS a automatický export do `/share/hads4/HADS4_dashboard_card.yaml`.
- Přidáno interní API `/api/dashboard`, stažení YAML karty a ruční vynucení publikace.
- Opravena chybějící agregace stavů oprav v přehledu systému.

## 4.0.0-rc1

- Nový samostatný addon `hads4`; HADS 2/3 se neodstraňuje ani nepřepisuje.
- Režim kapitán / první důstojník s doslovným schvalováním změn.
- Opravné plány, diff, riziko, auditní stopa, předzásahová partial backup a soukromé lokální snapshoty.
- Allowlist akcí: přesná YAML náhrada, addon options, addon restart, Core check a zvlášť povolitelný Core restart.
- Ochrana proti změně souboru mezi náhledem a provedením pomocí SHA-256.
- Automatický rollback při chybě akce nebo neplatné konfiguraci.
- Sledování stejného diagnostického otisku po opravě; úspěch, návrat chyby a ruční rollback.
- Volitelná OpenAI Responses API analytická vrstva s aktuálním webovým hledáním a doménovým filtrem; AI nemá vykonávací oprávnění.
- Převzetí posledního HADS 2 reportu a až sedmi dnů exportů/raw logů HADS 3.
- HADS4 JSON/MD exporty, kapitánská sekce v denním ChatGPT reportu a oddělené soukromé rollback manifesty.
- Ochranná hlavička pro všechny mutující webové požadavky a přísnější bezpečnostní hlavičky Ingress UI.
- Zachovány a rozšířeny opravy HADS 3.3.1: chytré priority, SIGKILL/OOM důkaz, disk evidence, deduplikace, omezení case-links, parser WARNING/journald, OneDrive retry a coverage zdrojů.
