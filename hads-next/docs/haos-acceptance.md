# Živá přejímka RC4 — automatická diagnostika, stav ČEKÁ

Tento dokument je protokol pro skutečný HAOS. Kontejnerové testy, obrázky
z anonymizované fixture ani předaný text se nevydávají za nezávislou živou přejímku.
Cloud při přípravě kandidáta neměl autentizovaný přístup k cílové instalaci.
Žádná produkční oprava nebyla z cloudu vykonána.

## 1. Pouze úvodní aktualizace

Stáhnout přesný RC4 instalátor a porovnat SHA-256 s ACCEPTANCE.json.
Běžící RC3 předem nezastavovat ani neodinstalovávat. Postup je v přiloženém
českém návodu: --verify a --upgrade-rc3. Nativní update má vyžadovat částečnou
zálohu jen HADS Next a zachovat spisy a vlastníka. Při nejistém výsledku
zůstane marker a další zásah se nesmí opakovat automaticky.

Zaznamenat skutečnou verzi Core, Supervisor, OS, architekturu a verzi RC4
z HADS. Dokončení aktualizace není funkční ověření a záloha sama není důkaz restore.

## 2. HADS samo přečte zdroje

Po otevření má HADS samo zahájit nativní kontrolu. Zaznamenat konkrétní úspěšná
čtení a chyby; dostupné spojení se nepočítá za přečtenou diagnózu. Klíč AI není
potřeba. Žádné diagnostické příkazy v terminálu nejsou součástí tohoto kroku.

## 3. Paměťový incident

Pokud dostupná paměť nedosahuje rezervy 576 MiB, HADS má samo vytvořit spis,
načíst Core/Supervisor statistiky a běžící aplikace, uložit časy, skutečnou
spotřebu a limity a ukázat tabulku. Nedostupná aplikace se nepočítá jako nula.
Nejvýše 24 aplikací; omezení pokrytí musí být viditelné.

Po následující automatické kontrole (nejdříve po pěti minutách) má HADS samo
přidat jedno porovnání Core, Supervisora a nejvýše tří aplikací. Změny paměti
musí mít skutečný čas a neprohlašovat se za únik paměti. Stejné načtení nesmí
vytvářet další výskyt. Spis se neuzavře jen dokončením sběru nebo ústupem hlášky.

## 4. Marketplace/github_web

Pokud se kontrola opakuje, HADS má samo zachovat konkrétní pole a bezpečný
chybový kód, dohledat související čerstvé System Log záznamy a provést jediný
pevný veřejný HEAD bez domácích dat a přesměrování. Výsledek se výslovně váže
k síti aplikace HADS a nezaměňuje za přístup integrace v Core. Neúplný stream
nesmí zrušit dřívější neúspěšnou kontrolu. Bez prokázané příčiny žádná změna DNS.

## 5. Izolovaný Hermes bez modelu

Úvodní kontrola má sama ověřit načtení původního Hermesu a izolaci. Při nesplněné
rezervě musí srozumitelně uvést paměťové omezení a ponechat místní čtení v chodu.
Žádný modelový požadavek se při této kontrole neposílá. Stav tohoto kroku
zůstává čekající, dokud skutečně neproběhne v daném HAOS s dostatečnými prostředky.

## 6. Volitelný omezený skutečný model

Teprve po připravenosti a výslovném rozhodnutí vlastníka zadat klíč v privátním
nastavení poskytovatele. Výchozí test: tři požadavky za klouzavých 24 h,
48 000 bajtů vstupu a 512 výstupních tokenů, bez automatické placené fronty.
To není garantovaný dolarový strop. Zaznamenat skutečný model, souhlas,
počet odeslaných požadavků, nástroje, důkazy a co model nedokázal. Úspěšný
modelový JSON sám neuzavírá incident.

## 7. Zápisy a fyzické funkce

Samostatné schválení konkrétního neměnného plánu, kontrola cíle před provedením,
negativní pokusy bez schválení, deduplikace po restartu, podporovaný rollback
a skutečný funkční výsledek se testují odděleně. Vlastní CAS reference vyžaduje
oddělenou virtuální testovací instalaci. Pokud není dostupná, krok zůstává čekající;
produkční domácnost ji nenahrazuje. Světelná oprava vyžaduje explicitně vybraný
bezpečný cíl, schválení a skutečné funkční i fyzické ověření. Zálohové a OneDrive
kontroly rizikových operací se nesmějí obejít.

Rádio/Music Assistant a Zigbee vyžadují skutečné dostupné zdroje, očekávané
chování zvolené vlastníkem a konkrétní událost. Nepřečtený FastMCP ani nezaznamenaný
fyzický stisk se nevydávají za ověřené. Nenastavuje se hlasitost ani přehrávání
jako nevyžádaný diagnostický test.

## Výstup přejímky

U každého bodu skutečný čas, verze, PASS/FAIL/PENDING, omezení a export reportu
HADS bez klíčů. Dokud povinné živé kroky nejsou splněné, kandidát se neoznačuje
za produkčně přijatý nebo plně funkční v cílové domácnosti.
