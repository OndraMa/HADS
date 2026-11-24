# HASS-AI-Orchestrator: co lze převzít pro HADS

Kontrola 14. 11. 2026, projekt [ITSpecialist111/HASS-AI-Orchestrator](https://github.com/ITSpecialist111/HASS-AI-Orchestrator),
revize **cebfdff5d5a950ea9ad2cd166f7768af997e4d3b**, manifest **0.13.6**.
Zkontrolovány README, manifest, plan_executor, deep_reasoning_agent, main, external_mcp a requirements.
Jde o kontrolu zdrojů a dva malé izolované reprodukční testy, nikoli živou přejímku projektu ani celou jeho testovací sadu.

**Ano, jeho cíl velmi dobře odpovídá požadované práci HADS. Hotovou náhradu celého zadání ale tato verze neposkytuje.**
Má vícekolové uvažování, nativní nástroje HA, volitelný MCP klient, perzistentní konkrétní plány,
uživatelské posouzení, checkpointy a uživatelsky zaměřený dashboard. Je vhodný jako zdroj návrhu a kandidát
pro ohraničenou integraci; ne jako druhý paralelní neomezený správce produkční domácnosti.

| Požadavek HADS | Zjištění v kontrolované revizi |
|---|---|
| Model žádá další čtení a dostane výsledek | Implementovaný tool loop, schémata a limity |
| Konkrétní plán bez druhého přegenerování modelem | RecordedIntent a deterministický replay; pozitivní základ |
| Ochrana proti dvojímu vykonání | Atomické převzetí plánu, stav executing a checkpointy; nejistý zásah se automaticky neopakuje |
| Každý zápis schválí vlastník | README připouští rutinní auto akce. Výchozí politika není totožná s požadavkem HADS „všechny změny po mém schválení“ |
| Neměnný plán, autenticita vlastníka, expirace, aktuální cíl | V posuzované cestě execute není samostatně doložena celá sada těchto kontrol; samotný hash intentu a stav plánu nestačí |
| Funkčně ověřená oprava | README ji výslovně uvádí jako příští milestone. Service success neprokazuje výsledek zařízení |
| Záloha, OneDrive obnovitelnost, autorizovaný rollback | Pro požadovaný obecný katalog HADS v kontrolovaných cestách nedoložené |
| Opravy HAOS, konfigurací, registrů a statistik | Výchozí blocked_domains zahrnují hassio, script, automation, rest_command; nejde o hotový katalog těchto oprav |
| Originální Hermes | Používá vlastní kernel a modelové adaptéry. Automaticky nesplňuje požadavek originálního Hermesu |
| RPi 4 / 2 GB | ARM64 je uvedená podporovaná architektura, ne měření RAM. Doporučený lokální model má podle README artefakt asi 9,6 GB; pro toto zařízení potřebuje vzdálený model nebo jiný stroj |
| Kontrola celkových nákladů | Limity iterací/času/tokenů nejsou doložený společný dolarový strop HADS; samostatný orchestrátor může vytvořit další placenou frontu |

## Konkrétní kontrolované hranice

1. `plan_executor._result_ok` přijímá neznámý nedict výsledek jako úspěch; dokonce `None` a libovolný
   text vrací True. Také pending_approval chápe jako planner success. V HADS se tyto stavy nesmějí vydávat
   za vykonanou a funkčně ověřenou opravu. Ověřeno izolovaným vykonáním této funkce.
2. `main.APIAuthMiddleware` má volitelný bearer token; požadavek s hlavičkou `X-Ingress-Path`
   považuje za ingress bez kontroly zdrojového peeru v tomto middleware. Manifest současně používá
   `host_network: true`. Izolovaný test třídy potvrdil průchod s touto hlavičkou bez bearer tokenu.
   To není důkaz dostupnosti portu nebo zneužitelnosti konkrétní nasazené instalace — další síťové kontroly
   nebyly testované. Je to ale nedostatečná hranice, na kterou bych připojil opravná oprávnění HADS.
3. `/api/reasoning/plans/{plan_id}/execute` předává pouze ID do execute_plan; následný replay dostává
   `approved=True` jako kontext. Není to doklad podpisu schválení konkrétním vlastníkem nebo aktuálního
   snapshotu cíle. PlanStore dovoluje převzít pending/approved a nemá časovou expiraci v této metodě.
4. Upstream v README sám transparentně uvádí chybějící post-action verification a další plánovaný vývoj.
   To jsou podstatné mezery pro naše zadání, nikoli důvod jeho užitečné části přehlížet.

Výsledky dvou izolovaných kontrol a SHA-256 kontrolovaných souborů jsou v
[orchestrator-source-audit.json](evidence/orchestrator-source-audit.json).
Údaje README o počtu testů, bezpečnosti závislostí a živých ukázkách jsou tvrzení upstreamu;
v tomto auditu nebyly nezávisle zopakované. V rekurzivním stromu nebyl nalezen LICENSE a GitHub metadata
uvádějí license null. Před přímým převzetím kódu je potřeba vyjasnit licenci; návrh rozhraní lze posoudit již nyní.

## Doporučené zapojení

Neinstalovat nyní druhý AI server na paměťově omezený HAOS jako podmínku funkce HADS.
Převzít ověřitelné principy: konkrétní uložené intenty, checkpointy, viditelnou frontu schválení a úsporný kernel.
Hermes zůstane analytikem HADS. Pokud se později připojí Orchestrator, začít omezeným čtecím zdrojem
bez přenosu jeho schválení nebo spuštění automatických cílů. Žádný exportovaný plán se automaticky nespustí.

Případné opravné intenty musí znovu projít katalogem HADS, identitou vlastníka, expirací, přesným cílem,
zálohou, preconditions a funkčním ověřením. Dva nezávislé schvalovací systémy ani stejný API token
nesmějí vytvořit alternativní cestu kolem těchto kontrol.

To znamená **zahrnout do technického návrhu a posouzení integrací ano; označit za hotový chybějící
diagnostický a opravný engine nebo ho automaticky zapnout ne**. Produkční instalace nebyla změněna.

Zdroje pro opakování kontroly:

- [README a deklarované limity](https://github.com/ITSpecialist111/HASS-AI-Orchestrator/blob/cebfdff5d5a950ea9ad2cd166f7768af997e4d3b/README.md)
- [PlanStore a replay](https://github.com/ITSpecialist111/HASS-AI-Orchestrator/blob/cebfdff5d5a950ea9ad2cd166f7768af997e4d3b/ai-orchestrator/backend/plan_executor.py)
- [execute_plan](https://github.com/ITSpecialist111/HASS-AI-Orchestrator/blob/cebfdff5d5a950ea9ad2cd166f7768af997e4d3b/ai-orchestrator/backend/agents/deep_reasoning_agent.py)
- [API middleware a execute route](https://github.com/ITSpecialist111/HASS-AI-Orchestrator/blob/cebfdff5d5a950ea9ad2cd166f7768af997e4d3b/ai-orchestrator/backend/main.py)
- [Manifest 0.13.6](https://github.com/ITSpecialist111/HASS-AI-Orchestrator/blob/cebfdff5d5a950ea9ad2cd166f7768af997e4d3b/ai-orchestrator/config.json)
