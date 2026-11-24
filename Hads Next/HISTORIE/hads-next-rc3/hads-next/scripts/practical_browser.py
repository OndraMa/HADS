"""Reproducible offline UI acceptance; fake trusted ingress, no HAOS/model."""
import hashlib,json,os,sys,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from hads_next.haos_application import Application
from hads_next.addon_server import Server
from hads_next.observability import CoreWSReader
from playwright.sync_api import sync_playwright

def main():
    with tempfile.TemporaryDirectory() as directory:
        app=Application(directory)
        def auth(command):
            if command.get('type')=='config/auth/list':return [{'id':'offline-ui-owner','is_active':True,'is_owner':True,'system_generated':False,'group_ids':[]}]
            raise OSError('Fixture has no native sources')
        app.core_ws=CoreWSReader(auth)
        server=Server(('127.0.0.1',0),app,ingress_peer='127.0.0.1');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port);views=[]
        try:
            with sync_playwright() as pw:
                browser_path=os.environ.get('HADS_BROWSER_EXECUTABLE') or ('/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None)
                browser=pw.chromium.launch(executable_path=browser_path,headless=True,args=['--no-sandbox'])
                context=browser.new_context(extra_http_headers={'X-Remote-User-Id':'offline-ui-owner'})
                page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(origin);page.get_by_role('button',name='Potvrdit správu HADS a zahájit kontrolu zdrojů').click();page.wait_for_url(origin+'/setup')
                case=app.report_incident('Světlo nereaguje <script>window.bad=true</script>','light.offline_fixture',app.owner())
                with app.store._connect() as db:db.execute("UPDATE incidents SET status='archived' WHERE id=?",(case['incident']['id'],))
                app._timezone='Europe/Prague'
                app._sources={name:{'read_succeeded':True,'status':{'last_error':None}} for name in ('core_config','supervisor','haos','applications','entity_registry','device_registry','repairs','system_log','system_health')}
                app._apps=[{'slug':'fixture_radio','name':'Stream Player'},{'slug':'fixture_backup','name':'Backup Agent'}]
                app._summary.update(available=True,entity_count=837,version='2026.11.1',last_error=None)
                for slug in ('fixture_radio','fixture_backup'):
                    app.system._finding('app:'+slug,'application_failure','Aplikace hlásí neúspěšný běh.',['supervisor',slug],{'slug':slug,'state':'error'})
                app.system._finding('memory-reserve','system_resource_pressure','Paměť je pod rezervou.',['hads_runtime'],{'reserve_bytes':576*1024*1024})
                app.system.last=app.clock()
                app._entities=[{'entity_id':'automation.entry','name':'Světlo na chodbě – ukázka prohlížeče','state':'off'}]
                for width in [1280,390]:
                    page.set_viewport_size({'width':width,'height':900})
                    for path in ['/','/setup/lighting','/setup/monitors','/acceptance','/case/'+case['incident']['id']]:
                        response=page.goto(origin+path);assert response.status==200
                        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),(width,path)
                        assert all(link.bounding_box()['height']<100 for link in page.locator('nav a').all()),'Navigation must remain readable on mobile'
                        if path=='/':
                            assert page.locator('nav').count()==1
                            page.get_by_text('Stavy aplikací k ověření (2)',exact=True).click()
                            assert page.get_by_role('heading',name='Stream Player potřebuje kontrolu').count()==1
                            assert page.get_by_role('heading',name='Backup Agent potřebuje kontrolu').count()==1
                            assert 'AI je vypnutá' in page.inner_text('body')
                            assert 'Rezerva pro AI nebyla splněná' in page.inner_text('body')
                            page.evaluate('window.scrollTo(0,0)')
                            page.screenshot(path=str(ROOT/('.test-tmp/dashboard-'+('mobile' if width==390 else 'desktop')+'.png')),full_page=True)
                        assert page.evaluate('window.bad===undefined');views.append({'width':width,'path':path.split(case['incident']['id'])[0],'passed':True})
                    page.goto(origin+'/acceptance');page.locator('input[name=isolated]').check();page.get_by_role('button',name='Založit přejímkový protokol').click();page.wait_for_url('**/acceptance?session=*')
                    assert page.get_by_role('button',name='Provést tento test').count()==12
                    assert not page.locator('input[name=cost_consent]').is_checked()
                    assert page.get_by_text('Čeká na test',exact=False).count()>=12
                    page.keyboard.press('Tab');assert page.evaluate('document.activeElement.tagName')!='BODY'
                    download=page.get_by_role('link',name='Stáhnout anonymizovaný report').get_attribute('href')
                    report=context.request.get(origin+'/'+download).json();assert len(report['steps'])==12
                    assert report['all_steps_passed'] is False and 'offline-ui-owner' not in json.dumps(report)
                    if width==390:page.screenshot(path=str(ROOT/'.test-tmp/practical-acceptance-mobile.png'),full_page=True)
                assert context.request.get(origin+'/acceptance?session=invalid').status==404
                assert not errors;browser.close()
            files=list((ROOT/'src/hads_next').glob('*.py'))+[Path(__file__)]
            report={'scope':'offline_browser_fake_ingress_no_HAOS','browser':'system Chromium with Playwright','live_haos':False,'views':views,'acceptance_steps':12,'cost_consent_default':False,'anonymous_export':True,'script_injection_escaped':True,'historical_application_names_distinguished':True,'single_navigation':True,'AI_disabled_visible':True,'status_only_apps_not_functional_failures':True,'application_observations_expanded_for_preview':True,'data_origin':'anonymous_fixture_based_on_owner_reported_UI_shape_not_live_HAOS','keyboard_focus':True,'real_model_called':False,'passed':True,'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
            output=ROOT/'docs/evidence/practical-browser.json';output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'views':len(views),'report':str(output)}))
        finally:server.shutdown();server.server_close();app.detection.close();app.repairs.close()

if __name__=='__main__':main()
