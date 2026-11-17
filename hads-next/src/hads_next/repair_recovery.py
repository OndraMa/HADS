"""Read-only recovery of uncertain approved tool writes; no automatic replay."""
from contextlib import closing
import json
from .repair import connect,RepairBlocked
from .evidence import canonical

class RepairRecovery:
    def __init__(self,app):
        self.app=app
        with app.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS tool_recovery_reads(plan_id TEXT PRIMARY KEY,attempts INTEGER NOT NULL,checked_at REAL NOT NULL,result TEXT NOT NULL)')

    def cycle(self):
        with closing(connect(self.app.store.db_path)) as db:
            rows=db.execute("SELECT p.id,p.document FROM repair_plans p JOIN repair_executions e ON e.plan_id=p.id WHERE json_extract(p.document,'$.operation')='tool.approved' AND e.status='unknown_requires_reconciliation' ORDER BY e.started_at LIMIT 2").fetchall()
        for row in rows:
            with self.app.store._connect() as db:old=db.execute('SELECT * FROM tool_recovery_reads WHERE plan_id=?',(row['id'],)).fetchone()
            if old and (old['attempts']>=2 or self.app.clock()-old['checked_at']<300):continue
            d=json.loads(row['document'])
            provider=next((p for p in self.app.tools.registry.providers() if p['id']==d['binding']['provider']),{})
            if provider.get('connected') is not True:continue  # source collection retries connection independently
            try:result=self.app.approved_tools.reconcile(row['id'])
            except (ValueError,KeyError,TypeError):result={'read_verified':False,'retry_authorized':False,'detail_cs':'Kontrolní čtení nebylo ověřené. Další zápis je zastavený.'}
            with self.app.store._connect() as db:db.execute('INSERT OR REPLACE INTO tool_recovery_reads VALUES(?,?,?,?)',(row['id'],1 if old is None else old['attempts']+1,self.app.clock(),canonical(result)))

    def status(self,identity):
        with self.app.store._connect() as db:row=db.execute('SELECT * FROM tool_recovery_reads WHERE plan_id=?',(identity,)).fetchone()
        return {**json.loads(row['result']),'checked_at':row['checked_at']} if row else None

    def adopt(self,identity,principal):
        """Fresh owner decision accepts a freshly observed state, never a write."""
        broker=self.app.approved_tools;broker._owner(principal)
        with self.app._read_lock:
            plan=broker.plan(identity);result=broker.reconcile(identity)
            if not result['matches_proposed'] or not result['target_identity_matches']:
                raise RepairBlocked('Aktuální stav nebo fyzický cíl neodpovídá plánu. Nelze zahájit ověření tohoto výsledku.')
            with closing(connect(self.app.store.db_path)) as db:
                changed=db.execute("UPDATE repair_executions SET status='applied_verification_pending',completed_at=?,error='write_origin_uncertain_owner_adopted_observed_state' WHERE plan_id=? AND status='unknown_requires_reconciliation'",(self.app.clock(),identity)).rowcount
                if changed!=1:raise RepairBlocked('Tento zásah nečeká na rozhodnutí o nejistém výsledku.')
            self.app.store.record(plan.document['incident_id'],'owner_adopted_observed_state',{'plan_id':identity,'principal':principal,'no_write_performed':True,'new_functional_test_required':True,'write_origin_uncertain':True})
            self.app.repairs.start()
