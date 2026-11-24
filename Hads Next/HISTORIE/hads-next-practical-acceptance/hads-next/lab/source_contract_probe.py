"""Actual Core diagnostic reads with virtual devices; no radio/Zigbee hardware.

Recorder, logbook, traces, native WS authentication/event delivery and REST are
real. The zha_event is explicitly injected by this isolated fixture. Music
Assistant and Supervisor are not running here and remain separate contracts.
"""
import asyncio
from datetime import datetime,timezone
import json
import time

from homeassistant.components.recorder import get_instance
from homeassistant.core import Context


def prepare_fixture(path):
    directory=path/'custom_components'/'hads_lab_player';directory.mkdir(parents=True)
    (directory/'__init__.py').write_text('')
    (directory/'manifest.json').write_text(json.dumps({'domain':'hads_lab_player','name':'HADS virtual radio fixture',
        'version':'0.0.1','documentation':'https://github.com/OndraMa/HADS','codeowners':[],
        'requirements':[],'iot_class':'local_push'}))
    (directory/'media_player.py').write_text('''from homeassistant.components.media_player import MediaPlayerEntity,MediaPlayerEntityFeature,MediaPlayerState

async def async_setup_platform(hass,config,async_add_entities,discovery_info=None):
    async_add_entities([VirtualRadio()])

class VirtualRadio(MediaPlayerEntity):
    _attr_name="HADS lab radio"
    _attr_unique_id="hads_lab_radio"
    _attr_should_poll=False
    _attr_state=MediaPlayerState.PLAYING
    _attr_supported_features=MediaPlayerEntityFeature.STOP

    async def async_media_stop(self):
        self._attr_state=MediaPlayerState.IDLE
        self.async_write_ha_state()
''')


async def exercise_sources(hass,app):
    broker=app.investigations.broker
    async def read(case,name,**args):return await asyncio.to_thread(broker.read,case,name,args)
    iso=lambda stamp:datetime.fromtimestamp(stamp,timezone.utc).isoformat()
    now=time.time()
    system=app.store.open_incident('system','Laboratorní kontrola systémových čtení.',['homeassistant'],now)['id']
    system_reads={}
    for name in ('hads_get_system_health','hads_get_integration_repairs','hads_get_system_log'):
        result=await read(system,name)
        assert result['status'] in {'available','no_relevant_data'},result
        system_reads[name]=result
    assert system_reads['hads_get_system_health']['data']['complete']
    # Wait for the actual authenticated subscribe_events ACK, never assume the
    # collector exists merely because a thread has been started.
    for _ in range(100):
        with app.store._connect() as db:row=db.execute('SELECT start FROM zha_capture WHERE ended=0 ORDER BY id DESC LIMIT 1').fetchone()
        if row:break
        await asyncio.sleep(.1)
    assert row,'actual ZHA websocket subscription did not become ready'
    zha_start=time.time()
    zha_case=app.store.open_incident('zigbee','Laboratorní ZHA událost má spustit automatizaci.',
        ['automation.hads_zha_chain','input_boolean.hads_zha_target'],zha_start)['id']
    config=await read(zha_case,'hads_get_automation_config',automation_id='hads_zha_chain')
    assert config['status']=='available'
    context=Context()
    hass.bus.async_fire('zha_event',{'device_id':'11111111111111111111111111111111','command':'toggle','args':['PRIVATE_ZHA_ARG']},context=context)
    await hass.async_block_till_done()
    assert hass.states.get('input_boolean.hads_zha_target').state=='on'
    for _ in range(100):
        with app.store._connect() as db:count=db.execute('SELECT COUNT(*) FROM zha_observations').fetchone()[0]
        if count:break
        await asyncio.sleep(.05)
    zha_end=time.time()
    events=await read(zha_case,'hads_get_zha_events',device_id='11111111111111111111111111111111',start=iso(zha_start),end=iso(zha_end))
    assert events['status']=='available' and len(events['data']['events'])==1,events
    assert events['data']['events'][0]['context']['id']==context.id
    traces=await read(zha_case,'hads_get_automation_traces',automation_id='hads_zha_chain')
    trace=await read(zha_case,'hads_get_automation_trace',automation_id='hads_zha_chain',run_id=traces['data'][0]['run_id'])
    state=await read(zha_case,'hads_get_entity_state',entity_id='input_boolean.hads_zha_target')
    assert state['data']['state']=='on'
    assert state['data']['context']['parent_id']==context.id or trace['data'].get('context',{}).get('parent_id')==context.id
    assert 'PRIVATE_ZHA_ARG' not in app.store.export(zha_case)
    # A real native media_player service drives a virtual test entity; no actual
    # playback or volume in a household is changed.
    radio_start=time.time()
    assert hass.states.get('media_player.hads_lab_radio').state=='playing'
    await get_instance(hass).async_block_till_done()
    radio_context=Context()
    await hass.services.async_call('media_player','media_stop',{'entity_id':'media_player.hads_lab_radio'},blocking=True,context=radio_context)
    await hass.async_block_till_done();await get_instance(hass).async_block_till_done()
    assert hass.states.get('media_player.hads_lab_radio').state=='idle'
    radio_case=app.store.open_incident('radio','Virtuální rádio bylo zastaveno.', ['media_player.hads_lab_radio'],time.time())['id']
    radio_end=time.time()
    history=await read(radio_case,'hads_get_entity_history',entity_id='media_player.hads_lab_radio',start=iso(radio_start-60),end=iso(radio_end))
    actions=await read(radio_case,'hads_get_action_history',start=iso(radio_start-60),end=iso(radio_end))
    assert history['status']=='available',history
    assert {'playing','idle'}<={row['state'] for group in history['data'] for row in group}
    assert actions['status']=='available',actions
    stop=[row for row in actions['data'] if row.get('domain')=='media_player' and row.get('service')=='media_stop' and 'media_player.hads_lab_radio' in row.get('targets',{}).get('entity_id',[])]
    assert len(stop)==1 and stop[0]['context_id']==radio_context.id,actions
    reported=await asyncio.to_thread(app.report_incident,'Virtuální rádio bylo zastaveno.','media_player.hads_lab_radio',app.owner(),occurred_at=radio_end)
    conclusion=next(r['content'] for r in reversed(reported['records']) if r['kind']=='deterministic_investigation')
    assert conclusion['category']=='commanded_stop',conclusion
    return {'scope':'actual_Core_2026.11_native_diagnostic_contracts','physical_radio':False,'physical_zigbee':False,
        'zha_event_origin':'injected_fixture_on_actual_Core_event_bus','supervisor_live':False,'music_assistant_live':False,
        'system':system_reads,'zha':{'events':events,'trace':trace,'target_state':state,'chain_observed':True},
        'radio':{'history':history,'actions':actions,'deterministic_conclusion':conclusion},'passed':True}
