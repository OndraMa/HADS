"""Package only the exact source verified by the recorded ARM64 workflow.

Windows asyncio/socketpair cannot complete under this local environment's
network restrictions. Do not relabel the ARM64 run as a local test.
"""
import json
from pathlib import Path
import sys
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent / 'test-deps'))
import build_release as release

receipt = json.loads((here / 'cloud-verification.json').read_text(encoding='utf-8'))
assert receipt['version'] == release.VERSION == '2.0.0-rc3'
assert receipt['conclusion'] == 'success'
assert receipt['source_commit'] == 'e1f3f880c98bfa5fafc28261b7859483e11a7e1d'
proof_zip = here / 'packaging-source.zip'
release.source_zip(release.included_files(), proof_zip)
assert release.sha256(proof_zip) == receipt['source_sha256'], 'Source changed after cloud verification'
checks = receipt['checks']
assert checks['python_unittest']['tests'] > 395
assert checks['python_unittest']['errors'] == checks['python_unittest']['failures'] == 0
assert checks['python_unittest']['status'] == 'passed'
assert checks['cloud_arm64_verification']['result'] == 'passed'
release.main(verified_checks=checks)
