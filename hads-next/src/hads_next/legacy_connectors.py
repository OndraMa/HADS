"""Private staging of known Hermes RC3 connection settings, never activation."""
import ipaddress, json, os, secrets, stat
from urllib.parse import urlsplit

class LegacySettingsError(ValueError):
    """Safe user-facing setup message; never a remote error body."""

FIELDS = {
    'ha_mcp': ('ha_mcp_url','ha_mcp_token'),
    'hamster_mcp': ('hamster_mcp_url','hamster_mcp_token'),
    'music_assistant': ('music_assistant_mcp_url','music_assistant_mcp_token'),
    'hadocs': ('hadocs_api_url','hadocs_token'),
    'automation_inspector': ('automation_inspector_api_url','automation_inspector_token'),
}

def prepare(document):
    if not isinstance(document,dict) or len(json.dumps(document).encode())>32768:raise LegacySettingsError('Neplatný nebo příliš velký export nastavení.')
    options=document.get('options',document)
    if not isinstance(options,dict):raise LegacySettingsError('Export neobsahuje objekt options.')
    connections={}
    for provider,(url_key,token_key) in FIELDS.items():
        endpoint=options.get(url_key,'');token=options.get(token_key,'')
        if not isinstance(endpoint,str) or not isinstance(token,str):raise LegacySettingsError('Připojovací položky musí být text.')
        if not endpoint.strip():continue
        endpoint=endpoint.strip()
        if len(endpoint)>2048 or len(token)>4096 or any(ord(c)<32 for c in endpoint+token):raise LegacySettingsError('Neplatný připojovací údaj.')
        if token and (token.strip() in {'[skryto]','[redacted]','***'} or set(token)=={'*'}):raise LegacySettingsError('Maskovaný token nelze použít jako skutečné nastavení.')
        try:
            url=urlsplit(endpoint);port=url.port
            local=url.hostname in {'supervisor','localhost'}
            try:
                address=ipaddress.ip_address(url.hostname or '')
                local=local or address.is_loopback or address.is_private
            except ValueError:pass
            if not url.hostname or url.username or url.password or url.query or url.fragment or url.scheme not in {'http','https'} or url.scheme=='http' and not local:raise LegacySettingsError()
        except ValueError:raise LegacySettingsError('Nepodporovaná adresa; žádné připojení se neprovedlo.') from None
        connections[provider]={'endpoint':endpoint,'token':token,'enabled':False,'live_verified':False}
    if not connections:raise LegacySettingsError('Export neobsahuje použitelné explicitní adresy. Historický přehled není export nastavení.')
    return {'schema_version':1,'origin':'owner_supplied_Hermes_RC3_options_not_live_verified',
            'connections':connections,'approval_imported':False,'cost_consent_imported':False,'writes_enabled':False}

class LegacyConnectors:
    def __init__(self,app):self.app=app;self.path=app.data_dir/'legacy-connectors.pending.json'
    def stage_previous(self,principal):
        if not principal or principal!=self.app.owner():raise LegacySettingsError('Přenos smí provést jen ověřený vlastník.')
        if self.app.supervisor is None:raise LegacySettingsError('Supervisor není dostupný; nastavení nebylo přeneseno.')
        # Deliberately private path: the ordinary reader redacts tokens. This
        # fixed GET never sends options into status, evidence, logs or AI.
        try:
            with self.app._read_lock:
                raw=self.app.supervisor.transport('/addons/local_hads4/info')
            value=raw.get('data') if isinstance(raw,dict) and raw.get('result')=='ok' else None
            if not isinstance(value,dict) or value.get('slug')!='local_hads4' or value.get('version')!='2.0.0-rc3' or not isinstance(value.get('options'),dict):raise LegacySettingsError()
            keys={k for fields in FIELDS.values() for k in fields}
            options={k:v for k,v in value['options'].items() if k in keys}
        except Exception:raise LegacySettingsError('Původní Hermes RC3 a jeho nastavení nebyly potvrzené; přenos neproběhl.') from None
        return self.stage(options,principal,source='supervisor_Hermes_RC3_options_not_live_connector_verified')
    def _safe(self):
        if self.path.is_symlink():raise LegacySettingsError('Neplatná cesta soukromého nastavení.')
        if self.path.exists():
            info=self.path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mode&0o077 or info.st_size>32768:raise LegacySettingsError('Soukromé nastavení nemá bezpečný formát.')
    def stage(self,document,principal,*,source='owner_supplied_Hermes_RC3_options_not_live_verified'):
        if not principal or principal!=self.app.owner():raise LegacySettingsError('Přenos smí provést jen ověřený vlastník.')
        value=prepare(document);value['origin']=source;self._safe()
        temporary=self.path.with_name('.legacy-'+secrets.token_hex(8))
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
            os.replace(temporary,self.path)
        finally:temporary.unlink(missing_ok=True)
        return self.public_status()
    def public_status(self):
        self._safe()
        if not self.path.exists():return {'staged_providers':[],'active':False,'verified':False}
        value=json.loads(self.path.read_text())
        if value.get('schema_version')!=1 or not isinstance(value.get('connections'),dict):raise LegacySettingsError('Neplatné přenesené nastavení.')
        return {'staged_providers':sorted(k for k in value['connections'] if k in FIELDS),'active':False,'verified':False}
