# HADS Next 1.0.0-rc6 — oprava inventáře a podrobnosti Watchmanu

Jde o instalační kandidát. Rozlišuje přítomnost integrace/aplikace, stav procesu,
přečtené vlastní entity a dosud neověřenou funkci doplňku. Aktualizace nepředstírá
plnou funkčnost všech externích konektorů.

## Přechod z běžícího Next RC5

V přihlášeném GitHubu otevři vydání `hads-next-1.0.0-rc6`, adresář
`KE_STAZENI/HADS_Next_1.0.0-rc6`. Stáhni instalační .sh přes **Download raw file**
do /config. Nespouští se ve Windows.

```sh
bash /config/HADS_Next_install_1.0.0-rc6.sh --upgrade-rc5
```

RC5 předem nezastavuj ani neodinstalovávej. Skript ověří přesné vydané RC5 zdroje,
uchová jejich zálohu a požádá Supervisor o aktualizaci pouze HADS Next s nativní
částečnou zálohou. Soukromá data a identita zůstávají. Zachová stav started/stopped.
Stav error, vlastní změny zdrojů nebo nedokončený zásah se neobcházejí.
Při chybě zachovej hlášku a marker; nic nemaž a nespouštěj další instalátor souběžně.

Kontrola bez instalace: stejný skript s `--verify`.
Nová samostatná instalace: `--install-dev`. Přímý přechod z RC2 nebo RC3 tento
kandidát nepodporuje. Původní Hermes 2.0.0-rc3 se nemění. Záloha zdrojů ani
částečná záloha aplikace nedokazují obnovitelnost HAOS/OneDrive.

## Automatická kontrola

Po ověřeném přihlášení vlastníka HADS spustí nativní kontrolu a opakuje ji při
pravidelné kontrole. Stránka **Doplňky a ověření** ukáže Spook, HA-MCP,
Automation Inspector, HADocs, Entity Availability, Hamster MCP, HAGHS, Watchman
a Music Assistant. HASK není automaticky aktivovaný; jeho experimentální možnosti popisuje přiložený návod.

Čtení využívá existující API Core a Supervisoru, entity registry a Repairs.
Neodhaduje URL podle názvu, nestahuje stránky UI, nevyvolává Watchman report,
nespouští aplikace a neposílá modelové požadavky. Čte také známou entitu
sensor.system_ha_global_health_score; to samo neprokazuje verzi její integrace.

Nativní stav entity není funkční přejímka doplňku. Čas odpovědi není čas skenu.
MCP autentizace, katalog a konkrétní diagnostická volání se bez jejich provedení
nezobrazí jako ověřené. Nula nálezů neprokazuje zdravý zdroj.
Přítomnost odvozujeme z aktuální komponenty nebo aplikace; starý záznam registru
sám přítomnost nepotvrzuje. Nenalezení není důkaz odinstalování.

## Převzetí nastavení původního Hermes RC3

Na stránce **Doplňky a ověření** použij volitelně **Načíst návrh připojení
z původního Hermes RC3**. HADS provede jediný pevný GET informací aplikace
local_hads4, ověří její identitu a verzi 2.0.0-rc3 a vybere jen adresy a tokeny
pěti známých konektorů. Starou aplikaci nemusíš spouštět. Pokud tam není nebo
nemá použitelné explicitní nastavení, přenos se odmítne.

Ukládá se jen soukromý neaktivní návrh v /data/hads-next/legacy-connectors.pending.json
s oprávněním 0600. Zobrazuje se pouze seznam konektorů, nikoli URL nebo tokeny.
Nepřenášejí se souhlasy, AI klíče/náklady, oprávnění, historický stav „funguje“
ani staré chyby. Původní data se nemění.

Tento návrh ani v RC6 ještě neaktivuje HA-MCP, Hamster, HADocs nebo Inspector
adaptér. Jejich úplné funkční připojení je další nedokončená část. Pro známý JSON
export existuje soukromý formulář; nepatří do chatu ani GitHubu. Výpis historického
přehledu není export připojovacích údajů. Importují se pouze pole z ověřené RC3
konfigurace, ne její celý kód. Úspěšný přenos nedokazuje aktuální funkčnost.

## AI a opravy

Původní Hermes zůstává v image. AI je výchozí vypnutá; nativní kontroly nepotřebují
API klíč. Paměťová rezerva 576 MiB zůstává povinná před spuštěním workeru.
Volitelný malý test má 3 požadavky za klouzavých 24 hodin, 48 000 bajtů vstupu
a 512 výstupních tokenů na požadavek, bez automatické placené fronty.
Jde o technické limity, ne garantovaný dolarový strop.

Opravný katalog nadále zahrnuje vlastní testovací CAS referenci a zvlášť povolenou
jednoduchou světelnou aktivaci. Obecné zápisy Spook/HA-MCP, registrů, YAML
a statistik nejsou tímto vydáním implementované. Každá podporovaná oprava potřebuje
konkrétní souhlas a funkční ověření. Požadavky na ověřenou zálohu se nemění.
Živá HAOS přejímka, skutečný model a fyzické rádio/Zigbee čekají na ověření.

## Nové konkrétní opravy sběru

Platné Supervisor slugy s pomlčkou, tečkou a velkými písmeny nevyřadí ostatní aplikace. Neplatné položky jsou vynechané s viditelným omezením. HADS čte existující podrobnosti Watchmanu podle identity v registru, včetně zdrojových souborů a řádků. Nevyvolává report ani neukrývá nálezy. Jeden společný diagnostický spis zachovává důkazy bez umělých opakování a bez automatického uzavření při poklesu počtu. Starší nepodporovaná identita nebo neúplné atributy zůstávají neověřené.

Úplný návod připojení: [HAMCP_HERMES_CS.md](HAMCP_HERMES_CS.md). Přehled skutečně chybějících adaptérů a posouzení Orchestratoru je v dodané dokumentaci; instalace RC6 je automaticky nedoplní.
