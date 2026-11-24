# HADS Hermes: cloud migration and RC2 verification gate

This is a development handoff, NOT a verified RC2 release. The supplied archive
is the last RC1 source snapshot. Do not deploy it unchanged.

## User requirements and target

- Real local NousResearch Hermes Agent must remain; API-only replacement rejected.
- Production target: Raspberry Pi 4B, 2 GB RAM, aarch64 HAOS.
- Reported kernel: 6.18.39-haos-raspi; Landlock probe in Terminal returned
  ABI -1 / ENOSYS. This does NOT prove whether host or container security caused it.
- MemTotal 1886428 kB; MemAvailable 597596 kB at measurement.
- RC1 stopped before source replacement. Mandatory Landlock ABI 4 and a
  768 MiB memory admission gate currently make this deployment incompatible.

## Safety and authority

Work on code and tests in the cloud. No production HAOS access or deployment.
Do not install WSL, Docker or other software on the user's Windows PC.
Do not provision paid compute, call paid model APIs, add payment methods, or
enable unattended paid jobs. No real API credentials or household logs are
included or needed for initial tests. Never print or commit secrets.
Read-only diagnosis is autonomous. Every production mutation requires explicit
approval of its concrete plan plus independently verified OneDrive backup.
Installation backup exemption does not exempt repairs from backups.
Preserve durable spending limits, approval binding, rollback and outcome reports.

## Initial cloud task

1. Inspect archive filenames before extraction; reject absolute/traversal paths.
2. Verify source archive SHA-256 against SHA256SUMS. Extract into a dedicated
   workspace, not over the repository root. Commit readable sources on this
   development branch when permitted; preserve older release files.
3. Inspect available Linux runtime, architecture, Python, container tooling,
   kernel capabilities and available memory. Report actual evidence.
4. Run offline Python/UI regression suites; use fake local model responses.
5. Build and run the pinned REAL Hermes, not a stub AIAgent. RC1 Dockerfile
   invokes tests/hermes_upstream_smoke.py during build; audit this test first.
6. Reproduce the Landlock failure. Design and test an alternative enforced
   isolation boundary compatible with HAOS. Do NOT just remove confinement,
   broaden privileges, mount Docker socket, or turn off protection mode.
7. Verify no HA configuration, tokens or backup files are readable by Hermes;
   no shell/exec, direct external network or approval/write tools are available.
   Allowed diagnosis passes through an authenticated, bounded read broker.
8. Measure actual worker and combined HADS memory (peak RSS/cgroup where possible),
   timeout/cleanup and concurrent load. Do not lower the memory threshold based
   on guesswork. Distinguish amd64 tests from aarch64 tests and native vs emulated.
9. Keep RC2 blocked if isolation or memory admission cannot be proved. Cloud
   success cannot prove HAOS AppArmor/seccomp compatibility; provide a separate
   non-destructive on-device verification procedure before installation.

## Existing source and tests

Archive: HADS_Hermes_2.0.0-rc1-source.zip (inspect its layout before extraction).
Pinned Hermes v0.22.2: d923a5eb487a17c0a68801bba9ef0f56c81040a8.
Upstream actual supported runtime is Python 3.14; do not assume Python 3.12
is sufficient merely because RC1's mocked unit tests ran there.
RC1 previously passed 386 Python tests and JS contracts locally, but actual
Docker build, AIAgent startup, isolation and live HAOS were NOT verified.

Key files: hermes_bridge.py, hermes_worker.py, hermes_isolation.py,
hermes_preflight.py, Dockerfile, tests/hermes_upstream_smoke.py,
tests/test_hermes2.py, incident_workflow.py, runtime_core.py.

## Required deliverable

Evidence-backed report with commands, actual outputs, architecture, memory
measurements and test counts; readable source diff; honest pass/fail/not-run
matrix. Only produce an installable RC2 after its safety gates pass. No promises
of 100% reliability based on simulated tests. If cloud cannot run necessary
isolation/container tests, state the limitation instead of weakening protection.
