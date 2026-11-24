# HADS 4.4.0 — WebMCP a ověřitelný webový kontrakt

## Co vydání přidává

HADS 4.4.0 přidává do stránky devět omezených WebMCP Site Tools. Agent může přečíst
aktuální souhrn, seznam a detail incidentu, bezpečný náhled opravného plánu, stav
sběru protokolů a kontrolní snímek UI proti kanonickému backendu. Může také požádat
o rychlou diagnostiku, hluboký audit nebo oficiální kontrolu konfigurace HA.

Aktivní diagnostika se spustí jen po potvrzení ve viditelném dialogu HADS. WebMCP
nemůže schválit nebo spustit opravu, vytvořit opravný batch, provést rollback,
restartovat HA či doplněk nebo spustit shell. Tyto úkony zůstávají v samostatném
kapitánském workflow s povinnou plnou zálohou a rescue balíkem.

## Rozhraní

| Nástroj | Rozsah |
| --- | --- |
| `hads_get_command_center` | Zdraví, fronty a write gate |
| `hads_list_incidents` | Omezený seznam root incidentů |
| `hads_get_incident` | Redigovaný detail a důkazy |
| `hads_get_fix_plan` | Bezpečný náhled, bez tajných potvrzení a payloadu změn |
| `hads_get_log_sources` | Metadata sběru, ne surové logy |
| `hads_get_acceptance_snapshot` | UI × backend křížová kontrola |
| `hads_run_quick_audit` | Potvrzený rychlý sběr |
| `hads_run_deep_audit` | Potvrzený hluboký audit |
| `hads_run_config_check` | Potvrzený `POST /core/check` bez zápisu konfigurace |

Implementace používá `document.modelContext`; kompatibilní `navigator.modelContext`
je pouze fallback. Pokud WebMCP v použitém prohlížeči nebo HA iframe není dostupné,
panel HADS normálně funguje a v záhlaví zobrazí, že Site Tools nejsou podporované.

## Instalace a návrat

Instalátor nejprve požádá Supervisor o plnou zálohu, ověří její metadata a teprve
potom instaluje nebo aktualizuje lokální add-on. Stará databáze se zachová a nová
tabulka `site_tool_runs` vznikne migrací. Při problému lze obnovit plnou zálohu nebo
znovu nainstalovat uložený balíček 4.3.0; rozpracovaná oprava se po restartu sama
nespustí.

Po instalaci otevřete HADS a zkontrolujte:

1. záhlaví uvádí 4.4.0;
2. běžné načtení pěti stránek funguje;
3. stav WebMCP uvádí `připraveno · 9/9`, pokud jej daný browser/Ingress podporuje;
4. schválené opravy se nadále řídí pouze spodním tlačítkem HADS a povinnou zálohou.

## Co bylo ověřeno před zabalením

- kompilace všech Python modulů a kontrola syntaxe JavaScriptu;
- 79 lokálních Python regresních testů;
- Node kontraktní test všech devíti nástrojů, zákaz mutačních nástrojů, viditelné
  potvrzení diagnostiky, HTTP požadavek a UI × backend snapshot;
- kontrola instalačního payloadu, hashů a povinných souborů.

Toto není potvrzení funkčnosti v konkrétním HAOS. Kompletní reálný browser test se
provede jako druhý úkol až po instalaci podle [akceptačního scénáře](ACCEPTANCE_TEST_4.4.0.md).

