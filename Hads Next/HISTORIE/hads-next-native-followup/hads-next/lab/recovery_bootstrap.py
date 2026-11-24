"""Black-box reproduction of the reported recovery sequence, isolated container."""
import hashlib,importlib.util,json,platform,subprocess,tarfile
from pathlib import Path

def execute(args):return subprocess.run(args,capture_output=True,text=True,timeout=45)
def state(installed,version='1.0.0-rc2',status='error'):Path('/tmp/recovery-ha.json').write_text(json.dumps({'installed':installed,'version':version,'state':status}))

base=Path('/addons');target=base/'hads_next_practical';target.mkdir()
with tarfile.open('/released-rc2.tar.gz') as archive:archive.extractall(target,filter='data')
Path('/data/keep').write_text('remaining data sentinel');Path('/config/keep').write_text('unrelated home configuration')
other=base/'unrelated';other.mkdir();(other/'config.yaml').write_text('unrelated app source')
old_manifest=(target/'PACKAGE_MANIFEST.json').read_bytes();old_config=(target/'config.yaml').read_bytes()
script=['python','/recover.py','--recover-and-install','/released-rc3.sh']
state(True)
refused=execute(script);assert refused.returncode!=0 and 'stále nainstalovaný' in refused.stdout+refused.stderr,refused
assert (target/'config.yaml').read_bytes()==old_config
assert not list(base.glob('.hads-next-recovery-sources-*'))
# This state transition represents the user's prior uninstall, not an action of
# the helper. Production uninstallation may already have removed private data.
state(False)
inspection=execute(['python','/recover.py','--inspect']);assert inspection.returncode==0;assert json.loads(inspection.stdout)['verified_source_version']=='1.0.0-rc2'
blocked=execute(['bash','/released-rc3.sh','--install-dev']);assert blocked.returncode!=0 and 'zdrojový adresář' in blocked.stdout+blocked.stderr
verified=execute(['bash','/released-rc3.sh','--verify']);assert verified.returncode==0
assert json.loads(Path('/tmp/recovery-ha.json').read_text())['installed'] is False
recovered=execute(script);assert recovered.returncode==0,(recovered.stdout+recovered.stderr)[-4000:]
assert json.loads(Path('/tmp/recovery-ha.json').read_text())=={'installed':True,'version':'1.0.0-rc3','state':'started'}
assert (target/'PACKAGE_MANIFEST.json').read_bytes()!=old_manifest
assert Path('/data/keep').read_text()=='remaining data sentinel'
assert Path('/config/keep').read_text()=='unrelated home configuration'
assert (other/'config.yaml').read_text()=='unrelated app source'
completed=list(base.glob('.hads-next-recovery-completed-*.json'));assert len(completed)==1
receipt=json.loads(completed[0].read_text());assert receipt['previous_app_data_restore_proven'] is False
preserved=Path(receipt['preserved_source_directory']);assert (preserved/'config.yaml.source-backup').read_bytes()==old_config
with tarfile.open(receipt['source_backup']) as archive:assert archive.extractfile('PACKAGE_MANIFEST.json').read()==old_manifest
assert not (base/'.hads-next-recovery-pending.json').exists()
again=execute(script);assert again.returncode!=0
calls=[json.loads(x) for x in Path('/tmp/recovery-ha-calls.jsonl').read_text().splitlines()]
assert calls.count(['apps','install','local_hads_next_practical'])==1
assert not any(len(c)>1 and c[1] in {'uninstall','stop','update','restart'} for c in calls)
print(json.dumps({'scope':'native_container_actual_recovery_helper_and_published_RC3_installer_fake_Supervisor','architecture':platform.machine(),'live_haos':False,'actual_installer_sha256':hashlib.sha256(Path('/released-rc3.sh').read_bytes()).hexdigest(),'installed_error_refused':True,'uninstalled_orphan_guard_reproduced':True,'verify_alone_did_not_install':True,'exact_released_RC2_sources_preserved':True,'unrelated_data_untouched':True,'uninstalled_data_restored':False,'RC3_installed_and_started_in_fake_Supervisor':True,'no_repeated_install':True,'no_uninstall_stop_or_restart_commands':True,'passed':True}))
