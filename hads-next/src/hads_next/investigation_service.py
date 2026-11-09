"""One bounded worker at a time. Controller owns all credentials and state."""
import threading

from .ai_provider import AIProvider,ProviderDisabled
from .evidence_broker import EvidenceBroker
from .hermes_runtime import run_investigation
from .investigation_jobs import InvestigationJobs,JobBlocked
from .zha_observer import ZHAJournal,ZHAObserver
from .music_configuration import MusicConfiguration


class InvestigationService:
    def __init__(self,app,launcher=None):
        self.app,self.launcher=app,launcher
        self.provider=AIProvider(app.data_dir)
        self.jobs=InvestigationJobs(app.store)
        self.jobs.recover()
        self.zha=ZHAJournal(app.store,app.clock)
        self.zha_observer=ZHAObserver(self.zha,getattr(app.core_ws,'transport',None))
        self.music=MusicConfiguration(app.data_dir)
        self.broker=EvidenceBroker(app.store,core=app.core,core_ws=app.core_ws,supervisor=app.supervisor,zha=self.zha,music=self.music.reader(),clock=app.clock)
        self.broker._lock=app._read_lock
        self._slot=threading.Lock()
        self._schedule_lock=threading.RLock()
        self._active_job=None

    def status(self):
        return {'provider':self.provider.public_status(),'runtime_installed':self.launcher is not None,
            'worker_active':self._slot.locked(),'execution_authority':'none',
            'real_model_acceptance':'pending','haos_acceptance':'pending'}

    def start(self,incident_id,principal,*,ack_unknown=False):
        if not principal or principal!=self.app.owner():raise JobBlocked('Vyšetřování může spustit pouze ověřený vlastník.')
        identity=self.jobs.enqueue(incident_id)
        job=self.jobs.get(identity)
        if job['state'] in {'waiting_for_user','waiting_for_source'}:
            self.jobs.transition(identity,'reopened','Ověřený vlastník požádal o pokračování.')
        elif job['state']=='blocked' and job['attempts']<2:
            if self._slot.locked():return identity
            with self.app.store._connect() as db:
                pending=db.execute("SELECT 1 FROM investigation_model_calls WHERE job_id=? AND state='intent'",(identity,)).fetchone()
                if pending and not ack_unknown:raise JobBlocked('Výsledek předchozího volání není znám. Další pokus potřebuje výslovné potvrzení možného účtování.')
                if pending:
                    db.execute("UPDATE investigation_model_calls SET state='abandoned_unknown' WHERE job_id=? AND state='intent'",(identity,))
            self.jobs.transition(identity,'reopened','Ověřený vlastník povolil pokračování; dřívější případné účtování zůstává započítané.')
            self.app.store.record(incident_id,'investigation_resume_decision',{'job_id':identity,'principal':principal,'ack_unknown':bool(ack_unknown)})
        elif job['state'] not in {'new','reopened'}:
            return identity
        if self.launcher is None:
            self.jobs.transition(identity,'waiting_for_user','Izolovaný Hermes runtime není v tomto image dostupný. Sběr důkazů pokračuje bez AI.')
            return identity
        try:model,sender=self.provider.sender()
        except ProviderDisabled:
            self.jobs.transition(identity,'waiting_for_user','AI je vypnutá. Nejdříve nastav poskytovatele a potvrď souhlas s voláním a předáním redigovaných důkazů.')
            return identity
        self._kick()
        return identity

    def _kick(self):
        with self._schedule_lock:
            if not self._slot.acquire(blocking=False):return
        def run():
            try:
                while True:
                    with self.app.store._connect() as db:
                        row=db.execute("SELECT id FROM investigation_jobs WHERE state IN ('new','reopened') ORDER BY created_at LIMIT 1").fetchone()
                    if row is None:break
                    current=self.jobs.get(row[0])
                    if current['attempts']>=2:
                        self.jobs.transition(row[0],'blocked','Byl dosažen limit obnovování; další vyšetření potřebuje nové důkazy.');continue
                    try:
                        current_model,current_sender=self.provider.sender()
                        self._active_job=row[0]
                        run_investigation(self.jobs,row[0],self.broker,self.launcher,current_sender,model=current_model)
                    except ProviderDisabled:
                        self.jobs.transition(row[0],'waiting_for_user','AI je vypnutá. Důkazy zůstávají uložené.')
                    except Exception:
                        failed=self.jobs.get(row[0])
                        if failed['state'] in {'new','reopened'}:
                            self.jobs.transition(row[0],'blocked','Vyšetřování nelze zahájit; další automatické pokusy jsou zastavené.')
                    finally:self._active_job=None
            finally:
                with self._schedule_lock:
                    self._slot.release()
                    with self.app.store._connect() as db:
                        pending=db.execute("SELECT 1 FROM investigation_jobs WHERE state IN ('new','reopened') LIMIT 1").fetchone()
                    if pending:self._kick()
        threading.Thread(target=run,daemon=True,name='hads-hermes-investigation').start()

    def for_case(self,incident_id):
        with self.app.store._connect() as db:
            rows=db.execute('SELECT id FROM investigation_jobs WHERE incident_id=? ORDER BY created_at DESC LIMIT 5',(incident_id,)).fetchall()
        return [self.jobs.get(row[0]) for row in rows]

    def cancel(self,job_id,principal):
        if principal!=self.app.owner() or self._active_job!=job_id:
            raise JobBlocked('Tento aktivní případ nelze zastavit.')
        self.jobs.transition(job_id,'blocked','Vlastník zastavil vyšetřování. Probíhající požadavek může u poskytovatele doběhnout; další se již nespustí.')
        return self.launcher.cancel()
