"""Verify an independent restore attestation; the investigator cannot issue one.

A local target snapshot or successful OneDrive upload is NOT this receipt.
Only a separately provisioned public verifier key can validate an attestation
covering the original target and a real restored HAOS/config+registry backup.
"""
import base64
import json
import hashlib
import re
from .tool_registry import ToolDenied
from .evidence import canonical

class RestoreReceiptVerifier:
    def __init__(self,data_dir,clock):
        self.root=data_dir;self.clock=clock
        from .restore_connection import RestoreConnection
        self.connection=RestoreConnection(data_dir)

    def status(self):return self.connection.status()

    def _envelope(self,envelope,raw_key,target_hash):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        value=envelope['attestation']
        public=Ed25519PublicKey.from_public_bytes(base64.b64decode(raw_key,validate=True))
        public.verify(base64.b64decode(envelope['signature'],validate=True),canonical(value).encode())
        if value['schema']!=1 or value['storage']!='OneDrive' or value['restored'] is not True or value['scope']!='HAOS_config_and_registry' or value['verifier']=='HADS' or not value['verifier'] or value['target_sha256']!=target_hash or not self.clock()-86400<=value['verified_at']<=self.clock() or not self.clock()<value['expires_at']<=value['verified_at']+86400 or len(value['backup_sha256'])!=64:raise ValueError()
        if not re.fullmatch('[a-f0-9]{64}',value['backup_sha256']):raise ValueError()
        return {**value,'verifier_key_sha256':hashlib.sha256(base64.b64decode(raw_key,validate=True)).hexdigest()}

    def verify(self,target_hash):
        key=self.root/'backup-verifier.pub';receipt=self.root/'restore-attestation.json'
        if key.is_symlink() or not key.is_file() or key.stat().st_size>16000 or key.stat().st_mode&0o077:
            raise ToolDenied('Chybí nezávisle ověřená obnovitelná OneDrive záloha. Samotný snapshot nebo upload nestačí.')
        try:
            if receipt.is_symlink():raise ToolDenied('Neplatná cesta důkazu obnovitelnosti.')
            if receipt.is_file() and receipt.stat().st_size<=16000 and not receipt.stat().st_mode&0o077:
                try:return self._envelope(json.loads(receipt.read_text()),key.read_text(),target_hash)
                except Exception:pass
            envelope=self.connection.fetch(target_hash)
            if envelope is None:raise ValueError()
            value=self._envelope(envelope,key.read_text(),target_hash)
            from .restore_connection import private_write
            private_write(receipt,canonical(envelope))
            return value
        except ToolDenied:raise
        except Exception:raise ToolDenied('Podpis, rozsah, stáří nebo vazba důkazu obnovitelnosti není platná.') from None
