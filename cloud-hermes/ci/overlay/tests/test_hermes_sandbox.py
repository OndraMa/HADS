"""Offline regressions; actual syscall denials are tested in ARM64 Docker."""
import os
from pathlib import Path
import unittest
from unittest import mock
import hermes_sandbox as sandbox
import hermes_bridge as bridge


class SandboxTests(unittest.TestCase):
    def test_unsupported_os_fails_before_any_isolation_changes(self):
        with mock.patch.object(sandbox.sys, 'platform', 'win32'), mock.patch.object(sandbox.os, 'chroot', create=True) as change:
            with self.assertRaises(RuntimeError):
                sandbox.platform_check()
            change.assert_not_called()

    def test_worker_environment_does_not_inherit_broker_fd_or_tokens(self):
        with mock.patch.dict(os.environ, {'HADS_BROKER_FD': '9', 'SUPERVISOR_TOKEN': 'test', 'OPENAI_API_KEY': 'test'}):
            env = bridge.worker_environment(Path('/opt/hermes-root/tmp/hads-hermes-example'))
        self.assertNotIn('HADS_BROKER_FD', env)
        self.assertNotIn('SUPERVISOR_TOKEN', env)
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertEqual('/tmp/hads-hermes-example', env['HOME'])

    def test_no_landlock_or_namespace_fallback_and_no_new_sockets(self):
        source = Path(sandbox.__file__).read_text(encoding='utf-8')
        allowed = source.split("names = '''", 1)[1].split("'''.split()", 1)[0].split()
        for syscall in ('socket', 'connect', 'socketpair', 'execve', 'fork', 'vfork', 'chroot', 'mount', 'ptrace', 'bpf', 'io_uring_setup', 'process_vm_readv'):
            self.assertNotIn(syscall, allowed)
        self.assertIn('seccomp_rule_add_array', source)
        self.assertIn('os.setresuid(UID, UID, UID)', source)
        self.assertIn('resource.RLIMIT_AS', source)

    def test_adapter_only_accepts_original_connected_broker_once(self):
        with mock.patch.dict(os.environ, {'HADS_BROKER_FD': '42'}), mock.patch.object(sandbox.socket, 'create_connection'), mock.patch.object(sandbox.os, 'dup', return_value=43), mock.patch.object(sandbox.socket, 'socket') as sock:
            sandbox.install_broker_socket_adapter(12345)
            with self.assertRaises(PermissionError):
                sandbox.socket.create_connection(('example.org', 443))
            sandbox.socket.create_connection(('127.0.0.1', 12345), timeout=3)
            sock.assert_called_once_with(fileno=42)
            with self.assertRaises(PermissionError):
                sandbox.socket.create_connection(('127.0.0.1', 12345))
