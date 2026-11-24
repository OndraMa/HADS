# HADS Hermes 2.0.0-rc3 — ověření 2. 11. 2026

[Úspěšný běh ARM64](https://github.com/OndraMa/HADS/actions/runs/41439798311),
commit `e1f3f880c98bfa5fafc28261b7859483e11a7e1d`.

- Přesný zdrojový ZIP SHA-256: `fc57575471294dc968d78c4474db2ae1717b6c37b5aba1aab6246799febcf848`.
- 416 Python testů: 0 chyb, 0 selhání, 0 přeskočených; Python 3.14, nativní ARM64.
- Devět JS/UI sad a syntaxe všech webových skriptů: prošlo.
- Docker build a povinný test skutečného připnutého Hermes v0.22.2: prošlo.
- Tři po sobě jdoucí kroky ve stejném kontejneru: prošlo. Landlock úmyslně ENOSYS,
  512 MiB bez swapu, 1 CPU, network none, read-only root, 64 PID,
  no_new_privs a pouze CHOWN/SETUID/SETGID/SYS_CHROOT při spuštění.
- Špička paměti testovacího kontejneru: 186634240 B (178,0 MiB).
- Nejvyšší worker VmHWM ve třech krocích: 166727680 B (159,0 MiB).
- Exit 0; OOMKilled false; oom_kill 0. Použit falešný model, 0 placených API volání.
- Lokálně prošlo 21 nových Python testů a behaviorální test detailu incidentu.
  Úplný místní běh Windows se zastavil v interním socketpair asyncio;
  není označen jako úspěšný. Úplnou sadu ověřil výše uvedený ARM64 běh.
- Instalátor následně prošel syntaktickou kontrolou Bash, vloženého Pythonu,
  YAML včetně duplicitních klíčů, kontrolou SHA-256 a shodou každého souboru
  vloženého payloadu se zdroji. Instalační zdrojový ZIP je totožný s testovaným ZIP.

Neověřeno: konkrétní profil skutečného HAOS, připojení vašich doplňků,
skutečný model/API klíč, OneDrive readback, obnova a vykonání schválené opravy.
Změny nejsou nasazeny do HAOS. Zveřejnění v testovací větvi nemění hlavní větev.
