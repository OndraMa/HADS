# HADS: audit diagnostiky, zdrojů a bezpečných oprav

## Souhrnný závěr

HADS má potřebné stavební prvky, ale dosavadní sestava nepředstavuje kompletního autonomního opraváře. Rozdíl není jen ve formulaci hlášek. Některé důležité nálezy se při importu ztratily, různé typy důkazů byly považovány za stejnou věc a strukturovaný výsledek AI nenavazoval na kompilaci oprav. Zelený konektor proto mohl sousedit s neúplnou analýzou a množství incidentů s nulou vykonatelných plánů.

Vydání 4.7.0-rc1 opravuje konkrétní části tohoto toku. Nejde o prohlášení úplné funkčnosti na produkčním HAOS. Bez aktuálních odpovědí instalovaných doplňků a ověření skutečné opravy se nedá potvrdit provozní kompatibilita, úspěšná obnova ani úplnost detekce. Samotný úspěch automatických testů tyto důkazy nenahrazuje.

Požadovaný model má být autonomní při sběru a vyšetřování, nikoli svévolný při zápisu. Schválení se musí vztahovat na konkrétní změnu a její rozsah. Nová hypotéza po selhání může vést k novému návrhu; nesmí automaticky zdědit souhlas pro jiný zásah. Úspěšně přijatý požadavek API, dokončený zápis a odstraněná funkční závada jsou tři různé výsledky.

## 1. Referenční případy z projektu HA

Soukromé konverzace „Projekty Francka Nijhofa“ a „Oprava Home Assistant YAML“ dokládají několik odlišných tříd problémů. Nejsou návodem k opakování historických příkazů. Zejména numerická ID řádků databáze ani předpokládané náhrady entit nejsou přenositelné do další opravy. Zjištění vycházejí ze zpřístupněných stran konverzací a dostupného zdroje 4.6.3; nejde o úplný export veškerých zpráv a příloh projektu.[^1]

**Obnovená automatizace bez konfigurace.** V jednom případě nebyla automatizace nalezena v běžném YAML, ale její záznam zůstal v Entity Registry. Současně existovala historie v Recorderu. Správné vyšetření musí rozlišit zdroj konfigurace, registr, obnovený runtime placeholder a historické řádky. Odstranění historie samo o sobě neprokazuje odstranění příčiny. Koncovka `.txt` také není univerzální důkaz neaktivity: rozhodující je, co konfigurace skutečně načítá.[^1]

**Poškozený index statistik.** Hláška `wrong # of entries in index` je konkrétnější než obecné selhání čištění. Kontrola `quick_check` má menší rozsah než úplná kontrola a cizí klíče se ověřují samostatně. Bez konzistentní zálohy a znalosti aktivního schématu není přijatelné opakovat DELETE, vypínat vazby nebo přebírat stará metadata_id. Příčina vzniku poškození může zůstat neznámá i po úspěšném obnovení indexu.[^2]

**Ztráta vzdáleného přístupu po zastavení Core.** Ztráta UI/Ingressu neprokazuje zastavení Tailscale kontejneru. Pro návrh odstávky je však podstatné, že zanikla používaná řídicí cesta. HADS musí před takovou operací ověřit nezávislé spojení a způsob návratu. Oprava, která odřízne jediný kanál ověření, nesplňuje podmínky bezpečného automatického provedení.[^1]

**Reference v dashboardu a role YAML.** Chybějící skript v tlačítku Lovelace představuje jiný problém než vypnutá TV entita. Token `light.is_on` v roli podmínky zase není automaticky entity_id. Nesmí však být globálně ignorován, pokud stojí v opravdovém poli entity_id. Podobnost názvů telefonu je kandidátní vodítko, nikoli důkaz identity zařízení.[^1]

**Funkční Meross s chybou vedlejšího transportu.** Uživatelské pozorování rychlého ovládání je relevantní důkaz, který musí být porovnán s odpověďmi zařízení, protokolem a časem. Nevyvrací každou chybu, ale zpochybňuje závěr „zařízení je nefunkční“. Starý MQTT problém a nová chyba parsování HTTP odpovědi vyžadují odlišnou diagnózu. Není důvod automaticky doporučovat nové párování jen podle slova connection.[^1]

## 2. Diagnostické zdroje a jejich skutečný význam

| Zdroj | Co má přinášet | Co samo o sobě neprokazuje |
|---|---|---|
| Spook / HA Repairs | Konkrétní problém, identifikátory, reference a opravný kontext | Že libovolná hláška má automaticky vykonatelnou opravu |
| Automation Inspector | Vlastník, stav závislostí, kompatibilita, trace, zdroj konfigurace | Že cache získaná přes HTTP 200 je čerstvá |
| Watchman | Podezřelá reference, soubor, řádek, stav | Aktivní použití nebo sémantickou správnost reference |
| HADocs | Seskupené příčiny, postižené objekty, doporučení | Že rodič i všechny děti jsou nezávislé incidenty |
| Entity Availability | Časový průběh dostupnosti sledovaných skupin | Nepoužívanost nebo bezpečnost odstranění entity |
| HAGHS | Vysvětlitelné ukazatele a doporučující příznaky | Funkčnost konkrétní automatizace nebo celé domácnosti |
| Hamster MCP / HA-MCP | Přístup k datům a nástrojům | Samostatné diagnostické uvažování HADS |
| Core / Supervisor / host | Události a provozní kontext různých vrstev | Jednu potvrzenou příčinu podle prvního tracebacku |

### Spook

Zdroj kontroly neznámých odkazů automatizací pracuje s konfigurací a reference filtruje podle známých entit/služeb. Reaguje mimo jiné na načtení komponent, změny registru a reload; nejde pouze o ručně stisknuté tlačítko. Různé kontroly mají vlastní spouštěče a rozsah. Kontrola osiřelých statistik používá validaci Recorderu a vyhledává problém `no_state`; řešení vede ke Statistikám, nikoli k univerzální akci na smazání celé historie.[^3][^4]

Pro HADS z toho plyne nutnost uchovat domain, issue_id, překladové parametry a konkrétní objekty. Prázdný Repairs seznam znamená „tato kontrola nenalezla problém“, nikoli „všechny funkce domu byly otestovány“. Ignorování nálezu musí zůstat odlišné od jeho odstranění a od úspěšné opravy. V 4.7.0-rc1 nevznikl automatický čistič všech Spook nálezů.

### Automation Inspector

Aktuální veřejné schéma v2 obsahuje u automatizací a skriptů pole `entities`, `compatibility_issues` a `trace`. Informace o chybějících závislostech tedy nejsou omezené na kompatibilitu. Zdroj rozlišuje načtení, stav, restored placeholder, dostupnost a původ konfigurace. API poskytuje cache/readiness informace; čerstvost je potřeba posuzovat odděleně od HTTP úspěchu.[^5]

V HADS 4.6.3 byla při převodu zpracována kompatibilita a některé trace chyby, ale chybějící entity/služby z `entities` zůstávaly mimo tento převod. To je konkrétní vysvětlení chybějících nálezů, nikoli domněnka o nedostatečném výkonu CPU. Nové vydání toto pole zpracovává a zachovává kontext konfigurace. Historická diskuse autora na fóru potvrzuje zaměření nástroje na závislosti a jejich stav, ale není specifikací současného API.[^6]

### Watchman

Watchman sám popisuje heuristické hledání odkazů, včetně možnosti falešných pozitivních i negativních výsledků. Současné rozhraní umožňuje strukturovanou odpověď služby a volitelný report do souboru; dokumentace uvádí `force_parsing`, zatímco staré `parse_config` je deprecated. Podpora konkrétních parametrů se musí ověřit v instalované verzi, nikoli hádat podle starého changelogu HADS.[^7]

TXT soubor zůstává použitelnou záložní cestou, ale má slabší sémantiku než strukturovaná data. Cesta reportu není automaticky cestou chybné konfigurace a řádek TXT není řádkem YAML. Nová verze ponechává podezření z archivu/ESPHome viditelné s nižší naléhavostí a požadavkem ověřit aktivní zdroj. Neoznačuje tím libovolný soubor v archivu za bezpečně neaktivní. Komunitní diskuse je zdrojem praktických zkušeností, nikoli důkazem správnosti každého regex nálezu.[^8]

### HADocs

HADocs nabízí root-cause pohled, vazby na zařízení/entity a doporučení. Je proto užitečnější přebírat strukturu nálezu než pouze text názvu karty. Současná dokumentace popisuje i novější experimentální funkce, které nelze automaticky předpokládat u dříve zaznamenané instalace 0.17.0-rc5.[^9]

HADS používá obecnější převod JSON; nová verze zabraňuje opakovanému importu potomků rozpoznaného root-case jako dalších incidentů a stabilizuje identitu při změně textu. Není tím ověřena každá varianta HADocs API ani úplná deduplikace mezi HADocs a jinými poskytovateli. Další požadavek je verzovaný kontrakt se skutečnými anonymizovanými odpověďmi instalace a počty přijatých/odmítnutých nálezů.

### Entity Availability

Integrace sleduje vybrané skupiny, cooldown, dostupnost v časových oknech a podle konfigurace také staleness, baterii a signál. Novější verze rozlišují neesenciální a potlačené entity a ukládají vlastní historii. Sledování neměnného stavu není totéž co sledování posledního reportu: záleží na nastavení a konkrétním zařízení.[^10]

HADS nesmí doporučovat smazání teplotního senzoru jen proto, že několik hodin nezměnil hodnotu, ani poruchu vypnuté TV bez ohledu na její účel. Nový převod neeskaluje historické recovery/non-essential senzory jako aktuální závadu. Surová data poskytovatele zůstávají kontextem. Dlouhodobá nedostupnost může být závažná, ale musí se spojit s očekávanou funkcí, závislostmi a uživatelským záměrem.

### HAGHS

HAGHS zveřejňuje skóre a podrobnosti v atributech senzorů; nepotřebuje vlastní MCP endpoint, aby jej HADS využil. Skóre kombinuje více signálů, například hardware a aplikační údržbu. Nastavení grace period a vyloučení entit ovlivňuje interpretaci. Je to komunitní integrace, nikoli obecné potvrzení od Home Assistant Core.[^11]

HADS má doporučení HAGHS použít jako vodítko a dohledat autoritativní důkaz: skutečnou tlakovou metriku, stav integrace nebo konkrétní nedostupnou entitu. Nemá znovu penalizovat tutéž závadu jednou podle logu a podruhé podle skóre. Diskuse na fóru vysvětluje záměr projektu, nikoli kvalitu konkrétní domácí instalace.[^12]

## 3. Pomohou Hamster MCP a HA-MCP?

Ano, pokud HADS skutečně používá jejich výsledky při vyšetření. Pouhé připojení nebo vypsání katalogu nástrojů nestačí. Hamster vystavuje šest meta-nástrojů: vyhledání, vysvětlení, schéma, provedení příkazu a práci s dokumentačními zdroji. Integrace nabízí přístup k WebSocket/Supervisor schopnostem HA. Dokumentovaný endpoint je `/api/hamster_mcp` přes Streamable HTTP; autentizace může využít Bearer token HA.[^13]

HADS proto musí nejprve získat přesný příkaz a jeho parametry a následně připustit jen známá čtení. V 4.7.0-rc1 je odstraněn nebezpečný předpoklad, že příkaz bez slov „delete“ či „restart“ je čtecí. Například fire_event může vyvolat změny. Nový přesný allowlist zvyšuje bezpečnost, ale úmyslně neznamená plné využití všech Hamster funkcí. Přímé nativní čtení trace může být pro konkrétní účel jednodušší a lépe kontrolovatelné.

HA-MCP má jiný katalog a distribuční varianty. Aktuální dokumentace popisuje také jiný doporučený způsob instalace než starší add-on a používá soukromé adresy s tajnou částí. Nelze univerzálně doporučit port či webhook z jiné verze. Pro existující instalaci je potřeba její přesná adresa, běh služby, autentizace a úspěšná odpověď konkrétního čtecího nástroje. Není vhodné přidávat paralelní instance bez znalosti stávajícího klienta.[^14]

MCP není náhradou diagnostického plánovače. Ani jeden server automaticky neopraví chyby v řazení případů HADS nebo ve ztrátě dat z Inspectoru. Pro první spolehlivý tok má větší hodnotu několik ověřených čtení propojených s konkrétním incidentem než zelené ikony desítek možných nástrojů. Tokeny ani tajné URL se nesmějí ukládat do GitHubu či exportů pro výzkum.

## 4. Proč samotný OpenAI klíč nepřinesl zlepšení

V kódu existuje několik oddělených podmínek: zapnutí OpenAI, přítomnost klíče, povolení placeného výzkumu na pozadí, denní limit a limit na případ. Platný klíč sám nezapíná všechny tyto kroky. Navíc se limit spotřebovává po jednotlivých API požadavcích, nikoli po dokončených incidentech. Při vícekolovém vyšetření může několik případů vyčerpat denní příděl.

Ve výchozím zdroji byl počet kol omezen na tři i při vyšším nastavení. Výstupní schéma vracelo `proposed_actions` jako popisy kroků; plánovač následně hledal `repair_actions` v čitelném textu. To není funkční kompilace oprav. Nové vydání přenáší `analysis` přímo a zavádí samostatné přesné změny, které kontroluje proti živé konfiguraci. Popis opravy databáze tak stále zůstává doporučením, dokud neexistuje podporovaný bezpečný plán.

Oficiální API postup vyžaduje vrátit modelu výsledky nástrojů spolu s odpovídajícím kontextem. Pro stateless režim je dostupný šifrovaný reasoning obsah. Nová verze jej zahrnuje a poslední dostupný krok rezervuje na syntézu. Nevynucuje tím pravdivou diagnózu: model stále potřebuje dostatečné důkazy a může se mýlit.[^15][^16]

Správné provozní ověření musí ukázat dokončený request, použitý model, spotřebu, skutečné nástrojové výsledky a důvod, proč plán vznikl nebo nevznikl. Pokud API odpověď selže autorizací, neplatným modelem, rozpočtem či neúplným výstupem, nesmí UI ukazovat úspěšné AI vyšetření. Bez aktuálního redigovaného výsledku nelze určit jedinou příčinu potíží konkrétního běžícího systému.

## 5. Bezpečný model oprav a opakování

Každý plán musí mít vlastníka a přesný rozsah, důkazy, předchozí/nový stav, riziko, zálohu, návrat a způsob ověření. Před zápisem je nutné znovu ověřit aktuálnost stavu; schválený diff není trvalé oprávnění přepsat pozdější ruční změny. Záloha běžící SQLite databáze musí být konzistentní, nikoli jen kopie hlavního souboru ignorující WAL. SQLite nabízí pro konzistentní kopii vlastní backup API.[^17]

Po selhání čtení je přiměřené omezené opakování s odstupem. Po selhání zápisu musí následovat vyhodnocení, zda byl požadavek přijat, zda změna nastala a zda je potřeba návrat. Timeout neznamená „nic se nestalo“. Nelze bezpečně opakovat mazání či změnu registru bez tohoto rozlišení. Výsledek musí být trvale uložen a odkazovat na původní schválení.

Recorder poskytuje podporované údržbové operace. Ty však neřeší každé poškození databáze a stav řízení/obnovy musí být jasný. Oficiální dokumentace upozorňuje také na souvislosti skutečného poškození se selháním úložiště či napájení. Ani po vyčištění jedné statistiky nelze automaticky prohlásit za zdravý celý Recorder.[^18]

4.7.0-rc1 zachovává zálohovací a schvalovací brány a rozšiřuje pouze omezený převod přesných změn automatizací/skriptů. Nepřidává univerzální autonomní zásahy do registrů, SQL ani libovolného souborového systému. Automatická tvorba následného plánu po každém selhání zůstává nedokončenou oblastí. Jde o podstatné omezení požadovaného cíle, ne o drobnost schovanou za vysokým skóre.

## 6. Priority a deduplikace

Priorita má vycházet z doloženého funkčního dopadu, trvání, opakování a rozsahu. Nespuštěná automatizace vypnutí světel má typicky vyšší užitnou prioritu než jednorázové přerušení diagnostického streamu, ale závažná chyba úložiště nesmí zapadnout jen proto, že světla právě fungují. Restartové okno je kontext, nikoli globální filtr všech chyb.

Deduplikace má dvě úrovně. První sjednocuje opakované reprezentace téže události, například identický traceback v několika reportech. Druhá spojuje související symptomy do kořenového případu a zachovává původ každého důkazu. Stejný název integrace nestačí pro sloučení různých zařízení a různé zdroje nejsou automaticky nezávislá potvrzení, pokud opisují tentýž Repairs záznam.

Nová verze zlepšuje stabilitu identity HADocs a potlačuje rekurzivní děti rozpoznané příčiny. Neřeší kompletní deduplikaci všech poskytovatelů. Dalším akceptačním požadavkem je společná identita podle vlastníka, typu závady a konkrétní reference, s časem pozorování a verzí diagnostického zdroje. Zachování provenance je důležitější než umělé snížení počtu řádků.

## 7. Ověření vydání a další práce

Lokální regresní testy pokrývají konkrétní nové převody, zamítnutí neplatných změn, zachování strukturované analýzy, rozpočet, některé falešné nálezy a stávající schvalovací/zálohovací kontrakty. Výsledek balení zaznamenává verifikační JSON. Živé rozhraní, cílový Docker build a skutečná obnova zálohy tím nejsou otestované.

Pro produkční akceptaci je potřeba vzít alespoň jeden nález od každého důležitého poskytovatele, porovnat jeho data s HADS a provést jednu neškodnou přesnou opravu přes celou schvalovací cestu. Úspěch musí zahrnovat funkční scénář, ne pouze zmizení hlášky. Samostatně je potřeba ověřit výpadek konektoru, nedostupnou zálohu, změnu konfigurace po schválení a nejistý výsledek zápisu v testovacím prostředí.

GitHub má být zdrojem verzovaného kódu, testů, změn a instalačních artefaktů. Nemá být úložištěm API klíčů, databází domácnosti nebo surových logů. Nové změny mají procházet samostatnou větví a přezkoumatelným diffem; nestabilní kandidát nesmí být označen za produkčně ověřený jen proto, že je možné jej stáhnout. Pro úplný požadovaný autonomní systém zůstává nutné dokončit stavový tok následné diagnostiky po selhání, verzované provider kontrakty a živé akceptační scénáře.

## Zdroje

[^1]: Soukromý projekt HA: „Projekty Francka Nijhofa“, „Oprava Home Assistant YAML“, „HADS denní report“, „Oprava automatizace TS0043“ a „Zjednodušení HADS HABS HEDS“. Zpřístupněné nedávné zprávy; neúplné přílohy a stránkování. Historické asistentské rady nejsou považovány za ověřené postupy. Technické srovnání: lokální zdroj HADS 4.6.3 a diff 4.7.0-rc1.
[^2]: SQLite, [PRAGMA integrity_check / quick_check / foreign_key_check](https://sqlite.org/pragma.html). Dokumentace rozsahu kontrol, ověřeno 10. 9. 2026.
[^3]: Frenck a přispěvatelé, [Spook: unknown_entity_references.py](https://github.com/frenck/spook/blob/main/custom_components/spook/ectoplasms/automation/repairs/unknown_entity_references.py). Větev main, ověřeno 10. 9. 2026; nemusí odpovídat každé instalované verzi.
[^4]: Frenck a přispěvatelé, [Spook: orphaned_statistics.py](https://github.com/frenck/spook/blob/main/custom_components/spook/ectoplasms/recorder/repairs/orphaned_statistics.py). Větev main, ověřeno 10. 9. 2026.
[^5]: ITSpecialist111, [Automation Inspector README](https://github.com/ITSpecialist111/Automation-Inspector/blob/main/README.md) a [dependency_map.py](https://github.com/ITSpecialist111/Automation-Inspector/blob/main/automation_inspector/app/dependency_map.py). Schema v2, zdroj main, ověřeno 10. 9. 2026.
[^6]: ITSpecialist111, [Automation Inspector and diagnostics — Add-on](https://community.home-assistant.io/t/automation-inspector-and-diagnostics-add-on/894168), Home Assistant Community, příspěvek 24. 5. 2025. Historický záměr, nikoli současný kontrakt API.
[^7]: dummylabs, [Watchman README](https://github.com/dummylabs/thewatchman/blob/main/README.md). Současná dokumentace parsování, služby a omezení, ověřeno 10. 9. 2026.
[^8]: Home Assistant Community, [Watchman — keeps track of missing entities and actions](https://community.home-assistant.io/t/watchman-keeps-track-of-missing-entities-and-services-in-your-config-files/390391). Praktický kontext; technické závěry ověřovány primárně proti projektu.
[^9]: SirBlondieDK, [HADocs README](https://github.com/SirBlondieDK/HADocs/blob/main/README.md). Main, ověřeno 10. 9. 2026; současné funkce nelze zaměnit s instalovanou 0.17.0-rc5.
[^10]: italo-lombardi, [Entity Availability README](https://github.com/italo-lombardi/Home-Assistant-EntityAvailability/blob/main/README.md). Konfigurační význam skupin, stáří a senzorů, main, ověřeno 10. 9. 2026.
[^11]: HA-Pulse, [Home Assistant Global Health Score](https://github.com/HA-Pulse/home-assistant-global-health-score). Dokumentace atributů a konfigurace, ověřeno 10. 9. 2026.
[^12]: Home Assistant Community, [HAGHS — Global Health Score](https://community.home-assistant.io/t/haghs-global-health-score-is-your-instance-truly-healthy-featured-on-how-to-geek/985573). Diskuse návrhu, nikoli akceptační test.
[^13]: altendky, [Hamster MCP README](https://github.com/altendky/hamster-mcp/blob/main/README.md) a [meta-tools implementation](https://github.com/altendky/hamster-mcp/blob/main/src/hamster_mcp/mcp/_core/tools.py). Endpoint, autentizace a nástroje, ověřeno 10. 9. 2026.
[^14]: homeassistant-ai, [HA-MCP README](https://github.com/homeassistant-ai/ha-mcp/blob/master/README.md). Aktuální distribuce a možnosti, ověřeno 10. 9. 2026; odlišit od staršího instalovaného add-onu.
[^15]: OpenAI, [Function calling](https://developers.openai.com/api/docs/guides/function-calling). Předávání výsledků nástrojů a kontextu modelu, ověřeno 10. 9. 2026.
[^16]: OpenAI, [Create a model response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create). `reasoning.encrypted_content`, `store` a výstupní limit, ověřeno 10. 9. 2026.
[^17]: SQLite, [Online Backup API](https://sqlite.org/backup.html). Konzistentní kopie databáze, ověřeno 10. 9. 2026.
[^18]: Home Assistant, [Recorder](https://www.home-assistant.io/integrations/recorder/). Údržba a selhání úložiště, ověřeno 10. 9. 2026.
