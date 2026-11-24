# HADS Next 1.0.0-rc3 — opravný instalační kandidát

[Kompletní ZIP](HADS_Next_1.0.0-rc3-komplet.zip) · [Instalátor](HADS_Next_install_1.0.0-rc3.sh) · [Český návod](HADS_Next_1.0.0-rc3-navod-CS.md) · [Integrační přehled](INTEGRATIONS_CS.md) · [SHA-256](HADS_Next_1.0.0-rc3-SHA256SUMS.txt).

U souboru na GitHubu použij Download raw file. Skript nespouštěj ve Windows.
Pro aktuálně nainstalovaný Next RC2 nejprve v HA zastav **pouze HADS Next**.
Potom v terminálu podle návodu:

```sh
bash HADS_Next_install_1.0.0-rc3.sh --verify
bash HADS_Next_install_1.0.0-rc3.sh --upgrade-rc2
```

Po potvrzení RC3 spusť HADS Next ručně. AI zatím nech vypnutou. Nedělej uninstall
ani nemaž /data. Data, vlastník a nastavení se zachovají. Předchozí zdroje se
archivují a nativní update vyžádá částečnou zálohu aplikace. Nejde o obnovu celé
HAOS/OneDrive. Nejasný výsledek se automaticky neopakuje. Upravené nebo jiné
zdroje a stav error místo stopped se nepovažují za ověřený podklad pro upgrade.

Nová instalace bez RC2 používá --install-dev; existující aplikaci nepřepíše.
Původní Hermes 2.0.0-rc3 a ostatní aplikace zůstávají beze změny.

Původní Hermes je ve výsledné image HADS; nativní HA a Music Assistant MCP
adaptéry jsou přiložené. Externí MCP server a model nejsou automaticky zapnuté.
Spook/Watchman se neinstalují jako povinné závislosti. Podrobnosti jsou v matici.

Prošlo 185 regresí na AMD64 i ARM64, skutečný Core s původním Hermes a
skriptovaným modelem, produkční image, paměťová brána, restart, čistá instalace
a aktualizační skript s přesným RC2 zdrojem a falešným HA CLI. Živá aktualizace
Supervisorem ani vytvoření nativní zálohy tím nejsou označené za otestované.

[PR 10](https://github.com/OndraMa/HADS/pull/10) · [Nativní testy](https://github.com/OndraMa/HADS/actions/runs/43378322470) · [Prohlížeč](https://github.com/OndraMa/HADS/actions/runs/43378322338) · [Trvalé protokoly](../../hads-next/docs/evidence/installation-1.0.0-rc3/).

Instalátor SHA-256: `8a23625c688b4282f2661e6b24000a8e5ce3e7886705b4dd02f33805fe5b13d1`.
Testovaný runtime: `02fad0672de32f0edda264196800f9f80a3ed482`. Oba nativní buildy
vytvořily stejné bajty; všechny payload soubory odpovídají testovanému commitu.
Celý ZIP byl vytvořen dvakrát shodně. Zdrojový snapshot je z commitu
`52d9fe69124782291c03a849656144da39e31680`. Obsahuje aktuální HADS Next a
dokumentaci; staré vydané ZIPy zůstávají samostatně na GitHubu. Pro plnou
reprodukci nativního aktualizačního testu použij checkout repozitáře, kde je
zachovaná i přesná původní RC2 source fixture.

RC3 je kandidát. Skutečný LLM, živý MA MCP server, fyzická zařízení, RPi a
úplná HAOS přejímka stále čekají. Nic se neinstalovalo ani neopravovalo v domácnosti.
