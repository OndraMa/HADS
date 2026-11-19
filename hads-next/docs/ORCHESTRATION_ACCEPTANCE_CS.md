> **Aktualizace 19. 11. 2026:** následující text uchovává přejímku předchozí zdrojové revize PR #19 z 17. 11. Aktuální instalační kandidát, nová integrační část a přesné zbývající meze jsou v [CANDIDATE_20261119_CS.md](CANDIDATE_20261119_CS.md). Starší protokoly se nevydávají za test nové revize.

# Orchestrace po RC7 — implementace a přejímka

Výchozí revize: `c1372a392f213ab995c9848ae9721b3732967268` z větve `codex/hads-next-zha-followup`.
Vývoj pokračuje v `codex/hads-next-orchestration`. Nevzniká nový projekt, identita aplikace ani nové vydání RC.
Databáze a dřívější ochrany zůstávají; nové tabulky mají vlastní verzi. Vydané archivy se nemění.

## Rozhodnutí a provozní propojení

`Application.check_sources → ToolOrchestration → ToolRegistry → Diagnostic Tool Broker → IncidentStore`
a `Hermes → hads_list_tools / hads_get_tool_schema / hads_diagnostic_tool / hads_propose_tool_repair`.
Původní NousResearch runtime a měření placených volání se nenahrazují. Výsledky providerů nejsou instrukce ani autorita.

Zapisovací cesta je `přesný RepairPlan → ověřený vlastník + CSRF → ApprovalAuthority → ApprovedRepairBroker
→ vybraný provider → zpětné čtení → funkční pozorování → FunctionalVerifier → trvalý český report`.
Protokolový timeout po zápisu má nejistý výsledek, nikoli automatický retry nebo rollback. HADS omezeně
znovu přečte stav a vlastníku nabídne přijetí doloženého výsledku k novému funkčnímu testu bez dalšího zápisu.
Nejistota blokuje další zápisy tohoto brokeru i z jiného spisu. Návrat je nový plán
s novým souhlasem a kontrolou, že mezitím nevznikla cizí změna. Není to obnova celé HAOS instalace.

MCP discovery je dynamické, stránkované a omezené. HA-MCP tool-search je rozbalen přes skutečný
`ha_search_tools(tools=[…])` a pevné proxy; obecné proxy nejsou zpřístupněné modelu. Hamster má textové
schéma; automaticky se povolují jen přesně ověřené nativní příkazy. Neznámé funkce zůstávají v katalogu
jako blokované bez ohledu na `readOnlyHint`. Parametry ověřuje skutečný JSON Schema validátor,
bez vzdálených referencí. Identita serveru i jeho verze jsou označené jako hlášené serverem, ne jako atestace binárky.

## Konkrétní katalog oprav

- HA-MCP: jediná přímá světelná akce se stavovým triggerem, bez skriptů/šablon a dalších účinků;
  změna jedné reference. Náhradu musí doložit pozorovaná stejná `unique_id`/zařízení před a po změně ID,
  nikoli podobnost názvu. Použije skutečný `config_hash`, `config`, `entity_id`, `wait: true`, `run_actions: false`.
- Spook: přesná změna `disabled_by` jediné entity přes `homeassistant.enable_entity`; `disable_entity`
  slouží pouze jako zvlášť schvalovaný návrat předchozího povolení, nikoli potlačení nálezu.
  Záměr vlastníka je součástí konkrétního schválení. Zakázaná entita není automaticky závada.
- Oba adaptéry vyžadují podpis nezávislého důkazu skutečné obnovy OneDrive zálohy pokrývající původní cíl,
  kontrolu původního stavu, aktuálního schématu/verze/identity a výlučnou práci s cílem.
- Spook statistiky, ID změny, ZHA reporting/binding/attribute writes jsou evidované, ale jejich obecné vykonání
  zůstává blokované. Samotné přeposlání do služby by nedodalo spolehlivý rollback ani funkční verifikaci.
  Čtení statistických metadat/hodinové historie a konkrétní ruční alternativy jsou dostupné.
- ZHA Toolkit: navíc pevně omezené čtení standardních atributů se známým IEEE cílem, jediným pokusem,
  bez obecných parametrů, exportů, eventů, `attr_write`, změny sítě nebo klíčových clusterů.

Důkaz obnovitelnosti používá odděleně spravovaný veřejný Ed25519 klíč `backup-verifier.pub` a podepsaný
`restore-attestation.json` v soukromých datech. HADS podpis nevydává a model nemůže měnit klíč.
Je to kontrakt pro nezávislého ověřovatele, **nikoli nově ověřená integrace HABS/OneDrive**.
Dokud takový skutečný důkaz a důvěryhodný ověřovatel nejsou nastavené, tyto rizikové zápisy jsou blokované.
Izolované testy mají výslovně testovací klíč/verifier; nepřenášejí jeho důvěru do domácnosti.

## Provozní matice providerů

| Provider | Implementovaný programový kontrakt a společný výsledek | Nastavení / alternativa | Hranice |
|---|---|---|---|
| Core | Dosavadní REST/WS stavy, registry, historie, traces, Action history, Repairs; nově Recorder metadata/hodinová historie a manifesty | Stávající Supervisor token v kontroleru | Čas a dostupnost konkrétního čtení, žádné domýšlení UI API |
| Supervisor | Dosavadní info/stats/aplikace/logy + vlastní a Core logy | Stávající oprávnění aplikace | Stav procesu není funkční test |
| HAOS | Dosavadní `/os/info`; systémové prostředky přes podporovaný Supervisor | Bez privilegovaného shellu | Container není živý HAOS |
| Watchman | Vlastní senzorové reporty a konkrétní odkazy včetně `unavail`; navazující čtení | Existující integrace | Existující report není nový scan; ESPHome není HA reference |
| Spook | Společné Repairs včetně jeho kontrol; skutečný katalog služeb; dva oddělené opravné adaptéry | Nativní HA, manifest/get pro verzi | Doména Repairs nemusí být spook; nulový počet neprokazuje zdraví |
| HA-MCP | initialize, stránkované tools/list, tool-search plná schémata, stav/zařízení/automatizace/health; schválená konkrétní změna konfigurace | Privátní jednorázové připojení, výběrová aktivace starého návrhu; nativní fallback | Obecné proxy/shell/YAML Python nejsou modelové funkce |
| Nativní MCP | Autentizovaný Streamable HTTP katalog a GetLiveContext; případně vlastní explicitní URL | Supervisor přístup nebo privátní konfigurace | Assist exposure není plná administrativní diagnostika; nepropojuje se klient sám do sebe |
| Hamster MCP | initialize/tools/list, skutečné schema/call pro omezené nativní registry/stavy/Repairs/logy | Privátní endpoint; nativní fallback | Textové schéma není JSON Schema a obecný call se neexportuje |
| ZHA Toolkit | Doložené cache zha_devices + omezený attr_read přes službu s odpovědí | Již aktivní integrace | RF čtení je označené, nesmí spouštět zápisy/exporty |
| ZHA | Registry, nativní zařízení a existující journal zha_event | Nativní WS | LQI/last_seen a chybějící fyzický stisk nejsou důkaz příčiny |
| Automation Inspector | Skutečné GET /api/v1/status a /api/v1/inspection schema 2; související závislosti rozšiřují čtecí spis | Ověřený Supervisor hostname/ingress port 1234 nebo jednorázový privátní původ | Stale/failed report se odmítá, proces se nevydává za report |
| HADocs | Skutečné GET /api/status a /api/summary; health/incidents/recommendations | Ověřený interní port 8099 nebo privátní původ | Existující report po restartu má výslovně neověřenou čerstvost; žádný automatický HASK ani přepis overrides |
| HAGHS | Vlastní strukturované atributy (piliře, kandidáti, unhealthy integrace, Repairs, doporučení) | Nativní registry+stavy+manifest | Skóre není příčina ani nezávislé měření |
| Entity Availability | Vlastní entities/devices/count/per-device data a skutečné source timestamps | Nativní registry+stavy+manifest | Čtení senzorů není nový scan |
| Music Assistant | Dosavadní pevný FastMCP adaptér player/health/events/buffer/logs v katalogu, volí se podle cíle spisu | Existující privátní nastavení a mapping | Žádné nevyžádané přehrávání/stop/hlasitost |

## Praktické důkazy a původ zdrojů

`tests/test_tool_orchestration.py` používá skutečné lokální HTTP/MCP přenosy s anonymizovaným kontraktním serverem:
report Inspectoru a HADocs → více čtení → přesná HA-MCP konfigurace → schválení → jeden zápis → skutečné
kontrolerové pozorování trigger/context/stavu → fyzické potvrzení → souvislé okno → český report.
Samostatně testuje Spook registr, schéma/provider/target drift, falešný a expirovaný souhlas, obnovení procesu,
ztracenou odpověď po skutečném testovacím zápisu, podpis zálohy a neautorizované alternativní cesty.
Další scénáře ověřují automatické spuštění/obnovení event transportu, znovuotevření při funkčním selhání,
inverzní zápis až po novém souhlasu a zákaz použití znovu obsazeného identifikátoru.
**Server není skutečný HA-MCP/Spook runtime ani fyzický HAOS.**

Nativní kontejnerové CI navíc spouští původní Hermes se skutečným Core a nově pinned upstream Inspector builder
proti skutečnému Core WS. Hermes vybere report Inspectoru ze společného katalogu a pokračuje konfigurací,
trace a stavem Core. Model je lokální skriptovaný endpoint; nejde o důkaz diagnostického úsudku reálného LLM.
Oba nativní průchody revize `b34f68bcef944e48f71fd0858ace17deb4ce8952` prošly v
[CI 44156311112](https://github.com/OndraMa/HADS/actions/runs/44156311112): 304 testů na každé
architektuře a celý kontejnerový protokol. [Přesné protokoly](evidence/orchestration/RESULTS.json)
obsahují zdrojovou revizi, otisky, skutečný rozsah a zbývající omezení.
Samostatný `lab/approved_orchestration_probe.py` provede celý řetězec s původním Hermesem,
jeho návrhem, skutečnou HTTP schvalovací hranicí, jedním providerovým zápisem a funkčním reportem.
Poskytovatelé a pozorování jsou v této dodatečné zkoušce explicitní anonymizované doubles;
nepředstírá běh nainstalovaného HA-MCP, Spooku ani fyzického zařízení.

Ověřené upstream revize (17. 11. 2026):

- [Inspector aa24bd4](https://github.com/ITSpecialist111/Automation-Inspector/tree/aa24bd4485b5f74fd4547d84dc5fb1045bc766fa): main.py, dependency_map.py, settings.py, service.py.
- [HADocs c8dc8ff](https://github.com/SirBlondieDK/HADocs/tree/c8dc8ff2fd5157941a3749148b4326592ee065c5): web/app.py, knowledge/exporter.py.
- [HA-MCP 3accc57](https://github.com/homeassistant-ai/ha-mcp/tree/3accc57e25ee0243e138dc2a1b2d29db6d1d9a52): tools_config_automations.py, tools_registry.py, tools_search.py, tools_system.py, transforms/categorized_search.py.
- [Spook c2ed5ce](https://github.com/frenck/spook/tree/c2ed5ced29568be25a970206a188abd5e82fa9ed): enable_entity.py, update_entity_id.py, recorder/import_statistics.py.
- [Hamster fc7bbba](https://github.com/altendky/hamster-mcp/tree/fc7bbbae3b38c7ebf0acbf0d68e7adcfb12fe383): tools.py, hass_group.py, component/http.py.
- [Toolkit 7920582](https://github.com/mdeweerd/zha-toolkit/tree/79205820d52bd4797c7dacf6b1184380ba7ca613): services.yaml, zcl_attr.py; cache kontrakt z RC7.
- [HAGHS 5608a60](https://github.com/HA-Pulse/home-assistant-global-health-score/tree/5608a60c319837c2e70a4b76c63b77a3b064f30b): sensor.py.
- [Entity Availability ea6af1e](https://github.com/italo-lombardi/Home-Assistant-EntityAvailability/tree/ea6af1ed3812660f43e38e45b4db41eda1f3774b): sensor.py.
- [Core 2026.11.1](https://github.com/home-assistant/core/tree/2026.11.1): websocket_api/commands.py, recorder/websocket_api.py, zha/websocket_api.py, homeassistant/llm.py.

Původní RC3 nebyl aktivovaný ani změněný; přebírají se pouze vybrané privátní adresy/tokeny po jednorázovém
potvrzení vlastníkem. Staré souhlasy, automatické placené fronty ani neomezené vykonávání se nepřebírají.

## Živá přejímka — co ještě musí skutečně proběhnout

1. Zabezpečené připojení HAOS v prostředí, bez tokenu v chatu. Dřívější MCP pokus vrátil HTTP 503;
   z tohoto vývoje nebyl proveden žádný produkční zápis ani placené volání.
2. V přehledu nástrojů ověřit konkrétní odpovědi všech skutečně připojených providerů, jejich verzi,
   původ a stáří reportu. Nenastavený endpoint nebo stale report musí být viditelný jako mezera.
3. Na skutečném senzoru komory HADS sám propojí Watchman/registry/historii/ZHA/Toolkit a relevantní dependencies.
   Nepožaduje terminál ani kopírování logů. Případný fyzický test smí požadovat až pro konkrétní neznámou funkční podmínku.
4. Reálný model nejprve jen výslovně povoleným malým testem; zachovat rezervu 576 MiB a stávající limity.
   Vyčerpaný rozpočet nesmí ztratit spis ani spustit další placenou frontu.
5. Před rizikovou opravou doložit skutečného nezávislého ověřovatele/obnovu OneDrive. Testovací podpis ani upload není přejímka.
6. Schválit jedinou přesnou podporovanou změnu s výlučnou prací s cílem; ověřit nový funkční výsledek,
   ne pouze úspěch služby. Rollback schválit zvlášť a ověřit jeho rozsah.
7. Zapsat výsledky jako live, odděleně od offline/container. Teprve po kontrole celé matice zvažovat další RC.
