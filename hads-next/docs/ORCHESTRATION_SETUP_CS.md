# Jednorázové nastavení orchestrace po RC7

Tento postup popisuje zdrojovou větev PR #19. **Nové RC ani instalační balíček zatím nejsou vydané.**
Instalovaná RC7 tyto nové stránky a adaptéry ještě neobsahuje. Neměň kvůli tomuto dokumentu produkční instalaci.

## Co HADS zajistí sám

Po ověření vlastníka běží nativní sběr, korelace a výběr dostupných čtecích nástrojů bez AI.
Inspector/HADocs se vyhledají přes skutečný inventář a hostname Supervisoru a doložené interní porty.
Pokud interní rozhraní skutečně není dostupné, nastaví se jednou jeho privátní původ; HADS nepožaduje ruční diagnostické příkazy.
ZHA/Toolkit, Spook Repairs, Watchman, HAGHS a Entity Availability používají již dostupné HA připojení.
Pro samotný sběr není potřeba OpenAI klíč ani další samostatný Hermes.

## HA-MCP

1. V nástrojích HADS vyber `ha_mcp`. Použij skutečný endpoint z již nainstalovaného HA-MCP, bez odhadování callback URL.
   Endpoint s privátní cestou je přístupový údaj; patří jen do privátního formuláře HADS.
2. Povol diagnostické připojení. Pro lokální HTTP je nutný výslovný souhlas se soukromou sítí; HTTPS se ověřuje a redirecty se odmítají.
3. Ponech TLS, serverové bezpečnostní zásady a přísný režim osvědčených postupů zapnuté.
   Nepovoluj Python transformace, shell, sandbox vlastních nástrojů ani obecné souborové operace kvůli HADS.
4. HADS ověří initialize, stránkované tools/list a podle potřeby ha_search_tools s přesnými názvy funkcí.
   Potom provede konkrétní dovolené čtení k danému spisu. Katalog není funkční výsledek.
5. Read-only server je vhodný pro diagnostiku. Pokud má být později dostupná konkrétní oprava automatizace,
   server musí též povolit `ha_config_set_automation` a `ha_get_skill_guide`. Samotné vypnutí serverového read-only není schválení.
   Zapisovací spojení i jeho credential má pouze kontroler; Hermes k němu přímo přístup nemá.
6. Přísné best-practices ochrany se nevypínají. HADS načte skutečný referenční soubor, respektuje jeho receipt
   `BestPracticeKey` a váže jej na plán. Když se pravidla nebo receipt změní, předloží nový plán místo skrytého retry.
   Nástroj nevolá s `MandatoryBPS=false`, Python transformací ani `run_actions=true`.

## Nativní MCP a Hamster

Nativní MCP se může připojit přes stávající Supervisor proxy, pokud daná verze tuto cestu podporuje;
jinak se jednou nastaví skutečné URL z HA. Uplatňuje se skutečný katalog a pouze ověřená čtecí podmnožina.
MCP Client v HA je opačný směr; není potřeba propojovat HA klienta zpět do jeho vlastního agregátoru.

Hamster vyžaduje vlastní skutečný endpoint. HADS čte schema pro konkrétní nativní příkazy a používá
jen nezávisle povolené parametry. Obecný Hamster call ani všechny jeho služby se neposkytují modelu.

## Staré připojení Hermes RC3

Načti soukromý neaktivní návrh a potvrď aktivaci jednotlivého vybraného konektoru v Nástrojích servisního týmu.
Nepřenášejí se AI souhlasy, náklady, oprávnění k zápisu nebo stará tvrzení o úspěšném ověření.
Starý Hermes se kvůli přenosu nespouští a jeho instalace se nemění.

## Hermes a AI

Původní NousResearch Hermes zůstává součástí stejné aplikace a stejné izolace. Zachovává se limit 32 vstupních
nástrojů, paměťová rezerva 576 MiB, jeden worker a stávající nákladové limity. Další funkce vybírá přes společný broker,
nikoli přidáváním neomezených MCP serverů do jeho konfigurace.

AI povol až výslovně v privátním nastavení pro malý test. Klíč neposílej do chatu. Vyčerpaný rozpočet zachová spis
a zastaví další modelové požadavky; diagnostická čtení pokračují. Pro skutečný diagnostický úsudek je nutná
samostatná živá přejímka s autorizovaným modelem. Skriptovaný endpoint ji nenahrazuje.

## Co lze povolit k opravě

Oprava se schvaluje až jako neměnný konkrétní plán. Stránka ukazuje poskytovatele, funkci, parametry, původní stav,
změnu, důkazy, riziko, zálohu, funkční test a návrat. Potvrdíš požadovanou změnu a výlučnou práci s cílem;
HADS provede podporovanou operaci jednou. Úspěšný příkaz ještě neznamená vyřešený případ.

Povolování entity přes Spook není univerzální Zigbee oprava. Je to výslovné rozhodnutí, že daná uživatelem
zakázaná entita má opět běžet. Vypnutí entity se nenabízí jako způsob odstranění upozornění; je jen součástí
samostatně schváleného návratu předchozího povolení.

Změny registrů/konfigurace vyžadují nezávislý podepsaný důkaz skutečné obnovy OneDrive zálohy.
**Propojení se skutečným ověřovatelem HABS/OneDrive není tímto zdrojovým PR doložené.**
Testovací podpis z CI se nesmí instalovat do domácnosti jako důvěryhodný klíč. Bez skutečného důkazu se rizikový plán
nevydává za připravený. Toto není problém, který by vyřešilo povolení všech nástrojů.

Statistiky, reporting, binding, kanál a obecné změny registrů nejsou otevřený write katalog. U každé další operace
musí vzniknout vlastní kontrakt, doložená náprava, záloha a funkční ověření. Kde to chybí, zůstává konkrétní
ruční alternativa nebo další automatické čtení; nevydává se falešná oprava.
