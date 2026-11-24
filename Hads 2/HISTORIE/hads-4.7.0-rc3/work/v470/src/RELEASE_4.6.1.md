# HADS 4.6.1 – audit a průběžné vyšetřování

Opravné experimentální vydání nad 4.6.0. Nenahrazuje živou akceptaci na HAOS.

- Automatické vyšetřování i v rychlé kontrole; dostupné nálezy se načítají průběžně.
- Automatické sledování neblokuje první vyšetření. Přijaté závěry a ignorování zůstávají chráněné.
- Spravedlivější fronta s 30min odstupem a stavem posledního cyklu v panelu.
- Důkazy se nepřiřazují pouze podle názvu poskytovatele.
- Přesná cesta a stará hodnota pro selector opravy automatizací.
- Aktuální traces přes HA API; interní ID automatizace se nehádá, uložený fallback je historický.
- Načtený Spook je zjistitelný i bez Repairs. Update entita nedokazuje instalaci Codex Terminal Pro.
- Test sběru čeká na vlastní dokončený běh, ne první obnovenou řádku.
- Build ověřuje skutečně spuštěné testy; nepoužívá předem napsané počty úspěchů.

## Nastavení a upgrade

Použij přiložený instalátor HADS4_install_4.6.1.sh stejným dosavadním postupem pro lokální doplněk. Před instalací měj vlastní aktuální HA zálohu; v tomto úkolu nebyla instalace ani obnova provedena. Zachování existujících dat řeší původní instalační mechanismus; živá migrace je součást akceptace.

Nová volba periodic_investigation je výchozí true. Respektuje automatic_repair_planner a automatic_planner_limit. Při větší frontě může rychlá kontrola trvat déle. Placené ai_background_research se samo nezapíná.

Začni pouze čtecími body ACCEPTANCE_TEST_4.6.1.md. Zápisový test vyžaduje vybraný bezpečný cíl a tvoje samostatné schválení. Ani více CPU/RAM nezaručí úplnou interpretaci libovolné chyby; meze a zbývající práce jsou výslovně popsané v AUDIT_HA_4.6.0.md.

Konečný počet a výsledek lokálních testů je v HADS4_4.6.1-verification.json. Výsledky živého HAOS, Ingressu a restore testu jsou neověřené.

