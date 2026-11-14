"""Read Watchman's existing sensor contract; never trigger a scan or a write.

Contract inspected at dummylabs/thewatchman e0bf248 (sensor.py/coordinator.py).
Registry ownership and unique IDs survive user entity renames. Counts without
attributes, parsing in progress and unsupported schemas remain explicit gaps.
"""
from datetime import datetime
import hashlib
import re
from .evidence import canonical

KEYS = ('missing_entities', 'missing_actions', 'last_updated', 'last_parse', 'status')
IDENTIFIER = re.compile(r'[a-z][a-z0-9_]*\.[a-z0-9_]{1,128}')
MAX_ITEMS = 64


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def locations(value):
    """Positive projection of formatted file:lines; omit helper aliases/text."""
    result = []
    if not isinstance(value, str) or len(value) > 8192:
        return result
    for line in value.splitlines()[:32]:
        line = line.removeprefix('📄 ').strip()
        match = re.fullmatch(r'([A-Za-z0-9_./ -]{1,180}):([0-9,]{1,160})', line)
        if not match:
            continue
        path = match[1].removeprefix('/config/')
        if path.startswith('/') or any(x in {'', '.', '..'} for x in path.split('/')):
            continue
        if not (path.endswith(('.yaml', '.yml')) or path.startswith('.storage/lovelace')):
            continue
        lines = match[2].split(',')
        if any(not n or not 0 < int(n) <= 10000000 for n in lines):
            continue
        result.append({'file': path, 'lines': sorted({int(n) for n in lines})[:32]})
        if len(result) >= 4:
            break
    return result


def read_watchman(registry, state_map):
    by_key = {}
    gaps = []
    for row in registry:
        if row.get('platform') != 'watchman':
            continue
        for key in KEYS:
            if row.get('unique_id') == 'watchman_' + key:
                if key in by_key:
                    by_key[key] = None
                else:
                    by_key[key] = state_map.get(row.get('entity_id'))
    report = {'schema_version': 1, 'source': 'watchman_native_sensor_attributes',
              'last_update_at': None, 'last_parse_at': None, 'status': None,
              'counts': {}, 'findings': [], 'gaps': gaps, 'read_verified': False,
              'root_cause_proven': False, 'repair_performed': False}
    for key, target in (('last_updated', 'last_update_at'), ('last_parse', 'last_parse_at')):
        report[target] = timestamp((by_key.get(key) or {}).get('state'))
        if report[target] is None:
            gaps.append(key + '_unavailable')
    status = (by_key.get('status') or {}).get('state')
    report['status'] = status if status in {'idle', 'parsing', 'pending', 'waiting_ha', 'safe_mode'} else None
    if status != 'idle':
        gaps.append('scan_not_confirmed_idle')
    for key in ('missing_entities', 'missing_actions'):
        row = by_key.get(key) or {}
        raw_count = row.get('state')
        count = int(raw_count) if isinstance(raw_count, str) and re.fullmatch(r'[0-9]{1,6}', raw_count) else None
        report['counts'][key] = count
        attrs = row.get('attributes')
        attrs = attrs if isinstance(attrs, dict) else {}
        # Upstream uses entities on initial action sensor property, services on update.
        raw = attrs.get('services', attrs.get('entities')) if key == 'missing_actions' else attrs.get('entities')
        if count is None or not isinstance(raw, list) or len(raw) > 10000:
            gaps.append(key + '_details_unavailable')
            continue
        valid = []
        for item in raw[:MAX_ITEMS]:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not IDENTIFIER.fullmatch(item['id']):
                gaps.append(key + '_invalid_detail')
                continue
            state = item.get('state')
            loc = locations(item.get('occurrences'))
            valid.append({'id': item['id'], 'kind': key,
                          'state': state if state in {'missing', 'disabled', 'registry_disabled', 'unavailable', 'unknown'} else 'unclassified',
                          'locations': loc, 'source_context_required': True,
                          'possible_other_configuration_language': item['id'] in {'logger.log', 'script.execute'}})
        if len(raw) != count or len({x['id'] for x in valid}) != len(raw):
            gaps.append(key + '_count_or_details_incomplete')
        if len(raw) > MAX_ITEMS:
            gaps.append(key + '_truncated')
        report['findings'].extend(valid)
    report['gaps'] = sorted(set(gaps))
    report['read_verified'] = not gaps
    return report


def persist_watchman(app, report):
    """One diagnostic case, stable evidence identity; no artificial recurrence."""
    key = 'provider:watchman:references'
    with app.store._connect() as db:
        existing = db.execute('SELECT id FROM incidents WHERE correlation_key=?', (key,)).fetchone()
    if not report['findings'] and existing is None:
        return None
    event_id = hashlib.sha256(canonical(report).encode()).hexdigest()
    with app.store._connect() as db:
        old = db.execute("SELECT observed_at FROM evidence WHERE source='watchman_native' AND event_id=?", (event_id,)).fetchone()
    at = old[0] if old else app.clock()
    # Re-reading the same unresolved reference set is never another failure.
    incident = app.store.open_incident('provider_diagnostic', 'Watchman: odkazy vyžadují kontrolu kontextu.',
                                       ['integration:watchman'], at, correlation_key=key,
                                       occurrence_id='watchman-reference-review')
    added = app.store.add_evidence(incident['id'], {'source': 'watchman_native', 'kind': 'watchman_reference_snapshot',
                                  'event_id': event_id, 'observed_at': at, 'payload': report})
    if added:
        counts = report['counts']
        summary = ('HADS přečetl podrobnosti existujícího hlášení Watchmanu. '
                   + 'Chybějící entity: ' + str(counts.get('missing_entities'))
                   + '; akce: ' + str(counts.get('missing_actions')) + '. '
                   + ('Čtení je neúplné; chybějící údaje nepovažuji za nulu. ' if report['gaps'] else '')
                   + 'Jde o statické odkazy, nikoli důkaz poruchy zařízení. Zakázaná entita může být záměrná; '
                   'logger.log a script.execute mohou patřit ESPHome. Bez kontextu nic nepřepisuji ani nezapínám.')
        app.store.record(incident['id'], 'deterministic_investigation', {
            'summary_cs': summary, 'root_cause_proven': False,
            'needed': ['Kontext konfigurace a očekávaná funkce pro konkrétní odkaz.'],
            'next_test_cs': 'HADS při pravidelném čtení sám porovná další dostupný snímek Watchmanu. '
                            'Změna počtu ani zmizení odkazu neuzavře spis jako funkčně opravený. '
                            'Bez čtecího adaptéru ke kontextu je příprava přesné opravy omezená.'}, at=at)
    return incident['id']
