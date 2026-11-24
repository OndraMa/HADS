# HADS — kandidát 4.7.0-rc3

Autonomní čtení důkazů, AI follow-up, dohledatelná analýza a schválení konkrétní opravy s volbou okamžitého spuštění. **Není to dosud živě ověřená finální verze.**

- [Instalátor](outputs/HADS4_install_4.7.0-rc3.sh)
- [Změny, omezení a přejímací testy](work/v470/src/RELEASE_4.7.0-rc3.md)
- [181 offline testů a ověření balíčku](outputs/HADS4_4.7.0-rc3-verification.json)
- [SHA-256](outputs/HADS4_4.7.0-rc3-SHA256.txt)
- [OneDrive readback: samostatná instalace do Core](work/v470/src/companion/README.md)

Zápis vyžaduje souhlas a nezávisle ověřený OneDrive rescue. Volitelný Core companion čte soubor zpět a počítá SHA-256; instalátor doplňku jej neaktivuje. Plná cloudová záloha/rotace a univerzální pozitivní funkční verifikace nejsou dokončené. Živý HAOS, cílový Docker build a obnova nebyly testovány. Pozor: úspěšný unit test není důkaz funkčnosti celé domácnosti.

## Sestavení

Python 3.12+, Node.js a requirements-dev.txt. Spusťte `python work/v470/build_release.py` a `python work/v470/validate_release.py`. Výstupy jsou v outputs, včetně zdrojového ZIPu a samostatného ZIPu HADS Rescue Readback. Původní instalátory zůstávají zachovány. Nezveřejňujte klíče, logy ani databáze.
