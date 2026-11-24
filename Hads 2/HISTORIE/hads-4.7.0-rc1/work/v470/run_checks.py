"""Execute offline checks. Never report a check that did not run."""
import compileall
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def run_checks():
    source = Path(__file__).resolve().parent / "src"
    old_cwd = Path.cwd()
    os.chdir(source)
    sys.path.insert(0, str(source))
    try:
        suite = unittest.defaultTestLoader.discover(str(source / "tests"))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful() or not result.testsRun:
            raise RuntimeError(f"Unit tests failed: {result.testsRun} run, {len(result.failures)} failures, {len(result.errors)} errors")
        if not compileall.compile_dir(str(source), quiet=1):
            raise RuntimeError("Python compilation failed")
        for script in (source / "web").glob("*.js"):
            subprocess.run(["node", "--check", str(script)], check=True)
        subprocess.run(["node", str(source / "tests/test_webmcp_contract.mjs")], check=True)
        return {
            "python_unittest": {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "status": "passed"},
            "python_compileall": "passed",
            "javascript_syntax": "passed",
            "webmcp_contract": "passed",
        }
    finally:
        os.chdir(old_cwd)


if __name__ == "__main__":
    print(json.dumps(run_checks(), indent=2))
