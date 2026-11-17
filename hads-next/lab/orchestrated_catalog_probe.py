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
    app.tools._report('automation_inspector','dependency_report',value)
    app.tools.registry.provider('automation_inspector',connected=True,catalog_loaded=True,version=APP_VERSION,version_basis='actual_pinned_Inspector_builder',diagnostic_read_verified=True)
    app.tools.registry.replace('automation_inspector',[descriptor('dependency_report',object_schema(),contract='actual_upstream_builder_against_actual_Core')])
    incident=app.store.open_incident('automation_reference','Přímé ověření nástrojové orchestrace',['automation.hads_lab_reference','input_boolean.hads_lab_target','input_boolean.hads_lab_missing'],app.clock(),correlation_key='orchestration:actualCore')
    # Resolve the real automation entity from the actual Inspector output.
    actual=next(r['entity_id'] for r in value['items'] if r.get('config_id')=='hads_lab_reference' or r.get('entity_id','').startswith('automation.hads_lab'))
    with app.store._connect() as db:db.execute('UPDATE incidents SET components=? WHERE id=?',(json.dumps([actual,'input_boolean.hads_lab_target','input_boolean.hads_lab_missing']),incident['id']))
    evidence=app.tools.diagnostic_read(incident['id'],{'provider':'automation_inspector','tool':'dependency_report','arguments':{}})
    assert evidence['status']=='available' and evidence['evidence_ids']
    model=scripted_model();model.catalog_mode=True
    job=app.investigations.jobs.enqueue(incident['id'])
    result=await asyncio.to_thread(run_investigation,app.investigations.jobs,job,app.investigations.broker,launcher,model,model='hads-scripted-contract')
    assert result['job']['state']=='hypothesis_ready'
    names=[r['name'] for r in result['job']['reads']]
    assert names[:2]==['hads_list_tools','hads_diagnostic_tool'],names
    return {'passed':True,'actual_Core':True,'actual_pinned_Inspector_builder':True,'Inspector_application_HTTP_listener':False,
            'actual_original_Hermes':True,'catalog_selected_broker_read':True,'model_kind':'local_scripted_not_reasoning',
            'model_requests':len(model.requests),'live_haos':False,'paid_model_calls':0,'read_tools':names,'Inspector_version':APP_VERSION}
