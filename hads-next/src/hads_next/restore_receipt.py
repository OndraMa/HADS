"""Verify an independent restore attestation; the investigator cannot issue one.

A local target snapshot or successful OneDrive upload is NOT this receipt.
Only a separately provisioned public verifier key can validate an attestation
covering the original target and a real restored HAOS/config+registry backup.
"""
import base64
import json
from .tool_registry import ToolDenied
from .evidence import canonical

class RestoreReceiptVerifier:
    def __init__(self,data_dir,clock):self.root=data_dir;self.clock=clock
    def verify(self,target_hash):
        key=self.root/'backup-verifier.pub';receipt=self.root/'restore-attestation.json'
        for p in (key,receipt):
            if p.is_symlink() or not p.is_file() or p.stat().st_size>16000 or p.stat().st_mode&0o077:
                raise ToolDenied('Chybí nezávisle ověřená obnovitelná OneDrive záloha. Samotný snapshot nebo upload nestačí.')
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            envelope=json.loads(receipt.read_text());value=envelope['attestation']
            public=Ed25519PublicKey.from_public_bytes(base64.b64decode(key.read_text(),validate=True))
            public.verify(base64.b64decode(envelope['signature'],validate=True),canonical(value).encode())
            if value['schema']!=1 or value['storage']!='OneDrive' or value['restored'] is not True or value['scope']!='HAOS_config_and_registry' or value['verifier']=='HADS' or not value['verifier'] or value['target_sha256']!=target_hash or not self.clock()-86400<=value['verified_at']<=self.clock() or not self.clock()<value['expires_at']<=value['verified_at']+86400 or len(value['backup_sha256'])!=64:raise ValueError()
            return value
        except Exception:raise ToolDenied('Podpis, rozsah, stáří nebo vazba důkazu obnovitelnosti není platná.') from None
