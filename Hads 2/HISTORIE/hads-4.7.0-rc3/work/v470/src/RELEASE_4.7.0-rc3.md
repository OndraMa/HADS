# HADS 4.7.0-rc3 — evidence collection and failure follow-up

## Status

Development candidate, **not a fully validated final autonomous repairer**. No changes have been installed in the user's HAOS by this development task. Previous databases and manual decisions must remain intact. The add-on installer does not install the optional Core companion.

## Implemented

- Explicit **Approve and start this repair** runs just that plan through the existing backup-gated batch engine. Approve-to-queue remains available. The selected plan IDs are frozen at job launch; later approvals cannot silently join the batch. No persistent auto-write mode is enabled on upgrade.

- AI live-state tool reads Core directly with no stale-cache fallback. Current state is not confused with physical success.
- Device investigation reads a timezone-explicit, bounded Recorder window, entity/device registry association, and up to four same-device battery/signal/last-seen sensors. Disabled sensors remain disabled. Unknown history, missing telemetry and truncated results are explicit.
- Core/Supervisor/host log tails and installed-addon log tails are read-only AI tools. Zigbee2MQTT slug must exist in live inventory; ZHA evidence comes from Core. Historical case occurrences are supplied separately and labeled as imported findings, not complete raw logs.
- Resource investigation reads Core/Supervisor stats, host info, pages of eight installed addons, historical CPU/RAM aggregates and lifecycle events. Container memory limits are not presented as total host RAM. No process-level attribution is claimed.
- AI can request evidence and receive it in subsequent Responses calls. Results are redacted, kept as valid JSON and expose omissions. Older tool text can be compacted before another request; encrypted reasoning/function-call pairs are preserved. The existing 64-kB transport cap still applies.
- Last 200 tool observations per case are stored; latest 20 are visible in incident evidence with tool/time/run. Research summaries and repair histories are separate.
- Reviewable advice and necessary user questions have explicit routing. A model-provided `conclusion_verified` boolean is not accepted as proof. Hardware advice is not an executable repair.
- Failed/interrupted repairs re-enter read-only planning. Failure and old plan remain visible until a fresh plan is ready. The old deterministic recipe is not blindly proposed again; writes still require new approval.
- Similar phone/service names are candidates, not verified identity. A name-similarity score alone no longer creates an allegedly proven replacement plan; explicit verified selections remain supported.
- Optional `HADS Rescue Readback` Core component implements a real independent OneDrive download/hash contract. Native OneDrive alone does not expose this readback service. Automatic discovery uses the exact known service, not guessed names.
- Recorder purge rescue includes a consistent SQLite backup using SQLite backup API and quick_check before remote upload; oversized archives block, not bypass, the cloud requirement.

## Required acceptance before a stable release

1. Install candidate add-on and explicitly install/activate the optional Core companion; verify actual installed Core/OneDrive compatibility.
2. OneDrive: positive independent readback, negative cases, backup contents and recovery test. The companion verifies the rescue ZIP, **not a full native HA backup**. Full cloud-backup orchestration and safe replacement/rotation of the previous cloud backup remain incomplete.
3. Real failed-lights incident: compare automation trace, device history, source-addon report and resulting proposed plan; preserve unavailable evidence as unknown.
4. Actual paid API run and follow-up tool call, usage visibility and understandable Czech conclusion. Offline tests use mocked provider responses and spend no API credits.
5. Approve one low-risk exact repair; test backup gate, stale-plan rejection, resulting function, failure notification and follow-up. A general positive functional-test executor for arbitrary repairs is still missing; elapsed quiet time is not success.
6. Core restart/bootloop, RAM during install vs sustained pressure, and source-coverage consistency on actual HAOS. Per-process RAM, universal repair generation, complete raw historical-day log retrieval and all connector runtime versions are not guaranteed by this candidate.

## Sources

Read APIs follow [HA REST history/state](https://developers.home-assistant.io/docs/api/rest/) and [Supervisor endpoints](https://developers.home-assistant.io/docs/api/supervisor/endpoints/). [Recorder exclusion](https://www.home-assistant.io/integrations/history/) can mean no history. The AI loop follows [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling). OneDrive source references and setup are in [companion/README.md](companion/README.md).

Automated check counts and artifact hashes are emitted by the build; consult the generated verification JSON rather than treating this document as a live-system test report.
