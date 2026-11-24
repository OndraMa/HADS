# Instalační kandidát orchestrace — 19. 11. 2026

Verze kandidáta: **1.0.0-rc8**. Navazuje na PR #19; nepředstavuje úplně dokončený ani produkčně ověřený nástroj.
Přesný commit a ID sestavení jsou v `PACKAGE_MANIFEST.json`, `/health`, přehledu a API stavu.
Původ runtime je potvrzený pouze pokud všechny zabalené Python zdroje odpovídají manifestu.

## Jednorázové kroky vlastníka

1. Stáhni celý kandidát z aktuální vývojové větve GitHubu, ověř přiložené SHA-256 a přenes instalační `.sh`
   do `/config` v HAOS. Ve Windows jej nespouštěj a nic dalšího neinstaluj.
2. V terminálové aplikaci HAOS spusť `bash /config/HADS_Next_install_1.0.0-rc8.sh --verify`.
   Pro již instalovanou ověřenou RC6/RC7 použij `bash /config/HADS_Next_install_1.0.0-rc8.sh --upgrade`.
   To je instalační úkon, nikoli požadavek provádět diagnostiku domácnosti ručně.
   Neodinstalovávej starý HADS Next. Identita `local_hads_next_practical` a `/data` zůstávají.
3. Otevři HADS a zkontroluj verzi, commit a sestavení. Devět nativních čtení samo nepotvrzuje zapojení všech doplňků.
4. V **Nástroje servisního týmu → Jednorázové připojení → ha_mcp** vlož skutečnou adresu serveru do maskovaného pole.
   Pokud má adresa tajnou cestu, další token nepřidávej bez skutečného požadavku serveru.
   Pro soukromé HTTP je nutný samostatný souhlas. TLS ani serverové ochrany nevypínej.
5. HADS sám načte status/reporty/katalog a další dostupné důkazy. 401/403/404/503 mají konkrétní vysvětlení.
   Inspector/HADocs hledá přes skutečný Supervisor inventář. Hamster není povinný.
6. Doplnění nezjistitelného očekávání napiš do konverzace konkrétního spisu. Zpráva neschvaluje opravu ani AI.
   Placenou AI zatím není potřeba zapínat; místní sběr pokračuje samostatně.

Instalátor podle zadání **nevytváří novou předinstalační HA/OneDrive zálohu**. Zachovaný zdrojový strom
není záloha databáze ani obnova HAOS. Povinné nezávislé zálohy před skutečnými opravami zůstávají vynucené.
Při změně ověřeného sestavení se nepoužité staré souhlasy expirují; historie a plány zůstávají uložené.
Nejistý update ani nejistý opravný zápis se automaticky neopakují.

## Dokončené části a meze

- Registr 15 providerů, jejich skutečné diagnostické podmnožiny, původní izolovaný Hermes a oddělené schvalování z PR #19.
- Navíc ověřitelná identita sestavení, maskovaná MCP URL, konkrétní chyby přístupu, trvalá konverzace,
  čtení konfigurace skriptu a katalogu akcí související integrace, ochrana před opětovnou ingestí vlastních logů.
- Příjem podepsaného důkazu obnovy přes skutečně nakonfigurovanou HTTPS adresu, nezávislý klíč a kontrola každého cíle.
  [Kontrakt a nedokončená provozní část](RESTORE_VERIFIER_CONTRACT.md): skutečný nezávislý OneDrive ověřovatel zatím není připojený.
- Průběžné patnáctiminutové měření na hostiteli HADS, nejvýše jedna dávka za minutu; restart a mezery přeruší pokrytí.
  Zdejší cloudové testy nepředstavují naměřený výkon RPi. Povinná rezerva zůstává 576 MiB.
- Opravný katalog stále obsahuje konkrétní HA-MCP světelnou referenci a Spook povolení jedné entity, s odděleným návratem.
  Obecné změny statistik/Recorderu, registrů, skriptů, dashboardů a Zigbee binding/reporting/kanálu nejsou implementované automatické opravy.
  Čtení skriptu či katalogu služeb není oprávnění je měnit.

Při čtecím pokusu z cloudu 19. 11. 2026 všechny tři poskytnuté cesty HA-MCP vrátily HTTP 503 ještě před initialize.
Autentizace, nainstalovaná verze, katalog a skutečné incidentní čtení tím **nebyly potvrzené**.
Nelze tím určit, zda odpověď pochází od HA-MCP, proxy nebo přístupové infrastruktury.
Nebyl proveden žádný zásah domácnosti ani placené modelové volání.

Přesná živá přejímka zůstává v [protokolu](ORCHESTRATION_LIVE_ACCEPTANCE_CS.md).
Je nutné ověřit skutečné doplňky, funkční výsledek senzoru/automatizace/rádia, nezávislou obnovu a malý výslovně povolený test modelu.

## Když se Hermes do RPi bezpečně nevejde

279–301 MiB z předaného živého výpisu nestačí pro rezervu 576 MiB. Není to zdejší nové patnáctiminutové měření.
Neřeš to snížením rezervy nebo naslepo restartem Core. HADS má nejprve dokončit vlastní měření a zobrazit meze.
Konkrétní realistická varianta je oddělená testovací HAOS VM na hostiteli s nejméně 4 GiB RAM pro původní
Hermes a samostatně autentizovaný čtecí přístup k cílovému HA. Přesun vyžaduje ověřený vzdálený broker,
identitu a bezpečné předávání redigovaných důkazů; tento vzdálený worker dosud není implementovaný a nepovoluje se přepínačem.
Současný kandidát spouští skutečný Hermes lokálně a při malé paměti jej bezpečně odloží. Nezaměňuje jej za API-only agenta.

## Ověřený kontrakt AI poskytovatele

Oficiální OpenAI SDK `openai/openai-python` revize
`0d50c9daece1a4a0f4920f64b5ff90846b4e2050` obsahuje Chat Completions
`max_completion_tokens` zahrnující viditelné i reasoning tokeny; `max_tokens` je zastaralý a nekompatibilní s o-series.
HADS pro přesný oficiální endpoint `https://api.openai.com/v1/chat/completions` používá tento nový limit,
pro jiné dosud nakonfigurované kompatibilní endpointy zachovává jejich dosavadní `max_tokens` kontrakt.
Zdroj: `src/openai/types/chat/completion_create_params.py`; seznam jmen modelů je v
`src/openai/types/shared_params/chat_model.py` stejné revize. Například `gpt-4.1-mini` je v tomto SDK uveden;
není tím potvrzená dostupnost pro konkrétní účet ani provedený modelový test. Model zůstává volbou vlastníka.
Trvalé limity, žádné automatické zpoplatněné testy a samostatný souhlas zůstávají.
