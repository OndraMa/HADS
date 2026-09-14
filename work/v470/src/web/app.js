'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = value => value ? new Date(value).toLocaleString('cs-CZ') : 'neověřeno';
const label = value => ({waiting_budget:'Čeká na AI rozpočet',verification_blocked:'Chybí funkční ověření',awaiting_decision:'Oprava čeká na schválení',approved:'Schválená oprava',review_ready:'Diagnostický závěr',investigating:'Vyšetřuje HADS',reinvestigate:'Nové vyšetření',watching:'Sledování bez opravy',verifying:'Oprava provedena / probíhá ověřování',manual_monitoring:'Ruční zásah',rejected:'Zamítnuto',ignored:'Ignorováno kapitánem',known_expected:'Očekávaný stav',deferred:'Odloženo',needs_information:'Potřebuje vaši informaci',resolved:'Uzavřeno',repair_failed:'Oprava selhala / přerušena',pending_approval:'Čeká na schválení',running:'Probíhá',monitoring:'Ověřuje se výsledek',failed:'Selhalo',interrupted:'Přerušeno restartem',cancelled:'Zrušeno',succeeded:'Požadavek dokončen',verification_pending:'Čeká na ověření',blocked_remote_verify:'Čeká na ověření rescue',blocked_conflict:'Konflikt plánů',partial_failure:'Část oprav selhala',preparing_rescue:'Příprava bezpečné dávky'})[value] || value;
let state = null, page = 'overview', detail = null, detailTab = 'summary', selectedPlan = null, loading = null, reloadAgain = false, detailSequence = 0;
const drafts = new Map();
window.hadsRequestDecision = requestDecision;
window.addEventListener('hads:webmcp-status',event=>{const value=event.detail||{};$('siteTools').textContent=`WebMCP: ${value.state==='ready'?'připraveno':value.state==='partial'?'částečně':'nepodporováno'}${value.detail?` · ${value.detail}`:''}`;});
function requestDecision(text,reasonRequired=false){
  return new Promise(resolve=>{
    const dialog=$('decisionDialog'),form=$('decisionForm'),input=$('decisionReason');
    if(dialog.open){resolve(null);return;}
    $('decisionTitle').textContent=reasonRequired?'Důvod rozhodnutí':'Potvrzení úkonu';
    $('decisionText').textContent=text;$('reasonLabel').hidden=!reasonRequired;
    input.required=reasonRequired;input.value='';
    const finish=value=>{form.onsubmit=null;dialog.oncancel=null;dialog.close();resolve(value);};
    form.onsubmit=event=>{event.preventDefault();if(event.submitter?.value==='cancel'){finish(null);return;}if(reasonRequired&&!input.value.trim()){input.setCustomValidity('Napište důvod rozhodnutí.');input.reportValidity();return;}finish(reasonRequired?input.value.trim():true);};
    input.oninput=()=>input.setCustomValidity('');input.setCustomValidity('');
    dialog.oncancel=event=>{event.preventDefault();finish(null);};dialog.showModal();
    if(reasonRequired)input.focus();
  });
}
function notify(text, error = false) { $('notice').textContent=text; $('notice').className='notice'+(error?' error':''); $('notice').hidden=false; clearTimeout(notify.timer); notify.timer=setTimeout(()=>$('notice').hidden=true,8500); }
async function api(path, options = {}) {
  const safe = !options.method || options.method === 'GET';
  const delays = safe ? [0,250,700] : [0];
  for (let i=0;i<delays.length;i++) {
    if(delays[i]) await new Promise(r=>setTimeout(r,delays[i]));
    try {
      const headers={'X-HADS4-Request':'captain',...(options.body?{'Content-Type':'application/json'}:{})};
      // All human text is UTF-8 JSON, never an HTTP header or query string.
      const response=await fetch(path,{...options,headers,signal:AbortSignal.timeout(safe?30000:90000)});
      const data=await response.json().catch(()=>({}));
      if(!response.ok){if(safe&&[502,503,504].includes(response.status)&&i<delays.length-1)continue;throw new Error(data.error||data.message||`Dočasně nedostupné (HTTP ${response.status})`);}
      return data;
    } catch(error){if(!safe||i===delays.length-1)throw error;}
  }
}
const post=(path,value={})=>api(path,{method:'POST',body:JSON.stringify(value)});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitForLogCollection(jobId){
  // A refreshed source row is not proof that the entire collection finished.
  for(let attempt=0;attempt<30;attempt++){
    await pause(1000);
    const result=await api(`api/log-sources/test?job_id=${encodeURIComponent(jobId)}`);
    if(result.status!=='running')return result;
  }
  return {status:'running',message:'Test stále běží. Stav zdrojů se obnovuje, dokončení zatím není potvrzeno.'};
}
function rootRows(rows, empty='V této části nejsou žádné případy.') {
  return rows.length?rows.map(r=>{const stateLabel=r.decision_state==='watching'&&r.state_origin==='automatic'?'Automatické sledování HADS':label(r.planner_state==='waiting_budget'?'waiting_budget':r.decision_state);return `<article class="case" data-hads-root="${r.id}" data-hads-public-id="${esc(r.public_id)}" data-hads-state="${esc(r.decision_state)}"><div><span class="badge ${esc(r.priority)}">${esc(r.priority)}</span><div class="muted">${esc(r.public_id)}</div></div><div><h3>${esc(r.title)}</h3><p>${esc(r.root_cause)}</p><div class="meta"><span>${esc(stateLabel)}</span><span>Příčina vyžaduje ověření</span><span>${esc(when(r.last_seen))}</span></div></div><div class="actions"><button data-root="${r.id}">Otevřít incident</button></div></article>`;}).join(''):`<div class="empty">${esc(empty)}</div>`;
}
function allRoots(){const seen=new Set();return ['repair_cases','conclusion_cases','investigating_cases','watching_cases','automatic_monitoring_cases','history_cases'].flatMap(k=>state[k]||[]).filter(r=>!seen.has(r.id)&&seen.add(r.id));}
function render(){
  if(!state)return;
  $('main').dataset.hadsPage=page;
  const h=state.health||{}, check=state.batch_checklist||{}, latest=state.latest_batch||{}, approved=state.approved_plans||0;
  $('connection').textContent=`Data panelu: ${when(state.updated_at)}`;
  const planner=state.planner_status||{};
  $('plannerStatus').textContent=`Průběžné vyšetřování: ${planner.periodic_enabled?'zapnuto':'vypnuto'}. Poslední dokončený cyklus: ${when(planner.finished_at)}; vyšetřeno ${planner.processed??'—'}, nové plány ${planner.created??'—'}, selhání ${planner.failed??'—'}, AI odložena kvůli limitu ${planner.ai_deferred??0}, zbývalo k vyšetření ${planner.remaining??'—'}. Čísla popisují poslední cyklus, ne právě běžící práci.`;
  document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('selected',b.dataset.page===page));
  $('launch').disabled=!check.runnable;
  $('launch').textContent=approved?`Spustit ${approved} schválené opravy`:'Spustit schválené opravy';
  $('batchTitle').textContent=approved?`${approved} oprav čeká na spuštění`:'Žádné schválené vykonatelné opravy';
  $('batchNote').textContent='Spuštění vytvoří rescue a novou plnou HA zálohu. Bez ověření zálohy se nic nezmění. Přijetí závěru není oprava.';
  if(['preparing_rescue','running'].includes(latest.status)){$('batchTitle').textContent=`Dávka B-${latest.id}: ${label(latest.status)}`;$('launch').disabled=true;}
  else if(latest.last_error){$('batchTitle').textContent=`Poslední dávka: ${label(latest.status)}`;$('batchNote').textContent=latest.last_error;}
  $('checklist').innerHTML=`<span>Vykonatelné plány v evidenci (včetně samostatných): <b>${check.executable_plans||0}</b></span><span>Schválené: <b>${approved}</b></span><span>Záloha: <b>povinná při spuštění</b></span><span>Rescue této dávky: <b>${check.rescue_ready?'ověřeno':'zatím ne'}</b></span><span>Zápis: <b>${check.write_gate==='unlocked'?'dávka probíhá':'zamčeno'}</b></span>`;
  if(page==='overview') {
    $('main').innerHTML=`<div class="section-head"><div><span class="eyebrow">VAŠE ROZHODNUTÍ, OVĚŘENÉ ZMĚNY</span><h2>Co skutečně potřebuje pozornost</h2></div><button data-action="analyze">Spustit hlubokou analýzu</button></div><p class="muted">Skóre vychází z dostupných důkazů. Není zárukou funkčnosti všech doplňků.</p><div class="cards">${[['Aktuální provoz',h.current_health],['Spolehlivost',h.reliability],['Pokrytí diagnostiky',h.coverage],['Zdraví HADS',h.hads_health]].map(([name,n])=>`<div class="card"><span class="score">${Number.isFinite(n)?n:'—'}<small>/100</small></span>${name}</div>`).join('')}</div><div class="cards"><div class="card"><h3>Připravené opravy</h3><span class="score">${(state.repair_cases||[]).length}</span><p>Změna má konkrétní plán. Nejprve zkontrolujte náhled.</p><button data-page="repairs">Otevřít opravy</button></div><div class="card"><h3>Vyšetřuje HADS</h3><span class="score">${state.investigating_count||0}</span><p>Nejsou to schválené opravy. Můžete doplnit informaci nebo rozporovat závěr.</p><button data-page="incidents">Otevřít incidenty</button></div></div><h3>K rozhodnutí</h3>${rootRows([...(state.repair_cases||[]),...(state.conclusion_cases||[])],'Nyní není připravený návrh vyžadující váš souhlas.')}<details><summary>Proč má HADS toto zdravotní skóre?</summary><div class="cards">${Object.values(h.hads_health_breakdown||{}).map(p=>`<div class="card"><h3>${esc(p.label)} · ${esc(p.score)}</h3><p>${esc(p.detail)}</p></div>`).join('')}</div></details>`;
  } else if(page==='incidents') {
    $('main').innerHTML=`<h2>Incidenty a vyšetřování</h2><p class="muted">Technická hláška je důkaz, ne sama o sobě potvrzená příčina. Stejný incident si zachová rozhodnutí i konverzaci.</p><h3>Vyšetřuje HADS</h3>${rootRows(state.investigating_cases||[])}<details open><summary>Přijaté závěry a ověřování oprav (${(state.watching_cases||[]).length})</summary>${rootRows(state.watching_cases||[])}</details><details><summary>Automatické sledování bez vašeho rozhodnutí (${(state.automatic_monitoring_cases||[]).length})</summary><p class="muted">HADS případ pouze drží v evidenci kvůli stáří nebo opakování. Nejde o vámi přijatý závěr a lze jej znovu vyšetřit.</p>${rootRows(state.automatic_monitoring_cases||[])}</details>`;
  } else if(page==='repairs') {
    $('main').innerHTML=`<h2>Opravy a zálohy</h2><p class="muted">Schválení zařadí konkrétní změnu do dávky. Spuštění je samostatný rozkaz v dolní liště.</p>${rootRows(state.repair_cases||[],'HADS zatím nemá připravený opravný plán. Přijetí diagnostického závěru jej nevytvoří.')}<div id="standalone">${(state.standalone_plans||[]).map(p=>`<article class="case"><span class="badge">#${p.id}</span><div><h3>${esc(p.title)}</h3><p>${esc(label(p.status))}</p></div><button data-plan="${p.id}">Náhled a schválení</button></article>`).join('')}</div><h3>Poslední dávka</h3><div class="card">${latest.id?`B-${latest.id} · ${esc(label(latest.status))}<p>${esc(latest.last_error||'Výsledek opravy se ověřuje následným sledováním.')}</p><div class="meta">${(latest.results||[]).map(r=>`<span>Plán #${r.plan_id}: ${esc(label(r.status))} · záloha ${esc(r.result?.backup?.slug||'nepotvrzena')}</span>`).join('')}</div>`:'Zatím nebyla spuštěna žádná dávka.'}</div><details><summary>Řízená údržba historie Recorderu</summary><div class="callout">Určeno pouze pro aktivní SQLite databázi s cestou potvrzenou v nastavení HADS. Externí SQL databáze ani obecné mazání souborů nejsou podporovány. Historie se nemaže kvůli samotné nečinnosti entity.</div><label>Počet dnů historie, které mají zůstat<input id="keepDays" type="number" min="1" max="3650" value="30"></label><button data-action="recorder">Připravit náhled údržby (nic nemaže)</button></details><details><summary>Pokročilý přesný opravný plán</summary><p>Pro ručně připravené allowlist akce. Náhled a nové schválení jsou povinné.</p><label>Název<input id="manualTitle"></label><label>Akce jako JSON pole<textarea id="manualActions" placeholder='[{"type":"yaml_replace","path":"automations.yaml","before":"původní blok","after":"nový blok"}]'></textarea></label><button data-action="manualPlan">Připravit náhled</button></details>`;
  } else if(page==='sources') renderSources();
  else $('main').innerHTML=`<h2>Historie a ignorované případy</h2><p class="muted">Ignorování je rozhodnutí kapitána, nikoli důkaz zdravého systému. Je omezeno na tento incident; kdykoli ho lze znovu otevřít.</p>${rootRows(state.history_cases||[])}<h3>Opravné plány a výsledky (nejvýše 300)</h3>${(state.plan_history||[]).map(p=>`<article class="case"><span class="badge">#${p.id}</span><div><h3>${esc(p.title)}</h3><div class="meta"><span>${esc(label(p.status))}</span><span>${esc(when(p.updated_at))}</span><span>Záloha: ${esc(p.backup_slug||'zatím nepotvrzena')}</span></div>${p.last_error?`<p class="bad">${esc(p.last_error)}</p>`:''}</div><button data-plan="${p.id}">Otevřít plán a výsledek</button></article>`).join('')||'<div class="empty">Zatím nebyl připraven žádný opravný plán.</div>'}`;
}
function renderSources(){
  const yn=v=>v===true?'ano':v===false?'ne':'neověřeno / není samostatný doplněk';
  const presence=v=>v==='confirmed'?'potvrzena nyní':'nepotvrzena v aktuálním běhu';
  $('main').innerHTML=`<div class="section-head"><h2>Diagnostické zdroje</h2><button data-action="sources">Ověřit všechna spojení</button></div><div class="callout">Běžící proces není důkaz funkčnosti. „Bez nálezů“ znamená pouze to, že dostupné rozhraní nic nehlásí. Historický inventář není aktuální instalace. Čas odpovědi ani čas převzetí dat nedokazuje nový sken u poskytovatele. Úplnost využití všech jeho funkcí zatím není měřena.</div><div class="cards">${(state.tool_adapters||[]).map(s=>{const d=s.discovery||{};return `<article class="card"><h3>${esc(s.title)}</h3>${[['Aktuální přítomnost',presence(d.current_presence)],['Historický záznam',d.historical_seen?'ano':'ne'],['Proces běží',yn(d.running)],['Rozhraní ověřeno',yn(d.connection_verified)],['Poslední odpověď',when(d.last_success_at)],['Data převzata do HADS',when(d.last_used_at)],['Nálezy',d.findings_count??0],['Poslední chyba',s.last_error||'žádná zaznamenaná']].map(([k,v])=>`<div class="source-row"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join('')}<p class="muted">${d.connection_verified?'Čitelné diagnostické rozhraní; funkčnost všech funkcí není ověřena.':d.current_presence==='confirmed'?'Instalace zjištěna, čitelné aktuální rozhraní není ověřeno.':d.historical_seen?'HADS našel pouze starší stopu. Ta neznamená, že doplněk je nyní nainstalovaný nebo běží.':'Chybí aktuální diagnostické ověření.'}</p></article>`}).join('')}</div><div class="section-head"><h3>Sběr protokolů</h3><button data-action="logs">Otestovat sběr protokolů</button></div><div class="table-scroll"><table><thead><tr><th>Zdroj</th><th>Poslední úspěch</th><th>Řádků</th><th>Nových výskytů</th><th>Stav / chyba</th></tr></thead><tbody>${(state.log_sources||[]).map(r=>`<tr><td>${esc(r.label)}</td><td>${esc(when(r.last_loaded_at))}</td><td>${r.line_count||0}</td><td>${r.findings_count||0}</td><td>${esc(r.status)}<br>${esc(r.last_error||'')}</td></tr>`).join('')}</tbody></table></div>`;
}
async function reload(){
  if(loading){reloadAgain=true;return loading;}
  loading=(async()=>{
    do{
      reloadAgain=false;
      try{
        state=await api('api/first-officer');
        const values=[...$('main').querySelectorAll('input,textarea')].map(e=>[e.id,e.value]);
        const expanded=[...$('main').querySelectorAll('details')].map(e=>e.open);
        render();
        for(const [id,value] of values){if($(id))$(id).value=value;}
        [...$('main').querySelectorAll('details')].forEach((e,i)=>{if(expanded[i]!==undefined)e.open=expanded[i];});
      }catch(error){$('connection').textContent='Dočasně nedostupné — zobrazuji poslední data';notify(error.message,true);}
    }while(reloadAgain);
  })();
  try{return await loading;}finally{loading=null;}
}
function showDialog(){if(!$('incidentDialog').open)$('incidentDialog').showModal();}
async function openRoot(id, tab='summary'){
  saveDraft();const seq=++detailSequence;
  const root=await api(`api/root-cases/${id}`);if(seq!==detailSequence)return;
  detail=root;selectedPlan=root.repair_plan;detailTab=tab;
  $('incidentTitle').textContent=root.title;$('incidentId').textContent=`${root.public_id} · ${label(root.decision_state)}`;
  $('detailTabs').hidden=false;renderDetail();showDialog();
}
function saveDraft(){if(detail&&$('chatBody'))drafts.set(detail.id,$('chatBody').value);}
function renderPlan(p){
  if(!p)return '<div class="callout"><h3>Zatím není co spustit</h3>HADS nemá přesný vykonatelný plán. Přijetí závěru není oprava. V Konverzaci můžete doplnit důkaz a zvolit nové vyšetření.</div>';
  return `<h3>${esc(p.title)}</h3><div class="meta"><span>Plán #${p.id}</span><span>Riziko: ${esc(p.risk_level)}</span><span>${esc(label(p.status))}</span></div><p>${esc(p.rationale)}</p>${(p.preview||[]).map(v=>`<div class="card"><h3>${esc(v.type)} · ${esc(v.target)}</h3><pre class="code">${esc(v.diff||JSON.stringify(v.changes||{},null,2))}</pre>${v.warning?`<div class="callout">${esc(v.warning)}</div>`:''}<p><b>Záloha:</b> ${esc(v.backup||'Povinná nová plná záloha před zápisem.')}</p><p><b>Vrácení změny:</b> ${esc(v.rollback||'Postup je potřeba ověřit před spuštěním.')}</p><p><b>Ověření:</b> ${esc(v.verification||p.verification?.expected||'Následná analýza a sledování.')}</p></div>`).join('')}<p>${esc(p.last_error||'')}</p>${p.result?.backup?`<div class="callout">Záloha: ${esc(p.result.backup.slug)} · ${esc(p.result.backup.verification)}. Obnovení nebylo testováno.</div>`:''}<div class="actions">${p.status==='pending_approval'?`<button class="primary" data-action="approveAndRun">Schválit a spustit tuto opravu</button><button data-action="approvePlan">Pouze schválit do fronty</button>`:''}${['pending_approval','approved'].includes(p.status)?'<button class="danger" data-action="cancelPlan">Zrušit tento plán</button>':''}${p.rollback_available?'<button data-action="rollback">Připravit návrat konfigurace</button>':''}</div><p class="muted">„Schválit a spustit“ zahájí pouze tento plán. Při pouhém schválení do fronty použijte později „Spustit schválené opravy“. Před zápisem HADS ověří nový backup a aktuálnost konfigurace. Neúspěšná nebo přerušená oprava se sama neopakuje.</p>`;
}
function renderAnalysis(r){
  const research=r.research?.research||{},a=research.analysis||{},p=research.plan_readiness;
  if(r.research?.last_error)return `<section class="callout"><h3>Poslední vyšetření selhalo</h3><p>${esc(r.research.last_error)}</p><p>Předchozí analýza byla zachována jako historická. Nový výsledek není potvrzen.</p></section>`;
  if(!p&&!a.summary)return '';
  return `<section class="card"><h3>Poslední vyšetření HADS</h3>${a.summary?`<p>${esc(a.summary)}</p><p><b>Funkční dopad:</b> ${esc(a.functional_impact||'Neověřen')}</p><p><b>Další test:</b> ${esc(a.next_test||'Neuveden')}</p>`:''}${p?`<div class="meta"><span>Kandidátní kroky: ${Number(p.candidate_steps||0)}</span><span>Přesné změny: ${Number(p.exact_changes||0)}</span><span>Vykonatelné akce: ${Number(p.executable_actions||0)}</span></div>${(p.blockers||[]).map(b=>`<p class="callout">${esc(b)}</p>`).join('')}`:''}${research.ai_deferred_reason?`<p class="callout">AI odložena: ${esc(research.ai_deferred_reason)}</p>`:''}<p class="muted">Analýza ani připravený kandidát nejsou provedená oprava. Zápis vyžaduje samostatné schválení a ověřenou zálohu.</p></section>`;
}
function renderDetail(){
  if(!detail)return;
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('selected',b.dataset.tab===detailTab));
  const r=detail;
  if(detailTab==='summary')$('detailContent').innerHTML=`<h3>Co je problém</h3><p>${esc(r.root_cause)}</p><div class="meta"><span>Hodnocení pravidel není pravděpodobnost příčiny</span><span>Dopad: ${r.impact_score}/100</span><span>Poslední výskyt: ${esc(when(r.last_seen))}</span></div><h3>Doporučený postup</h3><p>${esc(r.recommendation)}</p>${!r.repair_plan?'<div class="callout">Jde o vyšetřování nebo závěr. Zatím není připravená vykonatelná oprava.</div>':''}<div class="actions"><button data-tab="chat">Vysvětlit / doplnit informace</button><button data-tab="repair">Zobrazit opravný plán</button><button data-decision="manual">Provedu ručně</button><button data-decision="reject" class="danger">Zamítnout návrh</button><button data-decision="ignore">Ignorovat tento incident</button>${!r.repair_plan?'<button data-decision="accept_analysis">Přijmout závěr a dále sledovat</button>':''}</div><p class="muted">Přijetí závěru není oprava. Ignorování nic nemaže, neskrývá důkazy a platí do ručního znovuotevření.</p>`;
  else if(detailTab==='evidence')$('detailContent').innerHTML=`<h3>Původní hlášky a důkazy</h3>${(r.evidence||[]).map(e=>`<div class="card"><span class="meta">HADS-${e.case_id} · ${esc(e.state)}</span><pre class="code">${esc(e.sample)}</pre></div>`).join('')}<h3>Postižené komponenty</h3>${(r.symptoms||[]).map(s=>`<div class="card"><h3>${esc(s.title)}</h3><span class="meta">${esc(s.source)} · ${s.occurrences}× · ${esc(when(s.last_seen))}</span></div>`).join('')}<details><summary>Výstup posledního plánovače</summary><pre class="code">${esc(JSON.stringify(r.research||{},null,2))}</pre></details>`;
  else if(detailTab==='repair')$('detailContent').innerHTML=renderAnalysis(r)+renderPlan(r.repair_plan);
  else if(detailTab==='history')$('detailContent').innerHTML=(r.decisions||[]).map(d=>`<div class="card"><h3>${esc(d.decision)}</h3><p>${esc(d.reason||'Bez poznámky')}</p><span class="meta">${esc(when(d.created_at))}</span></div>`).join('')||'<div class="empty">Zatím bez rozhodnutí.</div>';
  else {
    const c=r.conversation||{},u=c.usage||{},busy=c.job?.status==='running';
    $('detailContent').innerHTML=`<p class="muted">${r.chat_mode==='openai'?'AI diagnostický chat — měřená spotřeba API.':'Místní diagnostický rádce bez jazykového modelu a webu. Pro volný AI dialog nastavte OpenAI v možnostech doplňku.'} Konverzace nikdy sama neprovede opravu.</p><div class="meta"><span>API požadavky: ${u.calls||0}</span><span>Vstup: ${u.input_tokens||0} tokenů</span><span>Výstup včetně uvažování: ${u.output_tokens||0}</span><span>Web: ${u.web_calls||0} volání</span><span>Neznámá spotřeba: ${u.unknown_calls||0} požadavků</span></div>${(c.messages||[]).map(m=>`<article class="message ${esc(m.role)}"><b>${m.role==='user'?'Vy — tvrzení k ověření':'HADS'}</b><div class="meta">${esc(when(m.created_at))}</div>${esc(m.body)}</article>`).join('')}${busy?'<div class="callout">Vyšetření běží. Můžete detail zavřít, zprávy se neztratí.</div>':c.job?.last_error?`<div class="callout">${esc(c.job.last_error)}</div>`:''}<label>Otázka, nové důkazy nebo vysvětlení<textarea id="chatBody" maxlength="6000" placeholder="Například: telefon jsem přejmenoval; aktuální služba se jmenuje…"></textarea></label><div class="actions"><button data-action="chat" class="primary" ${busy?'disabled':''}>Odeslat otázku</button><button data-action="reinvestigate" ${busy?'disabled':''}>Nesouhlasím — znovu vyšetřit</button><button data-action="refreshDetail">Obnovit odpověď</button></div><p class="muted">Nové vyšetření odvolá starý souhlas s opravou. Bez AI uloží vysvětlení a zopakuje podporované místní kontroly; volný text automaticky nepřepisuje konfiguraci.</p>`;
    $('chatBody').value=drafts.get(r.id)||'';
    $('detailContent').insertAdjacentHTML('beforeend','<details><summary>Znám přesný nový název entity nebo služby</summary><p>HADS ověří existenci cíle a připraví přesný náhled. Tato volba sama není schválením opravy.</p><label>Vlastník<input id="choiceOwner" placeholder="automation.prichod_domu"></label><label>Původní odkaz<input id="choiceOld" placeholder="notify.mobile_app_stary_telefon"></label><label>Nový odkaz<input id="choiceNew" placeholder="notify.mobile_app_novy_telefon"></label><button data-action="choice">Ověřit náhradu a připravit plán</button></details>');
  }
  if(detailTab==='summary')$('detailContent').innerHTML=renderAnalysis(r)+$('detailContent').innerHTML;
  if(['summary','repair'].includes(detailTab)){
    const q=r.research?.research?.analysis?.user_question;
    if(q?.question)$('detailContent').insertAdjacentHTML('beforeend',`<section class="callout"><h3>HADS potřebuje odpověď</h3><p>${esc(q.question)}</p><p class="muted">${esc(q.why_readonly_cannot_answer||'Důvod chybějícího důkazu neuveden.')}</p><button data-tab="chat">Odpovědět v konverzaci</button></section>`);
  }
  if(detailTab==='evidence')$('detailContent').insertAdjacentHTML('beforeend',`<h3>Čtecí kroky AI vyšetřování</h3><p class="muted">Posledních 20 čtení; zkrácené odpovědi jsou označené. Úspěšné čtení není potvrzená oprava.</p>${(r.research_observations||[]).map(o=>`<details class="card"><summary>${esc(o.tool_name)} · ${esc(when(o.captured_at))} · běh ${Number(o.run_id)}</summary><pre class="code">${esc(JSON.stringify(o.result,null,2))}</pre></details>`).join('')||'<p>Dosud nebyla uložena žádná čtení AI pro tento případ.</p>'}`);
}
async function openPlan(id){detailSequence++;saveDraft();selectedPlan=await api(`api/repairs/${id}`);detail=null;$('incidentTitle').textContent=selectedPlan.title;$('incidentId').textContent=`Plán #${id}`;$('detailTabs').hidden=true;$('detailContent').innerHTML=renderPlan(selectedPlan);showDialog();}
async function act(name){
  if(name==='reload')return reload();
  if(name==='close'){saveDraft();$('incidentDialog').close();return;}
  if(name==='approveAndRun'){
    if(!selectedPlan)return;
    if(!await requestDecision('Schválit přesně zobrazenou opravu a ihned zahájit její zálohování a provedení? Ostatní schválené plány se nespustí. Bez ověřeného OneDrive rescue a HA zálohy se systém nezmění.'))return;
    const id=selectedPlan.id;
    const result=await post(`api/repairs/${id}/approve-and-run`,{confirmation:selectedPlan.confirmation_phrase,execution_confirmation:`EXECUTE HADS4-${String(id).padStart(4,'0')}`});
    notify(result.message);$('incidentDialog').close();await reload();return;
  }
  if(name==='refreshDetail')return openRoot(detail.id,detailTab);
  if(name==='analyze'||name==='sources'||name==='logs') {const paths={analyze:'api/first-officer/analyze',sources:'api/tool-adapters/refresh',logs:'api/log-sources/test'};const result=await post(paths[name]);if(name==='logs'){notify('Test sběru běží; čekám na dokončení všech zdrojů.');const outcome=await waitForLogCollection(result.job_id);notify(outcome.message,outcome.status!=='complete');}else notify(result.message||'Ověření zdrojů dokončeno.');await reload();return;}
  if(name==='launch') {if(!await requestDecision('Spustit schválené opravné plány? HADS ověří konflikty, rescue a novou plnou zálohu. Při selhání zálohy nic nezmění. Údržba DB může odstranit přesně schválenou historii.'))return;const result=await post('api/repair-batches/run');notify(result.message||'Příprava dávky byla spuštěna.');await reload();return;}
  if(name==='approvePlan'){if(!selectedPlan)return;if(!await requestDecision('Schválit přesně zobrazené změny včetně uvedeného rizika a případného odstranění historie?'))return;await post(`api/repairs/${selectedPlan.id}/approve`,{confirmation:selectedPlan.confirmation_phrase});notify('Oprava schválena. Je ve frontě; nyní lze použít Spustit schválené opravy.');$('incidentDialog').close();await reload();return;}
  if(name==='cancelPlan'){await post(`api/repairs/${selectedPlan.id}/cancel`);notify('Plán vyřazen ze schválených oprav.');$('incidentDialog').close();await reload();return;}
  if(name==='rollback'){if(!await requestDecision('Vrátit konfiguraci z tohoto plánu? Nejprve vznikne nová plná záloha. Při novějších změnách bude návrat odmítnut.'))return;await post(`api/repairs/${selectedPlan.id}/rollback`,{confirmation:selectedPlan.rollback_phrase});notify('Postup návratu dokončen; ověřte výsledek v plánu.');await openPlan(selectedPlan.id);await reload();return;}
  if(name==='chat'||name==='reinvestigate'){const body=$('chatBody').value.trim();if(!body)throw new Error('Napište otázku nebo důvod nového vyšetření.');if(name==='reinvestigate'&&!await requestDecision('Znovu vyšetřit incident a odvolat případný starý souhlas s opravou?'))return;const result=await post(`api/root-cases/${detail.id}/messages`,{body,kind:name});drafts.delete(detail.id);$('chatBody').value='';notify(result.message);await openRoot(detail.id,'chat');await reload();return;}
  if(name==='choice'){const result=await post(`api/root-cases/${detail.id}/choices`,{owner:$('choiceOwner').value,old_value:$('choiceOld').value,new_value:$('choiceNew').value});notify(result.message);await openRoot(detail.id,'chat');await reload();return;}
  if(name==='recorder'){const days=Number($('keepDays').value);if(!Number.isInteger(days)||days<1||days>3650)throw new Error('Zvolte 1–3650 dnů.');const p=await post('api/repairs',{title:`Recorder: zachovat ${days} dnů historie`,rationale:'Kapitánem vyžádaná údržba historie; nejedná se o automatické mazání nečinných entit.',actions:[{type:'recorder_purge',keep_days:days}]});await reload();await openPlan(p.id);return;}
  if(name==='manualPlan'){const p=await post('api/repairs',{title:$('manualTitle').value,actions:JSON.parse($('manualActions').value)});await reload();await openPlan(p.id);return;}
}
document.addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b||b.disabled)return;
  if(b.closest('#decisionDialog'))return;
  try {
    if(b.dataset.page){page=b.dataset.page;render();return;}
    if(b.dataset.tab){saveDraft();detailTab=b.dataset.tab;renderDetail();return;}
    b.disabled=true;
    if(b.dataset.root)await openRoot(Number(b.dataset.root));
    else if(b.dataset.plan)await openPlan(Number(b.dataset.plan));
    else if(b.dataset.decision){const reason=await requestDecision('Uveďte důvod svého rozhodnutí. Uchová se u tohoto incidentu.',true);if(reason===null)return;await post(`api/root-cases/${detail.id}/decision`,{decision:b.dataset.decision,reason});notify(b.dataset.decision==='accept_analysis'?`Závěr ${detail.public_id} přesunut do sledování. Nejde o opravu.`:'Rozhodnutí bylo uloženo.');await openRoot(detail.id);await reload();}
    else await act(b.dataset.action);
  }catch(error){notify(error.message,true);}finally{if(b.isConnected)b.disabled=false;if(b.id==='launch')b.disabled=!state?.batch_checklist?.runnable;}
});
$('incidentDialog').addEventListener('cancel',saveDraft);
setInterval(async()=>{if(document.hidden)return;await reload();if($('incidentDialog').open&&detailTab==='chat'&&detail?.conversation?.job?.status==='running'){try{await openRoot(detail.id,'chat');}catch(error){notify(error.message,true);}}},10000);
reload();
