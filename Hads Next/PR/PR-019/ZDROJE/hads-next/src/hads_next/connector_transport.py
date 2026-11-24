"""Controller-only HTTP/MCP transport; endpoints and credentials never reach AI."""
import ipaddress
import json
import re
import threading
from urllib.parse import urlsplit
from urllib.request import Request,build_opener
from urllib.error import HTTPError
from .observability import _NoRedirect,ReadFailure,bounded_body
from .music_assistant import MusicMCP


def endpoint(value,*,allow_private_http=False,origin_only=False):
    if not isinstance(value,str) or len(value)>2048 or any(ord(c)<33 for c in value):raise ValueError('Neplatná adresa.')
    u=urlsplit(value)
    if not u.hostname or u.username or u.password or u.query or u.fragment or '\\' in value:raise ValueError('Neplatná adresa.')
    local=u.hostname in {'localhost','supervisor'} or bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)+',u.hostname))
    try:local=local or ipaddress.ip_address(u.hostname).is_private
    except ValueError:pass
    if u.scheme!='https' and not (u.scheme=='http' and allow_private_http and local):raise ValueError('Vyžaduje HTTPS nebo výslovně povolenou soukromou síť.')
    if origin_only and u.path not in {'','/'}:raise ValueError('Pro HTTP report zadej pouze původ adresy.')
    try:u.port
    except ValueError:raise ValueError('Neplatný port.') from None
    return value.rstrip('/')

class ReportHTTP:
    def __init__(self,base,token='',*,allow_private_http=False):
        self.base=endpoint(base,allow_private_http=allow_private_http,origin_only=True)
        if not isinstance(token,str) or len(token)>4096 or any(ord(c)<32 for c in token):raise ValueError('Neplatný token.')
        self._token=token;self.opener=build_opener(_NoRedirect)
    def get(self,path):
        if path not in {'/api/v1/status','/api/v1/inspection','/api/status','/api/summary','/api/devices'}:raise ReadFailure('report_path_refused')
        headers={'Accept':'application/json'}
        if self._token:headers['Authorization']='Bearer '+self._token
        try:
            with self.opener.open(Request(self.base+path,headers=headers),timeout=8) as r:
                if r.headers.get_content_type()!='application/json':raise ReadFailure('report_not_json')
                return json.loads(bounded_body(r,1024000,10))
        except HTTPError as e:raise ReadFailure('report_http_rejected',e.code) from None
        except ReadFailure:raise
        except Exception:raise ReadFailure('report_unavailable') from None

class MCPConnection(MusicMCP):
    """Reuse the tested finite JSON/SSE framing, add bounded paginated discovery.

    No GET event stream, sampling, elicitation, callback listener or OAuth secret
    guessing. 401/403 is a setup blocker, not an empty successful catalog.
    """
    def __init__(self,url,token='',*,allow_private_http=False):
        self.endpoint=endpoint(url,allow_private_http=allow_private_http)
        self.max_rpc_bytes=2*1024*1024
        if not isinstance(token,str) or len(token)>4096 or any(ord(c)<32 for c in token):raise ValueError('Neplatný token.')
        self._token=token;self._opener=build_opener(_NoRedirect)
        self._session=None;self._protocol=None;self._sequence=0;self._server=None
        self.lock=threading.RLock();self.catalog=[];self.delegated={};self.discovery_phase='initialize'
    def discover(self):
        with self.lock:
            self._session=None;self._protocol=None;self.catalog=[];self.delegated={}
            self.discovery_phase='initialize'
            info=self._rpc('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'HADS-broker','version':'1'}})
            if not isinstance(info,dict) or info.get('protocolVersion') not in {'2025-03-26','2025-06-18'}:raise ReadFailure('mcp_protocol_unsupported')
            self._protocol=info['protocolVersion'];self._server=info.get('serverInfo')
            if not isinstance(self._server,dict) or not isinstance(self._server.get('name'),str) or not isinstance(self._server.get('version'),str):raise ReadFailure('mcp_server_identity_missing')
            self.discovery_phase='session'
            self._rpc('notifications/initialized',{},notification=True)
            self.discovery_phase='catalog'
            cursor=None;seen=set();names=set();rows=[]
            for _ in range(8):
                result=self._rpc('tools/list',{} if cursor is None else {'cursor':cursor})
                tools=result.get('tools') if isinstance(result,dict) else None
                if not isinstance(tools,list):raise ReadFailure('mcp_invalid_catalog')
                for row in tools:
                    if not isinstance(row,dict) or not isinstance(row.get('name'),str) or row['name'] in names or not isinstance(row.get('inputSchema'),dict):raise ReadFailure('mcp_ambiguous_catalog')
                    if not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}',row['name']):raise ReadFailure('mcp_invalid_tool_name')
                    names.add(row['name']);rows.append(row)
                if len(rows)>512:raise ReadFailure('mcp_catalog_limit')
                cursor=result.get('nextCursor')
                if cursor is None:self.catalog=rows;return rows
                if not isinstance(cursor,str) or not cursor or len(cursor)>2048 or cursor in seen:raise ReadFailure('mcp_pagination_loop')
                seen.add(cursor)
            raise ReadFailure('mcp_catalog_incomplete')
    @staticmethod
    def _tool_value(result):
        if not isinstance(result,dict) or result.get("isError"):raise ReadFailure("mcp_tool_rejected")
        if result.get("structuredContent") is not None:
            structured=result['structuredContent']
            meta=result.get('_meta',{}).get('fastmcp',{})
            if isinstance(meta,dict) and meta.get('wrap_result') is True:
                if not isinstance(structured,dict) or set(structured)!={'result'}:raise ReadFailure('mcp_invalid_wrapped_result')
                return structured['result']
            return structured
        blocks=result.get("content",[])
        if not isinstance(blocks,list) or len(blocks)!=1 or blocks[0].get("type")!="text":raise ReadFailure("mcp_tool_result_not_supported")
        text=blocks[0].get("text")
        if not isinstance(text,str):raise ReadFailure("mcp_tool_result_invalid")
        try:return json.loads(text)
        except ValueError:return text[:12000]

    def call(self,name,args):
        with self.lock:
            if name in self.delegated:
                proxy=self.delegated[name];args={'name':name,'arguments':args};name=proxy
            if self._protocol is None:raise ReadFailure('mcp_not_initialized')
            return self._tool_value(self._rpc('tools/call',{'name':name,'arguments':args}))

    def reviewed_meta_catalog(self):
        from .connector_policy import READS,WRITES
        from .tool_registry import validate
        names={r['name']:r for r in self.catalog}
        if 'ha_search_tools' not in names:return self.catalog
        request={'tools':list(READS)+list(WRITES)}
        validate(names['ha_search_tools']['inputSchema'],request)
        value=self.call('ha_search_tools',request)
        if not isinstance(value,list) or len(value)>len(request['tools']):raise ReadFailure('mcp_meta_catalog_invalid')
        extra=[];seen=set(names)
        for row in value:
            if not isinstance(row,dict):raise ReadFailure('mcp_meta_schema_invalid')
            name=row.get('name')
            if name in names or name not in request['tools'] or not isinstance(row.get('inputSchema'),dict):continue
            if name in seen:raise ReadFailure('mcp_meta_ambiguous_identity')
            proxy='ha_call_read_tool' if name in READS else 'ha_call_write_tool'
            if proxy not in names:continue
            self.delegated[name]=proxy;seen.add(name);extra.append(row)
        self.catalog+=extra
        return self.catalog
