"""Useful native enable-state operation, actual Core; physical lamp is virtual."""
import asyncio,json,threading,time
from core_hermes_probe import ScriptedModel

class NativeLightingModel(ScriptedModel):
    def __call__(self,body):
        self.requests.append(body);turn=len(self.requests)
        results=[json.loads(m['content']) for m in body['messages'] if m.get('role')=='tool']
        if turn==1:name,args='hads_get_incident',{}
        elif turn==2:name,args='hads_get_entity_state',{'entity_id':'automation.entry_lighting'}
        elif turn==3:name,args='hads_get_automation_config',{'automation_id':'entry_lighting'}
        elif turn==4:name,args='hads_get_entity_state',{'entity_id':'light.entry_lamp'}
        elif turn==5:
            evidence=sorted({identity for row in results for identity in row['evidence_ids']})
            name,args='hads_select_investigator',{'role':'repair_planner','task':'Posuď pouze vypnutou jednoduchou světelnou automatizaci a předlož návrh bez jakéhokoli zápisu.','handoff':{'summary_cs':'Core potvrzuje vypnutí a konfiguraci s jedinou světelnou akcí.','evidence_ids':evidence,'uncertainties':['Ověření fyzického výsledku musí potvrdit vlastník.']}}
        else:
            evidence=sorted({identity for row in results for identity in row['evidence_ids']})
            return self._response({'role':'assistant','content':json.dumps({'summary_cs':'Očekávaná světelná automatizace je vypnutá. Její konfigurace obsahuje konkrétní světlo a stavový trigger.','hypotheses':[{'claim':'Vypnutí blokuje příjem budoucích triggerů.','evidence_ids':evidence,'confidence':'supported'}],'needed':[],'next_test_cs':'Vlastník může schválit opětovnou aktivaci a vyvolat skutečný trigger.','repair_proposal':{'operation':'enable_lighting_automation','target':'automation.entry_lighting','reason':'Čerstvý stav off a explicitní záměr vlastníka.','evidence_ids':evidence}},ensure_ascii=False)},'stop')
        return self._response({'role':'assistant','content':None,'tool_calls':[{'id':'native-'+str(turn),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'tool_calls')

async def exercise_practical(hass,core,ws,launcher,path,user,models,endpoint,token):
    import aiohttp
    from hads_next.haos_application import Application
    from hads_next.addon_server import Server
    from hads_next.native_repair import AutomationStateTransport
    from hads_next.verification import FunctionalVerifier
    writer=AutomationStateTransport('http://127.0.0.1:8123',token,loopback=True)
    app=Application(path/'practical',core,core_ws=ws,launcher=launcher,automation_writer=writer)
    controller=Server(('127.0.0.1',0),app,ingress_peer='127.0.0.1');thread=threading.Thread(target=controller.serve_forever,daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(controller.server_port)
    try:
        app.enroll_owner(user.id)
        model=NativeLightingModel();models['hads-native-lighting']=model
        app.investigations.provider.configure(endpoint=endpoint,model='hads-native-lighting',api_key='SYNTHETIC_TEST_KEY',consent=True,principal=user.id)
        await asyncio.to_thread(app.repairs.allow_automation,'automation.entry_lighting',user.id)
        await hass.services.async_call('automation','turn_off',{'entity_id':'automation.entry_lighting','stop_actions':False},blocking=True)
        app.detection.consent(True,user.id)
        await asyncio.to_thread(app.system.inspect)
        cases=[c for c in app.snapshot()['cases'] if c['kind']=='automation_disabled'];assert len(cases)==1,app.snapshot()['cases'];identity=cases[0]['id']
        for _ in range(1400):
            jobs=app.investigations.for_case(identity)
            if jobs and jobs[0]['state'] in {'hypothesis_ready','blocked','failed'}:break
            await asyncio.sleep(.1)
        assert jobs[0]['state']=='hypothesis_ready',jobs[0]
        assert jobs[0]['conclusion']['repair_suggestion']['status']=='supported_native_candidate',jobs[0]['conclusion']
        config_before=await asyncio.to_thread(core.automation_config,'173100000001')
        async with aiohttp.ClientSession(headers={'X-Remote-User-Id':user.id}) as client:
            form={'csrf':controller.csrf,'incident_id':identity,'entity_id':'automation.entry_lighting','exclusive':'yes'}
            async with client.post(origin+'/repair/native_prepare',data=form,allow_redirects=False) as response:assert response.status==303,await response.text()
            plan=app.repairs.plans(identity)[0];plan_id=plan['plan_id'];assert plan['document']['operation']=='core.enable_lighting_automation'
            async with client.post(origin+'/repair/decide',data={'csrf':controller.csrf,'plan_id':plan_id,'decision':'approve'},allow_redirects=False) as response:assert response.status==303,await response.text()
            assert hass.states.get('automation.entry_lighting').state=='on';assert hass.states.get('light.entry_lamp').state=='off'
            assert app.store.case(identity)['incident']['status']=='open'
            # A premature user confirmation cannot manufacture a later physical observation.
            async with client.post(origin+'/repair/physical',data={'csrf':controller.csrf,'plan_id':plan_id},allow_redirects=False) as response:assert response.status==303
            await hass.services.async_call('input_button','press',{'entity_id':'input_button.entry_button'},blocking=True)
            await asyncio.sleep(11)
            assert hass.states.get('light.entry_lamp').state=='on'
            assert app.store.case(identity)['incident']['status']=='open','Premature confirmation incorrectly resolved the case'
            async with client.post(origin+'/repair/physical',data={'csrf':controller.csrf,'plan_id':plan_id},allow_redirects=False) as response:assert response.status==303,await response.text()
            for _ in range(60):
                if app.store.case(identity)['incident']['status']=='resolved':break
                await asyncio.sleep(.2)
            assert app.store.case(identity)['incident']['status']=='resolved',app.detection.health
            assert await asyncio.to_thread(core.automation_config,'173100000001')==config_before
            execution=app.repairs.native_engine(app.repairs.plan(plan_id)).execution(plan_id)
            reports=FunctionalVerifier(app.store.db_path).reports(execution.execution_id)
            rollback=await asyncio.to_thread(app.repairs.rollback,plan_id,user.id)
            async with client.post(origin+'/repair/decide',data={'csrf':controller.csrf,'plan_id':rollback.plan_id,'decision':'approve'},allow_redirects=False) as response:assert response.status==303,await response.text()
            assert hass.states.get('automation.entry_lighting').state=='off'
            assert hass.states.get('light.entry_lamp').state=='on','Rollback must not claim to undo physical effects'
            session=app.acceptance.create(user.id,isolated_confirmed=True)
            app.acceptance.run(session,'verification',user.id,{'incident_id':identity})
            for _ in range(30):
                if not app.acceptance.lock.locked():break
                await asyncio.sleep(.1)
            report=app.acceptance.export(session);assert report['steps'][10]['status']=='passed',report
            assert token not in json.dumps(report) and 'light.entry_lamp' not in json.dumps(report)
        return {'scope':'actual_Core_native_lighting_automation','model_kind':'scripted_protocol_test','useful_operation':'core.enable_lighting_automation','no_HADS_virtual_reference_used':True,'native_state_service_applied':True,'native_config_unchanged':True,'independent_proposal_validated':True,'premature_confirmation_did_not_resolve':True,'actual_context_and_watch_report':reports[-1],'owner_confirmation':'simulated_authenticated_operator_for_virtual_light','physical_lamp_tested':False,'rollback_disabled_future_triggers_only':True,'anonymized_acceptance_export':True,'system_diagnostics_detected_unexpected_disable':True,'model_calls':len(model.requests),'resources_after_investigation':report['resources'],'core_read_latency_ms':report['core_read_latency_ms'],'passed':True}
    finally:
        await asyncio.to_thread(controller.shutdown);controller.server_close()
