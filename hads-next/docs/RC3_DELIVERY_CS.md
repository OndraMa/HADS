# HADS Next 1.0.0-rc3 — opravný kandidát

Základ: RC2 a oprava přehledu z PR 9. Nová větev `codex/hads-next-rc3`.
Starý Hermes 2.0.0-rc3 ani již vydané RC1/RC2 se nemění.

## Opravy

Přehled má jednu navigaci, konkrétní názvy aplikací, oddělené funkční případy,
čekající kroky, ověřené výsledky, opakování a jasný stav AI. Staré obecné titulky
se zobrazují s přečteným názvem aplikace bez přepsání původních důkazů.

Supervisor `error` může následovat po úmyslném zastavení. Samotný tento údaj
proto není potvrzená funkční porucha a sám nezahajuje placené AI vyšetřování.
Stavový nález zůstává dohledatelný; není smazaný ani označený za vyřešený.
Uživatelem nahlášený skutečný problém a podporované plány zůstávají viditelné.

Paměťový nález neoznačuje jiné aplikace za oběti nedostatku paměti bez důkazů.
Průvodce ukazuje i odstup od 576 MiB. Brána se nesnižuje. Uživatel již doložil
vzorek 583 MiB a následný pokles pod rezervu; AI má zůstat vypnutá.

## Obsah

Původní Hermes je součást výsledné image aplikace; stavba stáhne přesný upstream
pin a constraints. Není nutná druhá HA aplikace Hermes. Jsou přiložené nativní
HA/Core/Supervisor/OS adaptéry, Music Assistant FastMCP klient, ZHA žurnál,
research role a původní oddělený opravný katalog s owner approval a verifierem.

MCP adaptér neobsahuje externí Music Assistant server ani jeho token. Spook,
Watchman a HA-MCP se automaticky neinstalují; nativní srovnatelná data se čtou
bez jejich povinné instalace. Přesný rozsah je v `INTEGRATIONS_CS.md` přiloženém
vedle instalačního návodu. Nelze vydávat přiložený adaptér za živě ověřené spojení.

## Instalace a přechod z RC2

V balíčku je český návod `HADS_Next_1.0.0-rc3-navod-CS.md`. Pro stávající
`local_hads_next_practical` použij výslovný `--upgrade-rc2`, nikoli uninstall.
Nejprve zastav jen Next RC2. Aktualizátor vyžaduje ověřenou vydanou sadu zdrojů,
nezměněné hashe a stav `stopped`; cizí či upravené zdroje odmítne.

Aktualizace zachovává identitu, `/data`, spisy a nastavení. Vytváří ověřený archiv
původních zdrojů a žádá nativní částečnou zálohu aplikace přes `ha apps update
--backup`. Záloha zdrojů není záloha dat; částečná záloha není nezávislá obnova
celého HAOS/OneDrive. Nejasný výsledek blokuje tichý retry a automatický restore.
Po potvrzení RC3 zůstává aplikace zastavená; vlastník ji spustí ručně.

Nová instalace používá `--install-dev`, stejný slug brání souběhu dvou Next.
Kompletní ZIP obsahuje aktuální HADS Next zdroje, návody a důkazy. Historické
vydané archivy se do ZIPu nerekurzují a zůstávají samostatně na GitHubu.

## Co není přijato

Není dostupný autorizovaný skutečný LLM ani přímé cloudové spojení do HAOS.
Reálný úsudek modelu, fyzické rádio/Zigbee, externí MA FastMCP server, nezávislá
OneDrive obnova a Raspberry Pi při souběžné zátěži proto nejsou označené jako
ověřené. Uživatel doložil první nativní čtení RC2 s Core 2026.11.1, což není
kompletní přejímka RC3. První živá etapa ponechá AI i opravy vypnuté.

Přesný nativně testovaný zdroj, hashe instalátoru a výsledky obou architektur
jsou ve verzovaném `docs/evidence/installation-1.0.0-rc3/ACCEPTANCE.json`.
Kandidát se publikuje až po úspěchu dostupných kontrol. Instalace a opravy
nebyly prováděné v uživatelově domácnosti.
