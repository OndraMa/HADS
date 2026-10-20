"""HTTPX's public transport interface over exactly one inherited broker FD.

The official OpenAI SDK and actual Hermes conversation loop are retained.
No dialing, DNS, TLS bypass to external servers, redirects, or extra API calls.
"""
import http.client
import os
import socket
import threading


def client_factory(port):
    import httpx
    descriptor = int(os.environ['HADS_BROKER_FD'])
    lock = threading.Lock()
    used = False
    maximum = 128 * 1024

    class BrokerTransport(httpx.BaseTransport):
        def handle_request(self, request):
            nonlocal used
            url = request.url
            if url.scheme != 'http' or url.host != '127.0.0.1' or url.port != int(port):
                raise httpx.ConnectError('HADS broker origin cannot be changed', request=request)
            if request.method != 'POST' or url.raw_path != b'/v1/chat/completions':
                # Discovery is unavailable, not evidence of a healthy model.
                return httpx.Response(403, json={'error': {'message': 'HADS exposes no model discovery or alternate endpoints'}}, request=request)
            data = request.read()
            if not 0 < len(data) <= maximum:
                raise httpx.WriteError('HADS model request exceeds its bound', request=request)
            with lock:
                if used:
                    raise httpx.ConnectError('A HADS reasoning step allows one model request, no transport retry', request=request)
                used = True
            headers = {key.decode('ascii'): value.decode('latin-1') for key, value in request.headers.raw
                       if key.lower() not in {b'host', b'content-length', b'transfer-encoding', b'connection'}}
            connection = http.client.HTTPConnection('127.0.0.1', int(port), timeout=60)
            # Wrap the inherited, parent-connected endpoint. No socket() syscall.
            connection.sock = socket.socket(fileno=descriptor)
            connection.sock.settimeout(60)
            try:
                connection.request('POST', '/v1/chat/completions', body=data, headers=headers)
                reply = connection.getresponse()
                content = reply.read(maximum + 1)
                if len(content) > maximum:
                    raise httpx.ReadError('HADS model response exceeds its bound', request=request)
                return httpx.Response(reply.status, headers=reply.getheaders(), content=content, request=request)
            except (OSError, http.client.HTTPException) as error:
                raise httpx.ConnectError('Inherited HADS broker exchange failed: ' + type(error).__name__, request=request) from error
            finally:
                connection.close()

        def close(self):
            # SDK client wrappers may close independently. No open connection is
            # created until the sole request; that request owns its descriptor.
            pass

    def make_client(*args, **kwargs):
        return httpx.Client(transport=BrokerTransport(), timeout=60, trust_env=False)
    return make_client
