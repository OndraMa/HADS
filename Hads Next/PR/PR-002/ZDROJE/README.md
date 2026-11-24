# HADS — kandidát 4.7.0-rc2

Bezpečnostní stabilizace, nikoli dokončený autonomní opravář.

- [Instalátor](outputs/HADS4_install_4.7.0-rc2.sh)
- [Změny, omezení a otevřené brány](work/v470/src/RELEASE_4.7.0-rc2.md)
- [Výsledky 146 offline testů](outputs/HADS4_4.7.0-rc2-verification.json)
- [SHA-256](outputs/HADS4_4.7.0-rc2-SHA256.txt)

Bez nezávislého OneDrive ověření zápis zůstává zablokovaný. Rotace poslední cloudové zálohy a úplné nové plánování po selhání nejsou dokončené. Živý HAOS, cílový Docker build a obnova nebyly testovány.

## Sestavení

Python 3.12+, Node.js a requirements-dev.txt. Spusťte `python work/v470/build_release.py` a `python work/v470/validate_release.py`. Výstupy v outputs; zdrojový ZIP se vytvoří při sestavení. Původní instalátory zůstávají zachovány. Nezveřejňujte klíče, logy ani databáze.
