# HADS Next – výsledek kritické kontroly RC1

Nový [PR 8](https://github.com/OndraMa/HADS/pull/8) vychází přesně z
`d2c8ad5da09287d256c324d6e4434bf92499d018` na samostatné větvi
`codex/hads-next-practical-acceptance`. RC1, RC3, main a vydané archivy se nemění.

## Rozdíl proti RC1

Přibyla skutečná úzce omezená operace `core.enable_lighting_automation`, která
používá nativní Core `automation.turn_on`. Není závislá na virtuální HADS referenci
ani companion integraci. Vlastník nejprve potvrdí očekávané zapnutí skutečné
jednoduché světelné automatizace. Úplnou konfiguraci, spouštěč, cíl a aktuální
stav čte a validuje nezávislý planner. Oprava má neměnný plán, ověřený snapshot,
čerstvou admin identitu, CSRF, expiraci, jednorázové schválení, persistentní záměr
a zákaz opakování po nejasném výsledku. Funkční verifier vyžaduje skutečný kontext,
změnu světla, souvislý interval a následné potvrzení vlastníka.

**Nativní stavová služba nemá CAS.** Nezapisuje konfiguraci. Omezení na jeden
explicitní bezpečný světelný cíl, výlučná práce potvrzená vlastníkem a poslední
čtení omezují riziko, ale netvoří atomickou transakci proti jinému editoru.
Budoucí triggery mohou rozsvítit světlo. Návrat jen deaktivuje budoucí triggery;
neslibuje vrácení již vykonané fyzické akce. Obecné služby, konfigurace, reloady,
systémové změny a rizikové zásahy bez obnovitelné zálohy zůstávají zakázané.

Systémová vrstva po pěti minutách automaticky čte omezené strukturované nativní
zdroje. Bez individuálních pravidel zachytí explicitní selhání aplikace,
Repairs, chybu System Health, čerstvé opakované chyby Recorderu, neplatné přímé
reference a neočekávané vypnutí vlastníkem vybraného světelného cíle. Přidává
paměť, disk, verzi před závadou, diagnostické mezery ZHA a volitelný MA health.
Stejná data nevytvářejí další výskyty ani nekonečné modelové analýzy. Po zvláštním
souhlasu zahajují významné funkční incidenty původní Hermes; bez AI sběr pokračuje.

Přibyla persistentní živá přejímka s dvanácti samostatnými kroky a anonymizovaným
exportem. Modelový komunikační test má vlastní souhlas, sdílený denní rozpočet,
jediný persistentní pokus a zákaz tichého opakování. Změna poskytovatele ruší
platnost starého zeleného výsledku. Jeho úspěch není důkazem úsudku modelu.

## Opravené chyby RC1

- Odezva se nezjišťuje na nesprávné hraně spouštěče a při již splněném cíli.
- Opakované triggery neodkládají původní deadline donekonečna.
- Výpadek heartbeat ruší neprokázanou kontinuitu.
- Pozdější přechod mimo očekávaný stav ruší dřívější pokrytí funkční opravy.
- Předčasné fyzické potvrzení nebo potvrzení před mezerou neuzavře nový pokus.
- Konfigurační ID automatizace se načítá z nativní entity; nemusí být stejné jako
  její zobrazované `entity_id`. Cizí automatizace se nesmí číst mimo rozsah spisu.
- Restart obnoví odběr i pro nativní světelné cíle bez zapnutého CAS katalogu.
- Historie plánů se filtruje podle spisu před aplikací limitu; zamítnutý plán
  nezůstává na hlavní stránce jako čekající rozhodnutí.
- Normální počáteční `unknown` u dosud nestisknutého `input_button` se neplete
  s nedostupným tlačítkem. `unavailable` stále blokuje zásah.

## Přesná technická hranice

| Oblast | Provedená implementace / ověření | Co potřebuje skutečný provoz |
|---|---|---|
| Praktická nativní oprava | Core 2026.11.0, nezávislý planner, vlastník, pevná služba, skutečný trigger, čas a report; virtuální světlo bez HADS reference | bezpečný testovací okruh a potvrzení skutečné lampy |
| Hermes | originální pin `d923a5e`, vícekroková smyčka a role s nativním Core | úsudek skutečného kompatibilního LLM |
| Systémové nálezy | bounded native adaptéry, persistentní epizody a deduplikace | skutečný Supervisor, logy aplikací a dlouhodobá dostupnost |
| Core/Supervisor restarty | výpadek API není prohlášen za restart | verifikovaný konkrétní záznam restartu; info API samotné neposkytuje počet restartů |
| Recorder | strukturovaný Health, je-li vystaven; čerstvá opakovaná konkrétní hlášení | stav a příčina skutečné DB; nevykonává se libovolný SQL dotaz |
| Disk/paměť | `/host/info` v GiB, proc/cgroup, worker peak, limity a Core read latency | společná zátěž RPi/Core/ZHA/MA a odezva oproti vlastnímu baseline |
| MA, ZHA | zachované pevné read-only kontrakty a journal; nepovolené playback testy nejsou použity | skutečný FastMCP, stream a fyzické Zigbee zařízení |
| Spook | jeho nativní Repairs nálezy bez dalšího privilegovaného konektoru | dostupnost dané instalace |
| Watchman | přímé reference vlastními nativními čteními; úplná shoda Watchman reportu se netvrdí | jeho konkrétní podporovaný strukturovaný výstup, je-li instalován |
| HA-MCP | není povinná další aplikace; srovnatelná dostupná data čte nativní broker | žádný obecný MCP write proxy není povolen |
| OneDrive/HAOS restore | ochrany zachovány; příslušné rizikové operace blokované | nezávislá obnova na odděleném HAOS |

Skutečná domácnost nebyla měněna. Živý HAOS není dostupný a v Cloud prostředí
není nakonfigurovaný autorizovaný modelový endpoint. Fyzická přejímka a reálný
LLM test proto čekají. Přesný postup je v [návodu](../haos/DOCS.md) a
[přejímkovém protokolu](haos-acceptance.md). Tato hranice není nahrazena výsledkem
ARM64 VM ani počtem unit testů.

## Reprodukce

`python scripts/check.py` provede offline regrese a negativní bezpečnostní testy.
`python scripts/practical_browser.py` provede oddělenou Chromium přejímku
(Playwright a Chromium jsou vývojové závislosti, ne součást HAOS instalace).
Workflow `hads-next-investigation.yml` testuje nativní AMD64 a ARM64: skutečný
Core s původním Hermes a skriptovaným HTTPS modelem, přesný instalační payload,
produkční image bez testovacího Core, memory admission 768/512 MiB a restart.

Finální revize, hashe a výsledky kandidáta jsou v
`evidence/installation-1.0.0-rc2/ACCEPTANCE.json`. Kandidát je přijatý pouze tehdy,
pokud tento protokol obsahuje úspěch obou architektur a shodu všech payload souborů.

## Finální dostupný kandidát – 12. 11. 2026

Obě nativní architektury prošly [během 43278689080](https://github.com/OndraMa/HADS/actions/runs/43278689080).
Testovaný runtime commit: `5fb55e1974e2fd25edde54d4446dcf28ea5d8933`.
Na každé architektuře prošlo 168 regresních testů, původní Hermes se skutečným
Core a praktickou nativní operací, produkční image bez testovacího Core,
paměťová brána a restart. Chromium ověřilo deset pohledů na desktopu a mobilu.

Instalátor obou architektur má shodný SHA-256:
`e09c1d0a4b7b10775ba2e5ef238a68390316793dadb355074798e3d28e9e7a29`.
Všechny payload soubory byly porovnány s přesným zdrojovým commitem.
Protokoly jsou trvale uložené v `evidence/installation-1.0.0-rc2/`.

Uživatel nemá testovací HAOS. [Postup prvního živého ověření](LIVE_WITHOUT_TEST_HAOS_CS.md)
proto začíná pouze čtením, s vypnutými opravami a AI. Tento kandidát není
přijatý pro obecné produkční opravy; reálný HAOS, fyzická zařízení, RPi a
úsudek běžného LLM zůstávají čekající. Žádná placená volání nebyla provedena.
