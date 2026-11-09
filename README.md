# HADS — stažení a návody

## HADS Next 0.1.0-dev1 pro testovací HAOS

**[Otevřít stránku vydání a stáhnout vše](https://github.com/OndraMa/HADS/releases/tag/hads-next-0.1.0-dev1)**

Na stránce vydání zvol **Stáhnout kompletní ZIP**, nebo otevři
**[složku KE_STAZENI](KE_STAZENI/HADS_Next_0.1.0-dev1/)**
a soubor `HADS_Next_0.1.0-dev1-komplet.zip`. Obsahuje instalační
soubor, české návody, zdrojový balíček aplikace a celý verzovaný repozitář.
Cloudový panel ChatGPT není potřeba. Repozitář je soukromý: přihlas se na GitHub
účtem, který k němu má přístup.

- [Postup stažení ve Windows](hads-next/docs/STAZENI_WINDOWS_CS.md)
- [Instalační soubor na GitHubu](hads-next/releases/0.1.0-dev1/HADS_Next_install_0.1.0-dev1.sh)
- [Český návod pro HAOS](hads-next/haos/DOCS.md)
- [Kontrolní součty SHA-256](hads-next/releases/0.1.0-dev1/SHA256SUMS)
- [Zdrojový kód, testy a dokumentace HADS Next](hads-next/)
- [Ověřené výsledky a omezení](hads-next/docs/results.md)

Jde o **vývojovou verzi**, která se instaluje vedle RC3. Umožňuje čtení Core
a incidentní spisy; Hermes a živé opravy v této instalační aplikaci nejsou aktivní.
Živá HAOS a ARM64/RPi přejímka čekají. Soubor `.sh` se spouští v terminálu HAOS,
nikoli ve Windows.

## Proč je na výchozí stránce stará 4.6.3

Výchozí větev `main` obsahuje historickou verzi. Pro novou práci vyber nad
seznamem souborů **`codex/hads-next`**, nebo otevři výše uvedené **Releases**.
Historické zdroje 4.x nejsou zdroje Hermes RC3 ani HADS Next.

RC3 zůstává beze změn ve větvi `hermes-2-rc2-cloud-verification` a v adresáři
`cloud-hermes/releases/2.0.0-rc3/`. Instalátory starších verzí se nepřepisují.
