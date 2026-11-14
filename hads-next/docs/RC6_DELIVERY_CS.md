# HADS Next 1.0.0-rc6 — opravy sběru a audit integrací

Jde o instalační kandidát opravující konkrétní chyby RC5, nikoli dokončení celého původního zadání.
Výsledek nativního sestavení a přesné hashe instalátoru jsou v `docs/evidence/installation-1.0.0-rc6/ACCEPTANCE.json`
po dokončení přejímky. Chybějící či neúspěšný protokol znamená, že balíček dosud není vydaný.

## Změny

- Supervisor slug s pomlčkou/tečkou/velkými písmeny se validuje podle upstream kontraktu; jedna vadná položka
  už nezruší inventář ostatních aplikací ani jejich čtení spotřeby paměti. Neplatné položky zůstávají mezerou v pokrytí.
- Watchman se čte podle vlastnictví a unique IDs v registru, včetně atributů odkazů/souborů/řádků.
  Nevyvolává nový sken, report, zápis ani model. Neznámé schéma, neúplný počet nebo probíhající parsování není úspěšná kontrola.
- Podklady Watchmanu mají společný diagnostický spis, nejsou zaměněné za prokázanou funkční poruchu domácnosti.
  Opakované načtení nevytvoří další výskyt ani důkaz; zmizení nálezu případ automaticky funkčně neuzavře.
  Zakázané entity ani záměny s ESPHome se automaticky neupravují.
- Přiložen podrobný [návod HA-MCP/Hermes](../haos/HAMCP_HERMES_CS.md) a
  [posouzení HASS-AI-Orchestrator 0.13.6](ORCHESTRATOR_REVIEW_CS.md) podle konkrétních upstream revizí.

## Instalace z RC5

Stáhni aktuální `.sh` z vydaného adresáře `KE_STAZENI/HADS_Next_1.0.0-rc6` do `/config`.
Jde pouze o úvodní aktualizaci aplikace; další diagnostické příkazy od uživatele se nepožadují.

```sh
bash /config/HADS_Next_install_1.0.0-rc6.sh --verify
bash /config/HADS_Next_install_1.0.0-rc6.sh --upgrade-rc5
```

RC5 předem nezastavuj ani neodinstalovávej. Ověřuje se přesný vydaný RC5 manifest
`ffd85701e410a2e8b8ccf97643db88233addf7dbb6fd9d78a3824276eeeb491d` a všechny soubory.
Zdrojová záloha není záloha dat aplikace ani HAOS. Nativní update požaduje částečnou zálohu;
nezávislá obnovitelnost HAOS/OneDrive tím není prokázaná. Při nejistotě se zásah neopakuje automaticky.
Staré publikované archivy se nemění a neodinstalovává se žádná jiná aplikace.

## Co zbývá

Obecný aktivní HA-MCP/Hamster adaptér, autentizované vlastní čtení Inspectoru/HADocs a opravné operace
Spook/registry/statistiky/YAML nejsou dokončené. Přepínače serveru, import starých options ani nová verze
samotného doplňku tuto implementaci nenahradí. Stávající úzký opravný katalog zůstává beze změny.

Originální Hermes je součástí obrazu; vyžaduje paměťovou rezervu 576 MiB a pro model výslovný souhlas.
AI i automatické placené vyšetřování se aktualizací samy nezapnou. Produkční zásah, skutečný placený LLM,
fyzická zařízení a plná živá HAOS přejímka nebyly v tomto prostředí provedené.

## Přejímka po instalaci

HADS sám obnoví inventář a nativní podklady. Na **Doplňky a ověření** se mají objevit rozpoznané aplikace
a konkrétní podrobnosti Watchmanu, pokud jeho nainstalovaná verze poskytuje ověřené atributy/unique IDs.
Počty i umístění musí odpovídat stejnému zdrojovému snímku. Přejmenované entity se hledají přes registr.
Neúplná data nebo starý čas skenu se nesmějí stát zeleným potvrzením funkčnosti doplňku.
Žádná automatizace, spínač, hlasitost, statistika ani registr se touto kontrolou nemění.
