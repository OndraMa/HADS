"""Exercise real published source trees and the native update command boundary."""
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


class CandidateUpgradeTests(unittest.TestCase):
    def exercise(self,version,*,fail=False,modified=False):
        upgrade=module('candidate_upgrade',ROOT/'scripts/upgrade_next.py')
        builder=module('candidate_builder',ROOT/'scripts/build_haos_installer.py')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);apps=root/'apps';apps.mkdir();old=apps/'hads_next_practical';old.mkdir()
            release_folder = 'HADS_Next_'+version+('-kandidat' if version=='1.0.0-rc8' else '')
            published=ROOT.parent/'KE_STAZENI'/release_folder/('HADS_Next_'+version+'-source.tar.gz')
            with tarfile.open(published) as archive:archive.extractall(old,filter='data')
            built=builder.build_installer(root/'candidate');new=root/'new';new.mkdir()
            with tarfile.open(built['source_archive']) as archive:archive.extractall(new,filter='data')
            data=root/'app-data';data.mkdir();sentinel=data/'incidents-and-conversations';sentinel.write_bytes(b'owner history and decisions')
            state={'version':version,'latest':version,'state':'started'};calls=[]
            def call(args):
                calls.append(args)
                if args==['store','reload']:state['latest']=builder.VERSION;return {}
                if args[-1]=='--help':return None
                if args[1]=='info':return {'version':state['version'],'version_latest':state['latest'],'state':state['state']}
                if args[1]=='update':
                    self.assertNotIn('--backup',args)
                    if fail:raise upgrade.UpgradeBlocked('uncertain fixture update')
                    state['version']=builder.VERSION;return {}
                raise AssertionError(args)
            if modified:
                (old/'hads_next/haos_application.py').write_text('owner changes')
                with self.assertRaises(upgrade.UpgradeBlocked):upgrade.upgrade(apps,'apps',new,call)
                self.assertEqual(calls,[])
            elif fail:
                with self.assertRaises(upgrade.UpgradeBlocked):upgrade.upgrade(apps,'apps',new,call)
                before=len(calls)
                with self.assertRaises(upgrade.UpgradeBlocked):upgrade.upgrade(apps,'apps',new,call)
                self.assertEqual(before,len(calls));self.assertTrue((apps/'.hads-next-upgrade-pending.json').is_file())
            else:
                receipt=upgrade.upgrade(apps,'apps',new,call)
                self.assertEqual(receipt['from'],version);self.assertEqual(receipt['to'],builder.VERSION)
                self.assertEqual(receipt['installer_backup_policy'],'no_preinstall_HA_or_cloud_backup_user_requested')
                self.assertEqual(state['state'],'started');self.assertEqual(state['version'],builder.VERSION)
                self.assertEqual(sum(len(a)>1 and a[1]=='update' and a[-1]!='--help' for a in calls),1)
                self.assertFalse(any(len(a)>1 and a[1] in {'uninstall','stop','restore'} for a in calls))
            self.assertEqual(sentinel.read_bytes(),b'owner history and decisions')

    def test_published_versions_upgrade_same_identity_without_preinstall_backup(self):
        for version in ('1.0.0-rc6','1.0.0-rc7','1.0.0-rc8'):
            with self.subTest(version=version):self.exercise(version)

    def test_uncertain_native_update_is_not_replayed(self):self.exercise('1.0.0-rc7',fail=True)

    def test_user_modified_sources_are_never_overwritten(self):self.exercise('1.0.0-rc6',modified=True)
