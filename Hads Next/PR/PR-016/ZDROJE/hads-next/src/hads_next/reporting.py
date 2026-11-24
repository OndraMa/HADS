"""Escaped, dependency-free Czech case overview; no HTTP or approval endpoint."""
from __future__ import annotations

from html import escape
import hashlib
import json
from pathlib import Path

from .observability import redact


def _text(value):
    return escape(str(value), quote=True)


def _detail(value):
    return '<details><summary>Technický detail</summary><pre>' + _text(
        json.dumps(redact(value), ensure_ascii=False, indent=2, sort_keys=True)
    ) + '</pre></details>'


def _card(title, description, value):
    return '<article><h3>' + _text(title) + '</h3><p>' + _text(description) + '</p>' + _detail(value) + '</article>'


def render_command_center(cases: list[dict], plans: list[dict] | None = None,
                          reports: list[dict] | None = None) -> str:
    """Render exported cases only; this function grants no authority.

    Inputs are IncidentStore.case() exports and plan/report documents. The HTML
    contains no active repair controls; the operator reviews the immutable plan
    with the local CLI. HAOS identity and ingress remain a separate live gate.
    """
    plans, reports = plans or [], reports or []
    if len(cases) + len(plans) + len(reports) > 1000:
        raise ValueError("Přehled překračuje limit 1000 položek; zvol užší export.")
    buckets = {title: [] for title in (
        'Co nefunguje', 'Co HADS vyšetřuje', 'Co ode mě potřebuje',
        'Co se podařilo vyřešit', 'Co se opakuje')}
    latest = {}
    for report in reports:
        incident_id = report.get('incident_id')
        if incident_id is not None and report.get('created_at', 0) >= latest.get(incident_id, {}).get('created_at', 0):
            latest[incident_id] = report
    for case in cases:
        incident = case.get('incident', case)
        incident_id = incident.get('id', '')
        report = latest.get(incident_id)
        symptom = incident.get('symptom') or 'Nahlášený funkční problém'
        verified = report and report.get('classification') == 'Vyřešeno a ověřeno'
        if not verified and incident.get('status') != 'archived':
            buckets['Co nefunguje'].append(_card(symptom,
                'Případ zůstává otevřený, dokud není doložen skutečný funkční výsledek.', case))
        analyses = case.get('analyses', [])
        if any(item.get('status') == 'running' for item in analyses):
            buckets['Co HADS vyšetřuje'].append(_card(symptom,
                'HADS porovnává dostupné důkazy. Další analýza potřebuje nová data; domácnost tímto exportem není ovládána.', case))
        elif analyses and analyses[-1].get('status') == 'failed':
            buckets['Co HADS vyšetřuje'].append(_card(symptom,
                'AI vyšetření se nedokončilo. Případ i důkazy jsou uložené a místní diagnostika může pokračovat.', case))
        occurrences = case.get('occurrences', [])
        if len(occurrences) > 1 or (report and report.get('classification') == 'Problém se opakoval'):
            buckets['Co se opakuje'].append(_card(symptom,
                f'Počet zaznamenaných výskytů: {len(occurrences)}. Opakování patří do jednoho spisu.', case))
    for plan in plans:
        report = latest.get(plan.get('incident_id'))
        if report and (report.get('plan_id') is None or report.get('plan_id') == hashlib.sha256(
                json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()):
            # An executed plan now needs verification/reporting, not approval again.
            continue
        target = plan.get('target', {})
        title = 'Oprava odkazu v automatizaci ' + str(target.get('automation_id', ''))
        summary = plan.get('reason') or 'Je připravena konkrétní změna k posouzení.'
        card = _card(title, summary, plan)
        card += '<p class="instruction">V místním rozhraní příkazové řádky otevři přesný plán a zvol '
        card += '<strong>Schválit opravu</strong>, <strong>Zamítnout</strong> nebo <strong>Provést ručně</strong>. '
        card += 'Tento statický přehled schválení nevydává. Změna plánu vyžaduje nové schválení.</p>'
        buckets['Co ode mě potřebuje'].append(card)
    for report in latest.values():
        classification = report.get('classification', '')
        if classification == 'Vyřešeno a ověřeno':
            buckets['Co se podařilo vyřešit'].append(_card(classification,
                report.get('summary', 'Funkční výsledek je doložen.'), report))
        elif classification in {'Oprava provedena, ověření čeká', 'Není dostatek důkazů'}:
            buckets['Co ode mě potřebuje'].append(_card('Ještě je potřeba funkční ověření',
                report.get('summary', 'Proveď popsaný funkční test a vyčkej sledovací dobu.'), report))
    sections = ''.join('<section><h2>' + title + '</h2>' + (
        ''.join(cards) if cards else '<p class="empty">Žádné položky v tomto exportu.</p>') + '</section>'
        for title, cards in buckets.items())
    return '''<!doctype html><html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>HADS Next — přehled případů</title><style>
body{font:17px/1.55 system-ui,sans-serif;background:#f3f5f7;color:#182638;margin:0 auto;padding:2rem;max-width:1100px}
header{border-bottom:3px solid #157a6e;margin-bottom:2rem}h1{line-height:1.2}h2{margin-top:2rem}
article{background:white;border:1px solid #cbd5df;border-left:4px solid #157a6e;padding:1rem 1.3rem;margin:.8rem 0;border-radius:5px}
article h3{margin-top:0}details{font-size:.9rem;color:#36465a}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere}
.scope,.instruction{background:#fff6db;padding:1rem;border-radius:5px}.empty{color:#58677a}
</style></head><body><header><h1>HADS Next</h1><p>Přehled funkčních problémů a jejich řešení</p></header>
<p class="scope">Vývojový offline přehled. Opravy a ověření se vztahují pouze k izolovanému testovacímu scénáři. Živý HAOS nebyl ověřen.</p>''' + sections + '</body></html>'


def export_center(path: str | Path, cases: list[dict], plans: list[dict] | None = None,
                  reports: list[dict] | None = None) -> Path:
    target = Path(path)
    target.write_text(render_command_center(cases, plans, reports), encoding='utf-8')
    return target
