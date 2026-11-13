"""Durable investigation queue, read checkpoints and metered model intents."""
import hashlib
import json
import time
import uuid

from .evidence import canonical


class JobBlocked(ValueError):pass


class InvestigationJobs:
    STATES={'new','collecting_evidence','investigating','waiting_for_source','waiting_for_user',
        'hypothesis_ready','repair_plan_ready','awaiting_approval','verifying','resolved','reopened','blocked','failed'}
    TRANSITIONS={
        'new':{'collecting_evidence','waiting_for_user','blocked'},
        'collecting_evidence':{'investigating','reopened','blocked','failed'},
        'investigating':{'waiting_for_source','waiting_for_user','hypothesis_ready','reopened','blocked','failed'},
        'waiting_for_source':{'reopened','blocked'},'waiting_for_user':{'reopened','blocked'},
        'hypothesis_ready':{'reopened','waiting_for_user','blocked'},'reopened':{'collecting_evidence','waiting_for_user','blocked'},
        'blocked':{'reopened'},'failed':{'reopened','blocked'}}

    def __init__(self,store,*,clock=time.time):
        self.store,self.clock=store,clock
        self.after_read=None  # trusted fault injection; never exposed to model/UI
        with store._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS investigation_schema(version INTEGER NOT NULL);
                INSERT INTO investigation_schema SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM investigation_schema);
                CREATE TABLE IF NOT EXISTS investigation_jobs(
                    id TEXT PRIMARY KEY,incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
                    deadline REAL,conclusion TEXT,UNIQUE(incident_id,fingerprint));
                CREATE TABLE IF NOT EXISTS investigation_steps(
                    id INTEGER PRIMARY KEY,job_id TEXT NOT NULL REFERENCES investigation_jobs(id) ON DELETE CASCADE,
                    at REAL NOT NULL,state TEXT NOT NULL,reason TEXT NOT NULL,evidence_ids TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS investigation_reads(
                    job_id TEXT NOT NULL REFERENCES investigation_jobs(id) ON DELETE CASCADE,request_hash TEXT NOT NULL,
                    name TEXT NOT NULL,arguments TEXT NOT NULL,result TEXT NOT NULL,at REAL NOT NULL,
                    PRIMARY KEY(job_id,request_hash));
                CREATE TABLE IF NOT EXISTS investigation_model_calls(
                    id TEXT PRIMARY KEY,job_id TEXT NOT NULL REFERENCES investigation_jobs(id) ON DELETE CASCADE,at REAL NOT NULL,
                    state TEXT NOT NULL,request_hash TEXT NOT NULL,response TEXT);
                CREATE TABLE IF NOT EXISTS investigation_daily_usage(day INTEGER PRIMARY KEY,count INTEGER NOT NULL);
            ''')
            if db.execute('SELECT version FROM investigation_schema').fetchone()[0]!=1:
                raise JobBlocked('Neznámé schéma vyšetřování.')

    def enqueue(self,incident_id):
        case=self.store.case(incident_id)
        fingerprint=hashlib.sha256(canonical([case['incident']['last_seen'],[x['evidence_id'] for x in case['evidence']]]).encode()).hexdigest()
        with self.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute("SELECT id FROM investigation_jobs WHERE incident_id=? AND state IN ('new','collecting_evidence','investigating','reopened') ORDER BY created_at LIMIT 1",(incident_id,)).fetchone()
            if active:return active[0]
            row=db.execute('SELECT id FROM investigation_jobs WHERE incident_id=? AND fingerprint=?',(incident_id,fingerprint)).fetchone()
            if row:return row[0]
            identity=uuid.uuid4().hex;now=self.clock()
            db.execute('INSERT INTO investigation_jobs(id,incident_id,fingerprint,state,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                (identity,incident_id,fingerprint,'new',now,now))
            db.execute('INSERT INTO investigation_steps(job_id,at,state,reason,evidence_ids) VALUES(?,?,?,?,?)',
                (identity,now,'new','Vyšetřování bylo zařazeno do fronty.','[]'))
            return identity

    def get(self,identity):
        with self.store._connect() as db:
            row=db.execute('SELECT * FROM investigation_jobs WHERE id=?',(identity,)).fetchone()
            if row is None:raise JobBlocked('Vyšetřování nebylo nalezeno.')
            result=dict(row)
            result['conclusion']=json.loads(result['conclusion']) if result['conclusion'] else None
            result['steps']=[dict(x) for x in db.execute('SELECT at,state,reason,evidence_ids FROM investigation_steps WHERE job_id=? ORDER BY id',(identity,))]
            result['reads']=[{'name':x['name'],'arguments':json.loads(x['arguments']),'result':json.loads(x['result'])} for x in db.execute('SELECT * FROM investigation_reads WHERE job_id=? ORDER BY at,rowid',(identity,))]
            result['model_calls']=db.execute('SELECT count(*) FROM investigation_model_calls WHERE job_id=?',(identity,)).fetchone()[0]
            return result

    def transition(self,identity,state,reason,evidence_ids=(),*,conclusion=None):
        if state not in self.STATES or not reason:raise JobBlocked('Neplatná změna stavu.')
        # Analysis cannot assert functional success, approval or execution.
        if state in {'resolved','awaiting_approval','verifying','repair_plan_ready'}:
            raise JobBlocked('Tento stav vyžaduje nezávislý opravný nebo ověřovací modul.')
        fingerprint=None
        if state in {'hypothesis_ready','waiting_for_source','waiting_for_user','blocked','failed'}:
            case=self.store.case(self.get(identity)['incident_id'])
            fingerprint=hashlib.sha256(canonical([case['incident']['last_seen'],[x['evidence_id'] for x in case['evidence']]]).encode()).hexdigest()
        with self.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT state FROM investigation_jobs WHERE id=?',(identity,)).fetchone()
            if old is None or state not in self.TRANSITIONS.get(old[0],set()):
                raise JobBlocked('Nepovolený přechod vyšetřování.')
            if not db.execute('UPDATE investigation_jobs SET state=?,updated_at=?,conclusion=coalesce(?,conclusion) WHERE id=?',
                (state,self.clock(),canonical(conclusion) if conclusion else None,identity)).rowcount:raise JobBlocked('Neznámé vyšetřování.')
            if fingerprint:db.execute('UPDATE investigation_jobs SET fingerprint=? WHERE id=?',(fingerprint,identity))
            db.execute('INSERT INTO investigation_steps(job_id,at,state,reason,evidence_ids) VALUES(?,?,?,?,?)',
                (identity,self.clock(),state,reason,canonical(list(evidence_ids))))

    def claim(self,identity):
        with self.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute("UPDATE investigation_jobs SET state='collecting_evidence',attempts=attempts+1,deadline=?,updated_at=? WHERE id=? AND state IN ('new','reopened') AND attempts<2",
                (self.clock()+180,self.clock(),identity)).rowcount
            if not changed:raise JobBlocked('Vyšetřování již běží, čeká na rozhodnutí nebo dosáhlo limitu obnovení.')
            db.execute('INSERT INTO investigation_steps(job_id,at,state,reason,evidence_ids) VALUES(?,?,?,?,?)',
                (identity,self.clock(),'collecting_evidence','Případ získal jediný vyšetřovací slot.','[]'))
        self.transition(identity,'investigating','Hermes zahájil omezené čtecí vyšetřování.')

    def recover(self):
        with self.store._connect() as db:
            rows=[row[0] for row in db.execute("SELECT id FROM investigation_jobs WHERE state IN ('investigating','collecting_evidence')")]
        for identity in rows:
            with self.store._connect() as db:
                pending=db.execute("SELECT 1 FROM investigation_model_calls WHERE job_id=? AND state='intent'",(identity,)).fetchone()
            state='blocked' if pending else 'reopened'
            self.transition(identity,state,'Běh byl přerušen. '+('Výsledek modelového volání není znám; automatické opakování je zablokované.' if pending else 'Důkazy jsou zachované; lze pokračovat se zbývajícím rozpočtem.'))

    def read(self,identity,broker,name,args):
        job=self.get(identity)
        if job['state']!='investigating' or self.clock()>job['deadline']:raise JobBlocked('Čtecí vyšetřování není aktivní.')
        authorize=getattr(broker,'authorize',None)
        if authorize:authorize(job['incident_id'],name,args)
        key=hashlib.sha256(canonical([name,args]).encode()).hexdigest()
        with self.store._connect() as db:
            row=db.execute('SELECT result FROM investigation_reads WHERE job_id=? AND request_hash=?',(identity,key)).fetchone()
            if not row and db.execute('SELECT count(*) FROM investigation_reads WHERE job_id=?',(identity,)).fetchone()[0]>=12:raise JobBlocked('Vyčerpán rozpočet diagnostických čtení.')
        if row:
            result={**json.loads(row[0]),'cached':True}
            replay=getattr(broker,'on_cached_read',None)
            if replay:replay(name,result)
            return result
        result=broker.read(job['incident_id'],name,args)
        with self.store._connect() as db:
            db.execute('INSERT OR IGNORE INTO investigation_reads VALUES(?,?,?,?,?,?)',
                (identity,key,name,canonical(args),canonical(result),self.clock()))
        if self.after_read:self.after_read(name,result)
        return result

    def model_intent(self,identity,body,*,daily_limit=12,case_limit=8):
        with self.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job=db.execute('SELECT state,deadline FROM investigation_jobs WHERE id=?',(identity,)).fetchone()
            if job is None or job[0]!='investigating' or self.clock()>job[1]:raise JobBlocked('Vyšetřování není aktivní.')
            if db.execute("SELECT 1 FROM investigation_model_calls WHERE job_id=? AND state='intent'",(identity,)).fetchone():
                raise JobBlocked('Předchozí volání má neznámý výsledek; automatický retry je zakázaný.')
            if db.execute('SELECT count(*) FROM investigation_model_calls WHERE job_id=?',(identity,)).fetchone()[0]>=case_limit:
                raise JobBlocked('Vyčerpán rozpočet modelu pro případ.')
            day=int(self.clock()//86400)*86400
            usage=db.execute('SELECT count FROM investigation_daily_usage WHERE day=?',(day,)).fetchone()
            if usage and usage[0]>=daily_limit:
                raise JobBlocked('Vyčerpán denní rozpočet AI.')
            db.execute('INSERT INTO investigation_daily_usage VALUES(?,1) ON CONFLICT(day) DO UPDATE SET count=count+1',(day,))
            identity_call=uuid.uuid4().hex
            db.execute('INSERT INTO investigation_model_calls VALUES(?,?,?,?,?,NULL)',
                (identity_call,identity,self.clock(),'intent',hashlib.sha256(canonical(body).encode()).hexdigest()))
            return identity_call

    def model_result(self,call_id,response):
        with self.store._connect() as db:
            db.execute("UPDATE investigation_model_calls SET state='response',response=? WHERE id=? AND state='intent'",(canonical(response),call_id))
