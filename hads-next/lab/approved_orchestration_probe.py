"""Original Hermes -> provider reports -> exact owner approval -> wire repair.

Reuses the same anonymous provider contract fixture as the offline suite.
The original confined agent and controller are real. Provider processes, Core
and physical observations in THIS additional probe are explicit test doubles;
the separate Core/Inspector probe exercises those actual upstream components.
"""
import asyncio
import copy
import json
import threading

from hads_next.addon_server import Server
from hads_next.hermes_runtime import run_investigation
from hads_next.connector_transport import ReportHTTP
from hads_next.tool_registry import fingerprint
from orchestration_wire_fixture import OrchestratedWire


async def exercise(launcher,scripted_model):
    fixture=OrchestratedWire('test_A_B_real_wire_reports_discovery_iteration_and_approved_config_change')
    fixture.setUp();app=fixture.app;controller=None
    try:
        for provider in ('automation_inspector','hadocs'):
            app.tools._http(provider,ReportHTTP(fixture.url,allow_private_http=True))
        fixture.receipt({'config':copy.deepcopy(fixture.config),'config_hash':fingerprint(fixture.config)})
        reason='Původní Hermes navrhuje jednu doloženou světelnou referenci; souhlas vydá pouze vlastník.'

        class Model(scripted_model):
            def __call__(self,body):
                self.requests.append(body)
                results=[json.loads(m['content']) for m in body['messages'] if m.get('role')=='tool']
                turn=len(self.requests)
                if turn==1:name,args='hads_list_tools',{}
                elif turn==2:
                    assert any(t['provider']=='ha_mcp' and t['name']=='ha_config_set_automation' and t['repair_operation_implemented'] for t in results[-1]['data']['tools'])
                    name,args='hads_get_tool_schema',{'provider':'ha_mcp','tool':'ha_config_set_automation'}
                elif turn==3:
                    assert results[-1]['data']['effect']=='write'
                    name,args='hads_diagnostic_tool',{'provider':'automation_inspector','tool':'dependency_report','arguments':{}}
                elif turn==4:
                    assert results[-1]['status']=='available' and results[-1]['evidence_ids']
                    name,args='hads_diagnostic_tool',{'provider':'ha_mcp','tool':'ha_config_get_automation','arguments':{'entity_id':fixture.auto}}
                elif turn==5:
                    assert results[-1]['data']['config_hash']==fingerprint(fixture.config)
                    config=copy.deepcopy(fixture.config);config['actions'][0]['target']['entity_id']=fixture.new
                    ids=sorted({e for r in results for e in r['evidence_ids']})
                    name,args='hads_propose_tool_repair',{'provider':'ha_mcp','tool':'ha_config_set_automation',
                        'parameters':{'entity_id':fixture.auto,'config':config,'config_hash':fingerprint(fixture.config),'run_actions':False,'wait':True},
                        'evidence_ids':ids,'reason':reason}
                else:
                    assert turn==6 and results[-1]['status']=='proposal_recorded' and results[-1]['approval_granted'] is False
                    assert fixture.writes==[],'Original Hermes must never write or approve'
                    ids=sorted({e for r in results for e in r['evidence_ids']})
                    conclusion={'summary_cs':'Inspector a konfigurace doložily chybnou světelnou referenci. Nezávislý plán čeká na vlastníka.',
                        'hypotheses':[{'claim':'Neplatná reference po doložené změně identity.','evidence_ids':ids,'confidence':'supported'}],
                        'needed':[],'next_test_cs':'Vlastník posoudí konkrétní plán; nic nebylo zapsané.','repair_proposal':None}
                    return self._response({'role':'assistant','content':json.dumps(conclusion,ensure_ascii=False)},'stop')
                return self._response({'role':'assistant','content':None,'tool_calls':[{'id':'approved-'+str(turn),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'tool_calls')

        model=Model();job=app.investigations.jobs.enqueue(fixture.case['id'])
        result=await asyncio.to_thread(run_investigation,app.investigations.jobs,job,app.investigations.broker,launcher,model,model='hads-scripted-provider-repair')
        assert result['job']['state']=='hypothesis_ready',result['job']
        assert fixture.writes==[]
        plan=next(p for p in app.repairs.plans(fixture.case['id']) if p['document']['reason']==reason)
        controller=Server(('127.0.0.1',0),app,ingress_peer='127.0.0.1')
        threading.Thread(target=controller.serve_forever,daemon=True).start()
        origin='http://127.0.0.1:'+str(controller.server_port)
        import aiohttp
        async with aiohttp.ClientSession(headers={'X-Remote-User-Id':'owner-fixture'}) as client:
            form={'plan_id':plan['plan_id'],'decision':'approve','exclusive':'yes'}
            async with client.post(origin+'/tool-repair/decide',data={**form,'csrf':'forged'},allow_redirects=False) as response:assert response.status==403
            assert fixture.writes==[]
            async with client.post(origin+'/tool-repair/decide',data={**form,'csrf':controller.csrf},allow_redirects=False) as response:assert response.status==303,await response.text()
            assert len(fixture.writes)==1 and fixture.config['actions'][0]['target']['entity_id']==fixture.new
            assert app.store.case(fixture.case['id'])['incident']['status']=='open'
            fixture.now+=1;app.detection.health.update(state='listening',heartbeat_at=fixture.now,continuous_since=fixture.now)
            app.repairs.trigger_coverage=fixture.now;app.repairs.trigger_heartbeat=fixture.now
            app.repairs.on_trigger({'data':{'entity_id':fixture.auto},'time_fired':fixture.iso(fixture.now),'context':{'id':'wire-functional-context'}})
            fixture.now+=1;app.repairs.observe_state({'entity_id':fixture.new,'state':'on','context':{'id':'wire-functional-context'}},fixture.now)
            fixture.now+=1
            async with client.post(origin+'/repair/physical',data={'plan_id':plan['plan_id'],'csrf':controller.csrf},allow_redirects=False) as response:assert response.status==303
            fixture.now+=32;app.detection.health['heartbeat_at']=fixture.now;app.repairs.trigger_heartbeat=fixture.now
            report=app.approved_tools.verify(plan['plan_id'])
            assert report['classification']=='Vyřešeno a ověřeno'
            assert app.store.case(fixture.case['id'])['incident']['status']=='resolved'
            assert len(fixture.writes)==1
        return {'passed':True,'scope':'actual_original_Hermes_controller_and_anonymous_provider_wire_fixture',
            'actual_original_Hermes':True,'actual_owner_HTTP_and_CSRF_boundary':True,'analyst_write_count':0,'approved_write_count':1,
            'repair_operation':'ha_mcp.ha_config_set_automation','independent_planner_used':True,'functional_report_classification':report['classification'],
            'model_kind':'local_scripted_not_reasoning','model_requests':len(model.requests),'paid_model_calls':0,'live_haos':False,
            'actual_installed_provider_processes':False,'physical_observations':'injected_anonymous_fixture','watch_clock':'controlled_offline_clock',
            'production_backup_verifier':False,'read_tools':[r['name'] for r in result['job']['reads']]}
    finally:
        if controller:
            await asyncio.to_thread(controller.shutdown);controller.server_close()
        fixture.doCleanups()
