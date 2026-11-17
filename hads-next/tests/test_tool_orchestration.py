"""Practical isolated provider wire scenarios. No live HAOS or paid LLM."""
import base64
import copy
import json
import tempfile
import threading
import unittest
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from contextlib import closing

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from hads_next.haos_application import Application
from hads_next.observability import CoreReader,CoreWSReader,ReadFailure
from hads_next.connector_transport import MCPConnection,ReportHTTP
from hads_next.connector_policy import READS,WRITES
from hads_next.tool_registry import ToolDenied,object_schema,validate,fingerprint
from hads_next.repair import RepairPlan,RepairBlocked,ApprovalAuthority,connect
from hads_next.evidence import canonical
from hads_next.tool_ui import settings

class OrchestratedWire(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=1800000000.;self.writes=[];self.calls=[];self.meta=False;self.changed_schema=False;self.uncertain=False;self.guide_ack='I-HAVE-READ-THE-BEST-PRACTICES-GUIDE-1234abcd'
        self.old='light.original_fixture';self.new='light.current_fixture';self.auto='automation.fixture_room'
        self.config={'id':'automation_fixture_id','alias':'Fixture room','triggers':[{'trigger':'state','entity_id':'binary_sensor.fixture_button','to':'on'}],
                     'conditions':[],'actions':[{'action':'light.turn_on','target':{'entity_id':self.old}}]}
        self.entry={'entity_id':'binary_sensor.fixture_contact','unique_id':'fixture_identity','device_id':'device_fixture','platform':'zha','config_entry_id':'zha_fixture','disabled_by':'user'}
        self.server=ThreadingHTTPServer(('127.0.0.1',0),self.handler());self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.app=Application(self.tmp.name,CoreReader(self.core),core_ws=CoreWSReader(self.ws),clock=lambda:self.now)
        self.addCleanup(self.app.repairs.close);self.addCleanup(self.app.detection.close)
        with self.app.store._connect() as db:db.execute("INSERT INTO application_settings VALUES('owner','owner-fixture')")
        self.app.tools.connections.configure('ha_mcp',url=self.url+'/mcp',token='fixture-only-token',private_http=True,enabled=True,principal='owner-fixture')
        self.client=self.app.tools.connections.clients['ha_mcp'];self.app.tools._mcp('ha_mcp',self.client)
        previous={'platform':'zha','unique_id':'light_identity_fixture','device_id':'light_device_fixture','entity_id':self.old,'config_entry_id':'zha_fixture'}
        self.app.approved_tools.identities([previous]);self.app.approved_tools.identities([{**previous,'entity_id':self.new}])
        self.case=self.app.store.open_incident('automation_reference','Ovladač nerozsvítí světlo',[self.auto,self.old],self.now,correlation_key='fixture:room')
        self.app.store.add_evidence(self.case['id'],{'source':'native_entity_context','kind':'entity_context','event_id':'fixture_initial','observed_at':self.now,'payload':{'entity_id':self.old,'classification':'missing'}})
        self.evidence=[e['evidence_id'] for e in self.app.store.case(self.case['id'])['evidence']]
    def definitions(self):
        rows=[{'name':n,'inputSchema':s} for n,s in {**READS,**WRITES}.items()]
        if self.changed_schema:rows[-1]['inputSchema']={**rows[-1]['inputSchema'],'description':'changed schema binding'}
        rows.append({'name':'run_arbitrary_shell','inputSchema':object_schema({'command':{'type':'string'}}),'annotations':{'readOnlyHint':True}})
        return rows
    def handler(self):
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def output(self,value,status=200):
                data=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def do_POST(self):
                outer.assertEqual(self.headers.get('Authorization'),'Bearer fixture-only-token')
                msg=json.loads(self.rfile.read(int(self.headers['Content-Length'])));outer.calls.append(msg)
                if msg['method']=='notifications/initialized':self.send_response(202);self.send_header('Content-Length','0');self.end_headers();return
                if msg['method']=='initialize':result={'protocolVersion':'2025-06-18','serverInfo':{'name':'ha-mcp','version':'fixture-contract-1'}}
                elif msg['method']=='tools/list':
                    if outer.meta:
                        result={'tools':[{'name':'ha_search_tools','inputSchema':object_schema({'tools':{'type':'array','items':{'type':'string'}}})},
                            *[{'name':n,'inputSchema':object_schema({'name':{'type':'string'},'arguments':{'type':'object'}})} for n in ('ha_call_read_tool','ha_call_write_tool')]]}
                    elif msg.get('params',{}).get('cursor')=='page2':result={'tools':outer.definitions()[2:]}
                    else:result={'tools':outer.definitions()[:2],'nextCursor':'page2'}
                elif msg['method']=='tools/call':
                    name=msg['params']['name'];args=msg['params']['arguments']
                    if name=='ha_search_tools':value=[r for r in outer.definitions() if r['name'] in args['tools']]
                    else:
                        if name in {'ha_call_read_tool','ha_call_write_tool'}:name=args['name'];args=args['arguments']
                        if name=='ha_get_skill_guide':value={'success':True,'file':args['file'],'content':'Acknowledgment key: '+outer.guide_ack+' — strict best-practices. Use literal targets and supported state triggers.'}
                        elif name=='ha_config_get_automation':value={'success':True,'config':copy.deepcopy(outer.config),'config_hash':fingerprint(outer.config),'references':{'entities':[outer.old]}}
                        elif name=='ha_get_state':value={'success':True,'data':{'entity_id':args['entity_id'],'state':'unavailable','private_token':'NEVER_EXPORT'}}
                        elif name=='ha_config_set_automation':
                            outer.assertEqual(args['config_hash'],fingerprint(outer.config));outer.assertIs(args['run_actions'],False);outer.assertEqual(args['BestPracticeKey'],outer.guide_ack)
                            outer.writes.append(copy.deepcopy(args));outer.config=copy.deepcopy(args['config'])
                            if outer.uncertain:self.output({'error':'lost reply'},503);return
                            value={'success':True,'config_hash':fingerprint(outer.config)}
                        elif name=='ha_get_device':value={'success':True,'device_id':'light_device_fixture','lqi':75}
                        else:value={'success':True,'repairs':[]}
                    result={'structuredContent':{'result':value},'_meta':{'fastmcp':{'wrap_result':True}}} if name=='ha_search_tools' else {'content':[{'type':'text','text':json.dumps(value)}]}
                else:outer.fail('unexpected MCP method '+msg['method'])
                self.output({'jsonrpc':'2.0','id':msg['id'],'result':result})
            def do_GET(self):
                if self.path=='/api/v1/status':self.output({'ready':True,'stale':False,'generation':1});return
                if self.path=='/api/v1/inspection':self.output({'schema_version':2,'app_version':'1.2.4','generated_at':outer.iso(outer.now),
                    'automations':{outer.auto:{'entity_id':outer.auto,'status':'enabled','entities':[{'id':outer.old,'status':'missing'}],'issue_count':1}},'scripts':{}});return
                if self.path=='/api/status':self.output({'version':'0.17.0-rc5','running':False,'finished_at':outer.iso(outer.now),'exit_code':0});return
                if self.path=='/api/summary':self.output({'available':True,'health':{'score':97},'incidents':[{'entity_id':outer.old,'reason':'invalid reference'}],'recommendations':[{'entity_id':outer.old,'description':'Inspect exact dependency'}]});return
                outer.fail('unexpected report path '+self.path)
        return Handler
    @staticmethod
    def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
    def core(self,path):
        if path=='/api/states/'+self.old:raise ReadFailure('http_error',404)
        if path=='/api/states/'+self.new:return {'entity_id':self.new,'state':'off','last_updated':self.iso(self.now)}
        if path=='/api/states/'+self.auto:return {'entity_id':self.auto,'state':'on','attributes':{'id':self.config['id']}}
        if path=='/api/states/'+self.entry['entity_id']:
            if self.entry['disabled_by'] is not None:raise ReadFailure('http_error',404)
            return {'entity_id':self.entry['entity_id'],'state':'on','last_updated':self.iso(self.now)}
        raise ReadFailure('unknown_fixture')
    def ws(self,command):
        if command['type']=='get_services':return {'homeassistant':{'enable_entity':{'fields':{'entity_id':{'required':True}}},'disable_entity':{'fields':{'entity_id':{'required':True}}}}}
        if command['type']=='manifest/get':return {'domain':'spook','version':'fixture-contract-1'}
        if command['type']=='config/entity_registry/get':return copy.deepcopy(self.entry)
        if command['type']=='call_service':
            self.assertEqual(command['domain'],'homeassistant');self.assertIn(command['service'],{'enable_entity','disable_entity'})
            self.assertEqual(command['service_data'],{'entity_id':[self.entry['entity_id']]})
            self.entry['disabled_by']=None if command['service']=='enable_entity' else 'user';self.writes.append(copy.deepcopy(command));return None
        raise ReadFailure('unsupported_fixture')
    def receipt(self,original):
        key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        attestation={'schema':1,'storage':'OneDrive','scope':'HAOS_config_and_registry','restored':True,'verifier':'independent-fixture-verifier',
            'target_sha256':fingerprint(original),'verified_at':self.now,'expires_at':self.now+3600,'backup_sha256':'a'*64}
        envelope={'attestation':attestation,'signature':base64.b64encode(key.sign(canonical(attestation).encode())).decode()}
        for name,value in [('backup-verifier.pub',base64.b64encode(public).decode()),('restore-attestation.json',json.dumps(envelope))]:
            p=self.app.data_dir/name;p.write_text(value);p.chmod(0o600)
    def prepare(self):
        proposed=copy.deepcopy(self.config);proposed['actions'][0]['target']['entity_id']=self.new
        original={'config':copy.deepcopy(self.config),'config_hash':fingerprint(self.config)};self.receipt(original)
        return self.app.approved_tools.prepare(self.case['id'],'ha_mcp','ha_config_set_automation',{'entity_id':self.auto,'config':proposed,'config_hash':fingerprint(self.config),'wait':True,'run_actions':False},self.evidence,'Doložená nová identita stejného zařízení',exclusive=True)
    def test_A_B_real_wire_reports_discovery_iteration_and_approved_config_change(self):
        for p in ('automation_inspector','hadocs'):self.app.tools._http(p,ReportHTTP(self.url,allow_private_http=True))
        result=self.app.investigations.broker.read(self.case['id'],'hads_diagnostic_tool',{'provider':'automation_inspector','tool':'dependency_report','arguments':{}})
        self.assertEqual(result['status'],'available');self.assertEqual(result['data']['items'][0]['entities'][0]['id'],self.old)
        hadocs=self.app.investigations.broker.read(self.case['id'],'hads_diagnostic_tool',{'provider':'hadocs','tool':'analysis_report','arguments':{}})
        self.assertEqual(hadocs['data']['health']['score'],97)
        self.assertTrue(result['evidence_ids']);self.assertEqual(self.writes,[])
        self.assertTrue(any(m['method']=='tools/list' and m['params'].get('cursor')=='page2' for m in self.calls))
        plan=self.prepare();self.assertEqual(len(self.app.repairs.plans(self.case['id'])),1)
        execution=self.app.approved_tools.decide(plan.plan_id,'approve','owner-fixture',exclusive=True)
        self.assertEqual(len(self.writes),1);self.assertEqual(execution.status,'applied_verification_pending');self.assertEqual(self.config['actions'][0]['target']['entity_id'],self.new)
        self.assertEqual(self.app.store.case(self.case['id'])['incident']['status'],'open')
        # No log disappearance or successful write can substitute a real trigger,
        # matching context, physical confirmation and continuous coverage.
        self.now+=1;self.app.detection.health.update(state='listening',heartbeat_at=self.now,continuous_since=self.now)
        self.app.repairs.trigger_coverage=self.now;self.app.repairs.trigger_heartbeat=self.now
        self.assertNotEqual(self.app.approved_tools.verify(plan.plan_id)['classification'],'Vyřešeno a ověřeno')
        trigger=self.now;self.app.repairs.on_trigger({'data':{'entity_id':self.auto},'time_fired':self.iso(self.now),'context':{'id':'fixture_context'}})
        self.now+=1;self.app.repairs.observe_state({'entity_id':self.new,'state':'on','context':{'id':'fixture_context'}},self.now)
        self.now+=1;self.app.approved_tools.confirm_physical(plan.plan_id,'owner-fixture')
        self.now=trigger+33;self.app.detection.health['heartbeat_at']=self.now;self.app.repairs.trigger_heartbeat=self.now
        self.assertEqual(self.app.approved_tools.verify(plan.plan_id)['classification'],'Vyřešeno a ověřeno')
        self.assertEqual(self.app.store.case(self.case['id'])['incident']['status'],'resolved')
    def test_meta_tool_search_is_discovered_but_proxies_never_exposed_to_AI(self):
        self.meta=True;self.app.tools._mcp('ha_mcp',self.client)
        self.assertIn('ha_config_get_automation',self.client.delegated)
        self.assertEqual(self.client.call('ha_config_get_automation',{'entity_id':self.auto})['config'],self.config)
        with self.assertRaises(ToolDenied):self.app.tools.registry.get('ha_mcp','ha_call_write_tool',effect='read')
    def test_F_unknown_shell_hint_and_write_through_diagnostic_route_are_denied(self):
        for name,args in [('run_arbitrary_shell',{'command':'echo forbidden'}),('ha_config_set_automation',{})]:
            with self.assertRaises(ToolDenied):self.app.tools.diagnostic_read(self.case['id'],{'provider':'ha_mcp','tool':name,'arguments':args})
        with self.assertRaises(ToolDenied):validate({'$ref':'https://invalid.invalid/schema'}, {})
        self.assertEqual(self.writes,[])
    def test_expired_forged_wrong_principal_changed_schema_and_target_block_before_write(self):
        plan=self.prepare()
        with self.assertRaises(RepairBlocked):self.app.approved_tools.execute(plan,'forged','owner-fixture')
        with self.assertRaises(RepairBlocked):self.app.approved_tools.decide(plan.plan_id,'approve','other',exclusive=True)
        token=ApprovalAuthority(self.app.store.db_path,owner='owner-fixture',clock=lambda:self.now).approve(plan,principal='owner-fixture',ttl=1)
        self.now+=2
        with self.assertRaises(RepairBlocked):self.app.approved_tools.execute(plan,token,'owner-fixture')
        self.changed_schema=True
        with self.assertRaises(RepairBlocked):self.app.approved_tools.decide(plan.plan_id,'approve','owner-fixture',exclusive=True)
        self.changed_schema=False;self.config['alias']='concurrent editor'
        with self.assertRaises(RepairBlocked):self.app.approved_tools.decide(plan.plan_id,'approve','owner-fixture',exclusive=True)
        self.assertEqual(self.writes,[])
    def test_G_timeout_after_write_is_durable_unknown_and_restart_never_replays(self):
        plan=self.prepare();self.uncertain=True
        result=self.app.approved_tools.decide(plan.plan_id,'approve','owner-fixture',exclusive=True)
        self.assertEqual(result.status,'unknown_requires_reconciliation');self.assertEqual(len(self.writes),1)
        from hads_next.approved_tools import ApprovedRepairBroker
        restarted=ApprovedRepairBroker(self.app)
        self.assertTrue(restarted.reconcile(plan.plan_id)['matches_proposed'])
        with self.assertRaises(RepairBlocked):restarted.decide(plan.plan_id,'approve','owner-fixture',exclusive=True)
        self.assertEqual(len(self.writes),1)
    def test_restore_attestation_signature_target_and_expiry_cannot_be_checkbox(self):
        with self.assertRaises(ToolDenied):self.app.approved_tools.backups.verify('x')
        self.receipt({'fixture':'old'})
        with self.assertRaises(ToolDenied):self.app.approved_tools.backups.verify('not-the-target')
        self.now+=3601
        with self.assertRaises(ToolDenied):self.app.approved_tools.backups.verify(fingerprint({'fixture':'old'}))
    def test_spook_entity_enable_is_separately_approved_and_functionally_verified(self):
        self.app.tools.registry.provider('spook',connected=True,catalog_loaded=True,version='fixture-contract-1');self.app.tools._services()
        incident=self.app.store.open_incident('manual_functional','Kontakt neaktualizuje stav',[self.entry['entity_id']],self.now)
        self.app.store.add_evidence(incident['id'],{'source':'native_entity_context','kind':'entity_context','event_id':'disabled-fixture','observed_at':self.now,'payload':{'entity_id':self.entry['entity_id'],'disabled_by':'user'}})
        ids=[e['evidence_id'] for e in self.app.store.case(incident['id'])['evidence']];self.receipt(self.entry)
        plan=self.app.approved_tools.prepare(incident['id'],'spook','homeassistant.enable_entity',{'entity_id':self.entry['entity_id']},ids,'Vlastník schvaluje povolení tohoto konkrétního kontaktu',exclusive=True)
        self.app.approved_tools.decide(plan.plan_id,'approve','owner-fixture',exclusive=True)
        self.assertIsNone(self.entry['disabled_by']);self.assertEqual(len(self.writes),1)
        self.now+=31;self.app.detection.health.update(state='listening',heartbeat_at=self.now,continuous_since=self.now-30)
        self.assertNotEqual(self.app.approved_tools.verify(plan.plan_id)['classification'],'Vyřešeno a ověřeno')
        self.assertEqual(self.app.approved_tools.confirm_physical(plan.plan_id,'owner-fixture')['classification'],'Vyřešeno a ověřeno')
    def test_disable_is_not_a_repair_and_forged_rollback_cannot_bypass_identity(self):
        self.app.tools.registry.provider('spook',connected=True,catalog_loaded=True,version='fixture-contract-1');self.app.tools._services()
        with self.assertRaises(RepairBlocked):
            self.app.approved_tools.prepare(self.case['id'],'spook','homeassistant.disable_entity',{'entity_id':self.old},self.evidence,'Nesmí skrýt závadu',exclusive=True)
        plan=self.prepare()
        with self.assertRaises(RepairBlocked):
            self.app.approved_tools.prepare(self.case['id'],'ha_mcp','ha_config_set_automation',plan.document['parameters'],self.evidence,'Falešný návrat',exclusive=True,rollback_of='not-a-plan')
        self.assertEqual(self.writes,[])

    def test_C_E_shared_DNS_correlation_and_H_AI_unavailable_keep_evidence_without_cost(self):
        self.app.orchestration.correlate([{'source':'core','component':'resolver','observed_at':self.now-20,'message':'DNS name resolution failed'},
            {'source':'application','component':'radio','observed_at':self.now-15,'message':'Cannot connect to provider'},
            {'source':'core','component':'weather','observed_at':self.now-10,'message':'connection refused'}])
        groups=self.app.orchestration.correlate([]);self.assertEqual(len(groups),1);self.assertEqual(len(groups[0]['components']),3);self.assertFalse(groups[0]['root_cause_proven']);self.assertEqual(len([c for c in self.app.snapshot()['cases'] if c['kind']=='network_correlation']),1)
        self.app.orchestration.cycle();self.assertFalse(self.app.investigations.status()['provider']['enabled'] if 'provider' in self.app.investigations.status() else False)
        self.assertTrue(self.app.store.case(self.case['id'])['evidence']);self.assertEqual(self.writes,[])
    def test_upstream_best_practice_receipt_is_read_bound_and_not_disabled(self):
        plan=self.prepare();self.assertEqual(plan.document['parameters']['BestPracticeKey'],self.guide_ack)
        self.assertIsNotNone(plan.document['guide_receipt'])
        self.guide_ack='I-HAVE-READ-THE-BEST-PRACTICES-GUIDE-abcd1234'
        with self.assertRaises(RepairBlocked):self.app.approved_tools.decide(plan.plan_id,'approve','owner-fixture',exclusive=True)
        self.assertEqual(self.writes,[])
        self.assertFalse(any(c.get('params',{}).get('arguments',{}).get('MandatoryBPS') is False for c in self.calls))

    def test_real_runtime_catalog_stays_within_unchanged_launcher_limit(self):
        from hads_next.investigator_roles import RoleBroker
        role=RoleBroker(self.app.investigations.broker,'fixture-job',self.case['id'])
        self.assertLessEqual(len(role.schemas()),32)
        names={r['name'] for r in role.schemas()}
        self.assertTrue({'hads_list_tools','hads_diagnostic_tool','hads_get_tool_schema','hads_propose_tool_repair'}<=names)

    def test_application_wires_report_discovery_and_collects_without_a_model(self):
        app=self.app
        app.tools.connections.clients['automation_inspector']=ReportHTTP(self.url,allow_private_http=True)
        app.tools.connections.clients['hadocs']=ReportHTTP(self.url,allow_private_http=True)
        def core(path):
            if path=='/api/config':return {'version':'2026.11.1','components':[]}
            if path=='/api/states':return []
            return self.core(path)
        def ws(command):
            if command['type'] in {'config/entity_registry/list','config/device_registry/list','system_log/list'}:return []
            if command['type']=='repairs/list_issues':return {'issues':[]}
            if command['type']=='system_health/info':return {'domains':{},'complete':True}
            return self.ws(command)
        app.core=CoreReader(core);app.core_ws=CoreWSReader(ws)
        app.investigations.broker.core=app.core;app.investigations.broker.ws=app.core_ws
        app.check_sources()
        providers={r['id']:r for r in app.tools.registry.providers()}
        self.assertTrue(providers['automation_inspector']['diagnostic_read_verified'])
        self.assertTrue(providers['hadocs']['diagnostic_read_verified'])
        self.assertTrue(any(e['source']=='automation_inspector' for e in app.store.case(self.case['id'])['evidence']))
        self.assertEqual(self.writes,[])

    def test_old_HADocs_report_survives_process_restart_without_claiming_a_new_scan(self):
        from hads_next.provider_reports import hadocs,sensor_report
        value=hadocs({'available':True,'health':{'health_score':97},'incidents':[],'recommendations':[]},
                     {'version':'0.17.0-rc5','running':False,'exit_code':None,'finished_at':None,'report_available':True})
        self.assertIsNone(value['generated_at']);self.assertFalse(value['freshness_verified'])
        report=sensor_report('entity_availability',[{'entity_id':'sensor.availability','platform':'entity_availability'}],
            [{'entity_id':'sensor.availability','state':'99.8','last_updated':self.iso(self.now),'attributes':{'per_device':{'binary_sensor.fixture_contact':99.8},'offline_entities':['binary_sensor.fixture_contact'],'count':1}}])
        attrs=report['sensors'][0]['attributes']
        self.assertEqual(attrs['per_device']['binary_sensor.fixture_contact'],99.8)
        self.assertEqual(attrs['offline_entities'],['binary_sensor.fixture_contact'])

    def test_private_connection_identity_never_reaches_public_setup_or_catalog(self):
        html=settings(self.app,'fixture-csrf');self.assertNotIn('fixture-only-token',html);self.assertNotIn(self.url,html)
        raw=canonical(self.app.tools.list_read(self.case['id'],{}));self.assertNotIn('fixture-only-token',raw);self.assertNotIn(self.url,raw)

if __name__=='__main__':unittest.main()
