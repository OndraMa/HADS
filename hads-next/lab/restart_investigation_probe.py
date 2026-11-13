"""Actually kills a confined worker after a committed evidence checkpoint."""
import asyncio
import threading
import time

from hads_next.haos_application import Application


async def exercise_restart(path,core,ws,launcher,user,endpoint,models,scripted_class):
    model=scripted_class();models['hads-restart-contract']=model
    app=Application(path/'restart-site',core,core_ws=ws,launcher=launcher)
    app.enroll_owner(user.id)
    app.investigations.provider.configure(endpoint=endpoint,model='hads-restart-contract',api_key='SYNTHETIC_TEST_KEY',consent=True,principal=user.id,mode='bounded')
    case=app.store.open_incident('automation_reference','Test přerušení vyšetřování.',
        ['automation.hads_lab_reference','input_boolean.hads_lab_target'],time.time())
    reached=threading.Event();release=threading.Event()
    def pause(name,result):
        if name=='hads_get_automation_config':reached.set();release.wait(20)
    app.investigations.jobs.after_read=pause
    identity=app.investigations.start(case['id'],user.id)
    assert await asyncio.to_thread(reached.wait,40),'Worker did not reach a persisted evidence checkpoint'
    assert app.investigations.cancel(identity,user.id)
    release.set()
    for _ in range(400):
        if not app.investigations.status()['worker_active']:break
        await asyncio.sleep(.05)
    assert not app.investigations.status()['worker_active']
    attempt=next(row['content'] for row in reversed(app.store.case(case['id'])['records']) if row['kind']=='hermes_worker_attempt')
    assert attempt['error']=='worker_cancelled' and attempt['exit_status']==-9,attempt
    assert len(model.requests)==2
    evidence_before=app.store.case(case['id'])['evidence']
    assert len(evidence_before)==1
    await asyncio.to_thread(app.investigations.zha_observer.close)

    class ResumeModel:
        def __init__(self):self.requests=[]
        def __call__(self,body):
            import json
            self.requests.append(body)
            if len(self.requests)==1:
                message={'role':'assistant','content':None,'tool_calls':[{'id':'cached-config','type':'function',
                    'function':{'name':'hads_get_automation_config','arguments':json.dumps({'automation_id':'hads_lab_reference'})}}]}
                reason='tool_calls'
            else:
                result=json.loads(next(m['content'] for m in reversed(body['messages']) if m.get('role')=='tool'))
                assert result['cached'] is True
                message={'role':'assistant','content':json.dumps({'summary_cs':'Pokračuji z uložené konfigurace; k potvrzení příčiny potřebuji další trace.',
                    'hypotheses':[{'claim':'Chybějící reference je zatím hypotéza.','evidence_ids':result['evidence_ids'],'confidence':'unconfirmed'}],
                    'needed':['Automation Trace'],'next_test_cs':'Získej aktuální trace.','repair_proposal':None})}
                reason='stop'
            return {'id':'resume-test','object':'chat.completion','created':int(time.time()),'model':'hads-restart-contract',
                'choices':[{'index':0,'message':message,'finish_reason':reason}],'usage':{'prompt_tokens':100,'completion_tokens':100,'total_tokens':200}}
    resumed_model=ResumeModel();models['hads-restart-contract']=resumed_model
    restarted=Application(path/'restart-site',core,core_ws=ws,launcher=launcher)
    source_calls=[]
    original=restarted.investigations.broker.read
    def counted(*args,**kwargs):source_calls.append(args[1]);return original(*args,**kwargs)
    restarted.investigations.broker.read=counted
    resumed_id=restarted.investigations.start(case['id'],user.id)
    assert resumed_id==identity
    for _ in range(800):
        job=restarted.investigations.jobs.get(identity)
        if job['state'] in {'waiting_for_source','failed','blocked'} and job['attempts']==2:break
        await asyncio.sleep(.05)
    assert job['state']=='waiting_for_source',job
    assert source_calls==[],'Confirmed read was unnecessarily repeated against Core'
    assert len(resumed_model.requests)==2
    assert restarted.store.case(case['id'])['evidence']==evidence_before
    assert restarted.store.case(case['id'])['incident']['status']=='open'
    for _ in range(100):
        if not restarted.investigations.status()['worker_active']:break
        await asyncio.sleep(.05)
    await asyncio.to_thread(restarted.investigations.zha_observer.close)
    return {'worker_actually_terminated':True,'controller_state_reconstructed':True,
        'terminated_worker_exit_status':attempt['exit_status'],
        'new_worker_resumed':True,'same_job_id':True,'evidence_retained':True,
        'source_reads_after_resume':0,'model_requests_before_interruption':2,'model_requests_after_resume':2,
        'attempts':job['attempts'],'final_state':job['state'],'full_haos_restart_tested':False}
