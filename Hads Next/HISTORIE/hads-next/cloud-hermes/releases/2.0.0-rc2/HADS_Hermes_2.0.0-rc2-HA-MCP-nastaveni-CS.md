# HA-MCP a HADS 5.1.0-rc3 — jednoduchý průvodce

## Co to je

Home Assistant obsahuje data, HADS spravuje vyšetřování, AI pomáhá uvažovat a HA-MCP nabízí nástroje pro přístup k těmto datům. HA-MCP není model, nepotřebuje samo OpenAI kredit a připojení neznamená provedenou opravu.

Příklad: automatizace nezhasla světlo. HADS si může načíst stav, historii kolem události a poslední uložené stopy automatizace. Zjištění porovná s logy. Stav `on` neprokazuje fyzicky svítící lampičku. Neexistující starší stopu nelze zpětně vytvořit. Spook, Watchman, Automation Inspector, HADocs, HAGHS a Entity Availability zůstávají samostatné diagnostické zdroje; MCP jejich výsledky nenahrazuje.

## 1. Zjistěte variantu — neinstalujte druhou kopii

**A: samostatný doplněk / aplikace.** Je v Nastavení → Aplikace (starší HA: Doplňky). Otevřete Home Assistant MCP Server, jeho konfiguraci a protokol.

**B: integrace v Core.** Je v Nastavení → Zařízení a služby → HA-MCP Custom Component. Serverová položka se jmenuje HA-MCP Server. Pouhá pomocná položka File & YAML Tools není MCP server. Pokud server skutečně chybí, aktuální verze autora jej přidává přes Přidat integraci → HA-MCP Custom Component → HA-MCP Server. Starší instalaci nelze automaticky považovat za kompatibilní.

## 2. Zpřístupněte pouze diagnostické čtení

V **HA-MCP**, nikoli v HADS, nastavte, pokud to vaše verze nabízí:

```yaml
read_only_mode: true
enable_tool_search: false
redact_secrets: true
```

Změňte příslušné volby, nenahrazujte celou existující konfiguraci těmito třemi řádky. Maskování tajemství je dodatečná ochrana, nikoli záruka odstranění všech citlivých informací.

V Tools povolte dostupné čtecí nástroje:

- `ha_search` — související entity.
- `ha_get_state` — aktuální stav.
- `ha_get_entity` — registr entity.
- `ha_get_history` — historie.
- `ha_get_automation_traces` — uložené průběhy automatizace.
- `ha_get_system_health` — systémová diagnostika.

Pokud Tool Search necháte zapnutý, tyto nástroje připněte (Pin), aby byly přímo v `tools/list`. HADS RC3 nepoužívá obecný dispatcher HA-MCP. Režim Full catalog u konverzačního agenta HA je jiná volba než HTTP MCP katalog pro HADS.

Změna Read Only Mode / Tool Search u doplňku podle autora vyžaduje restart **tohoto doplňku**, ne Core. U serveru v Core mohou změny vyvolat reload serverové položky. Postupujte podle vlastní verze a v HADS obnovte spojení. Čtecí režim MCP neblokuje oddělený schválený vykonavatel HADS s jeho vlastní write gate.

## 3. Zkopírujte skutečnou Connect URL

**A:** protokol doplňku obsahuje `MCP Server URL`. Běžný tvar je `http://HOST:9583/private_TAJNA_CESTA`. Pro interní hostname použijte skutečný hostname z informací aplikace. Port ani cestu neodhadujte.

**B:** Nastavení → Zařízení a služby → HA-MCP Custom Component → **HA-MCP Server → Konfigurovat**. URL je v admin-only konfiguraci nebo HA logu. Může být lokální webhook `http://HA-HOST:8123/api/webhook/mcp_TAJNY_IDENTIFIKATOR`; současná serverová verze nabízí i přímou adresu s výchozím portem 9584. **Zkopírujte nabídnutou URL, nevyrábějte ji z příkladu.**

Adresa panelu `/api/hassio_ingress/...` není MCP endpoint. Connect URL s tajnou cestou je přihlašovací údaj: neposílejte ji na screenshotu ani do GitHubu. Nevystavujte port do internetu. Pro místní HADS není potřeba Cloudflare ani veřejný webhook.

## 4. Vyplňte HADS

Nastavení → Aplikace → HADS → Konfigurace:

- **Přímá MCP adresa HA-MCP / `ha_mcp_url`:** skutečná Connect URL dostupná z HADS.
- **Token HA-MCP / `ha_mcp_token`:** u tajné cesty obvykle prázdný; postupujte podle autentizace vlastního endpointu. Nepatří sem OpenAI API klíč.

Uložte a restartujte HADS, pokud jej HA po změně vyžaduje. HADS RC3 nemá interaktivní OAuth průvodce. Prázdná adresa umožňuje automatické hledání, ale úspěch není zaručený.

## 5. Ověření skutečného použití

1. Diagnostické zdroje → **Ověřit všechna spojení**.
2. U HA-MCP ověřte rozhraní a nenulový počet podporovaných čtecích nástrojů. RC3 ukazuje „co dělat dál“ a chybějící nástroje. Úplný katalog není test všech funkcí.
3. Spusťte existující vyšetřování známého incidentu nebo hlubokou analýzu. Pokud je práce odložená kvůli RAM, jiné úloze či nastavení, zkontrolujte důvod. MCP neobchází plánovač.
4. Zkontrolujte **Poslední cílené čtení**, počty úspěšných čtení/chyb a důkazy incidentu. Katalog bez cíleného čtení neobsahuje historii případu.
5. U hlášky bez entity RC3 může číst prvního kandidáta z vyhledávání; jeho souvislost s incidentem ještě není potvrzená. Výsledek pro jinou entitu není správná diagnóza.

Test spojení a MCP čtení nevyžadují placené OpenAI. Vyšetřovací úlohy však mohou podle uložených voleb volat AI. Pro první kontrolu ponechte `ai_paid_calls_enabled`, `ai_paid_web_enabled` a `ai_background_research` vypnuté. Instalátor uložené volby zachovává, sám je nepřepíná. Klíče nevkládejte do incidentů.

## 6. Řešení potíží

| Stav | Co dál |
|---|---|
| Chybí adresa | Zkopírujte Connect URL serveru. Instalace pomocné komponenty nestačí. |
| Spojení selhalo | Ověřte běh, dosažitelnost z HAOS a přihlášení. Poslední chyba rozliší DNS, timeout či odmítnutí. |
| Katalog bez čtecích nástrojů | Vypněte skrytí nebo je připněte. Nepovolujte zápisy. |
| Katalog OK, cílené čtení žádné | Ověřte stav vyšetřování; katalog není analýza incidentu. |
| Chybí parametr / schéma | HADS jej nesmí vymyslet. Potřebujeme verzi poskytovatele a redigovaný popis chyby. |
| Ověření zastaralo | Obnovte spojení; stará odpověď neprokazuje aktuální dostupnost. |

## Zdroje a hranice

- [HA-MCP doplněk](https://github.com/homeassistant-ai/ha-mcp/blob/master/homeassistant-addon/DOCS.md)
- [HA-MCP server v Core](https://github.com/homeassistant-ai/ha-mcp/blob/master/docs/in-process-server.md)
- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching): podle OpenAI Docs doplněna explicitní cache GPT-6.1 Sol bez přepnutí modelu. Cache hit ani skutečné úspory nejsou bez měření zaručené.

RC3 vznikla s offline testy, bez nasazení na vašem HAOS, placeného API testu a systémové opravy. Povinné ověřené zálohy před opravami zůstávají. Dosavadní uživatelem požadovaný instalátor je bez nové předinstalační HA/OneDrive zálohy; místní kopie zdrojů ji nenahrazuje.
