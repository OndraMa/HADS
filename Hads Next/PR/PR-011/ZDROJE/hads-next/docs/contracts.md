# Kontrakty vertikálního scénáře

První verze je oddělený vývojový balík. Produkční RC3 ani archivy se nemění.
Pouze izolovaný opravný cíl může být zapisovatelný. Žádný HA write adaptér,
shell ani obecný MCP proxy není součástí veřejného rozhraní.

Výměnná data jsou JSON objekty. Čas je UTC Unix timestamp (sekundy).
Evidence obsahuje `source`, `kind`, `observed_at`, `payload`, `event_id`
(původní identifikátor; pokud chybí, hash kanonického obsahu).
Zachovat čas události odděleně od času čtení; znovunačtení není nový důkaz.
Source status rozlišuje installed/running/interface_available/authenticated/
read_succeeded/relevant/last_error a stáří důkazu; neznámé hodnoty jsou null.

Každá vrstva přijímá explicitní závislosti. Databáze je SQLite s verzí schématu.
Incidentní store uchovává celé důkazy, opakování a audit; AI má pouze kopii
relevantních důkazů bez tajemství. Analýzu znovu spouští až nový otisk důkazů.
Claim analýzy přetrvává i po pádu. Zůstal-li po restartu ve stavu running,
stejná data se automaticky znovu neanalyzují; je potřeba nový důkaz a přerušení
zůstává viditelné ve spisu. Tento stav není úspěšně dokončené vyšetření.
Evidence má limit 64 KiB na událost, 1000 událostí a 4 MiB na spis. Opakované
načtení identického eventu nezvyšuje počet důkazů ani výskytů. Nový skutečný
výskyt s novým ID znovu otevře i dříve vyřešený spis.

Opravný plán je neměnný kanonický JSON svázaný hashem. Obsahuje původní stav,
konkrétní změnu, důvod, evidence IDs, riziko, preconditions, backup policy,
funkční podmínku ověření, rollback a ruční alternativu. První operace opravuje
jediný chybný entity_id v izolovaném JSON fixture automatizace, nikoli HA YAML.
Její cílový kořen je explicitně lokální testovací adresář. Schválení vydává
oddělená lokální uživatelská služba; AI k ní nemá přístup. Toto rozhraní není
autentizace uživatele v HAOS a nesmí se vystavit přes HTTP bez následné integrace.

Provedení musí nejdříve trvale spotřebovat schválení a zapsat intent. Po pádu
se intent nikdy automaticky neopakuje. Neznámý stav vyžaduje nové zjištění stavu
a nové schválení. Ověření požaduje nové funkční důkazy po zásahu a sledovací dobu;
HTTP úspěch nebo zmizení chyby nejsou funkční důkaz.

Role jsou serializované logické specializace; jedna aktivní AI úloha, omezené
počty kroků/čtení a objem dat. Deterministická diagnostika funguje bez modelu.
