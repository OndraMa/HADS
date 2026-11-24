"""Original confined Hermes performs two actual Core reads within three calls."""
import asyncio,json,time
from core_hermes_probe import ScriptedModel
from hads_next.haos_application import Application
from hads_next.ai_budget import BudgetExceeded

class TrialModel(ScriptedModel):
    def __call__(self,body):
        self.requests.append(body);turn=len(self.requests);assert body['max_tokens']==512
        results=[json.loads(m['content']) for m in body['messages'] if m.get('role')=='tool']
        if turn==1:name,args='hads_get_incident',{}
        elif turn==2:name,args='hads_get_entity_state',{'entity_id':'input_boolean.hads_lab_target'}
        else:
            assert turn==3
            evidence=sorted({identity for row in results for identity in row['evidence_ids']})
            return self._response({'role':'assistant','content':json.dumps({'summary_cs':'Testovací případ a skutečný stav Core byly přečtené. Výsledek fyzického zařízení není tímto protokolovým testem ověřený.','hypotheses':[],'needed':['Funkční výsledek není předmětem testu rozpočtu.'],'next_test_cs':'Nativní sběr důkazů pokračuje bez dalších modelových požadavků.','repair_proposal':None},ensure_ascii=False)},'stop')
        return self._response({'role':'assistant','content':None,'tool_calls':[{'id':'trial-'+str(turn),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},'tool_calls')

async def exercise_trial(path,core,ws,launcher,user,models,endpoint):
    model=TrialModel();models['hads-trial-contract']=model
    app=Application(path/'trial-budget',core,core_ws=ws,launcher=launcher);app.enroll_owner(user.id)
    try:
        app.investigations.provider.configure(endpoint=endpoint,model='hads-trial-contract',api_key='SYNTHETIC_TEST_KEY',consent=True,principal=user.id)
        case=app.store.open_incident('manual_functional','Izolovaný test omezeného vyšetřování.',['input_boolean.hads_lab_target'],time.time())
        assert app.investigations.start(case['id'],user.id,automatic=True) is None
        assert len(model.requests)==0
        identity=app.investigations.start(case['id'],user.id)
        for _ in range(800):
            job=app.investigations.jobs.get(identity)
            if job['state'] in {'waiting_for_source','hypothesis_ready','blocked','waiting_for_user'}:break
            await asyncio.sleep(.05)
        assert job['state']=='waiting_for_source',{'job':job,'requests':len(model.requests)}
        assert job['model_calls']==3 and len(model.requests)==3
        assert [row['name'] for row in job['reads']]==['hads_get_incident','hads_get_entity_state']
        try:app.investigations.provider.sender()[1]({'messages':[]})
        except BudgetExceeded:pass
        else:raise AssertionError('Fourth request was allowed')
        assert len(model.requests)==3
        assert app.store.case(case['id'])['incident']['status']=='open'
        return {'passed':True,'scope':'actual_original_Hermes_actual_Core_scripted_HTTPS_model','live_haos':False,'paid_model_calls':0,'scripted_model_calls':3,'actual_read_tools':[r['name'] for r in job['reads']],'trial_auto_start_refused':True,'fourth_model_call_refused':True,'functional_incident_not_closed':True,'rolling_24h_calls_remaining':0}
    finally:app.system.automatic.close();app.detection.close();app.investigations.zha_observer.close()
