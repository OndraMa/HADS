# HADS 4.6.2 – opravy z živého auditu

Navazuje na 4.6.1 včetně průběžného vyšetřování, spravedlivější fronty, přesnějšího přiřazování důkazů a testu sběru protokolů. Lze přejít přímo z 4.6.0.

## Nové změny

- Host journal zachytí NETDEV WATCHDOG, timeouty, I/O chyby a zabití procesu při nedostatku paměti i bez explicitního ERROR. Zachová čas a zdroj; explicitní INFO nepovyšuje automaticky na chybu.
- Síťový timeout, cloudová kvóta, odmítnuté čištění statistik a Meross HTTP JSON chyba mají konkrétní české vysvětlení, diagnostický postup a kritéria ověření. Nejde o automatický důkaz hardwarové vady ani o automaticky schválenou opravu.
- Zigbee frame od zigpy/ZNP už není klasifikován jako snímek kamery. Neznámý producent rámce vede k přiznané nejistotě.
- Odpojený klient nevyvolá opakovaný zápis chybové odpovědi do mrtvého spojení. Jiné výjimky zůstávají viditelné.
- Watchman TXT fallback ignoruje běžné názvy souborů, slučuje opakovaný identifikátor a jeho identita se nemění při posunu řádku. Strukturované nálezy nadále uchovávají vlastníka.
- Panel rozlišuje převzetí dat od nového skenu poskytovatele. Počet vykonatelných plánů označuje jako evidenci včetně samostatných plánů, nikoli počet připravených incidentů.

## Bezpečnost a omezení

Povinná záloha ani schválení se neobcházejí. Instalátor nejprve požaduje plnou HA zálohu včetně databáze a kontroluje její metadata. Nejde o provedený test obnovy. Při selhání zálohy instalaci zastaví.

Živý audit doložil chybu kvóty OneDrive. Před instalací ověřte dostupné místo a použitelnou zálohu; samotné připojení OneDrive není zárukou obnovy. Balíček automaticky neuvolňuje prostor a nemaže historii.

Toto vydání NEPROKAZUJE úplné využití všech schopností Hamsteru/HAGHS/HADocs, neřeší všechny hypotézy auditu a není zárukou automatické opravy libovolného incidentu. Sjednocení identity mezi všemi formáty poskytovatelů a kompletní měření čerstvosti skenu zůstávají dalším úkolem. Staré případy ani jejich rozhodnutí se hromadně nemažou.

Živá instalace, prohlížeč nové verze a obnova zálohy nebyly při sestavení testovány. Výsledky skutečně provedených lokálních testů jsou v přiloženém verification.json.

## Instalace

Nahrajte HADS4_install_4.6.2.sh do /share a v HAOS terminálu s příkazem ha spusťte:

```sh
bash /share/HADS4_install_4.6.2.sh
```

Při chybě zálohy nepřeskakujte kontrolu. Po dokončení obnovte panel a ověřte zobrazenou verzi 4.6.2. Placený AI výzkum se sám nezapíná. Průběžná analýza může zvýšit dobu rychlé kontroly.

## Akceptace po instalaci

1. Zkontrolovat verzi, zachování nastavení, incidentů a schválení.
2. Spustit test sběru a vyčkat na výsledek konkrétního běhu.
3. Ověřit spojení konektorů; vypnutý HA-MCP nesmí být prezentován jako funkční.
4. Porovnat Watchman report a nálezy; automations.yaml nesmí být vydáván za entitu.
5. Zkontrolovat síťový timeout a Meross případy, jejich důkazy a časy. Starý případ nemusí být automaticky přejmenován.
6. Obnovit/zavřít panel a ověřit, že nepřibývá kaskáda BrokenPipe.
7. Zápisový test provést až na konkrétním schváleném bezpečném plánu s ověřenou zálohou; zkontrolovat výsledek a následné sledování. V tomto vydání nebyl živě proveden.
