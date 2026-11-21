"""Concrete Czech findings and repair boundaries, without raw diagnostics."""
from html import escape
from .dashboard import display_time


def render_context(app,case=None):
    rows=app.entity_context.reports(case)
    if not rows:return ''
    zone=app.snapshot()['timezone'];body='<section><h2>Co HADS zjistil o konkrétních cílech</h2>'
    labels={'unavailable':'Nedostupnost potvrzena čtením Core','unknown':'Hodnota není známá','disabled':'Entita je zakázaná',
            'missing':'Core potvrdil chybějící stav','state_available':'Aktuální stav je dostupný','unverified':'Čtení nebylo ověřené'}
    inventory_labels={'available':'Poskytuje stav','unavailable':'Nedostupná','unknown':'Hodnota neznámá',
                      'disabled':'Zakázaná','missing':'Chybí v seznamu stavů Core','unverified':'Čtení stavů neověřeno'}
    for row in rows:
        name=(row.get('registry') or {}).get('name') or row['entity_id']
        body+='<article><h3>'+escape(name)+'</h3><p>'+escape(row['entity_id'])+' — '+escape(labels[row['classification']])+'.</p><p>'+escape(row['summary_cs'])+'</p>'
        body+='<p>Poslední konkrétní čtení: '+escape(display_time(row['checked_at'],zone))+'.</p>'
        device=app.entity_context.device_context(row['entity_id'])
        if device:
            heading=device['name'] or 'Zařízení podle registru entit'
            body+='<h4>'+escape(heading)+'</h4>'
            if device['device_confirmed']:
                body+='<p><a href="/config/devices/device/'+escape(device['device_id'],quote=True)+'" target="_blank" rel="noopener noreferrer">Otevřít zařízení v Home Assistantu</a></p>'
            body+='<p>Entity přiřazené ke stejnému zařízení · '+escape(display_time(device['checked_at'],zone))+'.</p><ul>'
            for related in device['entities']:
                identity=escape(related['entity_id'])
                label=escape(related['name'])+' · ' if related['name']!=related['entity_id'] else ''
                affected=' <strong>(hlášená entita)</strong>' if related['entity_id']==row['entity_id'] else ''
                body+='<li>'+label+'<code>'+identity+'</code>'+affected+' · '+inventory_labels[related['status']]+'</li>'
            body+='</ul>'
            if device['total']>len(device['entities']):
                body+='<p>Zobrazeno '+str(len(device['entities']))+' z '+str(device['total'])+' entit.</p>'
        else:
            body+='<p>V aktuálním registru se nepodařilo potvrdit přiřazení této entity k zařízení.</p>'
        if 'case_evidence_budget' in row['gaps']:body+='<p>Spis dosáhl limitu důkazů. Aktuální čtení pokračuje, ale nový podklad není plně uložený; nesmí autorizovat opravu. Historii je nutné řízeně exportovat a archivovat.</p>'
        for key, label in (('zha', 'ZHA'), ('toolkit', 'ZHA Toolkit')):
            radio = row.get(key)
            if radio:
                lqi = escape(str(radio['lqi'])) if radio.get('lqi') is not None else 'nezjištěno'
                rssi = escape(str(radio['rssi'])) if radio.get('rssi') is not None else 'nezjištěno'
                body += ('<p><strong>'+label+'</strong> · Poslední komunikace '+escape(display_time(radio.get('last_seen'),zone))
                         +' · LQI '+lqi+' · RSSI '+rssi+'</p>')
        if row.get('zha') or row.get('toolkit'):
            body += '<p>Obě čtení vycházejí ze ZHA a mohou sdílet stejné měření. Čas komunikace ani signál sám neurčuje příčinu výpadku.</p>'
        body+='<p><strong>Další krok:</strong> '+escape(row['next_test_cs'])+'</p><p><strong>Oprava ke schválení:</strong> '+escape(row['repair']['reason_cs'])+'</p></article>'
    return body+'</section>'
