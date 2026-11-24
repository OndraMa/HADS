"""Cloud test harness: real release builder, original template shell minus replaced payload."""
from pathlib import Path
import json
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path.cwd()))
import build_release
build_release.TEMPLATE = Path(__file__).resolve().parents[1] / "ci" / "installer-template.sh"
suite = unittest.defaultTestLoader.discover("tests")
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({"tests": result.testsRun, "errors": len(result.errors), "failures": len(result.failures), "skipped": len(result.skipped)}))
if not result.testsRun or not result.wasSuccessful():
    raise SystemExit(1)
