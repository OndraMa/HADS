"""Non-installed writer for the disconnected, ephemeral Core laboratory only.

This is deliberately outside src/ and the HAOS package. It reuses HADS' approval
authority, immutable plans, durable intents, locks and replay protection. It is
not a production HA writer: Core's config API has no compare-and-swap contract.
"""
import json
import os
import re
from urllib.request import ProxyHandler, Request, build_opener

from hads_next.repair import RepairBlocked, RepairEngine, canonical
from hads_next.observability import MAX_BYTES, _NoRedirect


class CoreLabRepairEngine(RepairEngine):
    _operation = "core_lab.replace_entity_reference"
    _risk = "low_disconnected_virtual_core_only"
    _snapshot_scope = "single_virtual_automation_not_HAOS"
    _preconditions = ('exact_original_sha256', 'disconnected_loopback_core', 'session_nonce_identity',
        'single_virtual_automation', 'exclusive_ephemeral_configuration', 'unexpired_owner_approval')
    FILENAME = "hads_lab_reference.json"
    ENDPOINT = "/api/config/automation/config/hads_lab_reference"
    MISSING = "input_boolean.hads_lab_missing"
    TARGET = "input_boolean.hads_lab_target"

    def __init__(self, db_path, isolated_root, *, nonce, token, owner):
        # No caller-supplied URL, path, service or arbitrary automation target.
        if not re.fullmatch(r"[a-f0-9]{32}", nonce):
            raise RepairBlocked("Neplatná identita jednorázové Core laboratoře.")
        with open('/proc/net/route') as file:
            route = file.read().splitlines()[1:]
        with open('/proc/self/status') as file:
            status = dict(line.split(':', 1) for line in file if ':' in line)
        if route or set(os.listdir('/sys/class/net')) != {'lo'} or os.geteuid() == 0 \
                or int(status['CapEff'].strip(), 16) != 0 or status['NoNewPrivs'].strip() != '1' \
                or not (os.statvfs('/').f_flag & os.ST_RDONLY):
            raise RepairBlocked("Zápis je povolen pouze v odpojené laboratoři s read-only rootem.")
        self._nonce, self._token = nonce, token
        self._opener = build_opener(ProxyHandler({}), _NoRedirect)
        super().__init__(db_path, isolated_root, allowed_files={self.FILENAME}, owner=owner)
        self._assert_identity()

    def _request(self, path, content=None):
        request = Request('http://127.0.0.1:8123' + path,
            data=None if content is None else canonical(content).encode(),
            headers={'Authorization': 'Bearer ' + self._token, 'Content-Type': 'application/json'},
            method='GET' if content is None else 'POST')
        try:
            with self._opener.open(request, timeout=10) as response:
                data = response.read(MAX_BYTES + 1)
                if response.status != 200 or len(data) > MAX_BYTES:
                    raise RepairBlocked("Core laboratoř odmítla požadavek.")
                return json.loads(data)
        except Exception:
            raise RepairBlocked("Požadavek na Core laboratoř selhal; žádný automatický retry zápisu.") from None

    def _assert_identity(self):
        config = self._request('/api/config')
        if config.get('version') != '2026.11.0' or config.get('location_name') != 'HADS isolated lab ' + self._nonce:
            raise RepairBlocked("Cíl není právě vytvořená jednorázová Core laboratoř.")

    def _read(self, filename):
        if filename != self.FILENAME:
            raise RepairBlocked("Nepovolený laboratorní cíl.")
        self._assert_identity()
        document = self._request(self.ENDPOINT)
        self._entity(document)
        return canonical(document).encode()

    def _target_metadata(self, filename, original):
        return {**super()._target_metadata(filename, original),
            'api_path': self.ENDPOINT, 'origin': 'http://127.0.0.1:8123', 'lab_nonce': self._nonce}

    @staticmethod
    def _entity(document):
        try:
            if document['id'] != 'hads_lab_reference' or document['conditions'] != [] \
                    or document['triggers'] != [{'trigger': 'state', 'entity_id': 'input_button.hads_lab_run'}] \
                    or len(document['actions']) != 1:
                raise ValueError()
            action = document['actions'][0]
            entity = action['target']['entity_id']
            if set(action) != {'action', 'target'} or action['action'] != 'input_boolean.turn_on' \
                    or set(action['target']) != {'entity_id'} \
                    or entity not in {CoreLabRepairEngine.MISSING, CoreLabRepairEngine.TARGET}:
                raise ValueError()
            return entity
        except (KeyError, TypeError, ValueError):
            raise RepairBlocked("Podporována je jen jedna vlastní laboratorní automatizace s virtuálním cílem.") from None

    @classmethod
    def _change_entity(cls, document, new_entity_id):
        cls._entity(document)
        changed = json.loads(canonical(document))
        changed['actions'][0]['target']['entity_id'] = new_entity_id
        cls._entity(changed)
        return changed

    def _replace(self, filename, content):
        if filename != self.FILENAME:
            raise RepairBlocked("Nepovolený laboratorní cíl.")
        self._assert_identity()
        document = json.loads(content)
        self._entity(document)
        result = self._request(self.ENDPOINT, document)
        if result != {'result': 'ok'}:
            raise RepairBlocked("Core nepotvrdilo uložení laboratorní automatizace.")

    def _manual_alternative(self, filename, expected_old, new_entity_id):
        return f"Pouze v jednorázové Core laboratoři změň cíl automatizace hads_lab_reference " \
               f"z {expected_old} na {new_entity_id}. Spusť testovací tlačítko a ověř virtuální cíl."
