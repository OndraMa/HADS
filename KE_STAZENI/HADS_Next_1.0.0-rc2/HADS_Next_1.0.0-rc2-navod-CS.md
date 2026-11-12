# HADS Next 1.0.0-rc2 — kandidát pro omezenou přejímku

Tento kandidát není produkčně ověřený. Původní Hermes, broker, kontinuální
funkční monitory, schvalování, CAS reference, verifier, rollback a české UI
jsou propojené. Přibyla praktická nativní oprava: opětovná aktivace vlastníkem
vybrané jednoduché světelné automatizace. Obecná editace konfigurací není povolená.

## Stažení a bezpečná instalace

V soukromém GitHubu otevři větev `codex/hads-next-practical-acceptance`, adresář
`KE_STAZENI/HADS_Next_1.0.0-rc2`. Kompletní ZIP obsahuje instalační soubor,
český návod, companion integraci, zdroje a protokoly. Ve Windows použij
Download raw file a porovnej SHA-256 s přiloženým manifestem:

```powershell
Get-FileHash .\HADS_Next_install_1.0.0-rc2.sh -Algorithm SHA256
```

Skript se nespouští ve Windows. Pro instalaci použij **oddělený testovací HAOS**
s Core alespoň 2026.11.0. Terminál potřebuje `ha`, `bash`, `python3`, `base64`,
`mktemp` a existující připojené `/local_apps` nebo `/addons`. Chybějící Python
zastaví instalaci před změnou; neinstaluj vývojové balíčky do hostitele HAOS.
Alternativou je extrakce v Linuxu/WSL a ruční přenos do místních aplikací.
Stavba potřebuje internet pro připnutý base image, Hermes a constraints.

```sh
bash HADS_Next_install_1.0.0-rc2.sh --verify
bash HADS_Next_install_1.0.0-rc2.sh --install-dev
```

Pouhá inspekce, bez volání HA CLI a bez vykonání obsahu:

```sh
bash HADS_Next_install_1.0.0-rc2.sh --extract-only /absolutni/novy-adresar
```

Nový slug je `local_hads_next_practical`. RC3, 0.1, 0.2 i RC1 mají vlastní identitu
 a data a nepřepisují se. Existující cíl, symlink nebo opakovanou instalaci
instalátor odmítne. Neprovádí automatický uninstall, migraci databáze ani restart
Core. Selže-li sestavení, zachovej výstup a nezvyšuj oprávnění aplikace.

Pro ruční instalaci ze zdrojů v místních aplikacích:

```sh
ha store reload
ha apps install local_hads_next_practical
ha apps start local_hads_next_practical
ha apps info local_hads_next_practical
```

Starší CLI může používat alias `addons`; ověř jeho `--help`. Aplikace má ruční
start. Otevři její ingress přes Nastavení → Aplikace. Nevyžaduje Docker socket,
konfigurační mount, host network, další privileged capabilities nebo vypnutí
AppArmor/protection mode. Skutečná kompatibilita HAOS profilu ještě čeká.

## První nastavení

Průvodce ověřuje správce přes skutečné `config/auth/list`; běžně se nekopíruje
`owner_user_id` do YAML. Jiný uživatel, přímé spojení a cizí ingress identita
data ani schválení nezískají. Vlastník zkontroluje všech jedenáct položek:
verzi/platformu, Core, Supervisor/OS, jednotlivé zdroje, runtime, paměť,
poskytovatele, náklady, zálohy, opravný katalog a funkční diagnostiku.
**Čekající kontrola se nezelená pouze kvůli existující konfiguraci.**

Nejprve spusť kontrolu původního Hermes **bez modelu**. Nevolá API poskytovatele,
nepotřebuje klíč a nespouští staré placené úlohy. Minimální rezerva 576 MiB se
znovu kontroluje před každým workerem; nelze ji vypnout kvůli úspěchu testu.
Jeden worker má limit adresního prostoru 384 MiB. Na skutečném RPi 4 / 2 GB
se celková rezerva musí změřit při současném Core/ZHA/MA; kontejner to nenahrazuje.

Pokud chceš AI, nastav HTTPS OpenAI-compatible chat/completions API a vlastní
model, potom výslovně potvrď případné náklady a předání redigovaných důkazů.
ChatGPT Plus není API účet. Klíče patří jen do privátního nastavení, nikdy do
chatu, YAML zdrojů nebo GitHubu. Nejvýše 8 volání na případ / 12 denně,
1024 výstupních tokenů na požadavek. Nejasné dokončení blokuje tiché opakování.
Veřejný výzkum má zvláštní souhlas, pevné zdroje a limit 6 nových dotazů denně.

## Autonomní detekce a vyšetřování

Ve Sledovaných funkcích nastav konkrétní očekávání: nedostupnost, očekávaný
stav, přerušení přehrávání, nebo odezvu cíle po události spouštěcí entity.
Přehrávání nastav s očekáváním `playing`. HADS jej neprohlásí za poruchu pouze
proto, že již při spuštění bylo vypnuté. Propojenou automatizaci lze zadat jako
rozsah dalšího čtení. Je dovoleno nejvýše 32 pravidel; obvyklá prodleva je 30 s.

HADS odebírá skutečné změny stavů a hlídá konec podmínky. Mezery, výpadek a restart
ruší neprokázané intervaly. Stejný trvající problém nevytváří další výskyt;
obnova a další selhání znovu použijí stejný spis. Automatické AI vyšetřování
vyžaduje samostatný souhlas nad rámec nastavení poskytovatele. Bez něj detekce,
spisy a ruční zahájení fungují. Kompletní logy se nepollují; systémové zdroje
se kontrolují omezeně po pěti minutách. Nečitelný zdroj je viditelný.

Nejsou-li očekávání spolehlivě odvoditelná, nastav pravidlo nebo nahlas incident
s entitou a časem. Zdroj chybí ≠ prokázaná příčina. Spis ukazuje kroky, citace,
nejistoty a další test. Surová data jsou v technickém detailu.

Music Assistant je volitelný HTTPS FastMCP s pevnými read-only schématy a mapováním
přehrávače. Chybějící debug nástroj/buffer zůstane nepřečtený. ZHA žurnál uchovává
jen omezené softwarové události a mezery; nezaznamenaný fyzický stisk nedokazuje.
HADS jako diagnostický test nemění hlasitost ani přehrávání.

## Schválení, funkční ověření a rollback

Na stránce Opravy stáhni companion balíček a postup `README_CS.md`. Obsahuje
podporovanou custom integraci a YAML **pouze virtuálního testovacího okruhu**.
Jejich instalaci provádí operátor testovacího Core vědomě; aplikace nemá mount
konfigurace a nic do ní sama nekopíruje. Po instalaci a vlastní kontrole Core
povol pouze tento katalog. Bez čitelného companion API se katalog nepovolí.

Nativní automatizace používá šablonu odkazující na integračně vlastněný senzor.
CAS mění pouze jeho vlastní referenci mezi dvěma pevnými virtuálními ID.
Nedoplňuje CAS do obecného Core config API a neopravuje libovolné automatizace.
Žádná jiná konfigurace se nepřepisuje. Snapshot jediné reference není záloha HAOS.
Rizikové OneDrive operace zůstávají blokované bez nezávislé obnovitelnosti.

Ve spisu připrav plán a zkontroluj přesné před/po, revizi, citace, riziko,
snapshot, sledovací dobu a návrat. Tlačítko **Schválit opravu** existuje pouze
pro připravenou podporovanou operaci. Backend ověří vlastníka, CSRF, neměnný
plán, původní stav, snapshot, expiraci a jednorázový token. Server atomicky
porovná revizi i hodnotu. Souběžná změna vyžaduje nový plán a souhlas.

Po schválení stiskni pouze virtuální testovací tlačítko. Ověření potřebuje
skutečné spuštění automatizace a cílový stav se stejným kontextem, nepřerušené
odběry a 10 sekund sledování. HTTP 200 ani zmizení chyby incident neuzavřou.
Rollback je nový plán s novým schválením; obnovuje jednu referenci. Vrácený
chybný původní odkaz se nesmí označit za funkční opravu. Při neznámém výsledku
se další zásahy zastaví. Restart neopakuje zápis ani nevydává nový souhlas.

## Aktualizace a historie

Tato verze se přidává vedle 0.2, nemusí mazat její data. Nové datové schéma
má vlastní namespace. Pro historické spisy použij JSON export Next schema 1,
importuj v Historii. Import je idempotentní, zachovává výskyty a redigované
podklady, ale nepřenáší schválení, leases, tokeny ani platnost vyřešení.

Má-li starší aplikace pouze SQLite databázi, nejprve pořiď podporovaný konzistentní
export ze zálohy. Skript `scripts/export_previous_next.py --copied-snapshot KOPIE.sqlite
--output NOVY_ADRESAR` zkopírovanou Next DB čte read-only a vytvoří neautorizující
JSON spisy. Nespouštěj ho nad živým souborem. Přímý import odlišného RC3 schématu
není povolený; původní RC3 data zůstávají zachovaná.

Bezpečný návrat znamená zastavit pouze `local_hads_next_practical`, exportovat
jeho nové spisy a používat nezměněnou předchozí aplikaci. Neodinstaluj ji ani
nesdílej datové svazky. Automatické přepsání instalovaného kandidátu není podporované;
nový testovaný build vyžaduje samostatně ověřený update postup.

## Hranice přejímky

Skutečný LLM, živý HAOS ingress/AppArmor, Supervisor/MA server, fyzické rádio/Zigbee,
RPi 4 / 2 GB a OneDrive restore vyžadují externí přejímku. Verzi nelze označit
za produkčně hotovou. Přesné nativní výsledky a zbývající brány patří do
souhrnného protokolu; staré testy nejsou důkazem nových bajtů kandidátu.

## Praktická světelná oprava bez companion integrace

1. Obnov čtení Core a otevři **Světelné opravy**. Vyber skutečnou automatizaci.
2. Potvrď záměr: má být zapnutá a ovládá pouze zvolené bezpečné světlo.
   Backend si přečte úplnou konfiguraci a skutečné stavy. Povolený tvar má
   jediný stavový trigger (`binary_sensor` přechází na `on`, nebo `input_button`),
   jedinou akci `light.turn_on` na jednom explicitním světle, režim `single`
   a žádné podmínky, šablony, oblasti, data služby ani další akce.
   Tlačítko před prvním stiskem může mít normálně stav `unknown`.
3. Je-li tato automatizace neočekávaně vypnutá, systémová kontrola vytvoří spis.
   Kontroluje nejvýše 32 vlastníkem vybraných záměrů. Kontrolu lze zahájit ručně
   přes Zdroje; jinak běží po pěti minutách. Bez souhlasu s AI zůstává plně funkční.
4. V příslušném spisu potvrď, že stejný cíl současně nikdo neupravuje,
   a připrav přesný plán. Před schválením ověř cílové světlo i spouštěč.
5. Schválení je vázané na neměnný plán a aktuální kontext, konfiguraci i stav.
   Executor volá jen `automation.turn_on` pro tento cíl. **Nativní stavová služba
   nemá CAS**: konfiguraci nepřepisuje a netvrdí atomické ověření její neměnnosti.
   Existuje úzké závodní okno mezi posledním čtením a službou. Proto je nutná
   výlučná práce s cílem a pozitivní omezení na bezpečné světlo.
   Aktivace umožní budoucí triggery; není to pouhá kosmetická změna.
6. Po zásahu je spis stále otevřený. Vyvolej skutečný spouštěč. HADS vyžaduje
   odpovídající kontext automatizace a světla, alespoň deset sekund souvislého
   sledování a následné potvrzení vlastníka, že **správné fyzické světlo** reagovalo.
   Předčasné potvrzení ani HTTP 200 nestačí. Pokud je světlo již zapnuté,
   potřebný přechod nelze prokázat; další kontrolovaný test provádí vlastník.
7. Návrat je nový plán s novým schválením. Volá `automation.turn_off` se
   `stop_actions=false`, vypne budoucí triggery a **nevrací fyzické účinky světla**.
   Konfigurační snapshot není záloha HAOS ani náhrada OneDrive obnovitelnosti.

Pokud podmínky neplatí, HADS zápis odmítne a nabídne ruční postup. Chybějící
oprávnění není důkaz, že entita neexistuje. Nejasný výsledek či restart po záznamu
záměru zabrání automatickému opakování stejného zásahu.

## Automatické zdraví instalace

Bez jednotlivých funkčních pravidel se čtou nativní Core config, Supervisor,
seznam aplikací, Repairs, dokončené System Health, čerstvé opakované chyby
Recorderu, explicitní reference omezené dávky automatizací a vybrané záměry.
Supervisor `/host/info` poskytuje disk v GiB. Řadič ukládá nejvýše 240 paměťových
vzorků, CPU, povinnou rezervu a špičku původního workeru. Volitelný MA health
přidá strukturované chyby providerů. ZHA mezera je diagnostická mezera,
nikoli důkaz ztraceného fyzického stisku. Verze před novou závadou se uchová jako
časová souvislost, nikoli dokázaná příčina. Opakované stejné čtení nepřidává
výskyty ani znovu nevolá AI. Automatické Hermes vyšetřování významných nálezů má
samostatný výslovný souhlas a původní denní rozpočet.

Zastavená aplikace může být záměr; automatický incident vzniká pouze pro
explicitní stav `error`/`failed`. Samotný výpadek socketu nedokazuje restart Core
nebo Supervisora. Pokud API neposkytne konkrétní údaj, schopnost zůstane
neověřená; globální „všechno zdravé“ se z toho neodvozuje. Spook nálezy v Repairs
se čtou nativně. Watchman bez strukturovaného zdroje není vydáván za přečtený.

## Živá přejímka a skutečný model

Otevři **Živá přejímka**, potvrď oddělené testovací prostředí a založ protokol.
Dvanáct kroků zůstává samostatně ve stavu Prošlo / Selhalo / Nedostupné /
Čeká na test. U logů vyber skutečnou aplikaci, u incidentů skutečný spis.
Po restartu se vrať na stejnou adresu protokolu; databáze se zachová a nová
instance se porovná s původní. Export obsahuje pouze pevné důvody, stavy,
časy, pseudonym protokolu a numerické metriky. Neobsahuje logy, názvy entit,
prompty, vlastníka, endpointy ani tokeny. Celý export spisu je oproti tomu
technický dokument domácnosti; nesdílej ho jako anonymizovaný protokol.

Jednorázový modelový test má zvláštní souhlas s jedním případně placeným
požadavkem. Používá stejný denní rozpočet, po nejasném výsledku se neopakuje.
Změna poskytovatele zneplatní starý zelený výsledek. **Komunikační test
neprokazuje úsudek Hermes.** Pro ten je nutné následující ověření:

1. Nastav svůj HTTPS kompatibilní endpoint, klíč a model pouze v privátním UI.
   Povol vyšetřování jednoho spisu. Autonomii a veřejný výzkum můžeš ponechat vypnuté.
2. Na bezpečném testovacím světelném okruhu nahlas nesplněnou funkci nebo použij
   automaticky zachycené neočekávané vypnutí vybrané automatizace. Do symptomu
   nevkládej příčinu, hotovou diagnózu nebo požadovaný nástroj.
3. Spusť vyšetřování. Ve spisu zkontroluj skutečně vybrané nástroje, jejich
   výsledky a citace. Model musí požádat o další důkaz a předat relevantní úkol
   specialistovi; zkontroluj alternativní hypotézu a chybějící údaje.
4. Zkontroluj, že závěr cituje existující důkazy a že návrh projde nezávislým
   plannerem. Při nedostatku důkazů musí být nabídnut další test, nikoli vymyšlená příčina.
5. Bez schválení nesmí dojít ke změně. Nesmyslný cíl či jiná služba se odmítnou
   bez ohledu na text modelu. Podporovaný plán případně schval vlastníkem,
   vyvolej skutečný trigger a dokonči fyzický test i sledování.
6. Zaznamenej model, verzi, datum a uvedená kritéria v přejímkovém protokolu.
   Citlivý úplný spis ponech soukromý; k analýze sdílej anonymizovaný export.

V Cloud prostředí nebyl dostupný autorizovaný skutečný model ani HAOS.
Modelový úsudek, skutečný ingress/Supervisor, MA server a fyzická zařízení
proto čekají na tento postup. Předem napsaný protokolový model je nenahrazuje.
