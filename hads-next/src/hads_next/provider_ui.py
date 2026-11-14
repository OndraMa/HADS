"""Czech provider verification view. No credentials or raw provider payloads."""
from html import escape
from .dashboard import display_time

def render_providers(app, csrf):
    rows=app.providers.snapshot();zone=app.snapshot()['timezone']
    body='<h1>Doplňky a skutečné ověření</h1><p>Instalace, běžící proces a přečtený stav jsou různé důkazy. Žádný z nich sám nepotvrzuje funkci celého diagnostického nástroje.</p>'
    if not rows:body+='<p>Aktuální kontrola dosud neproběhla. Historický výpis předchozího HADS ji nenahrazuje.</p>'
    for row in rows:
        body+='<article><h2>'+escape(row['title'])+'</h2><p>'+escape(row['summary_cs'])+'</p>'
        body+='<p>Poslední čtení: '+escape(display_time(row['checked_at'],zone))+(' — výsledek je starší než 10 minut.' if row['stale'] else '')+'</p>'
        if row['last_error']:body+='<p>'+escape(row['last_error'])+'</p>'
        body+='<p>Načtené komponenty: '+escape(', '.join(row['matched_components']) or 'nepotvrzené')+'. Vlastní entitní záznamy: '+str(row['owned_entity_count'])+'.</p>'
        for item in row['applications']:
            label={'started':'běží','stopped':'zastavená','error':'hlásí chybu','failed':'hlásí chybu','startup':'startuje'}.get(item['state'],'stav neověřený')
            body+='<p>Aplikace '+escape(item['slug'])+': '+label+'; verze '+escape(item['version'] or 'neověřená')+'. Proces není funkční test.</p>'
        if row['samples']:
            body+='<ul>'+''.join('<li>'+escape(x['entity_id'])+': '+escape(str(x['state']) if x['state'] is not None else 'soukromý nebo nepodporovaný text vynechán')+'; změna stavu '+escape(display_time(x['source_updated_at'],zone))+'</li>' for x in row['samples'])+'</ul><p>Čas změny entity není důkaz nového skenu doplňku.</p>'
        if row['matching_repairs_count'] is not None:body+='<p>Nálezy se shodnou doménou v Repairs: '+str(row['matching_repairs_count'])+'. Nula neprokazuje zdravý doplněk.</p>'
        body+='<p>Vlastní funkční kontrakt: neověřený. '+('MCP autentizace a katalog: neověřené. ' if row['provider_id'] in {'ha_mcp','hamster_mcp','music_assistant'} else '')+'Zapisovací opravy: nepovolené.</p></article>'
    token='<input type="hidden" name="csrf" value="'+escape(csrf,quote=True)+'">'
    body+='<form method="post" action="provider-previous">'+token+'<p>Ze starého Hermes 2.0.0-rc3 lze přes Supervisor převzít pouze vybrané připojovací položky do neaktivního soukromého návrhu. Starou aplikaci kvůli tomu nespouštím ani neměním.</p><button>Načíst návrh připojení z původního Hermes RC3</button></form>'
    try:staged=', '.join(app.legacy_connectors.public_status()['staged_providers']) or 'žádné'
    except (OSError,ValueError,TypeError):staged='Soukromý návrh nelze bezpečně načíst.'
    return body+'<form method="post" action="check">'+token+'<button>Obnovit nativní ověření bez AI</button></form><p>HADS tato čtení provádí také při své pravidelné kontrole. Nevyvolává reporty ani změny v doplňcích.</p><details><summary>Přenést připojení ze starého Hermes RC3</summary><p>Soukromě uloží jen explicitní adresy a tokeny známých konektorů jako neaktivní návrh. Nepřenáší souhlasy, AI, důkazy úspěchu ani oprávnění. Tento návrh zatím žádný adaptér neaktivuje; další přejímka a zapojení čekají. Výpis obrazovky není export nastavení. JSON vkládej pouze zde v soukromém HADS, nikoli do chatu nebo GitHubu.</p><p>Připravené konektory: '+escape(staged)+'</p><form method="post" action="provider-settings">'+token+'<label>JSON options předchozího HADS<textarea name="document" required maxlength="16000" autocomplete="off"></textarea></label><button>Uložit neaktivní návrh připojení</button></form></details><a href="../setup">Zdroje a připravenost</a>'
