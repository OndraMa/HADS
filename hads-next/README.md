# HADS Next — integrovaný přejímkový kandidát

[Souhrnný výsledek a stav každé funkce](docs/FINAL_DELIVERY.md),
[nový PR 7](https://github.com/OndraMa/HADS/pull/7),
[instalace](haos/DOCS.md), [soubory ke stažení](../KE_STAZENI/HADS_Next_1.0.0-rc1/).

Kontinuální monitorovací podmínky → trvalý spis → původní Hermes a další
skutečná čtení → validovaný návrh → schválení vlastníkem → CAS vlastní virtuální
reference → skutečná nativní automatizace a funkční sledování → český report.
Návrat závady znovu otevře stejný spis. UI je responzivní, logy jsou v detailu.

Používá se původní RepairEngine/ApprovalAuthority/FunctionalVerifier. Obecný
Core automation config API nemá CAS, a proto se jím produkční konfigurace
nepřepisuje. Companion je omezená custom integrace pro vlastní testovací
referenci; její instalace a každý plán vyžadují vědomé rozhodnutí operátora.

Z adresáře hads-next lze spustit `python scripts/check.py`. Nativní reprodukce
je v `lab/README_CS.md`; testy používají skutečný Core a původní Hermes, model
zůstává skriptovaný. Chromium test: `python lab/browser_probe.py`.
Neprovedené živé kroky jsou v `docs/haos-acceptance.md`.

Starší 0.1/0.2 a RC3 zůstávají zachované. Nový slug je
`local_hads_next_acceptance`; historická data se importují neautorizujícím
schema-1 exportem, nikdy přenosem schválení nebo aktivních zápisů.
