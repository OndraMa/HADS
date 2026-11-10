# Stažení HADS Next ve Windows

Přihlas se do soukromého repozitáře OndraMa/HADS a otevři přímo
[větev codex/hads-next-investigation](https://github.com/OndraMa/HADS/tree/codex/hads-next-investigation).
Cloudový panel ChatGPT není potřeba. Na výchozí větvi main může být stará 4.6.3.

## Všechny zdroje, návody a testy

Na stránce větve zvol **Code → Download ZIP**. Archiv rozbal a otevři adresář
`hads-next`. Obsahuje `src/hads_next`, `tests`, `haos`, `lab`, `scripts`
a `docs`. Aktuální návod je
[haos/DOCS.md](../haos/DOCS.md), stav testů v [results.md](results.md).

Kandidát 0.2.0-dev1 prošel nativní přejímkou v AMD64 i ARM64 kontejnerech. Starý instalátor
0.1.0-dev1 nemá nový Hermes runtime; nepoužívej jej jako aktuální balíček.
Připravený nový instalátor a přehledný kompletní ZIP jsou v
[KE_STAZENI/HADS_Next_0.2.0-dev1](../../KE_STAZENI/HADS_Next_0.2.0-dev1/).
Samotný ZIP větve není důkaz úspěšného build/testu.

## Ověření souboru

Na GitHub stránce souboru použij **Download raw file**, nikoli „Uložit stránku
jako“, které může uložit HTML. U soukromého repozitáře může odkaz bez přihlášení
vracet 404. SHA-256 porovnej s manifestem přiloženým ke konkrétnímu kandidátu. Přesný
testovaný instalátor má SHA-256
`ea0c569b03f669d54f2ba5f709821601aad3b45236122c392c86bfe0a09fcb9c`.

V PowerShellu:

```powershell
Get-FileHash .\HADS_Next_install_0.2.0-dev1.sh -Algorithm SHA256
```

Soubor `.sh` se nespouští ve Windows. Na odděleném testovacím HAOS s potřebným
terminálem nejprve použij `--verify` a teprve potom explicitní `--install-dev`,
přesně podle instalačního návodu. Uživatel zatím testovací HAOS nemá; tento
dokument neznamená, že proběhla živá přejímka, ani nedává pokyn k zásahu v domácnosti.

Nový runtime má skutečný upstream Hermes a kontrolu připravenosti bez modelu.
Poskytovatel modelu a veřejný výzkum vyžadují zvláštní souhlas. Produkční zápisy
nejsou zpřístupněné; skutečný LLM, fyzická zařízení a HAOS čekají na přejímku.
