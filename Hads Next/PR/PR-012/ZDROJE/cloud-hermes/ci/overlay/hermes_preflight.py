"""Read-only installer preflight before add-on sources are replaced."""
import ctypes
import platform
import sys


def check():
    if sys.platform != "linux" or sys.maxsize <= 2**32 or platform.machine() not in {"aarch64", "x86_64", "arm64"}:
        raise RuntimeError("HADS Hermes vyžaduje 64bit HAOS (aarch64 nebo amd64).")
    # Terminal's syscall/capability profile is not the destination app profile.
    # The actual jailed worker must pass its negative tests BEFORE any API call.
    # No Landlock dependency and no privileged/protection-mode bypass.
    print("64bit Linux ověřen. Hermes používá chroot + UID + seccomp; skutečné ochrany ověří worker v cílovém kontejneru před voláním modelu.")


if __name__ == "__main__":
    try:
        check()
    except Exception as exc:
        print("Instalace Hermes zastavena: " + str(exc), file=sys.stderr)
        sys.exit(1)
