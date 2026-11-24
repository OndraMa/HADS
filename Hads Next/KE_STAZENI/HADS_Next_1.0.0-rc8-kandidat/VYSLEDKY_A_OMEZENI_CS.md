# Předání HADS Next 1.0.0-rc8 — kandidát k přejímce

Instalátor, kompletní ZIP, aktuální zdroje a testy, české návody a přesné protokoly jsou
v [KE_STAZENI/HADS_Next_1.0.0-rc8-kandidat](../../KE_STAZENI/HADS_Next_1.0.0-rc8-kandidat/).
Navazuje na [PR #19](https://github.com/OndraMa/HADS/pull/19), zachovává identitu aplikace,
incidenty, důkazy a historii. Nejde o potvrzení úplného původního zadání ani živého HAOS.

Testovaný zdroj: `476587fb9f7593ff951143b2f4c7c3bac011c51b`.
Sestavení: `ed84b262c3b8303c2c08aeae2728dc942e8e86674b1cfd299632254e7c2bfce0`.
Otisk instalátoru: `83e57cfe030f0476507fde9e549de995b89094fcf81ee92920174f1ceaf01163`.

## Co vlastník udělá jednou

Přenes instalátor do `/config` v HAOS. Stávající RC6/RC7 předem nezastavuj ani neodinstalovávej.
V terminálové aplikaci HAOS spusť:

```bash
bash /config/HADS_Next_install_1.0.0-rc8.sh --verify
bash /config/HADS_Next_install_1.0.0-rc8.sh --upgrade
```

Jde o instalační úkon. Diagnostické příkazy, kopírování logů nebo ruční vyšetřování nejsou potřeba.
Ve Windows nic neinstaluj. Přesný postup a podmínky jsou v přiloženém `NAVOD_CS.md`.
Instalátor podle zadání nevytváří novou předinstalační HA/OneDrive zálohu; ochrany oprav zůstávají.

Po spuštění HADS ukáže skutečnou verzi, commit a ID sestavení. V **Nástroje servisního týmu**
vlož skutečnou HA-MCP adresu do maskovaného pole. Pro přímou soukromou HTTP adresu potvrď pouze
příslušný souhlas se soukromou sítí. Token doplň jen pokud jej skutečný server vyžaduje.
Inspector/HADocs se vyhledají automaticky podle inventáře. HADS provede dostupná čtení sám.

## Hotovo / chybí / blokováno

| Stav | Konkrétní výsledek |
|---|---|
| Hotovo ve zdrojích a izolované přejímce | Registr 15 providerů, jejich podporované diagnostické podmnožiny, původní Hermes a oddělený schvalovaný vykonavatel |
| Hotovo v kandidátu | Ověřitelná identita, aktualizace z vydaných RC6/RC7, expirace starých nepoužitých souhlasů, maskované soukromé URL a konkrétní výsledky 401/403/404/503 |
| Hotovo v kandidátu | Trvalá konverzace spisu, lokální ignorování bez označení opravy, opětovné čtení bez AI a ochrana proti ingestování vlastních hlášení |
| Hotovo v kandidátu | Patnáctiminutový collector prostředků; souhrn se čte autonomně do paměťového spisu a je dostupný původnímu Hermesu stejným brokerem |
| Hotovo jako příjem důkazu | Soukromá HTTPS integrace nezávislého ověřovatele, připnutý veřejný klíč, podpis, rozsah, cíl, stáří a soukromá cache |
| Implementované omezené opravy | Doložená jediná světelná reference přes HA-MCP a zamýšlené povolení jedné entity přes Spook; nový samostatný souhlas pro návrat |
| Chybí jako automatické opravné adaptéry | Obecné statistiky/Recorder, přejmenování/mazání registrů, konfigurace skriptů/dashboardů a Zigbee binding/reporting/kanál/zápisy atributů |
| Chybí jako provozní propojení | Skutečný nezávislý OneDrive ověřovatel obnovy; přijímací adaptér jej nemůže nahradit. Rizikový zásah se bez důkazu zablokuje |
| Chybí | Vzdálený Hermes worker; kandidát používá skutečný lokální runtime a při malé RAM jej odloží |
| Blokováno přístupem | Živá autentizovaná čtení HA-MCP/HAOS, skutečné reporty nainstalovaných providerů a patnáctiminutové měření RPi; poskytnuté cesty z cloudu vrátily HTTP 503 |
| Čeká na samostatnou přejímku | Reálné modelové uvažování, fyzické výsledky Zigbee/automatizace/rádia a skutečný HAOS update |

HABS není povinnou závislostí instalace ani diagnostiky HADS. Potřebný nezávislý důkaz obnovy
před rizikovou opravou může poskytnout skutečný kompatibilní ověřovatel; HADS si jej nesmí vystavit sám.
Přijetí závěru nebo zprávy v konverzaci není souhlas s opravou ani placenou AI.

## Přesné testy a jejich význam

[Běh 44542135579](https://github.com/OndraMa/HADS/actions/runs/44542135579) prošel na ARM64 i AMD64:

- **323 testů na každé architektuře**, včetně skutečných místních HTTP/MCP/TLS přenosů a negativních schvalovacích testů.
- Přesný instalační payload, produkční Dockerfile, start s `network=none`, správný commit a sestavení v `/health`, čistý SIGTERM s kódem 0.
- Skutečný Core 2026.11.0, pinned upstream Inspector builder a původní izolovaný NousResearch Hermes.
- Dodatečný průchod Hermes → report/schema/konfigurace → inertní návrh → vlastník přes HTTP/CSRF → jeden testovací providerový zápis → funkční report.
- **26 lokálních mobilních/desktopových pohledů**. Instalační soubory obou architektur jsou totožné a odpovídají místní reprodukci.

Modelové odpovědi byly skriptované a bez placených volání. Opravný wire scénář používá anonymizované
poskytovatele, vstříknuté funkční události a řízené hodiny. Není to test fyzické domácnosti.
Skutečný proces Inspector HTTP serveru není součástí Core builder testu; jeho HTTP kontrakt má samostatný wire test.
Skutečné nainstalované HA-MCP/Spook/HADocs a další aplikace se tím neoznačují za živě přejaté.
323 testů neznamená úplné splnění zadání. Nebyl proveden externí bezpečnostní audit.

Protokoly jsou zachované v [RESULTS.json](evidence/candidate-20261119/RESULTS.json),
včetně SHA-256 stažených GitHub artefaktů, interních protokolů a 174 vstupních souborů.
[Živý přejímací postup](ORCHESTRATION_LIVE_ACCEPTANCE_CS.md) zůstává čekající.

Síťová politika cloudu byla při nové kontrole aktuální a neomezená. Veřejná cesta přesto vrátila
HTTP 503 a textový příznak `upstream connect error` před initialize. To nepotvrzuje poruchu HA-MCP
ani špatný token; identita, katalog a skutečné incidentní čtení z tohoto spojení nejsou ověřené.
Žádný produkční zásah ani placené modelové volání neproběhly.
