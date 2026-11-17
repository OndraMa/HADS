"""Czech provider verification view. No credentials or raw provider payloads."""
from html import escape
from .dashboard import display_time

def render_providers(app, csrf):
    rows=app.providers.snapshot();zone=app.snapshot()['timezone']
    catalog={r['id']:r for r in app.tools.registry.providers()}
    body='<h1>Inventář a nativní stopy doplňků</h1><p><a href="tools">Otevřít skutečné konektory, katalog funkcí a jejich ověřené výsledky</a></p><p>Instalace, běžící proces a přečtený stav jsou různé důkazy. Žádný z nich sám nepotvrzuje funkci celého diagnostického nástroje.</p>'
    if not rows:body+='<p>Aktuální kontrola dosud neproběhla. Historický výpis předchozího HADS ji nenahrazuje.</p>'
    for row in rows:
        tool=catalog.get(row['provider_id'],{})
        current=tool.get('connected') is True and app.clock()-tool.get('checked_at',0)<=600
        actual_read=current and tool.get('diagnostic_read_verified') is True
        summary='Společný konektor přečetl diagnostickou odpověď a předává ji incidentnímu systému. Rozsah funkcí, původ a omezení ukazuje katalog; samotná odpověď nepotvrzuje funkční zdraví zařízení.' if actual_read else row['summary_cs']
        body+='<article><h2>'+escape(row['title'])+'</h2><p>'+escape(summary)+'</p>'
        body+='<p>Poslední čtení: '+escape(display_time(row['checked_at'],zone))+(' — výsledek je starší než 10 minut.' if row['stale'] else '')+'</p>'
        if row['last_error']:body+='<p>'+escape(row['last_error'])+'</p>'
        body+='<p>Načtené komponenty: '+escape(', '.join(row['matched_components']) or 'nepotvrzené')+'. Záznamy registru se shodnou platformou: '+str(row['owned_entity_count'])+'.</p>'
        for item in row['applications']:
            label={'started':'běží','stopped':'zastavená','error':'hlásí chybu','failed':'hlásí chybu','startup':'startuje'}.get(item['state'],'stav neověřený')
            body+='<p>Aplikace '+escape(item['slug'])+': '+label+'; verze '+escape(item['version'] or 'neověřená')+'. Proces není funkční test.</p>'
        if row['samples']:
            body+='<ul>'+''.join('<li>'+escape(x['entity_id'])+': '+escape(str(x['state']) if x['state'] is not None else 'soukromý nebo nepodporovaný text vynechán')+'; změna stavu '+escape(display_time(x['source_updated_at'],zone))+'</li>' for x in row['samples'])+'</ul><p>Čas změny entity není důkaz nového skenu doplňku.</p>'
        native=row.get('diagnostic_read')
        if native and row['provider_id']=='watchman':
            body+='<h3>Existující hlášení Watchmanu</h3><p>'+('Počty a podrobnosti přečtené.' if native['read_verified'] else 'Čtení hlášení je neúplné; není to nulový nález.')+'</p>'
            body+='<p>Aktualizace Watchmanu: '+escape(display_time(native['last_update_at'],zone))+'; poslední parsování: '+escape(display_time(native['last_parse_at'],zone))+'. Čas tohoto čtení není čas nového skenu.</p>'
            body+='<p>Chybějící entity: '+escape(str(native['counts'].get('missing_entities')) if native['counts'].get('missing_entities') is not None else 'nezjištěno')+'; akce: '+escape(str(native['counts'].get('missing_actions')) if native['counts'].get('missing_actions') is not None else 'nezjištěno')+'.</p>'
            if 'case_evidence_budget' in native['gaps']:body+='<p>Spis dosáhl limitu důkazů. Nové čtení pokračuje, ale historii je nutné řízeně exportovat a archivovat; chybějící uložený důkaz nesmí autorizovat opravu.</p>'
            body+='<ul>'+''.join('<li>'+escape(x['id'])+' ('+escape(x['state'])+'): '+escape('; '.join(p['file']+':'+','.join(map(str,p['lines'])) for p in x['locations']) or 'kontext umístění není dostupný')+'</li>' for x in native['findings'])+'</ul>'
            if native['incident_id']:body+='<p><a href="../case/'+escape(native['incident_id'],quote=True)+'">Otevřít společný diagnostický spis Watchmanu</a></p>'
            body+='<p>Zakázaná entita může být záměrná; odkazy ESPHome potřebují jiný kontext než entity HA. Nic automaticky nepřepisuji ani nezapínám.</p>'
        elif native and row['provider_id']=='zha_toolkit':
            body+='<p>Konkrétní čtení seznamu zařízení: '+('proběhlo, přečtených zařízení '+str(len(native['devices'])) if native['read_succeeded'] else 'neověřené')+'. Čtou se pouze údaje existující v paměti ZHA; jejich stáří určuje poslední komunikace zařízení.</p>'
            if native.get('version'):body+='<p>Verze uvedená v odpovědi Toolkitu: '+escape(native['version'])+'. Kompatibilitu fyzické instalace musí potvrdit skutečná čtení.</p>'
        if row['matching_repairs_count'] is not None:body+='<p>Nálezy se shodnou doménou v Repairs: '+str(row['matching_repairs_count'])+'. Nula neprokazuje zdravý doplněk.</p>'
        verified=actual_read or bool(native and (native.get('read_verified') or native.get('read_succeeded')))
        body+='<p>'+('Konkrétní čtecí odpověď byla ověřena. Funkční výsledek zařízení tím není potvrzený. ' if verified else 'HADS zatím neověřil vlastní diagnostiku doplňku. ')
        if row['provider_id'] in {'ha_mcp','hamster_mcp','music_assistant'}:
            body+='Katalog konektoru: '+('načtený' if current and tool.get('catalog_loaded') else 'neověřený')+'. Autentizace: '+('server přijal credential' if current and tool.get('authenticated') is True else 'nepotvrzená samostatná identita; podrobnosti připojení jsou v katalogu')+'. '
        body+='Tato kontrola nic nepovoluje k zápisu; konkrétní opravný plán vyžaduje samostatný souhlas.</p></article>'
    token='<input type="hidden" name="csrf" value="'+escape(csrf,quote=True)+'">'
    body+='<form method="post" action="provider-previous">'+token+'<p>Ze starého Hermes 2.0.0-rc3 lze přes Supervisor převzít pouze vybrané připojovací položky do neaktivního soukromého návrhu. Starou aplikaci kvůli tomu nespouštím ani neměním.</p><button>Načíst návrh připojení z původního Hermes RC3</button></form>'
    try:staged=', '.join(app.legacy_connectors.public_status()['staged_providers']) or 'žádné'
    except (OSError,ValueError,TypeError):staged='Soukromý návrh nelze bezpečně načíst.'
    return body+'<form method="post" action="check">'+token+'<button>Obnovit nativní ověření bez AI</button></form><p>HADS tato čtení provádí také při své pravidelné kontrole. Nevyvolává reporty ani změny v doplňcích.</p><details><summary>Přenést připojení ze starého Hermes RC3</summary><p>Soukromě uloží jen explicitní adresy a tokeny známých konektorů jako neaktivní návrh. Nepřenáší souhlasy, AI, důkazy úspěchu ani oprávnění. Samotný neaktivní návrh žádný adaptér neaktivuje. Vybrané připojení lze jednorázově aktivovat v Nástrojích servisního týmu; souhlasy s opravami se nepřenášejí. Výpis obrazovky není export nastavení. JSON vkládej pouze zde v soukromém HADS, nikoli do chatu nebo GitHubu.</p><p>Připravené konektory: '+escape(staged)+'</p><form method="post" action="provider-settings">'+token+'<label>JSON options předchozího HADS<textarea name="document" required maxlength="32768" autocomplete="off"></textarea></label><button>Uložit neaktivní návrh připojení</button></form></details><a href="../setup">Zdroje a připravenost</a>'
