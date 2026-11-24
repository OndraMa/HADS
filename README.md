# HADS

Diagnostika a řízené opravy Home Assistant OS. Repozitář je rozdělený do tří samostatných řad.

| Složka | Verze a stav | Co zde najdeš |
|---|---|---|
| **[Hads 2](Hads%202/)** | **2.1.1** podle vlastníka; instalační balík zatím v dostupném repozitáři chybí | Přehled řady, místo pro 2.1.1, oddělený archiv starších HADS 4.x a PR #1–3 |
| **[Hads Hermess](Hads%20Hermess/)** | **2.0.0-rc3** | Instalátor, zdroje, český manuál, kontrolní součty a cloudové výsledky; historie RC2 |
| **[Hads Next](Hads%20Next/)** | Nejnovější dostupný kandidát **1.0.0-rc10**; RC9 a RC8 zachované | Kompletní balíky, zdrojový strom, návody, přejímky, historie všech Next větví a PR #4–19 |

## Rychlé odkazy

- **[HADS Next RC10 — kompletní balík](Hads%20Next/KE_STAZENI/HADS_Next_1.0.0-rc10-kandidat/HADS_Next_1.0.0-rc10-komplet-kandidat.zip)** · [návod](Hads%20Next/KE_STAZENI/HADS_Next_1.0.0-rc10-kandidat/NAVOD_CS.md) · [SHA-256](Hads%20Next/KE_STAZENI/HADS_Next_1.0.0-rc10-kandidat/SHA256SUMS)
- [HADS Next RC9 — balíky a dokumentace](Hads%20Next/KE_STAZENI/HADS_Next_1.0.0-rc9-kandidat/)
- [Hermess 2.0.0-rc3 — instalátor](Hads%20Hermess/cloud-hermes/releases/2.0.0-rc3/HADS_Hermes_install_2.0.0-rc3.sh) · [český manuál](Hads%20Hermess/cloud-hermes/releases/2.0.0-rc3/HADS_Hermes_2.0.0-rc3-manual-CS.md)
- [Všechny návody HADS Next](Hads%20Next/DOKUMENTACE.md) · [všech 19 pull requestů](Hads%20Next/PR/README.md)

## Jak číst verze

RC10/RC9/RC8 jsou instalační **kandidáti**. Poslední samostatně označené GitHub prerelease je [Next RC7](https://github.com/OndraMa/HADS/releases/tag/hads-next-1.0.0-rc7). Vyšší číslo balíku ani tento přesun nepotvrzují dokončenou živou přejímku HAOS. Staré HADS 4.x nejsou vydání HADS 2.1.1.

## Uspořádání a další vývoj

Tato hlavní větev je přehledný společný katalog a zachovaný obsah projektu, uspořádaný **24. 11. 2026**. Původních **21 větví** je zachováno jako neměnné snímky v adresářích HISTORIE jednotlivých řad. Každá řada má vlastní index Markdown dokumentů a záznam původu. Instalátory, ZIPy a zdrojové soubory snímků mají původní Git otisky.

Aktivní vývoj Next a jeho CI pokračují ve [větvi codex/hads-next-orchestration](https://github.com/OndraMa/HADS/tree/codex/hads-next-orchestration) / [PR #19](https://github.com/OndraMa/HADS/pull/19). Uspořádání neuzavírá ani neslučuje původní PR a nevytváří nové vydání. Při dalším vydání je potřeba aktualizovat tento katalog i odpovídající balíky. Původní soubor 4.6.3 je v [archivu před uspořádáním](Hads%202/HISTORIE/main-pred-usporadanim/HADS4_install_4.6.3.sh).
