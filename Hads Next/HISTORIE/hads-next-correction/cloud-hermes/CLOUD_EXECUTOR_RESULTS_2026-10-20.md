# HADS Hermes RC2 cloud verification — 2026-10-20

Status: **BLOCKED — no installable RC2 produced.** The inspected source is RC1, not a verified release. No production HAOS system was accessed or changed. No model API request was made, no cloud resources were provisioned, and no credentials were used.

## Source integrity and handling

- Repository: `OndraMa/HADS`
- Branch: `hermes-2-rc2-cloud-verification`
- Starting commit: `8ffcf8eaf823855aada80a3e53abc2bbef7ed1c0`
- Read `cloud-hermes/CLOUD_HANDOFF.md` and `cloud-hermes/SHA256SUMS` from that branch.
- Retrieved archive through the connected GitHub integration: `cloud-hermes/HADS_Hermes_2.0.0-rc1-source.zip`.
- Expected SHA-256: `db4efd61b0a85c068975e005a009e57ec3b7a87d6aef57720fa1457f1737b8cf`.
- Actual SHA-256: same; **PASS**.
- ZIP inspection: 121 entries; no absolute, traversal, drive-prefixed, or NUL-containing paths; **PASS**.
- Extracted to a dedicated `cloud-hermes/source-rc1` directory in scratch, never over a repository root.
- No source code or existing release was modified. The archive remains identified as RC1.

## Actual executor environment

Observed directly in the job:

| Check | Result |
|---|---|
| Kernel and architecture | Linux 6.18.55, x86_64 |
| Runtime context | root inside a Kata-style overlay guest; this is not HAOS |
| Python | 3.12.14; Python 3.14 executable not present |
| Memory | MemTotal 10,206,484 kB; MemAvailable 9,584,016 kB |
| Cgroup limit | 8,589,934,592 bytes; pids limit is unlimited |
| Seccomp | enabled, mode 2, one filter |
| Docker / Podman | not installed |
| `unshare -Ur true` | failed: cannot write uid_map, Operation not permitted |
| `unshare -m true` | failed: Operation not permitted |
| Bubblewrap namespace probe | failed while opening namespace; exit 1 |
| Landlock ABI probe | syscall returned -1, errno 38 (`ENOSYS`) |

These are cloud executor measurements, not evidence about the target Pi or HAOS container. No working kernel-enforced filesystem/network isolation mechanism was found here. Do not replace Landlock with an unconfined worker or broaden privileges.

## Checks run

- `node tests/test_hermes2_ui.mjs`: **PASS**, UI state contract (disabled, unverified, running, completed, failed).
- `python3 -m compileall -q .`: **PASS**, syntax compilation only.
- `python3 -m pytest -q`: **NOT RUN**; pytest is absent.
- `python3 -m unittest discover -s tests -v`: **BLOCKED**; all 25 discovered modules errored during import because `jsonschema` is unavailable. This is not a test failure in product logic and is not a passing suite.
- Real upstream Hermes `AIAgent` smoke test: **NOT RUN**. The Dockerfile's smoke test requires Python 3.14, pinned Hermes v0.22.2, build dependencies, and a Linux confinement path. This executor has no Docker/Podman, no Python 3.14, and no usable Landlock/namespaces. The fake local model in the smoke test was therefore not invoked.
- Isolation negative tests, filesystem/network denial, worker timeout/cleanup, combined HADS+worker peak RSS, and concurrency: **NOT RUN** because the boundary cannot be established here.
- The executor's high available memory is not a worker RSS measurement and cannot justify changing the admission gate.

## Target memory gate

The handoff reports target `MemAvailable=597596 kB`. That is less than the current 768 MiB threshold (786432 KiB), by approximately 18836 KiB (18.4 MiB). The existing gate must remain unchanged until real measurements show a safe value and the complete memory budget has been tested on representative aarch64 HAOS hardware. The 8 GiB executor cgroup provides no relevant sizing evidence.

## Safety gate matrix

| Gate | Status |
|---|---|
| Preserve local NousResearch Hermes Agent | Required; no API-only replacement |
| Verified pinned upstream runtime executing | **Blocked / not tested** |
| Enforced worker isolation on supported target | **Blocked / not tested** |
| No HA config, secrets, or backups visible to worker | **Not verified** |
| No shell/exec, direct external network, or approval/write tools | **Not verified** |
| Authenticated, bounded read broker | **Not verified end-to-end** |
| Real worker and combined peak memory on Pi-class aarch64 | **Not measured** |
| Timeout, cleanup, concurrency, security-negative tests | **Not run** |
| Read-only diagnosis and concrete per-repair approval | Must be retained; end-to-end tests blocked |
| Independently verified OneDrive backup before every repair | Must be retained; end-to-end tests blocked |
| Outcome report and rollback | Must be retained; end-to-end tests blocked |
| Durable spending caps / no paid requests | No requests made; persistence behavior not tested |
| Installable RC2 | **NO — do not install** |

## Separate non-destructive HAOS compatibility procedure

Only after a future candidate has passed cloud safety gates, test compatibility on HAOS in a staging add-on or disposable Pi image. Do not run a repair or provide production write access during these checks.

1. Record `uname -m`, `uname -r`, `cat /proc/meminfo`, `cat /proc/self/status` (especially `Seccomp`), and cgroup memory limit/current values from the actual add-on container.
2. Run the candidate's read-only preflight. Record Landlock ABI and every required syscall result. If ABI 4 or any required restriction cannot be applied, stop; keep Hermes disabled.
3. Verify container-level read access using harmless canary files: the worker must not read HA configuration, token/config directories, backup mounts, or host paths. Verify no Docker socket or broad host mount is present.
4. Run explicit negative probes under the enforced boundary: attempt file reads outside the private worker home, writes outside it, process execution, network access to a non-broker endpoint, access to broker write/approval endpoints, and access to a fake secret. Every attempt must be denied and logged without exposing contents.
5. Use only a local fake model endpoint bound to loopback; verify the actual pinned Hermes `AIAgent` starts, handles a bounded diagnosis, and cannot invoke write/approval tools. Confirm no external model/API traffic.
6. Measure worker peak RSS and whole add-on/cgroup peak under idle, one diagnosis, worst-case bounded diagnosis, and intended concurrency. Include SQLite/runtime overhead and safety reserve. Keep the 768 MiB gate unless those measurements justify a reviewed new budget.
7. Verify timeout termination and cleanup, then reboot/restart the staging add-on and confirm protections remain active. Test approval binding, OneDrive backup verification, outcome report, rollback path, and durable spending caps with non-production fixtures only.
8. Any failed or unavailable check blocks installation. Only after all evidence is recorded should a human review an installable candidate. Run read-only compatibility checks first; require explicit approval plus independently verified OneDrive backup for each production repair.

## Next blocking work

A compatible executor or staging environment must provide the actual target architecture/runtime and enforceable kernel isolation. Until then, changing or removing the mandatory isolation and lowering the memory threshold would weaken safety without evidence, so no RC2 code fix or release claim is justified.


Additional memory sample: HADS `runtime_core.memory_sample()` reported `available_bytes=8052232192` and process RSS `14168064` bytes in the executor. This is executor-only data, not Hermes worker RSS; it reflects the runtime's cgroup-aware sampler and cannot size the Pi deployment.
