"""Controller consumer of independently signed restoration attestations.

The configured URL is the verifier's exact receipt resource, not an inferred
HABS endpoint. HTTP success or OneDrive metadata never constitutes restoration.
No signing key or restore command is implemented in the HADS analyst process.
"""
import base64
import json
import os
import secrets
from urllib.request import Request, build_opener
from .connector_transport import endpoint
from .observability import _NoRedirect, bounded_body
from .tool_registry import ToolDenied


def private_write(path, value):
    if path.is_symlink():
        raise ToolDenied('Soukromý soubor nesmí být odkaz.')
    temporary = path.with_name('.restore-' + secrets.token_hex(10))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(value); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class RestoreConnection:
    def __init__(self, root):
        self.root = root
        self.path = root / 'restore-verifier-connection.json'
        self.last_error = None

    def settings(self):
        if not self.path.exists():
            return None
        try:
            if self.path.is_symlink() or self.path.stat().st_mode & 0o077 or self.path.stat().st_size > 8192:
                raise ValueError()
            value = json.loads(self.path.read_text())
            if set(value) != {'schema', 'url', 'token'} or value['schema'] != 1:
                raise ValueError()
            endpoint(value['url'])  # HTTPS only, no redirects or embedded credentials.
            if not isinstance(value['token'], str) or len(value['token']) > 4096 or any(ord(c) < 32 for c in value['token']):
                raise ValueError()
            return value
        except (OSError, ValueError, TypeError, KeyError):
            raise ToolDenied('Připojení nezávislého ověřovatele nelze bezpečně načíst.') from None

    def configure(self, url, token, public_key, *, principal, owner):
        if not principal or principal != owner:
            raise ToolDenied('Důvěru k ověřovateli smí nastavit pouze vlastník.')
        url = endpoint(url)
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key.strip(), validate=True))
        except (ValueError, TypeError):
            raise ToolDenied('Ověř veřejný Ed25519 klíč nezávislou důvěryhodnou cestou.') from None
        if not isinstance(token, str) or len(token) > 4096 or any(ord(c) < 32 for c in token):
            raise ToolDenied('Neplatné přístupové údaje.')
        try:previous = self.settings()
        except ToolDenied:previous = None  # Fresh explicit owner configuration can repair a corrupt file.
        if not token and previous and previous['url'] == url:
            token = previous['token']
        private_write(self.root / 'backup-verifier.pub', public_key.strip())
        private_write(self.path, json.dumps({'schema': 1, 'url': url, 'token': token}))
        self.last_error = None

    def fetch(self, target_hash):
        settings = self.settings()
        if settings is None:
            return None
        headers = {'Accept': 'application/json', 'HADS-Target-SHA256': target_hash}
        if settings['token']:
            headers['Authorization'] = 'Bearer ' + settings['token']
        try:
            request = Request(settings['url'], headers=headers)
            with build_opener(_NoRedirect).open(request, timeout=8) as response:
                if response.headers.get_content_type() != 'application/json':
                    raise ValueError()
                value = json.loads(bounded_body(response, 16000, 10))
            self.last_error = None
            return value
        except Exception:
            self.last_error = 'Nezávislý ověřovatel neposkytl podepsaný důkaz pro tento původní stav. Zásah je blokovaný; upload nestačí.'
            raise ToolDenied(self.last_error) from None

    def status(self):
        try:
            configured = self.settings() is not None
        except ToolDenied:
            configured = False
        return {'configured': configured, 'last_error': self.last_error,
                'restoration_verified': False, 'signing_authority': 'external_verifier_only',
                'detail_cs': 'Připojení ověřovatele samo nepotvrzuje obnovu. Platný podpis, původní cíl, rozsah a stáří se ověřují pro každý plán.'}
