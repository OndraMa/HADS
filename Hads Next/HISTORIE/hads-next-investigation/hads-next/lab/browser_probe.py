import sys,tempfile,threading,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path('src').resolve()))
from hads_next.haos_application import Application
from hads_next.observability import CoreWSReader
from hads_next.addon_server import Server
from playwright.sync_api import sync_playwright

with tempfile.TemporaryDirectory() as tmp:
 app=Application(Path(tmp))
 def ws(command):
  if command.get('type')=='config/auth/list':return [{'id':'browser-owner','is_active':True,'is_owner':True,'system_generated':False,'group_ids':[]}]
  raise OSError('Source unavailable in browser fixture')
 app.core_ws=CoreWSReader(ws)
 server=Server(('127.0.0.1',0),app,ingress_peer='127.0.0.1')
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 origin='http://127.0.0.1:'+str(server.server_port)
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
   context=browser.new_context(extra_http_headers={'X-Remote-User-Id':'browser-owner'},viewport={'width':1280,'height':1100})
   page=context.new_page()
   page.goto(origin);page.get_by_role('button').click()
   page.wait_for_url(origin+'/setup')
   page.get_by_role('heading',name='Průvodce připraveností').wait_for(timeout=3000)
   page.get_by_role('button',name='Ověřit skutečná čtení zdrojů').click()
   page.wait_for_url(origin+'/');page.goto(origin+'/setup');assert 'core_config' in page.inner_text('body')
   page.goto(origin+'/setup/ai')
   assert not page.locator('input[name=consent]').is_checked()
   assert app.investigations.provider.public_status()['enabled'] is False
   page.goto(origin+'/')
   page.locator('textarea[name=symptom]').fill('Rádio se samo vypnulo — browser fixture.')
   page.locator('input[name=entity_id]').fill('media_player.browser_fixture')
   page.get_by_role('button',name='Uložit incident a přečíst historii').click()
   page.get_by_role('link',name='Otevřít důkazy spisu').click();page.wait_for_url(origin+'/case/*')
   case_id=page.url.rsplit('/',1)[1]
   page.reload();assert 'Rádio se samo vypnulo' in page.inner_text('body')
   job=app.investigations.jobs.enqueue(case_id);app.investigations.jobs.claim(job)
   app.investigations.jobs.transition(job,'hypothesis_ready','Offline browser fixture.',conclusion={'summary_cs':'Chybí důkaz příčiny.','repair_suggestion':{'suggestion_id':'f'*64,'summary_cs':'Ověř mapování přehrávače.','manual_steps_cs':['Porovnej entitu a přehrávač bez změny přehrávání.']}})
   page.reload()
   assert page.get_by_role('button',name='Schválit opravu').count()==0
   page.get_by_role('button',name='Chci postupovat ručně').click()
   assert 'Zvolil jsi ruční kontrolu' in page.inner_text('body')
   assert page.get_by_role('button',name='Chci postupovat ručně').count()==0
   page.reload();assert 'Ověření výsledku stále čeká' in page.inner_text('body')
   assert app.store.case(case_id)['incident']['status']=='open'
   page.screenshot(path='.test-tmp/haos-investigation-browser.png',full_page=True)
   browser.close()
  receipt={'scope':'offline_browser_with_fake_ingress_and_fixture_case','live_haos':False,'browser':'system Chromium through Playwright','owner_enrolment':True,'source_check_with_unavailable_sources':True,'model_disabled_by_default':True,'manual_incident_persisted_after_reload':True,'exact_draft_manual_choice_visible_after_reload':True,'no_fake_approve_button':True,'incident_remains_open':True,'native_runtime':'separate actual container proof; no runtime injected into this browser fixture','passed':True,'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('src/hads_next').glob('*.py'))}}
  Path('docs/evidence/haos-investigation-browser.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
 finally:
  server.shutdown();server.server_close();thread.join()
