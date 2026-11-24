# HADS Hermes 2.0.0-rc2 — RPi 4B / HAOS aarch64

Tato verze odstraňuje závislost na Landlock ABI 4. Zachovává skutečný místní
Hermes Agent; jazykový model stále používá stávající OpenAI API přes bránu HADS.
Nepotřebuješ instalovat software do Windows, rclone ani další Hermes doplněk.

## Instalace

Instalátor přenes do `/config` a spusť shellem, nikoli Pythonem:

```sh
bash /config/HADS_Hermes_install_2.0.0-rc2.sh
```

Na tvou dřívější výslovnou žádost instalace nevytvoří novou HA/OneDrive zálohu.
Místní kopie zdrojů není záloha databáze ani systému. Povinné cloudové zálohy
před opravami zůstávají. Slug `local_hads4`, databáze a nastavení jsou zachované.
Nepouštěj dvě verze současně nad stejnou DB.

Instalátor v terminálu ověří Linux/64 bitů, ale neslibuje tím funkčnost cílového
kontejneru. Obraz se sestaví se skutečným Hermes smoke testem. Pokud test selže,
neobcházej ochranu ani nevypínej protection mode. První sestavení potřebuje
internet a více úložiště než starý Alpine obraz; na RPi může být pomalé.

## Nejdříve bez placení

1. Nech `ai_paid_calls_enabled` a `ai_paid_web_enabled` vypnuté.
2. Ověř start doplňku, panel RC2, otevření incidentu a načtení zdrojů.
3. Zkontroluj aktuální volnou RAM. Hermes má pevný limit virtuální paměti
   384 MiB, vyžaduje nejméně 576 MiB dostupné rezervy (384 + 192 pro systém),
   jeden pracovník, omezené počty kroků a čas. Nedostatek paměti
   analýzu odloží bez API volání; nepovažuje se za zdraví vyšetřovaného případu.
4. Teprve potom povol existující OpenAI klíč, placení a podle potřeby
   `ai_background_research`. Klíč sem do chatu neposílej.
5. Začni 6 požadavky za 24 h, 2 na incident a nejvýše 3 kroky. Web povol zvlášť.
   Toto není dolarová záruka: účtovány mohou být i vzdáleně neúspěšné požadavky.

## Jaká izolace skutečně běží

Chroot obsahuje jen interpreter, závislosti a připnutý Hermes, ne `/data`,
`/homeassistant`, `/share` nebo `/proc`. Worker zahodí root a capabilities.
Seccomp zakazuje nové síťové spojení, sockety, spouštění procesů a privilegované
operace. Po trusted inicializaci se zakážou také zápisy do souborů, včetně
ostatních vláken. Každý krok před API ověří negativní přístupové testy.

Modelová komunikace používá jeden již připojený descriptor k ověřené rodičovské
bráně. Skutečné API/Supervisor klíče zůstávají v rodiči. HADS provádí validovaná
čtení; Hermes sám nemá shell, automatické skills ani opravné nástroje.
Nejde o VM. Při selhání izolace je požadavek zastaven, ne spuštěn bez ochrany.

## Doplňky a opravy

HA-MCP/Hamster zůstávají read-only diagnostické zdroje. Nastavení popisuje
`HA_MCP_NASTAVENI_CS.md`. Spook Repairs, Watchman report, HADocs, Automation
Inspector, Entity Availability a HAGHS využívají zachované adaptéry. Nainstalovaný
doplněk neznamená ověřené spojení ani čerstvá diagnostická data.

Přijetí závěru není oprava. Spuštění vyžaduje konkrétní plán, tvoje schválení,
novou zálohu a nezávislé OneDrive ověření. Při selhání se zaznamená důvod a
další diagnostika, nikoli falešné potvrzení úspěchu.

## Co zbývá ověřit po instalaci

Skutečný HAOS profil, souběh ostatních doplňků na 2GB RPi, přístup konektorů,
OneDrive readback a výsledek konkrétní schválené opravy. Cloudové testy tato
živá ověření nenahrazují. Měření a přesné omezení RAM: `VERIFICATION_RC2.md`.
