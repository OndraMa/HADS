"""New candidate boundaries, real TLS/wire reads and source-only upgrade lifecycle."""
import base64
from contextlib import closing
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import ipaddress
import json
from pathlib import Path
import ssl
import tarfile
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.request import HTTPSHandler, build_opener
from urllib.parse import urlencode

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.x509.oid import NameOID
from hads_next.addon_server import Server
from hads_next.build_identity import VERSION, inspect_build, invalidate_previous_approvals
from hads_next.evidence import canonical
from hads_next.haos_application import Application
from hads_next.observability import ReadFailure, CoreWSReader, SupervisorReader
from hads_next.repair import connect
from hads_next.tool_registry import ToolDenied
from hads_next.connector_transport import MCPConnection

ROOT=Path(__file__).resolve().parents[1]


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.now=1800000000.
        self.app=Application(self.root/'data',clock=lambda:self.now)
        with self.app.store._connect() as db:db.execute("INSERT INTO application_settings VALUES('owner','owner')")
        self.case=self.app.store.open_incident('manual_functional','Fixture only',['script.fixture','integration:icloud'],self.now)

    def test_packaged_identity_detects_modified_or_unproven_runtime_sources(self):
        package=self.root/'hads_next';package.mkdir();source=package/'one.py';source.write_bytes(b'pass\n')
        manifest={'version':VERSION,'slug':'hads_next_practical','worktree_modified_at_build':False,
            'source_revision_at_build':'a'*40,'build_id':'b'*64,'files':{'hads_next/one.py':{'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}}
        (self.root/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest))
        self.assertTrue(inspect_build(package)['source_verified'])
        source.write_bytes(b'changed\n');self.assertFalse(inspect_build(package)['source_verified'])
        source.write_bytes(b'pass\n');manifest['worktree_modified_at_build']=True
        (self.root/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest));self.assertFalse(inspect_build(package)['source_verified'])

    def test_build_change_expires_unused_approvals_without_erasing_history(self):
        with closing(connect(self.app.store.db_path)) as db:
            db.execute("INSERT INTO repair_plans VALUES('plan','{}',X'00',0)")
            db.execute("INSERT INTO repair_decisions VALUES('token','plan','owner','approve',?,NULL)",(self.now+300,))
        with patch('hads_next.build_identity.current_build',return_value={'source_verified':True,'build_id':'new-build'}):
            invalidate_previous_approvals(self.app)
        with self.app.store._connect() as db:
            row=db.execute('SELECT * FROM repair_decisions').fetchone();self.assertEqual(row['expires_at'],self.now)
            self.assertEqual(row['decision'],'approve');self.assertEqual(db.execute('SELECT count(*) FROM repair_plans').fetchone()[0],1)

    def test_owner_dialogue_survives_restart_enters_evidence_and_never_approves(self):
        from hads_next.case_dialogue import render
        identity=self.case['id']
        self.app.dialogue.add(identity,'<script>bad</script> Rádio se zastavilo. https://example.invalid/private_secret','owner')
        with self.assertRaises(ValueError):self.app.dialogue.add(identity,'approve','other')
        reopened=Application(self.root/'data',clock=lambda:self.now)
        case=reopened.store.case(identity);page=render(case,'csrf')
        self.assertNotIn('<script>',page);self.assertNotIn('private_secret',canonical(case))
        self.assertTrue(any(e['kind']=='owner_statement' for e in case['evidence']))
        result=reopened.investigations.broker._read(identity,'hads_get_incident',{})
        self.assertIn('Rádio',canonical(result));self.assertIn('not_approval',canonical(result))
        with closing(connect(reopened.store.db_path)) as db:self.assertEqual(db.execute('SELECT count(*) FROM repair_decisions').fetchone()[0],0)
        self.assertEqual(reopened.store.case(identity)['incident']['status'],'open')

    def test_real_owner_http_dialogue_rejects_forged_csrf_and_keeps_message_private(self):
        self.app.core_ws=CoreWSReader(lambda _: [{'id':'owner','is_active':True,'is_owner':True,'system_generated':False,'group_ids':[]}])
        server=Server(('127.0.0.1',0),self.app,ingress_peer='127.0.0.1',owner_user_id='owner')
        threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def post(csrf):
            client=http.client.HTTPConnection('127.0.0.1',server.server_port)
            client.request('POST','/case/message',urlencode({'csrf':csrf,'incident_id':self.case['id'],'message':'Výsledek fyzického pozorování'}),{'X-Remote-User-Id':'owner','Content-Type':'application/x-www-form-urlencoded'})
            response=client.getresponse();status=response.status;response.read();client.close();return status
        self.assertEqual(post('forged'),403);self.assertEqual(post(server.csrf),303)
        self.assertEqual(len([r for r in self.app.store.case(self.case['id'])['records'] if r['kind']=='owner_message']),1)

    def test_ignore_and_read_only_recheck_preserve_case_without_inventing_repair_or_occurrence(self):
        before=len(self.app.store.case(self.case['id'])['occurrences'])
        self.app.dialogue.attention(self.case['id'],'ignore','owner')
        self.assertEqual(self.app.store.case(self.case['id'])['incident']['status'],'archived')
        with patch.object(self.app,'request_source_check',return_value=True) as read:
            self.app.dialogue.attention(self.case['id'],'recheck','owner');read.assert_called_once()
        after=self.app.store.case(self.case['id']);self.assertEqual(after['incident']['status'],'open')
        self.assertEqual(len(after['occurrences']),before)

    def test_script_configuration_uses_actual_MCP_wire_schema_and_never_exposes_script_writes(self):
        calls=[]
        schema={'type':'object','properties':{'script_id':{'type':'string'}},'required':['script_id']}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                rpc=json.loads(self.rfile.read(int(self.headers['Content-Length'])));calls.append(rpc)
                method=rpc['method']
                if method=='notifications/initialized':self.send_response(202);self.end_headers();return
                if method=='initialize':value={'protocolVersion':'2025-06-18','capabilities':{},'serverInfo':{'name':'ha-mcp-fixture','version':'9.2.0'}}
                elif method=='tools/list':value={'tools':[{'name':name,'inputSchema':schema} for name in ['ha_config_get_script','ha_config_set_script']]}
                elif method=='tools/call':
                    assert rpc['params']['name']=='ha_config_get_script'
                    value={'structuredContent':{'success':True,'config_hash':'f'*64,'config':{'alias':'Fixture','sequence':[{'action':'light.turn_off','target':{'entity_id':'light.fixture'},'data':{'alarm_secret':'not-for-evidence'}}]}}}
                else:raise AssertionError(method)
                data=json.dumps({'jsonrpc':'2.0','id':rpc['id'],'result':value}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        client=MCPConnection('http://127.0.0.1:'+str(server.server_port)+'/mcp',allow_private_http=True)
        self.app.tools._mcp('ha_mcp',client)
        result=self.app.tools.diagnostic_read(self.case['id'],{'provider':'ha_mcp','tool':'ha_config_get_script','arguments':{'script_id':'script.fixture'}})
        self.assertEqual(result['status'],'available');self.assertIn('light.turn_off',canonical(result));self.assertNotIn('not-for-evidence',canonical(result))
        before=len(calls)
        for tool,args in [('ha_config_get_script',{'script_id':'script.other'}),('ha_config_set_script',{'script_id':'script.fixture'})]:
            with self.assertRaises(ToolDenied):self.app.tools.diagnostic_read(self.case['id'],{'provider':'ha_mcp','tool':tool,'arguments':args})
        self.assertEqual(len(calls),before)

    def test_connection_outcomes_are_specific_and_never_echo_secret_url(self):
        from hads_next.connection_diagnostics import connection_failure
        from hads_next.tool_ui import settings
        for status in [401,403,404,503]:
            value=connection_failure(ReadFailure('https://secret.invalid/private_secret',status))
            self.assertEqual(value['last_response_status'],status);self.assertNotIn('private_secret',canonical(value))
            self.assertTrue(value['next_step_cs'])
        page=settings(self.app,'csrf')
        self.assertIn('name="url" type="password"',page)

    def test_failed_connector_preserves_specific_error_without_interrupting_native_catalog(self):
        class Unavailable:
            def discover(self):raise ReadFailure('private_secret',503)
        self.app.tools.connections.clients['ha_mcp']=Unavailable()
        self.app.tools.refresh({},[])
        rows={r['id']:r for r in self.app.tools.registry.providers()};value=rows['ha_mcp']
        self.assertEqual(value['last_response_status'],503);self.assertEqual(value['error_code'],'service_unavailable')
        self.assertFalse(value['catalog_loaded']);self.assertNotIn('private_secret',canonical(rows))
        self.assertIn('core',rows)

    def test_fifteen_minute_resource_study_counts_real_reads_and_breaks_on_gap(self):
        reads=[]
        def transport(path):
            reads.append(path);return {'result':'ok','data':{'memory_usage':40000000,'memory_limit':2000000000,'cpu_percent':1.0}}
        self.app.supervisor=SupervisorReader(transport)
        self.app._apps=[{'slug':'local_fixture','state':'started'}]
        with patch('hads_next.readiness.memory_available',return_value=300*1024*1024):
            for _ in range(16):self.app.resource_study.tick();self.now+=60
            result=self.app.resource_study.status()
            self.assertEqual(result['state'],'measured');self.assertGreaterEqual(result['covered_seconds'],900)
            self.assertFalse(result['worker_allowed_at_every_sample']);self.assertFalse(result['target_hardware_verified'])
            self.assertEqual(reads.count('/core/stats'),16);self.assertEqual(reads.count('/supervisor/stats'),16)
            evidence=self.app.investigations.broker._read(self.case['id'],'hads_get_runtime_health',{})
            self.assertEqual(evidence['data']['resource_study']['samples'],16)
            self.assertEqual(evidence['data']['resource_study']['minimum_available_bytes'],300*1024*1024)
            self.assertNotIn('samples_detail',evidence['data']['resource_study'])
            self.assertTrue(evidence['evidence_ids'])
            self.now+=91;self.assertEqual(self.app.resource_study.status()['state'],'interrupted')
            self.app.resource_study.tick();self.assertEqual(self.app.resource_study.status()['samples'],1)

    def test_self_generated_hads_logs_are_not_new_incidents(self):
        result=self.app.orchestration.correlate([{'source':'core','observed_at':self.now,'component':'hads_next.report','message':'DNS connection reset'}])
        self.assertEqual(result,[])
        with self.app.store._connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM orchestration_log_events').fetchone()[0],0)

    def test_memory_case_autonomously_reads_the_same_study_broker_without_model(self):
        memory=self.app.store.open_incident('system_resource_pressure','Fixture memory reserve',['hads_runtime'],self.now)
        self.app.tools._native({'core_config':{'version':'2026.11.2'}})
        self.app.orchestration.cycle(budget=1)
        case=self.app.store.case(memory['id'])
        self.assertTrue(any(e['source']=='hads_controller' for e in case['evidence']))
        with self.app.store._connect() as db:
            row=db.execute("SELECT state FROM orchestration_reads WHERE incident_id=? AND tool='hads_get_runtime_health'",(memory['id'],)).fetchone()
            self.assertEqual(row[0],'available');self.assertEqual(db.execute('SELECT count(*) FROM investigation_model_calls').fetchone()[0],0)

    def test_current_service_catalog_is_scoped_and_never_guesses_a_replacement(self):
        from hads_next.native_tool_reads import install
        self.app.core_ws=CoreWSReader(lambda q:{'icloud':{'request_sync':{'fields':{}}}} if q['type']=='get_services' else None)
        self.app.tools.registry.provider('core',connected=True,catalog_loaded=True)
        install(self.app.tools)
        result=self.app.tools.diagnostic_read(self.case['id'],{'provider':'core','tool':'services','arguments':{'domain':'icloud'}})
        self.assertEqual(result['status'],'available');self.assertFalse(result['data']['replacement_proven'])
        with self.assertRaises(ToolDenied):self.app.tools.diagnostic_read(self.case['id'],{'provider':'core','tool':'services','arguments':{'domain':'lock'}})


class IndependentVerifierTLSTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.now=1800000000.;self.target='a'*64;self.signer=ed25519.Ed25519PrivateKey.generate()
        self.public=base64.b64encode(self.signer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
        self.calls=[];self.status=200;self.envelope=None
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Anonymous verifier fixture')]);now=datetime.now(timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
            .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(key,hashes.SHA256()))
        cert_path=self.root/'tls.pem';key_path=self.root/'tls.key'
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM));key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                owner.calls.append({'target':self.headers.get('HADS-Target-SHA256'),'authorization':self.headers.get('Authorization')})
                data=json.dumps(owner.envelope).encode();self.send_response(owner.status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert_path,key_path)
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        threading.Thread(target=self.server.serve_forever,daemon=True).start();self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.context=ssl.create_default_context(cafile=str(cert_path))
        from hads_next.restore_receipt import RestoreReceiptVerifier
        self.verifier=RestoreReceiptVerifier(self.root,lambda:self.now)
        self.verifier.connection.configure('https://127.0.0.1:'+str(self.server.server_port)+'/signed-receipt','fixture-only-token',self.public,principal='owner',owner='owner')
        self.sign()

    def sign(self,**changes):
        value={'schema':1,'storage':'OneDrive','restored':True,'scope':'HAOS_config_and_registry','verifier':'independent-fixture-not-production','target_sha256':self.target,'backup_sha256':'b'*64,'verified_at':self.now-1,'expires_at':self.now+100,**changes}
        self.envelope={'attestation':value,'signature':base64.b64encode(self.signer.sign(canonical(value).encode())).decode()}

    def trusted(self):
        return patch('hads_next.restore_connection.build_opener',side_effect=lambda *handlers:build_opener(*handlers,HTTPSHandler(context=self.context)))

    def test_real_verified_tls_signature_target_scope_and_cache_with_no_signing_key_in_controller(self):
        with self.trusted():
            result=self.verifier.verify(self.target)
            self.assertEqual(self.verifier.verify(self.target),result)
        self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0]['target'],self.target)
        self.assertEqual(result['verifier_key_sha256'],hashlib.sha256(base64.b64decode(self.public)).hexdigest())
        self.assertEqual((self.root/'restore-attestation.json').stat().st_mode&0o777,0o600)
        self.assertNotIn('fixture-only-token',canonical(self.verifier.status()))

    def test_untrusted_tls_and_remote_503_cannot_create_a_proof(self):
        with self.assertRaises(ToolDenied):self.verifier.verify(self.target)
        self.assertFalse((self.root/'restore-attestation.json').exists())
        self.status=503
        with self.trusted(),self.assertRaises(ToolDenied):self.verifier.verify(self.target)
        self.assertFalse((self.root/'restore-attestation.json').exists())

    def test_signature_does_not_substitute_for_target_scope_or_actual_restore(self):
        for changes in [{'target_sha256':'c'*64},{'restored':False},{'scope':'upload_only'},{'expires_at':self.now-1}]:
            self.sign(**changes)
            with self.trusted(),self.assertRaises(ToolDenied):self.verifier.verify(self.target)
            self.assertFalse((self.root/'restore-attestation.json').exists())
        self.sign();self.envelope['signature']=base64.b64encode(b'bad-signature'*5).decode()
        with self.trusted(),self.assertRaises(ToolDenied):self.verifier.verify(self.target)
