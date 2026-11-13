# HADS Next RC4 — HADS provádí diagnostická čtení samo

Pracovní kandidát: dokončuje se přejímka opravy souběhu při startu. Pro instalaci
vyčkej na vydání označené tagem `hads-next-1.0.0-rc4`; tyto pracovní soubory se
před prvním vydáním nahradí přesnými nově ověřenými bytes.

[Instalační skript](HADS_Next_install_1.0.0-rc4.sh) ·
[Kompletní ZIP se zdroji a návody](HADS_Next_1.0.0-rc4-komplet.zip) ·
[Český návod](HADS_Next_1.0.0-rc4-navod-CS.md) ·
[Ověřené výsledky a zbývající hranice](VYSLEDKY_A_OMEZENI_CS.md) ·
[Živá přejímka](AKCEPTACE_HAOS_CS.md) · [Přesný obsah integrací](INTEGRATIONS_CS.md)

V přihlášeném GitHubu použij **Download raw file**. Pro aktuální běžící RC3
stačí nahrát nový `.sh` do `/config` a provést úvodní aktualizaci:

```sh
bash /config/HADS_Next_install_1.0.0-rc4.sh --upgrade-rc3
```

Instalátor ověřuje vlastní vložený balíček před změnami. Samostatná kontrola je
`bash /config/HADS_Next_install_1.0.0-rc4.sh --verify`.
**RC3 předem nezastavuj ani neodinstalovávej.** Supervisor aktualizuje jen HADS Next
s nativní částečnou zálohou jeho dat. Sestavení může trvat několik minut;
nespouštěj současně další instalátor. Při chybě zachovej hlášku a marker,
nic nemaž. Stav error, vlastní změny zdrojů a nedokončený zásah se neobcházejí.

Po aktualizaci otevři HADS. Nativní zdroje začne číst samo. Paměťový incident
sám vyšetří přes Core, Supervisor a běžící aplikace, uloží tabulku a po následující
automatické kontrole (nejdříve po pěti minutách) provede jedno porovnání.
U Marketplace/github_web samo doplní nativní diagnostiku, související protokol
a omezenou veřejnou síťovou sondu. **Pro tato čtení není potřeba API klíč ani
nový doplněk a uživatel nemusí spouštět diagnostické příkazy.**

AI klíč zadávej až později, pouze v privátním nastavení HADS. Výchozí malý test
má 3 požadavky za klouzavých 24 hodin a nejvýše 512 výstupních tokenů/požadavek,
bez automatické placené fronty. Rozpočet přežije restart i změnu klíče.
Cena závisí na modelu; toto není garantovaný dolarový strop.
Při 373 MiB nadále platí paměťová brána 576 MiB: HADS samo prověří prostředky,
nepředstírá spuštěný Hermes a neobchází ochranu.

[PR #13](https://github.com/OndraMa/HADS/pull/13) ·
[ARM64 + AMD64 přejímka](https://github.com/OndraMa/HADS/actions/runs/43436851932) ·
[16 desktopových/mobilních zobrazení](https://github.com/OndraMa/HADS/actions/runs/43436851956)

Na každé architektuře 223 testů, skutečný Core 2026.11.0 a původní izolovaný
Hermes se skriptovaným místním HTTPS modelem. Omezený režim skutečně zvládl dvě
čtení ve třech modelových voláních a odmítl čtvrté. Zabalená služba ukončila
SIGTERM s kódem 0 a zachovala případ po restartu. Aktualizátor byl ověřen se
skutečnými vydanými RC3 zdroji a falešným HA CLI/Supervisorem. Obě architektury
vytvořily shodný instalační soubor i zdrojový archiv; payload je byte po bytu
porovnaný s přesným Git commitem.

Testovaný zdroj: `1c5db118a861a0a89edf50dc636fc2d6657e1e60`.
SHA-256 instalátoru:
`35307113c7b26bd82b1b6c93c547ed4152eff6e94f576d68565adbe79368a593`.

Živá aktualizace/restore HAOS, původní Hermes při zátěži této domácnosti,
skutečný LLM, MA FastMCP a fyzické rádio/Zigbee stále čekají na ověření.
Kandidát se nevydává za produkčně převzatý. Podporované opravy mají nadále
samostatný neměnný plán, schválení a funkční ověření; rizikové operace bez
požadované ověřené zálohy zůstávají zablokované.
