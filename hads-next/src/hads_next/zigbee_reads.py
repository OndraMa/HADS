"""Positive projections for passive ZHA and one fixed ZHA Toolkit cache read.

Never exports coordinator network settings/backups (which include network keys).
Toolkit zha_devices is called with an immutable field list and no file, event,
command override, RF scan, reconfigure or arbitrary service arguments.
"""
from datetime import datetime
import math
import re

FIELDS = ('ieee', 'device_reg_id', 'lqi', 'rssi', 'last_seen', 'available', 'quirk_applied', 'power_source')
IEEE = re.compile(r'(?:[0-9a-fA-F]{2}:){7}[0-9a-fA-F]{2}')


def project_devices(value, *, toolkit=False):
    if toolkit:
        value = value.get('response') if isinstance(value, dict) else None
        if not isinstance(value, dict) or value.get('success') is not True or value.get('errors') != []:
            raise ValueError('toolkit_diagnostic_failed')
        if value.get('command', 'zha_devices') != 'zha_devices':
            raise ValueError('unexpected_toolkit_response')
        value = value.get('devices')
    if not isinstance(value, list) or len(value) > 2000:
        raise ValueError('invalid_zigbee_device_list')
    result = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get('ieee'), str) or not IEEE.fullmatch(item['ieee']):
            raise ValueError('invalid_zigbee_device')
        row = {'ieee': item['ieee'].lower()}
        device_id = item.get('device_reg_id')
        if isinstance(device_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', device_id):
            row['device_id'] = device_id
        for key in ('available', 'quirk_applied'):
            row[key] = item.get(key) if type(item.get(key)) is bool else None
        for key, low, high in (('lqi', 0, 255), ('rssi', -150, 30)):
            number = item.get(key)
            row[key] = number if type(number) in {int, float} and math.isfinite(number) and low <= number <= high else None
        stamp = item.get('last_seen')
        if isinstance(stamp, str):
            try:
                parsed = datetime.fromisoformat(stamp)
                stamp = parsed.timestamp() if parsed.tzinfo else None
            except (ValueError, OverflowError): stamp = None
        row['last_seen'] = stamp if type(stamp) in {int, float} and math.isfinite(stamp) and stamp >= 0 else None
        result.append(row)
    return result


def toolkit_request():
    return {'type': 'call_service', 'domain': 'zha_toolkit', 'service': 'zha_devices',
            'service_data': {'command_data': list(FIELDS)}, 'return_response': True}


def toolkit_response(value):
    devices=project_devices(value,toolkit=True)
    version=value['response'].get('zha_toolkit_version')
    return {'devices':devices,'version':version if isinstance(version,str) and re.fullmatch(r'[A-Za-z0-9_.+-]{1,50}',version) else None}
