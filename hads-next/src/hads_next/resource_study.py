"""A real fifteen-minute read-only study on the controller's actual host.

One bounded batch per minute, no AI or restarts. Restart/gaps break coverage;
container totals are never called host free memory. CI does not claim RPi data.
"""
import json
import threading
from .evidence import canonical
from .observability import project_supervisor_read, is_app_slug


class ResourceStudy:
    def __init__(self, app):
        self.app=app;self.stop=threading.Event();self.thread=None;self.lock=threading.Lock()
        with app.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS resource_study(at REAL PRIMARY KEY,series REAL NOT NULL,document TEXT NOT NULL)')

    def tick(self):
        if not self.lock.acquire(blocking=False):return
        try:
            now=self.app.clock()
            with self.app.store._connect() as db:
                last=db.execute('SELECT at,series FROM resource_study ORDER BY at DESC LIMIT 1').fetchone()
            if last and 0<=now-last['at']<60:return
            series=last['series'] if last and 0<now-last['at']<=90 else now
            data={'resources':self.app.system.sample_resources(),'application_sample':None,'gaps':[],
                  'scope':'actual_controller_host_not_necessarily_RPi_or_HAOS'}
            supervisor=self.app.supervisor
            if supervisor:
                for field,method in [('core','core_stats'),('supervisor','supervisor_stats')]:
                    try:data[field]=project_supervisor_read('app_stats',getattr(supervisor,method)())
                    except Exception:data['gaps'].append(field)
                apps=self.app._apps
                active=[r['slug'] for r in apps if isinstance(r,dict) and r.get('state')=='started' and is_app_slug(r.get('slug'))]
                if active:
                    slug=active[int(now//60)%len(active)]
                    try:data['application_sample']={'slug':slug,**project_supervisor_read('app_stats',supervisor.app_stats(slug))}
                    except Exception:data['gaps'].append('application_stats')
            else:data['gaps'].append('supervisor_not_connected')
            with self.app.store._connect() as db:
                db.execute('INSERT OR REPLACE INTO resource_study VALUES(?,?,?)',(now,series,canonical(data)))
                db.execute('DELETE FROM resource_study WHERE at IN (SELECT at FROM resource_study ORDER BY at DESC LIMIT -1 OFFSET 32)')
        finally:self.lock.release()

    def status(self):
        with self.app.store._connect() as db:
            rows=db.execute('SELECT * FROM resource_study ORDER BY at').fetchall()
        if not rows:return {'state':'not_measured','covered_seconds':0,'samples':0,'target_hardware_verified':False}
        current=[r for r in rows if r['series']==rows[-1]['series']]
        elapsed=current[-1]['at']-current[0]['at'];values=[json.loads(r['document']) for r in current]
        available=[r['resources']['available_bytes'] for r in values if type(r['resources'].get('available_bytes')) is int]
        stale=self.app.clock()-current[-1]['at']>90
        return {'state':'interrupted' if stale else 'measured' if elapsed>=900 and len(current)>=16 else 'collecting','covered_seconds':elapsed,
            'samples':len(current),'minimum_available_bytes':min(available) if available else None,
            'reserve_bytes':576*1024*1024,'worker_allowed_at_every_sample':bool(available) and len(available)==len(current) and min(available)>=576*1024*1024,
            'last_sample_at':current[-1]['at'],'target_hardware_verified':False,
            'scope':'actual_controller_host_not_live_RPi_acceptance','read_gaps':sorted({g for v in values for g in v['gaps']}),
            'samples_detail':[{'at':r['at'],**json.loads(r['document'])} for r in current]}

    def start(self):
        if not self.app.owner() or self.app.supervisor is None:return
        if self.thread and self.thread.is_alive():return
        def run():
            while not self.stop.is_set():
                try:self.tick()
                except Exception:pass  # Native incident collection remains independent.
                completed=self.app._source_job.get('completed_at')
                if self.app._source_job['state']!='running' and (completed is None or self.app.clock()-completed>=600):
                    self.app.request_source_check()
                self.stop.wait(60)
        self.thread=threading.Thread(target=run,daemon=True,name='hads-resource-study');self.thread.start()

    def close(self):self.stop.set()
