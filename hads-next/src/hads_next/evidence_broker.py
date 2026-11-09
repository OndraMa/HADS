"""Named, incident-scoped diagnostic reads. Credentials never cross this API.

Uses the existing native clients. No URL, path, code, service call or write
operation can be supplied by an investigator. Result statuses are data, never
an invented empty successful read. The trusted controller owns this object.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import threading
import time

from .observability import redact
from .evidence import canonical


class BrokerDenied(ValueError):
    pass


def _ids(value):
    if isinstance(value, str):
        value = [value]
    return [x for x in value[:64] if isinstance(x, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',x)] if isinstance(value,list) else []


def project_automation(value):
    if not isinstance(value, dict):
        raise BrokerDenied('Neplatná konfigurace automatizace.')
    def steps(rows):
        if not isinstance(rows,list): rows=[rows] if isinstance(rows,dict) else []
        result=[]
        for row in rows[:32]:
            if not isinstance(row,dict): continue
            item={k:row[k] for k in ('action','service','trigger','platform','condition','event_type')
                  if isinstance(row.get(k),str) and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,128}',row[k])}
            for key in ('entity_id','device_id'):
                if key in row:item[key]=_ids(row[key])
            target=row.get('target')
            if isinstance(target,dict):item['target']={k:_ids(target[k]) for k in ('entity_id','device_id','area_id') if k in target}
            # Arbitrary service data, templates, variables and webhook secrets
            # are deliberately excluded. Unsupported branches stay visible.
            item['omitted_fields']=sorted(set(row)-set(item))
            result.append(item)
        return result
    return {'id':str(value.get('id',''))[:128],
            'triggers':steps(value.get('triggers',value.get('trigger',[]))),
            'conditions':steps(value.get('conditions',value.get('condition',[]))),
            'actions':steps(value.get('actions',value.get('action',[]))),
            'projection':'references_and_structure_only'}


def project_trace(value):
    if not isinstance(value,dict):raise BrokerDenied('Neplatný automation trace.')
    result={k:redact(value[k]) for k in ('run_id','state','script_execution','last_step','timestamp') if k in value}
    trace=value.get('trace',{})
    if isinstance(trace,dict):
        result['steps']={}
        for path,entries in list(trace.items())[:64]:
            if not re.fullmatch(r'[a-zA-Z0-9_/-]{1,160}',path) or not isinstance(entries,list):continue
            items=[]
            for entry in entries[:8]:
                if not isinstance(entry,dict):continue
                item={k:redact(entry[k]) for k in ('timestamp','error') if isinstance(entry.get(k),str)}
                outcome=entry.get('result',{})
                if isinstance(outcome,dict):
                    item['result']={k:outcome[k] for k in ('result','choice','stop','error') if isinstance(outcome.get(k),(bool,str,int))}
                    params=outcome.get('params')
                    if isinstance(params,dict):
                        item['action']={k:params[k] for k in ('domain','service') if isinstance(params.get(k),str)}
                        data=params.get('service_data',{})
                        if isinstance(data,dict):item['target_entity_ids']=_ids(data.get('entity_id',[]))
                items.append(item)
            result['steps'][path]=items
    result['projection']='no_variables_or_service_secrets'
    return result


# Explicit HADS schemas, not upstream API names. additionalProperties=False is
# enforced again in dispatch; an LLM schema is not an authorization boundary.
_PARAMS={
    'hads_get_incident':{}, 'hads_get_related_incidents':{}, 'hads_get_core_status':{},
    'hads_get_entity_registry':{'entity_id':'entity'},'hads_get_device_registry':{'device_id':'id'},
    'hads_get_entity_state':{'entity_id':'entity'},
    'hads_get_entity_history':{'entity_id':'entity','start':'time','end':'time'},
    'hads_get_action_history':{'start':'time','end':'time'},
    'hads_get_automation_config':{'automation_id':'id'},
    'hads_get_automation_traces':{'automation_id':'id'},
    'hads_get_automation_trace':{'automation_id':'id','run_id':'id'},
    'hads_get_supervisor_status':{},'hads_get_haos_status':{},'hads_get_applications':{},
    'hads_get_addon_info':{'slug':'slug'},'hads_get_addon_stats':{'slug':'slug'},
    'hads_get_addon_logs':{'slug':'slug'}, 'hads_get_integration_repairs':{},
    'hads_get_system_log':{},
}


class EvidenceBroker:
    def __init__(self, store, *, core=None, core_ws=None, supervisor=None, clock=time.time):
        self.store,self.core,self.ws,self.supervisor,self.clock=store,core,core_ws,supervisor,clock
        self._lock=threading.RLock()
        self.extensions={}

    def schemas(self):
        result=[]
        for name,params in _PARAMS.items():
            properties={key:{'type':'string','maxLength':128 if kind!='time' else 40} for key,kind in params.items()}
            result.append({'name':name,'description':'Pouze čtení důkazů vybraného incidentu. Stav výsledku udává dostupnost zdroje.',
                'parameters':{'type':'object','properties':properties,'required':list(params),'additionalProperties':False}})
        result.extend(value['schema'] for value in self.extensions.values())
        return result

    def read(self, incident_id, name, arguments):
        with self._lock:
            return self._read(incident_id,name,arguments)

    def _read(self, incident_id,name,args):
        case=self.store.case(incident_id)
        now=self.clock()
        if name in self.extensions:
            return self.extensions[name]['read'](incident_id,args)
        if name not in _PARAMS or not isinstance(args,dict) or set(args)!=set(_PARAMS[name]):
            raise BrokerDenied('Nepovolený nástroj nebo parametry.')
        for key,kind in _PARAMS[name].items():
            value=args[key]
            pattern={'entity':r'[a-z][a-z0-9_]*\.[a-z0-9_]+','id':r'[A-Za-z0-9_-]{1,128}','slug':r'[a-z0-9_]{1,128}'}.get(kind)
            if not isinstance(value,str) or len(value)>128 or (pattern and not re.fullmatch(pattern,value)):
                raise BrokerDenied('Neplatný parametr '+key)
        if 'start' in args:
            try:
                start=datetime.fromisoformat(args['start']);end=datetime.fromisoformat(args['end'])
                if start.tzinfo is None or end.tzinfo is None:raise ValueError()
                first,last=case['incident']['first_seen'],case['incident']['last_seen']
                if not first-1800 <= start.timestamp() < end.timestamp() <= min(now+1,last+1800) or (end-start).total_seconds()>3600:
                    raise ValueError()
            except (ValueError,TypeError):raise BrokerDenied('Časové okno musí být do jedné hodiny a blízko incidentu.') from None
        if 'entity_id' in args:
            permitted=set(case['incident']['components'])
            # Newly discovered references may extend the investigation, never
            # an arbitrary entity mentioned in untrusted logs/model output.
            for row in case['evidence']:
                if row['kind']=='hads_get_automation_config':
                    for step in row['payload'].get('data',{}).get('actions',[]):
                        permitted.update(step.get('target',{}).get('entity_id',[]))
            if args['entity_id'] not in permitted:
                raise BrokerDenied('Entita nesouvisí s incidentem ani načtenou automatizací.')
        reader=None;source='hads_database';value=None;projection=lambda x:x
        if name=='hads_get_incident':
            value={'incident':case['incident'],'occurrences':case['occurrences'][-20:],
                   'evidence_index':[{'id':x['evidence_id'],'source':x['source'],'kind':x['kind'],'observed_at':x['observed_at']} for x in case['evidence'][-40:]]}
        elif name=='hads_get_related_incidents':
            with self.store._connect() as db:
                rows=db.execute('SELECT id,kind,symptom,components,first_seen,last_seen,status FROM incidents WHERE id!=? AND kind=? ORDER BY last_seen DESC LIMIT 10',
                    (incident_id,case['incident']['kind'])).fetchall()
            value=[dict(row) for row in rows if set(json.loads(row['components'])) & set(case['incident']['components'])]
        else:
            core={'hads_get_core_status':('config',()),'hads_get_entity_state':('states',(args.get('entity_id'),)),
                'hads_get_entity_history':('history',(args.get('start'),args.get('entity_id'),args.get('end'))),
                'hads_get_automation_config':('automation_config',(args.get('automation_id'),))}
            ws={'hads_get_entity_registry':('entity_registry',()),'hads_get_device_registry':('device_registry',()),
                'hads_get_action_history':('action_history',(args.get('start'),args.get('end'))),
                'hads_get_automation_traces':('traces',('automation',args.get('automation_id'))),
                'hads_get_automation_trace':('trace',('automation',args.get('automation_id'),args.get('run_id'))),
                'hads_get_integration_repairs':('repairs',()),'hads_get_system_log':('system_log',())}
            supervisor={'hads_get_supervisor_status':('info',()),'hads_get_haos_status':('os_info',()),
                'hads_get_applications':('apps',()),'hads_get_addon_info':('app_info',(args.get('slug'),)),
                'hads_get_addon_stats':('app_stats',(args.get('slug'),)),'hads_get_addon_logs':('app_logs',(args.get('slug'),))}
            catalog=core if name in core else ws if name in ws else supervisor
            reader=self.core if name in core else self.ws if name in ws else self.supervisor
            source='ha_core' if name in core else 'ha_core_ws' if name in ws else 'supervisor'
            if reader is None:
                return self._result(incident_id,name,source,'unavailable',None,now,'Zdroj není připojen.')
            method,params=catalog[name]
            value=getattr(reader,method)(*params)
            if value is None:
                if name=='hads_get_entity_state' and reader.status.last_response_status==404:
                    return self._result(incident_id,name,source,'no_relevant_data',
                        {'entity_id':args['entity_id'],'exists':False,'reason':'Core state API returned 404'},now,
                        'Entita nemá aktuální stav v Core. To samo nevysvětluje, proč chybí.')
                status='insufficient_permissions' if reader.status.last_response_status in {401,403} else 'read_failed'
                return self._result(incident_id,name,source,status,None,now,'Zdroj odmítl čtení nebo není dostupný.')
            list_tools={'hads_get_entity_registry','hads_get_device_registry','hads_get_automation_traces','hads_get_action_history','hads_get_system_log'}
            expected=list if name in list_tools or name=='hads_get_entity_history' else str if name=='hads_get_addon_logs' else dict
            if not isinstance(value,expected) or (name in list_tools and not all(isinstance(row,dict) for row in value)):
                return self._result(incident_id,name,source,'read_failed',None,now,'Zdroj vrátil neočekávané schéma; nejde o prázdný úspěšný výsledek.')
            if name=='hads_get_automation_config':projection=project_automation
            elif name=='hads_get_automation_trace':projection=project_trace
            elif name=='hads_get_core_status':
                projection=lambda value:{k:value[k] for k in ('version','state','time_zone','components') if k in value}
            elif name in {'hads_get_entity_state','hads_get_entity_history'}:
                def state(row):
                    return {k:redact(row[k]) for k in ('entity_id','state','last_updated','last_changed','context') if k in row} if isinstance(row,dict) else {}
                projection=lambda rows:state(rows) if isinstance(rows,dict) else [[state(x) for x in group[:100]] for group in rows[:8] if isinstance(group,list)]
            elif name=='hads_get_entity_registry':
                projection=lambda rows:[{k:x[k] for k in ('entity_id','unique_id','platform','device_id','config_entry_id','disabled_by') if k in x} for x in rows if isinstance(x,dict) and x.get('entity_id')==args['entity_id']]
            elif name=='hads_get_device_registry':
                projection=lambda rows:[{k:x[k] for k in ('id','manufacturer','model','config_entries','disabled_by') if k in x} for x in rows if isinstance(x,dict) and x.get('id')==args['device_id']]
            elif name=='hads_get_addon_logs':
                projection=lambda value:{'text':value[-7000:],'truncated':len(value)>7000}
        try:
            value=redact(projection(value))
            raw=canonical(value)
        except (ValueError,TypeError,KeyError):
            return self._result(incident_id,name,source,'read_failed',None,now,'Neočekávaný formát zdrojových dat.')
        if len(raw.encode())>12000:
            return self._result(incident_id,name,source,'read_failed',None,now,'Výsledek překročil limit; zúžení čtení je nutné.')
        state='no_relevant_data' if value in ([],{},'') else 'available'
        observed=None
        timestamps=[]
        def timestamp(value):
            try:
                if isinstance(value,str):
                    parsed=datetime.fromisoformat(value)
                    return parsed.timestamp() if parsed.tzinfo else None
                if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):return value
            except ValueError:pass
            return None
        if name=='hads_get_entity_state':timestamps=[timestamp(value.get('last_updated'))]
        elif name=='hads_get_entity_history':timestamps=[timestamp(row.get('last_updated')) for group in value for row in group]
        elif name=='hads_get_action_history':timestamps=[timestamp(row.get('when')) for row in value]
        elif name=='hads_get_automation_trace':timestamps=[timestamp(t) for t in value.get('timestamp',{}).values()]
        if any(t is not None for t in timestamps):observed=max(t for t in timestamps if t is not None)
        return self._result(incident_id,name,source,state,value,now,None,observed=observed)

    def _result(self, incident_id,name,source,status,value,now,detail,*,observed=None):
        evidence_ids=[]
        if status in {'available','no_relevant_data'} and value is not None and source!='hads_database':
            identity=hashlib.sha256(canonical([name,status,value]).encode()).hexdigest()
            with self.store._connect() as db:
                old=db.execute('SELECT observed_at FROM evidence WHERE source=? AND event_id=?',(source,identity)).fetchone()
            self.store.add_evidence(incident_id,{'source':source,'kind':name,'event_id':identity,
                'observed_at':old[0] if old else observed if observed is not None else now,
                'payload':{'data':value,'read_status':status,'time_basis':'source_timestamp' if observed is not None else 'read_snapshot_event_time_unknown'}})
            evidence_ids=[hashlib.sha256(canonical([source,identity]).encode()).hexdigest()]
        result={'tool':name,'source':source,'status':status,'data':value,'evidence_ids':evidence_ids,'read_at':now,
                'source_event_at':observed,'detail_cs':detail}
        self.store.record(incident_id,'broker_read', {k:v for k,v in result.items() if k!='data'})
        return result
