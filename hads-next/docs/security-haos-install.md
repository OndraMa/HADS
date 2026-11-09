# Bezpečnost instalačního souboru HAOS development preview

Tento dokument se vztahuje pouze k nové samostatné aplikaci `hads_next_dev`.
Nejde o aktualizaci RC3, migraci jeho databáze ani schválení oprav domácnosti.
Živé změny entit, automatizací, integrací, záloh, zařízení a historie nejsou
v katalogu této aplikace. Originální HADS a jeho data se instalací nemění.

## Hranice vůči zálohám RC3

RC3 má nezávislý OneDrive readback gate před zapisovacími opravami. Porovnává
velikost a SHA-256 skutečně staženého objektu; sám nedokládá obnovitelnost celé
instalace. Tento gate musí zůstat zachován. Historická instalační výjimka RC3
`no_preinstall_ha_or_cloud_backup_user_requested` se na Next nepřenáší a nový
instalátor ji nepoužívá jako souhlas k obcházení zálohy.

Instalace preview přidává oddělenou lokální aplikaci. Nepřepisuje existující
zdroje, neimportuje databázi RC3, nepřebírá jeho souhlasy a nevolá žádnou opravnou
operaci. Nehlásí, že byla vytvořena nebo ověřena HAOS/OneDrive záloha. Jakékoli
budoucí rozšíření na aktualizaci RC3, migraci konfigurace či živý opravný writer
je jiný scénář a musí splnit původní zálohové a nové identity/restore brány.

## Kontroly obalu

Instalátor musí před zápisem ověřit SHA-256 vloženého archivu. Členy payloadu
musí mít relativní normalizované cesty bez `..`, absolutní cesty, symlinků,
hardlinků, zařízení a kolizí jmen. Publikovaný manifest musí umožnit reprodukovat
obsah z čitelných verzovaných zdrojů. SHA-256 kontroluje integritu bajtů;
neznamená podpis vydavatele nebo audit živé funkce.

Výstupní adresář nové aplikace nesmí existovat ani být symbolickým odkazem.
Instalátor nesmí automaticky odstraňovat či přesouvat existující adresář stejného
jména. Výhradně dočasná pracovní složka vytvořená daným během může být automaticky
uklizena. Selhání Supervisoru po instalaci je nejasný stav: žádný automatický
uninstall, restart starého HADS, mazání dat ani skrytý návrat změn se nekoná.
Instalátor musí zachovat zdroje a srozumitelně sdělit, kterou fázi nepotvrdil.

Režim `--extract-only` slouží nezávislé offline prohlídce. Nikdy nesmí volat `ha`,
Supervisor, Docker ani spouštět kód z payloadu. Rozbalení do existujícího adresáře
a přes symlink v cestě je odmítnuto stejně jako při instalaci.

## Oprávnění runtime

Aplikace nemá host networking, Docker socket, privilegovaný režim nebo mount
konfigurace Home Assistantu. Token pro nativní čtení Core zůstává v transportní
vrstvě; není součástí exportu, logů, AI snapshotů ani HTML. Pouhé povolení Core
API nečiní token read-only: omezení zajišťuje úzký katalog podporovaných GET
čtení a absence write rozhraní v aplikaci. Není to token s odděleným oprávněním
na straně Home Assistantu.

Externí model ani Hermes produkční worker se automaticky nezapíná. Kontejnerový
Hermes test ze staršího milníku není dokladem izolace skutečného HAOS workeru.
Dokud nebude broker/worker a jeho identita samostatně přijatá na HAOS, musí být
produkční AI a všechny opravné zápisy blokované.

Povolení ingress v konfiguraci také není samo o sobě test identity. Před živou
přejímkou musí být ověřeno, že nepřímý přístup k portu z jiné aplikace nemůže
vydávat autentizované požadavky nebo obejít hranici důvěry Supervisor gateway.
Tato verze neposkytuje schvalovací ani obecné REST/MCP zapisovací endpointy.

## Rozsah nových testů

Izolované testy instalačního obalu ověřují integritu, odmítnutí změněného payloadu,
kolize cíle a symlinky, omezení rozbalených cest a skutečnost, že inspekční režim
nevyvolává `ha`. Zkouška s fake HA CLI dokládá pouze přesnou posloupnost příkazů,
nikoli funkci Supervisoru. Docker build dokládá import a běh balíčku v konkrétní
architektuře, nikoli instalaci na živém HAOS nebo fyzický výsledek v domácnosti.

ARM64, Raspberry Pi 4/2 GB, skutečný ingress, Core API autorizace, stav po restartu
HAOS a zachování RC3 musí mít samostatné live účtenky. Do té doby zůstávají v
přejímacím protokolu jako čekající.
