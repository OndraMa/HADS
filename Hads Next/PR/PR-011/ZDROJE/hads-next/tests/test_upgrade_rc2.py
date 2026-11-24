"""Stopped-app upgrade safety and failure recovery, fake HA CLI only."""
import importlib.util,json,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('upgrade',ROOT/'scripts/upgrade_rc2.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.apps=self.root/'apps';self.apps.mkdir();self.old=self.apps/'hads_next_practical';self.new=self.root/'new';self.calls=[];self.version='1.0.0-rc2';self.latest=self.version;self.state='stopped';self.fail_update=False
        def tree(path,version):
            path.mkdir();files={'config.yaml':('version: '+version+'\n').encode(),**{'source'+str(i)+'.py':b'code' for i in range(20)}}
            for name,data in files.items():(path/name).write_bytes(data)
            manifest={'version':version,'slug':'hads_next_practical','files':{n:{'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()} for n,d in files.items()}}
            (path/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest))
        tree(self.old,self.version);tree(self.new,module.VERSION)
        patcher=patch.object(module,'RC2_MANIFEST',module.digest((self.old/'PACKAGE_MANIFEST.json').read_bytes()));patcher.start();self.addCleanup(patcher.stop)
    def cli(self,args):
        self.calls.append(args)
        if args==['store','reload']:self.latest=module.VERSION;return {}
        if args[-1]=='--help':return None
        if args[1]=='info':return {'version':self.version,'version_latest':self.latest,'state':self.state}
        if args[1]=='update':
            if self.fail_update:raise module.UpgradeBlocked('Simulated unknown update outcome')
            self.assertIn('--backup',args);self.version=module.VERSION;return {}
        raise AssertionError(args)
    def test_exact_upgrade_preserves_data_and_remains_stopped(self):
        data=self.root/'data';data.mkdir();(data/'incidents.sqlite').write_bytes(b'untouched test sentinel')
        result=module.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(self.version,module.VERSION);self.assertEqual(self.state,'stopped');self.assertEqual((data/'incidents.sqlite').read_bytes(),b'untouched test sentinel')
        self.assertTrue(Path(result['source_backup']).is_file());self.assertFalse((self.apps/'.hads-next-upgrade-pending.json').exists())
        self.assertEqual(self.calls,[['apps','update','--help'],['apps','info',module.SLUG,'--raw-json'],['store','reload'],['apps','info',module.SLUG,'--raw-json'],['apps','update',module.SLUG,'--backup','--raw-json'],['apps','info',module.SLUG,'--raw-json']])
        old_count=len(self.calls)
        with self.assertRaises(module.UpgradeBlocked):module.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(old_count,len(self.calls))
    def test_running_or_error_state_is_not_assumed_stopped(self):
        for state in ('started','error'):
            self.state=state
            with self.assertRaises(module.UpgradeBlocked):module.upgrade(self.apps,'apps',self.new,self.cli)
            self.assertEqual((self.old/'config.yaml').read_text(),'version: 1.0.0-rc2\n')
            self.assertFalse(list(self.apps.glob('*.tar.gz')))
    def test_modified_original_or_additional_file_is_never_overwritten(self):
        (self.old/'custom.yaml').write_text('owner change')
        with self.assertRaises(module.UpgradeBlocked):module.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(self.calls,[]);self.assertEqual((self.old/'custom.yaml').read_text(),'owner change')
    def test_symlink_source_is_rejected_before_CLI(self):
        (self.old/'source0.py').unlink();(self.old/'source0.py').symlink_to(self.new/'source0.py')
        with self.assertRaises(module.UpgradeBlocked):module.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(self.calls,[])
    def test_uncertain_update_retains_marker_backup_and_no_replay(self):
        self.fail_update=True
        with self.assertRaises(module.UpgradeBlocked):module.upgrade(self.apps,'apps',self.new,self.cli)
        marker=self.apps/'.hads-next-upgrade-pending.json';self.assertTrue(marker.exists());self.assertTrue(Path(json.loads(marker.read_text())['source_backup']).is_file())
        count=len(self.calls)
        with self.assertRaises(module.UpgradeBlocked):module.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(count,len(self.calls))
    def test_store_version_mismatch_is_blocked_before_update(self):
        def cli(args):
            value=self.cli(args)
            if args[1]=='info' and self.latest==module.VERSION:value['version_latest']='unexpected'
            return value
        with self.assertRaises(module.UpgradeBlocked):module.upgrade(self.apps,'apps',self.new,cli)
        self.assertFalse(any(x[1]=='update' and '--backup' in x for x in self.calls))
