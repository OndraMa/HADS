"""Run the real Core probe in an ephemeral, disconnected Linux container.

No existing HA URL, token, configuration directory or host port is accepted.
Only public test source is staged; private checkout permissions are preserved.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "hads-next-core-lab:2026.11.0"


def main():
    env = dict(os.environ)
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(key, None)

    def docker(*args, timeout=180, check=True):
        result = subprocess.run(["docker", "--host=unix:///var/run/docker.sock", *args],
                                env=env, capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError((result.stdout + result.stderr)[-6000:])
        return result

    image = json.loads(docker("image", "inspect", IMAGE, "--format", "{{json .}}").stdout)
    name = "hads-core-lab-" + uuid.uuid4().hex[:12]
    inputs = [ROOT / "lab" / name for name in ("Core.Dockerfile", "core-constraints.txt", "core_contract_probe.py", "core_repair.py", "exercise_repair.py", "run_core_lab.py")]
    inputs += sorted((ROOT / "src" / "hads_next").glob("*.py"))
    inputs.append(ROOT / 'docs/evidence/core-lab-dependencies.txt')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="hads-core-public-test-") as temporary:
        stage = Path(temporary)
        stage.chmod(0o755)
        for source in inputs:
            target = stage / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o644)
        for directory in sorted(stage.rglob("*")):
            if directory.is_dir():
                directory.chmod(0o755)
        source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256((stage / p.relative_to(ROOT)).read_bytes()).hexdigest()
                         for p in inputs}
        try:
            result = docker("run", "--rm", "--name", name,
                "--network", "none", "--read-only", "--user", "65532:65532",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777",
                "--memory", "768m", "--memory-swap", "768m", "--cpus", "1", "--pids-limit", "96",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--mount", f"type=bind,src={stage},dst=/work,readonly", "-e", "PYTHONPATH=/work/src",
                image["Id"], "/work/lab/core_contract_probe.py")
            records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            if not records or not records[-1].get("passed"):
                raise RuntimeError("Core probe nevytvořil úspěšný výsledek.")
            report = {**records[-1], "recorded_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "image": {key: image[key] for key in ("Id", "Architecture", "Os", "Size")},
                "isolation": {"network": "none", "read_only_root": True, "uid": 65532,
                    "capabilities": 0, "memory_limit_bytes": 768 * 1024 * 1024},
                "input_sha256": source_hashes}
            if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != checksum
                   for name, checksum in source_hashes.items()):
                raise RuntimeError("Zdroj se během běhu změnil; výsledek se nepublikuje jako aktuální.")
            output = ROOT / "docs/evidence/core-lab.json"
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            docker("rm", "--force", name, check=False, timeout=30)


if __name__ == "__main__":
    main()
