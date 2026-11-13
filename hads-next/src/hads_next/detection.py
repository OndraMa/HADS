"""Persistent bounded functional monitors. No log-error-to-incident heuristic."""
import hashlib
import json
import re
import threading
import time
from datetime import datetime
from .evidence import canonical
from .observability import ReadFailure

ENTITY=re.compile(r'[a-z][a-z0-9_]*\.[a-z0-9_]+')

class DetectionEngine:
    def __init__(self,app):
        self.app=app;self.stop=threading.Event();self.thread=None;self.poll_thread=None;self.lock=threading.RLock()
        self._latest_states={}
        self.health={'state':'stopped','last_event_at':None,'last_error':None,'continuous_since':None,'heartbeat_at':None,'last_system_check_at':None}
        with app.store._connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS detection_rules(id TEXT PRIMARY KEY,document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS detection_state(rule_id TEXT PRIMARY KEY,document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS detection_settings(id INTEGER PRIMARY KEY,autonomous INTEGER NOT NULL DEFAULT 0);
            INSERT OR IGNORE INTO detection_settings VALUES(1,0);''')
        # Pending deadlines cannot span an unobserved restart.
        with app.store._connect() as db:db.execute('DELETE FROM detection_state')

    def rules(self):
        with self.app.store._connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT document FROM detection_rules ORDER BY id')]

    def configure(self,rule,principal):
        if principal!=self.app.owner() or not principal:raise ValueError('Pravidla může měnit jen vlastník.')
        if set(rule)-{'entity_id','kind','expected','grace_seconds','trigger_entity','enabled','automation_entity','trigger_state'}:raise ValueError('Neznámá pole pravidla.')
        if not ENTITY.fullmatch(str(rule.get('entity_id',''))) or rule.get('kind') not in {'unavailable','state','playback','response'}:raise ValueError('Neplatné pravidlo.')
        if type(rule.get('enabled',True)) is not bool:raise ValueError('Neplatný stav pravidla.')
        grace=rule.get('grace_seconds',30)
        if type(grace) is not int or not 1<=grace<=3600:raise ValueError('Doba musí být 1 až 3600 sekund.')
        expected=rule.get('expected','playing' if rule['kind']=='playback' else 'on')
        if not isinstance(expected,str) or not re.fullmatch(r'[A-Za-z0-9_. -]{1,64}',expected):raise ValueError('Neplatný očekávaný stav.')
        trigger=rule.get('trigger_entity','')
        if rule['kind']=='response' and not ENTITY.fullmatch(trigger):raise ValueError('Chybí spouštěcí entita.')
        automation=rule.get('automation_entity','')
        if automation and not re.fullmatch(r'automation\.[a-z0-9_]+',automation):raise ValueError('Neplatná automatizace.')
        trigger_state=rule.get('trigger_state','')
        if not isinstance(trigger_state,str) or len(trigger_state)>64:raise ValueError('Neplatný spouštěcí stav.')
        document={'trigger_state':trigger_state,'automation_entity':automation,'entity_id':rule['entity_id'],'kind':rule['kind'],'expected':expected,'grace_seconds':grace,'trigger_entity':trigger,'enabled':rule.get('enabled',True)}
        identity=hashlib.sha256((document['kind']+':'+document['entity_id']+':'+trigger).encode()).hexdigest()[:24]
        with self.lock,self.app.store._connect() as db:
            if db.execute('SELECT count(*) FROM detection_rules').fetchone()[0]>=32 and not db.execute('SELECT 1 FROM detection_rules WHERE id=?',(identity,)).fetchone():raise ValueError('Nejvýše 32 pravidel.')
            db.execute('INSERT OR REPLACE INTO detection_rules VALUES(?,?)',(identity,canonical(dict(document,id=identity))))
            db.execute('DELETE FROM detection_state WHERE rule_id=?',(identity,))
        return identity

    def consent(self,enabled,principal):
        if principal!=self.app.owner() or type(enabled) is not bool:raise ValueError('Chybí vlastník.')
        with self.app.store._connect() as db:db.execute('UPDATE detection_settings SET autonomous=? WHERE id=1',(int(enabled),))

    def snapshot(self):
        with self.app.store._connect() as db:enabled=bool(db.execute('SELECT autonomous FROM detection_settings WHERE id=1').fetchone()[0])
        return {**self.health,'rules':self.rules(),'autonomous_ai':enabled,'limit':32,'no_model_required':True}

    def ready(self):
        with self.lock:
            now=self.app.clock();self.health.update(state='listening',continuous_since=now,heartbeat_at=now,last_error=None)
            self._latest_states.clear()
            with self.app.store._connect() as db:db.execute('DELETE FROM detection_state')

    def heartbeat(self):
        with self.lock:
            now=self.app.clock()
            if self.health['heartbeat_at'] is not None and now-self.health['heartbeat_at']>15:self.ready()
            self.health['heartbeat_at']=now

    def gap(self,error):
        with self.lock:
            self.health.update(state='unavailable',continuous_since=None,last_error=error)
            with self.app.store._connect() as db:db.execute('DELETE FROM detection_state')

    def ingest(self,event):
        if event.get('event_type')!='state_changed':return
        data=event.get('data',{});entity=data.get('entity_id');raw=data.get('new_state')
        if not isinstance(raw,dict) or not ENTITY.fullmatch(str(entity or '')):return
        try:stamp=datetime.fromisoformat(event['time_fired']).timestamp()
        except (ValueError,KeyError,TypeError):return
        now=self.app.clock()
        if not now-60<=stamp<=now+5:return
        from .haos_application import project_state
        state=project_state(raw)
        if not state or state['entity_id']!=entity:return
        if self.health['heartbeat_at'] is not None and now-self.health['heartbeat_at']>15:self.ready()
        old=data.get('old_state') or {};value=state['state'];self.health['last_event_at']=stamp
        watched={r['entity_id'] for r in self.rules() if r['enabled']}
        if entity in watched:self._latest_states[entity]=value
        repairs=getattr(self.app,'repairs',None)
        if repairs:repairs.observe_state(state,stamp)
        with self.lock,self.app.store._connect() as db:
            for rule in self.rules():
                if not rule['enabled'] or entity not in {rule['entity_id'],rule['trigger_entity']}:continue
                row=db.execute('SELECT document FROM detection_state WHERE rule_id=?',(rule['id'],)).fetchone()
                pending=json.loads(row[0]) if row else None
                # Trigger means a real transition, not a repeated read or same-state attributes.
                if rule['kind']=='response':
                    if entity==rule['trigger_entity'] and old.get('state')!=value and (not rule.get('trigger_state') or value==rule['trigger_state']):
                        if self._latest_states.get(rule['entity_id'])==rule['expected']:pending=None
                        elif pending is None:pending={'since':stamp,'event':state,'trigger_at':stamp,'matched':False}
                    elif entity==rule['entity_id'] and pending and value==rule['expected'] and stamp>=pending['since']:
                        pending=None
                else:
                    failing=value in {'unavailable','unknown'} if rule['kind']=='unavailable' else value!=rule['expected']
                    if not failing:pending=None
                    elif pending is None:
                        # Playback is only armed by observed playing -> not-playing.
                        if rule['kind']=='playback' and old.get('state')!=rule['expected']:continue
                        pending={'since':stamp,'event':state,'reported':False}
                if pending is None:db.execute('DELETE FROM detection_state WHERE rule_id=?',(rule['id'],))
                else:db.execute('INSERT OR REPLACE INTO detection_state VALUES(?,?)',(rule['id'],canonical(pending)))
        self.tick()

    def tick(self):
        now=self.app.clock();events=[]
        with self.lock,self.app.store._connect() as db:
            if self.health['state']!='listening' or now-(self.health['heartbeat_at'] or 0)>15:return
            rules={r['id']:r for r in self.rules()}
            for row in db.execute('SELECT rule_id,document FROM detection_state').fetchall():
                rule=rules.get(row[0]);pending=json.loads(row[1])
                if not rule or not rule['enabled'] or pending.get('reported') or now-pending['since']<rule['grace_seconds']:continue
                if rule['kind']=='response' and rule['entity_id'] not in self._latest_states:
                    if self.app.core is None or not self.app._read_lock.acquire(blocking=False):continue
                    try:actual=self.app.core.states(rule['entity_id'])
                    finally:self.app._read_lock.release()
                    if not isinstance(actual,dict) or not isinstance(actual.get('state'),str):
                        self.health['last_error']='Chybí čerstvý stav cíle; nesplněnou odezvu nelze doložit.';continue
                    self._latest_states[rule['entity_id']]=actual['state']
                if rule['kind']=='response' and self._latest_states.get(rule['entity_id'])==rule['expected']:
                    db.execute('DELETE FROM detection_state WHERE rule_id=?',(rule['id'],));continue
                pending['reported']=True;db.execute('UPDATE detection_state SET document=? WHERE rule_id=?',(canonical(pending),row[0]));events.append((rule,pending))
        for rule,pending in events:self._incident(rule,pending,now)

    def _incident(self,rule,pending,now):
        text={'unavailable':'Zařízení zůstává nedostupné','state':'Monitorovaná funkce nedosáhla očekávaného stavu','playback':'Přehrávání skončilo během dohodnutého sledování','response':'Po spouštěcí události nenásledovala očekávaná odezva'}[rule['kind']]
        identity=hashlib.sha256(canonical([rule['id'],pending['since'],pending['event']]).encode()).hexdigest()
        with self.app.store._connect() as db:
            count=db.execute('SELECT count(*) FROM occurrences').fetchone()[0]
        if count>=10000:
            self.health['last_error']='Úložiště výskytů dosáhlo limitu; exportuj a archivuj historii. Nové důkazy se nesmějí tiše ztrácet.'
            return
        incident=self.app.store.open_incident('functional_monitor',text,[x for x in (rule['entity_id'],rule.get('automation_entity',''),rule.get('trigger_entity','')) if x],now,correlation_key='monitor:'+rule['id'],occurrence_id=identity)
        self.app.store.add_evidence(incident['id'],{'source':'ha_core_state_events','kind':'functional_condition_failed','observed_at':now,'event_id':identity,'payload':{'rule':rule,'started_at':pending['since'],'last_state':pending['event'],'coverage_since':self.health['continuous_since'],'cause_proven':False}})
        repairs=getattr(self.app,'repairs',None)
        if repairs:repairs.on_functional_failure(incident['id'],rule['entity_id'],now,identity)
        self.app.store.record(incident['id'],'deterministic_investigation',{'summary_cs':text+'. Příčina zatím není doložená. Porovnej historii, akce a trace.','next_test_cs':'Ověř očekávané chování a načti související důkazy.'})
        if self.snapshot()['autonomous_ai']:
            try:self.app.investigations.start(incident['id'],self.app.owner(),automatic=True)
            except ValueError:self.app.store.record(incident['id'],'automatic_investigation_deferred',{'summary_cs':'AI nelze nyní spustit; spis a lokální sledování zůstávají zachované.'})

    def start(self):
        transport=getattr(self.app.core_ws,'transport',None)
        if not callable(getattr(transport,'state_events',None)):return False
        if self.thread and self.thread.is_alive():return True
        self.stop.clear()
        def run():
            while not self.stop.is_set():
                try:transport.state_events(self.stop,self.ingest,self.ready,self.heartbeat)
                except Exception:self.gap('Odběr změn stavů není dostupný. Mezera není důkaz poruchy.')
                if self.stop.wait(10):break
        def timer():
            while not self.stop.wait(1):
                try:
                    self.tick()
                    now=self.app.clock()
                    if now-(self.health['last_system_check_at'] or 0)>=300:
                        self.app.request_source_check();self.health['last_system_check_at']=now
                    repairs=getattr(self.app,"repairs",None)
                    if repairs:repairs.verify_pending()
                except Exception:self.health['last_error']='Kontrola podmínek selhala; nelze potvrdit úplné pokrytí.'
        self.thread=threading.Thread(target=run,daemon=True,name='hads-state-monitor');self.thread.start()
        self.poll_thread=threading.Thread(target=timer,daemon=True,name='hads-monitor-deadlines');self.poll_thread.start();return True

    def close(self):
        self.stop.set()
        for thread in (self.thread,self.poll_thread):
            if thread:thread.join(timeout=3)
        self.gap('Sledování bylo zastaveno.')
