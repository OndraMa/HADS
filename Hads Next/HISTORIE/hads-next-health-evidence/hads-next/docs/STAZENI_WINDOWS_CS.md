# Stažení HADS Next ve Windows

Přihlas se do GitHubu s přístupem k soukromému OndraMa/HADS. Otevři přímo
[větev finálního kandidátu](https://github.com/OndraMa/HADS/tree/codex/hads-next-final-delivery)
a složku [KE_STAZENI/HADS_Next_1.0.0-rc1](../../KE_STAZENI/HADS_Next_1.0.0-rc1/).

Otevři `HADS_Next_1.0.0-rc1-komplet.zip` a stiskni **Download raw file**.
Neukládej HTML stránky pomocí „Uložit stránku jako“. ZIP obsahuje instalátor,
český návod, companion integraci s testovacím YAML, souhrnný protokol, kontrolní
součty a verzované zdroje. Začni `CTI_ME_NEJDRIVE_CS.txt` v kořeni ZIPu.

Pokud je na výchozí stránce stále 4.6.3, jsi na main. Přepni větev nebo použij
přímý odkaz. Cloudový panel ChatGPT není potřeba. 404 soukromého odkazu může
znamenat chybějící přihlášení nebo přístup. Starší 0.1 a 0.2 nejsou aktuální kandidát.

V PowerShellu porovnej instalační soubor s přiloženým SHA-256 manifestem:

```powershell
Get-FileHash .\HADS_Next_install_1.0.0-rc1.sh -Algorithm SHA256
```

Soubor .sh se spouští pouze v odpovídajícím terminálu **odděleného testovacího
HAOS**, nikoli ve Windows ani v produkční domácnosti. Podrobné podmínky jsou
v [haos/DOCS.md](../haos/DOCS.md). Nejprve `--verify`, potom explicitní
`--install-dev`. Samotná kontrola ani stažení nejsou živou přejímkou.

[Souhrn výsledků a přesné hranice](FINAL_DELIVERY.md). Kandidát není produkčně
ověřený. Model i autonomní AI vyžadují souhlas; opravný katalog je jen vlastní
virtuální reference s novým schválením každého plánu.
