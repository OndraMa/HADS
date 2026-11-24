# Aktuální kandidát 4.7.0-rc2

Aktuální změny a otevřené bezpečnostní/provozní brány: [RELEASE_4.7.0-rc2.md](RELEASE_4.7.0-rc2.md). Upload ACK nestačí. Bez pozitivního funkčního testu není oprava potvrzena. Níže zachovaný starší obsah nesmí rozšiřovat tuto smlouvu.

# HADS 4.7.0-rc1

Aktuální rozsah, audit a omezení: [vydání 4.7.0-rc1](RELEASE_4.7.0-rc1.md).
Starší průvodce níže zachovávají historii; nejsou potvrzením kompletní funkčnosti.

Diagnostické a rozhodovací centrum pro Home Assistant OS. Spojuje logy,
živé registry a dostupné diagnostické konektory. Připravuje návrhy a vyžaduje
samostatné schválení i spuštění konkrétní opravné dávky.

**Toto je lokálně testované experimentální vydání, ne potvrzení funkčnosti
na konkrétním HAOS.** Podrobná instalace, rozsah změn, nastavení chatu, databáze
a omezení jsou v [průvodci vydáním](RELEASE_4.6.2.md).

Porovnání s požadavky projektu HA, opravené chyby a dosud nehotové oblasti:
[audit 4.6.0](AUDIT_HA_4.6.0.md). Akceptace: [4.6.2](RELEASE_4.6.2.md#akceptace-po-instalaci).

- Pět přehledných stránek a oddělené karty detailu incidentu.
- Trvalá konverzace, ignorování, znovuvyšetření a přesná volba náhrady odkazu.
- Samostatné diagnostické závěry a skutečné schválené opravy.
- Povinná plná HA záloha a rescue před zápisem, kontrola konfliktů a hashů.
- Opt-in údržba lokální SQLite historie s konzistentním snapshotem.
- Živé diagnostické odpovědi oddělené od pouhé instalace/běhu doplňku.
- Spook, Hamster, Watchman, Inspector a další adaptéry zůstávají zahrnuté;
  jejich dostupnost je podmíněná skutečným rozhraním. Digest není zahrnutý.
- Devět omezených WebMCP Site Tools zpřístupňuje stav a diagnostiku pro řízený
  webový test. Schválení, spuštění oprav, rollback, restart ani shell nevystavují.
- Aktivní diagnostika přes WebMCP vyžaduje viditelné potvrzení v HADS a každý běh
  se zapisuje do auditní tabulky. Čtecí nástroje nevracejí celé surové logy.

HADS bez OpenAI klíče provádí lokální diagnostiku, ne plnohodnotný AI chat.
AI ani reporty nemají oprávnění spouštět neodsouhlasené opravy. Nečinné entity
se automaticky nemažou a libovolný shell či SQL nejsou podporované.

[Ověření](VERIFICATION_MATRIX.md) · [Bezpečnost](SECURITY.md) · [Změny](CHANGELOG.md)

Starší DOCS/ARCHITECTURE zachovávají historii návrhu. V případě rozdílu platí
průvodce 4.6.2 a audit, aktuální zdroj a naměřené testy, nikoli původní přísliby.
