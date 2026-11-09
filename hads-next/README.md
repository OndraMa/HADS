# HADS Next – izolovaný funkční základ

## Aktuální vyšetřovací větev

Aktuální zdroje jsou v `codex/hads-next-investigation`, navazující na ověřený
`codex/hads-next-correction` (`5fb2ba17cf0b50d483128bc0ccb834cc126dee47`).
[Kontrolovatelný návrh změn č. 6](https://github.com/OndraMa/HADS/pull/6)
obsahuje původní izolovaný Hermes připojený k živým čtením brokeru, trvalé
vyšetřování, bezpečný opt-in poskytovatele a nové čtecí adaptéry MA/ZHA.
Prošly skutečné Core 2026.11.0 API testy v AMD64 kontejneru a 132 regresních
testů P3; následně 140 testů rolí a výzkumu P4. [Výsledky a zbývající práce](docs/results.md), [reprodukce](lab/README_CS.md).

**Nový instalační kandidát zatím není vydán.** HAOS, ARM64/RPi, skutečný
Supervisor, Music Assistant a autonomní úsudek skutečného LLM čekají na svou
přejímku. Starý instalátor níže tento nový runtime neobsahuje a není kompletní
HADS Next. Zdrojové soubory lze stáhnout na GitHubu z této větve pomocí
**Code → Download ZIP**; pro soukromý repozitář je nutné přihlášení.

## Historický balíček 0.1.0-dev1 (neobsahuje aktuální Hermes runtime)

**Ke stažení ve Windows:** [GitHub vydání a kompletní ZIP](https://github.com/OndraMa/HADS/releases/tag/hads-next-0.1.0-dev1).
Cloud není potřeba; pro soukromý repozitář se přihlas do GitHubu.
[Průvodce stažením](docs/STAZENI_WINDOWS_CS.md) vysvětluje jednotlivé soubory.

Vývojová větev `codex/hads-next` vychází přesně z Hermes RC3
`c491893bd433fa0e17dcd852a3eaa610eb3148ad`. RC3, vydané archivy i jeho
bezpečnostní kontroly zůstávají zachované. Toto **není produkční Release Candidate**.
Nový [HAOS instalační soubor](releases/0.1.0-dev1/HADS_Next_install_0.1.0-dev1.sh)
přidá samostatnou vývojovou aplikaci vedle RC3. Nepřepisuje existující HADS.

## Instalace vývojové aplikace do testovacího HAOS

Stáhni instalační soubor a [SHA-256 manifest](releases/0.1.0-dev1/SHA256SUMS).
V Terminálu/SSH s `ha`, `bash` a `python3` spusť:

```sh
bash HADS_Next_install_0.1.0-dev1.sh --verify
bash HADS_Next_install_0.1.0-dev1.sh --install-dev
```

Aplikace má vlastní slug `local_hads_next_dev` a český ingress. Umožňuje číst
Core, nahlásit incident, získat cílenou historii a uchovat spis. Vlastníka
nastaví správce podle ID na úvodní stránce do volby `owner_user_id`.
**Hermes a živé opravy nejsou v této instalační verzi aktivní.** Původní agentní
smyčka je nadále samostatně ověřená offline. Živá HAOS a ARM64 přejímka čekají.
Podrobný postup, oprávnění a omezení jsou v [instalačním návodu](haos/DOCS.md).

První scénář: incident testovací automatizace → trvalé důkazy → originální
Hermes přečte automatizaci a následně trace → přesný plán jediné změny odkazu →
výslovné místní schválení → bezpečný zápis do fixture → vykonání testovací
automatizace → ověření cílového stavu a sledování → český report a přehled.

Modelový endpoint je lokální skriptovaný fixture bez poplatků. Prokazuje skutečné
řízení nástrojů upstream Hermes, nikoli inteligenci modelu nebo vyřešení závady
domácnosti. Čas funkčního fixture testu je simulovaný; neprokazuje skutečnou dobu
sledování rádia. Při živém nasazení se tato hranice musí nahradit důvěryhodným
sběračem a reálnými hodinami.

## Spuštění a testy

Vyžaduje Python 3.12+ na Linuxu. Offline balík nemá povinné externí závislosti.
Příkazy níže jsou z adresáře `hads-next`:

```sh
python scripts/check.py
```

Testy používají dočasné soubory, SQLite a lokální HTTP fixture server; prostředí
musí dovolit loopback socket. Účtenka je v `docs/evidence/offline-tests.json`.
Volitelné skutečné WS čtení vyžaduje `pip install '.[native-ws]'`; nepředává se
do AI workeru. Kontrakty jsou ověřeny podle HA 2026.11.0, připojení k živému
HAOS nebylo provedeno.

Původ RC3 lze zkontrolovat z kořene repozitáře:

```sh
python hads-next/tools/reconstruct_rc3.py --extract --write-manifest
```

## Průchozí scénář s reálným Hermes runtime

Nejdříve podle [Hermes dokumentace](docs/hermes.md) sestavte testovací Docker
image. Je potřeba několik GB volného disku; nejde o HAOS deployment. Test worker
má 512 MiB limit, běží jako nepřivilegovaný uživatel bez sítě a bez HA adresářů.

```sh
mkdir -p .test-tmp
PYTHONPATH=src python -m hads_next.cli init "$PWD/.test-tmp/vertical"
python scripts/hermes_smoke_run.py \
  --input .test-tmp/vertical/snapshots.json \
  --output .test-tmp/vertical/hermes-receipt.json
PYTHONPATH=src python -m hads_next.cli plan "$PWD/.test-tmp/vertical" \
  --receipt .test-tmp/vertical/hermes-receipt.json
```

Prohlédněte celý `plan.json`, původní i navržený stav, jedinou změnu cíle,
důkazy, riziko a ověřovací podmínku. Potom jako místní vlastník testu zvolte
**jeden** příkaz `approve`, `reject` nebo `manual`. Pouze `approve` dovolí zápis:

```sh
PYTHONPATH=src python -m hads_next.cli approve "$PWD/.test-tmp/vertical"
PYTHONPATH=src python -m hads_next.cli execute "$PWD/.test-tmp/vertical"
PYTHONPATH=src python -m hads_next.cli test-fixture "$PWD/.test-tmp/vertical"
```

`test-fixture` skutečně načte změněnou testovací automatizaci, vykoná ji proti
izolovanému registry/stavům a ověří výsledek s logickými hodinami. S neopraveným
odkazem funkční podmínka selže. Nevytváří žádné přehrávání, hlasitost ani stisk.
Výstupy: `report.json`, `case-export.json`, `command-center.html`. Opaque token
souhlasu je jen v soukromém `decision.json`, nikdy v přehledu nebo AI vstupu.
Stejný plán nelze vykonat znovu. Existující pracovní adresář se nepřepisuje;
pro nový test použijte jiný název.

Schválení v tomto CLI znamená oprávnění místního vlastníka procesu. Není to
hotová autentizace HA uživatele. CLI ani databázi nevystavujte jako REST/MCP
službu. Hash účtenky Hermes spojuje vstup a test, není podpis runtime ani souhlas.

## Co je připravené a co čeká

| Oblast | Rozsah |
| --- | --- |
| M0 audit | Přesný původ a bajtová shoda 133 souborů, ADR, upstream rešerše, hrozby a migrační hranice |
| M1 data | Omezená nativní čtení, SQLite spisy, dedup, opakování, retence/export a lokální fixture testy |
| M2 Hermes | Izolovaný originální native tool-loop; stav skutečného běhu dokládají jen uložené účtenky |
| M3/M4 | Jedna izolovaná oprava, místní schvalování, intent před zápisem, rollback s novým souhlasem, funkční verifier a český export |
| M5 HAOS RC | **Čeká**: skutečná HA identita, bezpečný HAOS broker/worker, skutečný model opt-in, ARM64/RPi a live přejímka |

Radio/Zigbee/DNS jsou deterministické vyšetřovací moduly s anonymizovanými
**syntetickými** fixtures; nevydáváme je za zachycená data skutečné domácnosti.
Music Assistant FastMCP, externí výzkum za běhu, dlouhodobé monitorovací úlohy,
osm specializovaných workflow, automatická tvorba skills a produkční HAOS nasazení
zatím nejsou implementované. Povinná další aplikace se nepřidává. Podrobné
kontrakty, oprávnění a alternativy jsou v [rešerši](docs/research.md).

Živé rizikové opravy nejsou v katalogu. Požadavek RC3 na ověřenou OneDrive zálohu
se neruší. Ověřený upload/hash není důkaz obnovitelnosti; bez odpovídajícího
nezávislého ověření bude riziková operace blokována. Lokální fixture snapshot
neznamená obnovu HAOS. Přejímka je v [HAOS protokolu](docs/haos-acceptance.md).
