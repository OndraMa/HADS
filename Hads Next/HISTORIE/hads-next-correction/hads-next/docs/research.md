# M0: rešerše upstream a capability matrix

Datum kontroly: **2026-11-08 UTC**. Internet byl dostupný přes připojené nástroje
GitHub a web. Kontrola níže znamená četbu dokumentace a zdrojů, **ne** připojení
k domácnosti, spuštění cizích projektů nebo ověření na HAOS. Všechny zdroje z
požadavku byly otevřeny. Není důvod povinně instalovat další komunitní aplikaci
kvůli datům, která poskytuje nativní API.

## Reprodukovatelnost a rozsah

GitHub API `repos/<owner>/<repo>/commits?per_page=1` poskytlo následující revize.
Štítek latest je informativní: **není důkazem**, že přečtený main odpovídá danému
vydání nebo že je vydání kompatibilní s konkrétní domácností.

| Projekt | Přečtená revize | Zjištěné vydání / kompatibilita |
|---|---|---|
| HA Core | zdroje pod tagem `2026.11.0` | Zkoumán kontrakt 2026.11.0; live kompatibilita čeká |
| [ha-mcp](https://github.com/homeassistant-ai/ha-mcp) | `f380f721b835aaa014a91913d5bfcf165db21a04` | latest `v9.1.1`; README vyžaduje HA >=2026.8.0 pro in-process integraci |
| [ha-mcp-readonly](https://github.com/paulomac1000/ha-mcp-readonly) | `d9b9c1ad47aa1f5dd04d9715e6c1dcd87a5b1061` | latest API hlásí `v2.3.0`; README ještě popisuje změny 2.0.0; neslučovat evidenci těchto verzí |
| [Spook](https://github.com/frenck/spook) | `4bee6e1561bb957eddee415159a18cc04de2d43c` | latest `v5.11.1`; main manifest má vývojové `0.0.0`, live kompatibilita čeká |
| [Watchman](https://github.com/dummylabs/thewatchman) | `e0bf2481cb2d84022ac5124ad5dc4b731e5be526` | latest `v0.8.4`, main manifest `0.8.6`; live kompatibilita čeká |
| [Vibecode Agent](https://github.com/Coolver/home-assistant-vibecode-agent) | `6c21a73f994bb1f136729388366ec27f5407859a` | README `2.10.50`, doporučený MCP klient `3.2.32`; latest release API vrací 404 |
| [Music Assistant server](https://github.com/music-assistant/server) | `16cc25456f3107f7a5db875b07b69efb079643fa` | web dokumentace 2.10.9; FastMCP `VERSION` ve zdroji `2.2.8`; verze pluginu není verze serveru |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | `3e82260ba041b75cf9eb20abf13bec937bb32e27` | latest `v0.23.0`; současný README uvádí installer Python 3.14; neověřeno na RPi 2 GB |
| [Hermes official plugins](https://github.com/NousResearch/hermes-official-plugins) | `13b2c1c9c8204bf333df240b2aacf98c3e6250b7` | bez latest release; jednotlivé pluginy mají vlastní verze/piny |

Piny jsou výsledkem online čtení; změna upstream main později není důvodem
automaticky změnit HADS runtime. Pro testovaný runtime platí jeho vlastní lock
a testovací protokol, nikoliv tato tabulka průzkumu.

## Co znovu použít a s jakou hranicí

| Zdroj | Čtení a přínos | Oprávnění / rizikový zápis | Rozhodnutí a alternativa |
|---|---|---|---|
| Nativní HA REST/WS | stavy, registry, historie, traces, Action history, Repairs, zdraví | bearer token; některá čtení admin-only; tentýž token může umožňovat služby a změny | První volba. Broker drží token a povolí konkrétní čtení. AI nedostává obecný HTTP klient ani token |
| Nativní HA MCP | standardní discovery a nativní administrační LLM čtení | hlavní `/api/mcp` má read-only volbu, standardně vypnutou; ostatní URL tuto volbu ignorují; služby/reload jsou write | Volitelný transport přes explicitní allowlist. Při nedostupnosti přímo nativní REST/WS |
| Supervisor | seznam aplikací, jejich stav/logy/statistiky, host/OS/Core informace | `hassio_api: true`; `default` dovolí `*/info`; seznam/logy/statistiky jiných aplikací potřebují `manager`, který má i write | Oddělený deterministický broker, analytik bez Supervisor tokenu. Při 403 pokračovat Core historií a přiznat chybějící důkazy |
| ha-mcp | širší katalog, registry, konfigurace, traces, souvislosti a nativní API adaptéry | README požaduje administrační účet/token; katalog obsahuje konfigurační write, služby, mazání | Neinstalovat povinně. Případně pouze prověřený allowlist čtení konkrétní verze; fallback nativní API |
| ha-mcp-readonly | čtení registrů, historie, kontextových vazeb a diagnostiky; provenance/rozpočty | token HA, některé funkce přístup ke konfiguraci; dev/template nástroje vypnuté; deklarované read-only není OS sandbox | Dobrá reference pro bounded provenance, ne povinná závislost. Bez něj nativní čtení; neposkytnout celou `/config` AI |
| Spook | existující Repairs o neplatných odkazech, doplňkové diagnostické údaje | custom integration běží uvnitř Core; také přidává akce/triggery/conditions | Pokud již instalován, číst Repairs. Neinstalovat kvůli prvnímu scénáři; vlastní kontrola konkrétní reference |
| Watchman | senzory a výsledky hledání chybějících odkazů | parsuje konfiguraci; `watchman.report` může psát soubor/posílat notifikace; `set_ignored_labels` je write | Číst existující senzory, nevolat report jako údajně čisté čtení. Heuristické nálezy jsou podnět, ne důkaz příčiny |
| Vibecode Agent | reference pro cílené čtení konfigurace a validaci | API key, filesystem/config write, nasazení, HACS správa; Git kopie není HAOS backup | Nepřebírat obecný zapisovací server do analytika. Nativní API a samostatný executor |
| MA FastMCP | stav přehrávače/fronty/provideru, lokální nedávné události/logy při zapnutí debug čtení | samostatný revokovatelný MA token; query/resources default read-only; debug/config default off; playback, volume, reload a config jsou write | Volitelný adaptér s discovery + ověřeným schématem + allowlist. Fallback HA media_player historie + app logy; přiznat chybějící MA události |
| Hermes upstream | skutečná agent loop, MCP, discovery, paměť, session search, skills, delegace | obecné terminal/file/code nástroje a pluginy mohou obejít approval; web/model může stát peníze | Pinned runtime v izolaci, pouze čtecí broker. Logické role sekvenčně; výzkum opt-in. Bez AI deterministická evidence pokračuje |
| Hermes official plugins | katalog produktových integrací včetně Home Assistant | plugin může přidat write nástroje a credentials; instalace je kód | Žádná automatická instalace. Home Assistant plugin není náhrada schvalovacího modulu. Bez něj vlastní omezený čtecí MCP broker |

README komunitních projektů bylo skutečně čteno na uvedených pinech, nikoliv
jejich testy spouštěny. Cizí počty testů nebo tvrzení o ARM nejsou výsledky HADS.

## Ověřené nativní kontrakty

Základ: [REST dokumentace](https://contributors.home-assistant.io/core/internals/rest-api/)
a [WebSocket dokumentace](https://contributors.home-assistant.io/core/internals/websocket-api/).
REST používá `Authorization: Bearer ...`; WS `/api/websocket` nejprve `auth_required`,
pak klient `auth` s `access_token`, následně `auth_ok` nebo `auth_invalid`.
WS požadavky mají číselné `id`; výsledky je nutné párovat a kontrolovat `success`.
Otevřené spojení není důkaz úspěšného čtení. Níže uvedené příklady neobsahují tokeny.

| Potřeba | Ověřený kontrakt a zdroj v HA Core `2026.11.0` | Hranice |
|---|---|---|
| Aktuální stavy | REST `GET /api/states`, `GET /api/states/<entity_id>` | API stav není důkaz fyzického výsledku |
| Historie | REST `GET /api/history/period/<timestamp>`, `GET /api/logbook/<timestamp>` | Recorder může mít omezenou retenci/vyloučené entity |
| Kontextové události | WS `logbook/get_events` se `start_time`, volitelně `end_time`, `entity_ids`, `device_ids`, `context_id` | Context id dokládá vazbu, nikoliv samo o sobě fyzickou příčinu |
| Action history | WS `logbook/get_action_calls`, povinné `start_time: str`, volitelné `end_time: str`; admin-only | Bez filtru entity na serveru v tomto schématu; omezit časové okno a redigovat action data před uložením/AI. Mohou obsahovat alarm kódy |
| Automation/script traces | WS `trace/list` s `domain: automation|script`, volitelně `item_id`; `trace/get` s `domain,item_id,run_id`; `trace/contexts` s volitelnou dvojicí `domain,item_id`; admin-only | Trace retention je omezená; debug breakpoint/step/continue/stop jsou write a nikdy se nevystavují |
| Registry | WS `config/entity_registry/list`, `config/device_registry/list`; `config/entity_registry/get` s `entity_id` | Při zjišťování názvů sledovat registry a stabilní device/config-entry vazby, ne jen friendly_name |
| Repairs | WS `repairs/list_issues`, `repairs/get_issue_data` s `domain,issue_id` | `repairs/ignore_issue` je změna a neopravuje příčinu |
| System Log | WS `system_log/list`, admin-only | Omezený deduplikovaný buffer warning/error; absence záznamu není absence poruchy |
| Živé logy integrace | WS `system_log/subscribe_raw`, volitelně `integration: str`, admin-only | Omezit délku sběru/objem a odhlásit odběr. Nepoužívat UI scraping |
| System Health | WS `system_health/info` | Event stream výsledků, ne jediný prostý REST objekt; některé hodnoty mohou doběhnout později |
| ZHA | WS `zha/devices`, `zha/device` s `ieee`; živý odběr událostí `zha_event` přes obecné `subscribe_events` | Nepřidávat permit, reconfigure, bind, topology update nebo cluster command do read allowlistu; fyzický stisk bez záznamu nelze doložit |

Přímé pinované zdroje a jejich Git blob SHA při kontrole:

| Soubor pod `homeassistant/components/` | Blob SHA |
|---|---|
| [logbook/websocket_api.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/logbook/websocket_api.py) | `39cf5736230841825bcacc9223a85c758cde5777` |
| [trace/websocket_api.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/trace/websocket_api.py) | `7eddc5326601fbc3a3ea7e488c7cc165bc3d696b` |
| [config/entity_registry.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/config/entity_registry.py) | `741534d15ca0cb6ee0a06c00f720a16141ed9276` |
| [config/device_registry.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/config/device_registry.py) | `04f35603236b875c4fd4c3f2b1c22172d571b346` |
| [repairs/websocket_api.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/repairs/websocket_api.py) | `b7daa5f69527f7508fc8efac6a87e5c3c265f4e5` |
| [system_log/__init__.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/system_log/__init__.py) | `3deac0d85b558b1ad8ae6a89b3493104c79e6fdf` |
| [system_log/stream.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/system_log/stream.py) | `d928973b36d7075eed5405ce955bebd1350e1d0e` |
| [system_health/__init__.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/system_health/__init__.py) | `f4177859ce21efe92c951c4d61fe00739a2179a4` |
| [zha/websocket_api.py](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/zha/websocket_api.py) | `ae5c1e38971f445232862853c5e0b7f6ef5ac447` |

Čtení zdrojů ověřuje existenci kontraktu na daném tagu, nikoliv jeho dostupnost
v konkrétní instalaci. Při `unknown_command`, chybě autentizace, nepovoleném čtení,
timeoutu nebo chybějící integraci musí adaptér vrátit explicitní omezení.
Nebyly hádány endpointy `/api/action_history` ani `/apps/...`.

### Action history: přesná odpověď a projekce

[`logbook/processor.py`](https://github.com/home-assistant/core/blob/2026.11.0/homeassistant/components/logbook/processor.py)
(blob `fb9e223f4ddb1922437eb954d973c49ec0e78655`) a `logbook/const.py`
potvrzují WS result jako seznam záznamů. Každý action záznam má `domain`,
`service`, `service_data`, `context_id` a `when` (Unix timestamp, protože
`timestamp=True`). `context_user_id` a kontextové údaje mohou být doplněny,
ale nejsou garantované. Cíl entity je typicky uvnitř `service_data.entity_id`,
nikoliv zaručeně v top-level `entity_id`.

Ukázka tvaru **syntetická, bez dat domácnosti**:

```json
{
  "id": 7,
  "type": "result",
  "success": true,
  "result": [{
    "domain": "media_player",
    "service": "media_stop",
    "service_data": {"entity_id": "media_player.test_radio"},
    "context_id": "01JC5000000000000000000000",
    "when": 1794135600.0
  }]
}
```

Použít pozitivní projekci, ne redakci několika známých secret keys:

- Ponechat validované identifikátory `domain`, `service`, `context_id`, číselné
  `when` a potřebné validované kontextové identifikátory.
- Z `service_data` vzít pouze validované cílové `entity_id`, případně známé
  target `device_id` / `area_id`, a původní `service_data` zahodit.
- Nepředávat libovolné `context_name`, `context_message`, `context_state`,
  `context_source`, action texty ani neznámé klíče. Mohou obsahovat citlivá data
  nebo nedůvěryhodný text. Ani čtení služby `alarm_control_panel` nesmí předat PIN.
- Před uložením do incidentu nebo předáním modelu ověřit velikost, typy,
  strukturu i počet záznamů. Přijetí WS zprávy není souhlas s uložením raw dat.

## Home Assistant 2026.11 a nativní MCP

[Release notes 2026.11](https://www.home-assistant.io/blog/2026/11/04/release-202611)
potvrzují Action history s původem/kontextem, propojené script traces, živé logy
integrací, nativní administrační LLM nástroje a Marketplace. Název entity na UI se
může měnit bez stejné změny jejího identifikátoru. Změny záloh a senzor velikosti
úspěšné automatické zálohy zlepšují pozorování, nedokazují obnovitelnost.

[MCP dokumentace](https://www.home-assistant.io/integrations/mcp_server/) výslovně
rozlišuje hlavní `/api/mcp` a jednotlivé `/api/mcp/<llm-api>` URL. Read-only se
vztahuje pouze na hlavní URL, je standardně vypnuté a vybírá nástroje podle
deklarace neexistence změn. Individuální URL tuto volbu ignorují. Pro HADS tedy
nepřipojovat naslepo URL `assist` ani administrační API. Discovery samo nesmí
rozšířit allowlist. Nativní System Log nástroje `system_log__get_entries` a
`system_log__get_logs` a System Health `system_health__get_system_info` jsou
ve zdrojích 2026.11.0 označené read-only; názvy potvrzeny v `system_log/llm.py`
a `system_health/llm.py`. Obecná akce/reload zůstávají mimo analytika.

[Automation troubleshooting](https://www.home-assistant.io/docs/automation/troubleshooting/)
je podklad pro rozlišení trigger → podmínka → akce → cílový stav. Ruční spuštění
automatizace není ekvivalent fyzického triggeru. Při nedochované trace lze
požádat o řízený stisk a časově omezený odběr. UI části bez ověřeného kontraktu
zůstávají ruční; není dovoleno nahrazovat API scrapingem.

## Supervisor a zálohy

[Apps endpointy](https://contributors.home-assistant.io/apps/supervisor-api/apps/):
`GET /addons`, `/addons/<slug>/info`, `/addons/<slug>/stats`, `/addons/<slug>/logs`.
Seznam obsahuje `addons`; slug zahrnuje prefix repozitáře. Název apps nezměnil
cesty API. Odpověď Supervisoru je nutné validovat včetně result/data obálky;
logy mohou být text. Nepoužít nezdokumentované přístupy k hostu.

[Supervisor oprávnění](https://contributors.home-assistant.io/apps/supervisor-api/)
nemají samostatnou roli pro read-only seznam/logy všech aplikací. Role `default`
dovoluje cesty končící `/info`, `manager` zahrnuje i změny. HADS broker proto
zůstává samostatnou hranicí a token není součástí promptu ani prostředí Hermes.

[Backup API](https://contributors.home-assistant.io/apps/supervisor-api/backups/)
potřebuje `backup`, `manager` nebo `admin`; čtení `/backups`, `/backups/info`,
`/backups/<slug>/info` neprokazuje obnovitelnost. Vytvoření/restore/freeze jsou
zásahy. OneDrive restore verification není vlastnost těchto endpointů. Dosavadní
RC3 podmínky se nesmí nahradit kontrolou existence, velikosti nebo uploadu;
riziková oprava bez nezávislé obnovovací evidence musí zůstat blokovaná.

## Music Assistant FastMCP

[Dokumentace](https://www.music-assistant.io/plugins/fastmcp-server/) uvádí
výchozí `/mcp/v1`, vlastní revokovatelný token klienta a opt-in debug/config
capabilities. Debug inspect/logs/events/providers umožní cílené vyšetřování;
debug reload i všechny playback/volume/config writes zůstávají vypnuté.
Read-only výchozí stav knihovny sám neposkytuje plnou diagnostiku. Nedávné
události závisí na zapnutém bufferu; nelze slíbit retrospektivu před jeho startem.

Ve zdroji `music_assistant/providers/fastmcp_server/` na pinu z tabulky přečteny
`commands/registry.py` (blob `18fbb3044014bb3ff639d942e14129b1a9515db2`),
`commands/debug.py` (`6772e56ea88c72ed354ff210e5c21493b14e85f1`) a
`command_policy.py` (`64b6c88d3f48ace23025086628ebe02c5ff98132`).
Ověřené interní příkazy: `fastmcp/debug/tail_log`, `log_stats`, `recent_events`,
`event_buffer_stats`, `health`, `routes`, `packages` (posledních šest pod stejným
prefixem). **Interní příkaz není bez discovery automaticky MCP tool jméno.**
Adaptér musí porovnat `tools/list` schémata, oprávnění a verzi; obecný command
passthrough není bezpečný read-only adaptér. Stream dostupnost z textu chyby
zůstává hypotéza, pokud chybí nezávislé časové důkazy.

## Hermes schopnosti a omezení

[Hermes README](https://github.com/NousResearch/hermes-agent/blob/3e82260ba041b75cf9eb20abf13bec937bb32e27/README.md)
potvrzuje MCP, skills, persistentní paměť a session search; skutečná agent loop
musí být upstream runtime, nikoli přeznačený JSON wrapper. Memory/session/skills
potřebují vyhrazený datový adresář s retencí a bez secrets. Web research zůstává
vypnutý do explicitního nastavení bezplatného povoleného zdroje. Žádný placený
gateway se nezapne automaticky. Přítomnost podpory neprokazuje výkon na RPi.

Runtime zvolený pro izolovaný HADS smoke je samostatně připnutý upstream
**v0.22.2**, commit `d923a5eb487a17c0a68801bba9ef0f56c81040a8`. To není main
z tabulky rešerše ani tvrzení o produkční kompatibilitě. Home Assistant plugin
na pinu official plugins nabízí `ha_list_entities`, `ha_get_state`,
`ha_list_services`, ale také `ha_call_service` a zápisy gateway notifikací.
Potřebuje `HASS_TOKEN` a `aiohttp >=3.9,<4`; analytik ho proto nepřebírá.

[Official plugins README](https://github.com/NousResearch/hermes-official-plugins/blob/13b2c1c9c8204bf333df240b2aacf98c3e6250b7/README.md)
uvádí přesun produktových integrací mimo core a verzi/piny jednotlivých pluginů.
Nový skill nemá získávat oprávnění a nový plugin není pouhá dokumentace.
Delegace se omezuje na logické role/sekvenční úlohy, bez dalších tajemství a bez
obecného shellu; bezpečnost nemůže stát jen na systémovém promptu.

## Zkušenosti, které nejsou API specifikace

Všechny následující odkazy byly dostupné. Jsou zdrojem návrhových zkušeností,
nikoli důkazem kontraktu či příčiny konkrétní domácnosti:

- [Hermes copilot](https://peyanski.com/hermes-agent-home-assistant-copilot-or-bad-idea/): malý cíl, lidské schválení a opětovné čtení výsledku.
- [AI roadmap](https://peyanski.com/home-assistant-ai-roadmap-official-helper/): oddělené schopnosti a jejich stav, ne slib hotového autonomního správce.
- [AI setup](https://peyanski.com/home-assistant-ai-setup-claude-chatgpt-one-click/): snadnější zapojení MCP neodstraňuje autentizaci ani kontrolu změn.
- [Komunitní diskuse](https://community.home-assistant.io/t/how-do-you-use-ai-with-home-assistant/1028637): kontext domácnosti a historie rozhodnutí jsou užitečné; pravidla v textovém adresáři nejsou nezávislé vynucení bezpečnosti.

## Co ještě musí prokázat přejímka

- Autentizace a jednotlivá read oprávnění skutečné verze HA/OS/Supervisoru;
  citlivá action data musí být redigována před modelovým endpointem.
- Dostupnost a obsah `logbook/get_action_calls`, trace retention, kontextové
  řetězce a události skutečného ovladače/přehrávače.
- MA discovery schémata konkrétní instalace, read-only capabilities a doba
  uchování event bufferu; test nesmí měnit hlasitost ani přehrávání.
- Marketplace/update kontrakty a nové backup senzory konkrétní instalace;
  zatím nejsou implementačně ověřený univerzální API adaptér.
- Reálná spotřeba Hermes a scheduleru na RPi 4 / 2 GB, výpadek modelu, restart
  během zásahu, autorizace a funkční rollback na izolovaném HAOS.
- Obnovitelnost požadované OneDrive zálohy samostatným obnovovacím testem.

Žádná položka tohoto seznamu není označena jako živě ověřená.
