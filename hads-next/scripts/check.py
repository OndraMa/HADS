"""Run offline tests and save a revision-bound, machine-readable receipt."""
import datetime
import hashlib
import json
from pathlib import Path
import platform
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    files = sorted(p for folder in ("src", "tests", "scripts") for p in (ROOT / folder).rglob("*.py"))
    inputs = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
    receipt = {
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "offline", "live_haos": False, "python": platform.python_version(),
        "architecture": platform.machine(), "tests_run": result.testsRun,
        "failures": [test.id() for test, _ in result.failures],
        "errors": [test.id() for test, _ in result.errors],
        "skipped": [test.id() for test, _ in result.skipped],
        "passed": result.wasSuccessful(), "input_sha256": inputs,
        "limitations": ["Synthetic fixtures, no physical HAOS installation", "Native Hermes has separate container receipts"],
    }
    output = ROOT / "docs/evidence/offline-tests.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
