"""Actual Inspector builder -> actual Core -> HADS provider contract -> Hermes.

The upstream application listener is not exercised here; the wire listener
contract has separate isolated tests. This probe makes neither a live-HAOS nor
real-provider-reasoning claim.
"""
import asyncio,json,sys
from pathlib import Path
from app import APP_VERSION
from app.settings import Settings
from app.dependency_map import DependencyMapBuilder
from hads_next.provider_reports import inspector
from hads_next.connector_policy import descriptor
from hads_next.tool_registry import object_schema
from hads_next.hermes_runtime import run_investigation

async def exercise(app,token,launcher,scripted_model):
    # A new isolated test DB keeps this additional free protocol exercise
    # separate from the unchanged per-installation/day admission limits.
    from hads_next.haos_application import Application
    app=Application(app.data_dir.parent/'orchestration-proof',app.core,core_ws=app.core_ws,launcher=launcher)
    settings=Settings(websocket_url='ws://127.0.0.1:8123/api/websocket',token=token,inspect_traces=True,scan_automations_file=False)
    original=await DependencyMapBuilder(settings).build()
    value=inspector(original,{'ready':True,'stale':False,'generation':1})
    assert original['schema_version']==2 and original['app_version']==APP_VERSION and original['summary']['inspected_items']>=1
    await asyncio.to_thread(app.check_sources)
    services=await asyncio.to_thread(app.core_ws.transport,{'type':'get_services'})
    assert isinstance(services,dict) and 'turn_on' in services.get('light',{}),'Actual Core service catalog must be readable, not silently replaced'
    app.tools._report('automation_inspector','dependency_report',value)
    app.tools.registry.provider('automation_inspector',connected=True,catalog_loaded=True,version=APP_VERSION,version_basis='actual_pinned_Inspector_builder',diagnostic_read_verified=True)
    app.tools.registry.replace('automation_inspector',[descriptor('dependency_report',object_schema(),contract='actual_upstream_builder_against_actual_Core')])
    incident=app.store.open_incident('automation_reference','Přímé ověření nástrojové orchestrace',['automation.hads_lab_reference','input_boolean.hads_lab_target','input_boolean.hads_lab_missing'],app.clock(),correlation_key='orchestration:actualCore')
    # Resolve the real automation entity from the actual Inspector output.
    actual=next(r['entity_id'] for r in value['items'] if r.get('config_id')=='hads_lab_reference' or r.get('entity_id','').startswith('automation.hads_lab'))
    with app.store._connect() as db:db.execute('UPDATE incidents SET components=? WHERE id=?',(json.dumps([actual,'input_boolean.hads_lab_target','input_boolean.hads_lab_missing']),incident['id']))
    evidence=app.tools.diagnostic_read(incident['id'],{'provider':'automation_inspector','tool':'dependency_report','arguments':{}})
    assert evidence['status']=='available' and evidence['evidence_ids']
    class ProviderModel(scripted_model):
        """A bounded protocol script; no claim of independent AI reasoning."""
        def __call__(self,body):
            self.requests.append(body)
            results=[json.loads(m['content']) for m in body['messages'] if m.get('role')=='tool']
            turn=len(self.requests)
            if turn==1:name,args='hads_list_tools',{}
            elif turn==2:
                assert any(r['provider']=='automation_inspector' and r['name']=='dependency_report' and r['available'] for r in results[-1]['data']['tools'])
                name,args='hads_diagnostic_tool',{'provider':'automation_inspector','tool':'dependency_report','arguments':{}}
            elif turn==3:
                assert results[-1]['status']=='available' and results[-1]['data']['items']
                item=next(r for r in results[-1]['data']['items'] if r.get('entity_id')==actual)
                self.automation_id=item['entity_id'].split('.',1)[1]
                name,args='hads_diagnostic_tool',{'provider':'core','tool':'hads_get_automation_config','arguments':{'automation_id':self.automation_id}}
            elif turn==4:
                assert results[-1]['data']['actions'][0]['target']['entity_id']==['input_boolean.hads_lab_missing']
                name,args='hads_get_automation_traces',{'automation_id':self.automation_id}
            elif turn==5:
                name,args='hads_get_automation_trace',{'automation_id':self.automation_id,'run_id':results[-1]['data'][0]['run_id']}
            elif turn==6:
                assert results[-1]['data']['steps']
                name,args='hads_get_entity_state',{'entity_id':'input_boolean.hads_lab_missing'}
            elif turn==7:
                assert results[-1]['status']=='no_relevant_data' and results[-1]['data']['exists'] is False
                ids=sorted({e for r in results for e in r['evidence_ids']})
                name,args='hads_select_investigator',{'role':'root_cause','task':'Porovnej report Inspectoru se skutečnou konfigurací, trace a nepřítomným stavem; nedoplňuj neověřenou náhradu.',
                    'handoff':{'summary_cs':'Inspector, konfigurace a trace se týkají stejné automatizace; původní cíl nemá aktuální stav.','evidence_ids':ids,'uncertainties':['Zamýšlená náhrada entity není doložená.']}}
            else:
                assert turn==8 and results[-1]['data']['role']=='root_cause'
                ids=sorted({e for r in results for e in r['evidence_ids']})
                value={'summary_cs':'Report Inspectoru byl porovnán s konfigurací a trace z Core. Cíl automatizace nemá aktuální stav; náhrada zatím není doložená.',
                    'hypotheses':[{'claim':'Možná neplatná reference automatizace.','evidence_ids':ids,'confidence':'supported_missing_current_state'}],
                    'needed':[],'next_test_cs':'Získat stabilní identitu původního zařízení; podobný název nestačí k opravě.','repair_proposal':None}
                return self._response({'role':'assistant','content':json.dumps(value,ensure_ascii=False)},'stop')
            return self._response({'role':'assistant','content':None,'tool_calls':[{'id':'catalog-'+str(turn),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'tool_calls')
    model=ProviderModel()
    job=app.investigations.jobs.enqueue(incident['id'])
    result=await asyncio.to_thread(run_investigation,app.investigations.jobs,job,app.investigations.broker,launcher,model,model='hads-scripted-contract')
    assert result['job']['state']=='hypothesis_ready'
    names=[r['name'] for r in result['job']['reads']]
    assert names[:3]==['hads_list_tools','hads_diagnostic_tool','hads_diagnostic_tool'],names
    return {'passed':True,'actual_Core':True,'actual_pinned_Inspector_builder':True,'Inspector_application_HTTP_listener':False,
            'actual_original_Hermes':True,'catalog_selected_broker_read':True,'catalog_selected_Inspector_then_Core':True,'model_kind':'local_scripted_not_reasoning',
            'model_requests':len(model.requests),'live_haos':False,'paid_model_calls':0,'read_tools':names,'Inspector_version':APP_VERSION}
