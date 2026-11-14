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
