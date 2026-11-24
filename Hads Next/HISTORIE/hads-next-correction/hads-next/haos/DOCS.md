# Instalace a přejímka HADS Next 0.1.0-dev1

**Pracovní větev `codex/hads-next-correction`: změny níže ještě nejsou vydaný
instalační balíček.** Již vydaná 0.1.0-dev1 se nemění. V pracovním kódu přibyl
průvodce s ověřením správce přes HA `config/auth/list`, automatické uložení
vlastníka a propojení Supervisor zdrojů. Neinstaluj pracovní zdroje jako hotovou
náhradu celé platformy; Hermes a živé opravy stále nejsou dokončené.

Tento balík je vývojová aplikace pro testovací HAOS. Dosavadní Next prokázal
izolovaný scénář s originálním Hermes, ale produkční HAOS worker a živé schvalované
opravy nejsou dokončené. Tento balík je neaktivuje a nenahrazuje je demonstrací.

## Před instalací

- Použij testovací HAOS a Home Assistant Core alespoň 2026.11.0. Připrav si
  běžnou vlastní zálohu instalace; existence zálohy sama nedokládá obnovitelnost.
- V Terminálu/SSH musí být dostupný příkaz `ha` a již připojený adresář místních
  aplikací `/local_apps` nebo starší `/addons`. Přepnutí protection mode aplikace
  HADS Next se nevyžaduje. Nepřipojuj jí Docker socket ani složku konfigurace HA.
- Instalační terminál potřebuje `bash`, `python3`, `base64` a `mktemp`. Pokud
  `python3` chybí, instalátor se zastaví před změnou. V terminálové aplikaci
  postavené na Alpine jej lze doinstalovat příkazem `apk add --no-cache python3`;
  tento příkaz nepatří do hostitelského shellu HAOS.
- Stáhni soubor `HADS_Next_install_0.1.0-dev1.sh` a odpovídající SHA-256 manifest
  z vývojové větve. Nepouštěj jej přímo z potrubí síťového downloaderu do shellu.
- RC3 může zůstat nainstalované. Nový slug je `local_hads_next_dev`; nic se
  nepřepisuje pod slugem starého HADS ani v jeho datovém adresáři.

## Soubor a instalační kroky

Ověř distribuovaný SHA-256 podle přiloženého manifestu, potom spusť kontrolu
vnitřního balíčku:

```sh
bash HADS_Next_install_0.1.0-dev1.sh --verify
```

Kontrola nesmí instalovat aplikaci ani volat zapisovací Supervisor operace.
Vlastní instalace se spustí explicitně:

```sh
bash HADS_Next_install_0.1.0-dev1.sh --install-dev
```

Instalaci nové samostatné vývojové aplikace spouštěj až explicitním instalačním
režimem popsaným ve výstupu `--help`. Instalátor musí odmítnout existující cíl,
chybný payload, symlink cíle a neznámé prostředí; neprovádí migraci ani upgrade RC3.

Podporované příkazy HA CLI pro tuto aplikaci jsou:

```sh
ha store reload
ha apps info local_hads_next_dev
ha apps install local_hads_next_dev
ha apps start local_hads_next_dev
```

Použij je ručně, pokud zvolíš pouze extrakci balíčku, nebo pro kontrolu kroků
provedených instalačním režimem. `ha apps install` může trvat několik minut při
stavbě image. Při chybě zachovej výstup instalace; nesnaž se problém obejít
restartem Core nebo změnou oprávnění HADS.

Starší HA CLI může místo `apps` vyžadovat `addons`; aktuální CLI zachovává tento
název jako alias. Obnova katalogu je `ha store reload`, nikoli vymyšlený příkaz
`ha apps reload`. Při nejistotě ověř `ha apps --help` nebo `ha addons --help`.

Po instalaci otevři **Nastavení → Aplikace → HADS Next – vývojová přejímka →
Otevřít webové rozhraní**. V některých verzích HA může být sekce ještě označená
jako Doplňky. Aplikace má výchozí `boot: manual`; automatické spuštění po restartu
HAOS zapni až po úspěšné místní přejímce. Manuální spuštění příkazem `ha apps start`
nebo tlačítkem Spustit není potvrzením úspěšné diagnostiky.

Ve vydané 0.1.0-dev1 se vlastník nastavuje ruční volbou `owner_user_id`.
Pracovní oprava tento krok nahrazuje průvodcem: přihlášeného správce ověří
proti HA API a po potvrzení uloží jeho identitu do databáze. Jiná identita,
neaktivní/systémový účet, neověřitelná role nebo spojení mimo Supervisor data
nezpřístupní. Role se opětovně ověřuje s nejvýše patnáctisekundovou cache.
Jde o přístupovou kontrolu, nikoli hotové schvalování HA oprav.

## Co tato verze dělá

- Zobrazuje český přehled a vlastní trvalé incidentní spisy přes HA ingress.
- Získává omezená skutečná čtení stavů a konfigurace Core, pokud proxy a oprávnění
  fungují. Přesný dostupný rozsah a chyby čtení musí být vidět v aplikaci.
- Ukládá data do vlastní `/data/hads-next`; nedostává mount konfigurace HA,
  staré databáze HADS, médií, záloh ani ostatních aplikací.
- Neprovádí služby, změny přehrávání/hlasitosti, restarty, reloady, mazání ani
  jiné živé opravy. Nemá obecnou REST/MCP proxy ani shell nástroj pro analytika.
- Nespouští model, původní Hermes ani izolovaný demo scénář automaticky. Není
  potřeba zadat žádný modelový API klíč. Původní Hermes zůstává ověřený samostatným
  offline kontejnerovým testem, ne produkčním workerem této aplikace.

## Oprávnění a skutečná bezpečnostní hranice

`homeassistant_api: true` zpřístupní Core proxy a Supervisor předá aplikaci
`SUPERVISOR_TOKEN`. Tento token přes Core proxy jedná jako **administrátor HA**;
není to read-only token. Proto jej drží pouze pevný čtecí adaptér bez obecného
výběru URL/metody a nikde se neexportuje. Vydaná 0.1.0-dev1 nemá `hassio_api`.
Pracovní oprava jej zapíná s rolí `manager`, protože ji dokumentované čtení
seznamu, logů a statistik jiných aplikací vyžaduje. Role umožňuje i zápis;
omezení zajišťuje pevný katalog GET operací a absence živého zapisovacího
rozhraní, nikoli read-only scope tokenu. Pracovní aplikace nadále nemá `docker_api`,
host networking, `privileged`, přístup k zařízením ani připojenou `/config`.

Do příkazové řádky, kódu nebo promptu nedávej skutečné tokeny. UI nepřijímá
libovolnou URL/HTTP metodu pro volání Home Assistantu a nezobrazuje token.
AI produkční aktivace a živý vykonavatel jsou vypnuté; tento proces proto
nespojuje administrátorský credential s agentním plánováním nebo shell nástroji.

Ingress server má přijímat pouze spojení od Supervisoru `172.30.32.2`.
Identitu uživatele předává Supervisor v `X-Remote-User-Id`; při chybějící identitě
nelze předpokládat výchozího kapitána. Prohlížeč nesmí podstrčit tyto hlavičky
přímo aplikaci. Host port se nepublikuje. `/health` poskytuje jen necitlivý stav
procesu pro watchdog, nikoli diagnostická data nebo důkaz úspěšné přejímky.

## První test po spuštění

1. Otevři rozhraní přes HA jako správce. Zkontroluj výslovné označení vývojové
   verze, vypnuté AI a nepřítomnost živých opravných operací.
2. Zkontroluj výsledek čtení Core: dostupnost rozhraní, autentizaci, konkrétní
   úspěšné čtení, jeho čas a případnou chybu. Nestačí běžící kontejner nebo HTTP 200.
3. Nahlas jednoduchý incident nebo použij dostupné read-only zjištění a ověř,
   že se vytvoří vlastní spis. Nevyvolávej výpadek skutečného domácího zařízení.
4. Obnov stránku a případ znovu otevři. Opakované načtení stejného důkazu nesmí
   přidat další výskyt. Samotný stav `unavailable` neprokazuje příčinu poruchy.
5. Zastav a znovu spusť **jen tuto testovací aplikaci**. Ověř zachování spisu,
   chyb čtení a že se nespustily žádné čekající zápisy nebo demo opravy.
6. Zkus rozhraní z nepřihlášené relace a přímý přístup mimo ingress. Diagnostická
   data musí zůstat nepřístupná. Zkontroluj, že nevznikl host port.
7. Zapiš verzi HAOS, Supervisoru a Core, architekturu, datum, operátora, výsledek
   a konkrétní důkazy. Úspěch tohoto testu neuzavírá Test J plného zadání.

Kompletní živá přejímka HADS Next, zejména rádio, fyzický Zigbee test, skutečný
Hermes worker, identita pro schvalování a nezávislá obnovitelnost OneDrive,
zůstává samostatnou podmínkou před zavedením živých oprav. Existující ochrany RC3
se touto instalací nevypínají. Lokální testovací snapshot není záloha HAOS.

## Návrat a odinstalace

Při potížích zastav jen `local_hads_next_dev` přes jeho stránku nebo příkaz
`ha apps stop local_hads_next_dev`. Core ani původní RC3 se tím nemění.
Neprováděj automatické mazání dat. Před odinstalací exportuj spisy a ověř
vlastní zálohu; odinstalace aplikace v HA může odstranit její soukromá data.
Instalátor neposkytuje automatickou obnovu celé HAOS instalace ani obcházení
chybného OneDrive ověření.

## Ověřené oficiální kontrakty

Kontrola dokumentace a zdrojů dne 2026-11-08, nikoli živá HAOS přejímka:

- [Konfigurace aplikací](https://contributors.home-assistant.io/apps/reference/configuration/):
  `arch`, `homeassistant_api`, ingress, watchdog, mapy, `boot` a `init`.
- [Komunikace s HA](https://contributors.home-assistant.io/apps/guides/communication/):
  `SUPERVISOR_TOKEN`, REST proxy `/core/api/` a její skutečná administrátorská práva.
- [Ingress](https://contributors.home-assistant.io/apps/guides/ingress/):
  zdrojová IP, relativní URL a identita předávaná Supervisorem.
- [Lokální aplikace](https://contributors.home-assistant.io/apps/first-app/):
  `/local_apps` a instalace lokálního Dockerfile Supervisorem.
- [Container image](https://contributors.home-assistant.io/apps/guides/dockerfile/):
  libovolný vhodný base image; bez S6 se ponechává `init: true`.
- HA CLI commit `bf6d59ff097e6da6aca179a4bac1b6cba133d1ba`:
  [apps](https://github.com/home-assistant/cli/blob/bf6d59ff097e6da6aca179a4bac1b6cba133d1ba/cmd/apps.go),
  [install](https://github.com/home-assistant/cli/blob/bf6d59ff097e6da6aca179a4bac1b6cba133d1ba/cmd/apps_install.go),
  [start](https://github.com/home-assistant/cli/blob/bf6d59ff097e6da6aca179a4bac1b6cba133d1ba/cmd/apps_start.go),
  [store reload](https://github.com/home-assistant/cli/blob/bf6d59ff097e6da6aca179a4bac1b6cba133d1ba/cmd/store_reload.go).
