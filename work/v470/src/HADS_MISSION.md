# Aktuální kandidát 4.7.0-rc3

Aktuální změny a otevřené bezpečnostní/provozní brány: [RELEASE_4.7.0-rc3.md](RELEASE_4.7.0-rc3.md). Upload ACK nestačí. Bez pozitivního funkčního testu není oprava potvrzena. Níže zachovaný starší obsah nesmí rozšiřovat tuto smlouvu.

# HADS: provozní poslání

HADS je lokální diagnostický a rozhodovací systém pro HAOS. Není to seznam
řádků z logu ani automatický nástroj pro mazání konfigurace.

## Závazný tok

1. Sbírá Core, Supervisor, host, stav entit, YAML a výstupy dostupných
   diagnostických doplňků.
2. Normalizuje a slučuje symptomy do jedné příčiny; restartové a přechodné
   události neeskaluje bez opakování nebo ověřeného dopadu.
3. Křížově ověří hlášku aktuálním stavem a funkčním důkazem. Například Meross
   MQTT chyba při funkčním HTTP ovládání není výpadek lampy.
4. Vysvětlí příčinu, důkazy, nejistoty a doporučený další krok lidským jazykem.
5. Připraví přesný vykonatelný plán jen tehdy, když zná cíl, stav před i po,
   riziko, rollback a následné ověření.
6. Kapitán plán samostatně schválí. Přijetí diagnostického závěru nikdy není
   souhlas se zápisem.
7. Před každou dávkou změn ověří rescue i novou plnou zálohu. Při neúspěchu
   zálohy zůstane zápisová brána zamčená.
8. Po opravě provede hlubokou kontrolu, uchová účtenku změny a výsledek označí
   jako ověřovaný, dokud se stav nepotvrdí.

## Důkazní pravidla pro zdroje

Každý konektor má oddělené stavy: aktuálně potvrzená přítomnost, běh procesu,
ověřené rozhraní, poslední úspěšná odpověď, data použitá v analýze a poslední
chyba. Historický log nebo inventář je pouze provenance; nesmí se zobrazit jako
současná instalace ani jako zdravý doplněk.

HADS využívá pouze strojově čitelné, aktuálně ověřené rozhraní konkrétního
doplňku. Chybí-li takové rozhraní, jasně uvede jeho mez a opře se o nativní HA
data; nevymýšlí nálezy ani funkčnost.

## Priorita pro člověka

Přednost mají selhané automatizace, nedostupná zařízení/služby, opakované
problémy Core/Supervisor/host a změny konfigurace s jasným dopadem. Transportní
šum, jednorázové chyby při restartu a interní chyby HADS se vysvětlují a drží
odděleně, dokud se neprokáže skutečný dopad.
