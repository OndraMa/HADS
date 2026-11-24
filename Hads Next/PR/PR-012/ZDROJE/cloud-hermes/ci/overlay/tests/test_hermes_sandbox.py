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

    def test_inference_seal_is_thread_synchronized_and_memory_is_bounded(self):
        source = Path(sandbox.__file__).read_text(encoding='utf-8')
        self.assertEqual(384 * 1048576, sandbox.ADDRESS_SPACE)
        self.assertIn('seccomp_attr_set(ctx, 4, 1)', source)
        self.assertIn("rule('write', Arg(0, 5, 3, 0))", source)
        self.assertNotIn('socket.create_connection =', source)
