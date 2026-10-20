"""Private immutable filesystem + unprivileged UID + seccomp allowlist.

No Landlock, namespaces, Docker socket or privileged-container dependency.
The sole network descriptor is connected by the trusted parent before launch.
Python's socket adapter is compatibility glue, NOT the security boundary.
"""
from contextlib import contextmanager
import ctypes
import errno
import os
from pathlib import Path
import platform
try:
    import resource
except ImportError:  # Offline unit-test import on Windows, never an execution fallback.
    resource = None
import socket
import stat
import sys
import tempfile

ROOT = Path('/opt/hermes-root')
ADDRESS_SPACE = 384 * 1024 * 1024
UID = 65534


def platform_check():
    if sys.platform != 'linux' or platform.machine() not in {'aarch64', 'arm64', 'x86_64'} or sys.maxsize <= 2**32:
        raise RuntimeError('Hermes sandbox requires 64bit Linux aarch64/amd64')
    if os.geteuid() != 0:
        raise RuntimeError('Trusted launcher requires root; worker always drops root')


def _remove_at(parent, name):
    """Reclaim ownership before entering worker-created mode-000 directories.

    fd-relative operations never follow worker symlinks. Only invoked after
    the worker exited; no surviving fork is allowed by its syscall filter.
    """
    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if stat.S_ISDIR(info.st_mode):
        os.chown(name, 0, 0, dir_fd=parent, follow_symlinks=False)
        os.chmod(name, 0o700, dir_fd=parent, follow_symlinks=False)
        child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            os.fchmod(child, 0o700)
            for entry in os.listdir(child):
                _remove_at(child, entry)
        finally:
            os.close(child)
        os.rmdir(name, dir_fd=parent)
    else:
        os.unlink(name, dir_fd=parent)


@contextmanager
def private_home():
    platform_check()
    base = ROOT / 'tmp'
    if ROOT.is_symlink() or ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o022:
        raise RuntimeError('Sandbox image root is not immutable to worker UID')
    if not base.is_dir() or base.is_symlink():
        raise RuntimeError('Sandbox private temporary storage is missing')
    directory = Path(tempfile.mkdtemp(prefix='hads-hermes-', dir=base))
    os.chmod(directory, 0o700)
    os.chown(directory, UID, UID)
    try:
        yield directory
    finally:
        if directory.parent != base or not directory.name.startswith('hads-hermes-'):
            raise RuntimeError('Refusing cleanup outside worker temporary root')
        fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            _remove_at(fd, directory.name)
        finally:
            os.close(fd)


def seccomp_filter():
    """libseccomp handles native-architecture checking; unknown calls denied."""
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
    allow = 0x7fff0000
    ctx = lib.seccomp_init(0x00050000 | errno.EPERM)
    if not ctx:
        raise RuntimeError('Cannot initialize seccomp allowlist')
    names = '''read write close close_range lseek pread64 pwrite64 readv writev
        open openat fstat stat lstat newfstatat statx access faccessat faccessat2
        mmap mmap2 mprotect munmap brk mremap madvise membarrier
        futex futex_waitv rseq set_robust_list get_robust_list
        clock_gettime clock_getres gettimeofday time nanosleep clock_nanosleep
        getpid getppid gettid getuid geteuid getgid getegid getgroups
        uname sysinfo getrandom prlimit64 getrlimit getrusage
        rt_sigaction rt_sigprocmask rt_sigreturn rt_sigtimedwait sigaltstack
        getcwd chdir fchdir getdents getdents64 readlink readlinkat
        fcntl ioctl dup dup2 dup3 poll ppoll select pselect6
        epoll_create epoll_create1 epoll_ctl epoll_wait epoll_pwait epoll_pwait2
        fsync fdatasync ftruncate truncate mkdir mkdirat unlink unlinkat
        rename renameat renameat2 rmdir chmod fchmod fchmodat fchmodat2
        utime utimes utimensat sched_yield sched_getaffinity sched_getparam
        sched_getscheduler sched_get_priority_max sched_get_priority_min getpriority getcpu
        getsockname getpeername getsockopt setsockopt recvfrom sendto
        recvmsg sendmsg shutdown exit exit_group restart_syscall'''.split()
    try:
        for name in names:
            number = lib.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and lib.seccomp_rule_add(ctx, allow, number, 0) != 0:
                raise RuntimeError('Cannot add syscall allow rule: ' + name)
        # libc's clone3 fallback needs ENOSYS rather than EPERM. clone itself
        # only permits threads sharing VM/signal handlers; namespaces forbidden.
        clone3 = lib.seccomp_syscall_resolve_name(b'clone3')
        if clone3 >= 0 and lib.seccomp_rule_add(ctx, 0x00050000 | errno.ENOSYS, clone3, 0) != 0:
            raise RuntimeError('Cannot deny clone3')
        class Arg(ctypes.Structure):
            _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_int), ('a', ctypes.c_uint64), ('b', ctypes.c_uint64)]
        lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(Arg)]
        lib.seccomp_rule_add_array.restype = ctypes.c_int
        conditions = (Arg * 1)(Arg(0, 7, 0x7e030980, 0x10900))
        if lib.seccomp_rule_add_array(ctx, allow, lib.seccomp_syscall_resolve_name(b'clone'), 1, conditions) != 0:
            raise RuntimeError('Cannot constrain thread creation')
        # Additional filters can only restrict further, never undo this one.
        # libseccomp uses these queries when installing the inference write seal.
        for name, operations in (('seccomp', (1, 2, 3)), ('prctl', (21, 22, 38, 39))):
            number = lib.seccomp_syscall_resolve_name(name.encode())
            for operation in operations:
                condition = Arg(0, 4, operation, 0)
                if lib.seccomp_rule_add_array(ctx, allow, number, 1, ctypes.byref(condition)) != 0:
                    raise RuntimeError('Cannot allow additive sandbox hardening')
        if lib.seccomp_load(ctx) != 0:
            raise RuntimeError('Kernel/security profile rejected seccomp allowlist')
    finally:
        lib.seccomp_release(ctx)


def confine(home, port):
    platform_check()
    inside = Path(home)
    if inside.parent != Path('/tmp') or not inside.name.startswith('hads-hermes-'):
        raise RuntimeError('Invalid worker home')
    fd = int(os.environ['HADS_BROKER_FD'])
    if fd < 3:
        raise RuntimeError('Invalid inherited broker descriptor')
    with socket.socket(fileno=os.dup(fd)) as broker:
        if broker.getpeername() != ('127.0.0.1', int(port)):
            raise RuntimeError('Inherited descriptor is not the authorized broker')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError('Cannot set no_new_privs')
    os.chroot(ROOT)
    os.chdir('/')
    os.nice(10)
    os.setgroups([])
    os.setresgid(UID, UID, UID)
    os.setresuid(UID, UID, UID)
    if os.getresuid() != (UID, UID, UID) or os.getresgid() != (UID, UID, UID):
        raise RuntimeError('Worker retained elevated identity')
    class CapHeader(ctypes.Structure):
        _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
    class CapData(ctypes.Structure):
        _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32), ('inheritable', ctypes.c_uint32)]
    header, capabilities = CapHeader(0x20080522, 0), (CapData * 2)()
    if libc.capget(ctypes.byref(header), capabilities) != 0 or any(c.effective or c.permitted or c.inheritable for c in capabilities):
        raise RuntimeError('Worker retained Linux capabilities')
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE, ADDRESS_SPACE))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    os.umask(0o077)
    seccomp_filter()
    os.chdir(inside)


def install_broker_socket_adapter(port):
    """Retain upstream HTTPX/OpenAI SDK; replace dialing with a connected FD.

    seccomp forbids socket/connect/socketpair even if this adapter is bypassed.
    The parent broker independently enforces authentication, schema and one call.
    """
    fd = int(os.environ['HADS_BROKER_FD'])
    used = False
    def connect(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, **kwargs):
        nonlocal used
        if used or address != ('127.0.0.1', int(port)) or source_address is not None:
            raise PermissionError('Only one inherited HADS broker connection is available')
        used = True
        result = socket.socket(fileno=fd)
        if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            result.settimeout(timeout)
        return result
    socket.create_connection = connect


def seal_filesystem():
    """After trusted bootstrap, inference cannot create/modify disk files.

    Existing stdout/stderr are the result/null protocol. SDK socket.send uses
    sendto on the sole inherited TCP connection. Descriptor duplication and
    writable opens are blocked so files cannot be moved onto stdout/stderr.
    """
    lib = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    class Arg(ctypes.Structure):
        _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_int), ('a', ctypes.c_uint64), ('b', ctypes.c_uint64)]
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(Arg)]
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    deny = 0x00050000 | errno.EPERM
    ctx = lib.seccomp_init(0x7fff0000)
    if not ctx:
        raise RuntimeError('Cannot initialize inference write seal')
    lib.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    lib.seccomp_attr_set.restype = ctypes.c_int
    if lib.seccomp_attr_set(ctx, 4, 1) != 0:  # SCMP_FLTATR_CTL_TSYNC
        lib.seccomp_release(ctx)
        raise RuntimeError('Cannot synchronize inference seal across threads')
    def rule(name, condition=None):
        number = lib.seccomp_syscall_resolve_name(name.encode())
        if number < 0:
            return
        code = (lib.seccomp_rule_add(ctx, deny, number, 0) if condition is None else
                lib.seccomp_rule_add_array(ctx, deny, number, 1, ctypes.byref(condition)))
        if code:
            raise RuntimeError('Cannot seal inference syscall ' + name)
    try:
        for name in ('mkdir', 'mkdirat', 'unlink', 'unlinkat', 'rmdir', 'rename', 'renameat', 'renameat2',
                     'truncate', 'ftruncate', 'chmod', 'fchmod', 'fchmodat', 'fchmodat2', 'utime', 'utimes', 'utimensat',
                     'pwrite64', 'pwritev', 'pwritev2', 'dup', 'dup2', 'dup3', 'writev'):
            rule(name)
        rule('write', Arg(0, 5, 3, 0))  # fd >= 3, stdout/stderr remain explicit protocol.
        for name, argument in (('open', 1), ('openat', 2)):
            for flag in (os.O_WRONLY, os.O_RDWR, os.O_CREAT, os.O_TRUNC, os.O_APPEND, 0x400000):
                rule(name, Arg(argument, 7, flag, flag))
        # Prevent F_DUPFD / F_DUPFD_CLOEXEC aliases of pre-existing writable FDs.
        rule('fcntl', Arg(1, 4, 0, 0))
        rule('fcntl', Arg(1, 4, 1030, 0))
        if lib.seccomp_load(ctx) != 0:
            raise RuntimeError('Cannot activate inference filesystem write seal')
    finally:
        lib.seccomp_release(ctx)
