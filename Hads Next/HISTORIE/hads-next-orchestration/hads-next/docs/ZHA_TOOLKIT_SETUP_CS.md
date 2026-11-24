# Co povolit pro ZHA Toolkit v HADS RC7

Pro automatickou diagnostiku **není potřeba povolit obecné opravy nebo přidávat Toolkit jako další MCP server**.
HADS používá stávající nativní připojení k HA a jednu pevně omezenou službu Toolkitu.
Není potřeba AI klíč, nový model ani další běžící AI aplikace.

## Pokud je Toolkit už aktivní

Aktualizuj HADS z vydané RC6 na vydanou RC7 podle instalačního návodu. Toolkit ani Core kvůli samotnému
čtení nerestartuj. HADS při své pravidelné kontrole sám ověří načtenou komponentu a konkrétní odpověď.
Na **Doplňky a ověření → ZHA Toolkit** ukáže výsledek, počet přečtených zařízení a verzi uvedenou v odpovědi,
pokud ji Toolkit poskytuje. „Komponenta načtená“ není totéž jako úspěšné čtení.

## Pokud byl pouze stažený přes HACS

Ověřený upstream [mdeweerd/zha-toolkit](https://github.com/mdeweerd/zha-toolkit/tree/79205820d52bd4797c7dacf6b1184380ba7ca613)
v README vyžaduje i aktivaci v `configuration.yaml`:

```yaml
zha_toolkit:
```

Pokud tento klíč už existuje, nepřidávej ho podruhé. ZHA musí být již nastavené a funkční; tento Toolkit
není určený pro Zigbee2MQTT nebo deCONZ. Po skutečném doplnění konfigurace ji nejprve ověř podporovanou
kontrolou HA a teprve potom použij restart Home Assistantu v jeho UI. Je to jednorázové nastavení integrace,
nikoli diagnostický příkaz nebo doporučená oprava senzoru. Jiná verze/fork může mít jiný instalační postup.

HADS žádný tento zápis ani restart sám neprovádí. Pokud je komponenta načtená a konkrétní služba nefunguje,
další restarty bez důkazů nejsou řešení; HADS oznámí omezení a použije dostupné nativní ZHA čtení.

## Co přesně se čte

- Pouze existující seznam zařízení v cache, s identitou potřebnou pro vazbu na registr, dostupností,
  poslední komunikací a dostupnými LQI/RSSI údaji.
- Pevná služba `zha_toolkit.zha_devices`, `return_response: true`, pevný seznam polí.
- Žádné vlastní `command`, soubory CSV/JSON, vlastní eventy, RF skeny, reporting writes, reconfigure,
  binding, permit join, kanál, firmware nebo odstranění zařízení.

HADS při výsledku `success: false`, chybách nebo nesprávném schématu nezobrazí nulu jako úspěch.
Starší interní API Toolkitu nemusí být kompatibilní s konkrétním Core; tato hranice zůstává viditelná.
Kontejnerové testy HADS nejsou živá přejímka této instalace Toolkitu.

## Kdy je co schvalovat

Pro samotné čtení není potřeba nový souhlas s opravou. Ve spisu RC7 zobrazí stav konkrétní entity,
co sám přečetl a proč má nebo nemá návrh ke schválení. Bez příčiny, potvrzeného cíle a podporované
opravné operace **není co schválit**. Zapnutí všech nástrojů HA-MCP ani Toolkitu nedoplní chybějící bezpečný vykonavatel.

Zapisovací Zigbee/registry operace nejsou v tomto katalogu hotové. Nesmějí se obejít obecným service call,
MCP nebo shellem. Zejména zakázaná entita a chybějící podobně pojmenovaný odkaz nejsou autorizací k zapnutí či přejmenování.
Pro fyzický výsledek může být nakonec potřeba jednoduchý uživatelský test; není potřeba terminálové vyšetřování.
