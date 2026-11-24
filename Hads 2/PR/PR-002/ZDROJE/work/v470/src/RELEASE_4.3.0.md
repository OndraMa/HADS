# HADS 4.3.0 — opravy s dohledatelným souhlasem

## Stav vydání

Lokálně testovaný instalační balík. Není nasazen na vašem HAOS a není zárukou
bezchybnosti všech integrací. Číslo verze je 4.3.0; add-on zůstává označený
`experimental`, dokud neproběhne ověření s aktuálními verzemi vašich doplňků.
Toto vydání nahrazuje workflow RC5, nikoli všechny dosud nepodporované zásahy.

## Instalace

1. Uložte `HADS4_install_4.3.0.sh` do `/share/` v Home Assistantu.
2. Spusťte v terminálu HAOS `bash /share/HADS4_install_4.3.0.sh`.
   Instalátor vyžaduje `ha`, Python 3, Bash, tar a sha256sum. Nejdříve vytvoří
   novou plnou HA zálohu a nezávisle ověří její metadata. Bez ní se zastaví.
3. Zdroj předchozí verze zůstane v `/share/hads4_installer_backups/`.
   Databáze HADS v `/data` se nemaže. Starší HADS 2/3 nejsou upraveny.
4. Obnovte panel (Ctrl+F5), ověřte 4.3.0 a spusťte hlubokou analýzu.
5. Schválení z předchozího vydání se jednorázově vrací k potvrzení, protože
   se změnily podmínky zálohy. Další běžné restarty již souhlas neruší.

Při přerušené opravě HADS zamkne zápis a označí plán jako přerušený. Nespouští
jej znovu. Zkontrolujte manifest, plnou zálohu a skutečný stav před novým plánem.
Installer backup ověřuje dostupnost, rozsah a metadata; neprovádí test obnovy.

Pokud rebuild/start selže, neopakujte opravy naslepo. Původní zdroj zůstává
v uvedené záložní složce a plná HA záloha u Supervisoru. Zkontrolujte log a
skutečně běžící verzi. Případný návrat zdroje/rebuild nebo obnova HA je ruční
zásah; instalátor jej sám neprovede.

## Co je nové

- Oddělené stránky Přehled, Incidenty, Opravy a zálohy, Diagnostické zdroje, Historie.
- Detail incidentu: Souhrn, Důkazy, Konverzace, Oprava, Historie rozhodnutí.
- Závěr přijatý ke sledování není oprava. Přijatá/zamítnutá/ignorovaná rozhodnutí
  již nepřepisuje další běh plánovače bez výslovného znovuotevření.
- Ignorování se vztahuje na konkrétní root-case, nic nemaže a nezvyšuje zdravotní
  skóre. Platí do ručního znovuotevření; nemá automatickou dobu expirace.
- Konverzace přežije restart. „Nesouhlasím — znovu vyšetřit“ odvolá staré schválení.
  Strukturovaná volba nového odkazu umožňuje předat přesnou službu telefonu;
  plánovač musí ověřit její existenci a původní konfiguraci před vytvořením návrhu.
- Aktualizační entita ani katalog služeb nedokazují funkčnost doplňku.
  Běh procesu, odpověď diagnostického rozhraní a nalezené problémy jsou oddělené.
- Spook, Watchman, Automation Inspector, HADocs, HA-MCP, Hamster, HAGHS a Entity
  Availability zůstávají zdroji s různými schopnostmi. Codex Terminal Pro bez
  funkčního diagnostického rozhraní není prohlašován za zdravý. Digest není zahrnut.
- GET retry pro přechodné výpadky, ale strict fresh read jako výchozí režim.
  Cache nesmí potvrdit zápis, zálohu, čerstvý sběr logů ani funkčnost konektoru.
- Samostatná historie plánů a výsledků, včetně identifikátoru předzásahové zálohy.

## Bezpečná opravná dávka

Náhled → přesný souhlas → tlačítko Spustit → konflikty → rescue ZIP + potvrzení
uploadu → nová plná HA záloha → nezávislé čtení metadat → lokální kopie → nový
test aktuálnosti → zápis → zpětné čtení/config check → následné sledování.

Záloha je povinná bez ohledu na staré volby `backup_before_repairs` a
`allow_repair_without_backup`. Kontroluje se ID, jedinečný název, full typ,
nenulová velikost, zahrnutí HA databáze a dotčených doplňků. Jde o kontrolu
metadat u Supervisoru, nikoli automatický test obnovení kompletního systému.
Plné zálohy mohou trvat dlouho a potřebují dostatek místa. HADS je nemaže.

Rescue v OneDrive zůstává samostatná brána. Starší nastavení
`rescue_accept_upload_ack=true` dovoluje potvrzení úspěšného uploadu integrací;
není to nezávislá kontrola vzdáleného obsahu. Požadujete-li i tu, nastavte false
a dostupnou ověřovací službu. Chybějící ověření v tomto režimu dávku zastaví.

Rollback se nepoužije přes novější cizí změnu. Ruční rollback nejprve vytvoří
novou plnou zálohu. Restart nelze vzít zpět. HADS nikdy automaticky neobnovuje
celý systém kvůli jedné neúspěšné akci.

## Podporovaný rozsah zápisů

| Oblast | Vykonatelný postup |
|---|---|
| Existující YAML/YML v `/config` | Přesná jedinečná náhrada s kontrolním hashem, bez secrets.yaml a symlinků |
| Automatizace a skripty | Přesná změna kanonického JSON přes HA API, kontrola před/po |
| Doplňky | Změna voleb s validací nebo explicitní restart |
| Core | Kontrola konfigurace; explicitní restart jen při povolení v nastavení |
| Historie Recorderu | Samostatný plán `recorder_purge`, zachování 1–3650 dnů, bez repack/apply_filter |

Libovolný shell, mazání adresářů, přepis `.storage`, libovolné SQL, opravy
poškozených neznámých DB a zásahy do externí MariaDB/PostgreSQL nejsou automaticky
podporované. Zůstávají k ručnímu zásahu. Schválení diagnózy jim neudělí oprávnění.
Nečinná entita se sama nemaže; existence a závislosti musí být ověřené.

## Údržba databáze

Výchozí stav je vypnutý. Pouze pokud používáte lokální SQLite Recorder a
ověřili jste skutečnou aktivní cestu, nastavte například:

```yaml
recorder_maintenance_enabled: true
recorder_sqlite_path: home-assistant_v2.db
```

Nepovolujte při externí DB ani pokud jde o zbytek staré neaktivní databáze.
V Opravy a zálohy rozbalte údržbu historie, zvolte počet zachovaných dnů a
připravte plán. Náhled vysvětluje odstranění starší historie. Plán se schvaluje
a spouští stejně jako ostatní opravy; v dávce musí být sám.

Před službou Recorderu vznikne plná HA záloha a navíc konzistentní kopie SQLite
přes backup API (včetně transakcí dostupných ve WAL), `PRAGMA quick_check` a SHA-256.
Kopie je v `/data/repair_private/plan_NNNNNN/recorder-before.db`.
Nedostatek místa, časový limit, neznámé schéma nebo chyba konzistence zastaví zásah.
HADS NEkopíruje zpátky živou DB. Obnova je ruční při odstávce. Přijetí požadavku
`recorder.purge` není důkaz dokončení údržby; stav zůstává k ověření, protože
Recorder úlohu zpracovává asynchronně. Není automaticky měřeno, kolik řádků ubylo.

## Konverzace a AI

Bez klíče funguje místní rádce, uložené zprávy a deterministické kontroly —
nikoli plnohodnotný jazykový model. Pro AI zapněte `openai_enabled` a nastavte
klíč přímo v konfiguraci doplňku, ne v chatu. Model se nepřepíná automaticky.
Místní testy používají pouze simulované odpovědi; žádný placený API test neproběhl.

- `ai_background_research: false`: automatické placené zkoumání zvlášť vypnuté.
- `ai_daily_call_limit: 20`: maximum API požadavků za klouzavých 24 h.
- `ai_case_daily_call_limit: 6`: limit požadavků na zdrojový případ za 24 h.
- `ai_max_output_tokens: 4000`: strop výstupu včetně uvažování na požadavek.
- Nejvýše 3 kola, 64 kB odesílaného kontextu na požadavek a zkrácené výstupy nástrojů.
- U incidentu jsou skutečně nahlášené vstupní/výstupní tokeny, uvažování,
  webová volání a počet požadavků s neznámou spotřebou. Selhání spotřebuje slot.
- Toto není pevný dolarový rozpočet. Web může přidat vstupní tokeny a náklady.
  Nastavte také limity projektu u poskytovatele API.

AI výstup, web a doplňky jsou návrhy/důkazy, nikdy souhlas se zápisem.
Není delegováno na obecného HA konverzačního agenta s možností spouštět služby.
Staré volby `advisor_use_ha_conversation`/`advisor_agent_id` se pro chat nepoužijí.

## Co ověřit na vašem HAOS

1. Spook: aktuální Repairs. Hamster/HA-MCP: handshake a read-only výstup.
2. Automation Inspector/HADocs: konkrétní živý nález a doporučení, ne jen health API.
3. Jeden známý neplatný odkaz: správný vlastník, změna před/po, souhlas, fronta.
4. Rescue a plná HA záloha: ID a čas odpovídají aktuálnímu plánu.
5. Po opravě skutečná funkce automatizace a následná analýza bez regrese.
6. DB údržbu až po samostatném ověření aktivní SQLite cesty a obnovitelnosti záloh.

## Použitá oficiální dokumentace

- [Supervisor API](https://developers.home-assistant.io/docs/api/supervisor/endpoints/)
- [Obsah a metadata záloh](https://developers.home-assistant.io/docs/api/supervisor/models/)
- [Recorder](https://www.home-assistant.io/integrations/recorder/)
- [OpenAI Docs: limity výstupu a usage](https://developers.openai.com/api/docs/guides/reasoning/)
