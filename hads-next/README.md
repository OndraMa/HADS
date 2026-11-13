# HADS Next 1.0.0-rc3

[PR 10](https://github.com/OndraMa/HADS/pull/10) · [Stažení](../KE_STAZENI/HADS_Next_1.0.0-rc3/)
· [Instalace / upgrade RC2](haos/DOCS.md) · [Integrační přehled](haos/INTEGRATIONS_CS.md)
· [Výsledek a limity](docs/RC3_DELIVERY_CS.md).

Opravený přehled, rozlišení stavových pozorování aplikací a funkčních problémů,
původní Hermes, nativní HA/Supervisor/OS adaptéry a volitelný Music Assistant
FastMCP klient. Nezávislé schvalování a funkční verifier zůstávají zachované.

`--upgrade-rc2` aktualizuje pouze ověřený zastavený `local_hads_next_practical`,
zachová data a vyžádá nativní částečnou zálohu aplikace. Nejde o restore celé HAOS.
AI a obecné zápisy se automaticky nezapínají. Testy: `python scripts/check.py`;
prohlížeč: `python scripts/practical_browser.py`; skutečný Core a původní Hermes
se testují odděleně na AMD64 a ARM64 se skriptovaným modelem. Živé hranice jsou
v přiloženém návodu a protokolu.
