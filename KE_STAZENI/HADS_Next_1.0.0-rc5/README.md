# HADS Next 1.0.0-rc5 — instalační kandidát

RC5 přidává **Doplňky a ověření**, automatické nativní čtení dostupných údajů
a soukromý přenos vybraného nastavení původního Hermes RC3. HASK je vynechaný.
**Plné funkční propojení všech doplňků ani obecné zápisy Spook/HA-MCP ještě
nejsou hotové.** Nativní přítomnost nebo stav procesu se za jejich ověření nevydávají.

[Instalační soubor](HADS_Next_install_1.0.0-rc5.sh) ·
[Kompletní ZIP](HADS_Next_1.0.0-rc5-komplet.zip) ·
[Český návod](HADS_Next_1.0.0-rc5-navod-CS.md) ·
[Výsledky a omezení](VYSLEDKY_A_OMEZENI_CS.md) ·
[Živá přejímka](AKCEPTACE_HAOS_CS.md) · [Integrace](INTEGRATIONS_CS.md)

V přihlášeném GitHubu použij **Download raw file**. Ulož `.sh` do `/config`
a při aktuálním běžícím Next RC4 proveď úvodní aktualizaci:

```sh
bash /config/HADS_Next_install_1.0.0-rc5.sh --upgrade-rc4
```

**RC4 předem nezastavuj ani neodinstalovávej.** Supervisor aktualizuje jen
HADS Next s nativní částečnou zálohou. Skript ověřuje přesné vydané RC4 zdroje,
zachovává soukromá data a identitu. Při chybě zachovej hlášku a marker, nic nemaž
a nespouštěj instalátory souběžně. Název aplikace je nyní stálý
**HADS Next – diagnostika**; číslo verze je uvedené zvlášť.

Po aktualizaci otevři HADS a stránku **Doplňky a ověření**. Nativní kontrola běží
automaticky bez AI klíče a bez diagnostických příkazů uživatele. Rozlišuje
aktuální komponentu/aplikaci, stav procesu, přečtené entity a neověřenou vlastní
diagnostiku. Skóre HAGHS může přečíst z uvedené entity; tím neprokazuje identitu
ani verzi jeho balíčku. U HADocs se neověřená vazba na HADS nezaměňuje za
tvrzení, že samotný HADocs nefunguje.

Tlačítko **Načíst návrh připojení z původního Hermes RC3** volitelně převezme
jen známé připojovací položky přes pevný Supervisor GET z ověřené aplikace/verze.
Původní aplikaci není potřeba spouštět. Výsledek je **soukromý neaktivní návrh**,
nikoli aktivované připojení. Staré souhlasy, AI klíče/náklady a oprávnění se
nepřenášejí. Tokeny se nezobrazují a nepatří do chatu ani GitHubu.

Prošlo 249 izolovaných testů na každé nativní architektuře ARM64/AMD64,
skutečný Core a původní izolovaný Hermes se skriptovaným HTTPS modelem,
18 zobrazení prohlížeče, restart se zachováním dat a přesný instalační skript
se skutečnými RC4 zdroji a falešným HA CLI/Supervisorem. SIGTERM skončil kódem 0.
Obě architektury vytvořily stejné instalační bytes. Všech 57 souborů payloadu
je porovnáno s přesným Git commitem. Kompletní ZIP byl vytvořen dvakrát shodně.

[PR #16](https://github.com/OndraMa/HADS/pull/16) ·
[Nativní přejímka](https://github.com/OndraMa/HADS/actions/runs/43540465092) ·
[Prohlížeč](https://github.com/OndraMa/HADS/actions/runs/43539064833)

Testovaná zdrojová revize: `84bb795b522c60d26b2b67e7e07fb9b0fc12bcce`.
SHA-256 instalátoru: `a1f88f5e7389f9deb06374f0f707bf1a727c1d9a0e14edbdb2151ca60624260a`.
SHA-256 kompletního ZIPu: `755e9a848e40fb4d72cd8f4ec3b86842f4f3d44e1d2a4b80e934de0ed1f322cd`.

AI je výchozí vypnutá. Malý volitelný test má 3 požadavky / klouzavých 24 h
a nejvýše 512 výstupních tokenů/požadavek, bez automatické placené fronty.
To není dolarový strop. Paměťová brána 576 MiB a zálohové požadavky zůstávají.
Podporované opravy nadále vyžadují konkrétní souhlas a funkční ověření.

Živá aktualizace a obnova HAOS, skutečné funkční API externích doplňků,
RPi při domácí zátěži, reálný LLM a fyzické rádio/Zigbee/světla čekají na
přejímku. Toto vydání není produkčně ověřený ani dokončený celý původní systém.
