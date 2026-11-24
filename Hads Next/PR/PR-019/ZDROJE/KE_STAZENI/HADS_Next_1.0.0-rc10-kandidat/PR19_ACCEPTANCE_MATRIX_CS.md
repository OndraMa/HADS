# Přejímací matice aktuální vývojové větve PR #19

Stav HOTOVO znamená dokončenou zdrojovou změnu s izolovaným důkazem. Živá
přejímka má vlastní řádky. Výchozí revize této sady změn je `6a6c18a`.
Staré instalační archivy a měření se vztahují ke svým původním revizím.

| Požadavek | Stav | Implementace | Důkaz a mez |
|---|---|---|---|
| A. Odstranění Hamsteru a migrace | HOTOVO | [Konektory](../src/hads_next/tool_connections.py), [katalog](../src/hads_next/tool_registry.py), [starý import](../src/hads_next/legacy_connectors.py) | [Test migrace](../tests/test_tool_orchestration.py) načte starý soubor, vyřadí Hamster, zachová HA-MCP a blokuje opětovnou aktivaci. |
| B. HA-MCP pro cílenou diagnostiku | NEOVĚŘENO V HAOS | [MCP transport](../src/hads_next/connector_transport.py), [adaptér](../src/hads_next/tool_orchestration.py), [orchestrace](../src/hads_next/orchestration_cases.py) | [Izolovaný MCP test](../tests/test_tool_orchestration.py) ověří skutečné HTTP volání, cílený registr a historii. Mechanismus katalogu váže schéma, diagnostika rozlišuje fáze spojení a Core zůstává samostatným zdrojem. |
| C. Podporované schválené opravy | NEOVĚŘENO V HAOS | [Broker](../src/hads_next/approved_tools.py), [místní schémata](../src/hads_next/connector_policy.py) | [Testy](../tests/test_tool_orchestration.py) vykonají povolení senzoru přes HA-MCP, povolení entity přes Spook a změnu jedné světelné reference. Ověření vyžaduje funkční podnět a skutečná pozorování. |
| C. Ostatní běžné zásahy | NEDOKONČENO | [Katalog operací](../src/hads_next/connector_policy.py), [broker](../src/hads_next/approved_tools.py) | Obecné úpravy YAML, smazání entit, změny statistik, Zigbee reporting, binding a přepárování nemají schválený vykonavatel s ověřením a návratem. |
| D. Obnovitelnost záloh | NEDOKONČENO | [Příjem dokladů](../src/hads_next/restore_connection.py), [kontrakt](RESTORE_VERIFIER_CONTRACT.md) | Podpis, cíl, rozsah a čas kontroluje [TLS test](../tests/test_candidate_completion.py). Rozhraní produkčního HABS ani nezávislou službu s reálnou obnovou se nepodařilo ověřit. Krytí opravy nelze odvodit z denního uploadu. |
| E. Zpráva vlastníka spustí čtení a přinese odpověď | HOTOVO | [Konverzace](../src/hads_next/case_dialogue.py), [fronta čtení](../src/hads_next/orchestration_cases.py) | [Izolovaný MCP test](../tests/test_tool_orchestration.py) dokládá cílená čtení a trvalou odpověď, nulový počet modelových volání a odmítnutí cizího cíle. |
| E. Vyšetření původním Hermesem a výsledek po schválení | NEOVĚŘENO V HAOS | [Hermes](../src/hads_next/hermes_runtime.py), [laboratorní scénář](../lab/approved_orchestration_probe.py) | Laboratorní scénář používá reálný izolovaný runtime, skriptované odpovědi modelu a neprodukční automatizaci mimo vlastní HADS companion. Koncový průchod na živém HAOS se skutečným modelem čeká. |
| F. Přejímka skutečných integrací a Pi 4/2 GB | NEOVĚŘENO V HAOS | [Akceptační protokol](ORCHESTRATION_LIVE_ACCEPTANCE_CS.md), [měření](../src/hads_next/resource_study.py), [přijetí workeru](../src/hads_next/investigation_service.py) | Nové měření na cílovém stroji neproběhlo. ARM64 kontejner nenahrazuje Pi. Rezerva 576 MiB zůstává. Oddělený runtime na jiném stroji s oddělenými oprávněními zatím není otestovaný. |
| Finální instalátor, SHA-256 a nezávislá kontrola | NEDOKONČENO | [CI laboratoř](../../.github/workflows/hads-next-orchestration.yml), [přejímka](ORCHESTRATION_LIVE_ACCEPTANCE_CS.md) | Finální balíček vznikne až po uzavření zbývajících implementačních bodů, kontrole a ověření cílové revize. Případné dočasné CI balíčky slouží pouze testu sestavení. |

Před schválením živého opravného testu musí být k dispozici oddělený HAOS,
nezávislý ověřovatel, skutečně obnovená záloha pro vybraný cíl a model s výslovným
rozpočtem. Doklad z laboratorního klíče se do produkce nepřenáší. Pokud FastMCP
u Music Assistantu není k dispozici, HADS použije historii Core a dostupné logy.
Čtení FastMCP v takové instalaci zůstane označené jako neověřené.

Upstream kontrakty pro čtecí a zapisovací funkce HA-MCP jsou v
[Tool Exploreru HA-MCP](https://homeassistant-ai.github.io/ha-mcp/tools/).
