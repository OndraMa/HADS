# Bezpečnost HADS 4.5.0

HADS má silnou Supervisor roli a zapisovatelný mount konfigurace. Write gate je
aplikační pojistka, nikoli oddělení oprávnění na úrovni OS. Chyba nebo kompromitace
doplňku může tato oprávnění zneužít; add-on nevystavujte veřejnému internetu.

## Opravy

- Pouze allowlist YAML náhrady, API konfigurace automatizací/skriptů, addon options,
  restart a explicitně povolená údržba SQLite Recorderu. Žádný libovolný shell/SQL.
- Diagnostický závěr není oprava. Náhled a souhlas se vztahují na konkrétní plán.
- Vykonání vyžaduje samostatný příkaz, schválený plán, nekonfliktní dávku, rescue
  a novou plnou zálohu. Staré volby umožňující vynechat backup nemají účinek.
- Metadata zálohy se čtou nezávislým čerstvým GET: slug/název/full/HA/DB/velikost
  a dotčené addony. Není to kryptografické ověření archivu ani test obnovy.
- Rescue OneDrive s `rescue_accept_upload_ack=true` přijímá potvrzení uploadu;
  nezávislé vzdálené ověření vyžaduje false a nakonfigurovanou ověřovací službu.
- Před zápisem se znovu kontroluje očekávaný obsah. Změnil-li se, nic se nepřepisuje.
- Rollback nepřepíše novější cizí změnu. Celý HA ani živou DB automaticky neobnovuje.
- Po timeoutu mutace není bezpečné automatické opakování. Stav zůstává k ručnímu
  ověření. Restart HADS nikdy automaticky neopakuje rozpracovanou dávku.

## Data a AI

- Logy, web, MCP, externí reporty i chat jsou neověřené podklady, nikoli souhlas.
- API klíče patří do nastavení. Redakce je best effort, nikoli záruka odstranění
  všech soukromých údajů. Před zapnutím AI zvažte předávání diagnostiky poskytovateli.
- Chat nepoužívá obecného HA agenta schopného spouštět služby. MCP nástroje se
  filtrují na čtecí schopnosti, ale i metadata třetí strany mohou být chybná.
- Limity API jsou perzistentní; neznámá spotřeba po timeoutu spotřebuje slot.
  Rozpočet v měně ani cenový strop tyto limity nezaručují.
- Snapshoty v `/data/repair_private` obsahují citlivou konfiguraci a případně
  kompletní historii. Na Linuxu jsou privátní; zálohy chraňte jako původní systém.

## WebMCP Site Tools

- WebMCP je doplňkové rozhraní stránky, ne náhrada lidského ovládání ani bezpečnostní
  brány backendu. Diagnostické texty se vždy považují za nedůvěryhodná data.
- Devět zveřejněných nástrojů nemá oprávnění schválit nebo spustit opravu, rollback,
  restart či shell. Náhled plánu nezahrnuje akce s hodnotami před/po ani potvrzovací fráze.
- Aktivní diagnostiky vyžadují viditelný dialog HADS a přesný backendový marker; běh
  se auditně uloží. Marker není samostatná autentizace a nenahrazuje ochranu Ingressu.
- Odpovědi jsou omezené délkou a počtem položek, důkazy redigované a surové logy se
  WebMCP nástrojem nevydávají. Prompt injection v logu nesmí být vykonána jako pokyn.
- Pokud prohlížeč nebo nadřazený HA iframe WebMCP nepovolí, běžné UI HADS zůstává
  funkční a stav jasně ukáže „nepodporováno“ nebo částečnou registraci.

Při problému vypněte repairs_enabled, zastavte HADS, zkontrolujte repair_audit,
manifesty a Supervisor. Při kompromitaci obměňte dotčené tokeny.
