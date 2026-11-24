"""Optional fixed-catalog Music Assistant FastMCP reads.

Contract: MA server 16cc2545, FastMCP plugin 2.2.8. Only five verified
ma_api commands can be invoked through the generic upstream meta-tool. Neither
the meta-tool nor its command name/URL/token is exposed to Hermes.
"""
from datetime import datetime
import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request,build_opener

from .observability import ReadFailure,SourceStatus,_NoRedirect,redact,bounded_body,bounded_chunks


COMMANDS={
    'player':'players/get',
    'health':'fastmcp/debug/health',
    'events':'fastmcp/debug/recent_events',
    'buffer':'fastmcp/debug/event_buffer_stats',
    'logs':'fastmcp/debug/tail_log',
}


def safe_music(value,depth=0):
    """Drop URL credentials, queries and fragments even with unknown key names."""
    if depth>8:return '[omezená hloubka]'
    if isinstance(value,dict):return {k:safe_music(v,depth+1) for k,v in value.items()}
    if isinstance(value,list):return [safe_music(x,depth+1) for x in value]
    if isinstance(value,str):
        def clean(match):
            try:
                url=urlsplit(match.group(0))
                host=url.hostname or ''
                return url.scheme+'://'+host+(':'+str(url.port) if url.port else '')+url.path
            except ValueError:return '[skrytá URL]'
        return re.sub(r'https?://[^\s\"<>]+',clean,value)
    return value


class MusicMCP:
    """Bounded Streamable HTTP subset; no sampling, elicitation or reconnect.

    JSON and finite POST SSE replies supported. Server initiated requests and
    redirects fail closed. Auth is sent only to the owner's fixed HTTPS URL.
    Protocol framing verified against MCP Python SDK v1.13.1 streamable_http.py.
    """
    def __init__(self,endpoint,token):
        url=urlsplit(endpoint)
        if url.scheme!='https' or not url.hostname or url.path!='/mcp/v1' or url.username or url.password or url.query or url.fragment:
            raise ValueError('Music Assistant vyžaduje HTTPS adresu /mcp/v1 bez údajů v URL.')
        if not isinstance(token,str) or not 8<=len(token)<=2048 or any(c in token for c in '\r\n'):raise ValueError('Neplatný token Music Assistantu.')
        self.endpoint,self._token=endpoint,token
        self._opener=build_opener(_NoRedirect)
        self._session=None;self._protocol=None;self._sequence=0;self._server=None

    def _rpc(self,method,params,*,notification=False):
        self._sequence+=1
        payload={'jsonrpc':'2.0','method':method,'params':params}
        if not notification:payload['id']=self._sequence
        headers={'Authorization':'Bearer '+self._token,'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
        if self._session:headers['Mcp-Session-Id']=self._session
        if self._protocol:headers['MCP-Protocol-Version']=self._protocol
        request=Request(self.endpoint,data=json.dumps(payload).encode(),headers=headers,method='POST')
        try:
            with self._opener.open(request,timeout=10) as response:
                session=response.headers.get('Mcp-Session-Id')
                if session:
                    if not re.fullmatch(r'[\x21-\x7e]{1,256}',session):raise ReadFailure('invalid_mcp_session')
                    self._session=session
                if notification:
                    if response.status!=202:raise ReadFailure('mcp_notification_rejected')
                    return None
                content=response.headers.get_content_type()
                if content=='application/json':
                    raw=bounded_body(response,128000)
                    message=json.loads(raw)
                elif content=='text/event-stream':
                    data=[];message=None;buffer=b''
                    for chunk in bounded_chunks(response,128000,15):
                        buffer=(buffer+chunk).replace(b'\r\n',b'\n')
                        while b'\n' in buffer:
                            raw,buffer=buffer.split(b'\n',1);line=raw.decode('utf-8')
                            if line.startswith('data:'):data.append(line[5:].lstrip())
                            elif not line and data:
                                candidate=json.loads('\n'.join(data));data=[]
                                if 'method' in candidate:raise ReadFailure('mcp_server_request_refused')
                                if candidate.get('id')==payload['id']:message=candidate;break
                        if message is not None:break
                    if message is None:raise ReadFailure('mcp_result_missing')
                else:raise ReadFailure('mcp_content_type')
                if not isinstance(message,dict) or message.get('jsonrpc')!='2.0' or message.get('id')!=payload['id'] or 'method' in message:
                    raise ReadFailure('mcp_invalid_reply')
                if 'error' in message:raise ReadFailure('mcp_command_rejected')
                return message['result']
        except HTTPError as error:raise ReadFailure('mcp_http_error',error.code) from None
        except ReadFailure:raise
        except Exception:raise ReadFailure('mcp_read_failed') from None

    @staticmethod
    def _tool_value(result):
        if not isinstance(result,dict):raise ReadFailure('mcp_invalid_tool_result')
        if result.get('isError'):raise ReadFailure('mcp_tool_unavailable_or_forbidden')
        value=result.get('structuredContent')
        if value is not None:return value
        blocks=result.get('content',[])
        if len(blocks)!=1 or blocks[0].get('type')!='text':raise ReadFailure('mcp_structured_result_required')
        try:return json.loads(blocks[0]['text'])
        except (ValueError,KeyError):raise ReadFailure('mcp_invalid_tool_json') from None

    def read(self,section,arguments):
        if section not in COMMANDS:raise ReadFailure('mcp_command_not_allowed')
        if self._protocol is None:
            info=self._rpc('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'HADS-readonly','version':'0.1'}})
            if not isinstance(info,dict) or info.get('protocolVersion') not in {'2025-03-26','2025-06-18'}:raise ReadFailure('mcp_protocol_unsupported')
            self._protocol=info['protocolVersion'];self._server=info.get('serverInfo')
            self._rpc('notifications/initialized',{},notification=True)
            catalog=self._rpc('tools/list',{})
            names={row.get('name') for row in catalog.get('tools',[]) if isinstance(row,dict)}
            if not {'get_tool_schema','call_tool'}<=names:raise ReadFailure('ma_meta_tools_missing')
        canonical='ma_api:'+COMMANDS[section]
        descriptor=self._tool_value(self._rpc('tools/call',{'name':'get_tool_schema','arguments':{'tool_name':canonical}}))
        if not isinstance(descriptor,dict) or descriptor.get('name')!=canonical or descriptor.get('command')!=COMMANDS[section]:raise ReadFailure('ma_schema_identity_mismatch')
        hints=descriptor.get('annotations',{})
        if hints.get('readOnlyHint') is not True or hints.get('destructiveHint') is not False:
            raise ReadFailure('ma_readonly_contract_missing')
        schema=descriptor.get('inputSchema',{})
        if schema.get('type')!='object' or not set(arguments)<=set(schema.get('properties',{})) or not set(schema.get('required',[]))<=set(arguments):
            raise ReadFailure('ma_schema_changed')
        envelope=self._tool_value(self._rpc('tools/call',{'name':'call_tool','arguments':{
            'name':canonical,'arguments':arguments,'response_mode':'full','max_items':30}}))
        if not isinstance(envelope,dict) or envelope.get('command')!=canonical or 'data' not in envelope:raise ReadFailure('ma_command_result_mismatch')
        return {'data':envelope['data'],'truncated':bool(envelope.get('truncated')),'server_info':self._server}


class MusicAssistantReader:
    def __init__(self,transport,mapping,clock=time.time):
        if not isinstance(mapping,dict) or len(mapping)>32 or any(not re.fullmatch(r'media_player\.[a-z0-9_]+',k) or not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',v) for k,v in mapping.items()):
            raise ValueError('Neplatná vazba HA entity na přehrávač Music Assistantu.')
        self.transport,self.mapping,self.clock=transport,mapping,clock
        self.status=SourceStatus('music_assistant_fastmcp')

    def diagnostics(self,entity_id,section,start,end):
        self.status.relevant=None;self.status.read_succeeded=False
        if entity_id not in self.mapping:raise ReadFailure('ma_player_mapping_not_configured')
        if section not in {'player','health','events','buffer','logs'}:raise ReadFailure('ma_section_not_allowed')
        if start<self.clock()-3600:raise ReadFailure('ma_recent_window_expired')
        arguments={'player_id':self.mapping[entity_id],'raise_unavailable':False} if section=='player' else \
            {'limit':30,'id_filter':self.mapping[entity_id],'since_seconds':min(3600,max(1,int(self.clock()-start)+1))} if section=='events' else \
            {'lines':30,'since_seconds':min(3600,max(1,int(self.clock()-start)+1))} if section=='logs' else {}
        try:
            envelope=self.transport.read(section,arguments)
            value=envelope['data']
            if section=='player':
                if value is not None and not isinstance(value,dict):raise ReadFailure('ma_invalid_player')
                value=None if value is None else {k:value[k] for k in ('player_id','provider','available','playback_state','powered','active_source','elapsed_time','elapsed_time_last_updated') if k in value}
            elif section=='events':
                if not isinstance(value,dict) or not isinstance(value.get('events'),list) or not isinstance(value.get('buffer_capacity'),int):raise ReadFailure('ma_invalid_events')
                projected=[]
                for event in value['events'][:30]:
                    stamp=datetime.fromisoformat(event['timestamp'])
                    if stamp.tzinfo is None:raise ReadFailure('ma_event_timezone_missing')
                    if start<=stamp.timestamp()<=end and event.get('object_id')==self.mapping[entity_id]:
                        # Raw event.data may include signed stream URLs or tokens.
                        data=event.get('data')
                        projected.append({k:event[k] for k in ('timestamp','event_type','object_id') if k in event} | {
                            'data':{k:data[k] for k in ('player_id','available','playback_state','provider') if k in data} if isinstance(data,dict) else None,
                            'omitted_raw_payload':True})
                value={'events':projected,'buffer_capacity':value['buffer_capacity'],'total_seen':value.get('total_seen'),
                       'history_before_buffer_start':'unavailable','stream_delivery_proven':False}
            elif section=='health':
                if not isinstance(value,dict) or not isinstance(value.get('providers_loaded'),int):raise ReadFailure('ma_invalid_health')
                value={k:value[k] for k in ('providers_loaded','providers_disabled','providers_error','providers_error_details','queues_total','queues_with_active_playback','queues_with_errors','disabled_capabilities','event_buffer_active','policy_schema_version') if k in value}
            elif section=='buffer':
                if not isinstance(value,dict) or not isinstance(value.get('capacity'),int):raise ReadFailure('ma_invalid_buffer')
                value={k:value[k] for k in ('capacity','current_size','total_seen','dropped','subscribed_since','by_type') if k in value}
            else:
                if not isinstance(value,dict) or not isinstance(value.get('lines'),list):raise ReadFailure('ma_invalid_logs')
                value={'lines':[{k:row[k] for k in ('timestamp','level','component','message') if k in row} for row in value['lines'][:30] if isinstance(row,dict)],
                    'truncated':bool(value.get('truncated')),'interpretation':'Log similarity alone does not establish cause.'}
            self.status.interface_available=True;self.status.authenticated=True;self.status.read_succeeded=True
            self.status.last_read_at=self.clock();self.status.last_error=None;self.status.last_response_status=None
            return redact(safe_music({'section':section,'entity_id':entity_id,'data':value,'truncated':envelope.get('truncated',False),
                'server_info':envelope.get('server_info'),'stream_delivery_tested':False}))
        except Exception as error:
            self.status.last_error=str(error) if isinstance(error,ReadFailure) else 'ma_read_failed'
            self.status.last_response_status=error.status if isinstance(error,ReadFailure) else None
            if self.status.last_response_status in {401,403}:self.status.authenticated=False
            return None
