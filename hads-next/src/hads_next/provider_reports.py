"""Project real provider reports into common evidence, never raw secrets/config."""
import math
import re
from datetime import datetime
from .tool_registry import ToolDenied
ENTITY_RE=re.compile(r'[a-z][a-z0-9_]*\.[a-z0-9_]+')

def stamp(value):
    try:
        d=datetime.fromisoformat(value)
        return d.timestamp() if d.tzinfo else None
    except (ValueError,TypeError):return None

def safe_report(value,depth=0):
    # Provider reports can contain private log content, URLs, action payloads
    # and prompt injection. This structural projection is data, never authority.
    if depth>7:return None
    if isinstance(value,dict):
        allowed={'id','unique_id','platform','config_entry_id','context_id','parent_id','entity_id','device_id','domain','status','state','severity','type','kind','code','reason','message',
                 'summary','title','description','source','entities','references','dependencies','issues','findings','trace','error',
                 'timestamp','last_seen','last_updated','available','enabled','disabled_by','lqi','rssi','unit_of_measurement',
                 'device_class','state_class','health_score','potential_score','main_root_cause','root_cause','affected_entities','confidence','related_items','priority','action','estimated_score_gain','score','hardware_score','application_score','repair_count','cpu_percent',
                 'memory_usage','memory_limit','cpu_usage','version','version_latest','update_available','integration',
                 'stale_candidates','stale_watch_entities','zombie_entities','dead_device_ids','integration_unhealthy_entries',
                 'repairs','recommendations','psi_available','db_size_mb','name','count','start','end','mean','min','max','sum',
                 'last_reset','statistic_id','statistic_unit','unit_class','has_sum','has_mean','mean_type','statistics',
                 'data','metadata','attributes','errors','success','value','result','attribute','read_before','reporting_config'}
        return {k:safe_report(v,depth+1) for k,v in list(value.items())[:256] if k in allowed or ENTITY_RE.fullmatch(k)}
    if isinstance(value,list):return [safe_report(v,depth+1) for v in value[:128]]
    if isinstance(value,str):
        # Remove all credential-bearing URLs and known assignments before persistence.
        from .observability import redact
        return re.sub(r'https?://[^\s<>"\']+','[URL vynechána]',redact(value))[:1000]
    if value is None or type(value) in {bool,int}:return value
    if type(value) is float:return value if math.isfinite(value) else None
    return None

def inspector(value,status):
    if not isinstance(value,dict) or value.get('schema_version')!=2 or not isinstance(value.get('automations'),dict) or not isinstance(value.get('scripts'),dict) or stamp(value.get('generated_at')) is None:
        raise ToolDenied('Automation Inspector vrátil neověřený kontrakt.')
    if not isinstance(status,dict) or status.get('ready') is not True or status.get('stale') is not False:raise ToolDenied('Výsledek Inspectoru není připravený nebo je zastaralý.')
    items=[]
    for key,row in list(value['automations'].items())+list(value['scripts'].items()):
        if not isinstance(row,dict):raise ToolDenied('Neplatná položka Inspectoru.')
        items.append({'id':key,'entity_id':row.get('entity_id'),'status':row.get('status'),'config_id':row.get('config_id'),
            'config_hash':row.get('config_hash'),'entities':safe_report(row.get('entities',[])),
            'targets':safe_report(row.get('targets',[])),'trace':safe_report(row.get('trace')),
            'issues':safe_report(row.get('compatibility_issues',[])),'issue_count':row.get('issue_count')})
    return {'generated_at':value['generated_at'],'items':items[:256],'truncated':len(items)>256,
            'app_version':value.get('app_version'),'generation':status.get('generation')}

def hadocs(value,status):
    if not isinstance(value,dict) or value.get('available') is not True or not isinstance(value.get('health'),dict) or not isinstance(value.get('incidents'),list) or not isinstance(value.get('recommendations'),list):raise ToolDenied('HADocs nemá dostupný ověřitelný report.')
    if not isinstance(status,dict) or status.get('running') is True or status.get('exit_code')!=0 or stamp(status.get('finished_at')) is None:raise ToolDenied('HADocs nemá dokončený úspěšný sken.')
    return {'generated_at':status['finished_at'],'health':safe_report(value['health']),
            'incidents':safe_report(value['incidents']),'recommendations':safe_report(value['recommendations']),
            'truncated':len(value['incidents'])>128 or len(value['recommendations'])>128}

def sensor_report(provider,registry,states):
    owned={r['entity_id'] for r in registry if isinstance(r,dict) and r.get('platform')==provider and isinstance(r.get('entity_id'),str)}
    rows=[]
    for row in states:
        if row.get('entity_id') not in owned:continue
        attrs=row.get('attributes')
        if not isinstance(attrs,dict):continue
        selected=safe_report(attrs)
        # These are documented structured sensor attributes, not a new scan.
        if selected:rows.append({'entity_id':row['entity_id'],'state':row.get('state'),'last_updated':row.get('last_updated'),'attributes':selected})
    if not rows:raise ToolDenied('Vlastní strukturované senzorové údaje nebyly přečtené.')
    return {'sensors':rows[:64],'truncated':len(rows)>64,'scope':'existing_provider_sensor_attributes_no_new_scan'}
