"""Read-only presentation of existing cases, observations and owner decisions."""
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo
from .health_cases import diagnostic_observation,health_domain

GENERIC_APP_SYMPTOM='Aplikace hlásí neúspěšný běh.'


def application_name(case, applications):
    names={row['slug']:row['name'] for row in applications}
    components=[x for x in case.get('components',[]) if x!='supervisor']
    return next((names[x] for x in components if x in names),components[0] if components else 'Neurčená aplikace')


def case_title(case, applications):
    if case.get('kind')=='integration_repair' and health_domain(case):return health_domain(case)+': požadavek Home Assistantu na opravu'
    if case.get('kind')=='system_resource_pressure' and 'hads_runtime' in case.get('components',[]):return 'Pro spuštění Hermes chyběla paměť'
    if case.get('kind')=='system_health_failure':
        domain=health_domain(case)
        return ('Marketplace' if domain=='marketplace' else domain or 'Integrace')+': neúspěšná diagnostická kontrola'
    if case.get('kind')!='application_failure':return case['symptom']
    name=application_name(case,applications)
    if case['symptom']==GENERIC_APP_SYMPTOM:return name+' potřebuje kontrolu'
    return name+': '+case['symptom']


def application_observation(case):
    # Legacy auto-created cases keep their evidence and identity. A Supervisor
    # status alone does not establish expected running or functional impact.
    return case.get('kind')=='application_failure' and str(case.get('correlation_key') or '').startswith('health:app:') and case.get('status')!='resolved'


def case_summary(case):
    if application_observation(case):return 'Stav aplikace sám nepotvrzuje funkční poruchu. Může souviset i se záměrným zastavením; očekávaný běh a dopad zatím nejsou doložené.'
    if case.get('kind')=='system_resource_pressure' and 'hads_runtime' in case.get('components',[]):
        return 'Naměřená paměť nestačila pro bezpečné spuštění AI. Místní diagnostika pokračuje. Tento nález sám nevysvětluje chyby jiných aplikací.'
    return {
        'application_failure':'Je zaznamenaná chyba běhu aplikace. Příčinu a dopad na domácnost je ještě potřeba ověřit.',
        'source_unavailable':'Některý zdroj nelze přečíst. To samo neprokazuje poruchu zařízení.',
        'system_health_failure':'Neprošla diagnostická kontrola integrace. Příčina a dopad na funkce domácnosti nejsou doložené. Konkrétní kontrola a další postup jsou ve spisu.',
        'automation_disabled':'Automatizace, která má být podle vlastníka zapnutá, je vypnutá.',
        'integration_repair':'Home Assistant požaduje kontrolu integrace. Podrobnosti jsou ve spisu.',
        'automation_reference':'Automatizace odkazuje na entitu bez doloženého aktuálního stavu.',
        'manual_functional':'Uživatelem nahlášený problém čeká na ověření dostupnými důkazy.',
    }.get(case.get('kind'),'Je zaznamenaný problém. Ověřené důkazy a další postup najdeš ve spisu.')


def plural_findings(count):
    if count==1:return '1 systémový nález ke kontrole'
    if 2<=count<=4:return str(count)+' systémové nálezy ke kontrole'
    return str(count)+' systémových nálezů ke kontrole'


def display_time(value,zone):
    try:return datetime.fromtimestamp(value,ZoneInfo(zone)).strftime('%d. %m. %Y v %H:%M')
    except (ValueError,TypeError,OverflowError,OSError,KeyError):return 'Čas není dostupný'


def render_dashboard(app,csrf):
    value=app.snapshot();cases=value['cases'];applications=value['applications'];core=value['core'];health=value['system_health']
    provider=value['investigation_service']['provider'];runtime=value['investigation_service']
    jobs={c['id']:app.investigations.for_case(c['id']) for c in cases}
    plans={c['id']:app.repairs.plans(c['id']) for c in cases}
    observations=[c for c in cases if application_observation(c) and c['status']=='open' and not plans[c['id']]]
    observation_ids={c['id'] for c in observations}
    diagnostics=[c for c in cases if diagnostic_observation(c) and c['status']=='open' and not plans[c['id']]]
    diagnostic_ids={c['id'] for c in diagnostics}
    historical=[c for c in diagnostics if (app.system.followup.report(c['id']) or {}).get('state')=='check_passed']
    historical_ids={c['id'] for c in historical}
    diagnostics=[c for c in diagnostics if c['id'] not in historical_ids]
    grouped=app.orchestration.grouped_children() if hasattr(app,'orchestration') else set()
    opened=[c for c in cases if c['status']=='open' and c['id'] not in observation_ids|diagnostic_ids|grouped]
    resolved=[c for c in cases if c['status']=='resolved']
    recurring=[c for c in cases if c['occurrence_count']>1 and c['id'] not in observation_ids|diagnostic_ids|grouped]
    waiting=[c for c in cases if c['id'] not in observation_ids and (any((p['status'] is None and p.get('decision') not in {'reject','manual'}) or p['status']=='applied_verification_pending' for p in plans[c['id']]) or jobs[c['id']] and jobs[c['id']][0]['state']=='waiting_for_user' and jobs[c['id']][0]['conclusion'] and provider['enabled'] and runtime['runtime_installed'])]
    active=sum(bool(jobs[c['id']] and jobs[c['id']][0]['state']=='investigating') for c in cases)
    esc=lambda x:escape(str(x),quote=True)
    def card(c):
        latest=jobs[c['id']][0] if jobs[c['id']] else None
        job_labels={'investigating':'Probíhá čtecí vyšetřování','waiting_for_user':'Potřebuje tvou součinnost','waiting_for_source':'Čeká na další důkazy','blocked':'Další vyšetřování potřebuje kontrolu','hypothesis_ready':'Pracovní závěr je připravený'}
        label='Vyřešeno a ověřeno' if c['status']=='resolved' else job_labels.get(latest['state'],'Čeká na vyšetření') if latest else 'Čeká na vyšetření'
        if c['id'] in observation_ids and not latest:label='Stav bez potvrzeného dopadu'
        if c['status']=='open' and c['kind']=='system_resource_pressure' and 'hads_runtime' in c['components']:label='Rezerva pro AI nebyla splněná'
        summary='Funkční ověření potvrdilo výsledek. Podrobnosti jsou v reportu.' if c['status']=='resolved' else case_summary(c)
        context=app.entity_context.reports({'incident':c,'evidence':[]})
        if context:summary=context[0]['summary_cs']
        automatic=app.system.automatic.report(c['id']) if c['id'] in diagnostic_ids else None
        followup=app.system.followup.report(c['id']) if c['id'] in diagnostic_ids else None
        if followup and (not latest or not provider['enabled']):
            summary=followup['summary_cs']
            label={'still_failing':'Znovu přečteno; nález trvá','check_passed':'Kontrola již nález nepotvrzuje','unavailable':'Další čtení je neúplné'}[followup['state']]
        if automatic:
            summary=(summary+' ' if followup else '')+automatic['summary_cs']
            if not followup:label='HADS sbírá další důkazy' if automatic['state']=='reading' else 'Automatické čtení dokončeno s omezením' if automatic['gaps'] else 'Důkazy automaticky načtené'
        return '<article class="case-card"><div class="case-top"><span class="case-kind">'+('Aplikace HAOS' if c['kind']=='application_failure' else 'Diagnostická kontrola' if c['kind']=='system_health_failure' else 'Prostředky pro AI' if c['kind']=='system_resource_pressure' and 'hads_runtime' in c['components'] else 'Zachycený případ')+'</span><span class="badge">'+esc(label)+'</span></div><h3>'+esc(case_title(c,applications))+'</h3><p>'+esc(summary)+'</p><div class="case-footer"><span>Výskytů: '+str(c['occurrence_count'])+' · '+esc(display_time(c['last_seen'],value['timezone']))+'</span><a href="case/'+esc(c['id'])+'">Otevřít důkazy spisu <span aria-hidden="true">→</span></a></div></article>'
    def cards(rows,empty):return ''.join(card(c) for c in rows) if rows else '<div class="empty-state">'+esc(empty)+'</div>'
    findings=health['active_findings']
    health_message='Systémová kontrola ještě neproběhla.' if health['last_check_at'] is None else plural_findings(findings) if findings else 'Poslední kontrola nezachytila aktivní systémový nález.'
    source_count=sum(bool(v.get('read_succeeded')) for v in value['sources'].values());source_total=len(value['sources'])
    source_text=str(source_count)+' z '+str(source_total)+' zdrojů přečteno' if source_total else 'Čtení zdrojů zatím není ověřené'
    ai_text=('Probíhá '+str(active)+' čtecí vyšetřování.' if active else 'AI je povolená. Žádné vyšetřování právě neběží.') if provider['enabled'] else 'AI je vypnutá. Sběr důkazů a místní diagnostika pokračují.'
    if provider['enabled'] and provider.get('mode')=='trial':ai_text='Testovací AI má samostatný omezený rozpočet a spouští se pouze výslovně pro vybraný případ. Nativní čtení HADS provádí automaticky bez placeného modelu.'
    if provider['enabled'] and not runtime['runtime_installed']:ai_text='Poskytovatel je povolený, ale runtime Hermes není dostupný. AI vyšetřování nemůže běžet.'
    elif provider['enabled'] and runtime['runtime_probe']['state']!='ready':ai_text+=' Kontrola runtime zatím nepotvrdila připravenost.'
    tiles=''.join('<a class="metric" href="#'+anchor+'"><span>'+label+'</span><strong>'+str(count)+'</strong><small>'+detail+'</small></a>' for anchor,label,count,detail in [('investigation','Otevřené funkční případy',len(opened),'Zachycené problémy'),('waiting','Čeká na tebe',len(waiting),'Souhlas nebo další test'),('resolved','Ověřené výsledky',len(resolved),'Potvrzená funkce'),('recurring','Opakované závady',len(recurring),'Více než jeden výskyt')])
    body='<div class="page-heading"><div><p class="eyebrow">PŘEHLED DOMÁCNOSTI</p><h1>Co se děje u tebe doma</h1><p class="muted">Důležité problémy, průběh vyšetřování a ověřené výsledky na jednom místě.</p></div><span class="connection '+('connected' if core['available'] else '')+'">'+('Core čtení funguje' if core['available'] else 'Čtení Core není ověřené')+'</span></div>'
    body+='<div class="health-strip"><div><strong>'+esc(health_message)+'</strong><p>Nejde o celkové hodnocení zdraví domácnosti. Nepřečtené zdroje zůstávají neověřené.</p></div><a href="setup">'+esc(source_text)+' →</a></div><div class="metrics">'+tiles+'</div>'
    if len(cases)==50:body+='<p class="muted">Přehled zobrazuje posledních 50 spisů; počty se vztahují k této zobrazené sadě.</p>'
    body+='<div class="overview-grid"><section id="investigation"><div class="section-heading"><div><p class="eyebrow">PROBLÉMY A VYŠETŘOVÁNÍ</p><h2>Co nefunguje</h2></div><span class="count">'+str(len(opened))+'</span></div>'+cards(opened,'Zatím tu není otevřený případ. To samo o sobě nepotvrzuje, že všechny funkce domácnosti fungují.')+'</section><aside><section id="waiting"><p class="eyebrow">DALŠÍ KROK</p><h2>Co ode mě potřebuje</h2>'+cards(waiting,'Žádná čekající rozhodnutí.')+'</section><section class="assistant-panel"><span class="badge">VYŠETŘOVÁNÍ</span><h2>Jak právě pracuje HADS</h2><p>'+esc(ai_text)+'</p><a href="setup/ai">Nastavení AI →</a><p class="muted">Povolení AI a případných nákladů je samostatné rozhodnutí. Návrh opravy sám nic nemění.</p></section></aside></div>'
    if observations:body+='<details id="application-observations"><summary>Stavy aplikací k ověření ('+str(len(observations))+')</summary><p>Tyto údaje nepočítám jako potvrzené funkční problémy. Samotný stav error může následovat i po záměrném zastavení. Evidence zůstává uložená a není označená jako vyřešená.</p>'+cards(observations,'')+'</details>'
    if diagnostics:body+='<section id="diagnostic-observations"><h2>Diagnostika a připravenost ('+str(len(diagnostics))+')</h2><p>Tyto nálezy vyžadují prověření nebo omezují HADS. Samy nepotvrzují poruchu funkce domácnosti. Spisy a důkazy zůstávají otevřené.</p>'+cards(diagnostics,'')+'</section>'
    if historical:body+='<details id="historical-diagnostics"><summary>Dřívější diagnostické nálezy ('+str(len(historical))+')</summary><p>Poslední kontrola je už nepotvrzuje. Důkazy zůstávají zachované; není to potvrzení provedené a funkčně ověřené opravy.</p>'+cards(historical,'')+'</details>'
    body+='<div class="results-grid"><section id="resolved"><p class="eyebrow">POTVRZENÁ NÁPRAVA</p><h2>Co se podařilo vyřešit</h2>'+cards(resolved,'Dosud žádný ověřený výsledek. Pouhý úspěch příkazu případ neuzavírá.')+'</section><section id="recurring"><p class="eyebrow">DLOUHODOBÉ SOUVISLOSTI</p><h2>Co se opakuje</h2>'+cards(recurring,'Zatím nejsou opakované případy. Stejné načtení důkazu se nepočítá znovu.')+'</section></div>'
    entities=''.join('<option value="'+esc(e['entity_id'])+'">'+esc(e.get('name',e['entity_id']))+'</option>' for e in value['entities'])
    apps=''.join('<option value="'+esc(a['slug'])+'">'+esc(a['name'])+'</option>' for a in applications)
    token='<input type="hidden" name="csrf" value="'+esc(csrf)+'">'
    body+='<section id="report" class="report-panel"><div class="section-heading"><div><p class="eyebrow">NĚCO NEFUNGUJE?</p><h2>Nahlásit problém</h2><p>Popiš, co se stalo. HADS uloží čas a přečte dostupné důkazy.</p></div></div><form method="post" action="incident">'+token+'<label>Co se stalo?<textarea name="symptom" maxlength="1000" required placeholder="Rádio se právě samo vypnulo."></textarea></label><div class="form-grid"><label>Kdy? Volitelné, časové pásmo '+esc(value['timezone'])+'<input type="datetime-local" name="occurred_at"></label><label>Dotčená entita<input name="entity_id" list="entities" maxlength="200" required placeholder="media_player.radio"></label></div><datalist id="entities">'+entities+'</datalist><button>Uložit incident a přečíst historii</button></form></section>'
    body+='<details><summary>Vyšetřit konkrétní aplikaci HAOS</summary><form method="post" action="incident/app">'+token+'<label>Aplikace<select name="slug" required>'+apps+'</select></label><label>Co nefunguje?<input name="symptom" required maxlength="1000"></label><button>Načíst stav, statistiky a protokol aplikace</button></form></details>'
    body+='<details><summary>Technický stav čtení a verze</summary><p>Vývojová verze '+esc(value['version'])+'. Načtených entit: '+str(core['entity_count'])+'. Živá přejímka ještě není dokončená. Hermes vyžaduje izolovaný runtime a výslovně povoleného poskytovatele AI. Obecné zásahy jsou zakázané. Každý podporovaný opravný plán potřebuje samostatné schválení.</p><p>'+esc(core.get('last_error') or 'Poslední čtení Core nehlásí chybu.')+'</p><a href="setup">Zkontrolovat jednotlivé zdroje</a><form method="post" action="read">'+token+'<button>Obnovit čtení Core</button><p>Nejvýše jednou za minutu.</p></form></details>'
    return body
