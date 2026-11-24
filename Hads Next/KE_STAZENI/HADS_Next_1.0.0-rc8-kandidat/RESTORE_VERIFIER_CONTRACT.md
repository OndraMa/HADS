# Consumer contract for an independent OneDrive restoration verifier

HADS now implements the receiving integration: private HTTPS configuration, a pinned
independently obtained Ed25519 public key, bounded authenticated retrieval, signature/target/scope/time
validation and a private atomic receipt cache. It does not issue its own signature.

This is a **HADS-owned consumer contract**, not a claim that HABS exposes an endpoint with this shape.
No usable HABS restoration-verifier API or deployed independent signer was identified during this work.
An independent verifier must actually implement this contract or publish the existing signed receipt
at an exact HTTPS resource configured by the operator. Merely configuring a URL does not finish that service.

The controller makes `GET <exact configured resource>` with `Accept: application/json`,
`HADS-Target-SHA256: <canonical original target snapshot hash>` and optional Bearer authorization.
It follows no redirects, verifies TLS, limits the response to 16,000 bytes and eight seconds per socket.
URLs/tokens are never sent to the analyst or public status. There is no invented `/habs/verify` path.

Response: the existing schema-1 envelope `{"attestation": {...}, "signature": "<base64 Ed25519>"}`.
The signature covers UTF-8 `canonical(attestation)` (sorted keys, compact JSON, no NaN).
The attestation requires `storage: "OneDrive"`, `restored: true`,
`scope: "HAOS_config_and_registry"`, a non-HADS independent `verifier`, the exact
`target_sha256`, the complete `backup_sha256`, `verified_at` and `expires_at`.
Verification must be no older than 24 hours, not in the future, and expire within 24 hours of verification.
The public-key fingerprint also becomes part of the approved plan's proof binding.

The independent operator must prove that the identified OneDrive object was retrieved,
the hash matched, restoration in an isolated HAOS succeeded and the restored configuration/registry
covered the original target. Upload success, metadata, an extracted YAML file or a CI signature do not meet this.
No production restore or backup mutation is performed by the receiving adapter.

Configure once in **Nastavení / Ověřovatel záloh** using the real verifier resource and a public key
verified through an independent trusted route. The public key is not a private signing key.
The form requires a fresh authenticated owner and CSRF. The model cannot configure trust.
Bad TLS, HTTP errors, wrong signatures, wrong targets, upload-only scope and expired receipts fail closed.
No receipt from tests may be imported as production trust. Actual independent restoration remains a live blocker.
