# HADS 4.7.0-rc2 — bezpečnostní stabilizace

Kandidát navazuje na audit Work A01–A13/B01–B12 a potvrzené požadavky uživatele. Není kompletním splněním celé auditní matice. Instalace do živého HAOS nebyla provedena.

## Změny

- A01/A12: odstraněna akceptace upload ACK, textových shod a negativních/neurčitých odpovědí. Nezávislá služba musí potvrdit přesný soubor, účet, složku, velikost a SHA-256 ve smlouvě verification_version=1. Staré nastavení rescue_accept_upload_ack se ignoruje. Bez takového verifieru zůstane zápis blokovaný.
- A02: uplynutí času bez výskytů již neoznačuje pokus a plán za úspěšné. Přechází do verification_blocked. Pozitivní funkční ověřovače pro jednotlivé opravy zbývají; tuto mezeru nezakrýváme výsledkem successful. Observer vyžaduje čerstvé čtení dostupné entity před uzavřením svého případu.
- A03/A04: opakovaný OOM během téhož dne je P2; neověřený souběh healthcheck spojení není P1. Jednorázovému OOM se bez důkazů nepřipisuje zotavení. Kompletní epizodové vyhodnocení OOM a aktuální kritické dostupnosti dále zbývá.
- A07: explicitní journal level <info> má přednost před slovem timeout.
- A09/B04: stáří samo nepřesouvá automatický případ do sledování. Planner eviduje waiting_budget a počítá neuzavřenou práci v remaining. UI nezobrazuje pevná procenta jako pravděpodobnost příčiny.
- B01/B03: HTTP banner až po bindu, chyba bindu je explicitní; log má UTC čas a verzi. Samostatná předstartovní readiness služba a úplné correlation IDs zbývají.
- B02: společný výpadek Core ukončí dávku publikace nejvýše po třech pokusech místo násobení počtem senzorů; publisher má omezený exponenciální odstup.
- B05: Repairs pro disk, startup a backup mají oddělené vysvětlení; neznámý typ nepředstírá chybný odkaz.
- Hamster hledá čtecí příkaz hass/get_states namísto celé věty incidentu. Nejde o implementaci všech jeho funkcí.

## AI rozpočet

Nová volba ai_call_limits_enabled má výchozí hodnotu false podle výslovné volby uživatele. Denní limity pak neblokují výzkum; omezení kroků jednoho vyšetření, velikosti vstupu a výstupu zůstávají. Režim nezapíná sám AI, nemění klíč a nepovoluje automatické dobíjení. Nečte aktuální zůstatek OpenAI; 30 USD je údaj od uživatele, nikoli měřený finanční strop. Po zapnutí volby lze původní limity opět používat.

## Smlouva nezávislého verifieru

Odpověď služby je přímo objekt s poli verification_version=1, exists=true, filename, config_entry_id, destination_folder, size a sha256. Identita, velikost a SHA-256 vzdálených bajtů musí odpovídat konkrétnímu rescue archivu.

Služba musí číst vzdálený objekt; nesmí jen vracet metadata požadavku. HADS neimplementuje novou OneDrive službu a netvrdí, že ji nynější integrace poskytuje. Pokud existující integrace nemá odpovídající ověřování, tato verze bezpečně blokuje opravy. Hash archivu není test obnovení.

## Otevřené části — důležité před instalací

- Neimplementována bezpečná rotace/přepsání poslední OneDrive zálohy ani sdílená plná záloha celé dávky. Původní zálohy se nemažou; nový rescue má vlastní soubor.
- A05/A06/A08/A10/A11/B06–B10 nejsou kompletně vyřešeny: chybí úplný kontrakt dokončeného výzkumu, migrovaná identita epizod, všechny časové parsery, automatické nové plánování po selhání, jednotná záloha dávky a úplná taxonomie/provenance.
- Neproběhly živé HAOS/Ingress, obnovovací a produkční migrační zkoušky ani Docker build cílové architektury. Univerzální opravy databází a registrů nejsou deklarovány.
- Původní historické succeeded záznamy nejsou přeznačeny za nově ověřené. Nový stav verification_blocked nic sám neznovuspouští.

## Instalace a návrat

Neinstalovat s očekáváním, že RC2 automaticky odemkne opravy. Nejdříve zachovat nezávisle dostupnou HA zálohu a přístup mimo jediný Ingress. Instalátor provádí aktualizaci lokálního doplňku; před spuštěním zkontrolovat SHA-256. Návrat vyžaduje předchozí zdroj a konzistentní zálohu dat, nikoli smazání incidentové databáze.

Ověřené výsledky jsou v souboru verification.json u balíku. Původní test upload ACK byl opraven podle změněné bezpečnostní smlouvy, nikoli odstraněn.
