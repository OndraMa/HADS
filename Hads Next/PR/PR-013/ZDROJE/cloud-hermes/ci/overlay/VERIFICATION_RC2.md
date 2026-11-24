# RC2 — důkazy ověření, 20. 10. 2026

První úspěšný test nové izolace: commit
`ba2b1433cf41e14b60d1ff3b6155572949400ea7`,
[GitHub Actions 39409467512](https://github.com/OndraMa/HADS/actions/runs/39409467512).

- 394 Python testů, 0 chyb, 0 selhání, 0 přeskočených.
- Všech 9 JS/UI smluv a syntaktická kontrola prošly.
- Nativní ARM64, Python 3.14, skutečný připnutý Hermes v0.22.2.
- Docker build včetně skutečného analytického kroku prošel.
- Druhý test vynutil Landlock `-1 / ENOSYS`, network none, read-only root,
  512 MiB RAM bez swapu, 1 CPU, 64 PID, no_new_privs a pouze 4 potřebné
  výchozí Docker capabilities. Žádný privileged/SYS_ADMIN/host namespace.
- Výsledek: exit 0, OOMKilled false, cgroup oom/oom_kill 0.
- Špička celého testovacího kontejneru 186437632 B = 177,8 MiB.
- Worker VmHWM 166445056 B = 158,7 MiB; VmPeak 281821184 B = 268,8 MiB.
- Ověřeno odmítnutí socketů, procesů, root eskalace, citlivých cest a zápisu
  během inference; bezpečný úklid mode-000 a symlinků.
- Použit falešný lokální model. Žádné placené API, přístup do HAOS ani oprava.

Tato čísla nejsou univerzální minimum ani záruka pro tvé zatížení. RC2 drží
limit virtuální paměti 384 MiB a před krokem vyžaduje 576 MiB volné rezervy,
včetně 192 MiB pro systém. Použije menší z MemAvailable a cgroup headroom.
Tvůj vzorek 597596 KiB odpovídá 583,6 MiB, tedy jen těsně nad admission.
Při poklesu pod limit se krok odloží bez placení, neobejde se bezpečnost.

Po těchto výsledcích následuje finální test RC2 se třemi po sobě jdoucími
pracovníky v témže 512MiB kontejneru. Jeho stav je uveden v předávací zprávě;
nezaměňovat tento první úspěch s testem všech pozdějších změn.

Neověřeno: konkrétní HAOS AppArmor/seccomp profil, celkový souběh doplňků na RPi,
skutečný API poskytovatel, OneDrive readback a provedení oprav po schválení.
