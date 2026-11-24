"""Actual Core contract probe. Never connects to an existing HA installation.

Creates an ephemeral configuration and a real HA user/token in memory. No HA
objects, handlers, validation, authentication or service execution are mocked.
This is Core in a container, not HAOS, Supervisor or a completed HADS repair.
"""
import asyncio
from importlib.metadata import distributions, version
import json
import os
from pathlib import Path
import resource
import tempfile
import uuid

import aiohttp
import yaml
from homeassistant import bootstrap, config as ha_config, config_entries, core_config, loader
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from hads_next.observability import CoreReader, CoreWSReader, NativeHTTP
from exercise_repair import exercise


async def main():
    assert version('homeassistant') == '2026.11.0'
    inventory = Path(__file__).resolve().parents[1] / 'docs/evidence/core-lab-dependencies.txt'
    actual_dependencies = '\n'.join(sorted(item.metadata['Name']+'=='+item.version for item in distributions())) + '\n'
    assert actual_dependencies == inventory.read_text(), 'Dependency inventory differs from the tested image'
    nonce=uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='hads-core-lab-') as directory:
        path=Path(directory)
        automation={'id':'hads_lab_reference','alias':'HADS laboratory reference',
            'triggers':[{'trigger':'state','entity_id':'input_button.hads_lab_run'}],
            'conditions':[], 'actions':[{'action':'input_boolean.turn_on',
                'target':{'entity_id':'input_boolean.hads_lab_missing'}}]}
        (path/'automations.yaml').write_text(yaml.safe_dump([automation]))
        (path/'configuration.yaml').write_text('''homeassistant:
  name: HADS isolated lab '''+nonce+'''
  latitude: 0
  longitude: 0
  elevation: 0
  unit_system: metric
  time_zone: UTC
  auth_mfa_modules: []
http:
  server_host: 127.0.0.1
  server_port: 8123
api:
websocket_api:
config:
automation: !include automations.yaml
input_boolean:
  hads_lab_target:
    initial: false
input_button:
  hads_lab_run:
''')
        hass=HomeAssistant(directory)
        loader.async_setup(hass)
        hass.config.skip_pip=True
        config=await ha_config.async_hass_config_yaml(hass)
        hass.config_entries=config_entries.ConfigEntries(hass,config)
        assert await bootstrap.async_load_base_functionality(hass)
        try:
            for domain in bootstrap.CORE_INTEGRATIONS:
                assert await async_setup_component(hass,domain,config),domain
            await core_config.async_process_ha_core_config(hass,config['homeassistant'])
            for domain in ('homeassistant','persistent_notification','http','websocket_api','api','config','input_boolean','input_button','automation'):
                assert await async_setup_component(hass,domain,config),domain
            user=await hass.auth.async_create_user('HADS lab operator',group_ids=['system-admin'])
            refresh=await hass.auth.async_create_refresh_token(user, client_id='https://hads-lab.invalid/')
            token=hass.auth.async_create_access_token(refresh)
            await hass.async_start()
            await hass.async_block_till_done()
            # Token is private to this process. It is never printed or exported.
            async with aiohttp.ClientSession(headers={'Authorization':'Bearer '+token}) as client:
                base='http://127.0.0.1:8123'
                async with client.get(base+'/api/config') as r:
                    assert r.status==200
                    info=await r.json()
                    assert info['version']=='2026.11.0'
                    assert info['location_name']=='HADS isolated lab '+nonce
                endpoint=base+'/api/config/automation/config/hads_lab_reference'
                async with client.get(endpoint) as r:
                    assert r.status==200
                    original=await r.json()
                    assert original['actions'][0]['target']['entity_id']=='input_boolean.hads_lab_missing'
                # Invalid request must fail validation without changing the file.
                before=(path/'automations.yaml').read_bytes()
                async with client.post(endpoint,json={'invalid':True}) as r:
                    assert r.status==400
                assert (path/'automations.yaml').read_bytes()==before
                async with client.post(base+'/api/services/input_button/press',json={'entity_id':'input_button.hads_lab_run'}) as r:
                    assert r.status==200
                await hass.async_block_till_done()
                async with client.get(base+'/api/states/input_boolean.hads_lab_target') as r:
                    state=await r.json()
                    assert state['state']=='off','Broken reference must not operate the target'
                reader = CoreReader(NativeHTTP(base, token, allow_local_http=True))
                native_config = await asyncio.to_thread(reader.config)
                assert native_config['version'] == '2026.11.0'
                assert (await asyncio.to_thread(reader.states, 'input_boolean.hads_lab_target'))['state'] == 'off'

                async def ws_command(command):
                    async with client.ws_connect(base+'/api/websocket') as ws:
                        assert (await ws.receive_json())['type'] == 'auth_required'
                        await ws.send_json({'type':'auth','access_token':token})
                        assert (await ws.receive_json())['type'] == 'auth_ok'
                        await ws.send_json({**command, 'id': 1})
                        result = await ws.receive_json()
                        assert result['type'] == 'result' and result['id'] == 1 and result['success'], result
                        return result['result']

                loop = asyncio.get_running_loop()
                ws_reader = CoreWSReader(lambda command: asyncio.run_coroutine_threadsafe(ws_command(command), loop).result(15))
                users = await asyncio.to_thread(ws_reader.auth_users)
                assert users is not None, ws_reader.status.last_error
                actual_user = next(item for item in users if item['id'] == user.id)
                assert actual_user['is_active'] and 'system-admin' in actual_user['group_ids']
                assert isinstance(await asyncio.to_thread(ws_reader.entity_registry), list)
                assert isinstance(await asyncio.to_thread(ws_reader.device_registry), list)
                traces = await asyncio.to_thread(ws_reader.traces, 'automation', 'hads_lab_reference')
                assert traces, ws_reader.status.last_error
                trace = await asyncio.to_thread(ws_reader.trace, 'automation', 'hads_lab_reference', traces[0]['run_id'])
                assert isinstance(trace, dict), ws_reader.status.last_error
                repair = await exercise(hass, path, nonce, token, user, client, trace)
            async with aiohttp.ClientSession() as anonymous:
                async with anonymous.get(base+'/api/config') as r:
                    assert r.status==401
            print(json.dumps({'scope':'actual_core_container','core_version':version('homeassistant'),
                'live_haos':False,'supervisor_tested':False,'approved_repair':True,
                'native_api_authentication':True,'automation_config_read':True,
                'invalid_config_rejected_without_write':True,'broken_automation_does_not_operate_target':True,
                'actual_core_auth_list_and_registries':True,'actual_automation_trace':True,
                'native_http_reader':True,'repair':repair,
                'isolated_configuration':True, 'dependency_inventory_verified':True, 'runtime_uid':os.geteuid(),
                'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                'passed':True}))
        finally:
            await hass.async_stop(force=True)


if __name__=='__main__':
    asyncio.run(asyncio.wait_for(main(), timeout=90))
