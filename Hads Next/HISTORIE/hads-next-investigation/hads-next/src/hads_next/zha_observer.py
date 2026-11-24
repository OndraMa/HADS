"""Bounded zha_event journal with explicit capture coverage, never inferred presses.

Only a trusted native websocket collector can append observations. Model tools
can query a case-scoped time range; they cannot subscribe, inject or configure.
"""
from datetime import datetime
import hashlib
import json
import re
import threading
import time

from .evidence import canonical
from .observability import ReadFailure


def project_event(event):
    if not isinstance(event,dict) or event.get('event_type')!='zha_event':raise ValueError('not_zha_event')
    stamp=datetime.fromisoformat(event['time_fired'])
    if stamp.tzinfo is None:raise ValueError('timezone_required')
    data=event.get('data',{})
    if not isinstance(data,dict):raise ValueError('invalid_event_data')
    result={'event_type':'zha_event','time_fired':stamp.isoformat(),'data':{},'context':{}}
    for key in ('device_id','device_ieee','unique_id','command'):
        value=data.get(key)
        if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',value):result['data'][key]=value
    for key in ('endpoint_id','cluster_id'):
        value=data.get(key)
        if isinstance(value,int) and not isinstance(value,bool) and 0<=value<=65535:result['data'][key]=value
    for key in ('id','parent_id','user_id'):
        value=event.get('context',{}).get(key)
        if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value):result['context'][key]=value
    # args/params can contain lock PINs and are deliberately never persisted.
    if not result['data'].get('device_id'):raise ValueError('missing_device_id')
    return stamp.timestamp(),result


class ZHAJournal:
    SCHEMA=1
    def __init__(self,store,clock=time.time):
        self.store,self.clock=store,clock
        with store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS zha_journal_schema(version INTEGER PRIMARY KEY)')
            versions=[r[0] for r in db.execute('SELECT version FROM zha_journal_schema')]
            if versions and versions!=[self.SCHEMA]:raise RuntimeError('unsupported_zha_journal_schema')
            db.execute('INSERT OR IGNORE INTO zha_journal_schema VALUES(?)',(self.SCHEMA,))
            db.execute('CREATE TABLE IF NOT EXISTS zha_observations(id TEXT PRIMARY KEY,observed_at REAL NOT NULL,device_id TEXT NOT NULL,payload TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS zha_observations_time ON zha_observations(observed_at)')
            db.execute('CREATE TABLE IF NOT EXISTS zha_capture(id INTEGER PRIMARY KEY,start REAL NOT NULL,verified_until REAL NOT NULL,ended INTEGER NOT NULL DEFAULT 0,error TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS zha_collector_status(id INTEGER PRIMARY KEY CHECK(id=1),last_attempt REAL,last_error TEXT,authenticated INTEGER,interface_available INTEGER)')
            db.execute('INSERT OR IGNORE INTO zha_collector_status(id) VALUES(1)')
            # A restart is a real gap; never extend coverage over downtime.
            db.execute("UPDATE zha_capture SET ended=1,error='collector_restarted' WHERE ended=0")
        self.capture=None

    def attempt(self):
        with self.store._connect() as db:db.execute('UPDATE zha_collector_status SET last_attempt=? WHERE id=1',(self.clock(),))

    def ready(self):
        now=self.clock()
        with self.store._connect() as db:
            self.capture=db.execute('INSERT INTO zha_capture(start,verified_until) VALUES(?,?)',(now,now)).lastrowid
            db.execute('UPDATE zha_collector_status SET last_error=NULL,authenticated=1,interface_available=1 WHERE id=1')
        self.trim()

    def heartbeat(self):
        if self.capture is None:return
        with self.store._connect() as db:
            db.execute('UPDATE zha_capture SET verified_until=? WHERE id=? AND ended=0',(self.clock(),self.capture))

    def append(self,event):
        stamp,projected=project_event(event)
        now=self.clock()
        if not now-7*86400<=stamp<=now+5:raise ValueError('event_outside_retention')
        identity=hashlib.sha256(canonical(projected).encode()).hexdigest()
        with self.store._connect() as db:
            db.execute('INSERT OR IGNORE INTO zha_observations VALUES(?,?,?,?)',
                (identity,stamp,projected['data']['device_id'],canonical(projected)))
        self.trim()

    def ended(self,error=None,*,status=None):
        with self.store._connect() as db:
            if error:
                db.execute('UPDATE zha_collector_status SET last_error=? WHERE id=1',(error,))
                if status in {401,403}:db.execute('UPDATE zha_collector_status SET authenticated=0,interface_available=1 WHERE id=1')
            if self.capture is not None:db.execute('UPDATE zha_capture SET ended=1,error=? WHERE id=?',(error,self.capture))
        self.capture=None

    def trim(self):
        with self.store._connect() as db:
            db.execute('DELETE FROM zha_observations WHERE observed_at<?',(self.clock()-7*86400,))
            db.execute('DELETE FROM zha_observations WHERE id IN (SELECT id FROM zha_observations ORDER BY observed_at DESC LIMIT -1 OFFSET 10000)')
            db.execute('DELETE FROM zha_capture WHERE verified_until<?',(self.clock()-7*86400,))
            db.execute('DELETE FROM zha_capture WHERE id IN (SELECT id FROM zha_capture ORDER BY id DESC LIMIT -1 OFFSET 1000)')

    def query(self,device_id,start,end):
        with self.store._connect() as db:
            rows=db.execute('SELECT payload FROM zha_observations WHERE device_id=? AND observed_at>=? AND observed_at<=? ORDER BY observed_at LIMIT 101',
                (device_id,start,end)).fetchall()
            intervals=[dict(r) for r in db.execute('SELECT start,verified_until,ended,error FROM zha_capture WHERE start<=? AND verified_until>=? ORDER BY start',(end,start))]
            last=db.execute('SELECT * FROM zha_capture ORDER BY id DESC LIMIT 1').fetchone()
            source=dict(db.execute('SELECT last_attempt,last_error,authenticated,interface_available FROM zha_collector_status WHERE id=1').fetchone())
        cursor=start
        for interval in intervals:
            if interval['start']>cursor:break
            cursor=max(cursor,interval['verified_until'])
        covered=cursor>=end
        return {'events':[json.loads(r[0]) for r in rows[:100]],'truncated':len(rows)>100,
            'capture_covers_window':covered,'coverage':intervals,
            'collector_state':'not_read' if last is None else 'stopped' if last['ended'] else 'listening',
            'last_verified_at':None if last is None else last['verified_until'],
            'last_error':source['last_error'] or (None if last is None else last['error']),
            'source_status':source,
            'physical_press_observed':False,
            'limitation_cs':'Záznam dokládá pouze přijaté softwarové události. Neprokazuje nezaznamenaný fyzický stisk.'}


class ZHAObserver:
    def __init__(self,journal,transport):
        self.journal,self.transport=journal,transport
        self.stop=threading.Event();self.thread=None

    def start(self):
        if not callable(getattr(self.transport,'zha_events',None)):return False
        if self.thread and self.thread.is_alive():return True
        self.stop.clear()
        def run():
            delay=2
            while not self.stop.is_set():
                try:
                    self.journal.attempt()
                    self.transport.zha_events(self.stop,self.journal.append,self.journal.ready,self.journal.heartbeat)
                    self.journal.ended()
                except Exception as error:
                    self.journal.ended(str(error) if isinstance(error,ReadFailure) else 'zha_subscription_failed',
                        status=error.status if isinstance(error,ReadFailure) else None)
                if self.stop.wait(delay):break
                delay=min(60,delay*2)
        self.thread=threading.Thread(target=run,daemon=True,name='hads-zha-observer');self.thread.start()
        return True

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=3)
        self.journal.ended()
