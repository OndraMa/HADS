"""Assemble a reviewable build context; does not publish an installer/release."""
import argparse
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    parser.add_argument('--receipt',action='store_true')
    args=parser.parse_args();target=args.destination
    if target.exists():raise ValueError('Use a new build context directory')
    target.mkdir(parents=True)
    shutil.copytree(ROOT/'src/hads_next',target/'hads_next',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ROOT/'lab',target/'lab',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(ROOT/'haos/Hermes.Dockerfile',target/'Dockerfile')
    if args.receipt:
        with (target/'Dockerfile').open('a') as output:
            output.write('\nFROM scratch AS receipt\nCOPY --from=0 /app/core-hermes-proof.json /core-hermes-proof.json\n')
    shutil.copyfile(ROOT/'haos/run.sh',target/'run.sh')
    shutil.copyfile(ROOT/'docs/evidence/hermes-dependencies.txt',target/'hermes-constraints.txt')
    for path in [target,*target.rglob('*')]:path.chmod(0o755 if path.is_dir() else 0o644)
    print(json.dumps({'context':str(target),'hermes_revision':'d923a5eb487a17c0a68801bba9ef0f56c81040a8'}))


if __name__=='__main__':main()
