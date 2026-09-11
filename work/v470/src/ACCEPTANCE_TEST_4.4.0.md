# Akceptační test HADS 4.4.0 po instalaci do HAOS

Tento test se provede až po potvrzení uživatele, že je 4.4.0 nainstalovaná. Testující
smí číst stav a po jednotlivém potvrzení spouštět diagnostiku. Nesmí schválit či
spustit opravu, restart, rollback, mazání, databázovou údržbu ani měnit nastavení.

## Předpoklady

- Home Assistant a HADS jsou dostupné přes skutečný Ingress.
- Panel ukazuje verzi 4.4.0 a uživatel je přihlášen jako správce.
- Je zaznamenán browser, verze HA Core, Supervisor a HADS.
- Před testem se uloží stav opravné fronty; žádné její položky se nemění.

## Kontrolní tok

1. Otevřít panel, zkontrolovat konzoli a načtení všech pěti stránek na desktopu.
2. Zapsat stav WebMCP. `9/9` je očekávání podporovaného browseru; nepodpora se musí
   projevit pravdivě a nesmí poškodit běžné UI.
3. Porovnat souhrn v UI s `hads_get_command_center`: skóre, počty fronty, schválené
   plány, write gate a stav poslední dávky.
4. Na každé stránce fronty porovnat viditelné karty s
   `hads_get_acceptance_snapshot`. Každý rozdíl ID, názvu či stavu je chyba.
5. Vybrat nejvýše tři reprezentativní incidenty a porovnat detail, příčinu,
   doporučení, počet důkazů a případný opravný plán.
6. Ověřit zdroje logů: Core, Supervisor, host a jednotlivé add-ony. Porovnat čas,
   řádky, počet nálezů, poslední úspěch a chybu s odpovídajícím HADS stavem.
7. Po viditelném potvrzení spustit rychlou diagnostiku, sledovat auditní run do
   dokončení a ověřit, že se aktualizoval backend i UI bez vzniku falešné opravy.
8. Po samostatném potvrzení spustit kontrolu konfigurace. Výsledek musí rozlišit
   platnou konfiguraci, skutečně neplatnou konfiguraci a nedostupný endpoint.
9. Hluboký audit spustit jen po dalším výslovném potvrzení. Ověřit Spook, Hamster,
   Watchman, Automation Inspector a další dostupné konektory podle živých odpovědí,
   ne podle pouhé instalace nebo běhu add-onu.
10. Obnovit stránku, zopakovat snapshot a ověřit perzistenci výsledku a absence
    neočekávaného spuštění schválených oprav.
11. Ověřit mobilní rozložení, detail incidentu, dialog potvrzení a spodní repair bar.
12. Zapsat všechny chyby konzole, HTTP 4xx/5xx, nesoulady a časy. Výsledek označit
    PASS jen tehdy, když UI × WebMCP × HADS SQLite × dostupná HA diagnostika souhlasí.

## Kritéria neúspěchu

- HADS ukáže konektor jako funkční bez aktuálně ověřeného spojení;
- incident nebo stav v UI nesouhlasí s kanonickým backendem;
- diagnostika proběhne bez viditelného potvrzení;
- WebMCP zpřístupní schválení, spuštění, restart, rollback, shell nebo surové logy;
- jediný výpadek 502 smaže poslední platná data nebo vytvoří trvalý falešný incident;
- test změní konfiguraci, databázi historie nebo stav opravné dávky.

Výstup testu bude obsahovat datum, prostředí, PASS/FAIL každého kroku, snímky,
porovnané hodnoty a přesný seznam nálezů. Samotné `9/9` neznamená, že HADS funguje
správně; je to pouze potvrzení registrace nástrojů.

