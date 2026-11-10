# HADS Next 0.2.0-dev1 — soubory ke stažení

Pro stažení všeho otevři **HADS_Next_0.2.0-dev1-komplet.zip** a použij ikonu
Download raw file. Obsahuje instalátor, český návod, výsledky, přejímkový protokol,
kontrolní součty a verzovaný zdrojový repozitář. Přihlášení do soukromého GitHubu
je nutné; cloudový panel ChatGPT není potřeba.

Začni souborem **CTI_ME_NEJDRIVE_CS.txt**. Instalátor se spouští na odděleném
**testovacím HAOS**, nikoli ve Windows. Nový slug zachovává RC3 i starý Next.

**Prošlo:** nativní AMD64 a ARM64 kontejnerové testy, skutečný Core a původní
Hermes, kontrola připravenosti bez modelu, paměťová brána, restart a 150 regresí
na každé architektuře. Modelový endpoint byl skriptovaný.
**Čeká:** skutečný LLM, živý HAOS/Supervisor/MA, fyzická zařízení a RPi 4 / 2 GB.
Produkční opravné zápisy jsou vypnuté. Nejde o produkčně ověřený Release Candidate.

[Zdrojový checkpoint 7b3df24](https://github.com/OndraMa/HADS/commit/7b3df242cd3aa056d76d64a478f122dca4fed6e9),
[úspěšná přejímka obou architektur](https://github.com/OndraMa/HADS/actions/runs/42678100603).
Instalátor přesně odpovídá testovaným bajtům; nebyl nově přebalen pod stejnou verzí.
SHA-256 instalátoru:
`ea0c569b03f669d54f2ba5f709821601aad3b45236122c392c86bfe0a09fcb9c`.

Podrobný aktuální stav je ve VYSLEDKY_A_OMEZENI_CS.md; původní schválený
instalační návod je HADS_Next_0.2.0-dev1-navod-CS.md. Dokumentace/repozitář
v kompletním ZIPu mají commit ade374d2c6ee05a0842feb5d66d39f0d7f6cccb9.
