# Audit HADS 4.6.0 a opravné vydání 4.6.1
Datum: 7. 9. 2026

## Výsledek

HADS 4.6.0 obsahuje použitelnou infrastrukturu: sběr logů, externí nálezy, root-cases, konverzaci, allowlist oprav, oddělené schválení a spuštění, zálohovací brány a protokol výsledků. Není ale dokončeným autonomním diagnostikem pro všechny poruchy HAOS. Vyšší dostupná RAM/CPU sama chybějící vyšetřovací postupy nenahradí.

Prošel jsem 14 identifikovaných dostupných souvisejících konverzací projektu HA, celkem 213 položek turns vrácených nástrojem, a aktuální kontext tohoto úkolu. Stránkování každé z těchto konverzací došlo do konce. Seznam je v AUDIT_CONVERSATION_INDEX.json. Obsah poskytuje omezené exporty zpráv; nepředstírám přístup k nezpřístupněným či všem archivovaným chatům a všem jejich přílohám. Dřívější tvrzení asistentů beru jako tvrzení k ověření, ne jako důkaz funkčnosti.

Porovnání se týká lokálního zdroje work/v460/src a instalačního balíku 4.6.0. Na běžící HAOS jsem se v tomto úkolu nepřipojil. Nová kopie je work/v461/src; původní 4.6.0 zůstává zachována.

## Jak má HADS fungovat podle tvých požadavků

1. Sám shromažďovat důkazy: Core, Supervisor, host, systémové služby, konkrétní doplňky, jejich reporty, registry, konfigurace, entity a traces.
2. Vyšetřovat skutečnou funkci: tlačítko → událost → trigger → podmínky → akce → zařízení. Selhané vypnutí světla má větší význam než osamocený infrastrukturní traceback.
3. Oddělovat důkaz, hypotézu a potvrzenou příčinu. Zdravá HTTP lampička s MQTT chybou není automaticky rozbitá lampička. Chybějící trace není důkaz úspěchu.
4. Slučovat stejné defekty při zachování původu důkazů. Nevracet vlastní reporty do ingestion jako nové chyby. Historie před upgradem není současný výpadek.
5. Bez obtěžování kapitána doplnit dostupné informace. Kapitánovi předat připravené rozhodnutí, nebo přesně vysvětlit, který údaj HADS nemůže zjistit.
6. Nabídnout čitelnou opravu: konkrétní cíl, před/po, důvod, riziko, ověření a rollback. Přijetí závěru není schválení opravy.
7. Zachovat zamítnutí, ignorování, ruční řešení, chat a audit historie i přes restart.
8. Zapsat až po schválení přesného plánu a samostatném spuštění. Před zápisem ověřit aktuální stav, konflikty a nové zálohy. Samotná existence připojeného OneDrivu není důkaz zálohy.
9. Ohlásit výsledek každé dávky: co bylo změněno, která záloha patří k dávce, co selhalo a zda je oprava potvrzena, nebo stále sledována.
10. Přednostně pracovat lokálně. Volitelná AI smí vyhledávat a navrhovat, nikoli obejít bezpečnostní brány.

## Konkrétní nálezy a změny

| Oblast | Zjištěno v 4.6.0 | 4.6.1 |
| --- | --- | --- |
| Průběžná kontrola | Rychlý scan nespouštěl opravný plánovač; čekalo se na deep audit. | Periodický scan obnoví externí nálezy a spustí lokální plánování. Nová volba periodic_investigation. |
| Automatické sledování | Plánovač vynechával všechny watching, i ty bez rozhodnutí kapitána. | Automaticky sledované případy jsou způsobilé k vyšetření; přijaté závěry se nepřepisují. |
| Fronta | Opakovaně první omezený počet případů; riziko hladovění konce seznamu. | Nejprve dosud nevyšetřené, pak nejdéle nevyšetřované; 30min odstup, explicitní vyšetření jej obchází. |
| Původ rozhodnutí | Starší přijetí mohlo ovlivnit stav po pozdějším znovuvyšetření. | Rozhoduje poslední kapitánský záznam, ne libovolné historické přijetí. |
| Vazba důkazů | Shodný název doplňku připojoval nesouvisející nálezy. | Při existujících source_ref se vyžaduje jejich shoda; jinak přesný identifikátor, nikdy jen provider. Konzervativní vazba může část souvisejících symptomů nepropojit, ale nevytváří neadresné opravy. |
| Selector v YAML | Hledání any/each/all napříč objektem ignorovalo konkrétní cestu poskytovatele. | Přesná omezená JSONPath + shoda staré hodnoty. Bez přesné cesty se oprava nepřipraví. |
| Automatizační traces | Jen soubor .storage/trace.saved_traces; navíc se hledalo entity_id místo interního ID. | Aktuální trace/list a trace/get, max. 3 poslední běhy pro max. 3 rozpoznané automatizace v plánování. Ověření interního ID; historický fallback je označený. Nic se nespouští. |
| Spook bez nálezů | Bez entity/služby/Repairs položky mohl být považován za nepřítomný. | Použije se i seznam právě načtených komponent HA. Nula Repairs není nedostupný Spook. |
| Codex Terminal Pro | Zbylá update entita mohla dokazovat instalaci. | Instalaci dokazuje inventář doplňků, ne update entita. Stále není čitelným diagnostickým konektorem. |
| Staré výsledky zdrojů | Část aktuálních příznaků přežívala expiraci. | Expiruje i connector_ready, data_used a potvrzení aktuální přítomnosti. Historie zůstává dohledatelná. |
| Viditelnost práce | Chyběl souhrn posledního průběžného plánování. | Panel ukáže čas, vyšetřené případy, nové plány, selhání a zbytek fronty posledního cyklu. Nejde o živý progress bar. |
| Test sběru logů | UI mohlo ohlásit dokončení po obnově jediné řádky zdroje. | Identifikovaný běh s konečným complete/partial/failed; cizí nebo ztracený běh je unknown, ne úspěch. |
| Ověření vydání | Build/validator měly napevno napsáno „94 passed“. | Build testy skutečně spouští a při chybě skončí; počet a výsledek jsou převzaté z test runneru a navázané na hash payloadu. |

Aktuální traces jsou zvolené podle posledních uložených běhů, nikoli záruka zachycení libovolného včerejšího stisku. Pro historickou rekonstrukci je nezbytná dostupná retenční historie a čas události.

## Diagnostické zdroje: co opravdu poskytuje implementace

| Zdroj | Implementované využití | Hranice ověření |
| --- | --- | --- |
| HA Core / Supervisor / host / systémové logy / add-on logy | Ingestion, stav sběru, časový kontext, interní metriky a evidence. | Skutečné oprávnění a úplnost na tvém HAOS nebyly živě testovány. |
| Spook | Repairs, identifikátory, rozlišení osiřelých statistik od poškození DB, nově načtený component. | Nula aktivních Repairs nedokazuje, že všechny funkce domácnosti fungují. |
| Watchman | Strukturovaná service_response, TXT fallback, reference a provenance; preferuje se jedna reprezentace reportu. | Ne všechny TXT řádky obsahují jednoznačného vlastníka automatizace. |
| Automation Inspector | Strukturované problémy, vlastník, doporučení, path/current/replacement, dostupný trace. | Přesný payload konkrétní nainstalované verze je nutné porovnat živě. |
| HADocs | JSON nálezy a doporučení; oddělení health od nálezového obsahu. | Obecný parser není záruka zpracování všech detailních UI funkcí. |
| Entity Availability | Offline/stale/battery/signal nálezy dle dostupných atributů; sloučení napříč skupinami. | Nečinnost neznamená bezpečnost odstranění entity. |
| HAGHS | Hledání dle platformy v registru, skóre hygieny a doporučující příznaky. | Hygiena konfigurace se nesmí zaměnit za dostupnost celého HA. |
| HA-MCP | Zjištění čitelného rozhraní a omezené případové dotazy dle dostupných nástrojů. | Instalace a handshake nedokazují použití všech funkcí. |
| Hamster MCP | Search → schema/explain → omezená čtecí volání. | Není povolen univerzální vzdálený zapisovací nástroj. |
| Codex Terminal Pro / Home Assistant Digest | Codex není funkční konektor; Digest není v diagnostickém katalogu. | Neoznačovat za mozky analýzy. |

Tento audit není nové kompletní upstream ověření všech verzí všech konektorů. Rozlišuje přítomný kód, offline smluvní testy a dosud neprovedený živý test.

## Co stále není hotovo — bez slibů navíc

- Úplná časová rekonstrukce dálkový ovladač → událost → automatizace → fyzický výsledek napříč všemi integracemi. Nové traces jsou důkaz, ne univerzální diagnostická interpretace.
- Automatické vyšetření Meross transportu podle konkrétních diagnostik zařízení, historie a ovládacího testu. Obecné rady a dostupné stavy nejsou totéž jako provedený test.
- Některé priorizační větve jsou stále založené na textu hlášky. Konkrétně audio/event-stream pravidla je nutné doplnit o skutečný dopad; plošné potlačení opakované funkční poruchy by bylo chybné.
- Úplná kauzální deduplikace napříč různými poskytovateli není prokázaná. Tato verze opravuje nebezpečně široké přiřazování důkazů, ne všechny možné duplicity.
- Lokální deterministické plánování pokrývá omezené, ověřitelné změny. Nezíská všeobecné AI uvažování tím, že mu přidáme RAM.
- Důležitá mez AI: současné striktní výstupní schéma poskytuje popisné proposed_actions, nikoli přesné repair_actions s allowlist typem a hodnotami před/po. Obecný návrh AI se tedy sám nestává vykonatelnou opravou. Pro další rozšíření je potřeba ověřovací překladač návrhu na konkrétní plán, ne pouze vložit API klíč nebo povolit zápis modelu.
- Automatické opravy všech souborů, adresářů či libovolné databáze nejsou podporované. Používá se allowlist; SQLite Recorder má vlastní omezený postup. „Can't find backup folder“ může označovat chybějící obsah archivu, ne adresář, který se má bezmyšlenkovitě vytvořit.
- Každou schválenou dávku musí potvrdit následné ověření, ne pouze HTTP úspěch. Živý restore test OneDrive/HA záloh nebyl proveden.
- Nové traces mohou obsahovat velké a citlivé hodnoty; používá se existující maskování. Před zapnutím externí AI je nutné zkontrolovat redakci na reálném vzorku.
- Denní report i protokol oprav mají existující kód, ale jejich doručení a obsah na tvé instanci není v tomto auditu potvrzen.

## Provozní nastavení

periodic_investigation=true a automatic_repair_planner=true: automatické lokální vyšetřování při rychlém scanu. automatic_planner_limit omezuje počet případů za cyklus; běhy se nepřekrývají přes scan lock. Doporučení není zvýšit počet procesů bez měření, ale nejdřív sledovat délku cyklu, paměť, timeouty a počet dokončených případů.

Placené AI vyšetřování zůstává oddělené opt-in: openai_enabled + vlastní klíč + ai_background_research. Výchozí limity v balíku jsou 20 volání denně, 6 na případ, nejvýše 4000 výstupních tokenů a 3 nástrojová kola. To nejsou cenové záruky ani pevný počet celkových tokenů na incident. Klíč nebyl nastaven ani použit v tomto úkolu.

## Ověření a navazující akceptace

Původní 4.6.0: skutečný běh 94 testů, 93 úspěšných a jeden neúspěšný (zastaralý očekávaný text sekce). Dřívější tvrzení „94 testů prošlo“ nebylo doložené a tento běh je opravuje.

Autoritativní konečný výsledek nové verze je ve vygenerovaném HADS4_4.6.1-verification.json. Testy jsou offline, s blokovaným síťovým přístupem v test fixtures. Není to důkaz funkčnosti nainstalovaných doplňků, skutečné obnovy zálohy ani fyzického ovládání světel.

Před běžným použitím projít ACCEPTANCE_TEST_4.6.1.md. Neinstaloval jsem aktualizaci do HA ani neprováděl žádnou systémovou opravu.

## Primární zdroje k novému ověření rozhraní

- [HA REST API: právě načtené komponenty](https://developers.home-assistant.io/docs/api/rest/)
- [HA Core: trace WebSocket API](https://github.com/home-assistant/core/blob/dev/homeassistant/components/trace/websocket_api.py)
- [HA Core: ukládání traces při zastavení](https://github.com/home-assistant/core/blob/dev/homeassistant/components/trace/__init__.py)

Upstream dev zdroje ověřeny 7. 9. 2026; nenahrazují zjištění verze a schopností tvé instance.
