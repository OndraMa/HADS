"""Shared responsive Czech UI; no remote assets or scripts."""
import re
from html import escape

STYLE='''body{margin:0!important;background:#f2f5f8!important;color:#182838!important;overflow-wrap:anywhere;font:16px/1.55 system-ui,sans-serif!important;max-width:none!important;padding:0!important}header{background:#112c3c;color:#fff;padding:18px max(18px,calc((100vw - 1100px)/2));}header strong{font-size:24px}header small{display:block;color:#bdd9db}nav{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}nav a{background:#fff;color:#154d57;padding:8px 12px;border:1px solid #ccdce0;border-radius:8px;text-decoration:none}main{max-width:1100px;margin:0 auto;padding:24px 18px}h1{font-size:clamp(24px,4vw,34px);line-height:1.2}h2{margin-top:30px;font-size:22px}article,form,details,.panel{background:#fff;border:1px solid #d6e0e8;border-radius:12px;padding:18px;margin:14px 0;box-shadow:0 2px 6px #173a4d08}article h3{margin-top:0}label{display:block;margin:12px 0}input:not([type=checkbox]):not([type=hidden]),select,textarea{display:block;width:100%;box-sizing:border-box;border:1px solid #a7bbc8;border-radius:7px;padding:10px;font:inherit}input[type=checkbox]{width:auto!important}textarea{min-height:90px}button{font:inherit;background:#086b66;color:#fff;border:0;border-radius:7px;padding:10px 15px;margin:5px 8px 5px 0;cursor:pointer}button[name=decision][value=reject]{background:#7d3437}a{color:#08625d}pre{overflow:auto;max-height:420px;font-size:13px;background:#eef3f6;padding:12px;border-radius:7px;white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:600}.notice{border-left:4px solid #a97112;background:#fff5df;padding:14px;border-radius:8px}.badge{display:inline-block;background:#e3f2ef;color:#075f55;padding:3px 9px;border-radius:16px;font-size:14px}ul{padding-left:22px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}@media(max-width:600px){main{padding:16px 12px}article,form,details{padding:13px}button{width:100%;margin:6px 0}nav a{flex:1;text-align:center}table{display:block;overflow:auto}}'''

def page(content,path):
    prefix='../'*max(0,path.count('/')-1)
    content=re.sub(r'<!doctype[^>]*>|</?(?:html|head|body)[^>]*>|<title>.*?</title>','',content,flags=re.I|re.S)
    nav=''.join('<a href="'+prefix+href+'">'+label+'</a>' for href,label in [('./','Domácnost'),('setup','Zdroje a připravenost'),('setup/monitors','Sledované funkce'),('setup/repair','Opravy'),('setup/history','Historie a migrace'),('setup/lighting','Světelné opravy'),('acceptance','Živá přejímka')])
    return '<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HADS Next</title><style>'+STYLE+'</style></head><body><header><strong>HADS Next</strong><small>Diagnostika, důkazy a bezpečně schvalované kroky</small></header><main><nav>'+nav+'</nav>'+content+'</main></body></html>'


def repair_cards(app,identity,csrf):
    result=''
    for plan in app.repairs.plans(identity):
        d=plan['document'];native=d['operation']=='core.enable_lighting_automation'
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
