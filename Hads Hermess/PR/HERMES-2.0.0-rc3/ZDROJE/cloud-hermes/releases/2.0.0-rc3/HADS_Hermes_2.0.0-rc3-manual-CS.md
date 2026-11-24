# HADS Hermes 2.0.0-rc3 — zapojení diagnostických zdrojů

## Co tato verze přidává

Hermes může během rozboru incidentu požádat o důkazy od konkrétního zdroje pomocí `hads_read_diagnostic_source`. Nepotřebuje dostat obecné oprávnění k libovolnému MCP příkazu. Čtecí kroky zařízení, protokolů a případné automatizace se ukládají do SQLite a jsou dostupné v detailu incidentu → Důkazy. Zobrazují dokončení, neúplnost, selhání a přerušení restartem. Stejný obsah s novým časem sběru není nový nezávislý důkaz.

Na RPi 4B se 2 GB běží kroky postupně. Jde o skutečné konkrétní čtecí funkce a jednoho koordinátora Hermes; tato verze nespouští několik nezávislých Hermes agentů současně. Hermes je skutečný lokální agent, modelové uvažování používá placené vzdálené API, pokud je výslovně zapnete. Lokální běh agenta neznamená lokální jazykový model.

## Instalace

Zkopírujte instalátor do `/config` a spusťte v terminálu HA:

```bash
bash /config/HADS_Hermes_install_2.0.0-rc3.sh
```

Instalátor na dřívější výslovnou žádost nevytváří novou předinstalační HA/OneDrive zálohu. Záloha před skutečnými opravami zůstává povinná. Po instalaci obnovte panel a nejdříve ponechte placenou AI vypnutou. Ověřte načtení panelu, aktuální čas posledního sběru, přístup ke konkrétnímu incidentu a konektory. Instalace ani offline testy samy neověří přístup k vašemu HAOS a OneDrive.

## Které zdroje HADS používá

| Zdroj | Použití | Co ověřit |
|---|---|---|
| HA Core / Supervisor / Host | Protokoly, skutečný inventář, stavy, Recorder historie, uložené traces, prostředky kontejnerů | HADS má potřebná čtecí oprávnění; historické logy/traces musí ještě existovat. RAM kontejneru není RAM procesu. |
| Spook | Aktivní položky Home Assistant Repairs | Spook je načtený v HA. Prázdný seznam Repairs není důkaz, že všechny automatizace fungují. |
| Watchman | Strukturovaná odpověď služby report, případně TXT report; odkazy na chybějící entity a akce | Služba `watchman.report` existuje; TXT fallback je dostupný jako `/config/watchman_report.txt`. HADS rozlišuje stáří reportu a nepočítá TXT a strukturovaný report jako dvě sady nálezů. |
| Automation Inspector | Podporovaný čtecí JSON report a konkrétní nálezy | Nastavte skutečné čtecí API a případný token podle vaší verze. UI Ingress URL není automaticky JSON API. HTTP 401/403 znamená chybějící přístup, nikoli zdravý doplněk. |
| HADocs | Podporovaný čtecí JSON report; relevantní nálezy a vztahy | Nastavte čtecí URL a token, pokud je vaše instalovaná verze poskytuje. Samotná instalace neposkytne všechny údaje z UI. |
| Entity Availability | Dostupné související entity/stavy a diagnostické nálezy | Integrace musí publikovat data v HA. Žádné odhadované univerzální REST API se nezavádí. |
| HAGHS | Skutečné číselné zdravotní senzory a související nálezy | Dostupné senzory jsou kontext, nikoli nezávislá autorita potvrzující každou příčinu. |
| HA-MCP | Povolená čtení podle ověřeného katalogu a schémat | Přímý MCP endpoint a token; nikdy samotná adresa panelu. |
| Hamster MCP | Vyhledání a ověření podporovaných čtecích cest | Přímý MCP endpoint; tato verze nepovoluje všechny obecné příkazy ani změny konfigurace. |
| Music Assistant MCP | Nově omezené čtení `fastmcp/debug/health` a `fastmcp/debug/recent_events` | Podporovaná verze pluginu FastMCP Server, konkrétní URL a diagnostický token. Není automaticky připojen ke každé verzi Music Assistantu. |

Home Assistant Digest ani Codex Terminal nejsou novou povinnou závislostí. Zelený stav instalace či ověření spojení sám o sobě není důkaz funkčního zařízení. HADS může používat pouze informace, které daný doplněk skutečně poskytne přes podporované rozhraní; úplné využití každé funkce libovolné verze doplňku tento kandidát neslibuje.

## HA-MCP

1. V HA-MCP otevřete nastavení serveru a zjistěte přímý MCP endpoint dostupný z kontejneru HADS. Nekopírujte časově omezenou Ingress adresu panelu.
2. Pro HADS vytvořte vlastní token a povolte čtecí diagnostiku: vyhledávání, aktuální stav, historie, informace o entitě, traces automatizací a systémové údaje, pokud je daná verze podporuje.
3. Do nastavení HADS vložte `ha_mcp_url` a případný `ha_mcp_token`. Token nevkládejte do chatu.
4. V Diagnostických zdrojích spusťte ověření. Katalog nástrojů znamená dostupné rozhraní; teprve konkrétní úspěšné čtení je použitý důkaz.
5. Když některý název neexistuje, HADS nesmí vymyslet parametry ani použít obecný zapisovací nástroj. Nativní HA čtení zůstává samostatným zdrojem.

## Hamster MCP

1. Zjistěte přímou adresu MCP serveru a způsob autorizace vaší instalace.
2. Vyplňte `hamster_mcp_url` a `hamster_mcp_token` v HADS.
3. Povolte diagnostická čtení, ne obecné spouštění služeb, editaci souborů nebo shell.
4. HADS vyhledá konkrétní podporovanou cestu a ověří její schéma. Pro případy Repairs/Spook požádá o podporované Repairs, pro Zigbee/baterii/signál o registr zařízení a pro problémy integrace o podporované údaje o konfiguraci. Pokud cesta potřebuje neznámé povinné parametry, čtení se odmítne místo odhadu.

## Music Assistant MCP — volitelné

Oficiální dokumentace: https://www.music-assistant.io/plugins/fastmcp-server/

1. Ve verzi Music Assistantu s pluginem FastMCP Server otevřete Settings → Plugins → Add Plugin → FastMCP Server.
2. Přes Connect Wizard vytvořte samostatného klienta HADS a získejte skutečnou URL a token. Nepoužívejte odhad portu ani adresu přehrávače.
3. Povolte pouze diagnostické schopnosti potřebné pro health a recent events. Ovládání přehrávání, reload providerů a zápisy konfigurace HADS tímto konektorem nepovoluje.
4. V HADS vyplňte nové položky `music_assistant_mcp_url` a `music_assistant_mcp_token`. Prázdná adresa znamená vypnuté propojení.
5. HADS při relevantním hudebním incidentu použije discovery → schéma → konkrétní čtení, nejvýše šest RPC požadavků pro jeden sběr. Chybějící plugin, rozhraní nebo oprávnění je mezera v důkazech, nikoli zdravý stav.

Konektor aktuálně používá dvě diagnostická čtení. Neprovádí přehrávání jako test a nečte veškeré interní informace Music Assistantu. Server může funkce omezovat podle tokenu a verze.

## Hermes, cena a schvalování

Hermes zůstává připnutý na otestovaný upstream v0.22.2. Nové vydání upstreamu se automaticky nestahuje. Zachovává se izolace chroot + neprivilegovaný uživatel + seccomp, bez předávání HA/OpenAI tajemství workeru, bez shellu a bez volného síťového přístupu workeru.

Paměťová hranice workeru je 384 MiB a start vyžaduje alespoň 576 MiB dostupné RAM. Jeden worker současně. Nedostatek rezervy se zobrazí jako odložená analýza; nevypínají se ochrany. Skutečný HAOS AppArmor/seccomp profil je nutné ověřit až na vašem zařízení.

Placená AI a placené webové hledání mají oddělené výslovné povolení. Samotné vložení API klíče je nezapne. Limity požadavků přežijí restart; počet požadavků není peněžní limit. Nastavte samostatný API projekt/klíč a kontrolujte skutečnou spotřebu u poskytovatele. Vývojové testy této verze nevolají placený model.

Hermes navrhne další čtení nebo strukturovaný závěr. Závěr není oprava. Konkrétní vykonatelný plán připravuje a kontroluje HADS, vy jej schválíte či zamítnete. Před zápisem musí být ověřená OneDrive záloha, poté následuje provedení a ověření. Selhání zůstává v historii. Nelze garantovat správnost každé hypotézy ani automatickou opravu každé závady.
