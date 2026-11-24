# HADS Next — skutečný vyšetřovací runtime

Aktuální větev je **codex/hads-next-investigation**, navazuje na ověřený
commit `5fb2ba17cf0b50d483128bc0ccb834cc126dee47`.
[Kontrolovatelný návrh změn č. 6](https://github.com/OndraMa/HADS/pull/6).

Původní připnutý NousResearch Hermes nyní čte skutečná Core API přes oddělený
broker, ukládá vícekrokové vyšetřování a připravuje nezávisle validované návrhy.
Vlastník ověřený přes HA spravuje poskytovatele, jednotlivé případy a souhlasy.
AI i veřejný výzkum jsou standardně vypnuté. Produkční zápisy nejsou zpřístupněné.

Instalační kandidát **0.2.0-dev1 prošel nativními kontejnerovými testy AMD64 i ARM64**. Obsahuje skutečný runtime
a kontrolu jeho připravenosti bez modelu. [Instalační návod a první spuštění](haos/DOCS.md),
[stažení ve Windows](docs/STAZENI_WINDOWS_CS.md), [výsledky](docs/results.md),
[reprodukce](lab/README_CS.md), [živá přejímka](docs/haos-acceptance.md).
V prohlížeči vyber tuto větev a **Code → Download ZIP**; cloudový panel není potřeba.

Na obou architekturách prošlo 150 offline testů, skutečný Core 2026.11.0 +
původní Hermes i výchozí instalační image. Model byl skriptovaný HTTPS endpoint, takže autonomní úsudek skutečného
LLM není prokázaný. Živý HAOS, Supervisor, MA server, fyzické rádio/Zigbee a
RPi 4 / 2 GB čekají na přejímku. Tyto hranice se neskrývají počtem testů.

Historický balíček 0.1.0-dev1 původní runtime neobsahuje. Zůstává zachovaný
v původních archivech; není doporučený aktuální instalátor. RC3, main a vydané
archivy se nepřepisují. Nová aplikace má vlastní slug a data.

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
