import datetime as dt
from contextlib import closing
import io
import json
import sqlite3
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import hads4
import incident_workflow
from repair_engine import RepairEngine, RepairError, canonical_json_hash, sha256_bytes
from tool_adapters import ToolAdapterBus
import test_rc8_regressions as legacy


class Workflow430Tests(unittest.TestCase):
    setUp = legacy.RC8RegressionTests.setUp
    tearDown = legacy.RC8RegressionTests.tearDown
    _case_and_plan = legacy.RC8RegressionTests._case_and_plan

    def engine(self, config=None, transport=None):
        root = self.test_root / 'config'
        root.mkdir(exist_ok=True)
        self.cfg = {'repair_mode_open': True, **(config or {})}
        return RepairEngine(transport or mock.Mock(return_value={}), lambda: root, self.test_root / 'private', lambda: self.cfg)

    def no_plan_root(self):
        case, plan, root = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("DELETE FROM repair_plans WHERE id=?", (plan,))
            conn.execute("UPDATE root_cases SET repair_plan_id=NULL,decision_state='investigating' WHERE id=?", (root,))
        return root

    def planner(self, root, research=None):
        bus = mock.Mock()
        bus.collect.return_value = {'used': [], 'evidence': []}
        return hads4.first_officer().automatic_repair_planner(mock.Mock(), mock.Mock(return_value={'id':999}), research or mock.Mock(return_value={'summary':'Pouze hypotéza'}), bus, root_ids=[root])

    def test_accept_persists_after_real_rebuild_and_planner(self):
        root = self.no_plan_root()
        hads4.first_officer().decide(root, 'accept_analysis', 'Sleduji')
        hads4.first_officer().rebuild_root_cases()
        self.assertEqual(0, self.planner(root)['processed'])
        self.assertEqual('watching', hads4.first_officer().root_case(root)['decision_state'])

    def test_rejection_persists_after_restart_rebuild_and_planner(self):
        root = self.no_plan_root()
        hads4.first_officer().decide(root, 'reject', 'Nesouhlasím s návrhem')
        hads4.init_db()
        hads4.first_officer().rebuild_root_cases()
        self.assertEqual(0, self.planner(root)['processed'])
        self.assertEqual('rejected', hads4.first_officer().root_case(root)['decision_state'])

    def test_ignore_cancels_approval_but_retains_evidence(self):
        _, plan, root = self._case_and_plan()
        hads4.first_officer().decide(root, 'approve')
        hads4.first_officer().decide(root, 'ignore', 'Známý problém bez dopadu')
        hads4.first_officer().rebuild_root_cases()
        self.assertEqual('ignored', hads4.first_officer().root_case(root)['decision_state'])
        self.assertEqual(0, hads4.first_officer().command_center()['approved_plans'])
        self.assertTrue(hads4.first_officer().root_case(root)['evidence'])

    def test_reinvestigate_reopens_ignored_case(self):
        root = self.no_plan_root()
        officer = hads4.first_officer()
        officer.decide(root, 'ignore', 'Známé')
        officer.decide(root, 'reinvestigate', 'Nová informace')
        self.assertEqual(1, self.planner(root)['processed'])

    def test_priority_alone_is_not_a_verified_conclusion(self):
        root = self.no_plan_root()
        with hads4.db() as conn:
            conn.execute("UPDATE root_cases SET priority='P1',confidence=99 WHERE id=?", (root,))
        self.assertEqual('investigating', self.planner(root)['results'][0]['status'])

    def test_decision_changed_during_research_is_not_overwritten(self):
        root = self.no_plan_root()
        def research(*args):
            hads4.first_officer().decide(root, 'ignore', 'Během výzkumu')
            return {'summary':'Závěr', 'conclusion_verified':True}
        self.planner(root, research)
        self.assertEqual('ignored', hads4.first_officer().root_case(root)['decision_state'])

    def test_approval_survives_restart_and_rebuild(self):
        _, _, root = self._case_and_plan()
        hads4.first_officer_decide(root, {'decision':'approve'})
        hads4.init_db()
        hads4.first_officer().rebuild_root_cases()
        self.assertEqual(1, hads4.first_officer_command_center()['approved_plans'])
        self.assertTrue(hads4.first_officer_command_center()['batch_checklist']['runnable'])

    def test_running_plan_recovery_never_auto_replays(self):
        _, plan, _ = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("UPDATE repair_plans SET status='running' WHERE id=?", (plan,))
        batch = hads4.first_officer().create_batch([plan], {})
        hads4.first_officer().update_batch(batch, status='running')
        hads4.init_db()
        self.assertEqual('interrupted', hads4.first_officer().batch(batch)['status'])
        self.assertEqual('interrupted', hads4.repair_plan_detail(plan)['status'])
        self.assertEqual('locked', hads4.get_setting('repair_write_gate'))

    def test_cannot_accept_conclusion_for_approved_repair(self):
        _, _, root = self._case_and_plan()
        hads4.first_officer().decide(root, 'approve')
        with self.assertRaises(ValueError):
            hads4.first_officer().decide(root, 'accept_analysis')
        self.assertEqual(1, hads4.first_officer().command_center()['approved_plans'])

    def test_unknown_action_cannot_be_approved_or_counted(self):
        _, plan, root = self._case_and_plan()
        with hads4.db() as conn:
            conn.execute("UPDATE repair_plans SET actions_json=? WHERE id=?", (json.dumps([{'type':'shell','cmd':'echo unsafe'}]), plan))
        with self.assertRaises(ValueError):
            hads4.first_officer().decide(root, 'approve')

    def test_full_backup_required_even_if_legacy_bypass_enabled(self):
        transport=mock.Mock(side_effect=RuntimeError('backup failed'))
        engine=self.engine({'backup_before_repairs':False,'allow_repair_without_backup':True},transport)
        with mock.patch('repair_engine.os.chmod'), self.assertRaises(RepairError):
            engine.execute(1,[{'type':'addon_restart','addon':'test'}])
        self.assertEqual('/backups/new/full',transport.call_args_list[0].args[0])
        self.assertEqual(1,transport.call_count)

    def test_gate_cannot_be_bypassed_by_disabling_first_officer(self):
        engine=self.engine({'repair_mode_open':False,'first_officer_enabled':False})
        with mock.patch('repair_engine.os.chmod'), self.assertRaises(RepairError):
            engine.execute(1,[{'type':'addon_restart','addon':'test'}])
        engine.supervisor_request.assert_not_called()

    def test_unverified_backup_rejects_missing_slug(self):
        engine=self.engine(transport=mock.Mock(return_value={'job_id':'still-running'}))
        with self.assertRaises(RepairError): engine._create_backup(1,[])

    def test_unverified_backup_rejects_excluded_database(self):
        engine=self.engine()
        def transport(path,**kw):
            if path=='/backups/new/full':
                self.backup_name=kw['body']['name'];return {'slug':'abc'}
            return {'slug':'abc','name':self.backup_name,'type':'full','size':12,'homeassistant':'2026.8','homeassistant_exclude_database':True}
        engine.supervisor_request=transport
        with self.assertRaises(RepairError): engine._create_backup(1,[])

    def test_unverified_backup_rejects_missing_affected_addon(self):
        engine=self.engine()
        def transport(path,**kw):
            if path=='/backups/new/full': self.backup_name=kw['body']['name'];return {'slug':'abc'}
            return {'slug':'abc','name':self.backup_name,'type':'full','size':12,'homeassistant':'2026.8','homeassistant_exclude_database':False,'addons':[]}
        engine.supervisor_request=transport
        with self.assertRaises(RepairError): engine._create_backup(1,[{'type':'addon_restart','addon':'wanted'}])

    def test_valid_backup_is_independently_checked_before_write(self):
        calls=[]
        def transport(path,method='GET',body=None,**kw):
            calls.append((method,path))
            if path=='/backups/new/full':self.backup_name=body['name'];return {'slug':'abc'}
            if path=='/backups/abc/info':return {'slug':'abc','name':self.backup_name,'type':'full','size':12,'homeassistant':'2026.8','homeassistant_exclude_database':False,'addons':[{'slug':'test'}]}
            if path=='/addons/test/restart':return {}
            raise AssertionError(path)
        engine=self.engine(transport=transport)
        with mock.patch('repair_engine.os.chmod'):
            result=engine.execute(1,[{'type':'addon_restart','addon':'test'}])
        self.assertEqual([('POST','/backups/new/full'),('GET','/backups/abc/info'),('POST','/addons/test/restart')],calls)
        self.assertTrue(result['verification_pending'])

    def test_stale_config_read_cannot_fall_back_to_cache(self):
        key='json:/core/api/config/automation/config/a'
        hads4.supervisor_read_cache[key]=({'alias':'old'},hads4.now_utc())
        with mock.patch('hads4.time.sleep'), self.assertRaises(RuntimeError):
            hads4.supervisor_request('/core/api/config/automation/config/a')

    def test_permission_denial_never_uses_cache_even_when_requested(self):
        hads4.supervisor_read_cache['json:/core/info']=({'old':True},hads4.now_utc())
        error=urllib.error.HTTPError('http://supervisor',401,'no',{},io.BytesIO(b'no'))
        with mock.patch('hads4.urllib.request.urlopen',side_effect=error), self.assertRaises(RuntimeError):
            hads4.supervisor_request('/core/info',allow_stale=True)

    def test_changed_yaml_cannot_be_silently_rebased_after_approval(self):
        engine=self.engine();target=engine.config_root()/'a.yaml';target.write_text('key: before\nother: original\n',encoding='utf-8')
        actions=engine.normalize_actions([{'type':'yaml_replace','path':'a.yaml','before':'key: before','after':'key: after'}])
        target.write_text('key: before\nother: USER EDIT\n',encoding='utf-8')
        with mock.patch.object(hads4,'config_root',engine.config_root):
            result=hads4.first_officer().plan_batch([{'id':1,'actions':actions}])
        self.assertTrue(result['blocked']);self.assertEqual('stale_approval',result['conflicts'][0]['type'])

    def test_yaml_rollback_refuses_newer_user_edit(self):
        engine=self.engine();target=engine.config_root()/'a.yaml';target.write_text('key: before',encoding='utf-8')
        actions=[{'type':'yaml_replace','path':'a.yaml','before':'key: before','after':'key: after'}]
        with mock.patch('repair_engine.os.chmod'),mock.patch.object(engine,'_create_backup',return_value={'slug':'verified'}):
            engine.execute(1,actions)
            target.write_text('key: NEW USER VALUE',encoding='utf-8')
            result=engine.rollback(1)
        self.assertFalse(result['ok']);self.assertEqual('key: NEW USER VALUE',target.read_text())

    def test_yaml_paths_cannot_escape_config(self):
        engine=self.engine()
        for path in ('../a.yaml','/etc/a.yaml','C:/a.yaml','secrets.yaml'):
            with self.subTest(path=path), self.assertRaises((RepairError,ValueError)):
                engine._safe_config_file(path)

    def test_recorder_requires_explicit_active_sqlite_configuration(self):
        engine=self.engine()
        with self.assertRaises(RepairError):engine.normalize_actions([{'type':'recorder_purge','keep_days':30}])

    def recorder_engine(self):
        engine=self.engine({'recorder_maintenance_enabled':True,'recorder_sqlite_path':'home-assistant_v2.db'})
        with closing(sqlite3.connect(engine.config_root()/'home-assistant_v2.db')) as conn, conn:
            conn.executescript('CREATE TABLE states(id INTEGER); CREATE TABLE events(id INTEGER); INSERT INTO states VALUES(1);')
        return engine

    def test_recorder_backup_is_consistent_and_does_not_modify_source(self):
        engine=self.recorder_engine()
        with mock.patch('repair_engine.os.chmod'):
            snap=engine._snapshot_recorder(engine._private_dir(1))
        self.assertEqual('ok',snap['quick_check']);self.assertEqual(64,len(snap['sha256']))
        with closing(sqlite3.connect(snap['path'])) as conn:self.assertEqual(1,conn.execute('SELECT count(*) FROM states').fetchone()[0])

    def test_recorder_bad_retention_is_rejected(self):
        engine=self.recorder_engine()
        for days in (0,False,1.5,'30',3651):
            with self.subTest(days=days),self.assertRaises(RepairError):engine.normalize_actions([{'type':'recorder_purge','keep_days':days}])

    def test_recorder_runs_only_after_both_backups_and_never_retries_post(self):
        engine=self.recorder_engine();calls=[]
        def transport(path,method='GET',body=None,**kw):
            calls.append(path)
            if path=='/core/api/services':return [{'domain':'recorder','services':{'purge':{}}}]
            if path=='/core/api/services/recorder/purge':
                self.assertTrue((engine.private_root/'plan_000001'/'recorder-before.db').exists())
                self.assertEqual({'keep_days':30,'repack':False,'apply_filter':False},body);return []
            raise AssertionError(path)
        engine.supervisor_request=transport
        with mock.patch('repair_engine.os.chmod'),mock.patch.object(engine,'_create_backup',return_value={'slug':'full'}) as backup:
            result=engine.execute(1,[{'type':'recorder_purge','keep_days':30}])
        backup.assert_called_once();self.assertEqual(1,calls.count('/core/api/services/recorder/purge'));self.assertTrue(result['verification_pending'])
        with mock.patch('repair_engine.os.chmod'):self.assertFalse(engine.rollback(1)['ok'])

    def test_recorder_is_exclusive_batch(self):
        result=hads4.first_officer().plan_batch([{'id':1,'actions':[{'type':'recorder_purge','keep_days':30}]},{'id':2,'actions':[{'type':'addon_restart','addon':'test'}]}])
        self.assertTrue(result['blocked'])

    def test_update_entity_does_not_prove_codex_connection_or_running(self):
        def supervisor(path,**kw):
            if path=='/core/api/states':return [{'entity_id':'update.codex_terminal_pro_aktualizace','state':'unavailable','attributes':{}}]
            return {}
        bus=ToolAdapterBus(hads4.db,hads4.now_utc,supervisor,lambda _:[],lambda:None)
        with mock.patch.object(bus,'_auto_mcp_urls',return_value={}),mock.patch.object(bus,'_auto_json_connector',return_value=(None,'')):
            row=bus.refresh()['adapters']['codex_terminal_pro']
        self.assertFalse(row['installed']);self.assertFalse(row['connection_verified']);self.assertIsNone(row['running']);self.assertIsNone(row['last_success_at'])

    def test_json_stale_response_cannot_mark_connector_connected(self):
        bus=ToolAdapterBus(hads4.db,hads4.now_utc,lambda *a,**k:{},lambda _:[],lambda:None)
        with mock.patch.object(bus,'_http_json',return_value=({'issues':[]},{'x-hads-stale':'true'})),self.assertRaises(RuntimeError):bus._json_connector('http://example.invalid')

    def test_adapter_snapshot_expires(self):
        bus=ToolAdapterBus(hads4.db,hads4.now_utc,lambda *a,**k:{},lambda _:[],lambda:None)
        with mock.patch.object(bus,'_auto_mcp_urls',return_value={}),mock.patch.object(bus,'_auto_json_connector',return_value=(None,'')) as read:
            bus.refresh();n=read.call_count;bus.refresh();self.assertEqual(n,read.call_count)
            bus._last_refresh_monotonic-=121;bus.refresh();self.assertGreater(read.call_count,n)

    def test_chat_history_persists_and_jobs_recover_after_restart(self):
        root=self.no_plan_root();body='Přejmenování telefonu — potřebuji vysvětlení.'
        incident_workflow.start_job(hads4.db,hads4.now_utc,root,body,'chat')
        hads4.init_db()
        context=incident_workflow.context(hads4.db,root)
        self.assertEqual(body,context['messages'][0]['body']);self.assertEqual('interrupted',context['job']['status'])

    def test_duplicate_chat_job_does_not_send_twice(self):
        root=self.no_plan_root();incident_workflow.start_job(hads4.db,hads4.now_utc,root,'Otázka','chat')
        with self.assertRaises(sqlite3.IntegrityError):incident_workflow.start_job(hads4.db,hads4.now_utc,root,'Otázka','chat')
        self.assertEqual(1,len(incident_workflow.context(hads4.db,root)['messages']))

    def test_ai_limits_and_actual_usage_are_persisted(self):
        case,_,_=self._case_and_plan()
        send=mock.Mock(return_value={'status':'completed','id':'fake','usage':{'input_tokens':120,'output_tokens':40,'output_tokens_details':{'reasoning_tokens':15}},'output':[]})
        cfg={'ai_daily_call_limit':1,'ai_max_output_tokens':700}
        incident_workflow.metered_call(hads4.db,hads4.now_utc,cfg,case,'fake',{'model':'test','input':'hello'},send)
        self.assertEqual(700,send.call_args.args[1]['max_output_tokens'])
        with self.assertRaises(ValueError):incident_workflow.metered_call(hads4.db,hads4.now_utc,cfg,case,'fake',{'model':'test'},send)
        with hads4.db() as conn:self.assertEqual(120,conn.execute('SELECT input_tokens FROM ai_calls').fetchone()[0])
        self.assertEqual(1,send.call_count)

    def test_ai_input_cap_prevents_network_call(self):
        send=mock.Mock()
        with self.assertRaises(ValueError):incident_workflow.metered_call(hads4.db,hads4.now_utc,{},1,'fake',{'input':'x'*65000},send)
        send.assert_not_called()

    def test_ai_incomplete_output_is_not_an_executable_plan(self):
        send=mock.Mock(return_value={'status':'incomplete','usage':{'input_tokens':1,'output_tokens':512}})
        with self.assertRaises(ValueError):incident_workflow.metered_call(hads4.db,hads4.now_utc,{},1,'fake',{'input':'x'},send)

    def test_failed_ai_call_consumes_slot_with_unknown_billing(self):
        send=mock.Mock(side_effect=TimeoutError('unknown remote outcome'))
        with self.assertRaises(TimeoutError):incident_workflow.metered_call(hads4.db,hads4.now_utc,{'ai_daily_call_limit':1},1,'fake',{},send)
        with self.assertRaises(ValueError):incident_workflow.metered_call(hads4.db,hads4.now_utc,{'ai_daily_call_limit':1},1,'fake',{},send)
        self.assertEqual(1,send.call_count)

    def test_ignore_survives_resolution_and_recurrence(self):
        case, _, root = self._case_and_plan()
        hads4.first_officer().decide(root, 'ignore', 'Známý trvalý šum')
        with hads4.db() as conn:conn.execute("UPDATE cases SET status='resolved' WHERE id=?",(case,))
        hads4.first_officer().rebuild_root_cases()
        self.assertEqual('resolved',hads4.first_officer().root_case(root)['decision_state'])
        with hads4.db() as conn:conn.execute("UPDATE cases SET status='new' WHERE id=?",(case,))
        hads4.first_officer().rebuild_root_cases()
        self.assertEqual('ignored',hads4.first_officer().root_case(root)['decision_state'])

    def test_duplicate_choice_does_not_change_approval(self):
        _, _, root = self._case_and_plan()
        hads4.first_officer().decide(root, 'approve')
        incident_workflow.start_job(hads4.db,hads4.now_utc,root,'Již běží','chat')
        with self.assertRaises(sqlite3.IntegrityError):hads4.submit_root_choice(root,{'owner':'automation.arrival','old_value':'notify.old','new_value':'notify.new'})
        self.assertEqual('approved',hads4.first_officer().root_case(root)['decision_state'])
        with hads4.db() as conn:self.assertEqual(0,conn.execute('SELECT count(*) FROM root_choices').fetchone()[0])

    def test_owner_choice_resolves_ambiguous_phone_reference(self):
        case, _, root = self._case_and_plan()
        with hads4.db() as conn:conn.execute('INSERT INTO root_choices VALUES(?,?,?,?,?)',(root,'automation.arrival','notify.mobile_app_old','notify.mobile_app_phone_b',hads4.now_utc()))
        before={'alias':'Arrival','action':[{'service':'notify.mobile_app_old'}]}
        def transport(path,**kw):
            if path=='/core/api/states':return [{'entity_id':'automation.arrival','state':'on','attributes':{'id':'arrival'}}]
            if path=='/core/api/services':return [{'domain':'notify','services':{'mobile_app_phone_a':{},'mobile_app_phone_b':{}}}]
            if path.endswith('/automation/config/arrival'):return before
            raise AssertionError(path)
        evidence={'evidence':[{'payload':{'findings':[{'evidence':{'issue':{'automation_id':'arrival','message':'automation.arrival uses notify.mobile_app_old'}}}]}}]}
        with mock.patch.object(hads4,'supervisor_request',side_effect=transport),mock.patch.object(hads4,'ha_ws_read',return_value=[]):
            result=hads4.derive_verified_repair_actions(case,evidence)
            self.assertEqual('notify.mobile_app_phone_b',result['repair_actions'][0]['after']['action'][0]['service'])
            with hads4.db() as conn:conn.execute("UPDATE root_choices SET new_value='notify.does_not_exist'")
            result=hads4.derive_verified_repair_actions(case,evidence)
            self.assertEqual([],result['repair_actions'])

    def test_duplicate_object_updates_in_one_plan_are_blocked(self):
        result=hads4.first_officer().plan_batch([{'id':1,'actions':[{'type':'automation_update','automation_id':'arrival'},{'type':'automation_update','automation_id':'arrival'}]}])
        self.assertTrue(result['blocked'])
        self.assertEqual('duplicate_target',result['conflicts'][0]['type'])

    def test_health_only_http_response_is_not_diagnostic_connection(self):
        bus=ToolAdapterBus(hads4.db,hads4.now_utc,lambda *a,**k:{},lambda _:[],lambda:None)
        with mock.patch.object(bus,'_json_connector',return_value={'status':'healthy'}):
            value,error=bus._auto_json_connector('hadocs','http://example.invalid/api','')
        self.assertIsNone(value)
        self.assertTrue(error)

    def test_post_batch_watching_is_not_false_resolution(self):
        _, plan, root=self._case_and_plan()
        hads4.first_officer().decide(root,'approve')
        engine=mock.Mock()
        engine.execute.return_value={'ok':True,'backup':{'slug':'test'},'verification_pending':True}
        with mock.patch('first_officer.FirstOfficer.prepare_rescue',return_value={'path':'synthetic.zip','sha256':'test'}),mock.patch.object(hads4,'upload_and_verify_rescue',return_value={'verified':True}),mock.patch.object(hads4,'repair_engine',return_value=engine),mock.patch.object(hads4,'run_deep_audit',return_value={'ok':True}):
            result=hads4.execute_approved_batch_sync()
        self.assertEqual('monitoring',result['status'])
        self.assertEqual([],result['after']['comparison']['resolved'])
        self.assertEqual(1,len(result['after']['comparison']['persistent']))
        self.assertEqual('verifying',hads4.first_officer().root_case(root)['decision_state'])
        self.assertEqual('locked',hads4.get_setting('repair_write_gate'))

    def test_failed_snapshot_retains_full_backup_receipt_without_write(self):
        engine=self.recorder_engine()
        with mock.patch('repair_engine.os.chmod'),mock.patch.object(engine,'_create_backup',return_value={'slug':'preserved-backup'}),mock.patch.object(engine,'_snapshot_recorder',side_effect=RepairError('Disk full')):
            with self.assertRaises(RepairError):engine.execute(5,[{'type':'recorder_purge','keep_days':30}])
        self.assertEqual('preserved-backup',engine.recovery_receipt(5)['backup']['slug'])
        engine.supervisor_request.assert_not_called()


if __name__=='__main__':unittest.main()
