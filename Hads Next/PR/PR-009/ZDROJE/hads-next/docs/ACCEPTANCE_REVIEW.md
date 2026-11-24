# Kritická přejímková revize RC1

Ověřený lokální i vzdálený HEAD: d2c8ad5da09287d256c324d6e4434bf92499d018,
PR 7, 10. 11. 2026. Nová bezpečná větev codex/hads-next-practical-acceptance.
Vydané archivy a RC3 zůstávají beze změny.

Kontrolní seznam implementace:
- [ ] P0: užitečná nativní operace mimo virtuální referenci, vlastník/intent/konfigurace/funkční výsledek.
- [ ] P0: systémové kontroly s deduplikací, korelací a cílenou AI frontou.
- [ ] P0: samostatná živá přejímka, jednorázový modelový test po souhlasu, anonymizovaný export.
- [ ] Monitoring: legitimní změny, mezery pokrytí, response deadline a opakování.
- [ ] Verifier: žádné uzavření přes mezeru či přerušený cílový stav.
- [ ] P1: měření zdrojů a funkční diagnostický provoz bez AI.
- [ ] Skutečný Core, původní Hermes, bezpečnostní negativní testy a obě architektury.
- [ ] Jeden souhrnný report a přesně testované instalační bajty až po dostupných branách.

Ověřené upstream kontrakty Core 2026.11.0:
- automation/services.yaml: blob 6b3afdca33508f48030a1916ddba7e0d3feacedd.
- automation/services.py: blob 83b8d5c81f445d4e4f066a01f1955527b356e3fa.
- automation/entity.py: blob 90d503f65b86dd01157c461e99e444417d2ba7c9.
- api/__init__.py: blob a66f75403c21c1dd64771713d60704502de0ee81.
- repairs/websocket_api.py: blob b7daa5f69527f7508fc8efac6a87e5c3c265f4e5.

automation.turn_on aktivuje odběry triggerů, nespouští explicitní automation.trigger.
turn_off má stop_actions; rollback musí použít false a nedeklarovat návrat
fyzických účinků dřívějších akcí. Jde o stavovou službu, nikoli atomický config CAS.
