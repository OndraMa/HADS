# Test J: přejímka na odděleném HAOS

Stav k **2026-11-09 UTC: ČEKÁ – ŽIVÝ HAOS NEPROVEDEN**. Uživatel nemá
testovací HAOS. Kontejnerové a offline výsledky níže tuto přejímku nenahrazují.

Kandidát 0.2.0-dev1 obsahuje původní izolovaný Hermes, ověření HA správce,
trvalé vyšetřování a opt-in modelu. Produkční zapisovací adaptér není
zpřístupněný. Návod je v [haos/DOCS.md](../haos/DOCS.md); přejímka čtecího
kandidátu může pokračovat nezávisle na blokované zapisovací části.

## Rozsah, role a evidence

Test provádí jmenovaný operátor v samostatné testovací domácnosti. Vlastník
testovacího HAOS je jediný schvalovatel změn. Sběrač, Hermes worker a vykonavatel
mají oddělené identity. Operátor může být zároveň vlastník; z protokolu musí být
zřejmé, v jaké roli schválil konkrétní plán. AI nesmí vystupovat jako uživatel.

Před začátkem založit neveřejný protokol s následujícími údaji:

- ID běhu, datum/čas UTC, operátor, schvalovatel a explicitní označení testovací
  instance. Nezapisovat hesla, tokeny, jejich autorizační hlavičky ani approval
  bearer credentials.
- Git commit Next, SHA-256 distribučního artefaktu a image digest, architektura,
  verze HA Core, OS, Supervisoru, MA serveru/pluginu, ZHA a firmwaru ovladače.
  Zvlášť pin Hermes a identita bezplatného testovacího modelového endpointu.
- Důkazy s původem, skutečným časem události a časem čtení, verzí adaptéru,
  oknem sběru, výsledkem čtení a chybějícími zdroji. Export je redigovaný;
  případné citlivé raw důkazy se do repozitáře ani modelu nekopírují.
- U každého výsledku rozsah `offline`, `container` nebo `live-test-haos`.
  Slovo `live` zde znamená jen tuto testovací instalaci, nikdy produkci.

Lokální CLI `approve` používající OS UID ani ručně vytvořený `observations.json`
nedokazují autentickou HAOS identitu nebo fyzický výsledek. Nynější verifier své
reporty označuje `offline_isolated_fixture`; nesmí se přejmenovat na live jen
změnou pole v exportu. Živá integrace vyžaduje vlastní důvěryhodný sběrač a vazbu
jeho důkazů na plán/provedení.

## J0 – podmínky, bez kterých se nesmí přejít k živému zápisu

Všechny následující body jsou tvrdé brány. Jejich nesplnění znamená zastavit
zapisovací část, zaznamenat blocker a pokračovat pouze nezávislým čtením.

1. Existuje zkontrolovaný kandidát HAOS aplikace s manifestem, přesnými verzemi,
   minimálními oprávněními, dokumentovaným instalačním i odinstalačním postupem
   a hashem/image digestem. Balení nesmí přepsat RC3, jeho adresář ani DB.
   Čtecí kandidát s původním workerem existuje; jeho HAOS izolace a skutečné
   zdroje čekají na tuto přejímku. Produkční vykonavatel není zpřístupněný.
2. M0–M4 mají vlastní reprodukovatelné protokoly; bezpečnostní negativní testy
   musí platit pro přesně tentýž commit/image, ne starý tag nebo image před opravou.
3. Ověřená identita schvalovatele přichází z autentizovaného důvěryhodného
   rozhraní. Otestovat přímé spojení mimo Ingress, podvržené hlavičky, jiného
   uživatele a chybějící relaci: žádná cesta nesmí vydat schválení. Konstantní
   jméno, řetězec principal z požadavku a samotná hlavička nejsou autentizace.
4. Čtecí broker drží HA/Supervisor/MA credentials. Hermes nemá síťovou cestu na
   HA, shell, obecný HTTP/MCP proxy, `/config`, approval DB ani credentials.
   Vykonavatel přijme pouze katalogovou operaci a neměnný schválený plán.
   Ověřit skutečná UID/mounty/síťovou politiku a zákaz alternativních zápisů,
   ne pouze seznam nástrojů v promptu.
5. Souhlas je jednorázový, expirovatelný a vázaný na hash plánu, identitu a hash
   aktuálního cíle. Změna cíle/plánu/parametrů vyžaduje nový souhlas. Otestovat
   reject/manual, replay a dva souběžné vykonavatele. AI nesmí souhlas získat sama.
6. Pro konkrétní operaci je ověřený podporovaný write API kontrakt cílové verze
   HA, přesný rozsah změny a bezpečný rollback. Nynější JSON fixture operace
   není takový adaptér a nesmí být namířena do živé konfigurace.
7. Existuje nezávisle ověřená záloha odpovídající rozsahu zásahu a bezpečný
   návratový postup. Zachovat OneDrive ochranu RC3 všude, kde ji RC3 vyžaduje.
   Zaznamenat readback SHA-256, velikost, zdroj a datum; navíc doložit obnovu
   do jednorázové testovací instance a funkční kontrolu obnoveného obsahu.
   Existence souboru, upload ACK, metadata `/backups` nebo shodný hash samotné
   nejsou důkaz obnovitelnosti. Neověřená obnova znamená blokaci rizikové změny.
8. Vlastník předem schválil funkční test a sledovací podmínku. Oprava světla
   neopravňuje ovládat zámek, topení, hlasitost ani přehrávání. Žádné produkční
   zařízení nebo cloudový účet domácnosti není součástí laboratorní topologie.

## J1 – příprava testovací instalace a instalace budoucího kandidáta

1. Použít samostatný RPi 4 / 2 GB s ARM64 HAOS a oddělený AMD64 HAOS, případně
   AMD64 VM. Instalaci HAOS provést podle [oficiálních návodů](https://www.home-assistant.io/installation/).
   Vybrat oficiální obraz pro správný hardware a uložit jeho verzi a kontrolní
   součet. Neobnovovat produkční credentials do zařízení připojeného k produkční síti.
2. Oddělit síť od produkční domácnosti. Použít samostatný Zigbee koordinátor,
   testovací ovladač a neškodnou testovací lampu; nepřepárovat produkční zařízení.
   MA a přehrávač patří do stejné laboratoře, s explicitně povoleným streamem.
   Zařízení se nesmí přes izolovanou instanci připojit k produkčním službám.
3. Nastavit správný čas/NTP a zaznamenat časové pásmo. Exporty normalizovat na
   UTC. Změřit klidový baseline HA bez HADS a rezervu CPU/RAM/úložiště.
4. Připravit neprivilegovaného uživatele pro běžná čtení a oddělenou identitu pro
   admin-only důkazy, jsou-li nutné. Credentials zadat pouze do budoucího
   chráněného nastavení/secret store. Nikdy je nevkládat do příkazu, dokumentace,
   repozitáře nebo vývojového promptu.
5. Až existuje kandidát splňující J0, instalovat pouze přes jeho zkontrolovaný
   HAOS instalační postup. Zapsat přesný manifest, přidělená oprávnění a image
   digest. Pokud postup chybí, označit `BLOCKED: chybí HAOS balíček`; nespouštět
   RC3 instalátor nebo libovolný Docker image jako náhradní instalaci Next.
6. První start je pouze read-only. Ověřit, že AI a placené hledání jsou vypnuté,
   základní sběr funguje a restart nezpůsobí spuštění čekajícího zásahu. Před
   další fází uložit redigovanou konfiguraci, baseline a funkční test návratu.

## J2 – skutečná čtení a autentizace zdrojů

Kontrakty a pinované zdroje jsou v [research.md](research.md). Dnes implementované
čtení ověřit jednotlivě přes `CoreReader`, `CoreWSReader`, `SupervisorReader` a
jejich dokumentované transporty. Není dodáván univerzální live runner ani CLI
pro autentizovanou HAOS přejímku. Případný laboratorní runner se musí před použitím
zrevidovat; nesmí přidat obecný síťový passthrough nebo zapisovací metody.

| Zdroj a praktický test | Očekávaný výsledek / hranice |
|---|---|
| Core REST `GET /api/config`, konkrétní `/api/states/<entity_id>` a časově omezená `/api/history/period/<timestamp>` | Verze, skutečný stav a historie správné testovací entity. Odlišit nedostupný Recorder od prázdné historie |
| Core WS `/api/websocket` autentizace | Ověřit `auth_required` → `auth` → `auth_ok`; `auth_invalid` a zakázané čtení ponechají incident otevřený |
| WS `config/entity_registry/list`, `config/device_registry/list` | Spárovat správný target a device; friendly_name není stabilní identifikátor |
| WS `trace/list`, `trace/get` | Správné domain/item_id/run_id; admin-only. Zachytit aktuální běh před vypršením retention |
| WS `logbook/get_action_calls` v krátkém okně | Admin-only; ověřit skutečný list response a `when` Unix timestamp; pozitivní projekce odstraní `service_data` kromě validovaných target IDs |
| Supervisor `GET /addons`, `/addons/<slug>/info`, `/addons/<slug>/stats` | Validovat `result/data`, správný slug a čerstvost. Role `manager` má i write: token zůstává jen v brokeru |
| Supervisor `/addons/<slug>/logs` | Zdokumentovaný kontrakt, současný `SupervisorReader` jej nevystavuje. Do implementace a integrační přejímky označit chybějící zdroj, ne úspěch |
| `system_log/list`, `system_log/subscribe_raw`, `system_health/info` | Kontrakty prozkoumané; současný reader nemá stream handler. Nejprve implementovat bounded subscription v brokeru a ověřit finish/unsubscribe; jinak uvést nedostupné |
| ZHA živé `zha_event`, `zha/device`/`zha/devices` | Současný reader nemá ZHA subscription. Sběr přes budoucí ověřený broker; žádný permit/bind/reconfigure jako čtecí test |
| MA FastMCP `tools/list` a vybraná čtení | Adaptér zatím není hotový. Ověřit konkrétní schema/pin, explicitní read-only capability, timeouty a redakci. Žádný command passthrough |

U každého zdroje samostatně zapsat installed, running, interface available,
authenticated, read succeeded, relevant, last error a evidence age. Neznámou
hodnotu ponechat neznámou. Výsledek 403 není důvod rozšířit práva workeru.
Vyzkoušet chybné credentials bez zveřejnění jejich obsahu, vypnutý zdroj a timeout;
náhradní cesta smí používat jen již schválená čtení.

Před předáním modelu vložit do **syntetické laboratorní odpovědi** canary secret
v `service_data`, `context_message`, neočekávaném klíči a v URL/exception.
Prokázat, že není v AI snapshotu, SQLite spisu, HTML, JSON exportu ani reportu.
Nepoužívat skutečné alarm kódy. Redakční test nevyžaduje volat alarm službu.

## J3A – rádio se samo zastaví

1. Vlastník určí testovací player/entity/provider a nahlásí konkrétní symptom,
   například „Rádio se právě samo vypnulo“. Zapsat čas `T0`, očekávaný stav a
   funkční dopad. Pozorování nemá samo zapínat, vypínat ani měnit hlasitost.
2. Získat HA historii nejméně `T0−5 min` až `T0+2 min`, pokud ji Recorder drží;
   zaznamenat skutečně pokryté okno. Přidat Action history a relevantní traces,
   MA player/queue/provider stav, recent events a logy, pokud jsou dostupné a
   povolené. Časová mezera nebo chybějící zdroj musí zůstat viditelný.
3. Korelovat target IDs, `context_id`, původ uživatele/automatizace a čas události.
   Změna `playing→idle` sama nedokazuje stop příkaz. Blízký log o síti sám
   nedokazuje přerušení streamu. MA a HA pořadí může mít zpoždění.
4. Výsledek musí rozlišit doložený stop od uživatele/automatizace, změnu z
   integrace, výpadek streamu, odpojení přehrávače, nedostupný provider, síťový
   výpadek a nedostatek důkazů. Vysvětlení v češtině ukáže důkazní oporu a
   chybějící krok; bez opory nevytvoří automaticky opravný plán.
5. Pro test klasifikace může operátor v laboratoři zvlášť a výslovně schválit
   kontrolní běh s vlastním stopem nebo odpojením testovacího playeru. Jde o
   označený řízený experiment, nikoli samovolný incident nebo automatickou
   diagnostickou akci. Síť produkční domácnosti se neodpojuje.
6. Je-li později schválena podporovaná oprava, vlastník ručně spustí testovací
   rádio a potvrdí slyšitelný výsledek. Sbírat nové stavy i události po zásahu.
   Předem určit sledování nejméně 30 minut a alespoň dvojnásobek známého intervalu
   opakování. Pro denní/nahodilou závadu zvolit odpovídající delší okno; krátký
   běh není důkaz vyřešení. Všechny mezery sběru brání tvrzení o souvislém pokrytí.

## J3B – Zigbee ovladač a výsledná reakce

1. Zapsat testovací device ID/IEEE, automatizaci, její podmínky a očekávanou
   cílovou entitu. Ověřit baterii/dostupné link údaje jen podporovaným čtením.
   LQI/RSSI snapshot není důkaz, zda se konkrétní fyzický stisk stal.
2. Spustit časově omezený odběr před uživatelským pokusem. UI požádá:
   **„Stiskni nyní prostřední tlačítko. Ověřím, kde se ztratí reakce.“**
   Operátor zaznamená čas skutečného stisku nezávisle na ZHA události.
3. Vyhodnotit řetězec: pozorovaný stisk → ZHA událost správného zařízení →
   spuštění správné automatizace → výsledek podmínek v trace → skutečná akce
   se správným target → nový stav testovací lampy → uživatelské potvrzení světla.
   Pouhé ruční „spustit automatizaci“ neověřuje trigger z ovladače.
4. Když není ZHA událost zachycena, napsat „Stisk není v dostupných datech;
   nelze určit, zda jej zařízení odeslalo“. Když událost existuje, určit
   první doloženě neúspěšný krok, neobvinit automaticky Zigbee síť.
5. Po budoucí schválené opravě provést deset předem dohodnutých stisků s
   dostatečnými rozestupy pro debounce a dokončení akce. Každý má vlastní čas,
   událost/trace a cílový výsledek. Test nesmí ovládat rizikové zařízení.
   Ověřit také podmínku, při které reakce nastat **nemá**, aby oprava
   neodstranila záměrnou podmínku. Deset pokusů není statistická záruka spolehlivosti.
6. Sledovat nejméně 30 minut bez mezery sběru a podle četnosti původní závady
   déle. Opakování po dočasném zlepšení znovu otevře stejný incident.

## J4 – první živá oprava, až po splnění J0

Současná implementace opravuje pouze jeden odkaz v izolovaném JSON souboru.
Tato část je **BLOCKED**, dokud není zpřístupněný a přezkoušený produkční HA
adaptér a schvalovací vazba na přesný plán. Ověření vlastníka čtecího UI již
existuje; samo neposkytuje oprávnění k opravě. Žádný níže popsaný krok nyní nespouštět náhradním shellem.

1. V čistém laboratorním HA vytvořit samostatnou bezpečnou automatizaci pro
   testovací lampu a záměrně chybný entity odkaz. Zapsat původní konfiguraci,
   její hash a správnou registry vazbu. Ostatní automatizace držet mimo rozsah.
2. HADS načte skutečný symptom a důkazy; skutečný Hermes runtime požádá alespoň
   o jeden další relevantní důkaz a dostane ho od brokeru. Pokud model nejede,
   deterministický spis pokračuje a chybějící AI krok zůstane označený.
3. Zobrazit jediný konkrétní diff, cíl, důvod/evidence IDs, riziko, zálohu,
   preconditions, očekávaný výsledek, watch interval, rollback a ruční alternativu.
   Vlastník v autentizovaném rozhraní zvolí Schválit opravu / Zamítnout /
   Provést ručně. Rozhodnutí uložit bez vystavení credential tokenu AI.
4. Před schválením, po odmítnutí a s cizím uživatelem ověřit odmítnutí zápisu
   přes každé dostupné rozhraní. Pozměnit target/parametr po schválení: vykonavatel
   musí zastavit bez změny. Po návratu cíle je potřeba nový plán/souhlas.
5. Po platném souhlasu vykonavatel provede jen přesně autorizovanou změnu,
   uloží intent a výsledek. Čerstvým čtením ověřit diff a nedotčené okolní objekty.
   HTTP 200 není potvrzení funkčního účinku.
6. Vlastník provede fyzický trigger. Ověřit skutečnou trace a cílový stav se
   stejným nebo doloženým rodičovským/potomkovským kontextovým řetězcem. Nepřepsat
   skutečná context IDs na shodná jen kvůli verifieru. Dnešní fixture verifier
   nepředstavuje kompletní živý resolver kontextového grafu.
7. Při neúspěchu zastavit další opravy, zachovat důkazy a vytvořit český report.
   Rollback smí být jen podporovaný a znovu explicitně schválený plán, s kontrolou
   současného stavu; ověřit jeho funkční výsledek. Obnova jednoho souboru není
   obnova HAOS. Nevratná operace nesmí slibovat automatický rollback.
8. Restart během testovacího zásahu provést pouze na laboratoři s obnovovací
   cestou. Zkoušet před intentem, po intentu a po potvrzení změny. Nesmí vzniknout
   duplicitní zápis. Neznámý výsledek se znovu přečte a čeká na nové schválení;
   samotný restart nedává oprávnění pokračovat.
9. Vytvořit kontrolní falešnou opravu: odstranit jen logový symptom ve fixture
   nebo testovacím zdroji, funkční poruchu ponechat. Incident musí zůstat otevřený.
   Nevypínat produkční diagnostiku a nemazat skutečnou historii.

Výsledky: Vyřešeno a ověřeno / Oprava provedena, ověření čeká / Částečné zlepšení /
Oprava selhala / Problém se opakoval / Není dostatek důkazů. Každý report uvádí,
co se funkčně stalo, dobu pokrytí a omezení. Neúplné pokrytí nebo neprovedený
uživatelský test nedovolí „Vyřešeno a ověřeno“.

## J5 – výkon, výpadky a bezpečný provoz

Stejný kandidát otestovat na AMD64 a ARM64; zvlášť skutečný RPi 4 / 2 GB.
Emulovaný ARM64 build není důkaz běhu ani paměťové rezervy na tomto RPi.

- Změřit baseline a nejvyšší RSS/cgroup memory, CPU, počet procesů/frontu,
  latenci UI/HA, růst DB a volné úložiště při klidu, burstu událostí a jedné AI
  úloze. PSI číst jen dostupným podporovaným zdrojem; nedostupnost přiznat.
- Před během stanovit měřitelné limity z baseline a manifestu kandidáta. Jedna
  aktivní AI úloha, omezené čtení/retence a hard limity musí udržet rezervu pro
  HA. Bez naměřené rezervy se AI na RPi neaktivuje. Zásah watchdogu, OOM,
  zhoršení běžného provozu nebo ztráta funkčních důkazů znamenají nepřijetí.
- Odpojit pouze testovací model endpoint. Evidence a deterministická diagnostika
  pokračují, případy se neztrácejí a fronta neroste neomezeně. Obnova modelu
  nesmí opakovat analýzu bez nových důkazů nebo znovu provést zásah.
- Ověřit deduplikaci opětovným čtením stejných logů; jeden doložený DNS výpadek
  s více integračními projevy vytvoří jeden hlavní případ s navázanými projevy.
- Otestovat restart HADS, heartbeat, bounded retry a retenci. Výpadek zdroje
  má srozumitelné české vysvětlení a neuzavírá incident.
- Pokud RPi podmínky nesplní, ponechat deterministický read-only provoz a AI
  spouštět jen při prokázané rezervě. Případný jiný runtime/host je nová explicitní
  varianta s vlastní přejímkou, ne důkaz splnění požadavku na lokální Hermes.

## Migrace RC3: pouze read-only pilot, žádná stará schválení

Tento strom nedodává hotový migrační importér. Před jeho napsáním a ověřením
nelze měnit schéma nebo data RC3. Výchozí RC3 aplikace používá uvnitř aplikace
`/data/hads4.db`; tato cesta není návodem na přístup k hostiteli HAOS.

1. Pracovat s konzistentním exportem z existující autorizované zálohy RC3 nebo
   podporovaným konzistentním snapshotem. Nekopírovat jen živý SQLite DB soubor
   bez odpovídajícího WAL/SHM a nesahat privilegovaně na hostitelské adresáře.
   Pokud konzistence není doložena, export neimportovat.
2. Před exportem zdokumentovat původní verzi, commit/archiv SHA, schema version,
   ID zálohy, readback/restore evidence a čas. Originál ponechat beze změny;
   kontrolní SHA-256 počítat na stabilním exportu, ne proměnlivém živém souboru.
3. Obnovu celé požadované zálohy provést na jednorázovém odpojeném HAOS a ověřit
   Core/config i RC3 data. Test nesmí připojit obnovené produkční tokeny do sítě.
   Zaznamenat obnovitelnost odpovídající rozsahu; samotný ZIP DB je jen datový export.
4. Z konzistentní kopie číst SQLite read-only, bez inicializace starého runtime,
   migrací, `VACUUM`, změn pragmat trvale zapisujících zdroj nebo importů secrets.
   Před importem zkontrolovat integritu kopie, tabulky, počty a retenční rozsah.
5. Předem schválit mapování do nového verzovaného schématu: původní incident ID,
   původ a čas důkazů, skutečné opakování, hypotézy a historické výsledky. Zachovat
   namespace původu RC3, redigovat data a nededuplikovat jen podle podobného textu.
6. **Nepřenést platná schválení, tokeny, leases, frontu zápisů, running intents
   ani plán určený k automatickému provedení.** Stará rozhodnutí smí být nanejvýš
   neautorizující historická informace. Next vyžaduje nový přesný plán a souhlas.
7. Pilotní import nejprve do nové prázdné Next DB v laboratoři. Ověřit počty,
   export, původ, deduplikaci, opakování, zachování času a nulovou vykonatelnou
   frontu. Spustit znovu tentýž import: nesmí duplikovat důkazy.
8. Návrat znamená zastavit testovací Next, uchovat jeho nové důkazy a znovu použít
   nezměněný RC3 zdroj/DB podle ověřeného postupu. Next schéma se nikdy nezapisuje
   zpět do RC3. Konfliktní aktivní vykonavatelé nesmějí běžet souběžně.

## Akceptační tabulka – vyplnit až skutečnými výsledky

`ČEKÁ` znamená neprovedeno. Pole evidence musí později obsahovat neveřejný
redigovaný artefakt, jeho SHA-256 a rozsah měření. Verze/datum/operátor se vyplní
ze skutečného běhu; nepřebírají se z historických účtenek RC3.

| Test / přijímací podmínka | Stav live | Evidence | Verze / commit / hardware | Datum UTC | Operátor |
|---|---|---|---|---|---|
| J0 balíček a ověřená instalační cesta | ČEKÁ – preview existuje, živá přejímka neproběhla | čeká | čeká | neprovedeno | neurčen |
| J0 autentická identita, expirace, replay, cizí uživatel | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J0 broker/worker/executor isolation, všechny write cesty | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J0 OneDrive readback a nezávislý restore test | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J1 čistá AMD64 HAOS instalace a návrat | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J1 ARM64 HAOS na RPi 4 / 2 GB a návrat | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J2 Core REST/WS skutečná čtení a chyby práv | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J2 Supervisor aplikace/info/stats/logs | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J2 Action history redakce před DB/AI/exportem | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J2 živé logy/System Health a ukončení subscription | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J3A rádio – stop/stream/disconnect/unknown | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J3A MA discovery, oprávnění, read-only diagnostika | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J3B skutečný stisk → event → trace → akce → fyzická reakce | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J4 nový důkaz ve skutečné Hermes smyčce na HAOS | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J4 přesný plán → souhlas → pouze autorizovaný zápis | ČEKÁ – write adaptér chybí | čeká | čeká | neprovedeno | neurčen |
| J4 funkční výsledek a celé sledovací okno | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J4 restart bez duplicit a autorizovaný rollback | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J4 falešná oprava incident neuzavře | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J5 výpadek AI, dedup, DNS korelace, zotavení | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| J5 CPU/RAM/PSI/latence/retence na RPi 4 / 2 GB | ČEKÁ | čeká | čeká | neprovedeno | neurčen |
| Migrace read-only, provenance, nulová stará schválení | ČEKÁ – importér chybí | čeká | čeká | neprovedeno | neurčen |
| Český Command Center a závěrečný report s omezeními | ČEKÁ | čeká | čeká | neprovedeno | neurčen |

Přijetí M5 vyžaduje doložené splnění všech povinných bran a funkčního výsledku
na cílové platformě. Neprovedený řádek se nesmí označit PASS ani skrýt v počtu
unit testů. Produkční rozhodnutí je následný samostatný krok vlastníka; tento
protokol ani jeho příprava nedávají oprávnění zasáhnout produkční domácnost.
