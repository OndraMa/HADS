"""Native isolated recovery acceptance; never accesses the user's HAOS."""
import argparse,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
IMAGE='python:3.14-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b'

def main():
    p=argparse.ArgumentParser();p.add_argument('--architecture',choices=['amd64','arm64'],required=True);args=p.parse_args()
    mounts=[(ROOT/'scripts/recover_rc3.py','/recover.py'),(ROOT/'lab/recovery_bootstrap.py','/bootstrap.py'),(ROOT/'lab/recovery_fake_ha.py','/usr/local/bin/ha'),(ROOT.parent/'KE_STAZENI/HADS_Next_1.0.0-rc2/HADS_Next_1.0.0-rc2-source.tar.gz','/released-rc2.tar.gz'),(ROOT.parent/'KE_STAZENI/HADS_Next_1.0.0-rc3/HADS_Next_install_1.0.0-rc3.sh','/released-rc3.sh')]
    command=['docker','--host=unix:///var/run/docker.sock','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--memory-swap','256m','--pids-limit','32']
    for folder in ['/tmp','/addons','/data','/config']:command+=['--tmpfs',folder+':rw,nosuid,nodev,size=16m']
    for source,destination in mounts:command+=['--mount',f'type=bind,src={source.resolve()},dst={destination},readonly']
    command += [IMAGE,'python','/bootstrap.py']
    env={k:v for k,v in os.environ.items() if k not in {'DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'}}
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=240)
    if result.returncode:raise RuntimeError((result.stdout+result.stderr)[-5000:])
    report=json.loads(result.stdout);assert report['passed']
    assert report['architecture']==('aarch64' if args.architecture=='arm64' else 'x86_64')
    out=ROOT/'docs/evidence'/('recovery-'+args.architecture+'.json');out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
