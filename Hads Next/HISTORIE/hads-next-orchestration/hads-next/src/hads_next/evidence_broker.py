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

from .observability import redact,project_supervisor_read,is_app_slug
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
            event_data=row.get('event_data')
            if isinstance(event_data,dict):
                item['event_data']={k:_ids(event_data[k]) for k in ('device_id','command') if k in event_data}
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
    if isinstance(value.get('context'),dict):
        result['context']={k:value['context'][k] for k in ('id','parent_id','user_id') if isinstance(value['context'].get(k),str)}
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
    'hads_get_runtime_health':{},'hads_get_incident':{}, 'hads_get_related_incidents':{}, 'hads_get_core_status':{}, 'hads_get_supported_repairs':{},
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
    'hads_get_system_log':{}, 'hads_get_system_health':{}, 'hads_get_owned_reference':{},
    'hads_get_zha_events':{'device_id':'id','start':'time','end':'time'},
    'hads_get_music_assistant_diagnostics':{'entity_id':'entity','section':'section','start':'time','end':'time'},
}


class EvidenceBroker:
    def __init__(self, store, *, core=None, core_ws=None, supervisor=None, zha=None, music=None, clock=time.time):
        self.store,self.core,self.ws,self.supervisor,self.clock=store,core,core_ws,supervisor,clock
        self.zha=zha
        self.music=music
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
            pattern={'entity':r'[a-z][a-z0-9_]*\.[a-z0-9_]+','id':r'[A-Za-z0-9_-]{1,128}','slug':r'[-_.A-Za-z0-9]{1,128}'}.get(kind)
            if not isinstance(value,str) or len(value)>128 or (pattern and not re.fullmatch(pattern,value)):
                raise BrokerDenied('Neplatný parametr '+key)
            if kind=='slug' and not is_app_slug(value):raise BrokerDenied('Neplatný identifikátor aplikace.')
            if kind=='section' and value not in {'player','health','events','buffer','logs'}:raise BrokerDenied('Nepovolené čtení Music Assistantu.')
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
                if row['kind']=='hads_get_owned_reference' and row['source']=='ha_core_ws':
                    from .managed_repair import ManagedReferenceEngine
                    try:permitted.add(ManagedReferenceEngine._entity(row['payload']['data']))
                    except ValueError:pass
                if row['kind']=='hads_get_automation_config':
                    for step in row['payload'].get('data',{}).get('actions',[]):
                        permitted.update(step.get('target',{}).get('entity_id',[]))
            if args['entity_id'] not in permitted:
                raise BrokerDenied('Entita nesouvisí s incidentem ani načtenou automatizací.')
        if 'device_id' in args:
            devices=set()
            for row in case['evidence']:
                data=row['payload'].get('data')
                if row['kind']=='hads_get_entity_registry' and isinstance(data,list):
                    devices.update(x['device_id'] for x in data if isinstance(x,dict) and x.get('device_id'))
                if row['kind']=='hads_get_automation_config' and isinstance(data,dict):
                    for step in data.get('triggers',[])+data.get('actions',[]):
                        devices.update(step.get('device_id',[]))
                        devices.update(step.get('event_data',{}).get('device_id',[]))
                        devices.update(step.get('target',{}).get('device_id',[]))
            if args['device_id'] not in devices:raise BrokerDenied('Zařízení není doložené registry ani automatizací tohoto případu.')
        resolved_automation=args.get('automation_id')
        if resolved_automation is not None:
            entities={x for x in case['incident']['components'] if x.startswith('automation.')}
            known={x.split('.',1)[1] for x in entities}
            prior={str(e['payload']['data'].get('id')) for e in case['evidence'] if e['kind']=='hads_get_automation_config' and e['source']=='ha_core' and isinstance(e.get('payload',{}).get('data'),dict)}
            if resolved_automation not in known|prior:raise BrokerDenied('Automatizace není doložená tímto spisem.')
            if resolved_automation in known and self.core is not None:
                state=self.core.states('automation.'+resolved_automation)
                actual=state.get('attributes',{}).get('id') if isinstance(state,dict) else None
                if isinstance(actual,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',actual):resolved_automation=actual
        reader=None;source='hads_database';value=None;projection=lambda x:x
        if name=='hads_get_music_assistant_diagnostics':
            if self.music is None:return self._result(incident_id,name,'music_assistant_fastmcp','unavailable',None,now,'Music Assistant FastMCP není nastavený. Použij historii HA a logy aplikace přes Supervisor.')
            from .observability import ReadFailure
            try:value=self.music.diagnostics(args['entity_id'],args['section'],start.timestamp(),end.timestamp())
            except ReadFailure as error:return self._result(incident_id,name,'music_assistant_fastmcp','not_read',None,now,str(error))
            if value is None:
                status='insufficient_permissions' if self.music.status.last_response_status in {401,403} else 'read_failed'
                return self._result(incident_id,name,'music_assistant_fastmcp',status,None,now,self.music.status.last_error)
            if len(canonical(value).encode())>12000:return self._result(incident_id,name,'music_assistant_fastmcp','read_failed',None,now,'Výsledek překročil limit důkazů.')
            status='available'
            if args['section']=='events':
                if value['data']['buffer_capacity']==0:status='not_read'
                elif not value['data']['events']:status='no_relevant_data'
            elif value['data'] is None:status='no_relevant_data'
            return self._result(incident_id,name,'music_assistant_fastmcp',status,value,now,
                'Prázdný buffer bez známé doby sběru nevylučuje dřívější událost; dodávka streamu nebyla testována.')
        elif name=='hads_get_zha_events':
            if self.zha is None:return self._result(incident_id,name,'zha_event','not_read',None,now,'Sběr ZHA událostí není zapnutý.')
            value=self.zha.query(args['device_id'],start.timestamp(),end.timestamp())
            status='available' if value['events'] else 'no_relevant_data' if value['capture_covers_window'] else 'not_read'
            observed=max((datetime.fromisoformat(x['time_fired']).timestamp() for x in value['events']),default=None)
            return self._result(incident_id,name,'zha_event',status,value,now,value['limitation_cs'],observed=observed)
        elif name=='hads_get_owned_reference' and not set(case['incident']['components']) & {'automation.hads_next_reference_test','input_boolean.hads_next_test_target'}:
            raise BrokerDenied('Spis se netýká vlastní testovací reference.')
        elif name=='hads_get_runtime_health':
            system=getattr(self,'runtime_system',None)
            if system is None:return self._result(incident_id,name,'hads_controller','unavailable',None,now,'Měření není dostupné.')
            source='hads_controller';value=system.status()
            providers=getattr(getattr(system,'app',None),'providers',None)
            if providers is not None:
                value['diagnostic_providers']=[{k:r[k] for k in ('provider_id','presence_confirmed','native_state_read_succeeded','functional_verified','gaps','checked_at','stale')} for r in providers.snapshot()]
        elif name=='hads_get_supported_repairs':
            from .repair_suggestions import supported_catalog
            value=supported_catalog()
            runtime=getattr(self,'runtime_system',None)
            tools=getattr(getattr(runtime,'app',None),'tools',None)
            if tools:
                value['orchestrated_operations']=[{k:r[k] for k in ('provider','name','schema_hash','risk','repair_operation_implemented','available')} for r in tools.registry.tools() if r['effect']=='write']
                value['production_limitation_cs']='Použij aktuální nástrojový katalog a nezávislé schválení konkrétního plánu. Změny registru a konfigurace potřebují ověřenou obnovitelnou zálohu. Obecné zápisy a neověřené operace jsou zakázané.'
        elif name=='hads_get_incident':
            value={'incident':case['incident'],'occurrences':case['occurrences'][-20:],
                   'evidence_index':[{'id':x['evidence_id'],'source':x['source'],'kind':x['kind'],'observed_at':x['observed_at']} for x in case['evidence'][-40:]]}
            value['owner_statements']=[{'text':e['payload']['text'][:1000],'evidence_id':e['evidence_id'],
                'authority':'owner_statement_not_approval_or_independent_confirmation'} for e in case['evidence']
                if e['source']=='authenticated_owner' and e['kind']=='owner_statement' and isinstance(e['payload'].get('text'),str)][-8:]
            automatic=[r['content'] for r in case['records'] if r['kind']=='automatic_read_report']
            system=getattr(self,'runtime_system',None)
            followup=system.followup.report(incident_id) if system is not None else None
            if followup:value['native_followup']=followup
            if automatic:
                latest=automatic[-1]
                value['automatic_diagnostics']={key:latest.get(key) for key in ('summary_cs','state','probe','root_cause_proven')}
                value['automatic_diagnostics'].update(measured=latest.get('measured',[])[:8],comparison=latest.get('comparison',[])[:8],gaps=latest.get('gaps',[])[:8],measured_total=len(latest.get('measured',[])),ai_view_truncated=len(latest.get('measured',[]))>8)
        elif name=='hads_get_related_incidents':
            with self.store._connect() as db:
                rows=db.execute('SELECT id,kind,symptom,components,first_seen,last_seen,status FROM incidents WHERE id!=? AND kind=? ORDER BY last_seen DESC LIMIT 10',
                    (incident_id,case['incident']['kind'])).fetchall()
            value=[dict(row) for row in rows if set(json.loads(row['components'])) & set(case['incident']['components'])]
            for related in value:
                history=self.store.case(related['id'])
                related['occurrence_count']=len(history['occurrences'])
                findings=[r['content'] for r in history['records'] if r['kind'] in {'hermes_investigation','deterministic_investigation'}]
                related['prior_findings']=[{'summary_cs':str(item.get('summary_cs',''))[:1000],
                    'authority':'previous_assessment_requires_current_evidence'} for item in findings[-2:]]
        else:
            core={'hads_get_core_status':('config',()),'hads_get_entity_state':('states',(args.get('entity_id'),)),
                'hads_get_entity_history':('history',(args.get('start'),args.get('entity_id'),args.get('end'))),
                'hads_get_automation_config':('automation_config',(resolved_automation,))}
            ws={'hads_get_entity_registry':('entity_registry',()),'hads_get_device_registry':('device_registry',()),
                'hads_get_action_history':('action_history',(args.get('start'),args.get('end'))),
                'hads_get_automation_traces':('traces',('automation',resolved_automation)),
                'hads_get_automation_trace':('trace',('automation',resolved_automation,args.get('run_id'))),
                'hads_get_integration_repairs':('repairs',()),'hads_get_system_log':('system_log',()),
                'hads_get_system_health':('system_health',()),'hads_get_owned_reference':('owned_reference',())}
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
            elif name=='hads_get_owned_reference':
                def projection(value):
                    from .managed_repair import ManagedReferenceEngine
                    ManagedReferenceEngine._entity(value)
                    return value
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
            elif name=='hads_get_action_history':
                targets=set(case['incident']['components'])
                def projection(rows):
                    projected=[]
                    for action in rows:
                        entities=sorted(targets.intersection(action.get('targets',{}).get('entity_id',[])))
                        if not entities:continue
                        projected.append({**{k:action[k] for k in ('when','domain','service','context_id','context_user_id') if k in action},
                                          'targets':{'entity_id':entities}})
                    return projected[-64:]
            elif name in {'hads_get_supervisor_status','hads_get_haos_status','hads_get_addon_info','hads_get_addon_stats'}:
                projection=lambda value:project_supervisor_read(method,value)
            elif name=='hads_get_applications':
                projection=lambda value:{'addons':[{k:row[k] for k in ('slug','name','state','version','version_latest','update_available','available') if k in row}
                    for row in value.get('addons',[])[:200] if isinstance(row,dict)]} if isinstance(value.get('addons'),list) else None
            elif name=='hads_get_addon_logs':
                projection=lambda value:{'text':value[-7000:],'truncated':len(value)>7000}
        try:
            value=redact(projection(value))
            if name in {'hads_get_supervisor_status','hads_get_haos_status','hads_get_addon_info','hads_get_addon_stats','hads_get_applications'} and not value:
                raise ValueError('missing_supervisor_fields')
            raw=canonical(value)
        except (ValueError,TypeError,KeyError,OverflowError):
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
            identity_value={k:v for k,v in value.items() if k!='retrieved_at'} if source=='public_research' and isinstance(value,dict) else value
            identity=hashlib.sha256(canonical([name,status,identity_value]).encode()).hexdigest()
            with self.store._connect() as db:
                old=db.execute('SELECT observed_at FROM evidence WHERE source=? AND event_id=?',(source,identity)).fetchone()
            self.store.add_evidence(incident_id,{'source':source,'kind':name,'event_id':identity,
                'observed_at':old[0] if old else observed if observed is not None else now,
                'payload':{'data':identity_value,'read_status':status,'time_basis':'source_timestamp' if observed is not None else 'read_snapshot_event_time_unknown'}})
            evidence_ids=[hashlib.sha256(canonical([source,identity]).encode()).hexdigest()]
        result={'tool':name,'source':source,'status':status,'data':value,'evidence_ids':evidence_ids,'read_at':now,
                'source_event_at':observed,'detail_cs':detail}
        self.store.record(incident_id,'broker_read', {k:v for k,v in result.items() if k!='data'})
        return result
