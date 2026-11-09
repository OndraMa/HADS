# Stažení HADS Next ve Windows

Cloudový panel ChatGPT není ke stažení potřeba. Soubory jsou v soukromém
repozitáři **OndraMa/HADS** na GitHubu, ve větvi **`codex/hads-next`**.
Výchozí větev `main` stále obsahuje starší HADS 4.6.3. Její soubor
`HADS4_install_4.6.3.sh` není instalátor HADS Next.

## Nejjednodušší stažení všeho

Otevři **[GitHub Releases — HADS Next 0.1.0-dev1](https://github.com/OndraMa/HADS/releases/tag/hads-next-0.1.0-dev1)**.
V části **Assets** klikni na **`HADS_Next_0.1.0-dev1-komplet.zip`**.
Tento ZIP má instalátor a český návod hned v kořeni; celý verzovaný repozitář
je v jeho podsložce `zdrojovy-repozitar`. Vedle ZIPu jsou ke stažení také
jednotlivé soubory a kontrolní součty.

Vydání je označené **Pre-release**, protože jde o vývojovou přejímku. Pokud
na výchozí stránce stále vidíš 4.6.3, klikni na **Releases** nebo použij přímý
odkaz výše. Přepnutí nebo sloučení produkční větve k tomu není nutné.

## Otevření správné verze

1. V běžném prohlížeči se přihlas do GitHubu účtem, který má přístup
   k soukromému repozitáři `OndraMa/HADS`.
2. Otevři [větev HADS Next](https://github.com/OndraMa/HADS/tree/codex/hads-next).
3. Nad seznamem souborů musí být vybraná větev **`codex/hads-next`**, nikoli
   `main`. Všechny nové zdroje, návody a výsledky jsou v adresáři `hads-next`.

Pokud GitHub zobrazí 404, nejprve ověř přihlášení a oprávnění k soukromému
repozitáři. Veřejný přímý odkaz na `raw.githubusercontent.com` nemusí u tohoto
repozitáře fungovat; níže jsou odkazy na běžné GitHub stránky souborů.

## Instalátor, návod a kontrolní součty

| Soubor / účel | Odkaz na GitHub |
| --- | --- |
| Samostatný HAOS instalátor | [HADS_Next_install_0.1.0-dev1.sh](https://github.com/OndraMa/HADS/blob/codex/hads-next/hads-next/releases/0.1.0-dev1/HADS_Next_install_0.1.0-dev1.sh) |
| Český instalační návod | [DOCS.md](https://github.com/OndraMa/HADS/blob/codex/hads-next/hads-next/haos/DOCS.md) |
| SHA-256 manifest | [SHA256SUMS](https://github.com/OndraMa/HADS/blob/codex/hads-next/hads-next/releases/0.1.0-dev1/SHA256SUMS) |
| Zdrojový balíček pro sestavení aplikace | [HADS_Next_0.1.0-dev1-source.tar.gz](https://github.com/OndraMa/HADS/blob/codex/hads-next/hads-next/releases/0.1.0-dev1/HADS_Next_0.1.0-dev1-source.tar.gz) |
| Přehled hotových a neověřených funkcí | [results.md](https://github.com/OndraMa/HADS/blob/codex/hads-next/hads-next/docs/results.md) |
| Protokol budoucí živé přejímky | [haos-acceptance.md](https://github.com/OndraMa/HADS/blob/codex/hads-next/hads-next/docs/haos-acceptance.md) |

Na stránce souboru použij tlačítko **Download raw file** (ikona stažení).
Tím uložíš skutečný soubor. Nepoužívej „Uložit stránku jako“, které by mohlo
uložit HTML GitHub stránky namísto instalátoru.

## Všechny soubory jako ZIP

Na [stránce správné větve](https://github.com/OndraMa/HADS/tree/codex/hads-next)
klikni **Code → Download ZIP**. ZIP rozbal ve Windows a otevři adresář
**`hads-next`**. V něm najdeš:

- `releases/0.1.0-dev1/`: instalátor, zdrojový archiv a SHA256SUMS;
- `haos/DOCS.md`: český instalační a uživatelský postup;
- `src/hads_next/`: čitelné zdrojové moduly;
- `tests/`: izolované testy a syntetické vstupy;
- `docs/`: audit, rešerši, architekturu, omezení a přejímku;
- `docs/evidence/`: skutečné uložené výsledky offline a kontejnerových testů.

ZIP obsahuje také historické soubory repozitáře. Pro HADS Next používej výše
uvedený adresář a instalátor verze `0.1.0-dev1`.

## Kontrola ve Windows a spuštění na HAOS

V PowerShellu můžeš zkontrolovat instalační soubor:

```powershell
Get-FileHash -Algorithm SHA256 -Path .\HADS_Next_install_0.1.0-dev1.sh
```

Výsledek porovnej s odpovídajícím řádkem v `SHA256SUMS`. Pro tento distribuovaný
instalátor je očekávaný SHA-256:

```text
8f0f168042e4b269de6edc213b9522b402789f809ec73e16f639b66440a2f2d4
```

**Instalátor `.sh` nespouštěj ve Windows.** Přenes jej do terminálové/SSH
aplikace svého testovacího HAOS, která má přístup k místním aplikacím a poskytuje
`ha`, `bash` a `python3`. V adresáři se souborem potom spusť:

```sh
bash HADS_Next_install_0.1.0-dev1.sh --verify
bash HADS_Next_install_0.1.0-dev1.sh --install-dev
```

Podmínky terminálu, připojeného `/local_apps` nebo `/addons`, minimální verze HA,
nastavení vlastníka `owner_user_id` a přejímka jsou v [instalačním návodu](../haos/DOCS.md).

## Skutečný rozsah tohoto balíčku

Jde o **samostatnou vývojovou aplikaci `0.1.0-dev1`**, která se přidává vedle
RC3 a nepřepisuje jej. Umožňuje české rozhraní, omezené čtení Core, ruční hlášení
incidentu, cílenou historii a vlastní SQLite spisy.

**Hermes ani živé opravy nejsou v instalační aplikaci aktivní.** Předchozí
originální Hermes loop má samostatné offline kontejnerové ověření; není tím
prokázaná bezpečná produkční HAOS integrace. Instalátor není dokončená autonomní
platforma ani produkční RC. Živá HAOS, skutečný ingress a ARM64/RPi přejímka
zůstávají čekající. Tento dokument ani stažení souborů jejich stav nemění.
