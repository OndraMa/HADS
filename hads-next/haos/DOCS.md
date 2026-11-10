# Instalace HADS Next 0.2.0-dev1

Vývojový kandidát pro **oddělený testovací HAOS**. Obsahuje původní připnutý
Hermes a skutečné čtecí vyšetřování. Živý zapisovací katalog oprav není
zpřístupněný. Návrh lze posoudit, odmítnout nebo provést ručně.

## Stažení ve Windows

Otevři [vývojovou větev](https://github.com/OndraMa/HADS/tree/codex/hads-next-investigation).
Výchozí stránka repozitáře může ukazovat starší HADS. Použij **Code → Download
ZIP** a archiv rozbal. Připravený instalátor hledej v novém adresáři
`KE_STAZENI/HADS_Next_0.2.0-dev1`, až bude jeho přejímka doložená.
SHA-256 instalačního souboru porovnej s přiloženým manifestem:

```powershell
Get-FileHash .\HADS_Next_install_0.2.0-dev1.sh -Algorithm SHA256
```

Skript se spouští v Linuxu/terminálové aplikaci HAOS, nikoli v PowerShellu.
Nepouštěj downloader přímo do shellu.

## Před instalací

- Oddělený HAOS s Core alespoň 2026.11.0. Živá HAOS přejímka a výkon na
  Raspberry Pi 4 se 2 GB dosud čekají.
- Terminál potřebuje `ha`, `bash`, `python3`, `base64`, `mktemp` a již
  připojené místní aplikace `/local_apps` nebo `/addons`. Chybějící Python
  zastaví instalátor před změnou. Neinstaluj vývojové balíčky do hostitele HAOS.
  Alternativou je extrakce v Linuxu/WSL a ruční přenos do místních aplikací.
- Stavba potřebuje internet pro připnutý image, Hermes a závislosti.
  Instalace a test připravenosti nepotřebují modelový klíč.
- Nový slug `local_hads_next_investigation` má vlastní datový svazek.
  Nepřepisuje RC3 ani `local_hads_next_dev`; stará data a schválení neimportuje.
- Připrav vlastní zálohu. Obnovitelnost OneDrive se tímto balíčkem nedokládá.
  Rizikové produkční opravy zůstávají nedostupné.

## Kontrola a instalace

```sh
bash HADS_Next_install_0.2.0-dev1.sh --verify
bash HADS_Next_install_0.2.0-dev1.sh --install-dev
```

První příkaz pouze kontroluje manifest a archiv. Druhý explicitně instaluje
novou aplikaci; odmítne existující cíl, symlinky a neznámé prostředí.
Nemigruje starý HADS. Stavba může trvat několik minut. Při chybě zachovej
výstup a nezvyšuj oprávnění HADS.

Pouhá extrakce do nového cíle:

```sh
bash HADS_Next_install_0.2.0-dev1.sh --extract-only ./hads-next-source
```

Po ručním přenosu do místních aplikací:

```sh
ha store reload
ha apps info local_hads_next_investigation
ha apps install local_hads_next_investigation
ha apps start local_hads_next_investigation
```

Starší CLI může používat alias `addons`; ověř jeho `--help`. Obnova katalogu
je `ha store reload`. Otevři **Nastavení → Aplikace → HADS Next – vývojová
přejímka → Otevřít webové rozhraní**. Automatický start zapni až po místní přejímce.

## První vyšetřování

1. Přihlas se jako správce a potvrď vlastnictví v průvodci. Identita se ověřuje
   přes skutečné HA `config/auth/list`, nikoli jen podle hlavičky prohlížeče.
2. Zkontroluj dostupnost zdrojů. Připojení není úspěšné konkrétní čtení.
   Chyby a nepřečtená data zůstávají viditelné.
3. Spusť **kontrolu připravenosti Hermes bez modelu**. Načte skutečný upstream
   agent v izolaci, ověří pin a oprávnění, nevolá poskytovatele. Nedostatek
   paměti nebo nefunkční izolace musí kontrolu zastavit.
4. Pouze chceš-li AI, nastav vlastní HTTPS OpenAI-compatible API a výslovně
   povol jeho použití. ChatGPT Plus není API účet. Klíč zadávej pouze do
   soukromého nastavení aplikace. Bez souhlasu model neběží.
5. Nahlas konkrétní problém a čas, například „Rádio se právě samo vypnulo.“
6. Ve spisu spusť vyšetřování. Původní Hermes vybírá povolená čtení a další
   důkazy. Logické specializace pracují postupně v jediném workeru.
7. Sleduj český průběh a závěr. Chybějící důkazy musí být přiznané;
   technické podklady jsou v detailu.
8. Posuď přesný původní stav, změnu, důvod, riziko a ruční alternativu návrhu.
   **Provést ručně / Zamítnout** se váží na konkrétní verzi návrhu.
   Produkční provedení opravy tato verze neslibuje.
9. Ověř funkční výsledek podle předem stanovené podmínky a sledovací doby.
   Zmizelá chyba nebo HTTP 200 incident neřeší. Automatické uzavření po živé
   opravě není vydávaná schopnost této verze.

## Volitelné zdroje a limity

Music Assistant má volitelné HTTPS FastMCP `/mcp/v1` a přesné mapování entity
na přehrávač. Pevné čtecí příkazy kontrolují skutečné upstream schéma. Některá
čtení potřebují upstream debug nástroje a buffer událostí. Jejich nedostupnost
je viditelná; alternativou jsou dostupná data HA a Supervisoru. HADS neprovádí
diagnostické změny hlasitosti, přehrávání ani reloady.

ZHA uchovává nejvýše 7 dní / 10 000 softwarových událostí včetně mezer pokrytí.
Neprokazuje nezaznamenaný fyzický stisk. Případný uživatelský test tlačítka
proveď vědomě podle pokynů spisu.

Veřejný výzkum vyžaduje zvláštní souhlas; má pevné zdroje, limit 6 nových
požadavků denně a 6hodinovou cache. Internetové návody nejsou příkazy ani důkaz
příčiny. Model má nejvýše 8 volání na vyšetřování, 12 denně a 1024 výstupních
tokenů na volání. Nejasně dokončené volání blokuje tiché opakování.

## Oprávnění, paměť a zastavení

Core proxy a Supervisor role `manager` mají širší oprávnění než čtení.
Token drží pevný řadič; AI worker jej nedostává. Analytik nemá síťové sockety,
obecný shell, Python nástroj, soubory HA ani zapisovací API. Pomocník spouští jen
pevný izolovaný proces. Řadič běží s UID 65532, worker s UID 65534.
Nezapínej Docker socket, host network, mount konfigurace, další privilegované
capabilities ani vypnutí AppArmor/protection mode.

Hermes běží lokálně, model může být vzdálený. Limit adresního prostoru workeru
384 MiB a rezerva 576 MiB nejsou záruka výkonu celého Raspberry Pi. Běží
nejvýše jeden worker. Deterministický sběr a databáze fungují bez modelu.

Při problému zastav pouze `local_hads_next_investigation`. Původní HADS je
samostatný. Před případným smazáním testovací aplikace exportuj potřebná data;
odinstalace může odstranit její datový svazek. Další kroky jsou v
`hads-next/docs/haos-acceptance.md` a přiložených protokolech.
