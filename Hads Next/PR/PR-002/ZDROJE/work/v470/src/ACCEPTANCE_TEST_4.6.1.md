# Akceptace HADS 4.6.1 na konkrétním HAOS

Zatím NEPROVEDENO. Oddělit lokální testy od živého výsledku.

## Čtecí část

1. Ověřit verzi 4.6.1 v panelu/API diagnostickém snapshotu. /health vrací pouze ok, nikoli verzi.
2. U všech zdrojů porovnat skutečný inventář/běh a čas úspěšné odpovědi s HA. Spook s nulou Repairs zůstane rozpoznaný; smazaný Codex Terminal se neprokáže zbylou update entitou.
3. Spustit sběr logů: Core, Supervisor, host, systémové a add-on logy. Výsledek konkrétního testu musí být complete/partial/failed. Restart HADS během čekání znamená neověřený výsledek, nikoli úspěch.
4. Nechat proběhnout periodický scan. Zkontrolovat čas a čísla plánovače v panelu. Pro dvě různé známé závady stejného doplňku nesmí detail obsahovat cizí nález.
5. Z Automation Inspectoru vybrat skutečný známý nález. Porovnat owner, source_ref, path/current/replacement a původní hlášku. Automaticky sledovaný případ se má dostat k vyšetření.
6. U selhané automatizace zkontrolovat interní ID a čas trace proti HA UI. Souborový fallback musí být označen jako historický. Prázdný seznam není úspěšný běh.
7. Porovnat jeden Watchman, Spook, HADocs, HAGHS a Entity Availability nález se zdrojem. Ověřit Hamster/HA-MCP případový dotaz, nejen handshake. Nezaměnit aktuální hygienu konfigurace za provozní výpadek.
8. Přijmout diagnostický závěr → sledování. Restartovat HADS → přijetí zachováno. Znovuvyšetřit → staré přijetí nesmí blokovat novou práci.
9. Meross: ověřit konkrétní HTTP/MQTT diagnostiku a skutečný funkční dopad. Samotný log neuzavírá diagnózu. Fyzický ovládací test provést jen s vědomím uživatele.

## Samostatně schvalovaná zápisová část

10. Zvolit bezpečný testovací objekt. Opravný plán má přesný před/po a cíl. Změna cíle po náhledu musí zablokovat neaktuální plán.
11. Schválit → plán ve Schválených a tlačítko připravené. Přijetí pouhého závěru tlačítko neaktivuje.
12. Spustit pouze po novém potvrzení. Ověřit novou HA zálohu, rescue odpovídající této dávce a příslušnou vzdálenou kontrolu; chyba zálohy nesmí dovolovat zápis.
13. Ověřit výsledný soubor/objekt, zprávu incidentu a oznámení HA. Ověřování nesmí tvrdit vyřešeno z neúplných logů.
14. Obnovu testovat pouze v bezpečném testovacím prostředí. Zapsat ID zálohy, výsledek a čas obnovy.

Ke každému bodu uložit skutečné důkazy a stav passed/failed/not_run. Nepředvyplňovat úspěch.

