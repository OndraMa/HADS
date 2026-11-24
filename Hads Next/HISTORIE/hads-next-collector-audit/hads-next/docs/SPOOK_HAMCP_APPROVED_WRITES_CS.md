# Spook a HA-MCP jako vykonavatelé schválených oprav

## Stav auditu 14. listopadu 2026

Vlastník požaduje automatické vyšetřování a konkrétní zápisy Spook/HA-MCP
teprve po schválení jednotlivého plánu. To rozšiřuje požadovaný katalog,
nepředstavuje souhlas se změnou v běžící domácnosti. V tomto auditu se nic
v domácnosti neměnilo ani nevolal model. Přístupové URL z chatu nejsou
součástí dokumentace, testů ani repozitáře.

RC4 používá Spook prostřednictvím nálezů Repairs. Schvalovaný vykonavatel
Spook a obecné HA-MCP zápisy zatím nejsou implementované. Tato dokumentace
je ověřený kontrakt a návrh zapojení, nikoli tvrzení o hotové implementaci.
Nový instalační kandidát tímto dokumentem nevzniká.

Pokus MCP `initialize` na poskytnuté veřejné HTTPS adrese vrátil HTTP 503.
`tools/list` ani `tools/call` proto nebyly provedeny. Odpověď nepotvrzuje
příčinu, dostupnost lokálního serveru ani nastavení OAuth. Lokální adresy
nejsou tímto výsledkem ověřené. Diagnostické příkazy uživatel nepotřebuje;
ověření z místního HADS vyžaduje jeho budoucí konfigurační adaptér.

Snímky uvádějí server HA-MCP 9.2.0, zapnuté beta funkce/YAML a vypnuté
potvrzování YAML změn. Jde o údaj uživatelského rozhraní; není to nezávisle
ověřená verze implementace. Změny v UI podle banneru čekají na restart
serveru. Aktuálně běžící konfiguraci nelze odvodit jen z poloh přepínačů.

## Ověřené upstream kontrakty

Spook: `3092fa14eccc2c3289ac906fbdbaaf385a1d22da`.
HA-MCP: `c8df42eb763ef803a8af837f06ef738dcee4fa76`.
Tyto zdroje nejsou důkazem shody s instalací vlastníka.

| Schopnost | Ověřený zdroj a význam | Hranice schváleného provedení |
| --- | --- | --- |
| Spook `homeassistant.rename_entity` | `custom_components/spook/ectoplasms/homeassistant/services/rename_entity.py`; mění registry `name`, nikoli entity_id | Jedna explicitní entita; přečtená původní hodnota a přesný nový název. Nelze zaměnit za opravu referencí entity_id. |
| Spook `homeassistant.set_entity_icon` | Sousední `set_entity_icon.py`; entita/seznam entit, icon včetně null | První kandidát pro vratný test metadata registru. HADS má povolit jediný cíl, zálohu hodnoty a samostatně schválený návrat. |
| Spook `recorder.import_statistics` | `ectoplasms/recorder/services/import_statistics.py`; metadata, jednotky a časové řádky | Volá Recorder import; návrat služby nedokazuje dokončení importu ani obnovitelnost. Produkční operace zůstane blokovaná bez nezávislé zálohy, kontroly dotčených řádků a návratové strategie. |
| HA-MCP `ha_set_entity` | `src/ha_mcp/tools/tools_entities.py`, `entity_update_fields.py`, `helpers.py`; více nepovinných polí a také hromadné cíle | HADS smí připravit jen podporované pole a jednu entitu. Ostatní parametry se odmítnou, nikoli předají z modelu. `icon=""` maže vlastní ikonu; null má jinou vstupní sémantiku než Spook. |
| HA-MCP historie statistik | `docs/tools/statistics.md`; `ha_get_history(source="statistics")` a metadata Recorderu | Uchovat rozdíl uložené a zobrazované jednotky; aktuální atribut entity nenahrazuje metadata historické statistiky. |

Spook tyto služby registruje jako administrátorské přes
`async_register_admin_service` v `custom_components/spook/services.py`.
Nedostupnost služby nebo nedostatečné oprávnění se musí zobrazit jako mezera,
nikoli obcházet jinou cestou nebo širším tokenem.

HA-MCP `docs/registry-label-concurrency.md` výslovně uvádí, že lokální zámky
nekoordinují jiné procesy, UI ani integrace a HA neposkytuje podmíněný zápis
štítků. Nové čtení a následný zápis se nesmějí vydávat za atomický CAS.
Po nejasné síťové odpovědi nelze automaticky opakovat zápis.

## Požadované zapojení do HADS

1. Privátní nastavení adresy a autentizace vlastníkem, bez publikování URL.
   Ověřit TLS, MCP initialize, stránkovaný tools/list a přesná schémata.
   Samotné annotations/readOnlyHint nejsou bezpečnostní autorita.
2. Diagnostický broker zpřístupní pouze předem ověřená čtení. Připojovací
   údaje ani obecný tools/call nejsou dostupné Hermesu.
3. Nezávislý plánovač sestaví jedinou podporovanou změnu. Plán určí
   instalaci/server, transport, nástroj či službu, otisk schématu, cíl,
   původní a navrženou hodnotu, důkazy, riziko, zálohu a ověření.
4. Vlastník schvaluje neměnný otisk konkrétního plánu přes autentizované
   rozhraní HADS. Uložené nastavení serveru ani souhlas s AI nejsou schválení.
   Změna schématu, serveru, cíle nebo parametrů vyžaduje nový plán a souhlas.
5. Vykonavatel použije existující trvalé schválení, expiraci, záznam záměru
   před zápisem a ochranu proti opakování po restartu. Změna cíle před akcí
   zápis blokuje. Nemá možnost přepnout na alternativní transport bez souhlasu.
6. Výsledek přečte nezávislé nativní API. HTTP 200 nebo odpověď MCP neuzavře
   funkční incident. Úprava ikony ověřuje jen ikonu, ne funkci domácnosti.
   Rollback musí být podporovaný pro danou operaci a samostatně schválený.

Existující požadavky na obnovitelnou HAOS/OneDrive zálohu se neobcházejí.
Mazání registrů, zařízení, historie a obecné importy nejsou automaticky
povolené tím, že je server nabízí. Nepodporovanou opravu HADS musí vysvětlit.

## Nastavení serveru pro první zapojení

- Pro práci s registrem není nutná beta úprava YAML, filesystem ani sandbox.
  Úzký začátek nepovoluje neomezený shell nebo libovolný Python.
- Pokud vlastník YAML beta režim potřebuje i pro jiné klienty, zapnout
  požadavek potvrzení změn. Toto potvrzení stále nenahrazuje schválení HADS.
- Ověřování TLS ponechat zapnuté. Redakci tajemství zapnout a logování
  kompletních HTTP těl/debug ponechat vypnuté.
- Nevypínat globálně zápisy, mají-li být dostupné schválené operace; místo
  toho omezit katalog a samostatně vynucovat souhlas v HADS.
- Serverové přepínače a OAuth callbacky klientů nezajišťují schvalování HADS.
  Přímí klienti serveru nejsou pod kontrolou vykonávacího modulu HADS.

## Co ještě musí být dokončeno

Privátní HA-MCP konfigurace HADS, lokální živé ověření katalogu, implementace
konkrétního adaptéru a UI pro plán, negativní testy všech cest a restartů,
nativní ARM64/AMD64 přejímka a explicitně schválený vratný živý test.
Zápisy statistik navíc potřebují ověřenou obnovu dotčených dat. Žádný z těchto
bodů se tímto auditem neoznačuje jako dokončený.
