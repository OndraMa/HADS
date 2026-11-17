"""HAOS controller wiring: autonomous reads, confined AI and separate approved writers."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time

from .diagnostics import investigate_radio
from .evidence import IncidentStore
from .observability import redact,project_supervisor_read,is_app_slug

VERSION = "1.0.0-rc7"
ENTITY = re.compile(r"[a-z][a-z0-9_]*\.[a-z0-9_]+")


def project_state(row):
    if not isinstance(row, dict) or not ENTITY.fullmatch(str(row.get("entity_id", ""))) or not isinstance(row.get('state'),str):
        return None
    context = row.get("context")
    return {"entity_id": row["entity_id"], "state": str(row.get("state", "unknown"))[:256],
            "last_updated": str(row.get("last_updated", ""))[:80],
            "name":str((row['attributes'] if isinstance(row.get('attributes'),dict) else {}).get("friendly_name",row["entity_id"]))[:120],
            "context": {k: str(context[k])[:128] for k in ("id", "parent_id") if context.get(k)}
                if isinstance(context, dict) else {}}


class Application:
    def __init__(self, data_dir, core=None, *, core_ws=None, supervisor=None, clock=time.time, launcher=None,runtime_error=None,automation_writer=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.store = IncidentStore(self.data_dir / "incidents.sqlite")
        self.core, self.clock = core, clock
        self.core_ws, self.supervisor = core_ws, supervisor
        self.runtime_error=runtime_error
        self.automation_writer=automation_writer
        with self.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS application_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        self._lock = threading.RLock()
        self._read_lock = threading.Lock()
        self._last_attempt = None
        self._entities = []
        self._entity_catalog = []
        self._summary = {"available": False, "version": None, "entity_count": 0,
                         "unavailable_count": 0, "last_refresh_at": None,
                         "last_error": "Čtení Core ještě neproběhlo.", "source_status": None}
        self._sources = {}
        self._apps = []
        self._timezone='UTC'
        self._source_job={'state':'idle','completed_at':None,'last_error':None}
        from .investigation_service import InvestigationService
        self.investigations=InvestigationService(self,launcher)
        from .repair_service import RepairService
        from .detection import DetectionEngine
        self.repairs=RepairService(self)
        self.detection=DetectionEngine(self)
        from .system_diagnostics import SystemDiagnostics
        self.system=SystemDiagnostics(self)
        from .provider_verification import ProviderVerification
        self.providers=ProviderVerification(self)
        from .entity_context import EntityContext
        self.entity_context=EntityContext(self)
        from .legacy_connectors import LegacyConnectors
        self.legacy_connectors=LegacyConnectors(self)
        self.investigations.broker.runtime_system=self.system
        from .tool_orchestration import ToolOrchestration
        from .approved_tools import ApprovedRepairBroker
        from .orchestration_cases import OrchestrationCases
        self.tools=ToolOrchestration(self)
        self.approved_tools=ApprovedRepairBroker(self)
        from .repair_recovery import RepairRecovery
        self.repair_recovery=RepairRecovery(self)
        self.orchestration=OrchestrationCases(self)
        from .live_acceptance import LiveAcceptance
        self.acceptance=LiveAcceptance(self)

    def request_source_check(self):
        if self.core is None and self.core_ws is None and self.supervisor is None and not self.tools.connections.clients:
            return False  # no source to read; do not spawn an orphan task
        with self._lock:
            if self._source_job['state']=='running':return False
            self._source_job['state']='running'
        def run():
            try:
                self.refresh(wait_for_reader=True)
                self.check_sources()
                self.system.inspect()
                self.refresh(wait_for_reader=True)
                with self._lock:self._source_job={'state':'finished','completed_at':self.clock(),'last_error':None}
            except Exception as error:
                with self._lock:self._source_job={'state':'failed','completed_at':None,'last_error':type(error).__name__}
        threading.Thread(target=run,daemon=True,name='hads-source-check').start()
        return True

    def request_initial_diagnostics(self):
        """HAOS entrypoint only: owner already enrolled; no paid work starts."""
        if not self.owner():return
        self.request_source_check()
        if self.investigations.launcher is not None and not self.investigations.status()['worker_active']:
            self.investigations.request_probe(self.owner())

    def owner(self):
        with self.store._connect() as db:
            row = db.execute("SELECT value FROM application_settings WHERE key='owner'").fetchone()
            return row[0] if row else ''

    def enroll_owner(self, user_id):
        # Caller must verify the trusted ingress principal with HA auth/list.
        with self.store._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT value FROM application_settings WHERE key='owner'").fetchone()
            if row and row[0] != user_id:
                raise ValueError('Vlastník již byl nastaven jiným uživatelem.')
            db.execute("INSERT OR IGNORE INTO application_settings VALUES('owner',?)", (user_id,))
        self.investigations.zha_observer.start()
        self.detection.start()
        status=self.repairs.status()
        if status['enabled'] or status['native_state_targets'] or status['provider_pending_verifications']:self.repairs.start()

    def check_sources(self):
        """Execute actual supported reads, preserving per-read success/errors."""
        sources = {}; values = {}
        reads = [('core_config', self.core, 'config'),
                 ('supervisor', self.supervisor, 'info'), ('haos', self.supervisor, 'os_info'),
                 ('applications', self.supervisor, 'apps'),
                 ('entity_registry', self.core_ws, 'entity_registry'),
                 ('device_registry', self.core_ws, 'device_registry'),
                 ('repairs', self.core_ws, 'repairs'), ('system_log', self.core_ws, 'system_log'),
                 ('system_health', self.core_ws, 'system_health')]
        with self._read_lock:
            for name, reader, method in reads:
                value = getattr(reader, method)() if reader else None
                values[name] = value
                if name == 'applications' and isinstance(value,dict) and isinstance(value.get('addons'),list):
                    with self._lock:
                        self._apps = [{'slug':a['slug'],'name':str(a.get('name',a['slug']))[:120]} for a in value['addons']
                                      if isinstance(a,dict) and is_app_slug(a.get('slug'))][:200]
                valid = value is not None
                if name in {'core_config','supervisor','haos'}:
                    valid=isinstance(value,dict) and isinstance(value.get('version'),str)
                elif name=='applications':
                    valid=isinstance(value,dict) and isinstance(value.get('addons'),list)
                elif name in {'entity_registry','device_registry','system_log'}:
                    valid=isinstance(value,list) and all(isinstance(row,dict) for row in value)
                elif name=='repairs':
                    valid=isinstance(value,dict) and isinstance(value.get('issues'),list)
                elif name=='system_health':
                    valid=isinstance(value,dict) and isinstance(value.get('domains'),dict) and value.get('complete') is True
                sources[name] = {'read_succeeded': valid,
                    'status': reader.status.snapshot(self.clock()) if reader else {'last_error': 'Zdroj není připojen.'},
                    'item_count': len(value) if isinstance(value, (list, dict)) else None}
                if value is not None and not valid:
                    sources[name]['status']={**sources[name]['status'],'read_succeeded':False,'last_error':'Zdroj vrátil neočekávaný formát dat.'}
                with self._lock:self._sources[name]=sources[name]
            states = self.core.states() if self.core else None
            self.providers.update(values,states)
            self.entity_context.update(values,states)
            self.providers.record_toolkit(self.entity_context.toolkit)
            self.tools.refresh(values,states)
            self.approved_tools.identities(values.get("entity_registry"))
            logs=values.get('system_log')
            if isinstance(logs,list):
                normalized=[]
                for row in logs[:256]:
                    if not isinstance(row,dict):continue
                    message=row.get('message')
                    if isinstance(message,list):message=' '.join(x for x in message[:4] if isinstance(x,str))
                    normalized.append({'source':'system_log','observed_at':row.get('timestamp'),'component':row.get('name',row.get('logger','unknown')),'message':message})
                self.orchestration.correlate(normalized)
            self.orchestration.cycle()
            self.repair_recovery.cycle()
        with self._lock:
            self._sources = sources
        return sources

    def report_app_incident(self, symptom, slug, principal):
        if not is_app_slug(slug) or not 3 <= len(symptom) <= 1000 or not principal:
            raise ValueError('Neplatné hlášení aplikace.')
        if self.supervisor is None:
            raise ValueError('Supervisor není připojen; nelze ověřit cílovou aplikaci.')
        with self._read_lock:
            info = self.supervisor.app_info(slug)
            if not isinstance(info, dict) or info.get('slug') != slug:
                raise ValueError('Stav aplikace není ověřen. Zkontroluj oprávnění Supervisoru.')
            now = self.clock()
            incident = self.store.open_incident('application_failure', redact(symptom), [slug], now,
                correlation_key='app:' + slug + ':' + hashlib.sha256(symptom.encode()).hexdigest())
            for kind, read in [('app_info',lambda:info),('app_stats',lambda:self.supervisor.app_stats(slug)),
                               ('app_logs',lambda:self.supervisor.app_logs(slug))]:
                value=read()
                status = self.supervisor.status.snapshot(self.clock())
                if value is not None and kind in {'app_info','app_stats'}:
                    try:value=project_supervisor_read(kind,value)
                    except (ValueError,TypeError,OverflowError):
                        value=None;status={**status,'read_succeeded':False,'last_error':'Zdroj vrátil neočekávaný diagnostický formát.'}
                if value is not None:
                    if isinstance(value,str): value=value[-16000:]
                    payload = {'data': value}
                    event_id = kind + ':' + hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
                    with self.store._connect() as db:
                        previous = db.execute('SELECT observed_at FROM evidence WHERE source=? AND event_id=?',
                            ('supervisor:' + slug,event_id)).fetchone()
                    self.store.add_evidence(incident['id'], {'source': 'supervisor:' + slug, 'kind': kind,
                        'observed_at': previous[0] if previous else now, 'event_id': event_id,
                        'payload': payload})
                self.store.record(incident['id'], 'source_read', {'kind':kind,'success':value is not None,'status':status})
            self.store.record(incident['id'], 'investigation', {'summary_cs':
                'Načetl jsem dostupný stav, statistiky a protokol této aplikace. Samotná chyba ani restart ještě nedokazují příčinu.',
                'actor': principal, 'repair_performed': False})
            return self.store.case(incident['id'])

    def refresh(self,*,wait_for_reader=False):
        acquired=self._read_lock.acquire(timeout=12) if wait_for_reader else self._read_lock.acquire(blocking=False)
        if not acquired:
            return self.snapshot()
        try:
            now = self.clock()
            if self._last_attempt is not None and now - self._last_attempt < 60:
                return self.snapshot()
            self._last_attempt = now
            if self.core is None:
                with self._lock:
                    self._summary["last_error"] = "Chybí přístup k HA Core. Incidenty lze nadále uložit."
                return self.snapshot()
            config = self.core.config()
            if isinstance(config,dict):
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
                try:
                    zone=str(config.get('time_zone','UTC'));ZoneInfo(zone)
                    with self._lock:self._timezone=zone
                except (ValueError,ZoneInfoNotFoundError):pass
            states = self.core.states()
            valid = isinstance(states, list) and len(states) <= 10000
            projected = [s for row in states if (s := project_state(row))] if valid else []
            status = self.core.status.snapshot(now)
            with self._lock:
                self._entities = projected
                self._summary = {"available": valid and status["read_succeeded"],
                    "version": config.get("version") if isinstance(config, dict) else None,
                    "entity_count": len(projected),
                    "unavailable_count": sum(s["state"] == "unavailable" for s in projected),
                    "last_refresh_at": now, "source_status": status,
                    "last_error": None if valid else "Stavy Core se nepodařilo přečíst v povoleném rozsahu."}
            return self.snapshot()
        finally:
            self._read_lock.release()

    def snapshot(self):
        with self.store._connect() as db:
            rows = db.execute("SELECT i.*, (SELECT count(*) FROM occurrences o WHERE o.incident_id=i.id) AS occurrence_count "
                              "FROM incidents i ORDER BY last_seen DESC LIMIT 50").fetchall()
        cases = []
        for row in rows:
            item = dict(row)
            item["components"] = json.loads(item["components"])
            cases.append(item)
        with self._lock:
            return {"version": VERSION, "mode": "read_only_development", "core": dict(self._summary),
                    "entities": list(self._entity_catalog or self._entities), "cases": cases,
                    "hermes_enabled": bool(self.investigations.launcher and self.investigations.provider.public_status()['enabled']), "live_repairs_enabled": (self.repairs.status()["enabled"] or self.repairs.status()["native_state_targets"]>0),
                    'investigation_service':self.investigations.status(),
                    'system_health':self.system.status(),'detection':self.detection.snapshot(),'repairs':self.repairs.status(),
                    'sources': dict(self._sources),
                    'applications': list(self._apps),
                    'source_job': dict(self._source_job),
                    'timezone': self._timezone,
                    "limitations_cs": "Živé opravy nejsou aktivní. AI vyžaduje izolovaný runtime a výslovný souhlas s poskytovatelem. Nedostupnost entity sama nedokazuje příčinu závady."}

    def report_incident(self, symptom, entity_id, principal, *, occurred_at=None):
        symptom = " ".join(str(symptom).split())
        if not 3 <= len(symptom) <= 1000 or not ENTITY.fullmatch(str(entity_id)) or not principal:
            raise ValueError("Vyplň popis problému a platné entity_id, například media_player.radio.")
        now = self.clock()
        incident_at = now if occurred_at is None else float(occurred_at)
        import math
        if not math.isfinite(incident_at) or not now-30*86400 <= incident_at <= now:
            raise ValueError('Čas incidentu musí být v posledních třiceti dnech.')
        with self.store._connect() as db:
            total = db.execute("SELECT count(*) FROM incidents").fetchone()[0]
            occurrences = db.execute("SELECT count(*) FROM occurrences").fetchone()[0]
        if total >= 200 or occurrences >= 2000:
            raise ValueError("Vývojové úložiště dosáhlo limitu. Nejprve exportuj spisy a připrav řízenou archivaci.")
        key = "manual:" + hashlib.sha256((entity_id + "\n" + symptom).encode()).hexdigest()
        incident = self.store.open_incident("manual_functional", redact(symptom), [entity_id], incident_at, correlation_key=key)
        incident_id = incident["id"]
        self.store.record(incident_id, "user_report", {"symptom": redact(symptom), "entity_id": entity_id,
            "principal": principal, "observed_at": incident_at, "reported_at": now, "scope": "haos_read_only_preview"})
        evidence = []
        with self._read_lock:
            history = None
            if self.core is not None:
                iso = lambda stamp: datetime.fromtimestamp(stamp, timezone.utc).isoformat()
                history = self.core.history(iso(incident_at - 600), entity_id, iso(min(now,incident_at+120)))
            if isinstance(history, list):
                rows = [row for group in history if isinstance(group, list) for row in group]
                # Recorder REST history may omit context. A current state is
                # usable only for the exact same source timestamp and value;
                # never attach a later action's context to an earlier event.
                current=project_state(self.core.states(entity_id)) if self.core else None
                if len(rows) > 1000:
                    rows = []
                previous = None
                for raw in rows:
                    state = project_state(raw)
                    if state is None or state["entity_id"] != entity_id:
                        continue
                    try:
                        dt = datetime.fromisoformat(state["last_updated"])
                        if dt.tzinfo is None:
                            continue
                        observed = dt.timestamp()
                    except ValueError:
                        continue
                    if not incident_at - 600 <= observed <= min(now,incident_at+120):
                        continue
                    source_identity=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()
                    if current and not state['context'] and current['entity_id']==state['entity_id'] and current['state']==state['state'] and current['last_updated']==state['last_updated']:
                        state={**state,'context':current['context'],'context_source':'core_current_state_exact_timestamp_match'}
                    payload = {**state, "from": previous["state"] if previous else None, "to": state["state"]}
                    event = {"source": "ha_core_history", "kind": "player_state" if entity_id.startswith("media_player.") else "entity_state",
                             "observed_at": observed, "payload": payload,
                             "event_id": source_identity}
                    # Persist the source state, whose identity does not change
                    # when a later history window begins with a different row.
                    self.store.add_evidence(incident_id, {**event, "kind": "entity_state", "payload": state})
                    evidence.append(event)
                    previous = state
            if self.core_ws is not None:
                iso = lambda stamp: datetime.fromtimestamp(stamp, timezone.utc).isoformat()
                actions = self.core_ws.action_history(iso(incident_at-600),iso(min(now,incident_at+120)))
                self.store.record(incident_id,'source_read',{'kind':'action_history','success':actions is not None,
                    'status':self.core_ws.status.snapshot(now)})
                if isinstance(actions,list):
                    for action in actions[:1000]:
                        if entity_id not in action.get('targets',{}).get('entity_id',[]): continue
                        stamp=action.get('when')
                        if not isinstance(stamp,(int,float)) or not incident_at-600 <= stamp <= min(now,incident_at+120):continue
                        event={'source':'ha_core_action_history','kind':'ha_action','observed_at':stamp,
                            'event_id':hashlib.sha256(json.dumps(action,sort_keys=True).encode()).hexdigest(),
                            'payload':{'action':str(action.get('domain',''))+'.'+str(action.get('service','')),
                                'target_entity_id':entity_id,'context':{'id':action.get('context_id')},
                                'origin_user_id':action.get('context_user_id')}}
                        self.store.add_evidence(incident_id,event)
                        evidence.append(event)
            read_status = self.core.status.snapshot(now) if self.core is not None else {"read_succeeded": False, "last_error": "Core není připojen."}
        conclusion = investigate_radio(evidence, entity_id, incident_at, window=600) if entity_id.startswith("media_player.") else {
            "category": "insufficient_evidence", "summary_cs": "Incident je uložený. Historie stavu sama příčinu nedokazuje.",
            "needed": ["Doplnit související události a funkční test."]}
        self.store.record(incident_id, "deterministic_investigation", {**conclusion,
            "source_status": read_status, "scope": "haos_read_only_preview",
            "limitation": "Toto je deterministický rozbor historie HA. Další čtení může vyžádat samostatné vyšetřování Hermes; Music Assistant vyžaduje nastavené připojení. Žádná oprava nebyla provedena."})
        if self.owner():self.request_source_check()
        return self.store.case(incident_id)
