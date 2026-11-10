# Kontrolní seznam finálního dodání

Výchozí vzdálená i lokální revize ověřena 10. 11. 2026:
`5f06e67c20d5016e334d1b838fe2d188d860aee7`, PR 6. Nová větev
`codex/hads-next-final-delivery`. RC3, main, staré distribuce se nemění.

| Oblast | Výchozí skutečný stav | Implementační kontrola |
|---|---|---|
| Hermes, broker, role, výzkum | Integrované a nativně testované, model skriptovaný | zachovat kontrakty a zopakovat testy |
| Automatická detekce | Chybí provozní kontinuální scheduler a monitorovací pravidla | perzistentní pravidla, odběr, debouncing, mezery, automatické frontování jen s opt-in |
| Opravný engine a approval | Funkční izolovaná laboratoř, bez provozního propojení | reuse původní authority/intent/verifier, úzký CAS mechanismus |
| Native automation config CAS | Core API nemá atomické podmíněné uložení | obecný zápis zůstává zablokován; vlastní CAS reference pro izolovanou testovací automatizaci |
| UI | Částečně neformátované stránky, statické sekce | jednotné responzivní rozhraní, skutečné řádky případů/rozhodnutí/reportů |
| Historie | SQLite, export, retence, bez importu | neautorizující idempotentní import incidentů/evidence |
| První spuštění | ověřený správce a dílčí kontroly | funkční stavy jednotlivých bran včetně oprav/záloh |
| Distribuce | 0.2 se zachovává | nová identita a kandidát až po dostupných integračních branách |
| Skutečný LLM / HAOS / hardware | nedostupné; žádné credentials | připravit přejímku, nikdy nepřeznačovat testy na live |
