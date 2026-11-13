# HADS Next 1.0.0-rc3 — opravný kandidát pro HAOS

Aktuální větev: **codex/hads-next-rc3** · [PR 10](https://github.com/OndraMa/HADS/pull/10).

- [Instalátor, kompletní ZIP, návody a kontrolní součty](KE_STAZENI/HADS_Next_1.0.0-rc3/)
- [Instalace a aktualizace z RC2 bez uninstallu](hads-next/haos/DOCS.md)
- [Co přesně obsahují HA, MCP a Hermes integrace](hads-next/haos/INTEGRATIONS_CS.md)
- [Souhrn oprav a zbývajících přejímek](hads-next/docs/RC3_DELIVERY_CS.md)

RC3 obsahuje opravený přehled a správně rozlišuje samotný stav aplikace od
potvrzeného funkčního problému. Původní Hermes je přímo ve výsledné image;
HA a Music Assistant MCP adaptéry jsou součástí HADS. Externí MCP server a
poskytovatel modelu vyžadují vlastní privátní nastavení, nezapínají se automaticky.

Stávající Next RC2 se aktualizuje explicitním `--upgrade-rc2` při potvrzeném
zastavení aplikace. Data a identita se zachovají. Starý Hermes 2.0.0-rc3, main
ani historické archivy se nepřepisují. První živé ověření ponechá AI a opravy
vypnuté. Jde o kandidát; skutečný model, fyzická zařízení a úplná HAOS přejímka
nejsou dosud označené jako ověřené.
