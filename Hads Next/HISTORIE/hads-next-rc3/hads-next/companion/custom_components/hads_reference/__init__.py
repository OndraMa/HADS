"""CAS only for an integration-owned reference; never writes automations.yaml.

The native test automation uses this reference as a template. This is a supported
custom integration API, NOT a claim of native automation configuration CAS.
"""
import asyncio
import hashlib
import json
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.helpers.storage import Store

DOMAIN='hads_reference'
MISSING='input_boolean.hads_next_test_missing'
TARGET='input_boolean.hads_next_test_target'
SENSOR='sensor.hads_next_test_reference'
CONFIG_SCHEMA=vol.Schema({vol.Optional(DOMAIN):vol.Schema({})},extra=vol.ALLOW_EXTRA)

async def async_setup(hass,config):
    storage=Store(hass,1,DOMAIN)
    saved=await storage.async_load()
    state=saved or {'revision':0,'entity_id':MISSING,'operations':{}}
    if not isinstance(state,dict) or set(state)!={'revision','entity_id','operations'} or type(state['revision']) is not int or state['revision']<0 or state['entity_id'] not in {MISSING,TARGET} or not isinstance(state['operations'],dict):
        return False
    lock=asyncio.Lock()
    def document():
        return {'id':'hads_next_reference_test','revision':state['revision'],
            'scope':'integration_owned_virtual_test_reference',
            'action':{'service':'input_boolean.turn_on','target':{'entity_id':state['entity_id']}}}
    def publish():hass.states.async_set(SENSOR,state['entity_id'],{'revision':state['revision'],'friendly_name':'HADS test reference'})
    publish()

    @websocket_api.websocket_command({vol.Required('type'):'hads_reference/read'})
    @websocket_api.require_admin
    def read(hass,connection,msg):connection.send_result(msg['id'],document())

    @websocket_api.websocket_command({vol.Required('type'):'hads_reference/cas',
        vol.Required('expected_revision'):vol.All(int,vol.Range(min=0)),
        vol.Required('expected_entity'):vol.In([MISSING,TARGET]),
        vol.Required('entity_id'):vol.In([MISSING,TARGET]),
        vol.Required('operation_id'):vol.All(str,vol.Match(r'^[a-f0-9]{64}$'))})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def cas(hass,connection,msg):
        async with lock:
            fingerprint=hashlib.sha256(json.dumps({k:msg[k] for k in ('expected_revision','expected_entity','entity_id')},sort_keys=True).encode()).hexdigest()
            old=state['operations'].get(msg['operation_id'])
            if old:
                if old['fingerprint']!=fingerprint:connection.send_error(msg['id'],'operation_conflict','Operation identity changed');return
                connection.send_result(msg['id'],old['result']);return
            if state['revision']!=msg['expected_revision'] or state['entity_id']!=msg['expected_entity']:
                connection.send_error(msg['id'],'stale_reference','Reference changed; new plan required');return
            if msg['expected_entity']==msg['entity_id']:
                connection.send_error(msg['id'],'no_change','No change');return
            updated={**state,'entity_id':msg['entity_id'],'revision':state['revision']+1,'operations':dict(state['operations'])}
            result={**document(),'revision':updated['revision'],'action':{'service':'input_boolean.turn_on','target':{'entity_id':updated['entity_id']}}}
            updated['operations'][msg['operation_id']]={'fingerprint':fingerprint,'result':result}
            # Exhaustion fails closed. Never evict an idempotency tombstone.
            if len(updated['operations'])>256:
                connection.send_error(msg['id'],'retention_required','Reference operation budget exhausted');return
            await storage.async_save(updated)
            state.clear();state.update(updated);publish()
            connection.send_result(msg['id'],result)

    websocket_api.async_register_command(hass,read)
    websocket_api.async_register_command(hass,cas)
    return True
