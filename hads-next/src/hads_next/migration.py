"""Idempotent non-authorizing import of the supported Next evidence export."""
import hashlib,json
from .evidence import canonical,normalize_evidence


def import_case(store,document):
    raw=canonical(document)
    if len(raw.encode())>512*1024 or document.get('schema_version')!=1:raise ValueError('Podporován je export spisu Next schema 1 do 512 KiB.')
    case=document.get('incident',{});events=document.get('evidence',[]);occurrences=document.get('occurrences',[])
    if not isinstance(case.get('id'),str) or not isinstance(case.get('components'),list) or len(case['components'])>64 or not all(isinstance(x,str) and len(x)<=200 for x in case['components']):raise ValueError('Neplatný spis.')
    if not events or len(events)>1000 or len(occurrences)>2000:raise ValueError('Chybí důkazy nebo je překročen limit.')
    # Import identity ignores decisions/analyses; source changes do not replace
    # earlier evidence or import a valid approval/lease/token/execution.
    source=hashlib.sha256(case['id'].encode()).hexdigest()
    prepared=[]
    for event in events:
        clean=normalize_evidence(event);clean['source']='import:'+source[:16]+':'+clean['source'][:150]
        clean['payload']={'imported_unverified':True,'original_source':event['source'],'data':clean['payload']}
        prepared.append(normalize_evidence(clean))
    # Validate everything before writing; import uses a separate correlation key.
    at=min(e['observed_at'] for e in prepared)
    incident=store.open_incident('imported_history',str(case.get('symptom','Historický incident'))[:1000],case['components'],at,correlation_key='import:'+source,occurrence_id='import:'+source)
    added=sum(store.add_evidence(incident['id'],e) for e in prepared)
    with store._connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS case_imports(source_id TEXT PRIMARY KEY,incident_id TEXT NOT NULL)')
        first=db.execute('INSERT OR IGNORE INTO case_imports VALUES(?,?)',(source,incident['id'])).rowcount
    if first:store.record(incident['id'],'historical_import',{'original_case_id':case['id'],'authority':'none','original_status':case.get('status'),'approval_imported':False,'verification':'requires_current_native_evidence'})
    return {'incident_id':incident['id'],'new_evidence':added,'approvals_imported':0}
