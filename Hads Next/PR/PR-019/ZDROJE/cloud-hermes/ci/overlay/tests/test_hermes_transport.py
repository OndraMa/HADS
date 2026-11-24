import os
import sys
import types
import unittest
from unittest import mock
import hermes_transport as transport


class WireError(Exception):
    def __init__(self, message, **kwargs):
        super().__init__(message)


class TransportTests(unittest.TestCase):
    def test_broker_wait_covers_upstream_but_stays_inside_worker_budget(self):
        self.assertGreater(transport.BROKER_TIMEOUT, 180)
        self.assertLess(transport.BROKER_TIMEOUT, 220)

    def fake_httpx(self):
        return types.SimpleNamespace(BaseTransport=object, ConnectError=WireError,
                WriteError=WireError, ReadError=WireError,
                Client=lambda **kw: types.SimpleNamespace(**kw), Response=mock.Mock())

    def request(self, **changes):
        values = {'url': types.SimpleNamespace(scheme='http', host='127.0.0.1', port=12345, raw_path=b'/v1/chat/completions'),
                  'method': 'POST', 'headers': types.SimpleNamespace(raw=[(b'Authorization', b'Bearer fake-only'), (b'Content-Length', b'999')]),
                  'read': lambda: b'{"messages":[]}'}
        values.update(changes)
        return types.SimpleNamespace(**values)

    def test_real_wire_uses_only_inherited_socket_and_preserves_auth(self):
        module = self.fake_httpx()
        with mock.patch.dict(sys.modules, {'httpx': module}), mock.patch.dict(os.environ, {'HADS_BROKER_FD': '42'}), \
                mock.patch.object(transport.socket, 'socket') as sock, mock.patch.object(transport.http.client, 'HTTPConnection') as connection:
            reply = connection.return_value.getresponse.return_value
            reply.status = 200
            reply.getheaders.return_value = [('Content-Type', 'application/json')]
            reply.read.return_value = b'{}'
            client = transport.client_factory(12345)()
            client.transport.handle_request(self.request())
            sock.assert_called_once_with(fileno=42)
            kwargs = connection.return_value.request.call_args.kwargs
            self.assertEqual({'Authorization': 'Bearer fake-only'}, kwargs['headers'])
            self.assertEqual(b'{"messages":[]}', kwargs['body'])
            self.assertFalse(client.trust_env)
            connection.return_value.close.assert_called_once()
            with self.assertRaises(WireError):
                client.transport.handle_request(self.request())
            self.assertEqual(1, connection.call_count)

    def test_discovery_has_no_network_and_cannot_spend(self):
        module = self.fake_httpx()
        with mock.patch.dict(sys.modules, {'httpx': module}), mock.patch.dict(os.environ, {'HADS_BROKER_FD': '42'}), \
                mock.patch.object(transport.http.client, 'HTTPConnection') as connection:
            client = transport.client_factory(12345)()
            client.transport.handle_request(self.request(method='GET'))
            self.assertEqual(403, module.Response.call_args.args[0])
            connection.assert_not_called()

    def test_external_origin_is_rejected_before_network(self):
        module = self.fake_httpx()
        with mock.patch.dict(sys.modules, {'httpx': module}), mock.patch.dict(os.environ, {'HADS_BROKER_FD': '42'}), \
                mock.patch.object(transport.http.client, 'HTTPConnection') as connection:
            client = transport.client_factory(12345)()
            for host in ('example.org', 'supervisor', 'localhost'):
                url = types.SimpleNamespace(scheme='http', host=host, port=12345, raw_path=b'/v1/chat/completions')
                with self.assertRaises(WireError):
                    client.transport.handle_request(self.request(url=url))
            connection.assert_not_called()

    def test_oversized_body_is_rejected_before_network(self):
        module = self.fake_httpx()
        with mock.patch.dict(sys.modules, {'httpx': module}), mock.patch.dict(os.environ, {'HADS_BROKER_FD': '42'}), \
                mock.patch.object(transport.http.client, 'HTTPConnection') as connection:
            client = transport.client_factory(12345)()
            with self.assertRaises(WireError):
                client.transport.handle_request(self.request(read=lambda: b'x' * (128 * 1024 + 1)))
            connection.assert_not_called()

