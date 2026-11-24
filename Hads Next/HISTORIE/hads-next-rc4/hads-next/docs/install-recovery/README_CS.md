# Obnova instalace HADS Next RC3 po odinstalování

## Doložený problém

Uživatel zastavil Next RC2, aplikace přešla do stavu `error`. RC3 upgrade vyžadoval
potvrzené `stopped` a opakovaně skončil ještě před změnou zdrojů. Po uživatelově
odinstalování zůstaly místní zdroje. Nová instalace je z bezpečnostních důvodů
odmítala přepsat. `--verify` jen ověřuje balíček; neprovádí instalaci. `--install`
není podporovaný argument původního RC3 skriptu. Přepínání mezi starými verzemi
neřeší ponechané zdroje. Snímek také ukazuje nutnost absolutní cesty `/config/...`.

Jde o nepokrytý instalační scénář, nikoli důkaz poruchy Core. Příčina stavu
`error` při zastavování není živě prokázaná ani tímto nástrojem opravená. Uživatele
neposíláme do dalšího odinstalování. Nástroj neodinstaluje ani nezastaví žádnou
registrovanou aplikaci; samotný `error` nepovažuje za důkaz její nepřítomnosti.

## Přesný rozsah nápravy

Samostatný stdlib Python pomocník nejprve čte úplný validní seznam instalovaných
aplikací přes podporovaný HA CLI. Pokračuje pouze při potvrzené nepřítomnosti
`local_hads_next_practical`. Ověří SHA-256 přesného vydaného RC3 instalátoru.

Ponechaný zdrojový adresář musí byte po bytu odpovídat vydanému RC2 nebo RC3,
včetně důvěryhodného manifestu. Neznámé soubory, změněné hashe a symlinky se
nepřesouvají. Původní zdroje se archivují a archiv se nezávisle přečte. Adresář
zůstane zachovaný pod jiným názvem; jeho kořenový config.yaml se přejmenuje,
aby nevznikla druhá aplikace v místním katalogu. Nic se nemaže v `/data` ani
v konfiguraci domácnosti. Ostatní aplikace a jejich zdroje se nemění.

Po opakované kontrole nepřítomnosti aplikace pomocník zavolá jen původní,
SHA-256 ověřený RC3 skript s `--install-dev`. Vyžaduje následné potvrzení verze
1.0.0-rc3 a stavu `started`. Nejasný předchozí upgrade, neúspěch instalace nebo
nepotvrzený výsledek zachová marker a zabrání slepému opakování. Nepoužívá se
žádný force, uninstall, restart jiných aplikací nebo snížení paměťové brány.

## Použití

Stáhni pomocník jako `HADS_Next_obnovit_instalaci_RC3.py` přes Download raw file
na GitHubu a ulož ho do `/config`, kde už podle snímku leží původní RC3 instalátor.
Nevkládej do něj klíče, tokeny ani hesla. Neprováděj současně další instalaci.

Pouhá kontrola bez změn:

```sh
python3 /config/HADS_Next_obnovit_instalaci_RC3.py --inspect
```

Pro doloženou situaci po odinstalování:

```sh
python3 /config/HADS_Next_obnovit_instalaci_RC3.py --recover-and-install /config/HADS_Next_install_1.0.0-rc3.sh
```

Pokud seznam aplikací ještě obsahuje Next, pokud je původ zdrojů neznámý nebo
existuje nedokončený marker, pomocník nic nepřesune. Zachovej přesnou hlášku;
nemaž adresáře nebo marker a neodinstalovávej znovu. Pokud soubor RC3 není přesný,
stáhni ho z původního předvydání `hads-next-1.0.0-rc3` přes Download raw file.

## Data a hranice ověření

Odinstalování mohlo odstranit soukromá data aplikace. Ze snímku nelze určit,
zda přežila. Pomocník na případná zachovaná data nesahá, ale neobnoví databázi,
která už byla odstraněná; kopie zdrojů není záloha dat ani HAOS/OneDrive restore.
Po instalaci může být nutné znovu potvrdit vlastníka. AI nech vypnutou.

Nativní kontejnerové testy používají skutečný pomocník, skutečné vydané RC2
zdroje a přesný RC3 instalátor, ale falešný Supervisor/HA CLI. Reprodukují sled
`installed/error → uživatelova předchozí odinstalace → zbylé zdroje → obnovení →
instalace RC3`, kontrolují zachování datových canary souborů a ostatních zdrojů.
Nejde o živou HAOS přejímku ani důkaz, že skutečné odinstalování data zachovalo.
Samotná aplikace RC3, její schválené opravy a Hermes se tímto pomocníkem nemění.
