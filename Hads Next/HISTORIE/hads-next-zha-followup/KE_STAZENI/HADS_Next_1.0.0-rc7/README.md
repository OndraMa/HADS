# HADS Next 1.0.0-rc7 — instalátor pro HAOS

[Stáhnout kompletní ZIP](HADS_Next_1.0.0-rc7-komplet.zip) · [Instalátor](HADS_Next_install_1.0.0-rc7.sh) · [SHA-256](HADS_Next_1.0.0-rc7-SHA256SUMS.txt)

Na souboru použij **Download raw file**, případně stáhni a rozbal kompletní ZIP.
**Uložit stránku jako stáhne HTML GitHubu, které není instalátor.** Ve Windows skript nespouštěj.
Instalační soubor zkopíruj do `/config` v HAOS. Pro existující vydanou RC6:

```sh
echo 'c38a295191659d73cb675e3fb1e68ddf059edb40b11a1013db8a10e5ea31f476  /config/HADS_Next_install_1.0.0-rc7.sh' | sha256sum -c - &&
bash /config/HADS_Next_install_1.0.0-rc7.sh --verify &&
bash /config/HADS_Next_install_1.0.0-rc7.sh --upgrade-rc6
```

RC6 předem nezastavuj ani neodinstalovávej. Aktualizace vyžaduje přesné vydané zdroje RC6 a nativní
částečnou zálohu; zachová data a stav. Při chybě nic nemaž a zachovej hlášku/marker.
Čistá nová instalace: po úspěšné kontrole součtu a `--verify` použij `--install-dev`.
Starší vydání musejí projít svými předchozími přechody; nepoužívej na ně upgrade z RC6.

- [Úplný český instalační návod](HADS_Next_1.0.0-rc7-navod-CS.md)
- [ZHA Toolkit — jednorázové nastavení a co povolit](../../hads-next/docs/ZHA_TOOLKIT_SETUP_CS.md)
- [HA-MCP a Hermes — přesný rozsah nastavení](HAMCP_HERMES_CS.md)
- [Audit, opravy sběru a nedokončené funkce](AUDIT_RC7_CS.md)
- [Přesný testovací protokol](ACCEPTANCE.json)
- [Nový PR 18](https://github.com/OndraMa/HADS/pull/18)

RC7 automaticky propojí Watchman cíle se stavem, registry, dostupnou historií a pasivní ZHA/Toolkit cache.
Pro toto čtení není potřeba AI klíč ani povolování obecných oprav. Vlastní diagnostické příkazy od uživatele
nevyžaduje. Neopravuje zařízení podle podobného názvu a nezpřístupňuje obecné služby Toolkitu AI.

Prošlo **273 testů na každé nativní architektuře ARM64/AMD64**, skutečný Core a původní izolovaný Hermes
se skriptovaným neplaceným modelem, test restartu/dat a aktualizace s testovacím Supervisor CLI,
plus **20 pohledů prohlížeče**. Instalační soubory jsou totožné na obou architekturách a 62 souborů
payloadu bylo porovnáno s revizí `513394ee9e73f54a639113786f7a6ab92b182870`.

Živý MCP přístup při kontrole vrátil HTTP 503. Funkce konkrétního Toolkitu a příčina selhání senzoru
komory zatím nejsou ověřené. Obecné opravné adaptéry ZHA/Spook/registry/statistiky a úplné vlastní
konektory HA-MCP/Hamster/Inspector/HADocs nejsou dokončené. Nejde o plné splnění původního zadání.
Paměťová rezerva, AI souhlasy a OneDrive ochrany se nemění. Živá HAOS obnova a fyzické výsledky čekají.

Kompletní ZIP obsahuje instalátor, aktuální zdroje, důkazy a návody včetně návodu Toolkitu ve
`zdrojovy-repozitar/hads-next/docs/ZHA_TOOLKIT_SETUP_CS.md`. Obsahuje stav dokumentace v okamžiku
balení; tento samostatný rozcestník do něj není rekurzivně přibalený.
