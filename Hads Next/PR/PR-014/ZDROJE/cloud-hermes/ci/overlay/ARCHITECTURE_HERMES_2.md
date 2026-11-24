# HADS Hermes 2 — hranice oprávnění a rozsah

Ingress UI -> HADS diagnostika -> Hermes worker -> požadavek na čtení
-> validátor katalogu/JSON argumentů -> HADS čtecí nástroje -> důkazy
-> další Hermes krok -> strukturovaný závěr -> kompilátor přesného plánu
-> náhled -> schválení -> ověřené OneDrive zálohy -> vykonavatel -> ověření.

Modelový tok: Hermes AIAgent -> dočasný autentizovaný localhost broker
-> perzistentní HADS limity -> OpenAI Responses -> účtenka skutečné usage.
Worker nedostává skutečný API klíč ani Supervisor token. Broker nevystavuje
HA čtení ani opravy; propustí pouze jeden modelový požadavek na krok.

## Proti dodanému návrhu

- HADS produkt + Hermes analytik: implementováno.
- HAOS aplikace a ARM64: připraven build, na RPi dosud neověřeno.
- Ne-AI sběr, konektory, historie, chat, schválení, zálohy: převzato a testováno.
- Nová samostatná HACS integrace a průvodce propojením: nejsou v této RC;
  použité je stávající Ingress UI a publikování HA senzorů.
- Lokální model a více providerů: upstream umožňuje, tato RC používá
  stávající OpenAI Responses bránu. Nejde o slib nové podpory.
- Automatické skills, shell, browser a delegace: záměrně vypnuté.
- Libovolná oprava: není slíbena. Pouze podporované akce přes existující
  kompilátor a vykonavatel; chybějící vykonavatel není falešný plán.

## Izolace a testování

Landlock není vyžadován. Oddělený chroot neobsahuje /data, /share, /config,
/homeassistant ani /proc. UID/GID 65534, nulové capabilities, no_new_privs,
seccomp default-deny bez socket/connect/exec/fork. Po inicializaci je TSYNC
filtrem zakázán také zápis do souborů ve všech vláknech. Jediný rodičem
připojený descriptor slouží HTTPX transportu do autentizované účtované brány.
Přístup přes předané stdin/stdout je záměrný. Pevný RLIMIT_AS 384 MiB,
admission 576 MiB (384 + 192 systémová rezerva), jeden worker současně.
Není to VM ani ochrana před exploitem jádra. Upstream a závislosti jsou
důvěryhodný kód; model a konektorová data nikoli.

Windows offline test není test skutečného seccomp/chroot. Při Docker sestavení
je povinný skutečný AIAgent smoke test s falešným lokálním modelem. Živé
HAOS, konektory, cloud readback a funkční opravu je třeba ověřit po instalaci.
ARM64 cloud test navíc vynucuje ENOSYS Landlock a 512 MiB bez swapu.
