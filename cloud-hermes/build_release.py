from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import pathlib
import re
import tarfile
import zipfile
from run_checks import run_checks


VERSION = "2.0.0-rc3"
HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "src"
OUTPUT = HERE.parents[1] / "outputs"
TEMPLATE = OUTPUT / "HADS4_install_4.5.0.sh"


def included_files() -> list[pathlib.Path]:
    result = []
    for path in SOURCE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(SOURCE)
        if "__pycache__" in relative.parts or ".test-tmp" in relative.parts or path.suffix == ".pyc":
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(SOURCE).as_posix())


def tar_payload(files: list[pathlib.Path]) -> bytes:
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            relative = path.relative_to(SOURCE).as_posix()
            data = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9) as stream:
        stream.write(raw_tar.getvalue())
    return compressed.getvalue()


def source_zip(files: list[pathlib.Path], destination: pathlib.Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(SOURCE).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 9, 3, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def installer(payload: bytes, destination: pathlib.Path) -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    template = template.replace("4.5.0", VERSION)
    # Explicit user-requested installer variant: no HA backup or cloud gate.
    # Runtime repair backup requirements remain unchanged.
    start_backup = template.index("echo 'Vytvářím povinnou plnou HA zálohu")
    end_backup = template.index('EXISTING=0\n', start_backup)
    template = template[:start_backup] + (
        "echo 'Instalace na výslovnou žádost bez nové HA/OneDrive zálohy. Místní kopie zdrojů není záloha databáze ani celého systému.'\n"
        'python3 "$STAGING/addon/install_guard.py" access\n\n'
    ) + template[end_backup:]
    template = template.replace('Předinstalační HA záloha: $BACKUP_SLUG', 'Nová předinstalační HA/OneDrive záloha nebyla vytvořena.')
    template = template.replace('python3 "$STAGING/addon/install_guard.py" access\n',
        'python3 "$STAGING/addon/hermes_preflight.py"\npython3 "$STAGING/addon/install_guard.py" access\n', 1)
    old = 'ha addons reload\nif [ "$EXISTING" = 1 ]; then\n  ha addons rebuild local_hads4\nelse\n  ha addons install local_hads4\nfi\nha addons start local_hads4'
    if old not in template:
        raise ValueError('Installer upgrade block no longer matches; refusing an unreviewed installer.')
    template = template.replace(old, 'python3 "$TARGET/install_guard.py" update "$VERSION" "$EXISTING"', 1)
    template = template.replace("Obnovte panel Ctrl+F5 a spusťte hlubokou analýzu. Funkčnost oprav ověřte na jednom konkrétním plánu.", "Obnovte panel Ctrl+F5. Nejprve ověřte paměťovou rezervu a první snapshot. Placenou AI zatím nezapínejte; tato RC vyžaduje kontrolu na HAOS.")
    digest = hashlib.sha256(payload).hexdigest()
    template = re.sub(r'EXPECTED_SHA256="[0-9a-f]{64}"', f'EXPECTED_SHA256="{digest}"', template, count=1)
    begin = "base64 -d > \"$STAGING/hads4.tar.gz\" <<'HADS4_PAYLOAD'\n"
    start = template.index(begin) + len(begin)
    end = template.index("\nHADS4_PAYLOAD\n", start)
    encoded = base64.b64encode(payload).decode("ascii")
    wrapped = "\n".join(encoded[index:index + 76] for index in range(0, len(encoded), 76))
    destination.write_text(template[:start] + wrapped + template[end:], encoding="utf-8", newline="\n")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    checks = run_checks()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = included_files()
    payload = tar_payload(files)
    install_path = OUTPUT / f"HADS_Hermes_install_{VERSION}.sh"
    zip_path = OUTPUT / f"HADS_Hermes_{VERSION}-source.zip"
    hash_path = OUTPUT / f"HADS_Hermes_{VERSION}-SHA256.txt"
    verification_path = OUTPUT / f"HADS_Hermes_{VERSION}-verification.json"
    manual_path = OUTPUT / f"HADS_Hermes_{VERSION}-manual-CS.md"
    notes_path = OUTPUT / f"HADS_Hermes_{VERSION}-release.md"
    mcp_guide = OUTPUT / f"HADS_Hermes_{VERSION}-HA-MCP-nastaveni-CS.md"
    manual_path.write_bytes((SOURCE / f"MANUAL_{VERSION}_CS.md").read_bytes())
    notes_path.write_bytes((SOURCE / f"RELEASE_{VERSION}.md").read_bytes())
    mcp_guide.write_bytes((SOURCE / "HA_MCP_NASTAVENI_CS.md").read_bytes())
    installer(payload, install_path)
    source_zip(files, zip_path)
    companion_path = OUTPUT / "HADS_Rescue_Readback_0.1.0.zip"
    with zipfile.ZipFile(companion_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            if path.is_relative_to(SOURCE / "companion"):
                info = zipfile.ZipInfo(path.relative_to(SOURCE / "companion").as_posix(), (2026, 9, 14, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())

    text = install_path.read_text(encoding="utf-8")
    match = re.search(r"HADS4_PAYLOAD'\n(?P<data>[A-Za-z0-9+/=\n]+)\nHADS4_PAYLOAD\n", text)
    if not match:
        raise SystemExit("Embedded payload marker was not found")
    embedded = base64.b64decode(match.group("data"))
    if embedded != payload:
        raise SystemExit("Embedded payload differs from built payload")
    expected = {path.relative_to(SOURCE).as_posix(): sha256(path) for path in files}
    actual: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(embedded), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            if member.name.startswith("/") or ".." in pathlib.PurePosixPath(member.name).parts:
                raise SystemExit(f"Unsafe payload member: {member.name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise SystemExit(f"Unreadable payload member: {member.name}")
            actual[member.name] = hashlib.sha256(stream.read()).hexdigest()
    if actual != expected:
        raise SystemExit("Extracted payload is not byte-identical to source")

    hashes = (
        f"{sha256(install_path)}  {install_path.name}\n"
        f"{sha256(zip_path)}  {zip_path.name}\n"
        f"{sha256(manual_path)}  {manual_path.name}\n"
        f"{sha256(notes_path)}  {notes_path.name}\n"
        f"{sha256(mcp_guide)}  {mcp_guide.name}\n"
        f"{sha256(companion_path)}  {companion_path.name}\n"
        f"{hashlib.sha256(payload).hexdigest()}  HADS4_{VERSION}-payload.tar.gz\n"
    )
    hash_path.write_text(hashes, encoding="utf-8", newline="\n")
    verification = {
        "version": VERSION,
        "installer_backup_policy": "no_preinstall_ha_or_cloud_backup_user_requested",
        "source_files": len(files),
        **checks,
        "installer_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "embedded_payload_matches": True,
        "extracted_payload_matches_source": True,
        "excluded_from_package": ["__pycache__", "*.pyc", ".test-tmp"],
        "live_haos_test": "not_run_requires_post_install_browser_acceptance",
        "hermes_upstream": {"version": "v0.22.2", "commit": "d923a5eb487a17c0a68801bba9ef0f56c81040a8"},
        "docker_build": "not_run_locally_no_docker; build_time_real_hermes_smoke_required",
        "cloud_arm64_verification": {
            "result": "not_run_for_rc3_at_build_time",
            "baseline_rc2_url": "https://github.com/OndraMa/HADS/actions/runs/39410665467",
            "note": "RC2 result is not verification of the RC3 payload.",
        },
    }
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"installer": str(install_path), "source": str(zip_path), "manual": str(manual_path), "hashes": str(hash_path), "verification": str(verification_path), "files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
