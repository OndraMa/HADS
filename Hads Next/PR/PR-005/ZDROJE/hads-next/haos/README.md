# HADS Next 0.1.0-dev1 pro HAOS

Samostatná místní aplikace pro **vývojovou přejímku** vedle HADS Hermes RC3.
Není to hotová náhrada RC3 ani produkčně ověřený Release Candidate.

Balík používá `slug: hads_next_dev`, v Supervisoru tedy
`local_hads_next_dev`. Nezapisuje do konfigurace Home Assistantu a nepřebírá
databázi, čekající plány ani schválení starého HADS. Vlastní spisy ukládá
do `/data/hads-next` uvnitř svého kontejneru.

Instalátor vytváří novou složku v již připojeném adresáři místních aplikací
(`/local_apps`, případně starší `/addons`). Existující cílovou instalaci musí
odmítnout přepsat. Docker image se staví na zařízení; vyžaduje internet pro
stažení připnutého základního Python image. Při běhu nevolá placené AI API.

Připravená architektura balíčku je `amd64` a `aarch64`; přítomnost architektury
v `config.yaml` **nedokládá** úspěšný ARM64 build, provoz na Raspberry Pi ani
živou HAOS instalaci. Skutečné výsledky jsou uvedeny v přiložené testovací účtence.

Podrobnosti instalace, oprávnění a přejímky: [DOCS.md](DOCS.md).
