"""Isolated package/install/runtime acceptance. Uses a fake Supervisor, never HAOS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "hads-next-haos:0.2.0-dev1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--image",default=IMAGE)
    args = parser.parse_args()
    image=args.image
    env = dict(os.environ)
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(name, None)
    def docker(*command, check=True, timeout=60):
        result = subprocess.run(["docker", "--host=unix:///var/run/docker.sock", *command],
            env=env, capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f"Docker {command[0]} exited {result.returncode}: " + (result.stderr + result.stdout)[-3000:])
        return result
    suffix = uuid.uuid4().hex[:12]
    name, volume = "hads-next-dev-smoke-" + suffix, "hads-next-dev-data-" + suffix
    report = {"scope": "container_with_fake_supervisor", "live_haos": False, "arm64_tested": False,
              "installer_sha256": hashlib.sha256(args.installer.read_bytes()).hexdigest()}
    try:
        isolation=["run","--rm","--network","none","--read-only","--cap-drop","ALL",
            "--cap-add","CHOWN","--cap-add","SETUID","--cap-add","SETGID","--cap-add","SYS_CHROOT",
            "--security-opt","no-new-privileges","--pids-limit","64","--cpus","1",
            "--tmpfs","/tmp:rw,nosuid,nodev,size=32m,mode=1777",
            "--tmpfs","/opt/hermes-root/tmp:rw,nosuid,nodev,size=32m,mode=1777"]
        result=docker(*isolation,"--memory","768m","--memory-swap","768m","--entrypoint","python",image,
            "-m","hads_next.runtime_check","--self-check",timeout=195)
        report["native_runtime_readiness"]=json.loads(result.stdout)
        assert report["native_runtime_readiness"]["passed"] is True
        rejected=docker(*isolation,"--memory","512m","--memory-swap","512m","--entrypoint","python",image,
            "-m","hads_next.runtime_check","--self-check",check=False,timeout=195)
        memory_receipt=json.loads(rejected.stdout)
        assert rejected.returncode!=0 and memory_receipt["result"]["error"]=="insufficient_memory_reserve",memory_receipt
        report["memory_admission_refused_without_model"]=memory_receipt
        docker("volume", "create", volume)
        docker("run", "-d", "--name", name, "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "SYS_CHROOT",
            "--security-opt", "no-new-privileges", "--memory", "768m", "--memory-swap", "768m",
            "--cpus", "1", "--pids-limit", "64", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--tmpfs", "/opt/hermes-root/tmp:rw,nosuid,nodev,size=32m,mode=1777",
            "--mount", f"type=volume,src={volume},dst=/data", image)
        probe = '''import http.client,json,time
for attempt in range(30):
 try:
  c=http.client.HTTPConnection('127.0.0.1',8099,timeout=2);c.request('GET','/health');r=c.getresponse();body=json.loads(r.read());assert r.status==200;break
 except (OSError,AssertionError):time.sleep(.1)
else:raise AssertionError('Health did not become ready')
c=http.client.HTTPConnection('127.0.0.1',8099,timeout=2);c.request('GET','/api/status',headers={'X-Remote-User-Id':'forged'});assert c.getresponse().status==403
status=open('/proc/1/status').read();assert 'Uid:\\t65532' in status;assert 'CapEff:\\t0000000000000000' in status
print(json.dumps({'health':body,'runtime_uid':65532,'capabilities':0,'direct_data_access':403}))'''
        report["runtime"] = json.loads(docker("exec", "--user", "65532", name, "python", "-c", probe).stdout)
        seed = "from hads_next.haos_application import Application; a=Application('/data/hads-next'); c=a.report_incident('Izolovaný test persistence','light.fixture','fixture-owner'); print(c['incident']['id'])"
        case_id = docker("exec", "--user", "65532", name, "python", "-c", seed).stdout.strip()
        docker("restart", name)
        docker("exec", "--user", "65532", name, "python", "-c", probe)
        read = "from hads_next.haos_application import Application; a=Application('/data/hads-next'); assert a.snapshot()['cases'][0]['id']==" + repr(case_id)
        docker("exec", "--user", "65532", name, "python", "-c", read)
        report["case_persisted_after_container_restart"] = True
        report["image"] = json.loads(docker("image", "inspect", image, "--format", "{{json .}}").stdout)
        report["image"] = {k: report["image"][k] for k in ("Id", "Architecture", "Os", "Size")}
        report["arm64_tested"]=report["image"]["Architecture"]=="arm64"
        report["raspberry_pi_tested"]=False
        with tempfile.TemporaryDirectory(prefix="hads-next-fake-ha-") as tmp:
            fake = Path(tmp) / "ha"
            fake.write_text('''#!/usr/local/bin/python3
import json,sys
args=sys.argv[1:]
with open('/tmp/ha-calls.jsonl','a') as f:f.write(json.dumps(args)+'\\n')
if args==['apps','--raw-json']:print(json.dumps({'result':'ok','data':{'addons':[]}}))
elif args==['apps','info','local_hads_next_investigation','--raw-json']:print(json.dumps({'data':{'version':'0.2.0-dev1','state':'started'}}))
elif args not in [['apps','--help'],['store','reload'],['apps','install','local_hads_next_investigation'],['apps','start','local_hads_next_investigation']]:sys.exit(91)
''')
            fake.chmod(0o755)
            assertion = '''import json,subprocess,pathlib
calls=[json.loads(x) for x in pathlib.Path('/tmp/ha-calls.jsonl').read_text().splitlines()]
assert calls==[['apps','--help'],['apps','--raw-json'],['store','reload'],['apps','install','local_hads_next_investigation'],['apps','start','local_hads_next_investigation'],['apps','info','local_hads_next_investigation','--raw-json']],calls
again=subprocess.run(['bash','/installer.sh','--install-dev'],capture_output=True)
assert again.returncode!=0
assert len(pathlib.Path('/tmp/ha-calls.jsonl').read_text().splitlines())==len(calls)
print(json.dumps({'fake_supervisor_only':True,'commands':calls,'reinstallation_refused':True}))'''
            script = "bash /installer.sh --install-dev > /tmp/install.log && python -c " + __import__("shlex").quote(assertion)
            result = docker("run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--memory", "256m", "--memory-swap", "256m",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m", "--tmpfs", "/addons:rw,nosuid,size=16m",
                "--mount", f"type=bind,src={args.installer.resolve()},dst=/installer.sh,readonly",
                "--mount", f"type=bind,src={fake},dst=/usr/local/bin/ha,readonly",
                "--entrypoint", "bash", image, "-c", script)
            report["install"] = json.loads(result.stdout)
        report["passed"] = True
        output = ROOT / "docs/evidence/haos-investigation-package.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception:
        print(docker("logs", name, check=False).stdout[-3000:])
        print(docker("logs", name, check=False).stderr[-3000:])
        raise
    finally:
        docker("rm", "-f", name, check=False)
        docker("volume", "rm", volume, check=False)


if __name__ == "__main__":
    main()
