# HADS — Kapitánské diagnostické centrum

## 4.7.0-rc1: kandidát k ověření

HADS sbírá diagnostické důkazy, připravuje závěry a podporované opravné plány. Závěr není oprava. Zápisy vyžadují schválení a zálohu; dostupnost doplňku sama nepotvrzuje funkčnost jeho diagnostiky.

- [Instalátor 4.7.0-rc1](outputs/HADS4_install_4.7.0-rc1.sh)
- [Změny, omezení a instalační postup](work/v470/src/RELEASE_4.7.0-rc1.md)
- [Výzkum konektorů a diagnostiky](docs/HADS_RESEARCH_2026-09-11.md)
- [Výsledky offline testů](outputs/HADS4_4.7.0-rc1-verification.json)
- [Kontrolní součty](outputs/HADS4_4.7.0-rc1-SHA256.txt)

Toto není potvrzení plně autonomních oprav celého HAOS. Neproběhl živý test na HAOS, Docker build cílové architektury, placené OpenAI volání ani obnova zálohy. Před produkčním použitím proveďte akceptační kroky z poznámek k vydání. Původní instalátor 4.6.3 zůstává zachován.

## Sestavení

Zdroj je v `work/v470/src`. Potřebujete Python 3.12+ s PyYAML a websocket-client a Node.js. V izolovaném prostředí nainstalujte závislosti z `requirements-dev.txt`, potom spusťte:

```sh
python work/v470/build_release.py
python work/v470/validate_release.py
```

Sestavení nejdříve spustí testy a vytvoří instalátor, zdrojový ZIP a kontrolní součty v `outputs`. Historický instalátor 4.5.0 slouží pouze jako obal sestavení; jeho vložený payload se nahrazuje současným zdrojem. ZIP a payload uvedené v součtech vzniknou při sestavení, nejsou samostatně uložené v této větvi.

Nové změny posuzujte přes pull request; kandidáta nepovažujte za stabilní jen podle zelených offline testů. Neukládejte API klíče, domácí logy ani databáze do repozitáře.
