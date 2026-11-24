"""Build/inspect the exact candidate payload, optionally boot its production image.

No HAOS credentials, household network, model endpoint or privileged host mounts.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hads_next.build_identity import inspect_build


def run(args):
    return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--docker',action='store_true');args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_haos_installer.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    built=builder.build_installer(output/'assets');installer=Path(built['installer']);context=output/'context'
    run(['bash',str(installer),'--verify']);run(['bash',str(installer),'--extract-only',str(context)])
    manifest=json.loads((context/'PACKAGE_MANIFEST.json').read_text());build=inspect_build(context/'hads_next')
    commit=run(['git','-C',str(ROOT),'rev-parse','HEAD']).strip()
    assert build['source_verified'] and build['source_commit']==commit
    assert manifest['installer_backup_policy']=='no_preinstall_HA_or_cloud_backup_user_requested'
    assert (context/'lab/service-requirements.txt').is_file()
    image_passed=False;health=None;stopped_exit=None
    if args.docker:
        image='hads-next-candidate:'+commit[:12]
        subprocess.run(['docker','build','--build-arg','CORE_LAB=0','-t',image,str(context)],check=True)
        container=run(['docker','run','-d','--network','none','--memory','2g','--cpus','1','--tmpfs','/data:rw,nosuid,nodev,size=64m',image]).strip()
        try:
            for _ in range(60):
                try:
                    raw=run(['docker','exec',container,'python','-c',"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8099/health',timeout=2).read().decode())"])
                    health=json.loads(raw)
                    if health['build']['source_verified']:break
                except (subprocess.CalledProcessError,ValueError):pass
                time.sleep(1)
            assert health and health['build']==build
            run(['docker','stop','--time','15',container]);stopped_exit=int(run(['docker','inspect','--format','{{.State.ExitCode}}',container]).strip())
            assert stopped_exit==0
            image_passed=True
        finally:
            subprocess.run(['docker','rm','-f',container],capture_output=True)
    proof={'scope':'offline_installer'+('_native_production_container' if args.docker else ''),'passed':True,
        'source_commit':commit,'build':build,'payload_sha256':hashlib.sha256(Path(built['source_archive']).read_bytes()).hexdigest(),
        'installer_sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),'payload_files':len(manifest['files']),
        'production_image_boot_passed':image_passed,'production_image_health':health,'SIGTERM_exit_code':stopped_exit,
        'network':'none' if args.docker else 'no_container','paid_model_calls':0,'live_haos':False,
        'actual_Supervisor_upgrade':False,'source_upgrade_tests':'separate test_upgrade_candidate.py with actual published RC6–RC9 source trees'}
    (output/'CANDIDATE_PROOF.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    print('HADS_CANDIDATE_PROOF='+json.dumps(proof,ensure_ascii=False,sort_keys=True))


if __name__=='__main__':main()
