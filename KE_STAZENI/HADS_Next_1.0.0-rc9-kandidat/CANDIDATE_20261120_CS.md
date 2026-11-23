# HADS Next RC9

Snímek z instalace potvrzuje RC8 ze zdroje `476587fb9f75`. Záhlaví s identitou sestavení se v této verzi může zalomit přes pevný začátek navigace a zakrýt záložku Domácnost. V RC9 je záhlaví součástí stejného posuvného sloupce jako navigace.

| Oblast | Stav |
|---|---|
| Navigace | Domácnost je pod záhlavím. Na nízkém desktopovém okně se lze posunout i k poslední záložce. |
| HA-MCP | Z předaného živého výpisu je doložené připojení a katalog. RC9 samostatně ověřuje čtení stavu jedné známé entity. Živé ověření tohoto testu čeká. |
| Hamster 0.2.2 | Při chybě schématu volitelného příkazu se zachovají dostupné funkce. RC9 ověřuje jedno povolené čtení registru. Výsledek z konkrétní domácnosti ještě není ověřený. |
| ZHA Toolkit | Předaný živý výpis potvrzuje čtení cache verze 1.2.6. RC9 přikládá ke spisu jen odpovídající zařízení z registru. |
| Watchman, Inspector, HADocs | Předané výpisy obsahují diagnostické odpovědi. U HADocs není doložený čas posledního úspěšného skenu. |
| Hermes | Lokální runtime vyžaduje rezervu 576 MiB. Živé patnáctiminutové měření na cílovém RPi a ověření skutečného modelu čekají. |
| Rizikové opravy | Přijímací integrace ověřuje podepsaný doklad. Živě ověřená nezávislá obnova OneDrive stále chybí. |
| Širší opravné operace | Obecné změny statistik, registrů, skriptů a Zigbee parametrů čekají na vlastní adaptéry a funkční přejímku. |

Přesný instalační postup je v přiloženém `NAVOD_CS.md`. RC8 aktualizuj příkazem `--upgrade` na existující aplikaci. Instalátor ověřuje původ zdrojů a používá stejnou identitu aplikace pro přístup k její databázi a historii.

Pro Hamster ponech jeho lokální adresu zakončenou `/api/hamster_mcp` a token uložený v soukromém formuláři HADS. Po aktualizaci otevři **Nástroje servisního týmu → hamster_mcp**. Karta ukáže výsledek spojení, katalogu a čtení registru. Hamster je volitelný.

Živou přejímku zaznamenej podle [přejímacího protokolu](ORCHESTRATION_LIVE_ACCEPTANCE_CS.md). Výsledky prohlížeče, testovacího MCP serveru a kontejnerové přejímky mají vlastní protokoly.
