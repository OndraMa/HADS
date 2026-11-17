# HADS Next 1.0.0-rc7 — vyšetřování konkrétních entit a ZHA Toolkit

Tento kandidát navazuje nálezy Watchmanu na aktuální stav, registr a dostupnou pasivní ZHA diagnostiku.
Není to plně dokončený autonomní opravář HAOS. Obecné Zigbee/registry opravy stále nejsou podporované.

## Bezpečné stažení a aktualizace z RC6

Na přihlášeném GitHubu otevři vydání `hads-next-1.0.0-rc7` a adresář `KE_STAZENI/HADS_Next_1.0.0-rc7`.
Použij **Download raw file** nebo stáhni kompletní ZIP a rozbal ho ve Windows. **Uložit stránku jako**
stáhne HTML/JavaScript GitHubu, nikoli instalátor. Správný `.sh` začíná `#!/usr/bin/env bash`.
Srovnej SHA-256 s manifestem vydání ještě před spuštěním skriptu; při neshodě ho nespouštěj.

Instalátor zkopíruj do `/config` v HAOS a spusť pouze tuto úvodní aktualizaci:

```sh
bash /config/HADS_Next_install_1.0.0-rc7.sh --verify
bash /config/HADS_Next_install_1.0.0-rc7.sh --upgrade-rc6
```

RC6 předem nezastavuj ani neodinstalovávej. Kontroluje se přesný manifest vydaných RC6 zdrojů
`4c8a8559b750013dc86588cac75ef81055d9b0ccd0334bbeeadaefacb8306dab` i jejich obsah.
Nativní Supervisor update požaduje částečnou zálohu a zachová data/stav aplikace. Záloha zdrojů není
obnovitelná záloha celé domácnosti. Nejasný zásah, vlastní změny nebo stav error se neobcházejí.
Čistá nová instalace používá `--install-dev`; starší RC musí projít svými vydanými přechody.
Při chybě nic nemaž a neodinstalovávej. Další diagnostické příkazy HADS od uživatele nevyžaduje.

## Co po instalaci udělá HADS sám

Po ověření vlastníka při pravidelné kontrole:

1. Přečte nativní zdroje a aktuální hlášení Watchmanu; rozpozná jeho `unavail` jako nedostupnost.
2. Konkrétní použitelné odkazy a otevřené ruční případy propojí s registry a stavy Core.
3. Pokud je ZHA Toolkit načtený, zavolá pouze pevné `zha_toolkit.zha_devices` s odpovědí a omezenými poli.
   Nevyvolává soubory, vlastní eventy, RF sken, reconfigure, binding ani změnu sítě.
4. Pro dotčená ZHA zařízení přečte nativní existující seznam ZHA. Selhání Toolkitu nevydá za funkční integraci
   a pokusí se pokračovat podporovanou nativní cestou. Oba zdroje vycházejí z dat ZHA; nejde o dvě nezávislá měření rádia.
5. Rozliší zakázanou entitu, chybějící stav s potvrzeným 404, nedostupnost, unknown a neúspěšné čtení.
   Přečte dostupnou krátkou historii; nic se automaticky nepřejmenovává ani nepovoluje.
6. Ověřená nedostupnost dostane funkční spis navázaný na zařízení; stejný problém se nesmí zdvojit s ručním případem.
   Opakované čtení není další výskyt. Nový výpadek po pozorované dostupnosti se eviduje, ale spis se bez funkční přejímky neuzavírá.

Na hlavní stránce tak nejsou výpadek čtecího API a mezera odběru `zha_event` vydávané za poruchu zařízení.
Dřívější již nepotvrzené diagnostické nálezy jsou ve sbalené historii. Vypnutá AI ani čekání na zdroj není žádost o schválení opravy.
Nabídka hlášení problému zahrnuje i registry a odkazy Watchmanu, včetně entit chybějících v aktuálních stavech.

Ve spisu je konkrétní závěr, poslední čtení, dostupná ZHA data a důvod, proč zatím není oprava ke schválení.
Při nedoložené příčině **není potřeba povolit obecné opravy**. Chybějící vykonavatel není problém, který vyřeší přepínač oprávnění.
ZHA Toolkit má mnohem širší možnosti, ale RC7 je nezpřístupňuje analytikovi jako obecné služby.

## Hermes, AI a staré konektory

Hermes má nový čtecí nástroj pro konkrétní již vyšetřený cíl spisu. Nedostane libovolný service call.
Paměťová rezerva 576 MiB a limity placených volání zůstávají zachované. AI se instalací sama nezapíná.
Převzaté staré adresy/tokeny zůstávají neaktivními soukromými návrhy; nepřenášejí autoritu ani souhlasy.
Další nastavení popisuje [HAMCP_HERMES_CS.md](HAMCP_HERMES_CS.md).

## Neověřené části

Izolované testy nejsou živá přejímka ZHA Toolkitu. Ověřený upstream kontrakt je zdokumentovaný v auditu RC7;
konkrétní instalace může vrátit nekompatibilní odpověď. Tu HADS označí a nepovažuje ji za nulu zařízení nebo úspěch.
Živé připojení dříve poskytnutého MCP při auditu vrátilo HTTP 503; neproběhla diagnostika senzoru v produkci.
Nativní cache ZHA, LQI a RSSI samy nedokazují příčinu. Síťové klíče, zálohy koordinátoru ani libovolné surové odpovědi se neexportují.
Živé fyzické rádio/Zigbee, skutečný placený model, HAOS/OneDrive obnovitelnost a obecné opravy čekají.
