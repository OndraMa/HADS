# Bezpečnost instalačního souboru HAOS development preview

Tento dokument se vztahuje pouze k nové samostatné aplikaci `hads_next_investigation`.
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

Původní Hermes je součástí kandidátu 0.2.0-dev1. Model je opt-in; kontrola
připravenosti bez modelu načte skutečného agenta a ověří izolaci. Kořenový
pomocník se spouští před snížením UID controlleru, má pevný protokol a nezná
HA/model credentials. Worker má UID 65534, vlastní chroot, seccomp allowlist,
zákaz socketů/fork/exec a po načtení agenta také zákaz zápisů. Controller má UID
65532, nulové efektivní capabilities a no-new-privileges. Jediný zděděný broker
FD přenáší délkově omezené JSON; obecná HTTP/MCP/Python/shell cesta neexistuje.
Zápisový laboratorní server není součástí výchozího image ani schvalovací UI.

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

## Podklad kompatibility Supervisoru a dosud neověřená hranice

Kontrola upstream `home-assistant/supervisor` 2026.11.0:
`supervisor/docker/app.py` blob `4dcb3c53feeddc6f433e458db44db7ca9134d6b6`,
`docker/const.py` blob `7b2406ba700a60b1f8a5205eeb0307722bbcdbc7` a
`apps/build.py` blob `1e0ddb73db3170b86d0ab110c203bdafde730f58`.
Výchozí kontejnerové capabilities obsahují CHOWN, SETUID, SETGID, SYS_CHROOT;
reduced-capability režim této verze odebírá AUDIT_WRITE, MKNOD, SETFCAP.
Aplikace proto nepožaduje další `privileged` položky ani vypnutí AppArmor.
Build používá podporovaný BuildKit. Tyto zdrojové důkazy nejsou živá přejímka
konkrétního profilu HAOS: případné selhání musí zablokovat AI, nikoli vést k
obcházení protection mode. ARM64 a AMD64 runtime skutečně prošly kontejnerovým
seccomp/chroot testem; skutečný AppArmor profil a ingress čekají na HAOS.

Supervisor role `manager` a Core proxy poskytují i zapisovací oprávnění.
Vynucená hranice je procesové oddělení a úzký čtecí katalog, nikoli falešný
slib read-only tokenu. Kompromitace důvěryhodného controlleru není pokrytá
pouhým promptem analytika; audit a další HAOS přejímka zůstávají nutné.

Trvalé výsledky obou nativních architektur jsou v
`evidence/installation-0.2.0-dev1/ACCEPTANCE.json`. RPi, živý Supervisor,
OneDrive restore a produkční vykonavatel nebyly tímto během přijaty.
