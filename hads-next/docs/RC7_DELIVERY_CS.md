# HADS Next RC7 — šetření sběru a konkrétních entit

Audit vychází z uživatelem vložených obrazovek a zdrojů RC6. Nejde o živou diagnostiku domácnosti.
Dříve poskytnutý HTTPS MCP webhook byl zkusen pouze metodou `initialize`; vrátil **HTTP 503**.
Nebyl zavolán žádný MCP nástroj, placený model, restart nebo produkční zápis. Příčina selhání senzoru
komory proto z tohoto prostředí není doložená a nesmí se vydávat za zjištěnou.

## Konkrétní zjištěné chyby HADS

| Zjištění | Dopad a oprava |
|---|---|
| Watchman používá `unavail`; RC6 přijímal jen `unavailable` | Stav byl nesprávně `unclassified`. RC7 převádí doložený upstream formát. |
| Watchman odkazy skončily ve společném spisu bez dalšího čtení | RC7 automaticky propojí cíle s registry, Core stavem, dostupnou krátkou historií a pasivní ZHA/Toolkit diagnostikou. |
| Nabídka entit obsahovala jen `/api/states` | Chybějící/zakázané entity mohly z nabídky zmizet. RC7 přidává registry a známé odkazy Watchmanu. |
| Výpadek API a mezera odběru ZHA se počítaly jako funkční problém domácnosti | RC7 je eviduje jako diagnostické mezery, znovu ověřuje sběr a zachovává historii. |
| ZHA gap zůstával aktivní i po obnovení odběru | Aktuální odběr se znovu vyhodnocuje. Historická mezera se nevyplňuje a nic nedokazuje o fyzickém stisku. |
| Čekání na AI/zdroj nebo blokovaný worker se zobrazovalo jako čekání na uživatele | RC7 odděluje skutečné schvalování/funkční testy od chybějícího čtení či vypnuté AI. |
| Staré již nepotvrzené kontroly zůstávaly v aktivní části | Jsou ve sbalené historii; neoznačují se jako funkčně vyřešené. |
| Některé provider karty vybíraly především tlačítka a hlásily příliš obecnou chybu | Diagnostické senzory mají přednost; chybějící vlastní stav není automaticky výpadek API nebo MCP. |

## Skutečný rozsah jednotlivých zdrojů

| Zdroj | Stav po této opravě | Co dosud není hotové/ověřené |
|---|---|---|
| Watchman | Vlastní počty/podrobnosti, zdrojové časy a navazující konkrétní čtení cíle | Význam libovolného YAML/ESPHome/Lovelace výrazu, bezpečné nahrazení reference |
| ZHA | Pasivní nativní seznam zařízení, vazba přes registry; zachycené události s pokrytím | Živé rádio a fyzická odezva této domácnosti |
| ZHA Toolkit | Jeden pevný cache read `zha_devices`, validace odpovědi/verze, omezená pole a nativní fallback | Živá kompatibilita konkrétní instalace; RF reads/reporting a zapisovací operace |
| Spook | Přítomnost, vybrané entity a nativní Repairs | Samostatný opravný katalog registrů/statistik s ověřenou zálohou |
| Entity Availability / HAGHS | Nativní entity a vybrané stavy | Kompletní vlastní strukturovaná historie a celková funkční přejímka |
| Automation Inspector 1.2.4 / HADocs 0.17.0-rc5 | Inventář potvrzuje běžící aplikaci a verzi | Jejich autentizované vlastní reporty ještě nejsou připojené; běžící proces to nenahrazuje |
| HA-MCP / Hamster MCP | Nativní přítomnost, omezené entity | Obecný aktivní MCP klient, autentizace a katalog nejsou touto změnou dokončené |
| Music Assistant | Stávající omezený volitelný adaptér | Živá přejímka player/provider dat a fyzického rádia |

Ne všechny chybějící části lze opravit nastavením oprávnění. Samotný počet „9 z 9“ nikdy neověřoval
všechny externí doplňky; vztahuje se k devíti základním nativním čtením. Katalog providerů nyní obsahuje
i ZHA Toolkit a odděleně ukazuje výsledek skutečného omezeného čtení.

## Proč zatím nemusí být oprava ke schválení

Příčinou nedostupnosti může být stav registru, přejmenovaný odkaz, neznámá hodnota, nedostupné zařízení,
výpadek sběru nebo další dosud nedoložená příčina. Nalezení entity v reportu není bezpečný opravný plán.
RC7 zobrazuje konkrétní aktuální klasifikaci a další automatické čtení, místo aby požadoval obecný souhlas.

Pro čtení ZHA Toolkitu není potřeba povolit jeho obecný `execute`, export souborů, vlastní eventy, binding,
reconfigure, změnu kanálu, permit join nebo mazání. Tyto operace HADS nezpřístupňuje analytikovi.
Pokud není doložená konkrétní bezpečná změna nebo chybí vykonavatel, není co schválit.
Stávající úzký katalog vlastní CAS reference a vybrané jednoduché světelné aktivace zůstává oddělený.
Obecné Zigbee/registry/konfigurační opravy **nejsou dokončené** a OneDrive ochrany se neobcházejí.

## Kontrakty a bezpečnost

- ZHA read používá pouze `zha/devices` podle [Core 2026.11.1](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/zha/websocket_api.py).
  Nečte `zha/network/settings`, protože odpověď obsahuje síťová data včetně klíčového materiálu.
- [ZHA Toolkit revize 79205820d52bd4797c7dacf6b1184380ba7ca613](https://github.com/mdeweerd/zha-toolkit/tree/79205820d52bd4797c7dacf6b1184380ba7ca613):
  `__init__.py` registruje volitelnou service response; `zha.py:zha_devices` čte cache a může zapisovat CSV/JSON
  pouze přes zvláštní parametry. HADS je nepřijímá a neposílá. Přijímá výhradně úspěšnou validní odpověď.
  Starší interní gateway API Toolkitu může s konkrétním Core selhat; pak se zdroj označí neověřený a použije se nativní cesta.
- [Watchman format_state](https://github.com/dummylabs/thewatchman/blob/e0bf2481cb2d84022ac5124ad5dc4b731e5be526/custom_components/watchman/utils/utils.py)
  dokládá zkrácení unavailable na unavail.
- Žádný nový shell ani obecný service caller není součástí AI nástrojů. Hermes může číst pouze konkrétní
  již doložený cíl spisu; cizí entity a starší důkazy jsou odmítnuté/označené jako neaktuální.
- Omezený počet cílů, rotace, časový rozpočet dalších čtení, trvalé deduplikované důkazy a maximálně 256 aktuálních
  reportů. Při opakování nedostupnosti se zachová jeden spis zařízení, bez falešného uzavření po jediném úspěšném čtení.
- AI, nákladové limity, paměťová rezerva 576 MiB a schvalovací autorita se aktualizací nemění.

## Testy a přejímka

Výsledky konkrétního vydaného balíčku patří do `docs/evidence/installation-1.0.0-rc7/ACCEPTANCE.json`.
Bez tohoto úspěšného protokolu kandidát není vydaný. Unit kontrakty používají anonymizované fixtures;
nejsou důkazem funkce nainstalovaného ZHA Toolkitu. Nativní Core/Hermes s lokálním skriptovaným modelem
se testují odděleně od živého HAOS, fyzických senzorů a placeného modelu.

Živá přejímka po instalaci musí ověřit skutečné načtení Toolkitu, vazbu hlášeného senzoru na registry/ZHA,
aktuální stav a případně jediný vlastníkem potvrzený funkční test. Nevyžaduje od uživatele terminálové vyšetřování.
Při nedostupném připojení nebo nedoložené příčině zůstává stav výslovně neověřený; nevzniká náhodná oprava.
