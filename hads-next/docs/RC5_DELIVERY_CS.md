# RC5: kontrola dostupných doplňků a přenos nastavení bez starých oprávnění

RC5 zahrnuje následnou opravu nativních System Health/Repairs reportů z PR14
a nové nativní ověření devíti zdrojů. HASK je na přání vlastníka vynechaný.
Přehled rozlišuje aktuálně načtenou komponentu, aplikaci a její stav/verzi,
vlastnictví entit podle registry platformy, skutečně načtené stavy a neověřený
vlastní funkční kontrakt. Samotný starý záznam registru nepotvrzuje instalaci.
Názvová shoda aplikace je stopa v inventáři, nikoli ověření jejího upstream původu.

Stav integrační entity může být soukromý text. Obecný přehled proto ukládá jen
omezené kategorie a konečná čísla, čas změny a nejvýše čtyři entity zdroje.
Nepřenáší libovolné atributy, přístupové URL, tokeny ani app options do přehledu
nebo AI. Opakování aktualizuje jediný stav zdroje, nevytváří incidenty ani
nové nálezy. Čas změny stavu není čas skenu doplňku. Výsledek starší než deset
minut je označený. Nativní kontrola běží ve stávající pravidelné čtecí frontě.

Tebou dodaná entita sensor.system_ha_global_health_score je navíc známým
čtecím cílem pro HAGHS. Nedokazuje sama balíček ani verzi. Výpis dostupnosti
99,8 % a nulových počtů je údaj vlastníka, nikoli nová živá přejímka HADS.
Verzi 2.4.2 nepřiřazujeme svévolně konkrétnímu balíčku bez jeho identity.

## Co se ze starého Hermes skutečně převzalo

Archiv Hermes 2.0.0-rc3 byl před čtením ověřen SHA-256:
`fc57575471294dc968d78c4474db2ae1717b6c37b5aba1aab6246799febcf848`.
Přečteny byly config.yaml, tool_adapters.py a příslušné regresní testy.
Je to důkaz původu vývojového podkladu, nikoli důkaz shody s běžící instalací.
Původní archiv zůstává nedotčený a nebyl spouštěný.

Známá připojovací pole pro HA-MCP, Hamster MCP, Music Assistant MCP, HADocs
a Automation Inspector lze přes ověřeného vlastníka převzít jedním pevným
čtením Supervisoru z aplikace local_hads4 verze 2.0.0-rc3. Import vybere jen
deset známých polí, nikdy nepředává ostatní options do evidence nebo modelu.
Záložní cestou je soukromý formulář pro skutečný export JSON options.

Návrh je uložený s oprávněním 0600 a zůstává **neaktivní**. Neukládá souhlasy,
AI klíč, náklady, automatické zápisy, historickou důvěru ani celý starý adaptér.
Prázdné výchozí hodnoty a maskované tokeny se nevydávají za použitelné nastavení.
Neznámá stará verze, neplatná cesta a symlinky se odmítnou.

Přiložený výpis z 6.–8. listopadu neobsahuje samotné nastavení připojení.
Ukazuje jen historické katalogy a částečné výsledky. Z něj nebylo možné
přenést adresy ani tokeny nebo prokázat funkčnost nástrojů.

## Hranice této verze

**RC5 ještě neobsahuje plné funkční adaptéry HA-MCP, Hamster, HADocs nebo
Automation Inspector.** Neaktivní návrh je automaticky nezapíná. Zobrazuje
neověřený kontrakt, ne úspěšnou přejímku. Dostupnost přes vlastní API a konkrétní
data pro incident je potřeba doplnit a testovat proti skutečnému kontraktu.
Existující MA FastMCP klient nadále vyžaduje vlastní ověřené nastavení a mapování.
Spook/Watchman lze využívat přes dostupné nativní nálezy, neprokazujeme však
jejich vlastní aktuální sken ani úplnost všech funkcí.

Obecné zápisy Spook/HA-MCP, YAML, registru a statistik nejsou hotové. Schválený
katalog zůstává původní úzký CAS test a jednoduchá světelná aktivace. Nic se
v domácnosti automaticky neopravuje, nerestartuje ani neskenuje voláním služby.
Paměťová brána 576 MiB, limity AI a zálohové požadavky zůstávají zachované.

Instalátor --upgrade-rc4 kontroluje přesný vydaný manifest RC4:
`8877726850f7d9bd17ecadb8c0b7966b103b177b2b86e5bb5d8acee5554149e9`.
Aktualizuje pouze Next přes nativní Supervisor s částečnou zálohou, zachovává
data i předchozí stav. Stará vydání, main a původní Hermes se nemění.

## Ověření

Izolované testy ověřují oddělení přítomnosti/procesu/dat/funkce, stáří zdrojů,
chybějící data, omezení velikosti, opakování bez incidentů a soukromý import
včetně role/CSRF a nepřenesených oprávnění. Skutečný Core/Hermes používá
samostatnou nativní kontejnerovou přejímku se skriptovaným HTTPS modelem.
Aktualizační test používá skutečné vydané RC4 zdroje a falešný Supervisor CLI.
Přesné výsledky a SHA-256 instalátoru jsou přiložené níže.

Přejímka zdrojové revize `a495bd1a36808cfcbb7faca087f02ff80615f8bc` je nyní
dokončená: 249 testů na každé nativní architektuře ARM64/AMD64, skutečný Core
a původní izolovaný Hermes se skriptovaným HTTPS modelem. Produkční image bez
Core fixture zvládla SIGTERM s kódem 0 a zachovala data po restartu. Skutečný
instalátor provedl aktualizaci skutečných RC4 zdrojů proti falešnému HA CLI,
vyžadoval zálohu a odmítl opakování. Obě architektury vytvořily identický
instalátor i zdrojový archiv. Všech 57 souborů payloadu je porovnáno s Git revizí.

Prohlížeč prošel 18 zobrazeními a uchoval snímky. Jeho poslední commit
`c07ddd8f57fffef2dfcb952c7b1f77f41c61707b` mění pouze uchování těchto artefaktů;
vstupní soubory aplikace, testů a prohlížečového scénáře odpovídají stejné
testované zdrojové revizi. Protokoly jsou v `docs/evidence/installation-1.0.0-rc5`
a `docs/rc5-review`.

[Nativní přejímka](https://github.com/OndraMa/HADS/actions/runs/43538178130) ·
[Prohlížeč a snímky](https://github.com/OndraMa/HADS/actions/runs/43539064833).
SHA-256 instalátoru: `1e998799eab0ae66409b989dccd9f8d497f17e77d8af9ae20abd088856c67ff4`.

Živá HAOS aktualizace a obnova, skutečné funkce externích doplňků, reálný LLM,
RPi při domácí zátěži a fyzické rádio/Zigbee zůstávají neověřené. Toto vydání
je vývojový instalační kandidát a neplní ještě celou původní definici úspěchu.
