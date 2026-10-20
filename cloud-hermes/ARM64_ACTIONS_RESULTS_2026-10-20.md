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

## Second run — real Hermes startup achieved, hardened runtime still fails

Run: https://github.com/OndraMa/HADS/actions/runs/39394930437
Commit: 0a2f7d7720d43b6276d9743f2804ca0e595a16c2

- Python 3.14.8 ARM64: 386 tests passed, zero failures/errors (21.561 s).
- All nine UI contract suites and JavaScript syntax checks passed.
- Docker build with pinned real Hermes and editable installation succeeded.
- During the real build smoke test: "Real pinned Hermes + one model call +
  Landlock: passed (fake model, no paid API)" at 08:41:28 UTC.
- Additional runtime trial used a read-only rootfs, no external container
  network, 512 MiB memory+swap ceiling, 64-pid limit and sharply reduced
  parent capabilities. It FAILED before starting the worker:
  subprocess Popen could not access /tmp/hads-hermes-* after ownership was
  transferred to nobody; temporary-directory cleanup then failed too.
- Docker reported ExitCode 1 and OOMKilled false. This is a filesystem
  permission/lifecycle failure, NOT proof Hermes exceeds 512 MiB.
- Do not remove Landlock or raise privileges merely to turn this result green.
  Review the trusted-parent/private-worker directory lifecycle and cleanup
  permissions, and test them explicitly with the intended production profile.
- No actual worker peak-RSS or combined HAOS/Pi memory measurement obtained.
- Real upstream startup is now demonstrated on the Actions build environment,
  NOT on HAOS with ENOSYS. Installer compatibility and memory admission still
  block an installable RC2. No release, production deployment or paid API call.

The user's screenshots showed a zero-dollar Actions budget and unused included
minutes. Budget settings were not modified. This report does not assert final
billing reconciliation; no larger/paid-only runner or artifact upload was used.
