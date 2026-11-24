# HADS 4.6.3 – lokální diagnostika při vyčerpaném AI rozpočtu

Živě reprodukováno v 4.6.2 dne 10. září: cyklus 25 případů / 25 selhání / 0 plánů. Detail R-220 uvádí dosažený místní limit AI požadavků za 24 hodin.

Příčina v kódu: výjimka z lokálního omezení spotřeby propadla do obecného selhání celého plánovače. Záznam případu byl nahrazen chybou namísto zachování výsledku místního vyšetření.

Změna: samostatný typ výjimky rozpočtu, pokračování s místními důkazy a výsledkem deterministického plánovače, samostatný počet odložených AI analýz v panelu. Jiné chyby se netají. Limit se nezvyšuje, žádný nový model ani placená služba se nezapíná. Neprovede se žádná oprava bez schválení.

Toto není řešení všech zbývajících problémů HADS. R-220 navíc odkazuje na esphome/archive; před opravou je nutné ověřit, zda jde o aktivní HA konfiguraci, ne archiv nebo odlišný jazyk ESPHome. Existující závěry se hromadně nemažou ani neschvalují.

Instalátor zachovává povinnou plnou zálohu a její kontrolu. Po instalaci 4.6.3 je nutné zopakovat živý cyklus při vyčerpaném limitu: lokální zpracování má pokračovat, AI odložené má být oddělené od skutečných selhání, rozhodnutí a důkazy mají přetrvat reload. Produkční schválení opravy není testovací tlačítko.

Živá reprodukce starého problému je ověřená. Živá oprava nové sestavy a obnova zálohy dosud ověřené nejsou. Výsledek automatických testů je v verification.json. Kompletní změny předchozího vydání zůstávají v RELEASE_4.6.2.md.
