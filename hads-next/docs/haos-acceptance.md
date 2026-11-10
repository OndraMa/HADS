# Finální živá přejímka — stále ČEKÁ / NEPROVEDENO

Operátor provede na **odděleném testovacím HAOS**, nikdy automaticky v produkční
domácnosti. Zapiš verze Core/OS/Supervisor, commit kandidátu, SHA-256 instalátoru,
image digest, hardware, datum/čas Europe/Prague a UTC, operátora a vlastníka.
Nezapisuj hesla, tokeny nebo modelové klíče do protokolu.

| Pořadí | Praktický krok a očekávaný důkaz | Stav |
|---|---|---|
| 1 | Ověřit hash a vnitřní manifest, nainstalovat nový slug vedle RC3/0.2, potvrdit nezměněná původní data | ČEKÁ |
| 2 | Ingress ověří skutečného správce; cizí uživatel/CSRF/přímé spojení jsou odmítnuté | ČEKÁ |
| 3 | Přečíst Core, Supervisor, OS, registry, aplikace/info/stats/logs; zaznamenat úspěch nebo přesnou mezeru každého čtení | ČEKÁ |
| 4 | Bez modelu načíst původní Hermes, ověřit UID/chroot/seccomp/paměť a skutečný HAOS AppArmor; při chybě nezvyšovat oprávnění | ČEKÁ |
| 5 | Nastavit virtuální companion okruh podle companion/README_CS.md, povolit jen tento katalog | ČEKÁ |
| 6 | Nastavit odezvu testovacího tlačítka → cíle; stisk vytvoří skutečný funkční incident a důkazy | ČEKÁ |
| 7 | Po vlastním souhlasu spustit poskytovatele a zvlášť autonomní AI; původní Hermes získá další data a citovaný návrh | ČEKÁ – reálný LLM |
| 8 | Ověřit konkrétní před/po, revizi, riziko, snapshot a cílový plán; zamítnutí/ruční volba nic nevykoná | ČEKÁ |
| 9 | Schválit pouze virtuální CAS; čerstvé čtení potvrdí přesnou referenci, HTTP samo incident neuzavře | ČEKÁ |
| 10 | Stisk testovacího tlačítka skutečně spustí nativní automatizaci; kontext cíle a nejméně 10 s souvislého pokrytí → český funkční report | ČEKÁ |
| 11 | Nově schválený rollback obnoví jen referenci, další funkční selhání znovu otevře tentýž spis; žádná legitimní změna sama neopakuje incident | ČEKÁ |
| 12 | Přerušit pouze testovací HADS/worker v bezpečných bodech; žádná duplicitní změna, nejasný výsledek blokuje další zápisy | ČEKÁ |
| 13 | Export z kopie předchozí Next DB, idempotentní import historie, nulový přenos schválení; návrat zastavením nového slugu | ČEKÁ |
| 14 | Výpadek modelu a čtecího zdroje neztratí spisy, nevytváří falešné důkazy pokrytí a nedělá placené retry | ČEKÁ |
| 15 | RPi 4 / 2 GB: při Core/ZHA/MA změřit paměť/CPU/PSI/latenci a rezervu, 24 h pilot bez OOM a zhoršení domácnosti | ČEKÁ |

## Samostatné praktické zdroje

Rádio: zapsat čas skutečného samovolného zastavení, Core historii/kontext/Action
history a MA události/logy. Rozlišit uživatele/automatizaci, odpojení, provider,
stream, restart nebo nedostatek důkazů. Bez důkazu nevyvozovat příčinu. Po ručním
řešení sledovat nejméně 30 minut, podle původní četnosti déle. HADS jako test
nezmění hlasitost nebo přehrávání. Skutečný MA debug buffer musí být doložený.

Zigbee: operátor skutečně stiskne tlačítko a nezávisle zapíše čas. Porovnat
zha_event, zařízení, trigger, podmínky, trace, akci a fyzickou odezvu cíle.
Nezachycený fyzický stisk není prokázané selhání Zigbee. Udělat deset vědomých
pokusů a také podmínku, při které se reakce očekávat nemá. Software injekce
události v kontejneru tuto přejímku nenahrazuje.

OneDrive: nezávisle obnovit odpovídající zálohu na jednorázový odpojený HAOS,
zkontrolovat Core/config i data. Existence souboru nebo SHA-256 jednoho objektu
není důkaz obnovitelnosti celé instalace. Rizikový katalog se tímto kandidátem
neodemyká. Původní ochrany RC3 se nemění.

Reálný model: operátor nastaví oprávněný HTTPS endpoint přes privátní nastavení
prostředí/aplikace a vědomě potvrdí náklady. Předem zapiš incident bez řešení,
model/verzi a limit; zkontroluj skutečné volby nástrojů, další důkazy, citace a
neověřené hypotézy. Nepřepisovat odpovědi modelu, nepředávat hotové řešení a
nevydávat skriptovaný server za autonomní úsudek. Bez dostupného endpointu je
výsledek ČEKÁ, nikoli PASS.

Celkové přijetí vyžaduje skutečné výsledky a důkazy všech relevantních řádků.
Neprovedený řádek se nesmí odvodit z počtu unit testů. Produkční použití je
následné samostatné rozhodnutí vlastníka po živé přejímce.
