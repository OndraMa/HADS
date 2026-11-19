"""Owner setup and review UI for actual orchestrated functions, not counters."""
import json
from html import escape
from .tool_connections import KINDS
from .dashboard import display_time


def settings(app,csrf):
    token='<input type="hidden" name="csrf" value="'+escape(csrf,quote=True)+'">'
    body='<h1>Nástroje servisního týmu</h1><p>HADS sám vybírá diagnostická čtení. Připojení není schválení opravy. Adresy ani tokeny se nezobrazují v katalogu, důkazech nebo Hermesu.</p>'
    if app.tools.connections.load_error:body+='<p>'+escape(app.tools.connections.load_error)+'</p>'
    configured = {row['provider']: row for row in app.tools.connections.public()}
    if app.snapshot()['source_job']['state'] == 'running':
        body += '<p role="status">Probíhá čtecí kontrola. <a href="tools">Obnovit výsledek</a></p>'
    for provider in app.tools.registry.providers():
        tools=[r for r in app.tools.registry.tools() if r['provider']==provider['id']]
        body+='<article><h2>'+escape(provider['id'])+'</h2><p>Verze: '+escape(str(provider.get('version') or 'neověřená'))+'; původ: '+escape(str(provider.get('version_basis','neověřeno')))+'</p>'
        labels={'installed':'Nainstalováno','running':'Běží','connected':'Připojeno','authenticated':'Autentizováno','catalog_loaded':'Katalog načten','diagnostic_read_verified':'Vlastní diagnostická odpověď přečtená'}
        if provider['id'] in KINDS:
            connection = configured.get(provider['id'])
            if connection:
                body += '<p>Soukromé nastavení je uloženo. Diagnostické připojení je '+('povolené' if connection['enabled'] else 'vypnuté')+'.</p>'
        body+='<ul>'+''.join('<li>'+label+': '+('ano' if provider.get(key) is True else 'ne' if provider.get(key) is False else 'neověřeno / rozhraní bez vlastní autentizace')+'</li>' for key,label in labels.items())+'</ul>'
        if provider.get('diagnostic_read_at') is not None:
            body+='<p>Poslední konkrétní diagnostické čtení: '+escape(display_time(provider['diagnostic_read_at'],app.snapshot()['timezone']))+'. Obnovení katalogu tento čas neposouvá.</p>'
        if provider.get('last_error'):body+='<p>'+escape(provider['last_error'])+'</p>'
        if provider.get('last_used_at') is not None:
            body+='<p>Data byla použita ve spisu <a href="../case/'+escape(provider['last_used_incident'],quote=True)+'">otevřít případ</a>. Čas čtení není novým nezávislým potvrzením.</p>'
        body+='<p>Čas vlastního reportu: '+('zdroj jej v tomto čtení nedoložil' if provider.get('source_data_at') is None else escape(display_time(provider['source_data_at'],app.snapshot()['timezone'])))+'.</p>'
        body+='<details><summary>Skutečné funkce a jejich omezení</summary><ul>'+''.join('<li>'+escape(t['name'])+' — '+escape(t['effect'])+', '+escape(t['policy'])+(' — opravný adaptér implementovaný, každý plán vyžaduje zvláštní souhlas' if t['repair_operation_implemented'] else '')+'</li>' for t in tools)+'</ul></details></article>'
    body+='<h2>Jednorázové připojení</h2><p>Inspector a HADocs se HADS pokusí připojit přes ověřený inventář Supervisoru a jejich doložený interní port. Ostatní MCP endpointy nastav zde nebo aktivuj vybraný starý návrh. Nepřidávej k Hermesu neomezený shell nebo obecný MCP přístup.</p>'
    body+='<form method="post" action="tool-connection">'+token+'<label>Poskytovatel<select name="provider">'+''.join('<option>'+p+'</option>' for p in KINDS)+'</select></label><label>Privátní adresa serveru (skrytá stejně jako token)<input name="url" type="password" required autocomplete="new-password" spellcheck="false"></label><label>Token pouze pokud jej skutečný server vyžaduje<input name="token" type="password" autocomplete="new-password"></label><p>U adresy s tajnou cestou obvykle stačí samotná adresa. HADS žádný další token neodhaduje. OAuth zde není podporovaný.</p><label><input type="checkbox" name="private_http" value="yes">Výslovně povoluji HTTP pouze uvnitř soukromé sítě HA</label><label><input type="checkbox" name="enabled" value="yes" checked>Povolit diagnostické připojení</label><button>Uložit a ověřit připojení bez AI a bez oprav</button></form>'
    for p in app.legacy_connectors.public_status()['staged_providers']:
        if p in KINDS:body+='<form method="post" action="tool-activate">'+token+'<input type="hidden" name="provider" value="'+escape(p,quote=True)+'"><button>Aktivovat pouze připravené připojení '+escape(p)+'</button></form>'
    return body+'<p>Rizikové registry/konfigurační změny vyžadují nezávislý podepsaný důkaz obnovení OneDrive zálohy. Chybějící důkaz nelze nahradit přepínačem ani textem AI.</p>'


def repair_card(plan,csrf,app=None):
    d=plan['document'];form='<input type="hidden" name="csrf" value="'+escape(csrf,quote=True)+'"><input type="hidden" name="plan_id" value="'+plan['plan_id']+'">'
    body='<article><h3>Oprava pomocí '+escape(d['binding']['provider'])+'</h3><p>'+escape(d['reason'])+'</p><p>Nástroj: '+escape(d['binding']['tool'])+'; cíl: '+escape(d['parameters']['entity_id'])+'</p><p>'+escape(d['expected_result'])+'</p><details><summary>Původní stav, přesná změna, důkazy, záloha, riziko a návrat</summary><pre>'+escape(json.dumps(d,ensure_ascii=False,indent=2))+'</pre></details>'
    if plan['status'] is None:
        body+='<form method="post" action="../tool-repair/decide">'+form+'<label><input type="checkbox" name="exclusive" value="yes" required>Potvrzuji výlučnou práci s tímto cílem; během zásahu jej jinde neupravuji.</label><button name="decision" value="approve">Schválit přesně tuto opravu</button><button name="decision" value="reject" formnovalidate>Zamítnout</button><button name="decision" value="manual" formnovalidate>Provést ručně</button></form>'
        if plan.get('decision')=='manual':body+='<p>'+escape(d['manual_alternative'])+'</p>'
    else:
        labels={'applied_verification_pending':'Oprava provedena, ověření čeká','verified':'Vyřešeno a ověřeno','failed':'Oprava selhala','recurred':'Problém se opakoval','unknown_requires_reconciliation':'Výsledek zápisu není jistý. Další zásahy jsou zastavené; HADS smí jen znovu přečíst stav.','tool_intent':'Zásah je rozpracovaný; neopakuje se.','rollback_reference_restored':'Návrat konfigurace ověřen; funkční výsledek se posuzuje zvlášť.'}
        body+='<p>Výsledek zásahu: '+escape(labels.get(plan['status'],'Zásah vyžaduje kontrolu uložených důkazů.'))+'</p>'
        if plan['status']=='unknown_requires_reconciliation' and app is not None:
            recovery=app.repair_recovery.status(plan['plan_id'])
            body+='<form method="post" action="../tool-repair/recheck">'+form+'<p>Automatická kontrolní čtení jsou omezená. Po obnovení přístupu nebo ruční změně může vlastník nejvýše jednou za minutu vyžádat nové čtení. Původní příkaz se tím neopakuje.</p><button>Znovu ověřit nejistý výsledek bez zápisu</button></form>'
            if recovery and recovery.get('read_verified'):
                body+='<p>HADS znovu přečetl cíl. '+('Stav odpovídá schválené změně; původ zápisu ale není potvrzený.' if recovery.get('matches_proposed') else 'Aktuální stav neodpovídá schválené změně. Další zápis je zastavený.')+'</p>'
                if recovery.get('matches_proposed') and recovery.get('target_identity_matches'):
                    body+='<form method="post" action="../tool-repair/adopt">'+form+'<p>Tato volba nic nezapisuje do HA. Začne nové funkční ověření s aktuálním stavem.</p><button>Přijmout zjištěný stav a ověřit funkci bez dalšího zápisu</button></form>'
        if plan['status']=='applied_verification_pending' and not d['rollback']['rollback_of']:body+='<form method="post" action="../repair/physical">'+form+'<p>Proveď skutečný funkční test popsaného cíle; HADS sleduje nové důkazy a dobu ověření.</p><button>Potvrzuji skutečnou odezvu správného cíle</button></form>'
        elif plan['status']=='applied_verification_pending':body+='<p>HADS ověřuje návrat konfigurace čtením; tento krok nepotvrzuje vyřešení funkčního problému.</p>'
        if plan['status'] in {'applied_verification_pending','verified','failed','recurred'}:body+='<form method="post" action="../tool-repair/rollback">'+form+'<label><input type="checkbox" name="exclusive" value="yes" required>Cíl nyní nikdo jiný neupravuje.</label><button>Připravit návrat změny k novému schválení</button></form>'
    return body+'</article>'
