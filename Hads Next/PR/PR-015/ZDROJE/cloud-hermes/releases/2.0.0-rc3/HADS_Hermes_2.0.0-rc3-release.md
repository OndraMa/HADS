# HADS Hermes 2.0.0-rc3 — konkrétní důkazy od doplňků

- Nové čtecí nástroje koordinátora Hermes pro jeden výslovně vybraný diagnostický zdroj a uložené výsledky specialistů. Podporované zdroje zahrnují Spook, Watchman, HADocs, Automation Inspector, Entity Availability, HAGHS, HA-MCP a Hamster MCP.
- Postupné nativní čtení zařízení/systému, logů v časovém okně incidentu a případných traces. Každý krok ukládá stav, chybu, výsledek a shodu se staršími důkazy. Nedokončený krok se po restartu označí přerušený.
- Detail incidentu → Důkazy zobrazuje kroky včetně neúplných a selhaných čtení. Dokončení čtení neprohlašuje vyřešení problému.
- Volitelný Music Assistant FastMCP konektor pro dva přesně povolené diagnostické příkazy. Nové URL/token v nastavení, žádné ovládání přehrávání, reload ani editace konfigurace.
- Hamster volí vhodnější podporovanou čtecí cestu podle Repairs, zařízení nebo integrace; neznámé parametry se nedohadují.
- Zachovány strukturované reporty Watchmanu s TXT fallbackem, Repairs Spooku, schvalovací fronta, povinná ověřená záloha před opravami a izolace skutečného Hermes bez závislosti na Landlock.

Toto je kandidát RC3. Ověření na živém HAOS, skutečných konektorech a OneDrive se nesmí zaměňovat za offline či kontejnerové testy. Výsledky provedených testů jsou v doprovodném verification JSON. RC2 cloudový test nedokazuje funkčnost RC3.

Návod: MANUAL_2.0.0-rc3_CS.md. Instalátor na žádost nevytváří novou předinstalační HA/OneDrive zálohu. Runtime ochrany před skutečnými opravami jsou zachovány.
