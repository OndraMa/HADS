# HA-MCP, Hermes a diagnostické doplňky — nastavení pro HADS

Ověřeno ze zdrojů 14. 11. 2026. Toto je návod pro RC6 a popis jeho hranic.
Připojené aplikace na skutečném HAOS nebyly z tohoto vývojového prostředí autentizovaně testované.
Nativní čtení HADS fungují bez AI klíče. Samotná konfigurace nenahradí chybějící adaptér.

## 1. Co již HADS automaticky čte

Po přihlášení vlastníka otevři **Zdroje a připravenost → Doplňky a ověření**.
Kontrola se opakuje přibližně každých pět minut. Není potřeba zadávat příkazy do terminálu.

| Zdroj | Dostupné čtení v RC6 | Co tím není ověřeno |
|---|---|---|
| Core a Supervisor | Verze, stavy, seznam aplikací, registr entit/zařízení, Repairs, System Health; podle incidentu statistiky a protokoly | Samotný úspěch HTTP nepotvrzuje funkci domácnosti |
| Spook | Načtená komponenta, vlastní entity, sdílené Repairs | Registr/statistiky nelze tímto katalogem opravovat |
| Watchman | Počty **i atributy s odkazy**, stav, skutečný čas aktualizace a parsování; společný diagnostický spis | Statická reference není důkaz poruchy ani automaticky bezpečná oprava |
| Entity Availability | Entity vlastněné integrací a jejich vybrané stavy | Kompletní časová historie a očekávání jednotlivých zařízení |
| HAGHS | Také vlastníkem určený `sensor.system_ha_global_health_score` | Jedna entita neurčuje totožnost/verzi celého projektu |
| Automation Inspector / HADocs | Aktuální inventář aplikací, stav a dostupná verze | Jejich vlastní diagnostické HTTP reporty zatím HADS nepřipojuje |
| HA-MCP / Hamster MCP | Přítomnost komponenty/aplikace a vlastní entity | MCP autentizace, `tools/list` a konkrétní čtení zatím nemají obecný aktivní adaptér |
| Music Assistant | Volitelný omezený FastMCP adaptér, samostatné nastavení | Obecné změny přehrávání ani prověření všech providerů |

Počet „9 z 9 zdrojů“ označuje nativní čtení HADS, **nikoli devět funkčně ověřených externích doplňků**.
Přítomnost, spuštěný proces, autentizace, konkrétní úspěšné čtení a funkční výsledek jsou různé stavy.

RC6 opravuje odmítání platných identifikátorů aplikací s pomlčkou. Jeden neplatný řádek už nezruší ostatní.
Pokud stále chybí vlastní report Inspectoru/HADocs, není tím prokázaná chyba jejich instalace.

## 2. HA-MCP: nastavení serveru

Otevři **Nastavení → Aplikace → HA-MCP → Otevřít webové rozhraní**.
Názvy odpovídají doloženým obrazovkám a aktuálnímu upstreamu; starší verze nemusí mít všechny volby.
Zobrazené „Verze serveru MCP“ je nastavitelné pole a samo nepotvrzuje verzi instalovaného kódu.

1. Na **Nastavení serveru** ponech **Ověřit certifikáty TLS** a **Povolit WebSocket** zapnuté.
   Nevypínej TLS kvůli připojení. Nezveřejňuj port serveru do internetu jako náhradu autentizace.
2. Zapni **Redigovat tajemství**. **Režim ladění** a **Diagnostika HTTP přenosu** nech vypnuté pro běžný provoz.
   Redakce serveru je další ochrana; HADS musí stále promítat jen povolené důkazy.
3. Pro nynější diagnostické použití zapni **Režim pouze pro čtení**.
   Vypni nepotřebné **beta úpravy YAML**, nástroje souborového systému a sandbox vlastních nástrojů.
   Široké oprávnění všech nástrojů není podmínkou diagnostiky.
4. **Povolit zásady zabezpečení nástrojů** ponech zapnuté.
   **Přístup k bezpečnostním zásadám vývojářských nástrojů** nech vypnutý; model nesmí měnit vlastní oprávnění.
5. Pokud YAML úpravy používá jiný záměrně povolený klient, ponech pro něj **Vyžadovat potvrzení pro úpravy YAML (náhled rozdílu)** zapnuté.
   To není totéž jako schválení plánu v HADS a nesmí se vydávat za kompletní kontrolu zápisů.
6. Ulož změny a použij **Restartovat server HA-MCP**, pokud jej stránka výslovně vyžaduje.
   Restart celého Home Assistantu není součástí tohoto návodu.

Globální read-only zablokuje také opravné zápisy ostatních klientů. Pro budoucí oddělení čtení a oprav
upstream podporuje připojení na suffix **`/readonly`** stejného autentizovaného MCP endpointu.
Například obecný tvar `https://SERVER/mcp/readonly`; u soukromé cesty patří suffix za její skutečný základ.
**Toto není potvrzení, že tuto cestu podporuje nainstalovaná verze nebo její HA webhook proxy.**
Existenci je nutné ověřit protokolovým testem, ne odhadem URL. Stejný credential může na základní cestě
stále zapisovat; analytik jej proto nesmí dostat přímo. Potřebuje nezávislý omezený broker.

Připojovací URL s náhodnou soukromou cestou nebo webhook identifikátorem je přístupový údaj.
Ukládá se pouze v soukromém nastavení, nikdy do promptu, GitHubu nebo výpisu agentovi.
OAuth callbacky Claude/ChatGPT nejsou připojení serveru k HADS. Nevyplňuj smyšlenou callback adresu.

### Jak se má ověřit skutečná funkce MCP

HADS má po implementaci obecného adaptéru sám provést: `initialize` → dokončení MCP inicializace →
stránkované `tools/list` → validace schémat → jedno konkrétní dovolené čtení se známým cílem.
Musí evidovat autentizaci, čtení, čas dat a každou mezeru. Popis „read-only“ od serveru nestačí:
smíšené nástroje potřebují kontrolu konkrétních argumentů. Negativní zápisové testy patří do izolované laboratoře,
ne do produkční domácnosti. Bez adaptéru RC6 se tento postup **automaticky neprovede**.

V RC6 lze původní nastavení převzít tlačítkem **Načíst návrh připojení z původního Hermes RC3**.
Import uloží pouze neaktivní soukromý návrh. Neaktivuje MCP, nepřenáší souhlasy a nedokazuje jeho funkčnost.
Není tu skrytý krok, který by uživatel musel dohledat: aktivní obecný MCP adaptér je nedokončená implementace HADS.

## 3. Hermes: první ověření bez placeného modelu

Originální NousResearch Hermes je již součástí obrazu HADS, pinned commit
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`. Neinstaluj kvůli tomu druhý samostatný Hermes.
Novější upstream má další schopnosti, které tento pin automaticky nezískává.

1. Otevři HADS jako ověřený vlastník.
2. Otevři **Zdroje a připravenost** a použij **Ověřit Hermes bez volání modelu**.
   Tím se model nevolá a nic se neúčtuje.
3. Výsledek musí potvrdit skutečné načtení původního runtime a izolaci. „Launcher dostupný“ ještě nestačí.
4. Pokud brání paměť, HADS dále automaticky čte statistiky Core/Supervisora/aplikací.
   Rezerva **576 MiB** se kontroluje znovu před workerem. Číslo nesnižuj pouze proto, aby kontrola zezelenala.
   Spotřeba kontejneru ani součet aplikací není volná paměť hostitele.

Hermes má pouze pojmenované diagnostické nástroje přes broker. Nemá shell, síťové credentialy ani přímé zapisovací API.
Přidání neomezeného MCP serveru do obecného Hermes `config.yaml` není bezpečné zapojení do HADS.
Upstream paměť/skills/delegace nesmějí rozšiřovat oprávnění. Jeden omezený worker šetří prostředky RPi.

## 4. Malý výslovný test s AI

Teprve při úspěšném runtime testu a dostatečné paměti:

1. Na straně poskytovatele založ samostatný projekt pro HADS. Nastav nízké dostupné limity a upozornění;
   ověř, zda jde o vynucený limit nebo pouze upozornění. HADS negarantuje dolarový strop.
2. Klíč vlož výhradně do **HADS → Nastavení AI**. Neposílej ho sem ani na GitHub.
3. Pro OpenAI nastav přesnou URL **`https://api.openai.com/v1/chat/completions`**.
   Nezadávej pouze `/v1` ani endpoint Responses. Jiný poskytovatel musí podporovat tento konkrétní kontrakt přes HTTPS.
4. Zadej skutečně dostupný model, který podporuje tool calling a požadavky tohoto adaptéru včetně
   `max_tokens` a JSON výsledku. Samotné jméno GPT v dokumentaci jiného projektu kompatibilitu neprokazuje.
   Kompatibilita skutečného modelu v domácnosti zatím nebyla otestovaná.
5. Vyber **Omezený test: nejvýše 3 požadavky za 24 hodin, pouze výslovně spuštěný případ**.
   Povolení předání redigovaných dat poskytovateli potvrď jen pokud s tím souhlasíš a ulož.
6. V jednom konkrétním spisu spusť **Spustit nebo obnovit čtecí vyšetřování Hermes**.
   Sleduj skutečně provedená čtení, chybějící důkazy a změnu hypotézy. Vysvětlení není důkaz opravy.

Test má nejvýše **3 síťové požadavky celkem za klouzavých 24 hodin**, také maximálně 3 na případ,
48 000 bajtů vstupu a 512 výstupních tokenů na požadavek. Selhání se také započítá; restart ani změna klíče
počet nevynuluje. Automatická placená fronta se v testovacím režimu nezapíná.
Rozšířený režim má jiné limity a samostatný souhlas s autonomním vyšetřováním; nyní ho není potřeba povolovat.
3 volání mohou skončit nedostatkem důkazů — není správné tento stav vydat za hotovou diagnózu.

## 5. Watchman, Spook a zdrojový kontext

Pro čtení Watchmanu není potřeba zapínat jeho reportovací službu ani zapisovací HA-MCP nástroje.
RC6 používá vlastnictví v registru a unique IDs `watchman_missing_entities`, `watchman_missing_actions`,
`watchman_last_updated`, `watchman_last_parse`, `watchman_status` podle ověřeného upstream kontraktu.
Přejmenování entity v UI nevadí. Starší odlišná identita je viditelné omezení; nenahrazuje se hádáním podle názvu.

Počet a atributy se musejí shodovat. Pět nálezů v jednom okamžiku a pozdější textový report se čtyřmi
není tentýž snímek. Watchman má heuristický parser a může zachytit také `logger.log` a `script.execute`
z ESPHome. Takové řádky potřebují kontext; HADS je nemaže ani neoznačuje za opravené.
Zakázaný spínač se automaticky nepovoluje. Zmizelá chyba neuzavírá funkční incident.

Spook Repairs jsou čtené přes nativní HA API. Nulový počet pouze v doméně `spook` neověřuje všechny
jeho reapers ani oprávnění. Zápisy do registrů a import/mazání statistik potřebují vlastní katalog,
náhled původního/nového stavu, zálohu s ověřenou obnovitelností a funkční kontrolu.
**Takový obecný vykonavatel Spook/HA-MCP není v RC6 hotový a přepínače serveru jej nedoplní.**

## 6. Automation Inspector a HADocs

**Inspector 1.2.4:** ověřené rozhraní je GET `/api/v1/inspection` (schema 2),
`/api/v1/status`, `/ready`; starší kompatibilní alias `/dependency_map.json`.
Při selhání refresh může vrátit starší data s `X-Automation-Inspector-Stale: true`.
Je nutné zachovat jejich původní `generated_at`. Automatická četba nemá používat `?refresh=true`.
Manifest má ingress port 1234, ale žádný publikovaný host port. Neotevírej port podle starých návodů.
Pro běžný provoz ponech zahrnutí zakázaných automatizací a čtení traces podle vlastního nastavení;
nález u zakázané automatizace neznamená, že ji HADS smí zapnout.

**HADocs 0.17.0-rc5:** ověřené GET `/api/status`, `/api/health`, `/api/summary`, `/api/hask-preview`.
Summary čte existující `knowledge/health.json`, `inventory.json`, `incidents.json`, `recommendations.json`
z output adresáře (manifest default `/share/hadocs`). POST `/api/scan` spouští sken; nejde o pasivní čtení.
Konkrétní manifest používá Supervisor integraci; nevyžaduj další HA token podle starší obecné instalační stránky,
pokud současná aplikace již funguje přes Supervisor.

Obě aplikace používají HA Ingress. App token HADS neumí legálně vytvořit libovolnou uživatelskou ingress session:
Supervisor session endpoint vyžaduje Home Assistant autoritu. HADS tuto hranici neobchází voláním interní IP,
podvržením uživatelských hlaviček ani scrapováním UI. Další implementace potřebuje podporovaný autentizovaný
strojový přístup nebo omezené čtení dokumentovaného exportu; samotná přítomnost webu není datový kontrakt HADS.

## 7. Volitelný HASK Preview v HADocs

Nejde o další automaticky aktivovaný opravný engine. V uvedené verzi je to experimentální **read-only,
candidate-only** znalostní vstup; nemění health score, findings, recommendations ani root causes.

Pokud chceš pouze ověřit preview, nejprve musí existovat validní consumer bundle podle dokumentace HASK.
Do **HADocs → Konfigurace** patří `hask_enabled: true`, `hask_preview_enabled: true`
a `hask_bundle_path` na skutečný read-only bundle; default `/config/hask-bundle` sám soubory nevytvoří.
Chybějící či neplatný explicitní bundle je chyba a nemá se tiše nahrazovat jiným zdrojem.
Bez připraveného bundle nech obě volby vypnuté. Ostatní databázové a evidence přepínače nezapínej hromadně:
mají samostatné podmínky inicializace a experimentální smlouvy.
Úspěšný `SUPPORTED_CANDIDATE` stále není důkaz příčiny ani autorizace opravy.

## 8. Co je potřeba dokončit v HADS

Aktivní obecný MCP klient s omezeným katalogem; autentizované vlastní čtení Inspectoru/HADocs;
čtení skutečného zdrojového kontextu nálezů; úzké opravné adaptéry registr/statistiky/konfigurace;
ověření záloh a živé funkční přejímky. To je vývojová práce, nikoli povinnost uživatele ručně vyšetřovat.
Aktuální bezpečný katalog obsahuje vlastní virtuální CAS referenci a samostatně povolenou jednoduchou
světelnou aktivaci. Instalace kandidáta neznamená dokončení celého původního zadání.

### Ověřené zdroje

- [HA-MCP read-only](https://github.com/homeassistant-ai/ha-mcp/blob/d02506531432aad040ece773ab1013b3e31ef6a8/src/ha_mcp/read_only.py)
  a [HTTP suffix/auth routing](https://github.com/homeassistant-ai/ha-mcp/blob/d02506531432aad040ece773ab1013b3e31ef6a8/src/ha_mcp/http_transport.py).
- [Hermes pin použitý v HADS](https://github.com/NousResearch/hermes-agent/tree/d923a5eb487a17c0a68801bba9ef0f56c81040a8).
- [Watchman sensors](https://github.com/dummylabs/thewatchman/blob/e0bf2481cb2d84022ac5124ad5dc4b731e5be526/custom_components/watchman/sensor.py).
- [Automation Inspector 1.2.4](https://github.com/ITSpecialist111/Automation-Inspector/tree/aa24bd4485b5f74fd4547d84dc5fb1045bc766fa).
- [HADocs 0.17.0-rc5](https://github.com/SirBlondieDK/HADocs/tree/c8dc8ff2fd5157941a3749148b4326592ee065c5)
  a [HASK Preview](https://github.com/SirBlondieDK/HADocs/blob/c8dc8ff2fd5157941a3749148b4326592ee065c5/docs/guides/features/HASK-Preview.md).
