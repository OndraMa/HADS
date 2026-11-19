"""Concrete Czech findings and repair boundaries, without raw diagnostics."""
from html import escape
from .dashboard import display_time


def render_context(app,case=None):
    rows=app.entity_context.reports(case)
    if not rows:return ''
    zone=app.snapshot()['timezone'];body='<section><h2>Co HADS zjistil o konkrétních cílech</h2>'
    labels={'unavailable':'Nedostupnost potvrzena čtením Core','unknown':'Hodnota není známá','disabled':'Entita je zakázaná',
            'missing':'Core potvrdil chybějící stav','state_available':'Aktuální stav je dostupný','unverified':'Čtení nebylo ověřené'}
    for row in rows:
        name=(row.get('registry') or {}).get('name') or row['entity_id']
        body+='<article><h3>'+escape(name)+'</h3><p>'+escape(row['entity_id'])+' — '+escape(labels[row['classification']])+'.</p><p>'+escape(row['summary_cs'])+'</p>'
        body+='<p>Poslední konkrétní čtení: '+escape(display_time(row['checked_at'],zone))+'.</p>'
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
