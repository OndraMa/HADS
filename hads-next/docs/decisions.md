# M0 – rozhodnutí, bezpečnost a pořadí přejímky

ADR-001 až ADR-005 zachycují počáteční M0. Pro stávající HAOS aplikaci po RC7
je doplňuje ADR-006 níže; původní popis lokální fixture se nevydává za současný katalog celé aplikace.

## ADR-001: Nový strom a ověřený původ

Rozhodnutí: samostatný Python balík `hads-next`, výchozí revize a SHA jsou
v audit.md a provenance.json. Žádný import monolitického RC3 runtime. Rekonstrukce
RC3 slouží auditu; její 133 souborů se reprodukuje skriptem, nekopíruje do Next.
Migrace nejdříve read-only export; staré souhlasy se nikdy nepřenášejí.

## ADR-002: Pět hranic

| Vrstva | Moduly | Smí | Nesmí |
| --- | --- | --- | --- |
| Observability | observability | Explicitní omezená nativní čtení, stav zdrojů, redakce | Volat služby, obecně proxyovat REST/MCP |
| Incident & Evidence | evidence, diagnostics | Spis v SQLite, dedup, historie, deterministické hypotézy | Vydávat podobnost za příčinu |
| Hermes Investigation | investigation + izolovaný worker | Originální upstream, katalog čtecích důkazů, další krok | Schvalovat, vidět HA tokeny, volat vykonavatele |
| Repair & Approval | repair | Přesný neměnný plán, lokální identita, intent journal, jedna fixture operace | Živě měnit HAOS, přijímat obecný kód/path patch |
| Verification & Reporting | verification, reporting | Nový funkční důkaz a český report | Uzavřít případ po HTTP 200/zmizení logu |

Vyměnitelné JSON kontrakty jsou v contracts.md; každá vrstva má vlastní testy.
Databáze není bezpečnostní izolace procesů. Budoucí HAOS verze musí fyzicky oddělit
credential broker, AI worker a vykonavatele samostatnými identitami/mounty.

## ADR-003: Jeden skutečný scénář před katalogem oprav

První operace opraví jediný `action.target.entity_id` v místní fixture automatizace.
Není to adaptér HA automation REST a není to oprava živé domácnosti. Výsledek
vyžaduje zachycené spuštění a odpovídající stav stejného cíle po změně, včetně
sledovacího intervalu. Hodiny a observační transport lze v testu nahradit, ale
výsledek je vždy označen offline. Radio/Zigbee fixtures ověřují klasifikaci;
nekonají playback, volume ani fyzické stisky.

## ADR-004: AI není autorita

Externí obsah, logy i odpovědi modelu jsou nedůvěryhodné. Nativní Hermes používá
jen úzkou čtecí bránu se stropem kroků/objemu; žádné dynamické importy skills,
shell, univerzální MCP, delegace s většími právy, paměť s tajemstvími. Placení
providerové se samovolně nezapínají. Základní diagnostika pokračuje bez AI.
Reálný upstream smoke s bezplatným lokálním test endpointem má samostatnou účtenku;
neprokazuje schopnosti skutečného modelu ani kvalitu příčinného úsudku.

## ADR-005: Schválení a selhání

Souhlas váže konkrétní hash plánu, identitu, expiraci a jeden execution intent.
Změněný cíl vyžaduje nové zjištění a souhlas. Pád po intentu má neznámý výsledek,
nikdy automatické opakování zápisu. Rollback je další explicitně schválený plán.
První lokální autorita je CLI spuštěné vlastníkem na izolovaném pracovním stroji;
řetězec principal není důkaz identity pro HAOS ingress nebo veřejnou HTTP službu.
Takovou službu tento balík nevystavuje.

Riskantní živé operace nejsou registrovány. Budoucí katalog musí zachovat stávající
OneDrive readback a přidat důkaz obnovitelnosti odpovídající rozsahu změny.
Lokální snapshot fixture nenahrazuje zálohu ani obnovu HAOS.

## Hrozby a hranice důkazů

Testujeme neautorizovaný zápis, jiného uživatele, změněný plán/cíl, replay,
expiraci, souběh, pád, podvržené ověření, neplatné cesty/symlinky, únik tokenů
přesměrováním/exception a vykreslení nedůvěryhodných řetězců v HTML.
Kompromitovaný host/root nebo proces vlastníka s přístupem k approval DB může
měnit autoritu; izolovaný vývojový balík tento threat model neřeší. Testovací
endpoint dokazuje protokol a tool loop, nikoli skutečné vyšetření fyzické události.

## Gates

M0 je audit, rešerše, tyto ADR, security model a migration boundary.
M1 vyžaduje verzované úložiště a izolované testy podle zdokumentovaných API.
M2 vyžaduje skutečný originální Hermes s dalším čtením; žádný JSON mock jej nenahradí.
M3/M4 lze nezávisle testovat offline bez aktivace AI či produkčního zápisu, ale
celou vertikálu označit hotovou až po skutečném spojení s ověřeným M2.
M5 zůstává blokováno do ARM64 a autentizované testovací HAOS přejímky. Žádný
instalátor tohoto vývojového stromu nesmí přepsat RC3.

## ADR-006: Orchestrace skutečných providerů ve stávající aplikaci

Datum: 17. 11. 2026. Stav: implementováno ve zdrojovém PR #19, přejímka živého HAOS čeká.
Navazuje na `c1372a392f213ab995c9848ae9721b3732967268`, zachovává instalační identitu,
databázi, původní Hermes a dosavadní samostatné testovací katalogy.

Rozhodnutí:

- `ToolRegistry` eviduje skutečné providery, dostupnost, autentizaci, katalog a jeho schémata,
  původ/verzi, poslední ověřené čtení, rizika a implementovaného vykonavatele.
  Obnovení katalogu neposouvá čas diagnostického čtení. Změna původu/verze/schématu vyžaduje nové ověření.
- `ToolOrchestration` používá upstream reporty a skutečné MCP/native kontrakty. Čtyři společné
  vstupy zachovají limit launcheru 32 nástrojů. Hermes obdrží katalog a výsledky, nikoli transporty a credentials.
- `OrchestrationCases` získává omezené dávky důkazů i bez AI, rozšiřuje doložené závislosti,
  ukládá korelace jako hypotézy a předává návrhy nezávislému plánovači.
- `ApprovedRepairBroker` rekonstruuje jen konkrétně implementované operace: jednu doloženou světelnou
  referenci HA-MCP a opětovné povolení jedné entity přes Spook. Neomezený service caller nevzniká.
  Každý skutečný zápis má samostatný neměnný plán, ověřeného vlastníka, CSRF, expiraci,
  vazbu na poskytovatele/schéma/cíl/původní stav a nezávislý důkaz obnovitelnosti OneDrive.
- `RepairRecovery` po nejasném výsledku pouze čte. Původní příkaz se neopakuje a
  další zápisy brokeru jsou blokované. Přijetí pozorovaného stavu vlastníkem spustí nové funkční ověření,
  žádný další příkaz. Rollback má vlastní nový plán a souhlas.
- Funkční report vyžaduje skutečný novější trigger/context/stav, čerstvé souhlasící čtení,
  požadované potvrzení a souvislé sledování. Rozpor přeruší interval; výsledek HTTP nestačí.

Zvažované alternativy:

- Automaticky zpřístupnit celý MCP katalog: odmítnuto. `readOnlyHint` není bezpečnostní politika,
  obecné proxy/Python/filesystem mohou obejít omezení a některé služby mají vedlejší účinky.
- Znovu implementovat Inspector/HADocs/Watchman: odmítnuto. Použijí se skutečné existující výsledky
  a jejich zdrojový čas, s viditelným fallbackem tam, kde rozhraní není dostupné.
- Přidat druhý plný AI orchestrátor: není podmínkou provozu. Zůstává původní Hermes a jedno
  měření rozpočtu; posouzení HASS-AI-Orchestrator je v samostatném zdrojovém auditu.
- Vydat obecné statistické/Zigbee/registry zápisy jako hotové adaptéry: odmítnuto, dokud nemají
  konkrétní bezpečnou transformaci, odpovídající obnovitelnost, funkční test a inverzní kontrakt.

Důsledky: diagnostické konektory se zapojují do stejného spisu a běží úsporně; bezpečnost nevyžaduje
zakázat všechny opravy. Katalog je však úzký a jednotlivá oprava není plné splnění zadání.
Podpisový kontrakt zálohy není sám propojením skutečného HABS/OneDrive ověřovatele.
Živé HAOS, nainstalované provider procesy, reálný úsudek modelu a RPi prostředky mají oddělenou přejímku.
Do jejího ověření nevzniká další RC ani nový distribuční instalátor.
