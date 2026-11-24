# Akceptační test HADS 4.5.0 na HAOS

Tento test odděluje čtecí diagnostiku od zápisové opravy. Nejprve proveďte body
1–8 bez zásahu do systému. Bod 9 vyžaduje předem zvolený bezpečný testovací plán.

1. **Verze a panel:** panel i `/health` ukazují 4.5.0, pět stránek se načte a
   konzole prohlížeče neobsahuje chybu JavaScriptu.
2. **Zdroje:** u Core, Supervisor, hostu a každého podporovaného doplňku porovnejte
   stav běhu se Supervisor UI. „Připojeno“ nesmí přepsat skutečnou chybu doplňku.
3. **Logy:** spusťte test sběru. Tabulka musí ukázat čas, řádky, nálezy a konkrétní
   chybu. Výpadek jednoho volitelného zdroje musí dát `partial`, ne úspěch.
4. **Watchman:** spusťte report a Deep Analysis. Jedna chybějící reference smí
   vytvořit jediný root-case, i když existuje TXT i strukturovaná odpověď.
5. **Spook/Entity Availability/HAGHS:** porovnejte jeden známý nález s jejich UI.
   Musí zůstat zachovaný identifikátor, typ problému a původní zdroj.
6. **Automation Inspector:** ověřte vlastníka, cestu, current/replacement a trace.
   Neznámá náhrada nesmí vytvořit vykonatelný plán.
7. **Funkční priorita:** vyšetřete poslední selhání zvolené automatizace. HADS má
   uvést trigger, poslední trace, selhavší krok, dopad a ověřovací scénář. Obecný
   restartový event-stream/PulseAudio šum nesmí tento incident vytlačit.
8. **AI (volitelné):** na jediném incidentu spusťte výzkum. Výstup musí oddělit
   fakta, hypotézy, důkazy pro/proti a chybějící důkaz. Nesmí schválit plán ani
   aktivovat tlačítko spuštění.
9. **Bezpečná testovací oprava:** zkontrolujte before/after/riziko/rollback,
   schvalte plán a ověřte aktivaci tlačítka. Po spuštění musí vzniknout plná HA
   záloha i rescue, zápis až po nich, následná kontrola a záznam výsledku v
   incidentu i persistentním oznámení. Při konfliktu „before“ musí být dávka
   zablokována bez zápisu.
10. **Restartová odolnost:** schválený, ještě nespouštěný plán musí po restartu
    HADS zůstat dohledatelný. Diagnostický závěr musí zůstat ve sledování a nesmí
    rozsvítit tlačítko oprav.

Test neprošel, pokud HADS zobrazí zdroj jako funkčně zdravý jen proto, že odpověděl
health endpoint, pokud sloučí různé příčiny, zdvojí tentýž nález, skryje výsledek
opravy nebo provede zápis bez obou záloh a explicitního spuštění.
