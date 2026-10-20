# HADS Hermes RC2 — dokončené cloudové ověření

20. 10. 2026, nativní ARM64 Linux, Python 3.14.

Testovaný vývojový commit: `f3692081cf0dbbb6f92950de9ae1827e229cad11`.
[Úspěšný běh 39410665467](https://github.com/OndraMa/HADS/actions/runs/39410665467),
job `118587451980`. Testy skončily 10:53:15 UTC.

- 395 Python regresí: 0 selhání, 0 chyb, 0 přeskočených.
- 9 JS/UI sad, JS syntax a Python compileall: úspěch.
- Sestavení Docker obrazu včetně skutečného Hermes analytického kroku: úspěch.
- Další 3 po sobě jdoucí kroky skutečného Hermes v0.22.2: úspěch.
- Upstream commit: `d923a5eb487a17c0a68801bba9ef0f56c81040a8`.
- Falešný lokální model; žádné placené API ani zásah do produkčního HAOS.

## Vynucené podmínky kontejneru

Landlock ABI -1 / ENOSYS pomocí přidaného seccomp filtru; nejde o vypnutí
Docker ochrany. RAM 512 MiB, bez swapu, 1 CPU, 64 PID, read-only root a
privátní tmpfs, network none, no_new_privs. Capabilities pouze CHOWN, SETUID,
SETGID, SYS_CHROOT; žádné SYS_ADMIN, privileged ani host namespaces.

Worker používá chroot bez HA mountů, UID/GID 65534, nulové capabilities,
nativní seccomp allowlist a další TSYNC filtr zakazující zápisy během inference.
Prošly negativní testy citlivých cest, vytváření socketů, exec/fork a root
eskalace i úklid nepřístupných adresářů a symlinků.

## Naměřeno při třech krocích

| Ukazatel | Výsledek |
|---|---:|
| Nejvyšší cgroup memory.peak celého testu | 185499648 B = 176,9 MiB |
| Nejvyšší worker VmHWM | 166547456 B = 158,8 MiB |
| Nejvyšší worker VmPeak | 281833472 B = 268,8 MiB |
| Ukončení kontejneru | exit 0 |
| OOMKilled | false |
| cgroup oom / oom_kill | 0 / 0 |

Jde o malé falešné analytické kroky, nikoli celou zátěž HAOS. Worker má pevný
RLIMIT_AS 384 MiB; admission vyžaduje 576 MiB dostupné rezervy (384 + 192 pro
systém), podle menší hodnoty MemAvailable/cgroup headroom. Jeden worker najednou.
Vnitřní modelové retry/recovery a fallback jsou vypnuté; HADS měří každý požadavek.

## Co výsledek nepotvrzuje

Konkrétní AppArmor/seccomp profil cílového HAOS, výkon a souběh všech doplňků
na uživatelově RPi 4B 2GB, skutečný poskytovatel API, OneDrive readback a výsledek
schválené opravy. Tyto kroky vyžadují přejímku po instalaci. Chyba izolace musí
zastavit pracovníka před placeným API; není povolen neizolovaný fallback.

Instalátor na předchozí výslovnou žádost nevytváří novou předinstalační HA ani
OneDrive zálohu. Opravy nadále vyžadují konkrétní schválení a ověřené cloudové
zálohy. Main větev a běžící HAOS nebyly změněny.
