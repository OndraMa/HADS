# HADS Next 1.0.0-rc8 — instalační kandidát

Zdrojový PR: https://github.com/OndraMa/HADS/pull/19
Testovaný commit: `476587fb9f7593ff951143b2f4c7c3bac011c51b`.

- `HADS_Next_install_1.0.0-rc8.sh`: instalátor pro HAOS, ne pro Windows.
- `HADS_Next_1.0.0-rc8-komplet-kandidat.zip`: instalátor, celý aktuální zdrojový strom a testy, návody, matice a skutečné protokoly.
- `NAVOD_CS.md`: přesný postup aktualizace z RC6/RC7 se zachováním stejné identity a dat.
- `SHA256SUMS`: otisky všech souborů včetně kompletního ZIPu.
- `AKCEPTACE.json`, `VYSLEDKY/`: trvale zachované důkazy s vazbou na zdroj a jejich rozsah.

**323 testů na každé architektuře ARM64/AMD64**, skutečný produkční image spuštěn bez domácí sítě,
ověřená identita sestavení a čisté ukončení SIGTERM (0). Skutečný Core a původní Hermes prošly
kontejnerovou přejímkou se skriptovaným modelem. 26 lokálních mobilních/desktopových pohledů prošlo.
Jde o kandidát k přejímce; živý HAOS, úsudek skutečného modelu a fyzické opravy nejsou ověřené.

Tři poskytnuté cesty HA-MCP vrátily při nové čtecí kontrole HTTP503 před initialize.
Katalog a konkrétní diagnostické čtení skutečného serveru nejsou potvrzené.

Příjem podepsaného nezávislého důkazu OneDrive je implementovaný. Skutečná nezávislá služba obnovy
není připojená; rizikové opravy zůstávají blokované. Obecné opravy statistik/Recorderu, registrů,
skriptů, dashboardů a Zigbee binding/reporting/kanálu nejsou implementované automatické operace.
Původní Hermes zůstává lokální; paměťová rezerva 576 MiB se nesnižuje. Patnáctiminutový collector
je připravený, živé měření na RPi 4B/2 GB zde kvůli nedostupnému přístupu neproběhlo.

Instalátor podle výslovného zadání nevytváří novou předinstalační HA/OneDrive zálohu.
To neruší bezpečnostní požadavky před skutečnými opravami. Nic automaticky neodinstaluje.

Reprodukce balíčku: přesná aktiva obou úspěšných CI jobů jsou ověřená proti SHA-256 GitHub artefaktů;
`build_candidate_download.py --ref <testovaný commit> --package <ověřená CI aktiva> --output <nový adresář>`
porovná každý zabalený soubor s Git objektem. Připojené JSON protokoly jsou totožné s `VYSLEDKY/` ve větvi;
kompletní ZIP používá pevná metadata ZIP (1980-01-01, regular 0644), pak se obnoví SHA256SUMS.
Žádná privátní připojovací adresa, token ani produkční databáze nejsou součástí distribuce.

HABS není povinnou závislostí instalace ani diagnostiky HADS. Přijímací integrace záloh neobchází požadavek skutečné nezávislé obnovy.
