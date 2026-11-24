# Aktuální kandidát 4.7.0-rc3

Aktuální změny a otevřené bezpečnostní/provozní brány: [RELEASE_4.7.0-rc3.md](RELEASE_4.7.0-rc3.md). Upload ACK nestačí. Bez pozitivního funkčního testu není oprava potvrzena. Níže zachovaný starší obsah nesmí rozšiřovat tuto smlouvu.

# HADS 4 Command Center – architektura a původ funkcí

> Historie návrhu do RC5, nikoli protokol ověření 4.5.0. Aktuální hranice funkcí
> a testů jsou v RELEASE_4.5.0.md a VERIFICATION_MATRIX.md. Nový incident_workflow.py
> spravuje trvalé konverzace, uživatelské volby, souběh úloh a měření API spotřeby.

HADS 4 je samostatný Home Assistant add-on. Není slepencem cizích repozitářů a neinstaluje jejich kód. Převádí jejich nejlepší ověřené principy do jednoho lokálního systému s jednotnou databází, životním cyklem případů a bezpečnostním modelem kapitán / první důstojník.

## Šest spolupracujících částí

1. **Observer** – trvalé read-only spojení s Home Assistant WebSocket API. Zachycuje významné stavové přechody, změny registrů a životní cyklus HA. Při výpadku dál funguje polling a sníží se pouze Diagnostic Confidence.
2. **Detective** – deduplikace, korelace, incidenty, Change Intelligence a graf `host → Supervisor → add-on/integrace → config entry → zařízení → entita → YAML/dashboard`.
3. **Engineer** – allowlist Repair Engine, náhled, diff, blast radius, kapitánská fráze, partial backup, lokální snapshot, Core check, sledování a rollback.
4. **Health Engine** – odděluje Current Health, Reliability, Diagnostic Confidence a HADS Health. Zobrazuje jedenáct subsystémů.
5. **Memory** – ukládá otisk, příčinu, příznaky, prostředí, verze, opravu, výsledek, dobu zotavení, regresi a znovuotevření.
6. **AI Officer** – používá OpenAI Responses function tools nad lokálními důkazy a volitelný web. Vrací hypotézy s pravděpodobností, důkazy pro/proti, nejistotu, test, návrh opravy, ověření a rollback. Jeho nástroje jsou read-only.

## First Officer workflow

1. Deep Analysis vytvoří kanonické root cases a Repair Queue.
2. Automatic Repair Planner načte důkazy případu, výsledky Tool Adapter Layer a známou historii. Přijme pouze strukturované allowlist akce, ověří jejich náhled přes Repair Engine a vytvoří stav `pending`.
3. Kapitán vybere `approve`, `reject`, `manual` nebo `needs_information`. `approve` pouze změní stav na `approved`.
4. Batch Planner při společném spuštění plánů sestaví závislosti, rebazuje sekvenční YAML změny, odhalí konflikty a vytvoří konečné pořadí.
5. HADS vytvoří Rescue Package a uploadne jej. Logický Repair write gate se odemkne pouze po nezávislém potvrzení přesného vzdáleného souboru.
6. Repair Engine provede allowlist akce. Selhání zastaví zbytek dávky a použije existující rollback hranice.
7. Post-batch Deep Analysis porovná health a množiny root cases před a po dávce.

## Tool Adapter Layer

`tool_adapters.py` objeví runtime inventář, entity, Repairs, služby a reporty skutečně nainstalovaných nástrojů. Stav `available` znamená nalezenou instalaci; `active` vyžaduje použitelné runtime rozhraní. Adaptér nesmí vyrábět výsledky jen podle názvu integrace.

| Adaptér | Konzumovaná runtime evidence |
|---|---|
| HA-MCP | služby/senzory integrace a strukturované HA Repairs |
| HAGHS | skutečná health entita 0–100 a její atributy; samostatná konfigurační hygiena |
| HADocs | nakonfigurovaný čtecí JSON endpoint s root causes a doporučeními |
| Hamster MCP | nakonfigurovaný Streamable HTTP endpoint a filtrované read-only MCP nástroje |
| Spook | HA Repairs a související runtime entity |
| Watchman | služba reportu, existující reporty a křížová kontrola registru/služeb |
| Automation Inspector | nakonfigurovaný read-only inspection JSON endpoint |
| Entity Availability | přesné entity a atributy dostupnosti, MTBF/MTTR, signálu a baterie |
| Native HADS | explicitní fallback, když externí runtime neposkytne použitelný důkaz |

Každý použitý důkaz se ukládá s názvem adaptéru a zdrojem. To umožňuje v UI rozlišit nainstalovaný nástroj bez runtime, aktivní adaptér a nativní fallback.

## Funkční inspirace a runtime integrace

| Zdroj | Co HADS 4 přebírá jako princip | Implementace v HADS 4 |
|---|---|---|
| HA-MCP a HA-MCP integration | široké strukturované nástroje pro HA a in-process použití AI | read-only Tool Adapter a interní function tools nad jednou lokální evidence vrstvou; bez obecného zápisového nástroje |
| HADocs | evidence-first analýza, kořenová příčina, dopad závislostí | Detective, dependency graph, blast radius, důkazy pro/proti |
| HAGHS | srozumitelné lokální skóre 0–100 a transparentní doporučení | aktivní HAGHS adaptér zobrazí samostatnou konfigurační hygienu; provozní Current Health zůstává nativní časové skóre HADS |
| předchozí HADS | logy, diagnostické reporty, historie a zkušenosti z předchozích dnů | import HADS 2/3, recurrence, incidents, knowledge base, denní report |
| Codex Terminal Pro | preflight, přesný diff, test po změně a dohledatelná změna | Repair Plan, hash souboru, backup, Core check, auditní stopa; volný terminál není převzat |
| Hamster MCP | hluboký diagnostický přístup, HA Repairs a automation traces | runtime adaptér, AI tools pro živý stav, Repairs, traces, logové důkazy a systémový kontext |
| Watchman | statické odkazy na chybějící entity/služby | runtime adaptér pro reporty, YAML audit a statické reference |
| Spook | nativní Repairs a kontrola dashboard odkazů | runtime Repairs adaptér a Lovelace reference v grafu |
| Automation Inspector | read-only audit automatizací, závislostí a traces | YAML reference, graf spotřebitelů, trace context |
| EntityAvailability | přesné sledování dostupnosti a zotavení | Observer stavy ACTIVE → VERIFYING → RESOLVED |

## Bezpečnostní hranice

- Observer, Detective, Memory a AI tools pouze čtou nebo zapisují do interní databáze HADS.
- AI Officer nemá shell, `eval`, libovolný HA service call ani přímé vykonání opravy.
- Engineer provádí pouze explicitně povolené typy akcí a pouze po přesné kapitánské frázi.
- Režim `autopilot` automatizuje sběr, korelaci a ověřování; neobchází schválení změn.
- Když nejsou důkazy, správný výstup je `NEVÍM` a návrh nejmenšího testu, ne domyšlená příčina.

## Ověřené zdroje

- HA-MCP: https://github.com/homeassistant-ai/ha-mcp
- HA-MCP integration: https://github.com/homeassistant-ai/ha-mcp-integration
- HADocs: https://github.com/SirBlondieDK/HADocs
- HAGHS: https://github.com/HA-Pulse/home-assistant-global-health-score
- Codex Terminal Pro: https://github.com/jgassens/codex-terminal-pro
- Hamster MCP: https://github.com/altendky/hamster-mcp
- Watchman: https://github.com/dummylabs/thewatchman
- Spook Repairs: https://spook.boo/repairs/
- Home Assistant WebSocket API: https://developers.home-assistant.io/docs/api/websocket/
- OpenAI function calling: https://developers.openai.com/api/docs/guides/function-calling
