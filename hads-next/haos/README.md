# HADS Next 0.2.0-dev1 — vývojová přejímka

Samostatná HAOS aplikace s původním připnutým NousResearch Hermes, čtecími
adaptéry, trvalými incidenty a českým přehledem. AI je ve výchozím stavu vypnutá.
Skutečný test připravenosti Hermes nepotřebuje model ani klíč.

Kandidát je určen pro oddělený testovací HAOS. Živý HAOS, fyzické rádio/Zigbee,
Raspberry Pi 4 a skutečný jazykový model nemají dokončenou přejímku.
Produkční zapisovací opravy nejsou zpřístupněné. Návrh lze posoudit,
odmítnout nebo provést ručně; laboratorní oprava není produkční oprávnění.

Nový slug `local_hads_next_investigation` zachovává RC3 i starý Next. Výchozí
balík neobsahuje testovací Core ani laboratorní zapisovací server. Nevyžaduje
Docker socket, mount konfigurace, vypnutí AppArmor ani další privilegované
capabilities. Postup a přesné hranice jsou v [DOCS.md](DOCS.md).
