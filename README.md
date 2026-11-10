# HADS — stažení a návody

Aktuální vývojová větev je **codex/hads-next-investigation**.
Ve Windows otevři přímo [složku ke stažení HADS Next 0.2.0-dev1](https://github.com/OndraMa/HADS/tree/codex/hads-next-investigation/KE_STAZENI/HADS_Next_0.2.0-dev1).
Kompletní ZIP obsahuje instalátor, český návod, kontrolní součty, testovací
protokoly a verzované zdroje. Cloudový panel ChatGPT není potřeba.

- [Stažení ve Windows](hads-next/docs/STAZENI_WINDOWS_CS.md)
- [První nastavení a instalace](hads-next/haos/DOCS.md)
- [Výsledky a čekající schopnosti](hads-next/docs/results.md)
- [Kontrolovatelný návrh změn č. 6](https://github.com/OndraMa/HADS/pull/6)
- [Úspěšné AMD64 i ARM64 testy](https://github.com/OndraMa/HADS/actions/runs/42678100603)

Kandidát obsahuje skutečný původní Hermes, oddělený čtecí broker a kontrolu
připravenosti bez modelu. Obě architektury prošly testy se skutečným Core a
instalačním image. Modelový endpoint byl skriptovaný. **Živý HAOS, skutečný LLM,
fyzická zařízení a RPi zatím přijaté nejsou; produkční zápisy jsou vypnuté.**
Používej oddělený testovací HAOS. Stažení není pokyn k zásahu v domácnosti.

Výchozí main může dál ukazovat starý HADS 4.6.3. Přepni větev nad seznamem
souborů nebo použij přímé odkazy výše. RC3 zůstává ve větvi
`hermes-2-rc2-cloud-verification`; vydané archivy se nepřepisují.

Historický [balíček 0.1.0-dev1](KE_STAZENI/HADS_Next_0.1.0-dev1/) nový Hermes
runtime neobsahuje. Nepoužívej jej jako aktuální instalátor.
