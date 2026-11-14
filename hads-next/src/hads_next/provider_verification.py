"""Evidence-based provider inventory from supported native HA reads.

No network discovery, URL guessing, report triggers or model calls. A native
entity read is never relabelled as a functional test of the provider.
"""
import json, math, re
from datetime import datetime
from .evidence import canonical

SPECS = {
    'spook': ('Spook', ('spook',), ('spook',)),
    'ha_mcp': ('HA-MCP', ('ha_mcp_tools', 'ha_mcp'), ('ha_mcp', 'ha_mcp_server')),
    'automation_inspector': ('Automation Inspector', ('automation_inspector',), ('automation_inspector',)),
    'hadocs': ('HADocs', ('hadocs',), ('hadocs',)),
    'entity_availability': ('Entity Availability', ('entity_availability',), ('entity_availability',)),
    'hamster_mcp': ('Hamster MCP', ('hamster_mcp',), ('hamster_mcp',)),
    'haghs': ('Home Assistant Global Health Score', ('haghs',), ('haghs', 'home_assistant_global_health_score')),
    'watchman': ('Watchman', ('watchman',), ('watchman',)),
    'music_assistant': ('Music Assistant', ('music_assistant',), ('music_assistant', 'music_assistant_beta')),
}

def normalized(value):
    return re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_') if isinstance(value, str) else ''

def shape_list(value):
    return isinstance(value, list) and all(isinstance(x, dict) for x in value)

def entity_state(row, now):
    state = row.get('state')
    # A state may contain arbitrary private text/URLs. Only categorical and
    # finite numeric data belong in this general inventory.
    safe = state if isinstance(state,str) and state in {'on','off','unknown','unavailable','idle','ok','error'} else None
    if safe is None and isinstance(state, str):
        try:
            number = float(state)
            if math.isfinite(number): safe = number
        except ValueError: pass
    stamp = row.get('last_updated'); updated = None
    if isinstance(stamp, str):
        try:
            parsed = datetime.fromisoformat(stamp)
            if parsed.tzinfo: updated = parsed.timestamp()
        except (ValueError, OverflowError): pass
    return {'entity_id': row['entity_id'], 'state': safe, 'source_updated_at': updated,
            'state_age_seconds': max(0, now-updated) if updated is not None else None,
            'provider_scan_time_verified': False}

class ProviderVerification:
    def __init__(self, app):
        self.app = app
        with app.store._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS provider_verifications(provider_id TEXT PRIMARY KEY,checked_at REAL NOT NULL,document TEXT NOT NULL)')

    def update(self, values, states):
        config = values.get('core_config')
        loaded = config.get('components') if isinstance(config, dict) else None
        components_ok = isinstance(loaded, list) and all(isinstance(x,str) for x in loaded)
        components = set(loaded) if components_ok else set()
        registry = values.get('entity_registry'); registry_ok = shape_list(registry) and len(registry)<=10000
        apps = values.get('applications'); apps = apps.get('addons') if isinstance(apps, dict) else None
        apps_ok = shape_list(apps) and len(apps)<=1000 and all(isinstance(a.get('slug'),str) and re.fullmatch(r'[a-z0-9_]+',a['slug']) for a in apps)
        states_ok = shape_list(states) and len(states) <= 10000
        state_map = {r.get('entity_id'):r for r in states if isinstance(r.get('entity_id'),str)} if states_ok else {}
        repairs = values.get('repairs'); issues = repairs.get('issues') if isinstance(repairs, dict) else None
        if not shape_list(issues):issues=None
        now = self.app.clock()
        documents = []
        for key, (title, domains, app_names) in SPECS.items():
            matched_components = sorted(components.intersection(domains))
            matched_apps = [a for a in (apps or []) if normalized(a.get('name')) in app_names or a['slug'] in app_names or a['slug'].partition('_')[2] in app_names] if apps_ok else []
            # Entity names alone never establish which integration owns them.
            owned = [r for r in (registry or []) if r.get('platform') in domains and isinstance(r.get('entity_id'),str)
                     and re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+', r['entity_id'])] if registry_ok else []
            # Owner supplied this canonical score entity as a read target.
            # It proves a readable entity, not the package's identity/version.
            if key=='haghs' and 'sensor.system_ha_global_health_score' in state_map and not any(r['entity_id']=='sensor.system_ha_global_health_score' for r in owned):
                owned=owned+[{'entity_id':'sensor.system_ha_global_health_score'}]
            samples = [entity_state(state_map[r['entity_id']], now) for r in owned if r['entity_id'] in state_map][:4]
            known = bool(matched_components or matched_apps)
            gaps = []
            if not components_ok: gaps.append('loaded_components_unavailable')
            if not apps_ok: gaps.append('application_inventory_unavailable')
            if not registry_ok: gaps.append('entity_registry_unavailable')
            if not states_ok: gaps.append('entity_states_unavailable')
            if owned and not samples: gaps.append('owned_entities_have_no_readable_state')
            gaps.append('provider_functional_contract_not_verified')
            relevant_issues = [r for r in (issues or []) if isinstance(r,dict) and r.get('domain') in domains] if isinstance(issues,list) else None
            report = {'provider_id': key, 'title': title, 'presence_confirmed': known,
                      'installation_absence_proven': False, 'matched_components': matched_components,
                      'applications': [{'slug':a['slug'], 'state':a.get('state') if a.get('state') in {'started','stopped','error','startup','failed'} else None,
                                        'version':str(a['version']) if re.fullmatch(r'[A-Za-z0-9_.+:-]{1,80}',str(a.get('version',''))) else None} for a in matched_apps[:8]],
                      'owned_entity_count':len(owned), 'native_state_read_succeeded': bool(samples),
                      'samples':samples, 'samples_truncated':len(owned)>len(samples),
                      'shared_repairs_read_succeeded':isinstance(issues,list),
                      'matching_repairs_count':len(relevant_issues) if relevant_issues is not None else None,
                      'mcp_authenticated':None, 'mcp_catalog_verified':False,
                      'functional_verified':False, 'gaps':gaps, 'writes_enabled':False,
                      'last_error':'Některé nativní podklady nelze aktuálně přečíst.' if any(g!='provider_functional_contract_not_verified' for g in gaps) else None,
                      'summary_cs':('Aktuální stopa nalezena.' if known else 'Aktuální přítomnost nebyla potvrzena; to neprokazuje odinstalování.')
                          + (' Nativní stavy vlastních entit byly přečtené.' if samples else '')
                          + ' Vlastní diagnostická funkce doplňku zatím není ověřená.'}
            documents.append((key,now,canonical(report)))
        with self.app.store._connect() as db:
            db.executemany('INSERT OR REPLACE INTO provider_verifications VALUES(?,?,?)', documents)

    def snapshot(self):
        with self.app.store._connect() as db:
            rows = db.execute('SELECT * FROM provider_verifications ORDER BY provider_id').fetchall()
        now = self.app.clock()
        return [{**json.loads(r['document']), 'checked_at':r['checked_at'], 'read_age_seconds':max(0,now-r['checked_at']),
                 'stale':now-r['checked_at']>600} for r in rows]
