"""Initial setup update of HADS only, not a diagnostic action or HA repair."""
import importlib.util,json,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('upgrade3',ROOT/'scripts/upgrade_rc5.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)

class UpgradeRC5Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.apps=self.root/'apps';self.apps.mkdir();self.old=self.apps/'hads_next_practical';self.new=self.root/'new';self.calls=[];self.version='1.0.0-rc5';self.latest=self.version;self.state='started';self.fail=False
        for path,version in [(self.old,self.version),(self.new,u.VERSION)]:
            path.mkdir();files={'config.yaml':('version: '+version+'\n').encode(),**{'source'+str(i)+'.py':b'unchanged' for i in range(20)}}
            for name,data in files.items():(path/name).write_bytes(data)
            manifest={'version':version,'slug':'hads_next_practical','files':{n:{'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()} for n,d in files.items()}}
            (path/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest))
        p=patch.object(u,'RC5_MANIFEST',u.digest((self.old/'PACKAGE_MANIFEST.json').read_bytes()));p.start();self.addCleanup(p.stop)
    def cli(self,args):
        self.calls.append(args)
        if args==['store','reload']:self.latest=u.VERSION;return {}
        if args[-1]=='--help':return None
        if args[1]=='info':return {'version':self.version,'version_latest':self.latest,'state':self.state}
        if args[1]=='update':
            self.assertIn('--backup',args)
            if self.fail:raise u.UpgradeBlocked('Unknown native update result')
            self.version=u.VERSION;return {}
        if args[1]=='start':self.state='started';return {}
        raise AssertionError(args)
    def test_running_app_updates_itself_through_native_backup_without_manual_stop(self):
        data=self.root/'data';data.mkdir();(data/'incidents.sqlite').write_bytes(b'keep fixture data')
        receipt=u.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(self.version,u.VERSION);self.assertEqual(receipt['state'],'started')
        self.assertTrue(Path(receipt['source_backup']).is_file());self.assertEqual((data/'incidents.sqlite').read_bytes(),b'keep fixture data')
        self.assertFalse(any(a[1] in {'stop','uninstall','restart'} for a in self.calls))
        self.assertEqual(sum('--backup' in a for a in self.calls),1)
    def test_stopped_is_preserved_but_error_is_not_assumed_stopped(self):
        self.state='error'
        with self.assertRaises(u.UpgradeBlocked):u.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(self.version,'1.0.0-rc5');self.assertFalse(list(self.apps.glob('*.tar.gz')))
        self.state='stopped';u.upgrade(self.apps,'apps',self.new,self.cli);self.assertEqual(self.state,'stopped')
    def test_uncertain_update_has_preserved_sources_and_no_automatic_replay(self):
        self.fail=True
        with self.assertRaises(u.UpgradeBlocked):u.upgrade(self.apps,'apps',self.new,self.cli)
        count=len(self.calls);self.assertTrue((self.apps/'.hads-next-upgrade-pending.json').exists())
        with self.assertRaises(u.UpgradeBlocked):u.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(len(self.calls),count)
    def test_owner_source_changes_and_pending_recovery_are_not_overwritten(self):
        (self.apps/'.hads-next-recovery-pending.json').write_text('previous interrupted setup')
        with self.assertRaises(u.UpgradeBlocked):u.upgrade(self.apps,'apps',self.new,self.cli)
        self.assertEqual(self.calls,[])
