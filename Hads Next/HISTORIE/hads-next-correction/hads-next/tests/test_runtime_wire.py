"""Offline wire integration: real HTTP and WS clients, fixture HA server.

This does not establish live Core/Supervisor or HAOS acceptance.
"""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlencode
from unittest.mock import patch
import unittest

from websockets.sync.client import connect as actual_connect
from websockets.sync.server import serve
from hads_next.addon_server import Server, SupervisorCoreTransport, SupervisorTransport
from hads_next.haos_application import Application
from hads_next.observability import CoreReader, CoreWSReader, NativeHTTP, NativeWebSocket, SupervisorReader


class WireIntegration(unittest.TestCase):
    def test_ingress_enrollment_app_logs_and_radio_context_use_real_wire_clients(self):
        now=time.time(); calls=[]
        users=[{'id':'fixture-admin','is_owner':True,'is_active':True,'system_generated':False,'group_ids':[]}]
        context='stop-context'
        def ws_handler(ws):
            ws.send(json.dumps({'type':'auth_required'}))
            self.assertEqual(json.loads(ws.recv())['access_token'],'fixture-only')
            ws.send(json.dumps({'type':'auth_ok'}))
            cmd=json.loads(ws.recv());calls.append(cmd['type'])
            data={'config/auth/list':users,'config/entity_registry/list':[],
                'config/device_registry/list':[],'repairs/list_issues':{'issues':[]},'system_log/list':[]}.get(cmd['type'])
            if cmd['type']=='logbook/get_action_calls':
                data=[{'domain':'media_player','service':'media_stop','when':now-2,'context_id':context,
                       'service_data':{'entity_id':'media_player.radio','code':'DO_NOT_EXPORT'}}]
            ws.send(json.dumps({'id':cmd['id'],'type':'result','success':True,'result':data}))
        class HTTP(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(handler):
                self.assertEqual(handler.headers.get('Authorization'),'Bearer fixture-only')
                calls.append(handler.path)
                if handler.path.endswith('/logs'):
                    data=b'provider failed password=DO_NOT_EXPORT'
                else:
                    if handler.path=='/core/api/config': result={'version':'2026.11.0','time_zone':'Europe/Prague'}
                    elif handler.path=='/core/api/states': result=[]
                    elif handler.path=='/addons': result={'result':'ok','data':{'addons':[{'slug':'fixture_music','name':'Music fixture'}]}}
                    elif handler.path.startswith('/core/api/history/period/'):
                        from datetime import datetime,timezone
                        iso=lambda n:datetime.fromtimestamp(n,timezone.utc).isoformat()
                        result=[[{'entity_id':'media_player.radio','state':'playing','last_updated':iso(now-10)},
                                 {'entity_id':'media_player.radio','state':'idle','last_updated':iso(now-1),'context':{'id':context}}]]
                    else:result={'result':'ok','data':{'slug':'fixture_music','version':'1','state':'stopped'}}
                    data=json.dumps(result).encode()
                handler.send_response(200);handler.end_headers();handler.wfile.write(data)
        upstream=ThreadingHTTPServer(('127.0.0.1',0),HTTP)
        http_thread=threading.Thread(target=upstream.serve_forever,daemon=True);http_thread.start()
        try:
            with serve(ws_handler,'127.0.0.1',0) as websocket, tempfile.TemporaryDirectory() as directory:
                thread=threading.Thread(target=websocket.serve_forever,daemon=True);thread.start()
                address=f'ws://127.0.0.1:{websocket.socket.getsockname()[1]}'
                with patch('websockets.sync.client.connect',side_effect=lambda _,**kw:actual_connect(address,**kw)):
                    native=NativeHTTP(f'http://127.0.0.1:{upstream.server_port}','fixture-only',allow_local_http=True)
                    core=SupervisorCoreTransport('fixture-only');core._http=native
                    supervisor=SupervisorTransport('fixture-only');supervisor._http=native
                    ws=CoreWSReader(NativeWebSocket('ws://supervisor/core/websocket','fixture-only',supervisor_proxy=True))
                    app=Application(Path(directory),CoreReader(core),core_ws=ws,supervisor=SupervisorReader(supervisor))
                    app.refresh()
                    server=Server(('127.0.0.1',0),app,ingress_peer='127.0.0.1')
                    ui_thread=threading.Thread(target=server.serve_forever,daemon=True);ui_thread.start()
                    def request(method,path,fields=None):
                        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
                        connection.request(method,path,urlencode(fields) if fields else None,
                            {'X-Remote-User-Id':'fixture-admin','Content-Type':'application/x-www-form-urlencoded'})
                        response=connection.getresponse();result=(response.status,response.read().decode());connection.close();return result
                    try:
                        self.assertIn('Vítej v HADS',request('GET','/')[1])
                        self.assertEqual(request('POST','/setup/enroll',{'csrf':server.csrf})[0],303)
                        for _ in range(100):
                            if app.snapshot()['source_job']['state']!='running':break
                            time.sleep(.02)
                        self.assertEqual(app.snapshot()['source_job']['state'],'finished')
                        self.assertTrue(app.snapshot()['sources']['applications']['read_succeeded'])
                        self.assertEqual(request('POST','/incident/app',{'csrf':server.csrf,'slug':'fixture_music','symptom':'Hudba nefunguje'})[0],303)
                        self.assertEqual(request('POST','/incident',{'csrf':server.csrf,'entity_id':'media_player.radio','symptom':'Rádio se vypnulo'})[0],303)
                        radio=next(c for c in app.snapshot()['cases'] if c['kind']=='manual_functional')
                        status,page=request('GET','/case/'+radio['id'])
                        self.assertEqual(status,200)
                        self.assertIn('Zastavení navazuje na příkaz',page)
                        self.assertNotIn('DO_NOT_EXPORT',page)
                        self.assertIn('/addons/fixture_music/logs',calls)
                        self.assertIn('logbook/get_action_calls',calls)
                        users[0]['is_active']=False;server._auth_cache=None
                        self.assertEqual(request('GET','/api/status')[0],403)
                        self.assertEqual(Application(Path(directory)).owner(),'fixture-admin')
                    finally:
                        server.shutdown();server.server_close();ui_thread.join()
                websocket.shutdown();thread.join()
        finally:
            upstream.shutdown();upstream.server_close();http_thread.join()


if __name__=='__main__':unittest.main()
