# HADS 4.5.0

HADS 4.5.0 je diagnostické a rozhodovací centrum pro Home Assistant OS. Zpracuje
technickou událost jako důkaz, spojí ji s funkčním dopadem, vyšetří příčinu a
teprve z jednoznačného plánu vytvoří opravu, kterou může kapitán samostatně
schválit a spustit. Diagnostický závěr ani tlačítko „dále sledovat“ nejsou oprava.

## Co je nové

- Watchman používá čerstvý strukturovaný výsledek služby a nesmí vytvořit druhý
  případ z jeho TXT kopie. Zachovává entitu/akci, vlastníka, řádek a kontext.
- Automation Inspector zachovává přesného vlastníka, JSON cestu, původní hodnotu
  a návrh náhrady. Nenahraná nebo v trace selhaná automatizace je funkční nález.
- Spook Repairs rozlišuje neplatné reference, osiřelé statistiky a kandidáty k
  úklidu. Osiřelá statistika není automaticky označena za poškozenou databázi.
- Entity Availability slučuje stejnou postiženou entitu napříč skupinami a
  zachovává všechna pozorování. HAGHS se hledá přes registr entit i po přejmenování
  a každý aktivní doporučující příznak má samostatný závěr.
- HA-MCP používá korektní MCP inicializaci. Hamster může provést pouze řízený tok
  search → schema/explain → allowlistované čtení; mutační cesty jsou odmítnuty.
- HADocs rozlišuje health/status od nálezového `/api/summary`. Úspěšné health
  volání tedy samo nevytvoří falešný stav „data použita“.
- Core, Supervisor, host a add-on logy mají stav `complete`, `partial` nebo
  `failed`. Neúplný sběr nesmí potvrdit, že oprava byla úspěšná.
- Jednorázový PulseAudio nebo event-stream výpadek při restartu je vysvětlen jako
  infrastruktura/diagnostické pokrytí. Funkční selhání automatizace a její trace
  mají před touto telemetrií přednost.
- Meross závěr musí porovnat transport s živým stavem zařízení, historií a
  ovládacím testem; samotný MQTT publish error není důkaz nefunkční lampy.
- Volitelný OpenAI výzkum používá Responses API se striktním JSON schématem.
  Výstup je poradní evidence; nikdy přímo neotevře write gate ani nespustí opravu.
- Každá dokončená opravná dávka uloží k incidentu čitelný protokol a vytvoří
  idempotentní oznámení Home Assistantu s výsledkem, rescue zálohou a stavem
  následného ověřování.

## Bezpečnost oprav

Skutečná oprava musí obsahovat přesný cíl, stav před změnou, stav po změně,
riziko, ověření a rollback. Schválení a spuštění jsou dvě různé operace. Před
prvním zápisem musí vzniknout plná HA záloha i rescue balík a musí projít kontrola
konfliktu/hodnoty „before“. HADS neposkytuje AI ani WebMCP libovolný shell, SQL
nebo obecný zápis. Údržba lokální SQLite Recorder databáze je samostatná opt-in
operace s konzistentní kopií a kontrolou databáze; není univerzálním DB editorem.

## Volitelná AI analýza

Bez API klíče běží deterministická lokální diagnostika a konektory. Pro AI je
nutné zapnout `openai_enabled` a vložit vlastní `openai_api_key`. Klíč se neposílá
do prohlížeče a exporty jej maskují. Limity volání a výstupu zůstávají v nastavení.
Online výzkum má používat povolené domény a výstup musí uvést hypotézy, důkazy
pro/proti, chybějící důkaz, další bezpečný test a pouze poradní návrhy akcí.

## Po instalaci

1. Otevřete HADS a spusťte „Ověřit všechna spojení“ a potom Deep Analysis.
2. Na stránce zdrojů ověřte zvlášť instalaci, běh, spojení, poslední úspěch,
   poslední použití dat, počet nálezů a poslední chybu.
3. U Watchmanu nastavte report do `/config/watchman_report.txt`; HADS při
   ručním/deep běhu upřednostní strukturovanou odpověď služby.
4. U HA-MCP/Hamster nastavte endpoint jen pokud autodetekce nenajde skutečný
   runtime. Samotná update entita není konektor.
5. OpenAI nejprve ponechte vypnuté. Zapněte jej až po ověření lokálních zdrojů,
   nastavte denní limit a vyzkoušejte jeden incident bez opravy.
6. Proveďte scénář v `ACCEPTANCE_TEST_4.5.0.md`. Zápisovou část spusťte pouze na
   bezpečném a předem zvoleném testovacím případu.

## Co není tvrzeno

Lokální testy neprokazují kompatibilitu s konkrétními verzemi doplňků ani jejich
aktuálním payloadem na vašem HAOS. HADocs rc5 a soukromá rozhraní doplňků se musí
potvrdit po instalaci. „Připojeno“ znamená ověřené rozhraní, ne bezchybný doplněk.
„0 nálezů“ znamená pouze nulový výstup právě dostupného rozhraní. Skutečnou
funkčnost automatizace či zařízení potvrzuje až cílený test a ověřovací okno.

Home Assistant Digest a Codex Terminal Pro nejsou diagnostické zdroje HADS.
Digest není zahrnutý a Codex Terminal Pro není považován za strojově čitelný
konektor. Produkční kontrola přes browser je druhá fáze po instalaci.
