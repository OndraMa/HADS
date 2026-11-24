"""One bounded worker at a time. Controller owns all credentials and state."""
import threading

from .ai_provider import AIProvider,ProviderDisabled
from .evidence_broker import EvidenceBroker
from .hermes_runtime import run_investigation
from .runtime_check import probe_runtime,verified_probe
from .investigation_jobs import InvestigationJobs,JobBlocked
from .zha_observer import ZHAJournal,ZHAObserver
from .music_configuration import MusicConfiguration
from .research import ResearchReader


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
        self.research=ResearchReader(self.broker);self.research.install()
        self._slot=threading.Lock()
        self._schedule_lock=threading.RLock()
        self._active_job=None
        self._probe={'state':'not_read','summary_cs':'Kontrola izolovaného Hermesu zatím neproběhla. Model se při ní nevolá.','checked_at':None}

    def status(self):
        return {'provider':self.provider.public_status(),'runtime_installed':self.launcher is not None,
            'public_research_enabled':self.research.enabled(),
            'runtime_probe':dict(self._probe),'runtime_start_error':getattr(self.app,'runtime_error',None),
            'worker_active':self._slot.locked(),'execution_authority':'none',
            'real_model_acceptance':'pending','haos_acceptance':'pending'}

    def request_probe(self,principal):
        if not principal or principal!=self.app.owner():raise JobBlocked('Kontrolu runtime může spustit pouze ověřený vlastník.')
        if self.launcher is None:
            self._probe={'state':'unavailable','summary_cs':'Izolovaný launcher není dostupný. Diagnostická čtení mohou pokračovat bez AI.','checked_at':self.app.clock()}
            return False
        with self._schedule_lock:
            if not self._slot.acquire(blocking=False):raise JobBlocked('Právě probíhá vyšetřování nebo kontrola. Vyčkej na jeho dokončení.')
            self._probe={'state':'running','summary_cs':'Načítám původní Hermes a ověřuji jeho izolaci. Žádný modelový požadavek se neposílá.','checked_at':None}
        def run():
            try:
                # No job/credentials/provider is attached. Unexpected model or
                # source requests fail before any external operation can run.
                result=probe_runtime(self.launcher,self.broker.schemas())
                valid=verified_probe(result)
                summary='Původní Hermes se načetl a izolace prošla. Nebyl volán model; skutečný výsledek vyšetřování tím ještě není ověřen.' if valid else \
                    'Pro Hermes není dostatečná paměťová rezerva. Sběr dat pokračuje bez AI.' if result.get('error')=='insufficient_memory_reserve' else \
                    'Izolaci Hermesu se nepodařilo potvrdit. AI se nespustí bez úspěšné kontroly před voláním modelu.'
                outcome={'state':'ready' if valid else 'failed','summary_cs':summary,'checked_at':self.app.clock(),'receipt':result}
            except Exception as error:
                outcome={'state':'failed','summary_cs':'Izolovaný Hermes není připraven. Diagnostika bez AI zůstává dostupná.',
                    'checked_at':self.app.clock(),'error_type':type(error).__name__}
            finally:
                # A readiness check must not start any queued model work.
                with self._schedule_lock:
                    self._slot.release();self._probe=outcome
        threading.Thread(target=run,daemon=True,name='hads-hermes-readiness').start()
        return True

    def start(self,incident_id,principal,*,ack_unknown=False,automatic=False):
        with self._schedule_lock:
            if not principal or principal!=self.app.owner():raise JobBlocked('Vyšetřování může spustit pouze ověřený vlastník.')
            trial=self.provider.public_status().get('mode')=='trial'
            if automatic and trial:return None
            if trial and self._slot.locked():raise JobBlocked('Právě probíhá jiný test. Testovací rozpočet nepovoluje automatickou frontu modelových volání.')
            if self._probe['state']=='running':raise JobBlocked('Právě se ověřuje Hermes bez volání modelu. Po dokončení spusť vyšetřování znovu.')
            return self._start(incident_id,principal,ack_unknown=ack_unknown)

    def _start(self,incident_id,principal,*,ack_unknown=False):
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
        self._kick(only_job=identity if self.provider.public_status().get('mode')=='trial' else None)
        return identity

    def _kick(self,only_job=None):
        trial=self.provider.public_status().get('mode')=='trial'
        if trial and only_job is None:return
        with self._schedule_lock:
            if not self._slot.acquire(blocking=False):return
        def run():
            try:
                while True:
                    with self.app.store._connect() as db:
                        row=db.execute("SELECT id FROM investigation_jobs WHERE state IN ('new','reopened') AND (? IS NULL OR id=?) ORDER BY created_at LIMIT 1",(only_job,only_job)).fetchone()
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
                    if trial:break
            finally:
                with self._schedule_lock:
                    self._slot.release()
                    with self.app.store._connect() as db:
                        pending=db.execute("SELECT 1 FROM investigation_jobs WHERE state IN ('new','reopened') LIMIT 1").fetchone()
                    if pending and not trial:self._kick()
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
