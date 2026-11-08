# M0: audit původu a architektury RC3

Audit proveden 2026-11-08, rozsah **offline kontrola repozitáře a bajtů balíčku**.
Nejde o nové ověření provozu na HAOS ani o opakování historických ARM64 testů.

## Přesná výchozí revize

- Repository: `https://github.com/OndraMa/HADS`.
- Ověřená zdrojová větev: `hermes-2-rc2-cloud-verification`.
- Commit: `c491893bd433fa0e17dcd852a3eaa610eb3148ad`.
- Commit message: `Publish exact ARM64-verified Hermes RC3 installer, source, Czech setup manual and verification receipts`.
- Jeho parent: `e1f3f880c98bfa5fafc28261b7859483e11a7e1d`.
- Nová vývojová větev: `codex/hads-next`; výchozí checkout byl čistý.
- V `/workspace` před zahájením nebyl Git checkout. Zadaný repozitář byl získán novým klonem správné větve. Není použit `main` ani historický `HADS4_install_4.6.3.sh`.
- Ve stromu nebyl nalezen `AGENTS.md`.

Release obsahuje historicky pojmenované soubory `hads4.py` a dokumentaci řad 4.x/5.x.
To samo nemění identitu balíčku: `config.yaml` má `version: "2.0.0-rc3"` a ověřený
archiv pochází z adresáře RC3. Historické dokumenty se nesmějí považovat za aktuální
specifikaci nového produktu.

## Reprodukovatelné ověření a rekonstrukce

```sh
python hads-next/tools/reconstruct_rc3.py --extract --write-manifest
```

Skript nikdy nespouští instalační shell ani nerozbaluje do HAOS adresářů. Nejdříve
ověří pevné SHA-256, bezpečnost názvů členů, absenci symlinků, počet a velikost
souborů. Poté porovná obsah distribučního ZIPu, CI ZIPu a tar.gz vloženého v
instalátoru. Rekonstrukce je v ignorovaném `hads-next/legacy-rc3/`; změněné soubory
skript odmítne přepsat. `provenance.json` obsahuje SHA-256 a velikost každého ze
133 souborů. Tento strom slouží auditu, není importován novým runtime.

| Objekt | SHA-256 / výsledek |
| --- | --- |
| RC3 source ZIP | `fc57575471294dc968d78c4474db2ae1717b6c37b5aba1aab6246799febcf848` |
| RC3 instalátor | `ad2c64db2c6b027e9898636c5c18a6ce5d5c2370d3a96977a07df7fa2d9469da` |
| Vložený payload tar.gz | `f325d73174a58d5ceaa1b3c9029ad5c7e38569a2054dadb912f82190bb75b9ca` |
| `cloud-hermes/ci/source-rc3.zip` | Bajtově shodný s release ZIPem |
| Payload vs ZIP | Přesná shoda názvů i obsahu všech 133 souborů |
| Celková velikost rozbalených zdrojů | 1 576 663 bajtů |
| Manuál, release notes a MCP návod | Bajtově shodné uvnitř ZIPu a v release adresáři |

Všech pět samostatně dostupných položek release SHA manifestu souhlasí. Manifest
navíc uvádí `HADS_Rescue_Readback_0.1.0.zip` a samostatný
`HADS4_2.0.0-rc3-payload.tar.gz`, které v release adresáři nejsou. Payload byl
ověřen z instalátoru. Samostatný Rescue ZIP tudíž nově ověřen není; jeho čitelný
zdroj pod `companion/` je součástí ověřeného zdrojového stromu.

SHA shoda prokazuje shodu bajtů s publikovanými očekáváními. Neposkytuje podpis
release, nezávislý bezpečnostní audit ani důkaz správnosti funkce v domácnosti.
Historický `verification.json` uvádí 416 ARM64 testů, Hermes smoke a 186 634 240
bajtů peak paměti, ale zároveň `live_haos_acceptance: false`. Tyto údaje jsou
**historická účtenka dodaná s RC3**, nejsou výsledkem nového běhu HADS Next.

## Zjištěná struktura a příčiny dluhu

25 Python modulů má přibližně 14 851 řádků; samotný `hads4.py` má 8 503 řádků,
`tool_adapters.py` 1 697 a `first_officer.py` 1 076. V hlavním modulu se mísí
HTTP UI, databáze, sběr, analýza, schvalování, orchestrátor oprav, upload a
ověřování záloh. Existují oddělené komponenty, ale jejich hranice jsou závislé
na globálním stavu a callback funkcích hlavního modulu. To ztěžuje důkaz, že každá
cesta zápisu prochází stejným neměnným schválením a nezávislým vykonavatelem.

`repair_engine.py` používá allowlist osmi druhů akcí, včetně restartu Core,
změn voleb aplikací a `recorder_purge`. Pro první nový vertikální scénář je tento
katalog příliš široký. Pozitivní jsou ochrany cesty, zákaz secrets.yaml, hash
původního stavu, zákaz symlinků, soukromé snapshoty a žádný shell/eval. Nejde však
o důvod automaticky převzít celý zapisovací modul a deklarovat jej bezpečným.

## Hermes: co je skutečně v RC3

`Dockerfile`, `hermes_bridge.py` a `hermes_worker.py` odkazují na originální
NousResearch Hermes `v0.22.2`, commit
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
Worker importuje `run_agent.AIAgent`, tedy není pouze přímý LLM HTTP klient.
Současně jej spouští s `enabled_toolsets=[]`, `max_iterations=1`, `skip_memory=True`,
`skip_context_files=True`, `checkpoints_enabled=False` a bez skills/delegace.
AI vrací obálku JSON s požadavky na čtení a HADS může provést další vnější kolo.
To je omezený analytický pracovník, nikoli ověření požadovaného plného upstream
vyšetřovacího workflow. Je třeba znovu ověřit skutečnou upstream tool loop s
malým čtecím katalogem a zachovat izolaci od HA tokenů a vykonavatele.

RC3 obsahuje užitečný bezpečnostní vzor: veřejný runtime uvnitř chroot,
UID/GID 65534, nulové capabilities, seccomp default-deny, zákaz socket/exec/fork,
pozdější zákaz zápisu ve všech vláknech. Předpřipojený descriptor slouží místní
modelové bráně; HA token ani skutečný modelový klíč se do pracovníka nepředává.
Limit workeru je 384 MiB a admission požaduje 576 MiB volné rezervy. Tyto ochrany
se nesmějí nahradit pouhou instrukcí v promptu. Nová upstream konfigurace musí
znovu projít negativními testy; historický test neověřuje novou kombinaci nástrojů.

## Schvalovací identita v RC3

`Handler.require_captain_header` ověřuje pouze konstantní hlavičku
`X-HADS4-Request: captain`. `approve_repair_plan` kontroluje potvrzovací frázi
vázanou na číselné ID plánu a audit zapisuje konstantního aktéra `Kapitán Ondřej`.
HTTP server poslouchá na `0.0.0.0`; balíček současně deklaruje administrační
Ingress. Bez živé síťové konfigurace nelze odvodit skutečnou dosažitelnost mimo
Ingress ani tvrdit vzdálené zneužití. V aplikaci však toto není kryptografický
důkaz identity schvalujícího uživatele, expirace či vazby na neměnnou verzi.
Next proto nesmí tuto schvalovací implementaci přebrat; musí mít vlastní
nezávislou autentizaci a hash konkrétního plánu. Izolovaný test může používat
lokálního operátora, ale není důkazem správnosti budoucí HA Ingress identity.

## OneDrive a zachování bezpečnostního požadavku

Dvě různé větve ochrany je nutné rozlišovat:

1. `install_guard.py` / `native_backup.py`: umí nahrát HA backup přes existující
   HA OneDrive agent a stáhnout jej zpět; porovnává velikost/SHA-256 a očekávaný
   HADS DB obsah. Konkrétní RC3 instalátor má historickou explicitní výjimku
   `no_preinstall_ha_or_cloud_backup_user_requested` a příslušnou cestu nevolá.
   Tato minulá instalační výjimka není autorizací k vynechání zálohy nových oprav.
2. `hads4.py:_execute_approved_batch_sync`: před zápisem tvoří rescue ZIP a
   volá `upload_and_verify_rescue`. Bez nezávislé čtecí služby se batch blokuje.
   Kontroluje vzdálené SHA-256, velikost, config entry, složku a verzi odpovědi.
   `companion/custom_components/hads_rescue/verifier.py` skutečně stahuje OneDrive
   objekt a počítá hash; nevrací pouze očekávanou hodnotu.

Samotný `repair_engine._create_backup` kontroluje jen metadata Supervisoru a
vrací `restore_tested=False`. I vzdálený companion vrací `restore_tested=False`.
Upload, existence objektu, metadata a shodný hash **nedokazují obnovitelnost celé
instalace**. Nový rizikový live zásah musí být zablokován, dokud požadovaná záloha
není nezávisle ověřena pro příslušný rozsah. První izolovaný scénář nemá HAOS
přístup a jeho snapshot/rollback je jen změna testovacího objektu. Nesmí být
vydáván za obnovu HAOS. Stávající RC3 ochrany nejsou měněny ani vypínány.

## Mapa převzetí

| Komponenta RC3 | Rozhodnutí pro Next | Důvod |
| --- | --- | --- |
| RC3 source + instalační archivy | Zachovat beze změny | Auditovatelný původ a návrat ke stávající instalaci |
| Hermes pin, sandbox a broker | Převzít jako referenční vzor, znovu ověřit | Skutečný upstream a konkrétní hranice oprávnění |
| `runtime_core` bounded reads, cache, resource admission | Převzít principy | Omezená paměť a čtení jsou vhodné pro RPi |
| OneDrive hard gate a nezávislý readback | Zachovat bezpečnostní požadavek | Upload ACK nestačí; restore má samostatný důkaz |
| Maskování citlivých dat | Převzít princip a doplnit hraniční testy | Evidence a export nesmějí zveřejnit tokeny |
| `hads4.py` globální orchestrátor | Nepřevzít do nového runtime | Smíšené odpovědnosti a obtížně izolovatelné cesty |
| Široký katalog oprav a recorder purge | Nepřevzít do první verze | Nejprve jeden přesný vratný testovací zásah |
| Hlavní UI s technickými nálezy | Nahradit českým přehledem případů | Uživatel potřebuje dopad, žádost a ověřený výsledek |
| AI JSON závěr a vnější kola | Nepovažovat za dokončené M2 | Nutné prokázat skutečnou Hermes tool loop |
| Staré DB a config | Nemigrovat zápisem v první iteraci | Read-only export, explicitní mapování a oddělené schéma |

## Migrační hranice

Next se vyvíjí v novém adresáři a nové větvi. Nevpisuje schéma do RC3 databáze,
nepřebírá rozpracovaná schválení ani nespouští čekající opravy. Před živou migrací
je nutný read-only export, kontrola retence a redakce, mapování incidentů, snapshot
původních dat, návratový postup a přejímka v testovací HAOS instalaci. Případný
import musí uchovat původ a čas důkazu; importovaná rozhodnutí nikdy neznamenají
platný souhlas k novému plánu.

Živá HAOS autentizace ani testovací domácnost nejsou k dispozici. Kontrola přesných
HA API, nový Hermes runtime, container/ARM64 sestavení a fyzické výsledky musí mít
vlastní protokoly; tento audit je za ně nenahrazuje.
