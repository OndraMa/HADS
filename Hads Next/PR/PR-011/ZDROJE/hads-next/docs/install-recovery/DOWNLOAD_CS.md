# Obnovení instalace HADS Next RC3

Pro případ ze snímku: Next byl odinstalovaný, ale zůstaly místní zdroje, které
novou instalaci blokují. Původní aktualizační postup tuto situaci nepokryl.
**Nic dalšího neodinstalovávej a nemaž adresář ani data.**

1. Stáhni `HADS_Next_RC3_obnova.zip` přes **Download raw file** a rozbal jej ve Windows.
2. Pomocí File editoru nebo přenosu souborů ulož tyto dva soubory do `/config`:
   `HADS_Next_obnovit_instalaci_RC3.py` a `HADS_Next_install_1.0.0-rc3.sh`.
   Druhý soubor je přesně původní vydaný RC3 instalátor; pokud tam již leží,
   pomocník ověří jeho správný kontrolní součet.
3. Ve stejném HA terminálu jako na snímku spusť:

```sh
python3 /config/HADS_Next_obnovit_instalaci_RC3.py --recover-and-install /config/HADS_Next_install_1.0.0-rc3.sh
```

Příkaz ověří nepřítomnost aplikace u Supervisora, ověří původ ponechaných zdrojů,
uschová je do archivu i přejmenovaného adresáře a spustí RC3 instalaci. Samotná
instalace může trvat déle; nepouštěj další instalátor současně. Po potvrzení
spuštěného RC3 otevři **Nastavení → Aplikace → HADS Next → Otevřít webové rozhraní**.
V nové instalaci může být potřeba znovu potvrdit vlastníka; AI ponech vypnutou.

Pokud pomocník vypíše překážku, ulož a pošli přesnou hlášku. Nesnaž se ji obejít
mazáním markeru, adresáře nebo další odinstalací. Stav `error` u stále registrované
aplikace není důkaz odinstalování a helper v něm nic nepřesune.

Pouhá kontrola bez změn je k dispozici přes:

```sh
python3 /config/HADS_Next_obnovit_instalaci_RC3.py --inspect
```

## Co bylo ověřeno

[PR 11](https://github.com/OndraMa/HADS/pull/11) obsahuje změnu a všechny zdroje.
[Nativní ARM64 i AMD64 přejímka](https://github.com/OndraMa/HADS/actions/runs/43420601632)
prošla: 195 testů na každé architektuře a celý obnovovací postup se skutečným
pomocníkem, původními RC2 zdroji a přesným vydaným RC3 instalátorem.
Supervisor/HA CLI byl v této přejímce testovací. Živá HAOS přejímka zůstává čekající.
Soubory jsou v [tomto předvydání](https://github.com/OndraMa/HADS/releases/tag/hads-next-rc3-recovery1).

Příčina stavu `error` při zastavení dosud není prokázaná ani tímto nástrojem opravená.
Odinstalování mohlo odstranit soukromá data aplikace; pomocník je neumí zpětně
obnovit a kopie zdrojů není datová záloha. Na případná zbývající data ani jiné
aplikace pomocník nesahá. Aplikace, Hermes a MCP adaptéry zůstávají přesně z RC3;
nejde o nové tvrzení jejich živé funkčnosti nebo produkční přejímky.

Podrobný postup a bezpečnostní hranice jsou v `PODROBNY_POSTUP_CS.md`.
Reprodukovatelné sestavení těchto souborů:
`python3 hads-next/docs/install-recovery/build_delivery.py` v kořenu repozitáře.
