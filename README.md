# HADS Next 1.0.0-rc7 — konkrétní entity a ZHA Toolkit

Vývojová větev: **codex/hads-next-zha-followup** · [PR 18](https://github.com/OndraMa/HADS/pull/18).

- [Instalátor, kompletní ZIP, návody a SHA-256](KE_STAZENI/HADS_Next_1.0.0-rc7/)
- [Aktualizace z RC6 bez odinstalace](hads-next/haos/DOCS.md)
- [Co nastavit a povolit pro ZHA Toolkit](hads-next/docs/ZHA_TOOLKIT_SETUP_CS.md)
- [Podrobný návod HA-MCP a Hermes](hads-next/haos/HAMCP_HERMES_CS.md)
- [Audit sběru, skutečný rozsah a nedokončené části](hads-next/docs/RC7_DELIVERY_CS.md)
- [Přesný protokol balíčku](hads-next/docs/evidence/installation-1.0.0-rc7/ACCEPTANCE.json)

RC7 opravuje rozpoznání Watchman `unavail`, automaticky dohledává konkrétní cíle v registru,
aktuálních stavech, dostupné historii a pasivním ZHA/Toolkit seznamu. Chybějící entity zůstávají
v nabídce. Výpadky diagnostiky se nepočítají jako prokázané funkční poruchy domácnosti.
Čtení nevyžaduje AI klíč ani ruční diagnostické příkazy; Toolkit se nepřipojuje jako další MCP server.

**273 testů na každé architektuře ARM64/AMD64**, skutečný Core a původní izolovaný Hermes se
skriptovaným neplaceným modelem, aktualizace s testovacím Supervisorem a 20 webových pohledů prošly.
Přesný zdroj: `513394ee9e73f54a639113786f7a6ab92b182870`; 62 souborů instalačního payloadu
porovnáno s touto revizí, instalátor je na obou architekturách totožný.

Živý MCP přístup při kontrole vrátil HTTP 503. Živá funkce Toolkitu a příčina selhání senzoru komory
nejsou potvrzené. Obecné Zigbee/registry/statistiky opravy a úplné vlastní konektory
HA-MCP/Hamster/Inspector/HADocs **nejsou dokončené**. Kandidát není plné splnění původního zadání.

---

## Předchozí vydání RC6

# HADS Next 1.0.0-rc6 — oprava sběru pro HAOS

Aktuální vývojová větev: **codex/hads-next-collector-audit** · [PR 17](https://github.com/OndraMa/HADS/pull/17).

- [Instalátor, kompletní ZIP, návody a SHA-256](KE_STAZENI/HADS_Next_1.0.0-rc6/)
- [Přesný postup aktualizace z RC5](hads-next/haos/DOCS.md)
- [Podrobný návod HA-MCP, Hermes, Watchman, Inspector, HADocs a HASK](hads-next/haos/HAMCP_HERMES_CS.md)
- [Posouzení HASS-AI-Orchestrator 0.13.6](hads-next/docs/ORCHESTRATOR_REVIEW_CS.md)
- [Výsledky a nedokončené části](hads-next/docs/RC6_DELIVERY_CS.md)

RC6 opravuje zahazování inventáře kvůli platným názvům aplikací s pomlčkou a čte podrobnosti
existujících hlášení Watchmanu do společného diagnostického spisu. Nativní sběr nepotřebuje AI klíč
ani ruční diagnostické příkazy. Nezapíná zařízení, nepřepisuje konfiguraci a nespouští další AI službu.

**259 testů na každé architektuře ARM64/AMD64**, skutečný Core a původní izolovaný Hermes se
skriptovaným neplaceným modelem, aktualizace s testovacím Supervisorem a 18 webových pohledů prošly.
Přesný zdroj: `6a067f716b1e4870cbb21f08ed44e134800ecdff`; [úplný protokol](hads-next/docs/evidence/installation-1.0.0-rc6/ACCEPTANCE.json).
Živé HAOS a fyzické výsledky čekají. Obecné aktivní MCP konektory a opravné adaptéry Spook/registry/statistiky
**nejsou dokončené**. Kandidát není plné splnění původního zadání.

---

## Předchozí vydání RC5

# HADS Next 1.0.0-rc5 — automatická diagnostika pro HAOS

Aktuální větev: **codex/hads-next-rc5** · [PR 16](https://github.com/OndraMa/HADS/pull/16).

- [Instalátor, kompletní ZIP, návody a kontrolní součty](KE_STAZENI/HADS_Next_1.0.0-rc5/)
- [Instalace a aktualizace z RC4 bez uninstallu](hads-next/haos/DOCS.md)
- [Co přesně obsahují HA, MCP a Hermes integrace](hads-next/haos/INTEGRATIONS_CS.md)
- [Souhrn oprav, testů a zbývajících přejímek](hads-next/docs/RC5_DELIVERY_CS.md)

RC5 navazuje na automatická nativní čtení RC4. Při nedostatku paměti získá statistiky
Core, Supervisoru a běžících aplikací, uloží důkazy a jednou porovná další měření.
Marketplace/github_web prověří nativní diagnostikou a omezenou veřejnou sondou.
Pro tato čtení nepotřebuje nový doplněk, AI klíč ani diagnostické příkazy uživatele.
Původní Hermes, nativní HA API a Music Assistant MCP klient jsou součástí HADS.
Externí MCP server a poskytovatel modelu vyžadují privátní nastavení.

Stávající běžící Next RC4 se aktualizuje úvodním `--upgrade-rc4`; předem jej
nezastavuj ani neodinstalovávej. Supervisor aktualizuje jen HADS Next s nativní
částečnou zálohou. Data a identita zůstávají. Starý Hermes 2.0.0-rc3, main a
vydané archivy se nepřepisují. Podporované opravy potřebují konkrétní schválení.

AI je výchozí vypnutá. Volitelný malý test má společný trvalý limit 3 požadavky
za klouzavých 24 hodin, nejvýše 512 výstupních tokenů na požadavek a žádnou
automatickou placenou frontu. Limit není garantovaný dolarový strop.
Paměťová rezerva 576 MiB zůstává povinná pro spuštění Hermesu.

Prošlo 249 izolovaných testů na každé nativní architektuře ARM64/AMD64,
skutečný Core a původní Hermes se skriptovaným modelem a 18 zobrazení rozhraní.
Živá HAOS aktualizace a obnovitelnost, skutečný LLM a fyzické přístroje čekají
na přejímku. Jde o instalační kandidát, ne o produkčně ověřené vydání.

RC5 přidává stránku **Doplňky a ověření**, opakované nativní kontroly devíti
zdrojů a soukromý **neaktivní návrh** přenosu vybraných spojení z původního Hermes
RC3. Plné funkční adaptéry HA-MCP/Hamster/HADocs/Inspector ani jejich obecné
zápisy tím nejsou hotové. [Rozsah a omezení](hads-next/docs/RC5_DELIVERY_CS.md).
HASK je podle zadání vynechaný.
