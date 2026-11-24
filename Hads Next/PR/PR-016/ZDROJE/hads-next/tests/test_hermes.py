"""Offline negative contracts. Real upstream loop is a separate Docker smoke."""
import os
import unittest
from unittest.mock import patch
from hads_next.investigation import ReadGateway, ReadDenied, native_hermes_investigation

class EvidenceBoundaryTests(unittest.TestCase):
    def test_read_snapshot_and_deduplicate(self):
        original = {'automation': {'target': 'light.old_lamp'}}
        gateway = ReadGateway(original)
        original['automation']['target'] = 'light.changed'
        self.assertIn('light.old_lamp', gateway.read({'source': 'automation'}))
        with self.assertRaises(ReadDenied):
            gateway.read({'source': 'automation'})
        self.assertEqual(len(gateway.receipts), 1)

    def test_redact_before_model_and_hash(self):
        gateway = ReadGateway({'trace': {'password': 'secret-value',
             'nested': [{'api_key': 'secret-key'}], 'log': 'Authorization: Bearer abcdef'}})
        result = gateway.read({'source': 'trace'})
        for secret in ('secret-value', 'secret-key', 'abcdef'):
            self.assertNotIn(secret, result)
        self.assertIn('[redacted]', result)

    def test_all_write_and_escape_requests_denied(self):
        gateway = ReadGateway({'trace': {}})
        for request in ({'source': 'shell'}, {'source': 'trace', 'command': 'rm'},
                        {'source': 'http://supervisor/core/restart'},
                        {'source': '../data/options.json'}, {'source': []}, []):
            with self.subTest(request=request), self.assertRaises(ReadDenied):
                gateway.read(request)
        self.assertEqual(gateway.receipts, [])

    def test_budget_and_size_fail_closed(self):
        gateway = ReadGateway({'one': {}, 'two': {}}, max_reads=1)
        gateway.read({'source': 'one'})
        with self.assertRaises(ReadDenied):
            gateway.read({'source': 'two'})
        gateway = ReadGateway({'large': 'x'*100}, max_bytes=20)
        with self.assertRaises(ReadDenied):
            gateway.read({'source': 'large'})
        self.assertEqual(gateway.receipts, [])

    def test_no_automatic_paid_or_unconfined_runtime(self):
        gateway = ReadGateway({'trace': {}})
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            native_hermes_investigation(gateway, base_url='http://127.0.0.1:1234/v1')
        with patch.dict(os.environ, {'HADS_ISOLATED_TEST': '1'}, clear=True):
            for url in ('https://api.openai.com/v1', 'http://supervisor:80', 'file:///tmp/model'):
                with self.subTest(url=url), self.assertRaises(RuntimeError):
                    native_hermes_investigation(gateway, base_url=url)

if __name__ == '__main__':
    unittest.main()
