# HADS Next — praktická oprava a řízená přejímka

[PR 8](https://github.com/OndraMa/HADS/pull/8),
[souhrn výsledků](docs/PRACTICAL_ACCEPTANCE.md),
[český návod](haos/DOCS.md), [stažení](../KE_STAZENI/HADS_Next_1.0.0-rc2/).

Systémový incident → původní Hermes a další nativní důkazy → nezávislý plán →
souhlas vlastníka → pevná nativní aktivace světelné automatizace → skutečný
trigger, kontext, sledování a fyzické potvrzení → český report. Nově schválený
návrat vypne budoucí triggery; nevrací fyzické účinky světla. Původní CAS testovací
reference a bezpečnostní kontroly jsou zachované. Obecné konfigurační zápisy
jsou zakázané. Nativní stavová služba není config CAS.

Regrese: `python scripts/check.py`. Prohlížeč: `python scripts/practical_browser.py`.
Nativní Core/Hermes a produkční image testuje workflow pro AMD64 a ARM64;
model je skriptovaný. Nový slug `local_hads_next_practical` zachová staré aplikace.

[Živé ověření bez testovacího HAOS](docs/LIVE_WITHOUT_TEST_HAOS_CS.md) začíná pouze
čtením. Skutečný HAOS, fyzická zařízení, RPi a reálný LLM nejsou dosud přijaté.
