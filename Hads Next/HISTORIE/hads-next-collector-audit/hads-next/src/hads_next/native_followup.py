"""Report already executed native reads without AI or repair authority."""
import json
from .evidence import canonical
from .health_cases import health_domain, project_health_errors


class NativeFollowup:
    def __init__(self, app):
        self.app = app
        with app.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS native_followups(incident_id TEXT PRIMARY KEY, checked_at REAL NOT NULL, document TEXT NOT NULL)')

    def update(self, health, repairs, logs):
        with self.app.store._connect() as db:
            cases = db.execute("SELECT incident_id,key FROM health_episodes WHERE key LIKE 'health:%' OR key LIKE 'repair:%' ORDER BY active DESC,key LIMIT 128").fetchall()
        for row in cases:
            case = self.app.store.case(row['incident_id'])
            incident = case['incident']; domain = health_domain(incident)
            gaps = []; checks = []; issue_id = None
            if row['key'].startswith('health:'):
                domains = health.get('domains') if isinstance(health, dict) else None
                value = domains.get(domain) if isinstance(domains, dict) else None
                info = value.get('info') if isinstance(value, dict) else None
                errors = project_health_errors(info)
                complete = isinstance(info, dict) and health.get('complete') is True
                state = 'still_failing' if errors else 'check_passed' if complete else 'unavailable'
                checks = errors
                if not complete: gaps.append('system_health_incomplete')
                source = 'System Health'
            else:
                issue_id = row['key'].split(':', 2)[2]
                issues = repairs.get('issues') if isinstance(repairs, dict) else None
                if isinstance(issues, list) and all(isinstance(x, dict) and isinstance(x.get('domain'), str) and isinstance(x.get('issue_id'), str) for x in issues):
                    issue = next((x for x in issues if x['domain'] == domain and x['issue_id'] == issue_id), None)
                    state = 'still_failing' if issue is not None else 'check_passed'
                else:
                    state = 'unavailable'; gaps.append('repairs_unavailable')
                source = 'Repairs'
            if not isinstance(logs, list): gaps.append('system_log_unavailable')
            name = 'Marketplace' if domain == 'marketplace' else domain or 'neurčená integrace'
            summary = name + ': HADS automaticky znovu přečetl ' + source + '. '
            summary += {'still_failing': 'Požadavek nebo chyba kontroly stále trvá.',
                        'check_passed': 'Aktuální čtení již tento nález nepotvrzuje. Funkční oprava tím není ověřená.',
                        'unavailable': 'Úplný aktuální výsledek není dostupný; předchozí nález nelze zrušit.'}[state]
            if checks: summary += ' Neúspěšné kontroly: ' + ', '.join(x['field'] + ' (' + x['error'] + ')' for x in checks) + '.'
            if issue_id: summary += ' Identifikátor požadavku: ' + issue_id + '.'
            document = {'summary_cs': summary, 'state': state, 'domain': domain, 'issue_id': issue_id,
                        'checks': checks, 'gaps': gaps, 'root_cause_proven': False, 'repair_performed': False,
                        'next_test_cs': 'HADS při další pravidelné kontrole zopakuje dostupná nativní čtení a porovná protokol této integrace. Pokud příčina není doložená nebo katalog nemá bezpečnou opravu, oznámí tuto hranici. Diagnostické příkazy uživatele nevyžaduje.'}
            serialized = canonical(document)
            with self.app.store._connect() as db:
                old = db.execute('SELECT document FROM native_followups WHERE incident_id=?', (incident['id'],)).fetchone()
                db.execute('INSERT OR REPLACE INTO native_followups VALUES(?,?,?)', (incident['id'], self.app.clock(), serialized))
            if old is None or old[0] != serialized:
                self.app.store.record(incident['id'], 'native_followup', document)

    def report(self, incident_id):
        with self.app.store._connect() as db:
            row = db.execute('SELECT checked_at,document FROM native_followups WHERE incident_id=?', (incident_id,)).fetchone()
        return {**json.loads(row['document']), 'checked_at': row['checked_at']} if row else None
