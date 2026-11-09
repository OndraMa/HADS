# Skutečný Home Assistant Core bez testovacího HAOS

## Nový běh P0–P3: původní Hermes a skutečná diagnostická API

`haos/Dockerfile` s `CORE_LAB=1` nyní navíc spouští
`core_hermes_probe.py`: provozní controller, zabezpečené první nastavení,
skutečný izolovaný Hermes, živé dotazy Evidence Brokeru a místní skriptovaný
HTTPS model. `source_contract_probe.py` doplňuje Recorder, Activity/Action
history, System Health, virtuální rádio a vloženou ZHA událost s nativní trace.
Přehled a hashe: [hermes-core-sources.json](../docs/evidence/hermes-core-sources.json).
Nejde o reálný LLM úsudek, Music Assistant, Supervisor nebo fyzický HAOS test.

Reprodukce z adresáře `hads-next` (nové výstupní adresáře, žádné živé HA tokeny):

```bash
python scripts/investigation_context.py --receipt .test-tmp/investigation-context
docker build --build-arg CORE_LAB=1 --target receipt \
  --output type=local,dest=.test-tmp/investigation-result \
  .test-tmp/investigation-context
```

V cloud prostředí s TLS proxy je nutné doplnit BuildKit secret
`--secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt`. Ověřování TLS
zůstává zapnuté. Pro běh je potřeba dostatek prostoru pro Python/Core/Hermes;
VFS Docker driver dělá úplné kopie vrstev. Laboratoř vynechává pouze nepoužívané
UI překlady a JS source mapy z oficiálního frontend wheelu (verze 20261028.4,
SHA-256 `e5e59b82e63b288323d35886272f2e490ee62f6c7aaa2c56e7ef45e300d44757`).
Python kód Core/frontend ani diagnostické API nejsou nahrazené nebo upravené.
Virtuální platforma `hads_lab_player` je pouze řízený testovací přehrávač.

## Původní samostatný laboratorní test oprav

Tato laboratoř spouští skutečný balíček `homeassistant==2026.11.0` z PyPI
s nativními komponentami, validací, autentizací, automatizacemi a event bus.
HA objekty ani HTTP handlery nejsou nahrazené fixtures nebo mocky.
Je to nezávislý integrační test opravného základu, nikoli dokončený HADS,
Hermes vyšetřovací smyčka, HAOS instalátor nebo přejímka domácnosti.

Pro každý běh vznikne nová dočasná konfigurace a administrátor. Přístupový
token zůstává v paměti testovacího procesu a nevyžaduje se od uživatele.
Interní HA auth úložiště žije v dočasném tmpfs a zanikne s kontejnerem.
Přihlašovací materiál se nezapisuje do výsledku.
Kontejner má pouze loopback, žádný publikovaný port, root filesystem jen ke
čtení, UID 65532, nulové capabilities, zákaz získání dalších oprávnění a limit
768 MiB. Jediné připojené soubory jsou čitelné kopie testovacího zdroje.
Nepřipojuje `/config`, Docker socket ani adresář domácí instalace.

## Spuštění na vývojovém Linuxu

Je potřeba Python 3.12+, Docker s BuildKitem a volné místo pro obraz i běžící
kontejner. V prostředí s VFS je vhodná rezerva alespoň 3 GiB.
Z adresáře `hads-next`:

```sh
docker --host=unix:///var/run/docker.sock build -f lab/Core.Dockerfile -t hads-next-core-lab:2026.11.0 lab
python lab/run_core_lab.py
```

Cloud s HTTPS proxy předává při build navíc
`--secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt`.
Ověřování TLS zůstává zapnuté. Runtime již síť nepotřebuje.
Runner odstraňuje pouze svůj náhodně pojmenovaný kontejner. Starý výsledek
nepřepíše úspěchem, pokud nový běh selže.

## Co test skutečně dělá

1. Nativní API odmítne nepřihlášeného klienta a neplatnou konfiguraci.
2. HADS čte Core konfiguraci a stavy. WebSocket příkazy HADS čtou skutečnou
   admin identitu, entity/device registry a automation trace.
3. Virtuální tlačítko spustí automatizaci s neexistujícím cílem. Skutečný
   virtuální přepínač zůstane vypnutý. Konfigurace, stav a trace tvoří důkazy.
4. Stávající HADS katalog připraví neměnný plán jediné změny odkazu.
   Zápisy bez souhlasu, cizí principal a cíl mimo virtuální laboratoř odmítne.
5. Simulované místní rozhodnutí operátora vydá jednorázové schválení.
   Tentýž vykonavatel uloží durable intent a použije skutečné Core config API.
6. Znovuvytvoření vykonavatele nad stejnou SQLite nepovolí opakovaný zásah.
   Pouhé potvrzení zápisu nepovažuje verifier za vyřešení.
7. Skutečný trigger a změna cíle mají společné kontextové ID. Aktivní odběr
   událostí sleduje virtuální cíl nejméně dvě skutečné sekundy. Uložený český
   report uzavře spis a nový IncidentStore přečte jeho stav z databáze.
8. Řízeně vložená skutečná změna cíle na `off` znovu otevře tentýž případ.
   Vynechání dřívějšího důkazu při dalším ověření nevrátí falešný úspěch.

Výsledek je v `../docs/evidence/core-lab.json`: přesný image, platforma,
hash vstupů, původní a navržený objekt, kontextové důkazy, oba reporty,
čas a maximální RSS procesu. `core-lab-dependencies.txt` v témže adresáři
je inventář tohoto image, nikoli otestovaný ARM64 lockfile.
`core-constraints.txt` je převzat beze změny z Home Assistant Core tagu
`2026.11.0`, `homeassistant/package_constraints.txt`, Git blob
`1daa3a2b5c6db7348b316a88f7f9acdf86fd1bdc` (upstream Apache-2.0).

## Hranice výsledku

Zapisovač je pouze v `lab/core_repair.py` a do HAOS instalačního payloadu se
nebalí. Nelze mu předat adresu jiné instalace ani libovolnou automatizaci.
Nenahrazuje OneDrive zálohu ani obnovu HAOS; snapshot se týká jediného
virtuálního objektu. Dvou sekundový virtuální test nedokládá stabilitu rádia.
Schválení v testu není kliknutí skutečného uživatele v HAOS Ingress UI.

Core endpoint `/api/config/automation/config/{id}` v ověřené verzi neposkytuje
CAS/ETag a zapisuje celý `automations.yaml`; může doplnit ID jiným položkám.
Proto tato metoda smí v testu měnit pouze čerstvou, výhradně vlastněnou
konfiguraci s jedinou automatizací. Není tím vyřešen souběh s editorem HA UI
v produkci. HAOS zapisovač zůstává vypnutý.

Hermes není součástí tohoto konkrétního běhu. Supervisor, skutečný Ingress,
HAOS, ARM64/RPi, Music Assistant, ZHA a fyzické výsledky dosud neprošly touto
zkouškou. Jejich dostupnost tento protokol netvrdí.
