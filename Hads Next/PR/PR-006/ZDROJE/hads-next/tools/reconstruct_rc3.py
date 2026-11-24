#!/usr/bin/env python3
"""Verify RC3 bytes and reconstruct reviewable sources without executing installer."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

BASE_COMMIT = 'c491893bd433fa0e17dcd852a3eaa610eb3148ad'
SOURCE_SHA256 = 'fc57575471294dc968d78c4474db2ae1717b6c37b5aba1aab6246799febcf848'
INSTALLER_SHA256 = 'ad2c64db2c6b027e9898636c5c18a6ce5d5c2370d3a96977a07df7fa2d9469da'
PAYLOAD_SHA256 = 'f325d73174a58d5ceaa1b3c9029ad5c7e38569a2054dadb912f82190bb75b9ca'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe archive member')
    return path


def inspect(root):
    release = root / 'cloud-hermes/releases/2.0.0-rc3'
    source = release / 'HADS_Hermes_2.0.0-rc3-source.zip'
    installer = release / 'HADS_Hermes_install_2.0.0-rc3.sh'
    source_bytes = source.read_bytes()
    installer_bytes = installer.read_bytes()
    if digest(source_bytes) != SOURCE_SHA256 or digest(installer_bytes) != INSTALLER_SHA256:
        raise ValueError('RC3 source or installer does not match pinned checksum')
    present, absent = {}, []
    for line in (release / 'HADS_Hermes_2.0.0-rc3-SHA256.txt').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        checked_name(name)
        path = release / name
        if not path.is_file():
            absent.append({'path': name, 'expected_sha256': expected})
            continue
        actual = digest(path.read_bytes())
        if actual != expected:
            raise ValueError('Release manifest checksum mismatch: ' + name)
        present[name] = actual
    encoded = installer_bytes.decode().split("<<'HADS4_PAYLOAD'\n", 1)[1].split('\nHADS4_PAYLOAD', 1)[0]
    payload = base64.b64decode(encoded)
    if digest(payload) != PAYLOAD_SHA256:
        raise ValueError('Embedded payload checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as archive:
        entries = archive.infolist()
        if len(entries) != 133 or sum(i.file_size for i in entries) > 4 * 1024 * 1024:
            raise ValueError('Unexpected source archive size')
        files = {}
        for item in entries:
            checked_name(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16) or item.is_dir() or item.filename in files:
                raise ValueError('Unexpected source archive member')
            files[item.filename] = archive.read(item)
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        payload_files = {}
        for item in archive.getmembers():
            checked_name(item.name)
            if not item.isfile() or item.name in payload_files or item.size > 4 * 1024 * 1024:
                raise ValueError('Unexpected payload archive member')
            payload_files[item.name] = archive.extractfile(item).read()
    if files != payload_files:
        raise ValueError('Installer payload differs from source tree')
    ci_source = root / 'cloud-hermes/ci/source-rc3.zip'
    if ci_source.read_bytes() != source_bytes:
        raise ValueError('CI source ZIP differs from release ZIP')
    documents = {
        'MANUAL_2.0.0-rc3_CS.md': 'HADS_Hermes_2.0.0-rc3-manual-CS.md',
        'RELEASE_2.0.0-rc3.md': 'HADS_Hermes_2.0.0-rc3-release.md',
        'HA_MCP_NASTAVENI_CS.md': 'HADS_Hermes_2.0.0-rc3-HA-MCP-nastaveni-CS.md',
    }
    for inside, outside in documents.items():
        if files[inside] != (release / outside).read_bytes():
            raise ValueError('Release document differs from bundled document')
    return files, {
        'base_commit': BASE_COMMIT,
        'scope': 'offline byte verification; no HAOS, restore, upstream runtime or container validation',
        'source': str(source.relative_to(root)),
        'source_sha256': SOURCE_SHA256,
        'installer_sha256': INSTALLER_SHA256,
        'embedded_payload_sha256': PAYLOAD_SHA256,
        'ci_source_matches_release': True,
        'installer_payload_matches_source': True,
        'release_documents_match_source': documents,
        'present_release_manifest_files': present,
        'release_manifest_files_not_distributed_separately': absent,
        'files': {name: {'sha256': digest(data), 'bytes': len(data)} for name, data in sorted(files.items())},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true', help='Reconstruct ignored hads-next/legacy-rc3 tree, refusing changed files')
    parser.add_argument('--write-manifest', action='store_true', help='Write deterministic hads-next/provenance.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    files, manifest = inspect(root)
    if args.extract:
        destination = root / 'hads-next/legacy-rc3'
        if destination.is_symlink():
            raise ValueError('Extraction destination must not be a symlink')
        for name, data in files.items():
            target = destination.joinpath(*checked_name(name).parts)
            if any(p.is_symlink() for p in [target, *target.parents]):
                raise ValueError('Extraction path contains a symlink')
            if target.exists() and target.read_bytes() != data:
                raise ValueError('Refusing to replace changed reconstruction: ' + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    if args.write_manifest:
        (root / 'hads-next/provenance.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'result': 'verified_offline', 'files': len(files), 'source_sha256': SOURCE_SHA256,
                      'installer_payload_matches_source': True, 'ci_source_matches_release': True}))


if __name__ == '__main__':
    main()
