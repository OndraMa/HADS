# HADS Next 1.0.0-rc2 – instalační kandidát

[Kompletní ZIP](HADS_Next_1.0.0-rc2-komplet.zip), [instalátor](HADS_Next_install_1.0.0-rc2.sh),
[český návod](HADS_Next_1.0.0-rc2-navod-CS.md), [kontrolní součty](HADS_Next_1.0.0-rc2-SHA256SUMS.txt).
U souboru v přihlášeném GitHubu použij Download raw file. Skript .sh se nespouští ve Windows.

[PR 8](https://github.com/OndraMa/HADS/pull/8),
[úspěšné AMD64/ARM64 ověření](https://github.com/OndraMa/HADS/actions/runs/43278689080),
[trvalé protokoly](../../hads-next/docs/evidence/installation-1.0.0-rc2/),
[živé ověření bez testovacího HAOS](../../hads-next/docs/LIVE_WITHOUT_TEST_HAOS_CS.md).

Na obou architekturách prošlo 168 regresí a skutečný Core s původním Hermes,
praktickou nativní opravou a funkčním ověřením. Model byl skriptovaný, světlo virtuální.
Balíčky obou architektur jsou shodné a odpovídají přesnému testovanému zdroji.
Celý ZIP byl sestaven dvakrát se shodnými bajty.

Nová aplikace má slug local_hads_next_practical; RC1, RC3 a staré aplikace se nepřepisují.
AI, autonomní modelová analýza a opravy zůstávají při první instalaci vypnuté.
Pozdější živé ověření začne čtením. Nejde o přijaté produkční vydání: skutečný HAOS,
fyzická zařízení, RPi a úsudek reálného LLM ještě čekají.

Instalátor SHA-256: e09c1d0a4b7b10775ba2e5ef238a68390316793dadb355074798e3d28e9e7a29
Testovaný runtime: 5fb55e1974e2fd25edde54d4446dcf28ea5d8933
