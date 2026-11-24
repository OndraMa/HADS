"""P0 broker reads actual Core on demand, not prepared snapshots."""
import asyncio
from pathlib import Path
import time

from core_contract_probe import main
from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import BrokerDenied, EvidenceBroker


async def exercise(hass,path,nonce,token,user,client,trace,*,core_reader,ws_reader):
    store=IncidentStore(Path(path)/'broker.sqlite3')
    incident=store.open_incident('automation_reference','Testovací automatizace nezapnula cíl.',
        ['automation.hads_lab_reference'],time.time())
    broker=EvidenceBroker(store,core=core_reader,core_ws=ws_reader)
    async def read(name,arguments):
        return await asyncio.to_thread(broker.read,incident['id'],name,arguments)
    results=[]
    for name,args in [('hads_get_incident',{}),('hads_get_core_status',{}),
        ('hads_get_automation_config',{'automation_id':'hads_lab_reference'}),
        ('hads_get_automation_traces',{'automation_id':'hads_lab_reference'})]:
        result=await read(name,args)
        assert result['status']=='available',result
        results.append(result)
    runs=results[-1]['data']
    result=await read('hads_get_automation_trace',{'automation_id':'hads_lab_reference','run_id':runs[0]['run_id']})
    assert result['status']=='available',result
    results.append(result)
    assert results[2]['data']['actions'][0]['target']['entity_id']==['input_boolean.hads_lab_missing']
    assert result['data']['steps']
    size=len(store.case(incident['id'])['evidence'])
    await read('hads_get_automation_trace',{'automation_id':'hads_lab_reference','run_id':runs[0]['run_id']})
    assert len(store.case(incident['id'])['evidence'])==size
    unavailable=await read('hads_get_supervisor_status',{})
    assert unavailable['status']=='unavailable' and unavailable['data'] is None
    for name,args in [('shell',{}),('hads_get_addon_logs',{'slug':'../options.json'}),
        ('hads_get_automation_config',{'automation_id':'hads_lab_reference','method':'POST'}),
        ('hads_get_entity_state',{'entity_id':'sensor.secret_token'})]:
        try:await read(name,args)
        except BrokerDenied:pass
        else:raise AssertionError('Unsafe broker request accepted')
    return {'scope':'actual_core_broker_contract','hermes_in_this_test':False,
        'actual_automation_service_executed':False,'read_count':len(results),
        'reads':results,'missing_supervisor':unavailable,'deduplication_verified':True,
        'unsafe_requests_rejected':4,'writes_performed':0}


if __name__=='__main__':
    asyncio.run(asyncio.wait_for(main(exercise),timeout=90))
