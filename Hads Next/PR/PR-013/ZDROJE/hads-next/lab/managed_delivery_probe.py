"""Actual Core, controller routes, CAS and functional verification; scripted LLM."""
import asyncio,json,time
from core_hermes_probe import ScriptedModel

class ManagedModel(ScriptedModel):
    def __call__(self,body):
        self.requests.append(body);turn=len(self.requests)
        results=[json.loads(m['content']) for m in body['messages'] if m.get('role')=='tool']
        if turn==1:name,args='hads_get_incident',{}
        elif turn==2:name,args='hads_get_owned_reference',{}
        elif turn==3:name,args='hads_get_automation_traces',{'automation_id':'hads_next_reference_test'}
        elif turn==4:name,args='hads_get_automation_trace',{'automation_id':'hads_next_reference_test','run_id':results[-1]['data'][0]['run_id']}
        elif turn==5:name,args='hads_get_entity_state',{'entity_id':'input_boolean.hads_next_test_missing'}
        elif turn==6:name,args='hads_get_entity_state',{'entity_id':'input_boolean.hads_next_test_target'}
        else:
            evidence=sorted({identity for row in results for identity in row['evidence_ids']})
            return self._response({'role':'assistant','content':json.dumps({'summary_cs':'Testovací automatizace se spustila, ale vlastní reference ukazuje na chybějící virtuální cíl.',
                'hypotheses':[{'claim':'Chybná vlastní reference.','evidence_ids':evidence,'confidence':'supported'}],
                'needed':[],'next_test_cs':'Schval přesnou opravu vlastní testovací reference a stiskni testovací tlačítko.',
                'repair_proposal':{'operation':'replace_managed_reference','target':'hads_next_reference_test','change':{'from':'input_boolean.hads_next_test_missing','to':'input_boolean.hads_next_test_target'},'reason':'Aktuální companion reference a neúspěšná trace dokládají chybný virtuální cíl.','evidence_ids':evidence}},ensure_ascii=False)},'stop')
        return self._response({'role':'assistant','content':None,'tool_calls':[{'id':'managed-'+str(turn),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'tool_calls')

async def exercise_managed(hass,core,ws,launcher,path,user,models,endpoint):
    import aiohttp
    from hads_next.haos_application import Application
    from hads_next.addon_server import Server
    from hads_next.managed_repair import TARGET,MISSING
    from hads_next.repair import RepairBlocked
    import threading
    app=Application(path/'delivery',core,core_ws=ws,launcher=launcher)
    controller=Server(('127.0.0.1',0),app,ingress_peer='127.0.0.1')
    thread=threading.Thread(target=controller.serve_forever,daemon=True);thread.start()
    ui='http://127.0.0.1:'+str(controller.server_port)
    try:
        app.enroll_owner(user.id)
        model=ManagedModel();models['hads-managed-contract']=model
        app.investigations.provider.configure(endpoint=endpoint,model='hads-managed-contract',api_key='SYNTHETIC_TEST_KEY',consent=True,principal=user.id,mode='bounded')
        app.detection.consent(True,user.id)
        app.detection.configure({'entity_id':TARGET,'kind':'response','trigger_entity':'input_button.hads_next_test_run','automation_entity':'automation.hads_next_reference_test','expected':'on','grace_seconds':1},user.id)
        for _ in range(100):
            if app.detection.health['state']=='listening':break
            await asyncio.sleep(.1)
        assert app.detection.health['state']=='listening'
        await hass.services.async_call('input_button','press',{'entity_id':'input_button.hads_next_test_run'},blocking=True)
        for _ in range(100):
            cases=[x for x in app.snapshot()['cases'] if x['kind']=='functional_monitor']
            if cases:break
            await asyncio.sleep(.1)
        assert cases,'Real state stream must detect the failed native automation response'
        incident=cases[0]['id'];assert hass.states.get(TARGET).state=='off'
        for _ in range(1800):
            jobs=app.investigations.for_case(incident)
            if jobs and jobs[0]['state'] in {'hypothesis_ready','blocked','failed'}:break
            await asyncio.sleep(.1)
        assert jobs[0]['state']=='hypothesis_ready',jobs[0]
        suggestion=jobs[0]['conclusion']['repair_suggestion'];assert suggestion['status']=='supported_managed_candidate',suggestion
        await asyncio.to_thread(app.repairs.configure,True,user.id)
        for _ in range(100):
            if app.repairs.trigger_coverage:break
            await asyncio.sleep(.1)
        async with aiohttp.ClientSession(headers={'X-Remote-User-Id':user.id}) as client:
            async with client.post(ui+'/repair/prepare',data={'csrf':controller.csrf,'incident_id':incident},allow_redirects=False) as response:
                assert response.status==303,await response.text()
            plan=app.repairs.plans(incident)[0];identity=plan['plan_id']
            async with client.get(ui+'/case/'+incident) as response:assert 'Schválit opravu' in await response.text()
            # Real HTTP owner/CSRF boundary, no token or direct writer route.
            async with client.post(ui+'/repair/decide',data={'csrf':'forged','plan_id':identity,'decision':'approve'},allow_redirects=False) as response:assert response.status==403
            async with client.post(ui+'/repair/decide',data={'csrf':controller.csrf,'plan_id':identity,'decision':'approve'},allow_redirects=False) as response:assert response.status==303,await response.text()
            assert hass.states.get('sensor.hads_next_test_reference').state==TARGET
            async with client.post(ui+'/repair/decide',data={'csrf':controller.csrf,'plan_id':identity,'decision':'approve'},allow_redirects=False) as response:assert response.status==409
        # A write response alone must not resolve anything.
        assert app.store.case(incident)['incident']['status']=='open'
        await hass.services.async_call('input_button','press',{'entity_id':'input_button.hads_next_test_run'},blocking=True)
        for _ in range(180):
            if app.store.case(incident)['incident']['status']=='resolved':break
            await asyncio.sleep(.1)
        assert hass.states.get(TARGET).state=='on'
        assert app.store.case(incident)['incident']['status']=='resolved',app.repairs.last_error
        from hads_next.verification import FunctionalVerifier
        execution=app.repairs.engine().execution(identity)
        reports=FunctionalVerifier(app.store.db_path).reports(execution.execution_id)
        # Server CAS rejects a stale concurrent write; it is never forced.
        current=await asyncio.to_thread(ws.transport,{'type':'hads_reference/read'})
        try:
            await asyncio.to_thread(ws.transport,{'type':'hads_reference/cas','expected_revision':0,'expected_entity':MISSING,'entity_id':TARGET,'operation_id':'e'*64})
            raise AssertionError('stale CAS unexpectedly succeeded')
        except Exception as error:
            assert not isinstance(error,AssertionError)
        assert await asyncio.to_thread(ws.transport,{'type':'hads_reference/read'})==current
        rollback=await asyncio.to_thread(app.repairs.rollback,identity,user.id)
        await asyncio.to_thread(app.repairs.decide,rollback.plan_id,'approve',user.id)
        await asyncio.to_thread(app.repairs.verify_pending)
        assert hass.states.get('sensor.hads_next_test_reference').state==MISSING
        await hass.services.async_call('input_boolean','turn_off',{'entity_id':TARGET},blocking=True)
        await hass.services.async_call('input_button','press',{'entity_id':'input_button.hads_next_test_run'},blocking=True)
        for _ in range(60):
            if app.store.case(incident)['incident']['status']=='open':break
            await asyncio.sleep(.1)
        recurrence=app.store.case(incident)['incident']['status']=='open'
        # Independent concurrent clients cannot both commit revision 2.
        before=await asyncio.to_thread(ws.transport,{'type':'hads_reference/read'})
        command={'type':'hads_reference/cas','expected_revision':before['revision'],'expected_entity':MISSING,'entity_id':TARGET,'operation_id':'c'*64}
        competing={**command,'operation_id':'d'*64}
        concurrent=await asyncio.gather(asyncio.to_thread(ws.transport,command),asyncio.to_thread(ws.transport,competing),return_exceptions=True)
        assert sum(isinstance(r,dict) for r in concurrent)==1,concurrent
        committed=await asyncio.to_thread(ws.transport,{'type':'hads_reference/read'})
        assert committed['revision']==before['revision']+1
        winner=command if isinstance(concurrent[0],dict) else competing
        assert await asyncio.to_thread(ws.transport,winner)==committed
        assert (await asyncio.to_thread(ws.transport,{'type':'hads_reference/read'}))['revision']==committed['revision']
        return {'server_concurrent_CAS_one_winner':True,'server_idempotency_tombstone_survives_replay':True,'scope':'actual_Core_container_managed_reference' ,'live_haos':False,'model_kind':'scripted_protocol_test','detected_from_native_state_subscription':True,'investigation_started_automatically_after_owner_opt_in':True,
            'model_calls':len(model.requests),'additional_native_reads':len(jobs[0]['reads']),'suggestion':suggestion,'immutable_plan':plan,
            'csrf_forgery_denied':True,'approval_replay_denied':True,'stale_server_CAS_denied':True,'actual_functional_report':reports[-1],
            'rollback_restored_exact_reference':True,'recurrence_reopened_original_case':recurrence,'passed':recurrence}
    finally:
        await asyncio.to_thread(controller.shutdown);controller.server_close()
