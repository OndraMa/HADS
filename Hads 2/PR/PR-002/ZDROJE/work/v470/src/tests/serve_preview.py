"""Loopback-only preview backed by the real HADS DB/HTTP/workflow.

Only synthetic incidents; every Supervisor/API/remote operation is replaced.
Never connects to, modifies or imports data from a real Home Assistant.
"""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hads4
from test_rc8_regressions import RC8RegressionTests

fixture = RC8RegressionTests()
fixture.setUp()
hads4.WEB_DIR = Path(__file__).resolve().parents[1] / 'web'
_, plan_id, root_id = fixture._case_and_plan()
with hads4.db() as conn:
    conn.execute("UPDATE root_cases SET title='Test: oprava doručení oznámení',root_cause='Simulovaný problém pro ověření schvalovacího toku.',recommendation='Zkontrolujte náhled testovací akce. Toto není váš Home Assistant.' WHERE id=?", (root_id,))
    conn.execute("UPDATE repair_plans SET title='Testovací restart doplňku (simulace)',preview_json=? WHERE id=?", ('[{"type":"addon_restart","target":"meross","warning":"Pouze izolovaný lokální test; skutečný HA není připojen."}]',plan_id))
    hads4.ingest_event(conn, {'logger':'demo.transient','source_ref':'demo','integration':'demo','occurred_at':hads4.now_utc(),'level':'WARNING','message':'Simulace: jednorázový výpadek při restartu','source_name':'core'})
hads4.first_officer().rebuild_root_cases()

backups = {}
def supervisor(path, method='GET', body=None, **kw):
    if path=='/core/api/states': return [{'entity_id':'update.codex_terminal_pro_aktualizace','state':'unavailable','attributes':{}}]
    if path=='/core/api/services': return []
    if path=='/addons': return {'addons':[]}
    if path=='/backups/new/full':
        slug=f'test-backup-{len(backups)+1}'
        backups[slug]={'slug':slug,'name':body['name'],'type':'full','homeassistant':'test','homeassistant_exclude_database':False,'size':10,'addons':[{'slug':'meross'}]}
        return {'slug':slug}
    if path.startswith('/backups/') and path.endswith('/info'): return backups[path.split('/')[2]]
    if path=='/addons/meross/info': return {'options':{},'state':'started'}
    if path=='/addons/meross/restart': return {}
    if path=='/core/check': return {}
    raise RuntimeError('Simulovaný zdroj nemá odpověď: '+path)

hads4.supervisor_request=supervisor
hads4.ha_ws_read=lambda *a,**kw: []
hads4._tool_bus_instance=None
hads4.upload_and_verify_rescue=lambda *a,**kw:{'verified':True,'method':'ISOLATED_TEST_DOUBLE'}
hads4.run_deep_audit=lambda *a,**kw:{'ok':True,'test_double':True}
mock.patch('repair_engine.os.chmod').start()
hads4.tool_bus().refresh(force=True)
hads4.update_collector_source('core',True,required=True,line_count=150,findings_count=2)
hads4.update_collector_source('host',False,required=True,error='Simulace: HTTP 502')
server=ThreadingHTTPServer(('127.0.0.1',0),hads4.Handler)
print(f'Preview: http://127.0.0.1:{server.server_port}/ ; synthetic DB: {hads4.DB_PATH}',flush=True)
try:server.serve_forever()
finally:server.server_close()
