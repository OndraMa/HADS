# RC4: HADS čte a vyšetřuje, uživatel schvaluje změny

RC4 opravuje provozní mezeru RC3: nativní read-only příkazy nemá provádět uživatel.
Paměťový incident sám spustí trvalou frontu čtení statistik Core, Supervisora a
nejvýše 24 běžících aplikací. Výsledek a mezery uloží do spisu, ukáže spotřebu,
porovná limity a po pěti minutách samo získá ještě druhé měření Core,
Supervisora a nejvýše tří aplikací. Nedokončený GET po restartu bezpečně naváže;
selhání zdroje se nejvýše jednou opakuje s odstupem, potom zůstává viditelnou
mezerou. Nemění instalace ani nevyvozuje únik paměti z jediného čísla.

Marketplace/github_web se dále prověřuje nativním System Health, časově
souvisejícím System Log a pevným neautentizovaným HEAD na https://github.com/.
Výsledek sondy platí pro síťový kontext aplikace HADS. Nelze jím automaticky
prokázat přístup integrace v Core. Sonda nepřijímá URL z modelu nebo logu,
neposílá údaje domácnosti, klíče ani cookies a nenásleduje přesměrování.

## AI se zapíná až samostatným rozhodnutím

Originální Hermes zůstává připnutý na upstream revizi
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`. Není nahrazen generátorem JSON.
Automatická nativní čtení fungují bez poskytovatele a bez placeného modelu.
Výsledky jsou dostupné i brokeru Hermesu ve spisu; nevyžaduje je od uživatele.

Výchozí AI test: maximálně 3 skutečně odeslané požadavky za klouzavých 24 hodin,
48 000 bajtů vstupu a 512 výstupních tokenů na požadavek. Trvalé společné
počítadlo je před síťovým voláním, sdílené i s testem poskytovatele a odolné
proti restartu, souběhu a výměně klíče. Nejasné dokončení se započítá a samo se
neopakuje. Test se spustí pouze výslovně pro vybraný případ, nikoli automatickou
placenou frontou. Starý souhlas z RC3 vyžaduje nové potvrzení. Rozšířený režim
8 požadavků/případ a 12/24h i autonomní modelové vyšetřování mají vlastní volbu.
Cena závisí na tarifu/modelu; tyto technické limity nejsou garantovaným dolarovým
stropem a HADS nemá nezávislou kontrolu účtu u poskytovatele.

Po zahájení služby a přihlášení vlastníka HADS samo ověří nativní zdroje a
pokusí se ověřit izolovaný Hermes bez modelu. Paměťová brána 576 MiB zůstává
zachovaná. Při 373 MiB se worker nespustí; remote model neodstraňuje paměťovou
potřebu lokálního Hermesu. Tento blocker musí HADS vysvětlit a samo prověřit,
nepřekonává se snížením ochrany ani příslibem opravy bez důkazů.

## Aktualizace RC3 a data

Použij pouze úvodní `--upgrade-rc3` z nového instalátoru. Běžící RC3 se předem
ručně nezastavuje ani neodinstalovává. Ověřuje se původ každého souboru z přesného
vydaného RC3 manifestu SHA-256
`4d62ee8f2d90e973a7fae1413a3bb0c9dd3a5bf4364666720a6d8df819453c74`.
Nativní Supervisor update vyžádá částečnou zálohu této aplikace a zachová její
soukromá data i předchozí stav started/stopped. Cizí zdroje, stav error nebo
nejasný dřívější zásah se neobcházejí. Archiv zdrojů není obnova dat ani plné
HAOS/OneDrive. Při nejasném výsledku se další zápisy blokují a marker zůstává.

Služba zpracovává SIGTERM korektním ukončením HTTP serveru a workerů. To se
ověřuje na skutečném kontejneru; samo to nedokazuje příčinu dříve hlášeného
stavu error v konkrétním HAOS. Původní RC3 a vydané archivy zůstávají nedotčené.

## Hranice ověření

Testy používají izolované HTTP/WebSocket fixtures a skutečný Core 2026.11.0
s původním izolovaným Hermesem. AI endpoint je lokální skriptovaný HTTPS server,
ne skutečný placený LLM. Samostatný test musí prokázat dvě čtení řízená skutečným
Hermesem v rozpočtu tří volání a odmítnutí čtvrtého před odesláním.

Přejímka poslední zdrojové revize `cae2eabf1287ef4d952e66df4c1ffa79033b4ede`
prošla: 224 offline a bezpečnostních testů na každé architektuře, skutečný Core
a izolovaný původní Hermes na nativních ARM64 i AMD64 a 16 zobrazení rozhraní.
Omezený test skutečně provedl dvě čtení ve třech modelových požadavcích; čtvrtý
byl odmítnut před sítí. Kontejner zvládl SIGTERM s kódem 0 a uchoval případ po
restartu. Instalační soubor i zdrojový archiv vyšly na obou architekturách
shodně; všech 53 souborů vloženého payloadu je porovnáno s přesnou Git revizí.
Test startovního souběhu ověřuje načtení Core bez ručního obnovování.

Reprodukovatelné výsledky:
[nativní přejímka](https://github.com/OndraMa/HADS/actions/runs/43442196703),
[prohlížeč](https://github.com/OndraMa/HADS/actions/runs/43442203778),
`docs/evidence/installation-1.0.0-rc4/ACCEPTANCE.json` a přiložené protokoly.

Živá HAOS aktualizace, záloha/restore na cílové instalaci, RPi při aktuální
zátěži, skutečná dostupnost Marketplace, MA FastMCP, fyzické rádio/Zigbee a reálný
úsudek placeného modelu stále potřebují přejímku. Podporované opravy mají nadále
vlastní přesné schválení a funkční ověření. Příčina chyb ani fyzický výsledek se
nevydávají za vyřešené tím, že sběr doběhl nebo model vytvořil závěr.
