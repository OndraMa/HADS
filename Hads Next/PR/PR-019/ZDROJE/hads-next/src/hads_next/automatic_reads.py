"""Persistent, bounded incident-driven native reads. No shell, model or writer."""
import hashlib,json,re,threading,socket,ssl
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from .evidence import canonical
from .observability import project_supervisor_read,_NoRedirect,ReadFailure,is_app_slug


def probe_github():
    """Fixed unauthenticated HEAD; no response content, redirect or URL input."""
    result={'scope':'HADS_application_network_not_Core','http_status':None,'reachable':False}
    try:
        with build_opener(_NoRedirect).open(Request('https://github.com/',method='HEAD',headers={'User-Agent':'HADS-native-diagnostics'}),timeout=8) as response:
            result.update(http_status=response.status,reachable=200<=response.status<400,phase='http')
    except HTTPError as error:result.update(http_status=error.code,phase='http')
    except Exception as error:
        reason=error.reason if isinstance(error,URLError) else error
        result['phase']='dns' if isinstance(reason,socket.gaierror) else 'tls' if isinstance(reason,ssl.SSLError) else 'timeout' if isinstance(reason,TimeoutError) else 'redirect' if isinstance(reason,ReadFailure) and str(reason)=='redirect_refused' else 'connection'
    return result


class AutomaticReads:
    MAX_APPS=24
    def __init__(self,app):
        self.app=app;self.stop=threading.Event();self.thread=None;self.lock=threading.Lock()
        with app.store._connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS automatic_read_cases(
                id TEXT PRIMARY KEY,incident_id TEXT NOT NULL,episode REAL NOT NULL,state TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS automatic_read_tasks(
                case_id TEXT NOT NULL,kind TEXT NOT NULL,target TEXT NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
                result TEXT,read_at REAL,PRIMARY KEY(case_id,kind,target));''')
            # Repeating an interrupted GET is safe; attempts remain bounded.
            db.execute("UPDATE automatic_read_tasks SET state='pending' WHERE state='reading'")
    def schedule_memory(self,incident_id):return self._schedule(incident_id,'memory',('core_stats','supervisor_stats','inventory'))
    def schedule_marketplace(self,incident_id):return self._schedule(incident_id,'marketplace',('github_head',))
    def _schedule(self,incident_id,plan,kinds):
        with self.app.store._connect() as db:
            incident=db.execute('SELECT last_seen FROM incidents WHERE id=?',(incident_id,)).fetchone()
            if incident is None:raise KeyError(incident_id)
            identity=hashlib.sha256(canonical([plan,incident_id,incident[0]]).encode()).hexdigest()
            now=self.app.clock()
            inserted=db.execute('INSERT OR IGNORE INTO automatic_read_cases VALUES(?,?,?,?,?,?)',(identity,incident_id,incident[0],'pending',now,now)).rowcount
            if inserted:
                for kind in kinds:
                    db.execute('INSERT INTO automatic_read_tasks(case_id,kind,target,state) VALUES(?,?,?,?)',(identity,kind,'','pending'))
            else:
                db.execute("UPDATE automatic_read_tasks SET state='pending' WHERE case_id=? AND state='unavailable' AND attempts<2 AND read_at<=?",(identity,now-300))
                previous=db.execute('SELECT state,created_at FROM automatic_read_cases WHERE id=?',(identity,)).fetchone()
                followup=db.execute("SELECT 1 FROM automatic_read_tasks WHERE case_id=? AND kind='core_stats_followup'",(identity,)).fetchone()
                if plan=='memory' and previous['state'].startswith('completed') and now-previous['created_at']>=300 and followup is None:
                    targets=[]
                    for row in db.execute("SELECT target,result FROM automatic_read_tasks WHERE case_id=? AND kind='app_stats' AND state='read'",(identity,)):
                        result=json.loads(row['result']);targets.append((result['data']['memory_usage'],row['target']))
                    selected={slug for _,slug in sorted(targets,reverse=True)[:2]}
                    if any(slug=='local_hads_next_practical' for _,slug in targets):selected.add('local_hads_next_practical')
                    for kind,target in [('core_stats_followup',''),('supervisor_stats_followup','')]+[('app_stats_followup',slug) for slug in sorted(selected)]:
                        db.execute("INSERT OR IGNORE INTO automatic_read_tasks(case_id,kind,target,state) VALUES(?,?,?,'pending')",(identity,kind,target))
                    db.execute("UPDATE automatic_read_cases SET state='pending' WHERE id=?",(identity,))
            pending=db.execute("SELECT 1 FROM automatic_read_tasks WHERE case_id=? AND state IN ('pending','reading') LIMIT 1",(identity,)).fetchone()
        if inserted:self._report(identity)
        elif pending is None:self._maybe_deep(incident_id)
        self.start();return identity
    def _maybe_deep(self,incident_id):
        # Native reads need no model consent. Deep analysis needs both explicit
        # extended-mode consent and the separate autonomous investigation choice.
        status=self.app.investigations.provider.public_status()
        if not status.get('enabled') or not status.get('automatic_model_calls_allowed') or not self.app.detection.snapshot()['autonomous_ai']:return
        from .readiness import memory_available
        available=memory_available()
        if available is None or available<576*1048576:return
        try:self.app.investigations.start(incident_id,self.app.owner(),automatic=True)
        except ValueError:pass
    def start(self):
        if not self.app.owner() or self.app.supervisor is None or self.stop.is_set():return
        with self.lock:
            if self.thread and self.thread.is_alive():return
            self.thread=threading.Thread(target=self._run,daemon=True,name='hads-automatic-native-reads');self.thread.start()
    def _run(self):
        while not self.stop.is_set():
            try:
                worked=self.run_one()
            except Exception as error:
                # Preserve pending state/attempt count; do not restart a model
                # or consume the household's CPU in a retry loop.
                with self.app.store._connect() as db:
                    db.execute("UPDATE automatic_read_tasks SET state='unavailable' WHERE state='reading'")
                    db.execute("UPDATE automatic_read_cases SET state='blocked' WHERE state IN ('pending','reading')")
                return
            if not worked:return
            self.stop.wait(.2)
    def run_one(self):
        with self.app.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT t.*,c.incident_id FROM automatic_read_tasks t JOIN automatic_read_cases c ON c.id=t.case_id WHERE t.state='pending' ORDER BY c.created_at,t.rowid LIMIT 1").fetchone()
            if row is None:return False
            if row['attempts']>=2:
                db.execute("UPDATE automatic_read_tasks SET state='unavailable' WHERE case_id=? AND kind=? AND target=?",(row['case_id'],row['kind'],row['target']))
                exhausted=True
            else:
                db.execute("UPDATE automatic_read_tasks SET state='reading',attempts=attempts+1 WHERE case_id=? AND kind=? AND target=?",(row['case_id'],row['kind'],row['target']))
                exhausted=False
        if exhausted:self._report(row['case_id']);return True
        result={'read_succeeded':False,'source':row['kind'],'target':row['target'],'last_error':None}
        reader=self.app.supervisor
        kind=row['kind'].removesuffix('_followup')
        try:
            with self.app._read_lock:
                if reader is None:raise ValueError('source_not_configured')
                if kind=='github_head':value=probe_github()
                elif kind=='core_stats':value=reader.core_stats()
                elif kind=='supervisor_stats':value=reader.supervisor_stats()
                elif kind=='inventory':value=reader.apps()
                elif kind=='app_stats' and is_app_slug(row['target']):value=reader.app_stats(row['target'])
                else:raise ValueError('unsupported_read')
                status=reader.status.snapshot(self.app.clock())
                if kind!='github_head':result['source_status']={key:status.get(key) for key in ('interface_available','authenticated','last_read_at','last_response_status')}
                if row['kind']=='github_head':result.update(read_succeeded=True,probe=value)
                elif value is None:
                    result['last_error']=status.get('last_error') or 'read_failed'
                    result['http_status']=status.get('last_response_status')
                elif row['kind']=='inventory':
                    rows=value.get('addons') if isinstance(value,dict) else None
                    if not isinstance(rows,list) or len(rows)>1000:raise ValueError('invalid_inventory')
                    valid_rows=[a for a in rows if isinstance(a,dict) and is_app_slug(a.get('slug'))]
                    result['invalid_inventory_rows']=len(rows)-len(valid_rows)
                    apps=[{'slug':a['slug'],'name':str(a.get('name',a['slug']))[:120]}
                          for a in valid_rows if a.get('state')=='started']
                    result.update(read_succeeded=True,apps=apps[:self.MAX_APPS],truncated=len(apps)>self.MAX_APPS,
                        unverified_app_states=sum(a.get('state') not in {'started','stopped','error'} for a in valid_rows))
                else:
                    stats=project_supervisor_read('app_stats',value)
                    if 'memory_usage' not in stats or 'memory_limit' not in stats:raise ValueError('missing_memory_statistics')
                    result.update(read_succeeded=True,data=stats)
        except Exception as error:
            result['last_error']='Čtení neposkytlo ověřitelné údaje ('+type(error).__name__+').'
        now=self.app.clock()
        with self.app.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if result['read_succeeded'] and row['kind']=='inventory':
                for a in result['apps']:
                    db.execute("INSERT OR IGNORE INTO automatic_read_tasks(case_id,kind,target,state) VALUES(?,?,?,'pending')",(row['case_id'],'app_stats',a['slug']))
            db.execute('UPDATE automatic_read_tasks SET state=?,result=?,read_at=? WHERE case_id=? AND kind=? AND target=?',('read' if result['read_succeeded'] else 'unavailable',canonical(result),now,row['case_id'],row['kind'],row['target']))
            db.execute("UPDATE automatic_read_cases SET state='reading',updated_at=? WHERE id=?",(now,row['case_id']))
        event_id=hashlib.sha256(canonical([row['case_id'],row['kind'],row['target'],result]).encode()).hexdigest()
        with self.app.store._connect() as db:old=db.execute("SELECT observed_at FROM evidence WHERE source='automatic_native_reads' AND event_id=?",(event_id,)).fetchone()
        self.app.store.add_evidence(row['incident_id'],{'source':'automatic_native_reads','kind':'native_diagnostic_read','observed_at':old[0] if old else now,'event_id':event_id,'payload':result})
        self._report(row['case_id']);return True
    def _report(self,identity):
        with self.app.store._connect() as db:
            case=db.execute('SELECT * FROM automatic_read_cases WHERE id=?',(identity,)).fetchone()
            rows=db.execute('SELECT * FROM automatic_read_tasks WHERE case_id=? ORDER BY rowid',(identity,)).fetchall()
            remaining=sum(r['state'] in {'pending','reading'} for r in rows)
            gaps=[{'source':r['kind'],'target':r['target']} for r in rows if r['state']=='unavailable']
            for r in rows:
                data=json.loads(r['result']) if r['result'] else {}
                if r['kind']=='inventory' and (data.get('truncated') or data.get('unverified_app_states') or data.get('invalid_inventory_rows')):gaps.append({'source':'inventory','target':'','reason':'limited_coverage'})
            state='reading' if remaining else 'completed_with_gaps' if gaps else 'completed'
            db.execute('UPDATE automatic_read_cases SET state=?,updated_at=? WHERE id=?',(state,self.app.clock(),identity))
        measured=[];inventory=None;initial={};comparison=[]
        for row in rows:
            if row['kind']=='github_head':
                result=json.loads(row['result']) if row['result'] else {}
                probe=result.get('probe',{})
                summary='HADS automaticky ověřuje přístup ke GitHubu ze své aplikace.' if remaining else \
                    'Z aplikace HADS je GitHub dostupný. To nepotvrzuje stejné připojení integrace v Core.' if probe.get('reachable') else \
                    'HADS zaznamenal při přístupu ke GitHubu problém ve fázi '+str(probe.get('phase','nedostupné čtení'))+'. Příčina chyby Marketplace v Core tím ještě není prokázaná.'
                self.app.store.record(case['incident_id'],'automatic_read_report',{'summary_cs':summary,'state':state,'measured':[],
                    'probe':probe,'gaps':gaps,'root_cause_proven':False,'repair_performed':False,'model_calls':0,'shell_used':False,
                    'next_test_cs':'HADS sám porovnává další System Health a protokol Marketplace. Změnu DNS nebo restart nabídne pouze s doloženou příčinou a samostatným schválením. Diagnostické příkazy od uživatele nepožaduje.'})
                if not remaining:self._maybe_deep(case['incident_id'])
                return
        for row in rows:
            if not row['result']:continue
            result=json.loads(row['result'])
            if row['kind']=='inventory' and result['read_succeeded']:inventory=result
            if result['read_succeeded'] and 'data' in result:
                kind=row['kind'].removesuffix('_followup');key=(kind,row['target'])
                label='Home Assistant Core' if kind=='core_stats' else 'Supervisor' if kind=='supervisor_stats' else row['target']
                if row['kind'].endswith('_followup') and key in initial:
                    comparison.append({'component':kind,'target':row['target'],'change_bytes':result['data']['memory_usage']-initial[key]['memory_usage'],'elapsed_seconds':max(0,row['read_at']-initial[key]['observed_at'])})
                    measured=[item for item in measured if (item['component'],item['target'])!=key]
                item={'component':kind,'target':row['target'],'label':label,'memory_usage':result['data']['memory_usage'],'memory_limit':result['data']['memory_limit'],'observed_at':row['read_at']}
                measured.append(item)
                if not row['kind'].endswith('_followup'):initial[key]=item
        if inventory:
            names={a['slug']:a['name'] for a in inventory['apps']}
            for item in measured:item['label']=names.get(item['target'],item['label'])
        measured.sort(key=lambda x:x['memory_usage'],reverse=True)
        summary='HADS automaticky čte paměť Core, Supervisora a běžících aplikací.'
        if measured:summary+=' Největší dosud přečtený spotřebitel: '+measured[0]['label']+' ('+str(round(measured[0]['memory_usage']/1048576))+' MiB).'
        core=next((item for item in measured if item['component']=='core_stats'),None)
        hads=next((item for item in measured if item['target']=='local_hads_next_practical'),None)
        shared_limit=bool(core and hads and core['memory_limit']==hads['memory_limit'] and core['memory_limit']>0)
        if shared_limit:summary+=' Core a HADS hlásí stejný limit paměti; samostatný nižší limit HADS tím není doložený.'
        if remaining:summary+=' Zbývajících čtení: '+str(remaining)+'.'
        else:summary+=' Automatická čtení jsou dokončená'+(' s mezerami v dostupnosti.' if gaps else '.')
        summary+=' Jediné měření nedokazuje únik paměti ani neospravedlňuje restart. Součet statistik není volná paměť hostitele.'
        if comparison:summary+=' HADS provedl i druhé měření; změny spotřeby jsou uložené ve spisu. Dvě měření stále sama nedokazují příčinu.'
        document={'summary_cs':summary,'state':state,'measured':measured,'comparison':comparison,'gaps':gaps,'core_and_hads_same_reported_limit':shared_limit,'inventory_truncated':bool(inventory and inventory['truncated']),
                  'root_cause_proven':False,'repair_performed':False,'model_calls':0,'shell_used':False,'next_test_cs':
                  'HADS dokončí dostupná čtení sám. Při dalším skutečném výskytu porovná nové statistiky; opravu nabídne až při doloženém bezpečném cíli. Změnu aplikací ani diagnostické příkazy od uživatele nepožaduje.'}
        self.app.store.record(case['incident_id'],'automatic_read_report',document)
        if not remaining:self._maybe_deep(case['incident_id'])
    def report(self,incident_id):
        with self.app.store._connect() as db:
            row=db.execute("SELECT content FROM case_records WHERE incident_id=? AND kind='automatic_read_report' ORDER BY id DESC LIMIT 1",(incident_id,)).fetchone()
        return json.loads(row[0]) if row else None
    def close(self):
        self.stop.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(1)
