> **Aktualizace 19. 11. 2026:** následující text uchovává přejímku předchozí zdrojové revize PR #19 z 17. 11. Aktuální instalační kandidát, nová integrační část a přesné zbývající meze jsou v [CANDIDATE_20261119_CS.md](CANDIDATE_20261119_CS.md). Starší protokoly se nevydávají za test nové revize.

# Živá přejímka orchestrace po RC7

**Stav: čeká.** Tento dokument není potvrzení provedeného testu ani pokyn instalovat
zdrojovou větev do domácnosti. Nový instalační kandidát dosud není vydaný.
Zdrojový PR, offline a kontejnerové důkazy jsou popsané v [souhrnu](ORCHESTRATION_REVIEW_CS.md).

Čtecí přejímka a přejímka zápisů jsou samostatné. Diagnostické připojení nepovoluje změny.
Zapisovací testy patří do oddělené instalace a na výslovně určené testovací objekty.
Bez takového prostředí zůstávají čekající; nenahrazují se zásahem do běžné domácnosti.
Přístupové údaje se nastaví soukromě v prostředí, nikdy v chatu nebo tomto repozitáři.

## 1. Původ instalace a čtecí připojení

Přejímající zaznamená přesnou zdrojovou revizi, hash budoucího image/payloadu,
architekturu, Core/Supervisor/HAOS verze a datum. Běžící RC7 není instalace tohoto PR.
Nejprve ověří vlastnictví přes skutečný ingress a nechá HADS dokončit jeho autonomní čtení.
Označení `installed`, `running`, `connected`, `authenticated`, `catalog_loaded` a
`diagnostic_read_verified` musí odpovídat skutečně provedeným krokům.

| Zdroj | Co musí HADS sám získat | Úspěch a hranice |
|---|---|---|
| Core/Supervisor/HAOS | Konkrétní info, registry, Repairs, System Health, logy a dostupné statistiky | Každé čtení má vlastní výsledek; devět nativních čtení nepotvrzuje všechny doplňky |
| Inspector | `/api/v1/status` a `/api/v1/inspection` | Ready, schema 2, verze a skutečný generated_at; chybné/stale čtení zůstává mezerou |
| HADocs | `/api/status` a `/api/summary` | Vlastní health/incidents/recommendations; neznámý čas existujícího reportu se nesmí vydávat za nový scan |
| Watchman | Počty, podrobnosti a časy jeho existujícího reportu | Znovunačtení nemění zdrojový čas; ESPHome a zakázané entity nejsou automaticky chyby referencí HA |
| Spook | Aktuální manifest, společné Repairs a skutečné HA služby | Podklady sdílené přes Repairs se neoznačí za výhradní nálezy Spooku; žádný nevyžádaný service call |
| HAGHS/Entity Availability | Vlastní strukturované atributy z registru a stavů | Skóre a skupinové počty jsou podklad, nikoli důkaz funkce celé domácnosti |
| HA-MCP | Initialize, identita/verze, celý dovolený katalog nebo tool-search a konkrétní čtení cíle spisu | Zaznamenat skutečný název nástroje, schema hash, úspěch a důkaz; obecné proxy model nedostane |
| Nativní MCP/Hamster | Aktuální katalog a konkrétní povolené čtení | Pro Hamster ověřené schema/call cesty; obecný call není diagnostický nástroj modelu |
| ZHA/Toolkit | Vazba registru na IEEE, native/cache údaje, journal a případné konkrétní standardní attr_read | Žádné přepárování, binding, reporting, zápis atributu či síťový scan |
| Music Assistant | Skutečné namapování přehrávače a odpovědi dovolených FastMCP sekcí | Health/player/events/buffer/logs podle skutečné dostupnosti, bez stop/play/volume testu |

Při chybě 401/403/503 nebo chybějícím endpointu se nevyžaduje terminálová diagnostika od vlastníka.
HADS uloží mezeru a použije dostupné nativní nebo jiné podklady. Pokud nezbytný přístup chybí,
požádá pouze o jeho jednorázové soukromé nastavení.

## 2. Pět praktických případů

| Případ | Přejímací podmínka | Co není úspěch |
|---|---|---|
| A: nedostupný Zigbee senzor | Jeden spis propojí Watchman, správnou identitu v registru, dostupnou historii, ZHA/Toolkit a relevantní závislosti. Odliší disabled/missing/unavailable/read_failed; nedoloženou příčinu ponechá výslovně neověřenou | Přejmenování podle podobnosti, domnělé potvrzení fyzického stisku, samotná verze Toolkitu |
| B: chybná automatizace | Inspector/HADocs/Watchman podle jejich dostupnosti dodají konkrétní závislosti, Core skutečnou konfiguraci a trace, Hermes si vyžádá další podklad. Návrh obsahuje přesnou podporovanou změnu nebo konkrétní ruční alternativu | Obecné doporučení, vypnutí diagnostiky nebo automatická náhrada entity bez stabilní identity |
| C: statistika | HADS porovná metadata, časový průběh a jednotku zdroje; odliší chybějící záznam od selhaného Recorderu. Mutace zůstane blokovaná, protože obecný opravný adaptér není implementovaný | Označení importu/statistické opravy za dokončenou funkci |
| D: rádio | Stav, akce, kontext, trace, Music Assistant a dostupné síťové/logové události ukážou doložený stop/odpojení/provider/stream, nebo přesně pojmenují chybějící důkaz | Zahájení či zastavení přehrávání kvůli testu bez samostatného požadavku, závěr pouze podle textu chyby |
| E: systém | HADS sám porovná Core/Supervisor/aplikace a skutečné časy; více následků DNS propojí jako možnou společnou příčinu | Součet statistik vydávaný za volnou RAM hostitele nebo restart podle jediného měření |

Jestliže událost právě nenastala, test se neoznačí jako úspěšně vyšetřená závada.
Přípustný výsledek je „nebylo možné reprodukovat“ se skutečnými podklady a mezerami.

## 3. Malý reálný modelový test

1. **Ověřit Hermes bez volání modelu** musí potvrdit skutečnou izolaci, původní runtime a
   paměťovou rezervu. Nenastavovat nižší rezervu kvůli získání zeleného výsledku.
2. Jednorázově nastavit poskytovatele podle [návodu](ORCHESTRATION_SETUP_CS.md), s vlastním malým
   limitem poskytovatele a výslovným souhlasem. Výchozí trial není automatická placená fronta.
3. Na jednom skutečném spisu doložit posloupnost: katalog → vybraný provider → konkrétní čtení →
   další potřebný důkaz → aktualizovaná hypotéza. Výsledek musí citovat uložená evidence_id.
4. Vyčerpání limitu zachová spis a zastaví další volání. Rozšíření režimu je nové výslovné rozhodnutí;
   nemá se nahrazovat opakovaným stiskem tlačítka nebo změnou API klíče.

Skriptovaný endpoint z CI nesplňuje tento bod. Není potřeba vymýšlet opravu, pokud reálný případ
nemá dostatečné důkazy. Takový výsledek se zaznamená jako omezený.

## 4. Připravenost skutečné opravy v odděleném prostředí

Nejdříve musí existovat **skutečný nezávislý ověřovatel obnovy OneDrive** a obnovení zálohy
pokrývající původní objekt. HADS ověřuje jeho podpis, scope, stáří, expiraci a target hash.
Testovací CI klíč nebo pouhý upload se nepřijímá. Propojení s produkčním HABS není součástí
prokázané živé integrace tohoto PR; bez něho se test zápisu nepřekročí.

Operátor připraví jeden jednoduchý testovací světelný scénář nebo konkrétní uživatelem zakázanou
testovací entitu. U změny reference musí HADS pozorovat stejnou stabilní identitu před a po přejmenování.
Příprava záměrně chybné fixture patří operátorovi odděleného testu, nikoli diagnostice skutečné závady vlastníkem.

HADS sám připraví neměnný plán. Přejímající ověří, že obsahuje poskytovatele, nástroj, schéma,
cíl, parametry, původní stav, rozdíl, důkazy, riziko, zálohu, preflight, funkční podmínku,
návrat a ruční alternativu. Potom vlastník jednou schválí přesný plán a výlučnou práci s cílem.

Očekávané výsledky:

- Provede se právě jedna schválená operace a zpětné čtení odpovídá přesnému rozdílu.
- HA-MCP má `run_actions:false`. Uložení konfigurace samo nesmí spouštět světlo.
- Spook mění pouze povolení konkrétní entity; nevypíná hlášení ani nemaže registr.
- Případ zůstane otevřený do nového skutečného triggeru/stavu/kontextu, požadovaného
  fyzického potvrzení a nejméně 30 sekund souvislého pokrytí podle konkrétní operace.
- Předčasné potvrzení vlastníka nebo HTTP úspěch případ neuzavře.
- Návrat změny je nový plán s novým souhlasem, kontrolou cizích změn a čtením výsledku.
  Návrat nesmí použít staré ID, pokud už patří jinému zařízení. Nevrací fyzické účinky ani celé HAOS.

Poruchy zápisu, falešné souhlasy a úmyslné přerušení uprostřed zásahu se injektují pouze
v izolovaných kontraktních testech. Kvůli přejímce se nepřerušuje běžný HAOS.
Při skutečně nejistém výsledku má HADS automaticky pouze přečíst stav, neopakovat zápis,
blokovat další zásahy brokeru a případně nabídnout nové vlastnické přijetí pozorovaného
stavu k funkčnímu testu. Toto rozhodnutí nesmí znovu provést původní příkaz.
Po vyčerpání automatických kontrol může vlastník v témže spisu nejvýše jednou za minutu
vyžádat **Znovu ověřit nejistý výsledek bez zápisu**. Není to retry původní operace.
Nový schválený zásah nebo rollback zneplatní předchozí uzavření spisu; samotná změna konfigurace
se nezapočítá jako nový skutečný výskyt funkční závady.

## 5. Opakování a prostředky

Pro dlouhodobé opakování musí být definovaná funkční podmínka/monitor stejného spisu.
Běžná změna stavu není automatické selhání. Potvrzená nová nesplněná podmínka musí znovu
otevřít spis, uložit výskyt a český report; nesmí znovu použít původní souhlas.

Na RPi 4/2 GB zaznamenat alespoň 15 minut skutečné dostupné paměti, spotřeby HADS/Core/aplikací,
CPU a latence čtení při lokální diagnostice i během jednoho povoleného vyšetřování.
AI nesmí běžet pod povinnou rezervou. ARM64 build ani měření na CI runneru tento test nenahrazuje.

## 6. Protokol a rozhodnutí o vydání

Každý bod uloží `passed / failed / blocked / not_reproduced`, skutečný čas, zdrojovou revizi,
identifikátory lokálních spisů a otisky příslušných důkazů. Produkční exporty se nevkládají do veřejného repozitáře;
sdílí se jen výslovně zvolený anonymizovaný protokol bez tokenů a privátních URL.

Stávající dvanáctibodový webový průvodce pokrývá původní přejímku RC7. Sám nepotvrzuje
nové konektory a schvalovaný broker; tato doplňující přejímka musí být doložená zvlášť.
Chybějící statistické/Zigbee/obecné konfigurační opravné adaptéry se zapíší jako neimplementované,
nikoli jako zelený test. Vydání ani úplné splnění zadání se neodvodí pouze z počtu prošlých kontrol.
