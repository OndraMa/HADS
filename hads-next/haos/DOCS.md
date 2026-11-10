# HADS Next 1.0.0-rc1 — kandidát pro omezenou přejímku

Tento kandidát není produkčně ověřený. Původní Hermes, broker, kontinuální
funkční monitory, schvalování, CAS reference, verifier, rollback a české UI
jsou propojené. **Jediný zapisovací katalog je vlastní virtuální testovací
reference**, nikoli obecná editace automatizací domácnosti.

## Stažení a bezpečná instalace

V soukromém GitHubu otevři větev `codex/hads-next-final-delivery`, adresář
`KE_STAZENI/HADS_Next_1.0.0-rc1`. Kompletní ZIP obsahuje instalační soubor,
český návod, companion integraci, zdroje a protokoly. Ve Windows použij
Download raw file a porovnej SHA-256 s přiloženým manifestem:

```powershell
Get-FileHash .\HADS_Next_install_1.0.0-rc1.sh -Algorithm SHA256
```

Skript se nespouští ve Windows. Pro instalaci použij **oddělený testovací HAOS**
s Core alespoň 2026.11.0. Terminál potřebuje `ha`, `bash`, `python3`, `base64`,
`mktemp` a existující připojené `/local_apps` nebo `/addons`. Chybějící Python
zastaví instalaci před změnou; neinstaluj vývojové balíčky do hostitele HAOS.
Alternativou je extrakce v Linuxu/WSL a ruční přenos do místních aplikací.
Stavba potřebuje internet pro připnutý base image, Hermes a constraints.

```sh
bash HADS_Next_install_1.0.0-rc1.sh --verify
bash HADS_Next_install_1.0.0-rc1.sh --install-dev
```

Pouhá inspekce, bez volání HA CLI a bez vykonání obsahu:

```sh
bash HADS_Next_install_1.0.0-rc1.sh --extract-only /absolutni/novy-adresar
```

Nový slug je `local_hads_next_acceptance`. RC3, 0.1 i 0.2 mají vlastní identitu
 a data a nepřepisují se. Existující cíl, symlink nebo opakovanou instalaci
instalátor odmítne. Neprovádí automatický uninstall, migraci databáze ani restart
Core. Selže-li sestavení, zachovej výstup a nezvyšuj oprávnění aplikace.

Pro ruční instalaci ze zdrojů v místních aplikacích:

```sh
ha store reload
ha apps install local_hads_next_acceptance
ha apps start local_hads_next_acceptance
ha apps info local_hads_next_acceptance
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

Bezpečný návrat znamená zastavit pouze `local_hads_next_acceptance`, exportovat
jeho nové spisy a používat nezměněnou předchozí aplikaci. Neodinstaluj ji ani
nesdílej datové svazky. Automatické přepsání instalovaného kandidátu není podporované;
nový testovaný build vyžaduje samostatně ověřený update postup.

## Hranice přejímky

Skutečný LLM, živý HAOS ingress/AppArmor, Supervisor/MA server, fyzické rádio/Zigbee,
RPi 4 / 2 GB a OneDrive restore vyžadují externí přejímku. Verzi nelze označit
za produkčně hotovou. Přesné nativní výsledky a zbývající brány patří do
souhrnného protokolu; staré testy nejsou důkazem nových bajtů kandidátu.
