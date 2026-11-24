# HADS 4.7.0-rc1 — diagnostická analýza a převod návrhů do oprav

Datum: 10. září 2026. Výchozí zdroj: lokální 4.6.3. Nový adresář: `work/v470/src`.

## Stav vydání

Jde o kandidáta k instalaci a živé akceptaci, nikoli o prohlášení, že HADS umí bezpečně opravit celý HAOS. Neproběhla instalace na uživatelův HAOS, Docker build cílové architektury, placené API volání ani test skutečné obnovy zálohy. Prohlížeč nebyl použit.

Naměřené výsledky jsou v souboru `HADS4_4.7.0-rc1-verification.json` vedle instalátoru. Ten je autoritativní pro počet provedených testů a SHA-256. Každý nově sestavený balík obsahuje stejný zdroj jako přiložený ZIP.

## Co bylo skutečně změněno

1. **Automation Inspector:** importuje i pole `entities` ve schema v2. Právě tam poskytovatel ukládá chybějící entity a služby. Dřívější HADS četl kompatibilitu a trace, ale tyto závislosti ztrácel. Zachovává také `restored`, dostupnost a původ konfigurace a hash. Vypnutá automatizace není automaticky stejně naléhavá jako rozbitá aktivní.
2. **AI → opravný plán:** plánovač čte strukturované `analysis`, nikoli regulární výraz nad převedeným textem. Model může vrátit přesné `configuration_changes`. Kompilátor načte aktuální konfiguraci, ověří vlastníka incidentu, cestu a původní hodnotu a předá výsledek běžnému preview a schvalování. Nepřekládá obecnou radu do libovolného shellu/SQL.
3. **Rozpočet AI:** nejvýše osm kroků podle nastavení a zbývajícího denního rozpočtu. Poslední krok je vyhrazen závěru. Pro `store:false` se přenáší šifrovaný reasoning kontext. Limity plateb se nemění. Souběžně vyčerpaný rozpočet stále bezpečně zastaví další volání.
4. **Přehlednost:** Souhrn a Oprava ukazují poslední analýzu, funkční dopad, další test, počet kandidátních/přesných/vykonatelných změn a blokující důvody. Chyba nového vyšetření nesmaže předchozí analýzu a UI ji označí jako historickou.
5. **Sémantika zdrojů:** Watchman nález z archivu/ESPHome nebo nejasné role podmínky dostane potřebu ověření, ne jistotu aktivní závady. Historické/recovered/non-essential skupiny Entity Availability se nepovažují za aktivní poruchu. Potomci rozpoznaných root-cases HADocs zůstávají důkazy místo dalších incidentů.
6. **Bezpečnost:** Hamster používá přesný seznam povolených čtení. Nástroj není bezpečný jen proto, že neobsahuje slovo „delete“. Opravné akce nejsou přebírány přímo z nedůvěryhodného provider payloadu. Zálohy, schválení, kontrola aktuálnosti a následné sledování zůstávají povinné.
7. **Srozumitelné diagnózy:** přidány konkrétní interpretace nesouladu SQLite indexu, osiřelých statistik, neúspěšného Inspector refresh, uzavřeného Ingress streamu a chybějící backup složky.

## Co nový kompilátor podporuje

Pouze náhrady existujících JSON skalárů v načtených automatizacích a skriptech, nejvýše 12 změn v jednom návrhu. Cesta je přesný JSON Pointer; stará hodnota musí včetně typu souhlasit. Identita ani kořenový objekt se nepřepisují. Seznamy a celé bloky se tímto mechanismem nemažou ani nenahrazují. Změna mimo vlastníka doloženého v incidentu je odmítnuta. Obnovený placeholder není načtená konfigurace.

Takto lze připravit například přesnou změnu akce/služby, entity v existujícím cíli nebo konkrétního parametru. Shoda staré hodnoty ověřuje aktuálnost návrhu, **nikoli správnost jeho logiky**. Kapitán musí posoudit diff a dopad. Engine dále kontroluje stav před zápisem a zpětné čtení; funkční úspěch vyžaduje následné ověření.

Existující samostatné podporované opravy souborů, voleb doplňků a omezená údržba historie zůstávají. Tento update nepřidává univerzální AI editaci `.storage`, mazání libovolných `.db` ani neomezené příkazy. Žádný HADS plán se nespustí pouze na základě výstupu jazykového modelu.

## Instalace

Použij přiložený `HADS4_install_4.7.0-rc1.sh` v HAOS terminálu s příkazem `ha`. Nejdříve si ponech vlastní nezávisle dostupnou zálohu a obnovovací údaje. Instalátor vytváří a ověřuje metadata nové plné zálohy včetně Recorder databáze, zachovává původní zdroj doplňku a provádí rebuild `local_hads4`. Nemění nastavený API klíč. Neslibuje automatické zotavení po každé chybě rebuild/instalace; starý zdroj a HA záloha slouží k návratu.

Například po přenosu souboru do adresáře dostupného terminálu spusť `bash HADS4_install_4.7.0-rc1.sh` z tohoto adresáře. Nevypínej kvůli tomu Core přes svůj jediný Ingress přístup. Po instalaci ověř verzi i log a obnov panel. Nepovažuj pouhé „started“ za úspěch všech funkcí.

## Povinná akceptace na HAOS

- Inspector: porovnat jeden skutečný chybějící odkaz s `entities` v API a odpovídajícím incidentem HADS; zachovat vlastníka a zdroj.
- Spook: porovnat Repairs seznam včetně osiřelých statistik, nikoli pouze počet či dostupnost integrace.
- Watchman: čerstvé parsování, identifikace souboru/role; archivní ESPHome a `condition: light.is_on` nesmějí být vydávány za potvrzené chybějící HA entity.
- HADocs: jeden root s několika dětmi nesmí být několik samostatných kořenových příčin. Nepotvrzený formát nové verze se musí uvést jako mezera pokrytí.
- Entity Availability/HAGHS: porovnat konkrétní entity, čas a skupiny; neměnná hodnota ani vysoké skóre nejsou důkaz funkčnosti celé domácnosti.
- OpenAI: na jednom incidentu zkontrolovat dokončenou analýzu, skutečnou spotřebu, dopad, důkazy pro/proti a blokery. Platný klíč bez dokončeného API výsledku nestačí.
- Oprava: neškodný přesný kandidát → náhled → schválení → fronta → povinný backup/rescue → zápis → zpětné čtení → výsledná zpráva → funkční test. Ověřit i restart HADS mezi schválením a spuštěním.
- Selhání: nedostupná záloha, změněný soubor nebo nejasný výsledek zápisu musí zastavit další změny. Nezkoušet tento test na produkční databázi. Závěr přijatý ke sledování nesmí aktivovat tlačítko oprav.
- Logy: Core, Supervisor, host a každý vybraný doplněk musí mít úspěch/neúspěch, čas a skutečný obsah. Jednorázová chyba při restartu nesmí plošně potlačit jinou trvající poruchu.

## Zbývající práce

Nejsou kompletně realizované autonomní opravné strategie pro osiřelé registry/statistiky, Lovelace, libovolné poruchy DB, všechny nástroje MCP ani libovolný doplněk. Neexistuje důkaz odstranění všech duplikací napříč všemi zdroji. Automatická úvaha po každém selhaném zápisu a bezpečné vytvoření následného plánu vyžaduje další stavový tok; opakování zápisů naslepo zůstává zakázáno. Případné zvýšení rozpočtu AI je samostatná uživatelská volba.
