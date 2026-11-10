from datetime import datetime,timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from email.message import Message

from hads_next.evidence import IncidentStore
from hads_next.evidence_broker import EvidenceBroker,BrokerDenied
from hads_next.music_assistant import MusicMCP,MusicAssistantReader,COMMANDS,safe_music
from hads_next.music_configuration import MusicConfiguration
from hads_next.observability import ReadFailure


class Reply(io.BytesIO):
    def __init__(self,value,status=200,content='application/json'):
        super().__init__(value if isinstance(value,bytes) else json.dumps(value).encode())
        self.status=status;self.headers=Message();self.headers['Content-Type']=content
        self.headers['Mcp-Session-Id']='contract-session'


class MetaContract:
    """Inspected upstream wire fixture, not a running Music Assistant server."""
    def __init__(self,*,readonly=True,capacity=100,sse=False):
        self.requests=[];self.readonly=readonly;self.capacity=capacity;self.sse=sse

    def open(self,request,timeout):
        body=json.loads(request.data);self.requests.append(body)
        assert request.full_url=='https://ma.example/mcp/v1'
        assert request.get_header('Authorization')=='Bearer PRIVATE_MA_TOKEN'
        method=body['method']
        if method=='initialize':value={'protocolVersion':'2025-06-18','serverInfo':{'name':'contract_fixture','version':'2.2.8'},'capabilities':{'tools':{}}}
        elif method=='notifications/initialized':return Reply(b'',202)
        elif method=='tools/list':value={'tools':[{'name':'get_tool_schema'},{'name':'call_tool'}]}
        elif body['params']['name']=='get_tool_schema':
            name=body['params']['arguments']['tool_name'];command=name.removeprefix('ma_api:')
            fields={'player_id':{},'raise_unavailable':{}} if command=='players/get' else {'limit':{},'id_filter':{},'since_seconds':{}}
            value={'structuredContent':{'name':name,'command':command,'annotations':{'readOnlyHint':self.readonly,'destructiveHint':False},
                'inputSchema':{'type':'object','properties':fields,'required':[]}}}
        else:
            args=body['params']['arguments'];command=args['name'];assert command in {'ma_api:'+x for x in COMMANDS.values()}
            data={'events':[],'buffer_capacity':self.capacity,'total_seen':0} if command.endswith('recent_events') else \
                {'player_id':'ma_radio','available':True,'playback_state':'idle','current_media':{'uri':'https://radio/?token=PRIVATE_STREAM_TOKEN'}}
            value={'structuredContent':{'command':command,'data':data,'truncated':False}}
        envelope={'jsonrpc':'2.0','id':body['id'],'result':value}
        if self.sse:return Reply(('event: message\ndata: '+json.dumps(envelope)+'\n\n').encode(),content='text/event-stream')
        return Reply(envelope)


class MusicTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=IncidentStore(Path(self.tmp.name)/'case.db');self.now=1000000.
        self.case=self.store.open_incident('radio','Rádio se vypnulo.',['media_player.radio'],self.now)['id']

    def reader(self,wire):
        transport=MusicMCP('https://ma.example/mcp/v1','PRIVATE_MA_TOKEN');transport._opener=wire
        return MusicAssistantReader(transport,{'media_player.radio':'ma_radio'},lambda:self.now)

    def read(self,reader,section):
        broker=EvidenceBroker(self.store,music=reader,clock=lambda:self.now)
        args={'entity_id':'media_player.radio','section':section,
            'start':datetime.fromtimestamp(self.now-30,timezone.utc).isoformat(),'end':datetime.fromtimestamp(self.now,timezone.utc).isoformat()}
        return broker.read(self.case,'hads_get_music_assistant_diagnostics',args)

    def test_fixed_meta_catalog_and_both_wire_content_types(self):
        for sse in (False,True):
            wire=MetaContract(sse=sse);reader=self.reader(wire)
            result=self.read(reader,'player')
            self.assertEqual(result['status'],'available');self.assertEqual(result['data']['data']['playback_state'],'idle')
            self.assertNotIn('PRIVATE_STREAM_TOKEN',json.dumps(result)+self.store.export(self.case))
            self.assertEqual(wire.requests[-1]['params']['arguments']['name'],'ma_api:players/get')
            with self.assertRaises(ReadFailure):reader.transport.read('players/cmd/stop',{})
            self.assertEqual(len(wire.requests),5)

    def test_missing_readonly_contract_prevents_actual_call(self):
        wire=MetaContract(readonly=False)
        self.assertEqual(self.read(self.reader(wire),'player')['status'],'read_failed')
        self.assertEqual(wire.requests[-1]['params']['name'],'get_tool_schema')

    def test_disabled_buffer_is_not_successful_empty_history(self):
        self.assertEqual(self.read(self.reader(MetaContract(capacity=0)),'events')['status'],'not_read')
        self.assertEqual(self.read(self.reader(MetaContract(capacity=100)),'events')['status'],'no_relevant_data')

    def test_owner_settings_do_not_export_token_and_endpoint_change_needs_new_token(self):
        settings=MusicConfiguration(self.tmp.name)
        self.assertIsNone(settings.reader())
        settings.configure(endpoint='https://ma.example/mcp/v1',token='PRIVATE_MA_TOKEN',mapping={'media_player.radio':'ma_radio'},enabled=True,principal='owner')
        self.assertEqual(settings.path.stat().st_mode&0o777,0o600)
        loaded=MusicConfiguration(self.tmp.name)
        self.assertTrue(loaded.public_status()['enabled']);self.assertNotIn('PRIVATE_MA_TOKEN',json.dumps(loaded.public_status()))
        with self.assertRaises(ValueError):loaded.configure(endpoint='https://other.example/mcp/v1',token='',mapping={},enabled=True,principal='owner')

    def test_unknown_signed_url_parameters_and_url_credentials_are_removed(self):
        value=safe_music({'last_error':'Failed https://alice:password@radio.example/live?signature=PRIVATE_SIGNATURE#token'})
        self.assertEqual(value,{'last_error':'Failed https://radio.example/live'})


if __name__=='__main__':unittest.main()
