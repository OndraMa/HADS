"""Real Hermes native loop + deterministic local model; no inference API costs.

The local model is scripted, so this verifies runtime/tool contracts and the
read/analyse/read cycle, not the quality of an LLM's reasoning. Run in Docker
with no network, no capabilities, read-only root and bounded memory/pids.
"""
import contextlib
import io
import json
import importlib.metadata
import platform
import os
import resource
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

from hads_next.investigation import ReadGateway, native_hermes_investigation

requests = []
ADVERSARIAL = '--adversarial' in sys.argv
ATTACKS = [('terminal', {'command': 'touch /tmp/hads-write-canary'}),
           ('execute_code', {'code': "open('/tmp/hads-write-canary', 'w').write('bypass')"}),
           ('tool_call', {'tool': 'terminal', 'arguments': {'command': 'touch /tmp/hads-write-canary'}})]

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert body['model'] == 'hads-offline'
        assert {t['function']['name'] for t in body['tools']} == {'hads_read_evidence'}
        messages = body['messages']
        tools = [m for m in messages if m['role'] == 'tool']
        requests.append(body)
        index = len(tools)
        if ADVERSARIAL and index < len(ATTACKS):
            name, arguments = ATTACKS[index]
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': f'attack-{index}', 'type': 'function', 'function': {
                    'name': name, 'arguments': json.dumps(arguments)}}]}
            finish = 'tool_calls'
        elif index - (len(ATTACKS) if ADVERSARIAL else 0) < 2:
            index -= len(ATTACKS) if ADVERSARIAL else 0
            if index == 1:
                assert 'light.old_lamp' in tools[len(ATTACKS) if ADVERSARIAL else 0]['content']
            source = ('automation', 'trace')[index]
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': f'evidence-{index}', 'type': 'function', 'function': {
                    'name': 'hads_read_evidence', 'arguments': json.dumps({'source': source})}}]}
            finish = 'tool_calls'
        else:
            assert 'target_not_found' in tools[(len(ATTACKS) if ADVERSARIAL else 0) + 1]['content']
            message = {'role': 'assistant', 'content': 'Automatizace odkazuje na neexistující entitu light.old_lamp. Trace dokládá nedosažený cíl. Připravit přesnou změnu odkazu; nic nebylo opraveno.'}
            finish = 'stop'
        data = json.dumps({'id': f'offline-{len(requests)}', 'object': 'chat.completion',
            'created': 1, 'model': 'hads-offline', 'choices': [{'index': 0, 'message': message,
            'finish_reason': finish}], 'usage': {'prompt_tokens': 20, 'completion_tokens': 20,
            'total_tokens': 40}}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    if os.geteuid() == 0:
        raise RuntimeError('Smoke worker must be unprivileged')
    if Path('/data/options.json').exists() or Path('/homeassistant/configuration.yaml').exists():
        raise RuntimeError('HA mounts are forbidden')
    hermes_home = Path(os.environ['HERMES_HOME'])
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / 'config.yaml').write_text('tools:\n  tool_search:\n    enabled: off\n')
    raw = sys.stdin.read(65537)
    if len(raw) > 65536:
        raise ValueError('Snapshot too large')
    snapshots = json.loads(raw) if raw.strip() else {
        'automation': {'id': 'radio_button', 'target': 'light.old_lamp'},
        'trace': {'automation_id': 'radio_button', 'error': 'target_not_found'}}
    gateway = ReadGateway(snapshots)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        # Upstream logs are not the wire protocol.
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = native_hermes_investigation(gateway,
                    base_url=f'http://127.0.0.1:{server.server_port}/v1',
                    max_iterations=6 if ADVERSARIAL else 4)
        except RuntimeError:
            if not ADVERSARIAL:
                raise
            from hads_next.investigation import HERMES_REVISION
            result = {'engine': 'NousResearch/hermes-agent', 'revision': HERMES_REVISION,
                      'completed': False, 'read_receipts': gateway.receipts,
                      'execution_authority': 'none', 'scope': 'offline-container',
                      'security_outcome': 'native_loop_stopped_after_unapproved_tools'}
        if not ADVERSARIAL:
            assert [r['source'] for r in result['read_receipts']] == ['automation', 'trace']
            assert len(requests) == 3
        assert not Path('/tmp/hads-write-canary').exists(), 'Unapproved write was executed'
        attempts = min(len(requests), len(ATTACKS)) if ADVERSARIAL else 0
        if ADVERSARIAL:
            assert attempts == len(ATTACKS), 'Not all unauthorized tool paths were exercised'
        result['unauthorized_native_tool_attempts_denied'] = attempts
        result['model_requests'] = len(requests)
        result['dependencies'] = sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions())
        result['python_version'] = platform.python_version()
        result['platform'] = platform.machine()
        result['model'] = 'scripted-local-endpoint-no-cost'
        result['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        print(json.dumps(result, ensure_ascii=False))
    finally:
        server.shutdown()

if __name__ == '__main__':
    main()
