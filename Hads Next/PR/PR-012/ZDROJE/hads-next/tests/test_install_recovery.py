"""Owner-reported stop/error -> uninstall -> orphaned sources; no live HAOS."""
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery',ROOT/'scripts/recover_rc3.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.apps=self.root/'apps';self.apps.mkdir();self.target=self.apps/'hads_next_practical';self.target.mkdir();self.installer=self.root/'installer.sh';self.installer.write_bytes(b'isolated test fixture')
        contents={'config.yaml':b'version: 1.0.0-rc2\n',**{'module'+str(i)+'.py':b'original-source' for i in range(20)}}
        for name,data in contents.items():(self.target/name).write_bytes(data)
        manifest={'version':'1.0.0-rc2','slug':'hads_next_practical','files':{n:{'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()} for n,d in contents.items()}}
        (self.target/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest))
        for patcher in [patch.object(r,'SOURCE_MANIFESTS',{'1.0.0-rc2':r.sha((self.target/'PACKAGE_MANIFEST.json').read_bytes())}),patch.object(r,'INSTALLER_SHA256',r.sha(self.installer.read_bytes()))]:patcher.start();self.addCleanup(patcher.stop)
        self.current=None;self.reads=0;self.runs=0
        self.data=self.root/'data';self.data.mkdir();(self.data/'keep').write_text('remaining app data')
        self.other=self.apps/'unrelated';self.other.mkdir();(self.other/'config.yaml').write_text('unrelated app')
    def cli(self,args):
        self.assertEqual(args,['apps','--raw-json']);self.reads+=1
        return {'addons':([self.current] if self.current else [])+[{'slug':'unrelated','state':'started'}]}
    def install(self,installer):
        self.assertEqual(installer,self.installer);self.runs+=1
        self.target.mkdir();(self.target/'config.yaml').write_text('version: 1.0.0-rc3\n')
        self.current={'slug':r.SLUG,'version':'1.0.0-rc3','state':'started'};return 0
    def test_error_while_still_installed_is_not_treated_as_uninstalled(self):
        self.current={'slug':r.SLUG,'version':'1.0.0-rc2','state':'error'}
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,self.cli,self.install)
        self.assertTrue((self.target/'config.yaml').exists());self.assertEqual(self.runs,0)
        self.assertEqual(set(p.name for p in self.apps.iterdir()),{'hads_next_practical','unrelated'})
    def test_uninstalled_orphan_is_archived_preserved_and_reinstalled(self):
        before=(self.target/'config.yaml').read_bytes()
        receipt=r.recover(self.apps,'apps',self.installer,self.cli,self.install)
        self.assertEqual(self.runs,1);self.assertEqual(receipt['phase'],'installed_RC3_verified')
        preserved=Path(receipt['preserved_source_directory']);self.assertEqual((preserved/'config.yaml.source-backup').read_bytes(),before)
        self.assertFalse((preserved/'config.yaml').exists());self.assertTrue(Path(receipt['source_backup']).is_file())
        self.assertEqual((self.data/'keep').read_text(),'remaining app data');self.assertEqual((self.other/'config.yaml').read_text(),'unrelated app')
        self.assertFalse((self.apps/'.hads-next-recovery-pending.json').exists())
    def test_inspection_is_read_only(self):
        before=sorted(str(p.relative_to(self.apps)) for p in self.apps.rglob('*'))
        value=r.inspect(self.apps,'apps',self.cli)
        self.assertIsNone(value['installed_app']);self.assertEqual(value['verified_source_version'],'1.0.0-rc2')
        self.assertEqual(before,sorted(str(p.relative_to(self.apps)) for p in self.apps.rglob('*')))
    def test_custom_source_extra_file_is_never_moved(self):
        (self.target/'owner-change.txt').write_text('keep')
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,self.cli,self.install)
        self.assertEqual((self.target/'owner-change.txt').read_text(),'keep');self.assertEqual(self.runs,0)
    def test_wrong_or_old_installer_is_rejected_before_HA_or_sources(self):
        self.installer.write_text('other installer')
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,self.cli,self.install)
        self.assertEqual(self.reads,0);self.assertTrue((self.target/'config.yaml').exists())
    def test_unknown_previous_operation_is_not_bypassed(self):
        (self.apps/'.hads-next-upgrade-pending.json').write_text('old intent')
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,self.cli,self.install)
        self.assertEqual(self.runs,0);self.assertTrue((self.target/'config.yaml').exists())
    def test_failed_reinstallation_keeps_backup_and_blocks_blind_retry(self):
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,self.cli,lambda _:7)
        marker=self.apps/'.hads-next-recovery-pending.json';self.assertTrue(marker.exists())
        receipt=json.loads(marker.read_text());self.assertTrue(Path(receipt['source_backup']).exists())
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,self.cli,self.install)
        self.assertEqual(self.runs,0)
    def test_malformed_inventory_is_not_proof_of_uninstallation(self):
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,lambda _: {'unexpected':[]},self.install)
        self.assertTrue((self.target/'config.yaml').exists());self.assertEqual(self.runs,0)
    def test_installation_between_inventory_reads_blocks_source_move(self):
        def changed(args):
            if self.reads==2:self.current={'slug':r.SLUG,'state':'error','version':'1.0.0-rc2'}
            return self.cli(args)
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,changed,self.install)
        self.assertTrue((self.target/'config.yaml').exists());self.assertEqual(self.runs,0)
    def test_source_symlink_is_refused(self):
        (self.target/'module0.py').unlink();(self.target/'module0.py').symlink_to(self.installer)
        with self.assertRaises(r.RecoveryBlocked):r.recover(self.apps,'apps',self.installer,self.cli,self.install)
        self.assertEqual(self.runs,0)
