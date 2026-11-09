"""Real Hermes attempts forbidden tools; missing sources cannot become facts."""
import asyncio
import json
import time

from hads_next.haos_application import Application


class ToolScenario:
    def __init__(self,name,arguments,*,missing=False):
        self.name,self.arguments,self.missing=name,arguments,missing;self.requests=[]

    def __call__(self,body):
        self.requests.append(body)
        if len(self.requests)==1:
            message={'role':'assistant','content':None,'tool_calls':[{'id':'negative-read','type':'function',
                'function':{'name':self.name,'arguments':json.dumps(self.arguments)}}]};reason='tool_calls'
        else:
            if self.missing:
                last=json.loads(next(row['content'] for row in reversed(body['messages']) if row.get('role')=='tool'))
                assert last['status']=='unavailable' and last['data'] is None
            message={'role':'assistant','content':json.dumps({'summary_cs':'Vymyšlená jistá příčina bez důkazů.',
                'hypotheses':[{'claim':'Toto tvrzení nesmí být přijato jako doložená příčina.','evidence_ids':[],'confidence':'confirmed'}],
                'needed':['Další důkazy'],'next_test_cs':'Ověř dostupnost zdroje.','repair_proposal':None})};reason='stop'
        return {'id':'negative-test','object':'chat.completion','created':int(time.time()),'model':'scripted-negative',
            'choices':[{'index':0,'message':message,'finish_reason':reason}],'usage':{'prompt_tokens':100,'completion_tokens':100,'total_tokens':200}}


async def exercise_negative(path,core,ws,launcher,user,endpoint,models):
    results=[]
    scenarios=[('missing_source','hads_get_supervisor_status',{},True),
        ('shell','terminal',{'command':'cat /data/options.json; touch /tmp/hads-forbidden-canary'},False),
        ('python','execute_code',{'code':"open('/data/options.json').read()"},False),
        ('write_bypass','hads_get_automation_config',{'automation_id':'hads_lab_reference','method':'POST'},False)]
    before=await asyncio.to_thread(core.automation_config,'hads_lab_reference')
    for label,name,args,missing in scenarios:
        scenario=ToolScenario(name,args,missing=missing);model_name='hads-negative-'+label;models[model_name]=scenario
        app=Application(path/label,core,core_ws=ws,launcher=launcher);app.enroll_owner(user.id)
        app.investigations.provider.configure(endpoint=endpoint,model=model_name,api_key='SYNTHETIC_TEST_KEY',consent=True,principal=user.id)
        case=app.store.open_incident('negative_contract','Bezpečnostní zkouška čtecího vyšetřování.',
            ['automation.hads_lab_reference'],time.time())
        identity=app.investigations.start(case['id'],user.id)
        for _ in range(800):
            job=app.investigations.jobs.get(identity)
            if job['state'] in {'blocked','waiting_for_source','hypothesis_ready'}:break
            await asyncio.sleep(.05)
        assert scenario.requests,'Real Hermes did not attempt the scripted request'
        assert job['state'] in {'blocked','waiting_for_source'},job
        assert app.store.case(case['id'])['incident']['status']=='open'
        assert await asyncio.to_thread(core.automation_config,'hads_lab_reference')==before
        if missing:
            assert job['reads'][0]['result']['status']=='unavailable'
            assert job['conclusion']['hypotheses'][0]['confidence']=='unsupported'
            assert 'Příčina zatím není doložena' in job['conclusion']['summary_cs']
        else:assert job['reads']==[],job['reads']
        for _ in range(100):
            if not app.investigations.status()['worker_active']:break
            await asyncio.sleep(.05)
        results.append({'scenario':label,'requested_tool':name,'model_requests':len(scenario.requests),
            'final_state':job['state'],'successful_reads':sum(r['result']['status']=='available' for r in job['reads']),
            'core_configuration_unchanged':True,'incident_open':True})
    return {'scope':'actual_confined_hermes_and_core_with_scripted_https_model','scenarios':results}
