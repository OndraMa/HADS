# Přejímka RC3: Marketplace a paměť pro Hermes

Uživatel po obnově doložil spuštěné RC3, devět přečtených zdrojů a nález
`system_health_failure` pro `integration:marketplace`, konkrétně `github_web`.
Původní export obsahuje pouze název neúspěšné kontroly. Neobsahuje chybový kód,
URL, stav HTTP ani nezávislý důkaz příčiny nebo funkčního dopadu. Nelze z něj
prokázat chybu DNS, TLS, GitHubu nebo HAOS. Další uživatelský údaj je dostupná
paměť 373 MiB při bráně 576 MiB: do hranice chybí nejméně 203 MiB; také je
potřeba provozní rezerva. Není doloženo, která aplikace paměť spotřebovává.

Jde o **uživatelem předané živé pozorování**, nikoli nezávislou cloudovou
přejímku. Přímé autentizované HAOS připojení a modelový výsledek nejsou dostupné.
Zpráva neobsahovala výsledek tlačítka ověření izolovaného Hermesu. Nenahrazujeme
jej kontejnerovým výsledkem. Uživatelská ID, soukromá síťová adresa a ingress
odkaz se do fixtures ani této dokumentace nekopírují.

## Oprava ve zdrojích

- Nativní diagnostická kontrola a rezerva HADS mají vlastní viditelnou sekci.
  Samy se nepočítají jako poruchy funkcí domácnosti. Ručně nahlášený funkční
  incident zůstává v hlavním seznamu; žádný spis se nemaže ani neuzavírá.
- Detail starého i nového spisu vysvětlí konkrétní integraci a kontrolu,
  explicitně přizná chybějící chybový kód a nabídne podporované opakované
  nativní čtení bez modelu přes stávající CSRF chráněnou akci `setup/check`.
- Nové důkazy uchovávají pouze bezpečně vybrané chybové kódy z existujícího
  pole `error` odpovědi `system_health/info`. Volné zprávy, hlavičky a URL se
  neukládají. Nerozpoznaný kód se označí jako `unclassified`, nevykládá se.
  Nepřibývá žádný endpoint, webový scraping ani externí síťová sonda.
- Neúplný System Health stream nesmí deaktivovat dříve neúspěšnou kontrolu.
  Ani úspěšné nové diagnostické čtení automaticky neuzavírá funkční spis.
- Paměťový důkaz uchová skutečné měření při prvním nálezu a po novém výskytu.
  Běžné kolísání paměti nevytváří nové výskyty ani AI analýzy. Historický spis
  bez měření nedostane vymyšlenou hodnotu; aktuální údaj je v připravenosti.
- Nálezy samotné diagnostiky nebo paměti automaticky nevolají placenou AI.
  Stávající výslovné povolení a gate skutečného workeru zůstávají zachované.
- Odkazy na světelné opravy a příprava testovací reference se zobrazují jen
  u spisů s odpovídající komponentou automatizace.

## Hranice dodávky

Tato větev je zdrojová oprava pro další instalační kandidát. Již vydaný RC3,
jeho instalátory, obnovovací balíček a produkční instalace se zde nemění.
Testovaný kód není touto změnou automaticky nainstalovaný u uživatele. Není
důvod znovu odinstalovávat běžící RC3.

Lokální i nativní CI testy používají anonymizované fixtures, včetně 373 MiB
a tvaru Marketplace nálezu. Testy prokazují práci s důkazy a bezpečnostní
hranice, nikoli živý přístup Marketplace ke GitHubu nebo běh Hermesu na
konkrétním Raspberry Pi. Prohlížečová přejímka kontroluje desktop, mobil,
oddělení diagnostických nálezů a konkrétní další krok bez nesouvisející opravy.

## Další živé kroky

Na již nainstalovaném RC3 přečíst z nativních systémových informací pouze
sekci Marketplace a při opakování odpovídající časový úsek jeho protokolu.
Pro paměť nejprve porovnat podporované statistiky Core a běžících aplikací.
Nezastavovat náhodně aplikace a neměnit DNS podle samotného názvu kontroly.
Po případném vlastníkem zvoleném uvolnění prostředků znovu změřit paměť a
provést kontrolu izolovaného Hermesu bez modelu. Rizikové zásahy, placené
volání modelu nebo změna domácích automatizací nejsou součástí těchto kroků.
