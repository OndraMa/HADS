"""Shared responsive Czech UI; no remote assets or scripts."""
import re
from html import escape

from .command_center_style import STYLE

def page(content,path):
    prefix='../'*max(0,path.count('/')-1)
    content=re.sub(r'<!doctype[^>]*>|</?(?:html|head|body)[^>]*>|<title>.*?</title>|<style>.*?</style>','',content,flags=re.I|re.S)
    links=[('./','Domácnost'),('setup','Zdroje a připravenost'),('setup/monitors','Sledované funkce'),('setup/repair','Opravy'),('setup/history','Historie a migrace'),('setup/lighting','Světelné opravy'),('acceptance','Živá přejímka')]
    links.insert(2,('setup/tools','Nástroje servisního týmu'))
    links.insert(2,('setup/providers','Doplňky a ověření'))
    nav=''.join('<a href="'+prefix+href+'"'+(' aria-current="page"' if path in {'/','/index.html'} and href=='./' or path=='/'+href else '')+'>'+label+'</a>' for href,label in links)
    return '<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HADS Next</title><style>'+STYLE+'</style></head><body><header class="app-header"><a class="brand" href="'+prefix+'./"><span class="brand-mark" aria-hidden="true">H</span><strong>HADS Next</strong></a><small>Domácnost pod dohledem</small></header><nav class="main-nav" aria-label="Hlavní navigace">'+nav+'</nav><main>'+content+'</main></body></html>'


def repair_cards(app,identity,csrf):
    result=''
    for plan in app.repairs.plans(identity):
        d=plan['document']
        if d['operation']=='tool.approved':
            from .tool_ui import repair_card
            result+=repair_card(plan,csrf)
            continue
        native=d['operation']=='core.enable_lighting_automation'
        if native:original='Zapnutá' if d['original']['enabled'] else 'Vypnutá';proposed='Zapnutá' if d['proposed']['enabled'] else 'Vypnutá'
        else:original=d['original']['action']['target']['entity_id'];proposed=d['proposed']['action']['target']['entity_id']
        result+='<article><h3>Konkrétní opravný plán</h3><p>'+escape(original)+' → '+escape(proposed)+'</p><p>'+escape(d['reason'])+'</p><p>'+('Aktivace vybrané světelné automatizace nativní službou; konfigurace se nepřepisuje.' if native else 'Změna jediné vlastní virtuální testovací reference.')+'</p><p>'+escape(d['expected_result'])+'</p><p>Ověření vyžaduje skutečný spouštěč automatizace a '+str(d['verification']['watch_seconds'])+' sekund souvislého sledování. Snapshot není záloha HAOS.</p><details><summary>Přesný plán, rizika a záloha</summary><pre>'+escape(__import__('json').dumps(d,ensure_ascii=False,indent=2))+'</pre></details>'
        form='<input type="hidden" name="csrf" value="'+csrf+'"><input type="hidden" name="plan_id" value="'+plan['plan_id']+'">'
        if plan['status'] is None and plan.get('decision') in {'reject','manual'}:
            result+='<p>'+('Tento plán byl zamítnut. Nic nebylo vykonáno.' if plan['decision']=='reject' else escape(d['manual_alternative']))+'</p>'
        if plan['status'] is None:
            result+='<form method="post" action="../repair/decide">'+form+'<button name="decision" value="approve">Schválit opravu</button><button name="decision" value="reject">Zamítnout</button><button name="decision" value="manual">Zobrazit ruční postup</button></form>'
        else:
            labels={'verified':'Vyřešeno a ověřeno','applied_verification_pending':'Oprava provedena, ověření čeká','blocked_requires_review':'Výsledek zásahu není jistý; další zápisy jsou zastavené.','recurred':'Problém se opakoval','failed':'Oprava selhala','rollback_reference_restored':'Návrat reference ověřen; funkční problém zůstává.'}
            result+='<p class="badge">'+escape(labels.get(plan['status'],'Zásah vyžaduje kontrolu.'))+'</p><form method="post" action="../repair/rollback">'+form+'<button>Připravit samostatný návrat změny</button></form>'
        if native and plan['status']=='applied_verification_pending' and not d['rollback']['rollback_of']:
            result+='<form method="post" action="../repair/physical">'+form+'<p>Proveď skutečný trigger. Potom potvrď, že správné světlo reagovalo. Samotné potvrzení nenahrazuje kontext a sledovací dobu.</p><button>Potvrzuji skutečnou odezvu správného světla</button></form>'
        result+='</article>'
    return result
