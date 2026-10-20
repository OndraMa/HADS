# Native ARM64 Actions verification — first run

Run: https://github.com/OndraMa/HADS/actions/runs/39394410445
Commit: b9584b5985d05b4b7e91a8383c261a44b2b19561

Actual runner: Ubuntu 24.04.5 ARM64, Linux 7.0.0-1017-azure aarch64,
Python 3.14.8, Docker 28.0.4. Host Landlock ABI 8, errno 0.
This is NOT the HAOS target.

- Source checksum and safe extraction passed.
- Python: 386 tests, zero assertion failures, ONE import error:
  test_500_native_backup imports build_release, absent from addon-only ZIP.
  This is incomplete cloud handoff, not evidence of a Python 3.14 regression.
- All nine Node UI contract suites and JS syntax checks passed.
- Docker build reached real upstream installation, then failed because pinned
  Hermes setup.py explicitly disallows wheel distribution. The existing
  non-editable pip install is incorrect. Actual AIAgent has NOT started.
- Runtime isolation and 512 MiB trial skipped. No memory sizing claim.
- No paid model calls, deployment, or budget changes.

Follow-up supplies the unchanged local release builder/run_checks modules,
its original installer shell template (only embedded payload replaced, because
installer() replaces that payload anyway), and an explicit CI Dockerfile using
upstream-supported editable source installation. No wheel guard bypass,
no Landlock/security bypass, and no production installable release.

Correction to earlier executor report: 786432 - 597596 = 188836 KiB,
about 184.4 MiB, not 18836 KiB. The existing memory gate remains unmet.
