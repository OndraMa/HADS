"""Additional native contracts for shared orchestration, not new diagnostics."""
from datetime import datetime,timezone
from .connector_policy import descriptor
from .tool_registry import object_schema,ENTITY,ToolDenied
from .provider_reports import safe_report


def install(tools):
    rows=[descriptor('statistics',object_schema({'entity_id':ENTITY}),contract='Core_2026.11_recorder/list_statistic_ids_and_statistics_during_period'),
          descriptor('core_logs',object_schema(),contract='Supervisor_GET_/core/logs'),
          descriptor('supervisor_logs',object_schema(),contract='Supervisor_GET_/supervisor/logs')]
    # Install after native catalog replacement each pass.
    for provider,names in [('core',{'statistics','core_logs'}),('supervisor',{'supervisor_logs'})]:
        old=[{k:v for k,v in t.items() if k not in {'available','diagnostic_read_verified'}} for t in tools.registry.tools() if t['provider']==provider]
        tools.registry.replace(provider,old+[r for r in rows if r['name'] in names])
        for name in names:tools.routes[(provider,name)]=('native_extra',None)


def read(app,name,args):
    if name in {'core_logs','supervisor_logs'}:
        if app.supervisor is None:raise ToolDenied('Supervisor není připojený.')
        value=app.supervisor._read('/core/logs' if name=='core_logs' else '/supervisor/logs')
        if not isinstance(value,str):raise ToolDenied('Log nebyl přečtený.')
        # Logs are untrusted data; bounded and redacted before model/persistence.
        from .music_assistant import safe_music
        from .observability import redact
        return {'text':safe_music(redact(value))[-6000:],'truncated':len(value)>6000,'source_event_time_unknown':True}
    if name=='statistics':
        if app.core_ws is None:raise ToolDenied('Recorder není připojený.')
        ids=app.core_ws.transport({'type':'recorder/list_statistic_ids'})
        if not isinstance(ids,list):raise ToolDenied('Metadata statistik nebyla přečtená.')
        row=next((r for r in ids if isinstance(r,dict) and r.get('statistic_id')==args['entity_id']),None)
        if row is None:return {'statistic_id':args['entity_id'],'metadata_exists':False,'values':[],'root_cause_proven':False}
        now=app.clock();iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        values=app.core_ws.transport({'type':'recorder/statistics_during_period','statistic_ids':[args['entity_id']],
            'start_time':iso(now-86400),'end_time':iso(now),'period':'hour','types':['mean','min','max','state','sum','last_reset']})
        if not isinstance(values,dict) or not isinstance(values.get(args['entity_id']),list):raise ToolDenied('Historie statistik nebyla přečtená.')
        state=app.core.states(args['entity_id']) if app.core else None
        attrs=state.get('attributes') if isinstance(state,dict) else None
        mismatch=isinstance(attrs,dict) and row.get('unit_of_measurement')!=attrs.get('unit_of_measurement')
        return {'unit_mismatch_observed':mismatch,'root_cause_proven':False,'statistic_id':args['entity_id'],'metadata':safe_report(row),'entity_metadata':safe_report(attrs) if isinstance(attrs,dict) else None,
                'values':safe_report(values[args['entity_id']][:48]),'time_unit':'Core start/end are milliseconds since epoch',
                'write_available':False,'manual_alternative_cs':'Změnu hodnot nebo jednotek připrav až po porovnání metadat, historie a původní jednotky zdroje. V HA použij Vývojářské nástroje → Statistiky pro tento přesný statistic_id. Hromadný import, mazání nebo změna jednotky bez ověřené obnovitelné zálohy se neprovádí.'}
    raise ToolDenied('Neznámý nativní kontrakt.')
