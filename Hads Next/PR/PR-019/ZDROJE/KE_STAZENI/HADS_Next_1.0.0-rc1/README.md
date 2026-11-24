# HADS Next — jeden souhrnný přejímkový kandidát

**Začni kompletním ZIPem `HADS_Next_1.0.0-rc1-komplet.zip`.** Na stránce souboru
použij Download raw file. Repozitář je soukromý; přihlášení do GitHubu je nutné.
Windows ani cloudový panel ChatGPT nejsou potřebné pro čtení zdrojů a návodů.
Instalátor .sh se spouští výhradně podle návodu na odděleném testovacím HAOS.

- [Souhrnný výsledek s jedním stavem každé funkce](VYSLEDKY_A_OMEZENI_CS.md)
- [Nový PR 7](https://github.com/OndraMa/HADS/pull/7)
- [Úspěšné finální AMD64 i ARM64 testy](https://github.com/OndraMa/HADS/actions/runs/42826723489)
- Český návod: `HADS_Next_1.0.0-rc1-navod-CS.md`
- Companion, testovací YAML a postup: `HADS_companion_1.0.0-rc1.zip`
- Přesná čekající živá přejímka: `AKCEPTACE_HAOS_CS.md`
- Všechny kontrolní součty: `HADS_Next_1.0.0-rc1-SHA256SUMS.txt`

Prošlo 157 regresí na každé nativní architektuře i celý řetězec automatická
detekce → původní Hermes/nové Core důkazy → validovaný návrh → souhlas vlastníka
→ skutečné CAS → funkční sledování/report → rollback → znovuotevření spisu.
Skriptovaný byl model. Core, Hermes, HTTP/WS, databáze, CAS, kontext a čas byly skutečné.

**Rozsah opravy je pouze vlastní virtuální reference v přiložené custom integraci.**
Nejde o obecné přepisování automatizací ani produkčně přijatý systém.
Živý HAOS, reálný LLM, Supervisor/MA server, fyzické rádio/Zigbee, OneDrive
restore a RPi 4 / 2 GB mají čekající přejímku. Nový slug zachovává RC3 a 0.1/0.2.

Instalátor má SHA-256:
`ff70a3f2177df001e131ec9724d5857292da0197dc80e1eb87e5cd88fd74ef31`.
Testovaný zdrojový commit: `0457f9c0887f309bcfe197cc9aa2764b85e9e012`.
Všech 44 souborů payloadu odpovídá této revizi, obě architektury vytvořily stejné bajty.
ZIP obsahuje 243 souborů, včetně dokumentace a celého verzovaného repozitáře
z commitu `b4a9ac48efdde8f77fb5abb1f575680b445ab213`. Starší archivy uvnitř
zdrojového repozitáře nejsou aktuální instalátor. Dvě sestavení celého ZIPu
vytvořila stejné bajty. Původní vydané archivy se nepřepisují.
