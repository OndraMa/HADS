"""Host launcher of the fixed offline Hermes test; no configurable HA target."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path)
    parser.add_argument('--adversarial', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    payload = args.input.read_bytes() if args.input else b''
    if len(payload) > 65536:
        raise ValueError('Snapshot too large')
    command = ['docker', '--host=unix:///var/run/docker.sock', 'run', '--rm', '-i',
        '--network', 'none', '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--memory', '512m', '--memory-swap', '512m',
        '--pids-limit', '64', '--cpus', '1',
        '--tmpfs', '/tmp:rw,noexec,nosuid,size=96m,mode=1777']
    for variable in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        command.extend(['--env', variable + '='])
    for source, destination in (
        (ROOT / 'src/hads_next/investigation.py', '/app/hads_next/investigation.py'),
        (ROOT / 'scripts/hermes_smoke.py', '/app/hermes_smoke.py')):
        command.extend(['--mount', f'type=bind,src={source},dst={destination},readonly'])
    command.append('hads-next-hermes-smoke')
    if args.adversarial:
        command.append('--adversarial')
    completed = subprocess.run(command, input=payload, capture_output=True, timeout=150)
    if completed.returncode:
        raise RuntimeError('Hermes smoke failed: ' + completed.stderr.decode(errors='replace')[-3000:])
    result = json.loads(completed.stdout)
    if result.get('execution_authority') != 'none' or result.get('scope') != 'offline-container':
        raise RuntimeError('Unexpected Hermes receipt')
    metadata = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', 'image', 'inspect', 'hads-next-hermes-smoke', '--format', '{{.Id}}'], check=True, capture_output=True, text=True)
    result['image_id'] = metadata.stdout.strip()
    dependencies = result.pop('dependencies', [])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (args.output.parent / 'hermes-dependencies.txt').write_text('\n'.join(dependencies) + '\n')
    print(f'Hermes offline receipt: {args.output}')

if __name__ == '__main__':
    main()
