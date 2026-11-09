# Hermes: skutečný runtime, přesný rozsah ověření

## P0–P2 provozní vyšetřování, 2026-11-09

Nový provozní průchod používá `evidence_broker.py`, `investigation_jobs.py`,
`investigation_service.py`, `hermes_runtime.py` a oddělený root launcher.
`AIAgent.run_conversation` v auditovaném upstream pinu dostává pojmenované
čtecí nástroje. Každé jejich volání se vrací přes zděděný spojený FD do
controlleru, který provede skutečné nativní čtení. HA token ani modelový API
klíč nejsou ve workeru, jeho prostředí či filesystemu.

Controller odloží UID na 65532. Samostatný launcher bez přihlašovacích údajů
spouští pevně určený worker, který před inferencí aktivuje chroot, UID 65534,
NNP, limit 384 MiB adresního prostoru a RC3 seccomp/write seal. RC3 filtr není
rozšířen; doplněno bylo obnovení parent-death SIGKILL po změně UID. Worker
nevytváří sockety, nespouští procesy, nečte HA soubory a nemění filesystem.
Launcher přijímá pouze pevný start/stop/cancel protokol; nemá shell rozhraní.

Prošel skutečný Core 2026.11.0 + skutečný Hermes + provozní controller:
ověření HA admina → registrace → výslovná konfigurace AI → ověřený HTTPS
skriptovaný endpoint → fronta → šest čtení → pět nových důkazů → český závěr.
Odpověď Core 404 je samostatný negativní důkaz, nikoli vymyšlený stav entity.
Testovaný ingress peer je loopback simulace, nikoli HAOS ingress.

Prošel také skutečný SIGKILL workeru po uloženém čtení, rekonstrukce aplikace
a pokračování novým workerem ve stejném spisu; potvrzená konfigurace se znovu
nečetla z Core. Neznámý výsledek modelového volání blokuje další účtovaný retry.
Každý intent se uloží před síťovým požadavkem. Limit je 8 požadavků na případ,
12 za UTC den, 1024 výstupních tokenů na požadavek a nejvýše dvě spuštění
workeru na vyšetřování. Retence případů nesmaže denní počítadlo.

Přesné vstupy a rozsahy: `evidence/core-broker.json`,
`evidence/hermes-core-broker.json`, `evidence/hermes-controller-core.json`.
Základní instalační zdroj se ještě nepovažuje za hotový kandidát. Nový runtime
se sestavuje přes `scripts/investigation_context.py` a `haos/Hermes.Dockerfile`;
žádný nový instalační archiv se v tomto checkpointu nepublikuje.
Živý HAOS, skutečný Supervisor, ARM64/RPi a reálný jazykový model čekají.
Placený poskytovatel je standardně vypnutý; OAuth zde není implementováno.

Následující části popisují historickou snapshot demonstraci. Její omezení se
vztahují na starý `native_hermes_investigation`, který zůstává test entry pointem.

Stav k 2026-11-08: integrační test používá originální `NousResearch/hermes-agent`
`v0.22.2`, commit `d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
Jde o stejný pin jako v RC3; novější upstream HEAD byl při rešerši
`3e82260ba041b75cf9eb20abf13bec937bb32e27`, ale bez auditu jej nepřebíráme.
Docker build ověřuje git SHA před instalací a ukládá `HADS_PINNED_REVISION`.
Upstream v tomto commitu výslovně odmítá wheel build; používáme podporovaný
editable install. Zdroj není přepsán ani nahrazen implementací HADS.

## Co se skutečně spouští

`investigation.native_hermes_investigation` registruje jediný čtecí nástroj
`hads_read_evidence` do upstream registry a volá skutečný `AIAgent.run_conversation`.
Hermes sám zpracuje první modelový požadavek, zavolá nástroj, připojí jeho výsledek
do konverzace, provede další požadavek a další čtení a nakonec syntézu.
Neměníme upstream turn loop ani nenahrazujeme `AIAgent` test double.

Místní OpenAI-compatible endpoint je **skriptovaný testovací model**, který
vyžádá `automation`, podle získaného výsledku vyžádá `trace` a při návratu
`target_not_found` vytvoří český závěr. Test prokazuje native tool-loop a průchod
důkazů mezi tahy. **Neprokazuje kvalitu rozhodování jazykového modelu, řešení
živého incidentu ani schopnost obecného AI výzkumu.** Žádné placené API se nevolá.

Výsledek obsahuje SHA-256 kanonického vstupního snapshotu, seznam skutečně
provedených čtení, přesný runtime pin a označení `offline-container`. SHA binding
brání neúmyslnému přiřazení receipt k jiným důkazům; není kryptografickým podpisem
cizího runtime a nikdy nezastupuje uživatelské schválení změny.

## Bezpečnostní hranice

Host launcher má pevné argumenty Dockeru: `--network none`, read-only root,
UID/GID 65534, odebrané všechny capabilities, `no-new-privileges`, 512 MiB RAM,
žádný swap navíc, 64 PID, jeden CPU a 96 MiB dočasný tmpfs s `noexec,nosuid`.
Do kontejneru se připojují pouze dva veřejné zdrojové soubory read-only.
Důkazy jdou přes stdin; nejsou připojeny HA adresáře, Docker socket, tokeny,
konfigurační soubory ani hostitelský home. Proxy proměnné jsou v workeru prázdné.
Worker nemá cestu k zapisovacímu modulu a nenabízí shell, Python, HTTP ani MCP
write nástroje. Loopback testovací endpoint běží ve stejné síťové namespace.

Přesný katalog nástrojů kontrolujeme také po inicializaci; samotný allowlist
nebo proměnná `HADS_ISOLATED_TEST` nejsou OS izolací. `ReadGateway` přijímá
jen pojmenované, již připravené snapshoty: žádné URL, souborové cesty nebo kód.
Odmítá další argumenty, neznámé zdroje, opakované čtení a překročení rozpočtu.
Poskytovatel snapshotů musí odstranit tajemství před předáním do této vrstvy.

**Produkční spuštění zatím není připojené.** Test entry point je pouze pro
uvedený izolovaný kontejner a lokální testovací endpoint. Na HAOS nemůže HADS
spouštět další Docker kontejnery přes privilegovaný socket. Je nutné převést
native tool-loop do ověřené RC3 izolace chroot/UID/seccomp se spojeným FD
k důvěryhodnému modelovému/evidence brokeru a otestovat ji znovu v obou
architekturách. RC3 one-step JSON worker s `max_iterations=1` není vydáván za
nový native tool-loop. Do té doby M2 má pouze container proof-of-contract,
produkční aktivace a placené volání zůstávají blokované.

## Ověřené upstream možnosti a omezené alternativy

| Schopnost upstreamu | Zjištění ve pinned zdroji | Stav HADS Next / bezpečná alternativa |
|---|---|---|
| MCP client | `tools/mcp_tool*.py`, registrace `readOnlyHint`, include/exclude filtry | V workeru vypnuto; RO server-side broker musí mít exact-name katalog, nikoli důvěru pouze v hint |
| Tool discovery | `model_tools.get_tool_definitions`, registry-only toolset | Použit pouze `hads_evidence`; žádný obecný katalog write tools |
| Web search | Upstream web toolset a provider configuration | Neaktivováno; žádné placené hledání; budoucí broker vrátí citované omezené výřezy |
| Memory | Upstream `memory` toolset | `skip_memory=True`; historie z incident DB předaná jako read-only důkaz |
| Session search | `session_search` toolset | Vypnuto; budoucí filtrované hledání pouze v HADS spisech |
| Skills | Upstream skills a jejich autorská oprávnění | Automatické načítání/vytváření vypnuto; budoucí verzované, kontrolované textové postupy bez nových oprávnění |
| Delegation | `delegation` toolset / `delegate_task` | Vypnuto; jedna sekvenční vyšetřovací smyčka, logické specializace nemají další oprávnění |
| Další diagnostický krok | Native tool calls a konverzační smyčka `AIAgent` | Exercise přes dvě navazující čtení; nejvýše 4 iterace a 4 důkazy |

Osm požadovaných názvů rolí je definováno v `investigation.ROLES` jako smluvené
specializace. Tento první test vykonává čtení událostí a syntézu příčiny;
samostatné specialistické workflow pro všech osm rolí není hotové.

## Oficiální Hermes plugin Home Assistant

Ověřený zdroj `hermes-official-plugins` commit
`13b2c1c9c8204bf333df240b2aacf98c3e6250b7`, `homeassistant/README.md`.
Plugin požaduje Hermes >=0.21.5 a aiohttp >=3.9,<4; používá `HASS_TOKEN` (LLAT).
Má čtecí `ha_list_entities`, `ha_get_state`, `ha_list_services`, ale zároveň
zapisovací `ha_call_service`; gateway publikuje persistent notifications a může
volat notify služby. Entity allowlist omezuje cíle, neposkytuje samostatné
uživatelské schválení neměnného opravného plánu. Plugin proto přímo do analytika
nepřipojujeme. Nativní HA API přes observability poskytuje potřebná čtení bez
předání tokenu Hermesovi. Oficiální plugin nebyl spuštěn proti HAOS.

Zdroje:
- https://github.com/NousResearch/hermes-agent/tree/d923a5eb487a17c0a68801bba9ef0f56c81040a8
- https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/agent/tool_executor.py
- https://github.com/NousResearch/hermes-agent/blob/d923a5eb487a17c0a68801bba9ef0f56c81040a8/model_tools.py
- https://github.com/NousResearch/hermes-official-plugins/blob/13b2c1c9c8204bf333df240b2aacf98c3e6250b7/homeassistant/README.md

## Reprodukce

Z kořene `hads-next/`:

```sh
docker --host=unix:///var/run/docker.sock build \
  --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -f scripts/hermes_smoke.Dockerfile -t hads-next-hermes-smoke .
python scripts/hermes_smoke_run.py --output /tmp/hads-hermes-receipt.json
```

Vstup `--input snapshot.json` má tvar objektu s klíči `automation` a `trace`.
První fixture obsahuje `light.old_lamp`, druhá `target_not_found`.
Bez `--input` se použije vestavěná anonymizovaná fixture.
`--output` je hostitelský výstupní soubor, nikoli write oprávnění analytika.
Návratová hodnota neuzavírá incident ani neprovádí opravu.

Build instaloval originální runtime v cloudu. Při prvním sestavení se VFS
storage zaplnil kvůli opakovaným kopiím celého rootfs. Byly odstraněny pouze
konkrétní vlastní build artefakty a Dockerfile převeden na jeden instalační
RUN. Nemění se storage driver ani bezpečnost Docker daemonu. Reprodukce vyžaduje
několik GB volného místa; není to test paměťového profilu skutečné RPi/HAOS.

## Výsledek tohoto běhu

- `docs/evidence/hermes-native.json`: originální Hermes, 3 modelové požadavky,
  dva čtecí tool calls a česká syntéza; peak RSS 182435840 B.
- `docs/evidence/hermes-vertical.json`: tentýž native loop nad snapshotem
  skutečného offline vertikálního scénáře (ne test stub orchestrace),
  Python 3.14.10 / x86_64, peak RSS 182038528 B; obsahuje image ID a hash snapshotu.
- `docs/evidence/hermes-native-negative.json`: testovací endpoint se pokusil
  zavolat nepovolené `terminal`, `execute_code` a `tool_call` s příkazem vytvořit
  `/tmp/hads-write-canary`. Originální native loop se po chybných požadavcích
  zastavil; canary nevznikla. Jde o očekávaný negativní výsledek, proto
  `completed=false`, nikoli úspěšné vyšetření.
- `docs/evidence/hermes-dependencies.txt`: přesné instalované verze tohoto
  image. Finální build s tímto manifestem jako constraints skutečně prošel;
  všechny tři native testy byly zopakovány nad finálním image
  `sha256:da868e0fd12d26b10a34439e42e292548588f580a37c4efe5b172d948c224627`
  (linux/amd64, 513694006 B). `hermes-build.json` zaznamenává příkaz a SHA-256
  skutečně testovaných source/recipe/constraints/receipt souborů. Původní
  receipts před finálním buildem zůstávají v `hermes-prior-receipts.json`.
  Build odhalil chybějící execute bit nového package adresáře při
  `COPY --chmod=644`; finální instalační RUN explicitně nastavuje adresářům
  `/app` a `/app/hads_next` mód 755. Neprivilegovaný import i všechny testy
  poté prošly.
- Pět offline unit/negative testů hranice ReadGateway prošlo.

BuildKit v0.34.0 (driver docker) v tomto executor prostředí hlásí pouze
`linux/amd64`, `linux/amd64/v2`, `linux/amd64/v3`, `linux/amd64/v4`.
`/proc/sys/fs/binfmt_misc` je prázdný. **ARM64 build ani ARM64 spuštění zde
neproběhly**; nebyl instalován emulátor ani měněn daemon. RPi4/2GB, produkční
HAOS izolace, skutečný LLM, placené inference a reálný externí výzkum jsou
samostatné čekající přejímky.
