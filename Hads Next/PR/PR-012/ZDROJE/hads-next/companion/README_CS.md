# Bezpečný alternativní katalog vlastní testovací reference

Core config API nemá compare-and-swap. HADS proto žádným endpointem nepřepisuje
obecnou automatizaci. Tato volitelná custom integrace drží **jedinou vlastní
referenci** použitou v nativní testovací automatizaci. Zápis kontroluje revizi i
původní hodnotu v jednom zámku, trvale ukládá idempotency tombstones a přijímá jen
přechod mezi dvěma pevnými virtuálními input_boolean identifikátory. Žádná metoda
nepřijme URL, cestu, službu, YAML, libovolný cíl nebo příkaz shellu.

Na odděleném testovacím HAOS, jehož operátor má obnovovací cestu:

1. Zkopíruj adresář `custom_components/hads_reference` do odpovídajícího
   `custom_components` v konfiguraci testovacího HA. Zachovej ostatní komponenty.
2. Ručně sluč příslušné sekce `test-automation.yaml` do testovací konfigurace.
   Záznam automatizace vlož do již používaného seznamu automatizací. Nepřepisuj
   celé existující soubory a nevytvářej duplicitní sekce `automation`.
3. Nezapojuj tuto automatizaci, helpery ani senzor do fyzického zařízení nebo
   jiné automatizace. Jde o virtuální testovací okruh, nikoli produkční opravu.
4. Proveď standardní kontrolu konfigurace HA a vlastní vědomý restart testovacího
   Core. HADS tyto operace nespouští a konfiguraci domácnosti nemá připojenou.
5. V HADS → Opravy ověř companion a potvrď omezený katalog. Nefunkční API
   nesmí zpřístupnit schválení.
6. V Monitorech nastav odezvu: cíl `input_boolean.hads_next_test_target`, očekáváno
   `on`, spouštěč `input_button.hads_next_test_run`, automatizace
   `automation.hads_next_reference_test`, prodleva např. 5 sekund.
7. Stiskni testovací tlačítko v HA. S chybnou referencí zůstane virtuální cíl
   vypnutý a HADS založí spis. Spusť vyšetřování (nebo samostatně povol autonomní
   AI a její případné náklady). Zkontroluj důkazy a připrav přesný plán.
8. Schval konkrétní plán. Pak stiskni **pouze testovací tlačítko**. HADS očekává
   skutečné spuštění, stejný kontext změny cíle a 10 sekund souvislého pokrytí.
   HTTP úspěch ani změna reference incident samy neuzavřou.
9. Rollback je nový plán s novým schválením a čerstvou revizí. Obnovuje pouze
   referenci; záměrně chybný původní cíl funkci neobnoví. Report to musí přiznat.

Záloha jednotlivé reference není záloha HAOS ani OneDrive. Rizikové operace,
obecné změny automatizací a jejich zálohové brány jsou nadále zablokované.
Nativní Core admin může vlastní testovací prostředí spravovat mimo HADS; toto
není záruka proti jinému správci HA. AI nemá jeho token ani síťový přístup.

Živá HAOS přejímka čeká. Nativní kontejnerový test používá stejnou integraci,
Skutečný Core event bus, HTTP/WebSocket, controller, approval a verifier.
