# HADS Next 1.0.0-rc4 — automatická diagnostika pro HAOS

Aktuální větev: **codex/hads-next-rc4** · [PR 13](https://github.com/OndraMa/HADS/pull/13).

- [Instalátor, kompletní ZIP, návody a kontrolní součty](KE_STAZENI/HADS_Next_1.0.0-rc4/)
- [Instalace a aktualizace z RC3 bez uninstallu](hads-next/haos/DOCS.md)
- [Co přesně obsahují HA, MCP a Hermes integrace](hads-next/haos/INTEGRATIONS_CS.md)
- [Souhrn oprav, testů a zbývajících přejímek](hads-next/docs/RC4_DELIVERY_CS.md)

RC4 samo provádí nativní diagnostická čtení. Při nedostatku paměti získá statistiky
Core, Supervisoru a běžících aplikací, uloží důkazy a jednou porovná další měření.
Marketplace/github_web prověří nativní diagnostikou a omezenou veřejnou sondou.
Pro tato čtení nepotřebuje nový doplněk, AI klíč ani diagnostické příkazy uživatele.
Původní Hermes a HA/Music Assistant MCP adaptéry jsou součástí HADS.
Externí MCP server a poskytovatel modelu vyžadují privátní nastavení.

Stávající běžící Next RC3 se aktualizuje úvodním `--upgrade-rc3`; předem jej
nezastavuj ani neodinstalovávej. Supervisor aktualizuje jen HADS Next s nativní
částečnou zálohou. Data a identita zůstávají. Starý Hermes 2.0.0-rc3, main a
vydané archivy se nepřepisují. Podporované opravy potřebují konkrétní schválení.

AI je výchozí vypnutá. Volitelný malý test má společný trvalý limit 3 požadavky
za klouzavých 24 hodin, nejvýše 512 výstupních tokenů na požadavek a žádnou
automatickou placenou frontu. Limit není garantovaný dolarový strop.
Paměťová rezerva 576 MiB zůstává povinná pro spuštění Hermesu.

224 testů na každé nativní architektuře ARM64/AMD64, skutečný Core, původní
izolovaný Hermes se skriptovaným HTTPS modelem a 16 zobrazení rozhraní prošly.
Živá HAOS aktualizace a obnovitelnost, skutečný LLM a fyzické přístroje čekají
na přejímku. Jde o instalační kandidát, ne o produkčně ověřené vydání.
