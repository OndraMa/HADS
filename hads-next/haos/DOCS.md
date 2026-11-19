# HADS Next 1.0.0-rc8 — instalační kandidát

Kandidát PR #19 obsahuje aktuální orchestraci. RC6/RC7 ji neobsahují.
Živá HAOS přejímka a úplné splnění původního zadání nejsou potvrzené.

## Aktualizace ověřeného RC6/RC7

Stáhni kandidát z GitHubu a přenes `HADS_Next_install_1.0.0-rc8.sh` do `/config` v HAOS.
Neodinstalovávej stávající aplikaci. Ve Windows instalátor nespouštěj a nic dalšího neinstaluj.
V terminálové aplikaci HAOS spusť:

```bash
bash /config/HADS_Next_install_1.0.0-rc8.sh --verify
bash /config/HADS_Next_install_1.0.0-rc8.sh --upgrade
```

Instalátor nezaměňuje `error` za potvrzené zastavení. Ověří původní manifest a všechny zdroje;
upravený strom nebo nejasný předchozí update nepřepíše a nic automaticky neodinstaluje.
Použije native Supervisor update stejné identity `local_hads_next_practical` a zachová `/data`.
Historie, incidenty, důkazy a konverzace se nemažou. Nepoužité staré souhlasy při změně ověřeného sestavení expirují.
Nejistý update se neopakuje. Zachované staré zdroje nejsou záloha dat ani úplná obnova HAOS.

Podle výslovného zadání **nevytváří novou předinstalační HA/OneDrive zálohu**.
To neruší bezpečnostní požadavky před opravami domácnosti.

## Nová oddělená instalace

Pouze pokud HADS Next není instalovaný a jeho zdrojový adresář neexistuje:

```bash
bash /config/HADS_Next_install_1.0.0-rc8.sh --install-dev
```

Je potřeba HA CLI (`ha`), `bash`, `python3`, `base64` a připojený místní adresář aplikací
`/addons` nebo `/local_apps` v terminálové aplikaci HAOS. Chybějící adresář instalátor nevytváří naslepo.
Pro inspekci bez HA CLI použij `--extract-only /absolutni/novy-adresar`; existující cíl se nepřepisuje.
Původní Hermes 2.0.0-rc3 se nespouští ani nemění.

## První spuštění

Otevři HADS v HAOS. Přihlášeného vlastníka ověří Home Assistant; ID ani tokeny nepatří do chatu.
Záhlaví a `/health` ukazují verzi, zdrojový commit a ID sestavení. Neověřený původ je výslovně označený.
HADS sám čte dostupné nativní zdroje a reporty; nemusíš kopírovat logy ani spouštět diagnostické příkazy.

- `docs/CANDIDATE_20261119_CS.md`: jednorázové kroky a známé meze.
- `docs/ORCHESTRATION_SETUP_CS.md`: HA-MCP, původní Hermes a privátní připojení.
- `docs/RESTORE_VERIFIER_CONTRACT.md`: příjem skutečného nezávislého důkazu obnovy.
- `docs/ORCHESTRATION_LIVE_ACCEPTANCE_CS.md`: čekající živá přejímka.

V **Nástroje servisního týmu** stačí přesná HA-MCP URL do maskovaného pole; token jen pokud jej server vyžaduje.
Inspector/HADocs se hledají automaticky podle skutečného inventáře. Katalog není potvrzení diagnostiky.
Konverzace spisu uchová otázky i doplnění; její zprávy nic neschvalují.
AI vyžaduje původní izolovaný runtime, volných 576 MiB a odpovídající souhlas s náklady.
Změny domácnosti vyžadují konkrétní podporovaný plán, nezávislý důkaz obnovy a vlastnický souhlas.
