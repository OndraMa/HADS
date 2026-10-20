# HADS Hermes 2.0.0-rc2 — oprava spuštění bez Landlock

Skutečný místní NousResearch Hermes v0.22.2, commit
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`, zůstává analytickým agentem.
Nejde o náhradu Hermes pouhým API klientem ani o lokální jazykový model.

## Změny

- Landlock není podmínkou. Worker používá oddělený chroot, UID/GID 65534,
  nulové capabilities, no_new_privs a nativní seccomp allowlist.
- Nemůže vytvořit socket, připojit se do sítě, spustit program, fork ani číst
  konfiguraci HA, zálohy a skutečné klíče. Před zpracováním promptu se zápisy
  uzamknou filtrem synchronizovaným do všech vláken.
- Jediný rodičem připojený descriptor obsluhuje omezený HTTPX transport pro
  skutečný OpenAI SDK uvnitř Hermes. Jeden krok dovolí jediný účtovaný požadavek.
  Opakování, fallback a vnitřní recovery smyčky Hermes jsou vypnuté.
- Opravena instalace upstreamu: editable source, nikoli nepodporovaný wheel.
- Opravena oprávnění soukromých složek i bezpečný úklid mode-000 adresářů
  bez rozšiřování oprávnění kontejneru.
- Pevný limit virtuální paměti pracovníka 384 MiB, jeden pracovník současně,
  omezení CPU, descriptorů, výstupu a časů; měření RSS z důvěryhodného rodiče.

## Bezpečnost a meze ověření

Placené API a web zůstávají samostatně povolované a perzistentně měřené.
Žádná změna HA bez konkrétního schválení a ověřené OneDrive zálohy.
Instalátor na předchozí výslovnou žádost nevytváří novou předinstalační zálohu.

ARM64 kontejnerové testy používají skutečný Hermes a falešný model, ne placené API.
Přesné běhy a měření jsou v `VERIFICATION_RC2.md`. Cloud není skutečný RPi/HAOS:
AppArmor/seccomp cílového HAOS, souběh doplňků, OneDrive a první opravná dávka
vyžadují následnou přejímku. Chyba izolace nesmí povolit neizolovaný fallback.
Nejde o ochranu proti chybě jádra ani záruku všech možných oprav.
