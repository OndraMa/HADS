# Jediný souhrnný výsledek HADS Next

Pracovní datum: 10. 11. 2026 (Europe/Prague). Nový
[PR 7](https://github.com/OndraMa/HADS/pull/7), větev
`codex/hads-next-final-delivery`, výchozí ověřená revize `5f06e67`.
RC3, main, 0.1.0-dev1 a 0.2.0-dev1 zůstávají zachované.

## Co už prošlo celým řetězcem

Nativní AMD64 i ARM64 [běh 42822632534](https://github.com/OndraMa/HADS/actions/runs/42822632534)
prošel skutečný Core 2026.11.0 a původní připnutý Hermes. Skutečný odběr změn
stavů zachytil nesplněnou odezvu testovací automatizace; vznikl trvalý spis.
Hermes si šesti nástroji načetl nové důkazy přes broker, jeho návrh prošel
nezávislým validátorem a stávajícím plánovačem. Ověřený vlastník schválil přesný
plán přes controller HTTP rozhraní. Původní executor provedl CAS vlastní reference.
Skutečné spuštění automatizace, kontext cíle a sledovací interval vedly k českému
reportu „Vyřešeno a ověřeno“. Samostatně schválený rollback obnovil přesnou
referenci a další skutečné funkční selhání znovu otevřelo původní spis.

Model byl skriptovaný; **skutečný agent, Core, SQLite, HTTP/WebSocket, CAS,
spouštění automatizace a funkční čas byly reálné**. Není to fyzický HAOS test.
Finální zdroje navíc testují automatické spuštění Hermes po odděleném opt-in,
dva souběžné CAS klienty a idempotentní serverový replay. Jejich konečný běh
se zaznamená do trvalého `evidence/installation-1.0.0-rc1/ACCEPTANCE.json`.
Počet offline regresí je 155; sám není důkaz funkčnosti produktu.

## Přesný rozsah opravy

Běžné Core config API nemá atomické compare-and-swap. HADS je neobchází ani
nepřepisuje obecné automatizace. Volitelná podporovaná custom integrace vlastní
jedinou referenci, kterou nativní virtuální testovací automatizace čte šablonou.
Server mění pouze tuto referenci, atomicky kontroluje revizi i původní hodnotu
a trvale eviduje operation ID. Tím se nepřepisují změny jiného editoru v ostatní
konfiguraci. Není to oprava libovolného přímého entity odkazu v automations.yaml.

Katalog vyžaduje zvláštní povolení, čitelný companion, ověřeného vlastníka,
přesný neměnný plán, nový souhlas, snapshot a odběr funkčních událostí. AI nemá
HA klíč, sockety, shell, obecný Python/MCP proxy nebo zapisovací nástroj.
Zápis bez souhlasu, cizí uživatel, CSRF, změněný/stará revize a opakované provedení
se odmítají. Nejasný výsledek zastaví další zápisy stejného cíle; nic se tiše
neopakuje. Návrat reference má samostatné schválení a nepředstírá obnovu HAOS.

## Stav funkcí

Každý řádek má právě jeden stav; ověřený rozsah je v posledním sloupci.

| Funkce | Stav | Důkaz / přesná hranice |
|---|---|---|
| Aktuální kód a modulární propojení | IMPLEMENTOVÁNO A OVĚŘENO | PR 7, nativní integrovaný Core scénář |
| Kontinuální funkční monitory | IMPLEMENTOVÁNO A OVĚŘENO | skutečný state_changed odběr, deadline, mezery, perzistentní pravidla, 4 typy podmínek; max. 32 vybraných pravidel |
| Automatická AI fronta po opt-in | IMPLEMENTOVÁNO A OVĚŘENO | zvláštní souhlas + provider opt-in, stávající persistentní rozpočty; finální nativní běh |
| Původní Hermes a broker | IMPLEMENTOVÁNO A OVĚŘENO | nezměněný upstream pin d923a5e, skutečné nové Core čtení; úsudek modelu se tím nedokládá |
| Specializované role a předání | IMPLEMENTOVÁNO A OVĚŘENO | původní nativní smyčka s role handoff, vynucený katalog a citace |
| Aktuální stavy, registry, automation traces, historie, Action history, Health/Repairs/logy Core | IMPLEMENTOVÁNO A OVĚŘENO | skutečný Core 2026.11.0, pozitivní a negativní API kontrakty |
| Supervisor/OS/aplikace a jejich metriky/logy | IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST | zapojené původní adaptéry a omezená kontrola po 5 minutách; živý Supervisor chybí |
| Music Assistant FastMCP | IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST | přesně omezené upstream kontrakty, ne skutečný server/stream |
| ZHA softwarový řetězec | IMPLEMENTOVÁNO A OVĚŘENO | skutečný Core event → automation trace → virtuální cíl; žádný fyzický stisk |
| Fyzické rádio/Zigbee/ESPHome a dlouhodobé sledování | IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST | podmínky a podporovaná čtení; připojení a konkrétní fyzický výsledek musí doložit operátor |
| Trvalé spisy, nové výskyty, deduplikace | IMPLEMENTOVÁNO A OVĚŘENO | nativní znovuotevření stejného spisu, DB restart, regresní testy |
| Veřejný výzkum a historie pro Hermes | IMPLEMENTOVÁNO A OVĚŘENO | původní role/broker, skutečné veřejné API účtenky; souhlas, cache, denní rozpočet |
| Konkrétní CAS executor vlastní virtuální reference | IMPLEMENTOVÁNO A OVĚŘENO | skutečná companion integrace + původní RepairEngine, nativní Core |
| Jednotlačítkové schválení | IMPLEMENTOVÁNO A OVĚŘENO | ověřená HA admin identita/owner/CSRF → původní ApprovalAuthority → přesný zápis |
| Funkční verifier a rollback reference | IMPLEMENTOVÁNO A OVĚŘENO | skutečný kontext, čas, čekání, report; další selhání znovu otevře spis |
| Český responzivní Command Center | IMPLEMENTOVÁNO A OVĚŘENO | Chromium desktop a mobil 390 px, 5 stránek bez horizontálního přetečení; skutečné čekající plány a reporty |
| Jedenáct kontrol prvního spuštění | IMPLEMENTOVÁNO A OVĚŘENO | rozlišují nastavení od skutečného čtení/odpovědi; chybějící záloha se nezelená |
| Import/export historických Next spisů | IMPLEMENTOVÁNO A OVĚŘENO | kopie schema 1 read-only, nezměněný zdroj, skutečné výskyty, idempotence, žádná platná schválení |
| HAOS instalace, ingress a AppArmor na cílovém stroji | IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST | nový slug zachovává předchozí aplikace; u uživatele není oddělený testovací HAOS |
| Reálný LLM úsudek | NEDOKONČENO – KONKRÉTNÍ BLOKER | není dostupný autorizovaný modelový endpoint; nic placeného se nezapíná |
| Obecný přepis automatizací a další rizikové operace | NEDOKONČENO – KONKRÉTNÍ BLOKER | nativní endpoint nemá CAS; nevytváříme nebezpečný obecný katalog |
| OneDrive/HAOS nezávislý restore | NEDOKONČENO – KONKRÉTNÍ BLOKER | nejsou obnovovací podklady ani izolovaný HAOS; odpovídající zásahy jsou blokované |
| RPi 4 / 2 GB společně s Core/ZHA/MA | IMPLEMENTOVÁNO, ČEKÁ NA ŽIVÝ HAOS TEST | 576 MiB rezerva zachována, 1 worker; nativní ARM64 VM nenahrazuje měření RPi |

## Praktické doporučení

Kandidát je určen k **omezenému živému testování na odděleném HAOS**, nejprve
čtení a monitory, potom vlastní virtuální referenční okruh podle přiloženého
návodu. Není přijatý pro opravy produkční domácnosti. Uživatel dosud testovací
HAOS nemá. Žádný produkční zásah ani placené volání nebylo provedeno.

Základní deterministické funkce nepotřebují AI. Neznámá očekávání se nastavují
pravidlem; HADS netvrdí, že z logů automaticky zná záměr každého zařízení.
Žádná další vývojová verze se nemá označit jako dokončený produkt jen podle
počtu tříd nebo testů. Přejímkový kandidát musí odpovídat testovaným bajtům.
