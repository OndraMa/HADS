# HADS Next 1.0.0-rc10

Instalační kandidát PR #19 pro přejímku. Rozsah zdrojových změn, laboratorní
důkazy a zbývající kontroly jsou v [přejímce](ORCHESTRATION_LIVE_ACCEPTANCE_CS.md)
a [matici PR](PR19_ACCEPTANCE_MATRIX_CS.md). Předchozí distribuční soubory zůstávají uložené.

## Co nastavit jednou

| Zdroj | Nastavení | Jak poznat funkční čtení |
|---|---|---|
| HA Core, Supervisor a HAOS | Použij oprávnění nainstalované aplikace přes Supervisor. Vlastní token se do HADS nezadává. | Ve **Zdroje a připravenost** je úspěšné čtení. Ve spisu HADS ukáže konkrétní použité zdroje. |
| HA-MCP | V nastavení stávající integrace HA-MCP Server zkopíruj její připojovací URL dosažitelnou z HAOS. V **Nástroje servisního týmu → Jednorázové připojení** vyber `ha_mcp`, vlož adresu do soukromého pole a povol diagnostické připojení. Při soukromém LAN HTTP potvrď tento režim. Bearer token vyplň pouze pokud ho daná adresa vyžaduje. U tajné cesty stačí adresa. | **Vlastní diagnostická odpověď přečtená: ano** znamená konkrétní ověřený stav entity. Pokud ověření selže, karta ukáže fázi a dostupné další kroky. Už funkční uložené připojení lze ponechat. |
| Nativní Home Assistant MCP server | HADS nejdřív zkusí podporovanou cestu přes Supervisor. Pro ruční konfiguraci vlož URL serveru z HA pod `native_mcp`. Použij odpovídající token, pokud ho server vyžaduje. | Katalog a skutečné čtení jsou samostatné údaje. MCP Client v HA není předpoklad diagnostiky HADS. |
| Watchman, Spook, Entity Availability a HAGHS | Ponech funkční registraci v Core a dostupné relevantní senzory. Samostatná URL se nezadává. | Watchman poskytne obsah existujícího reportu, Spook společné Repairs a dostupné služby. Entity Availability a HAGHS poskytují údaje z dostupných entit. |
| Automation Inspector a HADocs | HADS zkusí interní adresu z potvrzeného inventáře Supervisora. Když automatické zjištění selže, použij **Jednorázové připojení**, vyber příslušný nástroj a zadej jeho dosažitelný HTTP(S) původ bez cesty. Token jen podle nastavení daného serveru. | Inspector musí vrátit podporovaný platný report. HADocs musí vrátit analýzu. U každého se zobrazuje, zda je doložen skutečný čas reportu. |
| ZHA a ZHA Toolkit | Žádná další URL. Registry a podporovaná čtení se získávají přes Core. | Ve spisu se zobrazí data přiřazená k cílovému zařízení. HADS neskenuje síť, nepřepárovává a nemění reporting ani binding. |
| Music Assistant | Pro nativní historii, akce a protokol potvrzené aplikace přes Supervisor se nezadává nic. Volitelné FastMCP lze nastavit přes **Zdroje a připravenost → Nastavit volitelnou diagnostiku Music Assistantu**. Tento konektor vyžaduje dosažitelnou HTTPS adresu s cestou `/mcp/v1`, token Music Assistantu a vazbu HA entity na ID přehrávače. | HADS ve spisu rozliší doloženou souvislost akcí a stavů od chybějících podkladů. FastMCP vyžaduje vlastní platnou diagnostickou odpověď. |
| Hermes | Místní diagnostika funguje bez klíče. Pro modelové vyšetřování nastav soukromě poskytovatele, model a rozpočet v **Zdroje a připravenost → Nastavit poskytovatele AI**. Automatiky s náklady vyžadují samostatný souhlas. | Kontrola izolace je samostatná. Spuštění modelu navíc vyžaduje paměťovou rezervu 576 MiB. |
| Obnova záloh | Vyplň soukromé nastavení ověřovatele pouze tehdy, pokud nezávislá služba skutečně vystavuje kompatibilní doklad o obnově. | HADS ověří podpis, stáří, rozsah a původní stav cíle před zásahem. Kompatibilní rozhraní HABS k vydání tohoto dokladu dosud není doložené. |

URL s tajnou cestou a tokeny zadávej jen do soukromých polí v HAOS. U HA-MCP použij existující
instalaci serveru. Oprávnění připojení umožní nabídnout podporované operace, ale zápis provede
vykonavatel až po schválení přesného plánu. Katalog zatím obsahuje cílené povolení entity
a změnu doložené světelné reference podle dostupného poskytovatele a uvedených předpokladů.

Původní Hamster se při startu vyřadí z aktivních připojení HADS. Ostatní nastavení zůstává.
Typy relací a nástroje jsou popsané v [HA-MCP](https://homeassistant-ai.github.io/ha-mcp/)
a [Music Assistant FastMCP](https://www.music-assistant.io/plugins/fastmcp-server/).

## Co probíhá bez ručního dohledávání

Při výpadku Zigbee HADS spojí registr entit s daty nativního ZHA a ZHA Toolkitu pro stejný cíl.
U případu rádia čte historii přehrávače, dostupnou historii akcí a protokol odpovídající aplikace
Music Assistant. Shoda kontextového ID může doložit stop příkaz. Samotný výřez protokolu nebo
časová shoda nedokládá původ závady. Pokud chybí příčina, spis uvádí nejistotu.

Změny veřejného dashboardu, obecné úpravy registru a YAML, zápisy statistik a zásahy do Zigbee
nejsou v katalogu schvalovatelných oprav. Volitelná připojení mohou být nedostupná nebo vrátit
neslučitelné schéma. Spis ukáže chybějící zdroj a pokračuje dostupnými čteními.
