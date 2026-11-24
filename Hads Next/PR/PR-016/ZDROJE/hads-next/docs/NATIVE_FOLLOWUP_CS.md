# Následná korekce nativního vyšetřování po živém výpisu RC4

Výpis vlastníka z 14. listopadu 2026 potvrzuje devět přečtených zdrojů,
automatické statistiky paměti a veřejnou sondu Marketplace. Neprokazuje
opravu Marketplace ani spuštěný Hermes. Při uvedených 537 MiB chybí do
požadované rezervy 576 MiB dalších 39 MiB; ochrana se nemění. Pro základní
čtení není potřeba AI poskytovatel. Další příkazy po uživateli nevyžadujeme.

Audit zjistil dvě konkrétní mezery RC4:

- Nativní System Health a System Log se pravidelně čtou i pro hassio a cloud,
  přehled však bez modelového jobu stále zobrazoval „Čeká na vyšetření“.
- Automatický nález Repairs zobrazoval obecný text a byl počítaný jako
  funkční porucha bez doloženého dopadu.

Změna vytváří trvalý report každého existujícího nativního nálezu, konkrétní
doménu a identifikátor požadavku Repairs. Rozlišuje stále přítomný nález,
aktuální kontrolu bez nálezu a nedostupné či neúplné čtení. Úspěšné čtení
neuzavře incident jako funkčně opravený. Změna reportu zůstane v historii,
stejné opakované čtení aktualizuje pouze čas poslední kontroly a nezvětšuje
počet důkazů ani výskytů. Report je dostupný v přehledu, detailu a čtecím
nástroji Hermesu. Související logy se cíleně přiřazují také nálezům Repairs;
ukládají se jen logger, čas, úroveň a podporované typy výjimek, nikoli
libovolný text, URL nebo tokeny. Čtení i korelace zůstávají omezené počtem.

Ověření: 228 izolovaných testů včetně čtyř nových regresí. Report a vstupní
SHA-256 jsou v `docs/evidence/native-followup/offline-tests.json`.
Prohlížeč má samostatný protokol. Žádné placené volání modelu ani přístup
do domácnosti nebyly použity. ARM64/AMD64 kontejnery a živá přejímka této
následné změny zatím neproběhly.

Tato větev obsahuje zdrojovou korekci, nikoli nový instalátor. Vydaný RC4 tag,
instalátor a archivy jsou neměnné; instalace RC4 tyto nové změny neobsahuje.
Bez reálného obsahu konkrétního nálezu nelze odvodit jeho příčinu ani slíbit
opravný plán. Obecné zápisy zůstávají zakázané, podporované opravy vyžadují
samostatný konkrétní souhlas. AI je nadále volitelná a má stávající limity.
