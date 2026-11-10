"""Actual Core + actual confined Hermes. Scripted model, zero paid inference."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
import sys
import threading
import ssl
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from datetime import datetime,timedelta,timezone
import ipaddress
import logging
import ctypes
import aiohttp

import yaml
from homeassistant import bootstrap,config as ha_config,config_entries,core_config,loader
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import EvidenceBroker
from hads_next.hermes_runtime import run_investigation
from hads_next.investigation_jobs import InvestigationJobs
from hads_next.observability import CoreReader,CoreWSReader,NativeHTTP,NativeWebSocket
from hads_next.runtime_launcher import RuntimeLauncher
from hads_next.haos_application import Application
from hads_next.addon_server import Server


class ScriptedModel:
    """Protocol test derives next arguments from the preceding actual read."""
    def __init__(self):self.requests=[];self.automation_id=None;self.evidence=[]

    def __call__(self,body):
        self.requests.append(body)
        results=[json.loads(m['content']) for m in body['messages'] if m.get('role')=='tool']
        turn=len(self.requests)
        if turn==1:name,args='hads_get_incident',{}
        elif turn==2:
            self.automation_id=next(x.split('.',1)[1] for x in results[-1]['data']['incident']['components'] if x.startswith('automation.'))
            name,args='hads_get_automation_config',{'automation_id':self.automation_id}
        elif turn==3:
            assert results[-1]['data']['actions'][0]['target']['entity_id']==['input_boolean.hads_lab_missing']
            name,args='hads_get_automation_traces',{'automation_id':self.automation_id}
        elif turn==4:
            name,args='hads_get_automation_trace',{'automation_id':self.automation_id,'run_id':results[-1]['data'][0]['run_id']}
        elif turn==5:
            assert results[-1]['data']['steps']
            name,args='hads_get_entity_state',{'entity_id':'input_boolean.hads_lab_missing'}
        elif turn==6:
            assert results[-1]['status']=='no_relevant_data' and results[-1]['data']['exists'] is False
            name,args='hads_get_entity_state',{'entity_id':'input_boolean.hads_lab_target'}
        elif turn==7:
            assert results[-1]['data']['state']=='off'
            evidence=sorted({identity for row in results for identity in row['evidence_ids']})
            name,args='hads_select_investigator',{'role':'root_cause','task':'Porovnej konfiguraci, trace a oba stavy; odděl chybějící cíl od neověřené příčiny.',
                'handoff':{'summary_cs':'Konfigurace a trace byly načteny. Cíl reference nemá aktuální stav; virtuální testovací cíl zůstal vypnutý.',
                    'evidence_ids':evidence,'uncertainties':['Chybí důkaz zamýšleného přemapování.']}}
        else:
            assert results[-1]['data']['role']=='root_cause'
            evidence=sorted({identity for row in results for identity in row['evidence_ids']})
            message={'role':'assistant','content':json.dumps({'summary_cs':'Automatizace se spustila, ale její cíl nemá aktuální stav v Core. Dostupný testovací cíl zůstal vypnutý.',
                'hypotheses':[{'claim':'Neaktivní cíl automatizace; možná neplatná reference.','evidence_ids':evidence,'confidence':'supported_missing_current_state'}],
                'needed':[],'next_test_cs':'V izolovaném testu ověř správný odkaz a skutečnou změnu cíle.',
                'repair_proposal':{'target':self.automation_id,'change':{'from':'input_boolean.hads_lab_missing','to':'input_boolean.hads_lab_target'},
                    'reason':'Chybějící reference.','evidence_ids':evidence,'risk':'virtual_lab_only',
                    'backup':'single_object_snapshot','verification':'actual_trigger_and_target_state','rollback':'separate_approval',
                    'manual_alternative':'Zkontroluj cíl v editoru automatizace.'}},ensure_ascii=False)}
            return self._response(message,'stop')
        message={'role':'assistant','content':None,'tool_calls':[{'id':'read-'+str(turn),'type':'function',
            'function':{'name':name,'arguments':json.dumps(args)}}]}
        return self._response(message,'tool_calls')

    def _response(self,message,reason):
        return {'id':'scripted-'+str(len(self.requests)),'object':'chat.completion','created':int(time.time()),
            'model':'hads-scripted-contract','choices':[{'index':0,'message':message,'finish_reason':reason}],
            'usage':{'prompt_tokens':100,'completion_tokens':100,'total_tokens':200}}


async def main():
    logging.basicConfig(level=logging.WARNING)
    launcher=RuntimeLauncher()
    assert ctypes.CDLL(None).prctl(38,1,0,0,0)==0
    os.setgroups([]);os.setresgid(65532,65532,65532);os.setresuid(65532,65532,65532)
    try:
        with tempfile.TemporaryDirectory(prefix='hads-native-core-') as directory:
            path=Path(directory)
            from source_contract_probe import prepare_fixture
            prepare_fixture(path)
            automation={'id':'hads_lab_reference','triggers':[{'trigger':'state','entity_id':'input_button.hads_lab_run'}],
                'actions':[{'action':'input_boolean.turn_on','target':{'entity_id':'input_boolean.hads_lab_missing'}}]}
            zha={'id':'hads_zha_chain','alias':'HADS ZHA chain','triggers':[{'trigger':'event','event_type':'zha_event',
                'event_data':{'device_id':'11111111111111111111111111111111','command':'toggle'}}],
                'actions':[{'action':'input_boolean.turn_on','target':{'entity_id':'input_boolean.hads_zha_target'}}]}
            (path/'automations.yaml').write_text(yaml.safe_dump([automation,zha]))
            (path/'configuration.yaml').write_text('''homeassistant:
  name: HADS native investigation lab
  latitude: 0
  longitude: 0
  elevation: 0
  unit_system: metric
  time_zone: UTC
  auth_mfa_modules: []
http:
  server_host: 127.0.0.1
  server_port: 8123
api:
websocket_api:
config:
recorder:
  commit_interval: 1
history:
logbook:
system_health:
system_log:
repairs:
media_player:
  - platform: hads_lab_player
automation: !include automations.yaml
input_boolean:
  hads_lab_target:
    initial: false
  hads_zha_target:
    initial: false
input_button:
  hads_lab_run:
''')
            hass=HomeAssistant(directory);loader.async_setup(hass);hass.config.skip_pip=True
            config=await ha_config.async_hass_config_yaml(hass)
            hass.config_entries=config_entries.ConfigEntries(hass,config)
            assert await bootstrap.async_load_base_functionality(hass)
            try:
                for domain in bootstrap.CORE_INTEGRATIONS:assert await async_setup_component(hass,domain,config)
                await core_config.async_process_ha_core_config(hass,config['homeassistant'])
                from homeassistant.helpers.recorder import async_initialize_recorder
                async_initialize_recorder(hass)
                for domain in ('homeassistant','http','websocket_api','api','config','recorder','history','logbook','system_health','system_log','repairs','input_boolean','input_button','media_player','automation'):
                    assert await async_setup_component(hass,domain,config),domain
                user=await hass.auth.async_create_user('Native lab admin',group_ids=['system-admin'])
                refresh=await hass.auth.async_create_refresh_token(user,client_id='https://hads-lab.invalid/')
                token=hass.auth.async_create_access_token(refresh)
                await hass.async_start();await hass.async_block_till_done()
                await hass.services.async_call('input_button','press',{'entity_id':'input_button.hads_lab_run'},blocking=True)
                await hass.async_block_till_done()
                assert hass.states.get('input_boolean.hads_lab_target').state=='off'
                core=CoreReader(NativeHTTP('http://127.0.0.1:8123',token,allow_local_http=True))
                ws=CoreWSReader(NativeWebSocket('ws://127.0.0.1:8123/api/websocket',token,allow_loopback=True))
                model=ScriptedModel()
                models={'hads-scripted-contract':model}
                # A real HTTPS, OpenAI-compatible test endpoint exercises the
                # production sender and opt-in path. Its CA is explicitly trusted
                # only in this ephemeral process; TLS verification stays enabled.
                from cryptography import x509
                from cryptography.hazmat.primitives import hashes,serialization
                from cryptography.hazmat.primitives.asymmetric import rsa
                key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
                name=x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME,'HADS isolated model CA')])
                certificate=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
                    .not_valid_after(datetime.now(timezone.utc)+timedelta(hours=1))
                    .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
                    .add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=True,data_encipherment=False,key_agreement=False,
                        key_cert_sign=True,crl_sign=True,encipher_only=None,decipher_only=None),critical=True)
                    .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False)
                    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),critical=False)
                    .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
                    .sign(key,hashes.SHA256()))
                ca=path/'model-ca.pem';private=path/'model-key.pem'
                ca.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
                private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
                os.environ['SSL_CERT_FILE']=str(ca)
                class ModelHandler(BaseHTTPRequestHandler):
                    def log_message(self,*args):pass
                    def do_POST(self):
                        assert self.path=='/v1/chat/completions'
                        assert self.headers.get('Authorization')=='Bearer SYNTHETIC_TEST_KEY'
                        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                        reply=json.dumps(models[body['model']](body)).encode()
                        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(reply)));self.end_headers();self.wfile.write(reply)
                model_server=ThreadingHTTPServer(('127.0.0.1',0),ModelHandler)
                tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(ca,private)
                model_server.socket=tls.wrap_socket(model_server.socket,server_side=True)
                threading.Thread(target=model_server.serve_forever,daemon=True).start()
                app=Application(path/'hads',core,core_ws=ws,launcher=launcher)
                controller=Server(('127.0.0.1',0),app,ingress_peer='127.0.0.1')
                threading.Thread(target=controller.serve_forever,daemon=True).start()
                try:
                    store=app.store;jobs=app.investigations.jobs
                    incident=store.open_incident('automation_reference','Tlačítko nezapnulo virtuální cíl.',
                        ['automation.hads_lab_reference','input_boolean.hads_lab_target'],time.time())
                    ui='http://127.0.0.1:'+str(controller.server_port)
                    async with aiohttp.ClientSession(headers={'X-Remote-User-Id':user.id}) as ui_client:
                        async with ui_client.post(ui+'/setup/enroll',data={'csrf':controller.csrf},allow_redirects=False) as response:assert response.status==303
                        async with ui_client.post(ui+'/setup/runtime',data={'csrf':controller.csrf},allow_redirects=False) as response:assert response.status==303
                        for _ in range(800):
                            readiness=app.investigations.status()['runtime_probe']
                            if readiness['state'] in {'ready','failed','unavailable'}:break
                            await asyncio.sleep(.05)
                        assert readiness['state']=='ready',readiness
                        assert model.requests==[],'Runtime readiness must not call the model'
                        async with ui_client.post(ui+'/setup/ai',data={'csrf':controller.csrf,'endpoint':'https://127.0.0.1:'+str(model_server.server_port)+'/v1/chat/completions',
                            'model':'hads-scripted-contract','api_key':'SYNTHETIC_TEST_KEY','consent':'yes'},allow_redirects=False) as response:assert response.status==303
                        async with ui_client.post(ui+'/investigate',data={'csrf':controller.csrf,'incident_id':incident['id']},allow_redirects=False) as response:assert response.status==303
                        for _ in range(1600):
                            investigations=app.investigations.for_case(incident['id'])
                            if investigations and investigations[0]['state'] in {'hypothesis_ready','blocked','failed','waiting_for_user','waiting_for_source'}:break
                            await asyncio.sleep(.1)
                        job=investigations[0]
                        assert job['state']=='hypothesis_ready',{'state':job['state'],'calls':job['model_calls'],'requests':len(model.requests),'reads':job['reads']}
                        suggestion=job['conclusion']['repair_suggestion']
                        assert suggestion['status']=='supported_lab_candidate' and suggestion['production_executable'] is False,suggestion
                        assert suggestion['change']=={'from':'input_boolean.hads_lab_missing','to':'input_boolean.hads_lab_target'}
                        async with ui_client.get(ui+'/case/'+incident['id']) as response:
                            page=await response.text();assert response.status==200
                            assert 'Automatizace se spustila' in page and 'SYNTHETIC_TEST_KEY' not in page
                            assert 'Návrh dalšího postupu' in page and 'Chci postupovat ručně' in page and 'Schválit opravu' not in page
                        async with ui_client.get(ui+'/api/status') as response:
                            status=await response.text();assert 'SYNTHETIC_TEST_KEY' not in status and token not in status
                    result={'completed':True,'engine':'NousResearch/hermes-agent','revision':'d923a5eb487a17c0a68801bba9ef0f56c81040a8',
                        'job':job,'runtime_readiness':readiness,'isolation_verified':True,'execution_authority':'none'}
                    runtime=next(row['content'] for row in reversed(store.case(incident['id'])['records']) if row['kind']=='hermes_worker_runtime')
                    result.update(runtime)
                    assert runtime['uid']==65534 and runtime['isolation_verified']
                    from restart_investigation_probe import exercise_restart
                    result['restart_test']=await exercise_restart(path,core,ws,launcher,user,
                        'https://127.0.0.1:'+str(model_server.server_port)+'/v1/chat/completions',models,ScriptedModel)
                    from negative_investigation_probe import exercise_negative
                    result['negative_tests']=await exercise_negative(path,core,ws,launcher,user,
                        'https://127.0.0.1:'+str(model_server.server_port)+'/v1/chat/completions',models)
                    from source_contract_probe import exercise_sources
                    result['source_contracts']=await exercise_sources(hass,app)
                finally:
                    await asyncio.to_thread(controller.shutdown);controller.server_close()
                    await asyncio.to_thread(model_server.shutdown);model_server.server_close()
                names=[row['name'] for row in result['job']['reads']]
                assert names==['hads_get_incident','hads_get_automation_config','hads_get_automation_traces','hads_get_automation_trace','hads_get_entity_state','hads_get_entity_state','hads_select_investigator'],names
                assert len(model.requests)==8
                role_findings=[r['content'] for r in store.case(incident['id'])['records'] if r['kind']=='investigator_finding']
                assert {r['role'] for r in role_findings}=={'automation','root_cause'}
                result['role_findings']=role_findings
                assert len(store.case(incident['id'])['evidence'])==5
                assert result['job']['state']=='hypothesis_ready'
                assert store.case(incident['id'])['incident']['status']=='open'
                assert token not in json.dumps(result)
                result.update({'scope':'actual_core_controller_and_confined_hermes_container','core_version':'2026.11.0',
                    'model_kind':'scripted_protocol_test','real_model_reasoning_tested':False,'live_haos':False,
                    'supervisor_live':False,'controller_uid':os.geteuid(),'ha_token_shared_with_worker':False,
                    'model_requests':len(model.requests),'actual_read_tools':names,'new_evidence_count':5,'passed':True})
                result['production_controller_flow_tested']=True
                result['model_endpoint']='local_scripted_https_with_verified_test_CA'
                result['ingress_peer']='simulated_loopback_not_HAOS_ingress'
                print(json.dumps(result,ensure_ascii=False))
            finally:await hass.async_stop(force=True)
    finally:launcher.close()


if __name__=='__main__':asyncio.run(asyncio.wait_for(main(),timeout=360))
