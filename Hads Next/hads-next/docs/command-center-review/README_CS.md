# Oprava přehledu RC2 podle prvního uživatelského ověření

Datum: 13. 11. 2026. Základ: doručený RC2, commit
`0097c74e6333c2b5c86e4dba098ee61e0f128d67`. Změny jsou v samostatné větvi
`codex/hads-next-command-center`. Vydaný instalátor a archivy RC2 se nepřepisují.
Tato úprava zatím není nasazená do uživatelova HAOS a nepředstavuje nové vydání.

## Co doložil uživatel

Text z jeho instalace uvádí Core 2026.11.1, 836–837 načtených entit a devět
úspěšných nativních čtení včetně Supervisora, OS, registrů, Repairs a System Health.
Hermes probe neproběhl, poskytovatel AI není nastavený. Paměťový vzorek 583 MiB
byl jen 7 MiB nad požadovanou rezervou; pozdější nález dokládá pokles pod bránu.
Z tohoto nálezu nelze určit přesnou tehdejší dostupnou paměť ani příčinu spotřeby.

Dva aplikační nálezy obsahují pouze Supervisor stav `error`: starší HADS
2.0.0-rc3 a Studio Code Server 7.2.0. Nejsou důkazem pádu RC2. Uživatel doplnil,
že se takový stav objevuje i po záměrném zastavení a aplikace lze poté spustit.
To je důvod neopovažovat samotný stav za funkční poruchu, nikoli nezávislý důkaz
chyby HAOS. Logy ani společná příčina nejsou ověřené.

Jde o uživatelem vložená data. V této relaci nemáme přímou autentizovanou
kontrolu HAOS. Nejsou sem kopírované ingress adresy, identifikátory soukromých
spisů ani jiné údaje domácnosti.

## Co se mění

- Přehled má jednu navigaci, čtyři souhrnné ukazatele, oddělené čekající kroky,
  skutečné výsledky, opakované případy a srozumitelný stav AI. Technické informace
  a méně časté formuláře jsou v detailech. Všechny údaje pocházejí ze stávajícího
  snapshotu; vykreslení samo nevolá HA API ani model.
- Aplikační spisy mají v přehledu i detailu konkrétní název z přečteného seznamu
  aplikací. Opraví se i zobrazení historických obecných titulků bez přepsání důkazů.
- Historické auto-nálezy `health:app:*` bez opravného plánu jsou označené jako
  stavové údaje k ověření. Nejsou počítané do funkčních problémů. Zůstávají uložené
  a otevřené, nejsou automaticky uzavřené ani smazané. Uživatelem nahlášený problém
  aplikace se tím neschová; schvalovaný plán a ověřené výsledky zůstávají viditelné.
- Samotný automaticky zaznamenaný stav aplikace nezahajuje placené AI vyšetřování
  ani při zapnuté autonomii. Detekce doloženého očekávaného chování, například
  neočekávaně vypnuté vybrané automatizace, nadále využívá původní souhlas a limity.
- Paměťová brána se nesnižuje. Průvodce uvádí i aktuální odstup od 576 MiB a
  upozorňuje, že překročení hranice samo nezaručuje připravenost při zátěži.
  Paměťový incident je označen jako historicky zachycený, nikoli jako důkaz
  současné nedostupnosti nebo příčina chyb jiných aplikací.
- Opravné operace, identity, CSRF, schvalování, snapshoty a rollback se nemění.

## Ověření a náhled

[Snímek desktopu](dashboard-desktop.png) · [Snímek mobilu](dashboard-mobile.png)

Snímky pocházejí z anonymní fixture ve skutečném Chromium. Nejsou to snímky
uživatelova HAOS. Detail dvou stavových nálezů je pro náhled otevřený; běžně je
sbalený. Fixture zahrnuje devět přečtených zdrojů, paměťový nález, dvě aplikace
s nerozlišitelným starým titulkem, vypnutou AI a archivovaný bezpečnostní test
HTML escapování. Nevolá se model ani domácnost.

Reprodukce: `python scripts/check.py` a `python scripts/practical_browser.py`.
Nový workflow `hads-next-command-center.yml` ověřuje offline regrese a Chromium
na desktopu i mobilu. Prohlížečový protokol obsahuje hashe přesných zdrojů.
Tato UI kontrola není nová ARM64/HAOS přejímka ani důkaz úsudku skutečného LLM.

## Proč není ovládán uživatelův boční prohlížeč

Ve spravovaném prostředí
`ccarenv_b64_Y2NhcmVudl9kNDlkNDllYzUxMjQ4MTkxOGJlZWQ1ODE4Y2M5ZWIyYg`
je desktop deklarovaný jako enabled, stav unknown, ale nástroje `cua_repl.js`
a `open_in_codex` nejsou nabídnuté. Otevřený boční prohlížeč uživatele proto není
zde ovladatelný. Předchozí omezený proxy požadavek skončil HTTP 503 a prostředí
nemá nakonfigurovanou Tailscale VPN. Samotná tato skutečnost nedokazuje chybu HADS.
Žádná tajemství se nevyžadují v chatu a žádná produkční aplikace se nerestartuje.

Lokální ověření: 179 regresních testů, bez selhání; Chromium deset pohledů
(1280 a 390 px), bez horizontálního přetečení a nečitelné navigace. Ověřené je
escapování názvů, relativní odkazy pro ingress, odlišení historických aplikací,
zachování původních důkazů, nulové automatické modelové volání ze stavové
observace a nezměněná aktivace specialisty u doložené očekávané automatizace.
Nativní HAOS, fyzická zařízení ani nový balíček zde testované nejsou.
