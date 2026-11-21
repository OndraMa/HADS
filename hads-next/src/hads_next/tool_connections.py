"""Owner-only private connection settings; legacy imports require activation."""
import json
import os
import secrets
import stat
from .connector_transport import MCPConnection,ReportHTTP
from .tool_registry import ToolDenied

KINDS={'ha_mcp':'mcp','native_mcp':'mcp','automation_inspector':'http','hadocs':'http'}

class ToolConnections:
    def __init__(self,app):
        self.app=app;self.path=app.data_dir/'tool-connections.json';self.clients={};self.values={}
        self.load_error=None
        try:
            if self.path.exists():
                if self.path.is_symlink() or not stat.S_ISREG(self.path.stat().st_mode) or self.path.stat().st_mode&0o077 or self.path.stat().st_size>32768:raise ToolDenied('Neplatné soukromé nastavení konektorů.')
                data=json.loads(self.path.read_text())
                if not isinstance(data,dict) or data.get('schema')!=1 or not isinstance(data.get('connections'),dict):raise ToolDenied('Neznámé schéma konektorů.')
                retired = 'hamster_mcp' in data['connections']
                data['connections'].pop('hamster_mcp', None)
                for provider,value in data['connections'].items():self._install(provider,value)
                if retired:
                    try:self._save()
                    except OSError:self.load_error='Nepoužívané historické nastavení zůstalo na disku. Aktivní konektory jsou načtené.'
        except (OSError,ValueError,TypeError,KeyError):
            self.clients={};self.values={};self.load_error='Soukromé nastavení konektorů nelze bezpečně načíst. Nativní diagnostika pokračuje; žádný neověřený konektor se neaktivoval.'
    def _install(self,provider,value):
        if provider not in KINDS or not isinstance(value,dict) or set(value)!={'endpoint','token','private_http','enabled'} or type(value['enabled']) is not bool or type(value['private_http']) is not bool:raise ToolDenied('Neplatný konektor.')
        cls=MCPConnection if KINDS[provider]=='mcp' else ReportHTTP
        client=cls(value['endpoint'],value['token'],allow_private_http=value['private_http'])
        self.values[provider]=value
        if value['enabled']:self.clients[provider]=client
        else:self.clients.pop(provider,None)
    def configure(self,provider,*,url,token,private_http,enabled,principal):
        if not principal or principal!=self.app.owner():raise ToolDenied('Pouze vlastník smí nastavit připojení.')
        if not token and self.values.get(provider,{}).get('endpoint')==url:token=self.values[provider]['token']
        self._install(provider,{'endpoint':url,'token':token,'private_http':private_http,'enabled':enabled})
        self._save()
    def _save(self):
        if self.path.is_symlink():raise ToolDenied('Neplatná cesta konektorů.')
        temp=self.path.with_name('.tools-'+secrets.token_hex(8));fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'w') as f:json.dump({'schema':1,'connections':self.values},f);f.flush();os.fsync(f.fileno())
            os.replace(temp,self.path)
            self.load_error=None
        finally:temp.unlink(missing_ok=True)
    def activate_previous(self,provider,principal):
        if provider not in KINDS:raise ToolDenied('Tento konektor se nepoužívá.')
        legacy=self.app.legacy_connectors;legacy._safe()
        if not legacy.path.exists():raise ToolDenied('Chybí soukromý návrh připojení.')
        value=json.loads(legacy.path.read_text()).get('connections',{}).get(provider)
        if not value:raise ToolDenied('V návrhu není tento konektor.')
        # Activates only the chosen connection. Never copies approval/AI/budget.
        self.configure(provider,url=value['endpoint'],token=value['token'],private_http=value['endpoint'].startswith('http://'),enabled=True,principal=principal)
    def public(self):
        return [{'provider':p,'configured':True,'enabled':v['enabled'],'private_http':v['private_http']} for p,v in self.values.items()]
