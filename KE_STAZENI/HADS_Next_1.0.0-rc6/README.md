# HADS Next 1.0.0-rc6 — instalační kandidát

- [Stáhnout instalační soubor pro HAOS](HADS_Next_install_1.0.0-rc6.sh) — použij **Download raw file**, ne uložit webovou stránku.
- [Kompletní ZIP: instalátor, zdroje, návody, testy a výsledky](HADS_Next_1.0.0-rc6-komplet.zip)
- [Instalace a aktualizace z RC5](HADS_Next_1.0.0-rc6-navod-CS.md)
- [Podrobný návod HA-MCP a Hermes](HAMCP_HERMES_CS.md)
- [Posouzení HASS-AI-Orchestrator 0.13.6](ORCHESTRATOR_REVIEW_CS.md)
- [Ověřené a nedokončené části](VYSLEDKY_A_OMEZENI_CS.md)
- [Kontrolní součty všech balíčků a dokumentace](HADS_Next_1.0.0-rc6-SHA256SUMS.txt)

Opravuje inventář aplikací a čte podrobnosti existujícího Watchman hlášení. Nerozhoduje automaticky o povolení zakázaných entit,
nezaměňuje ESPHome akce za dokázanou chybu a neuzavírá incident jen po zmizení nálezu.

## Aktualizace z běžící RC5

Ulož instalátor do `/config`. Toto je jednorázový instalační krok, nikoli ruční vyšetřování domácnosti.

```sh
bash /config/HADS_Next_install_1.0.0-rc6.sh --verify
bash /config/HADS_Next_install_1.0.0-rc6.sh --upgrade-rc5
```

RC5 předem nezastavuj ani neodinstalovávej. Pro čistou novou instalaci existuje `--install-dev`;
pokud už existují zdroje nebo starší verze, skript je nepřepíše. Pro RC4 nejprve použij již vydaný přechod RC4 → RC5.
Při stavu error nebo markeru nejisté operace nic nemaž; bezpečnostní brány se neobcházejí.
Původní Hermes 2.0.0-rc3 ani ostatní aplikace se nemění.

## Testy a hranice

259 testů na každé nativní architektuře ARM64/AMD64; skutečný Core a původní izolovaný Hermes se skriptovaným lokálním HTTPS modelem.
18 desktopových/mobilních webových pohledů. Nativní upgrade používá skutečný vydaný RC5 zdroj a testovací Supervisor CLI.
[CI ARM64/AMD64](https://github.com/OndraMa/HADS/actions/runs/43638589294) · [Webové CI](https://github.com/OndraMa/HADS/actions/runs/43638592113).

Zdrojový commit: `6a067f716b1e4870cbb21f08ed44e134800ecdff`.
59 souborů instalovatelného payloadu bylo porovnáno se zdroji, obě architektury vytvořily shodné bajty.
Kompletní ZIP byl sestaven dvakrát shodně; obsahuje 302 položek včetně manifestu.
Instalátor SHA-256: `2a619874cecfc24ce3decca83646388983c26ad3bed56b19c48e5851ecde5b95`.
Kompletní ZIP SHA-256: `5e169bb03ac4f8d6ac739f611f9a748ef82193a464721798c91d07701bf7c7b5`.

**Nejde o plně dokončený HADS.** Aktivní obecné MCP konektory a zapisovací adaptéry Spook/registry/statistiky/YAML ještě nejsou hotové.
HASK ani Orchestrator se automaticky neinstalují nebo neaktivují. AI zůstává vypnutá, paměťová rezerva 576 MiB se nemění.
Živá HAOS přejímka, fyzické rádio/Zigbee, skutečný placený LLM a nezávislá obnovitelnost záloh nejsou potvrzené.
