# HADS Rescue Readback 0.1.0 — optional Core companion

This component is shipped as source, **not automatically installed or activated** by the HADS add-on installer. It is not part of the add-on container. Do not mistake passing unit tests for a successful test in your Core.

## Why it exists

The official OneDrive integration in Home Assistant Core 2026.9.2 exposes upload and delete, but no independent file-readback service. An upload acknowledgement cannot satisfy HADS's mandatory independent verification gate. The companion reuses the already loaded native OneDrive client's read methods; it does not export OAuth tokens or require another API key.

It downloads exactly the requested ZIP under `HADS/Repairs` (or a subfolder), computes SHA-256 over the received bytes and returns a versioned verification receipt. HADS compares the account entry, folder, filename, size and hash with its local archive. No upload/delete/create/restore methods are called by this component. Administrator-originated calls and HA system contexts are accepted; ordinary users are rejected.

## Installation is a separate explicit operation

1. Back up current HA configuration and retain a working recovery/access path independent of the Core UI.
2. Copy **only** `custom_components/hads_rescue` from this folder to `/config/custom_components/hads_rescue`. If the destination already exists, review and back it up before replacing it.
3. Restart Core only when remote access/recovery is available; stopping Core can disconnect an Ingress-based remote session.
4. Add the **HADS Rescue Readback** integration in HA's integrations UI. Native OneDrive must already be configured and loaded.
5. HADS discovers the exact `hads_rescue.verify` service. It can also be configured explicitly as the rescue verification service.
6. Test readback of an existing small known rescue archive first, without approving a system repair. Compare SHA-256 and test negative cases (missing filename / wrong account). A missing object must keep repairs blocked.

The component is compatible by source inspection with the runtime client in Core **2026.9.2** using `onedrive-personal-sdk==0.1.7`. Other versions, setup/unload, permissions and actual cloud operations require runtime acceptance. It fails closed when the runtime is unavailable/incompatible. Its timeout is 120 seconds and read limit 250 MiB; HADS's configured upload limit may be lower. It does not provide full HA-backup upload, archive rotation, or proof of successful restoration.

## Sources inspected

- [Native OneDrive services, Core 2026.9.2](https://github.com/home-assistant/core/blob/2026.9.2/homeassistant/components/onedrive/services.py)
- [Native OneDrive setup/runtime](https://github.com/home-assistant/core/blob/2026.9.2/homeassistant/components/onedrive/__init__.py)
- [Native backup download streaming](https://github.com/home-assistant/core/blob/2026.9.2/homeassistant/components/onedrive/backup.py)

The verifier streams bytes and retains no downloaded file. Its error response intentionally omits SDK exception text, which may contain a signed download URL. Readback demonstrates that the remote bytes match the local rescue archive; it does **not** establish that all system data is in that archive or that a restore has succeeded.
