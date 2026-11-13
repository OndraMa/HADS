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

## Dostupné kontroly dokončené

Nativní [běh 43378322470](https://github.com/OndraMa/HADS/actions/runs/43378322470)
prošel na AMD64 i ARM64 nad revizí `02fad0672de32f0edda264196800f9f80a3ed482`.
Na každé architektuře prošlo 185 regresí, skutečný Core s původním Hermes,
praktická schvalovaná oprava a verifier, produkční image, paměťová brána, restart,
čistá instalace a celý aktualizační skript nad přesným vydaným RC2 zdrojem.
Aktualizační HA CLI a jeho částečná záloha byly simulované; zdroje, skript,
filesystem kontroly a zachování datového sentinel souboru byly skutečné.

[Prohlížečový běh 43378322338](https://github.com/OndraMa/HADS/actions/runs/43378322338)
také prošel. Snímky jsou z anonymní fixture, ne z domácnosti uživatele.

Obě architektury vytvořily stejný instalátor, SHA-256:
`8a23625c688b4282f2661e6b24000a8e5ce3e7886705b4dd02f33805fe5b13d1`.
Všechny payload soubory odpovídají přesnému testovanému commitu. Trvalé
protokoly a manifest jsou ve složce `evidence/installation-1.0.0-rc3/`.
