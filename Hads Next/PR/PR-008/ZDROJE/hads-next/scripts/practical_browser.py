"""Reproducible offline UI acceptance; fake trusted ingress, no HAOS/model."""
import hashlib,json,sys,tempfile,threading
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
                browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                context=browser.new_context(extra_http_headers={'X-Remote-User-Id':'offline-ui-owner'})
                page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(origin);page.get_by_role('button',name='Potvrdit správu HADS a zahájit kontrolu zdrojů').click();page.wait_for_url(origin+'/setup')
                case=app.report_incident('Světlo nereaguje <script>window.bad=true</script>','light.offline_fixture',app.owner())
                app._entities=[{'entity_id':'automation.entry','name':'Světlo na chodbě – ukázka prohlížeče','state':'off'}]
                for width in [1280,390]:
                    page.set_viewport_size({'width':width,'height':900})
                    for path in ['/','/setup/lighting','/setup/monitors','/acceptance','/case/'+case['incident']['id']]:
                        response=page.goto(origin+path);assert response.status==200
                        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),(width,path)
                        assert all(link.bounding_box()['height']<100 for link in page.locator('nav a').all()),'Navigation must remain readable on mobile'
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
            report={'scope':'offline_browser_fake_ingress_no_HAOS','browser':'system Chromium with Playwright','live_haos':False,'views':views,'acceptance_steps':12,'cost_consent_default':False,'anonymous_export':True,'script_injection_escaped':True,'keyboard_focus':True,'real_model_called':False,'passed':True,'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
            output=ROOT/'docs/evidence/practical-browser.json';output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'views':len(views),'report':str(output)}))
        finally:server.shutdown();server.server_close();app.detection.close();app.repairs.close()

if __name__=='__main__':main()
