"""Layer an ENOSYS Landlock profile over Docker's normal seccomp policy.

This only removes Landlock functionality; it does not relax Docker, chroot,
UID or worker seccomp restrictions. Runs a local fake model, never paid API.
"""
import ctypes
import errno
import json
import runpy

lib = ctypes.CDLL('libseccomp.so.2', use_errno=True)
lib.seccomp_init.argtypes = [ctypes.c_uint32]
lib.seccomp_init.restype = ctypes.c_void_p
lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
lib.seccomp_rule_add.restype = ctypes.c_int
lib.seccomp_load.argtypes = [ctypes.c_void_p]
lib.seccomp_load.restype = ctypes.c_int
lib.seccomp_release.argtypes = [ctypes.c_void_p]
ctx = lib.seccomp_init(0x7fff0000)
assert ctx
try:
    for name in (b'landlock_create_ruleset', b'landlock_add_rule', b'landlock_restrict_self'):
        number = lib.seccomp_syscall_resolve_name(name)
        assert number >= 0
        assert lib.seccomp_rule_add(ctx, 0x00050000 | errno.ENOSYS, number, 0) == 0
    assert lib.seccomp_load(ctx) == 0
finally:
    lib.seccomp_release(ctx)
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
abi = libc.syscall(444, 0, 0, 1)
assert abi == -1 and ctypes.get_errno() == errno.ENOSYS
print(json.dumps({'landlock_abi': abi, 'errno': ctypes.get_errno(), 'profile': 'additive_ENOSYS_no_security_bypass'}))
runpy.run_path('/app/hermes_upstream_smoke.py', run_name='__main__')
