"""Durable provider/function catalog. Discovery never grants execution rights."""
import hashlib
import json
import time
from .evidence import canonical

PROVIDERS=('core','supervisor','haos','spook','watchman','ha_mcp','native_mcp','hamster_mcp',
           'zha_toolkit','zha','automation_inspector','hadocs','haghs','entity_availability','music_assistant')

def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

class ToolDenied(ValueError):
    pass


from functools import lru_cache

@lru_cache(maxsize=256)
def schema_validator(serialized):
    from jsonschema import Draft202012Validator
    schema=json.loads(serialized)
    if len(serialized.encode())>48000:raise ToolDenied('Schéma překročilo limit.')
    def check(node,depth=0):
        if depth>32:raise ToolDenied('Schéma je příliš hluboké.')
        if isinstance(node,dict):
            for k,v in node.items():
                if k in {'$ref','$dynamicRef'} and (not isinstance(v,str) or not v.startswith('#/')):raise ToolDenied('Externí odkazy schématu nejsou povolené.')
                check(v,depth+1)
        elif isinstance(node,list):
            for v in node:check(v,depth+1)
    check(schema)
    try:Draft202012Validator.check_schema(schema)
    except Exception:raise ToolDenied('Schéma nelze bezpečně ověřit.') from None
    return Draft202012Validator(schema)

def validate(schema,value):
    if len(canonical(value).encode())>128000:raise ToolDenied('Parametry překročily limit.')
    try:
        if not schema_validator(canonical(schema)).is_valid(value):raise ToolDenied('Parametry neodpovídají ověřenému schématu.')
    except ToolDenied:raise
    except Exception:raise ToolDenied('Schéma nelze bezpečně ověřit.') from None


def object_schema(properties=None,required=None):
    properties=properties or {}
    return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}

ENTITY={'type':'string','pattern':r'^[a-z][a-z0-9_]*\.[a-z0-9_]+$','maxLength':160}
ID={'type':'string','pattern':r'^[A-Za-z0-9_:-]{1,128}$'}

class ToolRegistry:
    def __init__(self,store,clock=time.time):
        self.store,self.clock=store,clock
        with store._connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS tool_registry_schema(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO tool_registry_schema VALUES(1);
            CREATE TABLE IF NOT EXISTS tool_providers(id TEXT PRIMARY KEY,document TEXT NOT NULL,checked_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS tool_catalog(provider TEXT NOT NULL,name TEXT NOT NULL,document TEXT NOT NULL,
                checked_at REAL NOT NULL,PRIMARY KEY(provider,name));''')
            if [r[0] for r in db.execute('SELECT version FROM tool_registry_schema')]!=[1]:raise ToolDenied('Neznámé schéma katalogu.')

    def provider(self,provider,**fields):
        if provider not in PROVIDERS:raise ToolDenied('Neznámý poskytovatel.')
        current=next((p for p in self.providers() if p['id']==provider),{})
        # Fields contain capabilities/status only: no address, credential or remote body.
        allowed={'installed','running','connected','authenticated','catalog_loaded','diagnostic_read_verified','version',
                 'server_version','version_basis','last_error','authentication_basis','identity','origin_digest'}
        if set(fields)-allowed:raise ToolDenied('Neplatný stav poskytovatele.')
        current.update(fields);current.update(id=provider,checked_at=self.clock())
        with self.store._connect() as db:db.execute('INSERT OR REPLACE INTO tool_providers VALUES(?,?,?)',(provider,canonical(current),self.clock()))
        return current

    def providers(self):
        with self.store._connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT document FROM tool_providers ORDER BY id')]

    def replace(self,provider,tools):
        if provider not in PROVIDERS or not isinstance(tools,list) or len(tools)>512:raise ToolDenied('Neplatný katalog.')
        rows=[];seen=set()
        for tool in tools:
            name=tool.get('name')
            if not isinstance(name,str) or not 1<=len(name)<=160 or name in seen:raise ToolDenied('Nejednoznačná identita funkce.')
            seen.add(name)
            schema=tool.get('schema')
            schema_validator(canonical(schema))
            document={**tool,'provider':provider,'schema_hash':fingerprint(schema),'checked_at':self.clock()}
            document.pop('schema_example',None)
            document['repair_operation_implemented']=bool(tool.get('executor')) and tool.get('effect')=='write'
            document['repair_ready_for_approval']=False  # only a prepared immutable plan may set this
            rows.append((provider,name,canonical(document),self.clock()))
        with self.store._connect() as db:
            db.execute('BEGIN IMMEDIATE');db.execute('DELETE FROM tool_catalog WHERE provider=?',(provider,))
            db.executemany('INSERT INTO tool_catalog VALUES(?,?,?,?)',rows)

    def tools(self,*,include_blocked=True):
        with self.store._connect() as db:rows=[json.loads(r[0]) for r in db.execute('SELECT document FROM tool_catalog ORDER BY provider,name')]
        providers={p['id']:p for p in self.providers()}
        with self.store._connect() as db:
            try:
                plans=[(r[0],json.loads(r[1])) for r in db.execute("SELECT p.id,p.document FROM repair_plans p LEFT JOIN repair_executions e ON e.plan_id=p.id WHERE e.id IS NULL AND json_extract(p.document,'$.operation')='tool.approved' ORDER BY p.created_at DESC LIMIT 50")]
            except Exception:plans=[]
        for row in rows:
            row['prepared_plan_ids']=[identity for identity,plan in plans if plan['binding']['provider']==row['provider'] and plan['binding']['tool']==row['name'] and plan['binding']['schema_hash']==row['schema_hash']]
            row['repair_ready_for_approval']=bool(row['prepared_plan_ids'])
            provider=providers.get(row['provider'],{})
            row['available']=provider.get('connected') is True and provider.get('catalog_loaded') is True and self.clock()-row['checked_at']<=900
            row['diagnostic_read_verified']=provider.get('diagnostic_read_verified') is True
            row['repair_ready_for_approval']=row['repair_ready_for_approval'] and row['available'] and any(plan['binding']['provider']==row['provider'] and plan['binding']['tool']==row['name'] and plan['binding']['schema_hash']==row['schema_hash'] and plan['binding']['version']==provider.get('version') and plan['binding'].get('server_version')==provider.get('server_version') and plan['binding'].get('origin_digest')==provider.get('origin_digest') for _,plan in plans)
        return rows if include_blocked else [r for r in rows if r.get('policy')=='allowed' and r['available']]

    def get(self,provider,name,*,effect=None):
        row=next((x for x in self.tools() if (x['provider'],x['name'])==(provider,name)),None)
        if not row or not row['available'] or row.get('policy')!='allowed' or effect and row.get('effect')!=effect:
            raise ToolDenied('Funkce není aktuálně ověřená nebo povolená pro tuto operaci.')
        return row
