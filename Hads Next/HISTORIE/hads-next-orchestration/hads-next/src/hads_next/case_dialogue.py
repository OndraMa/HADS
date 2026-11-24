"""Durable owner dialogue; statements are evidence, never repair authorization."""
from html import escape
import re
import uuid
from .observability import redact


class CaseDialogue:
    def __init__(self, app):
        self.app = app

    def add(self, incident, text, principal):
        if not principal or principal != self.app.owner():
            raise ValueError('Konverzaci smí doplnit pouze vlastník.')
        case=self.app.store.case(incident)
        if case['incident']['status']!='open':
            raise ValueError('Pro nové vyšetřování nejprve znovu otevři případ.')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise ValueError('Doplň zprávu dlouhou nejvýše 2000 znaků.')
        with self.app.store._connect() as db:
            count = db.execute("SELECT count(*) FROM case_records WHERE incident_id=? AND kind='owner_message'", (incident,)).fetchone()[0]
        if count >= 100:
            raise ValueError('Konverzace dosáhla limitu 100 zpráv; historie zůstává uložená.')
        # Private webhook paths and pasted URLs must not enter the model context.
        text = re.sub(r'https?://[^\s<>]+', '[soukromá adresa vynechána]', redact(text.strip()))
        event = uuid.uuid4().hex
        self.app.store.add_evidence(incident, {'source': 'authenticated_owner', 'kind': 'owner_statement',
            'event_id': event, 'observed_at': self.app.clock(),
            'payload': {'text': text, 'authority': 'owner_statement_not_approval_or_independent_confirmation'}})
        self.app.store.record(incident, 'owner_message', {'message_id': event, 'text': text,
            'authority': 'owner_statement_not_approval'})
        self.app.request_source_check()
        return event

    def attention(self, incident, decision, principal):
        if not principal or principal != self.app.owner():raise ValueError('Rozhoduje pouze vlastník.')
        self.app.store.case(incident)
        if decision not in {'ignore','recheck'}:raise ValueError('Neznámé rozhodnutí.')
        if any(p['status'] in {'tool_intent','applied_verification_pending','unknown_requires_reconciliation','blocked_requires_review'} for p in self.app.repairs.plans(incident)):
            raise ValueError('Nejprve dokonči nebo vyjasni rozpracovaný zásah. Jeho stav nelze skrýt ignorováním.')
        self.app.store.record(incident,'case_attention_decision',{'decision':decision,'authority':'authenticated_owner_not_repair_approval'})
        if decision=='ignore':self.app.store.archive(incident,at=self.app.clock())
        else:
            with self.app.store._connect() as db:db.execute("UPDATE incidents SET status='open',archived_at=NULL WHERE id=?",(incident,))
            self.app.request_source_check()  # Read-only; never starts the model.


def render(case, csrf):
    rows = []
    for record in case['records']:
        if record['kind'] == 'owner_message':
            rows.append('<p><strong>Ty:</strong> ' + escape(record['content']['text']) + '</p>')
        elif record['kind'] in {'deterministic_investigation','owner_diagnostic_reply'} and record['content'].get('summary_cs'):
            rows.append('<p><strong>HADS:</strong> ' + escape(record['content']['summary_cs']) + '</p>')
    return ('<section><h2>Konverzace tohoto případu</h2>' + ''.join(rows[-40:])
        + '<form method="post" action="../case/message"><input type="hidden" name="csrf" value="'
        + escape(csrf, quote=True) + '"><input type="hidden" name="incident_id" value="'
        + escape(case['incident']['id'], quote=True) + '"><label>Doplnění nebo otázka<textarea name="message" maxlength="2000" required></textarea></label>'
        + '<p>HADS zopakuje dostupná čtení a odpoví ve spisu. Modelové vyšetřování má samostatné spuštění a rozpočet.</p><button>Poslat a prověřit bez AI</button></form>'
        + '<form method="post" action="../case/attention"><input type="hidden" name="csrf" value="'+escape(csrf,quote=True)+'"><input type="hidden" name="incident_id" value="'+escape(case['incident']['id'],quote=True)+'"><button name="decision" value="recheck">Znovu vyšetřit dostupnými čteními bez AI</button><button name="decision" value="ignore">Ignorovat v přehledu a zachovat historii</button></form><p>Ignorování není ověřená oprava a nemění zařízení ani diagnostické nástroje.</p></section>')
