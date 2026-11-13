"""Independent tests of the self-contained HAOS development installer.

Every execution below is --extract-only or invalid arguments. No production
mount or actual HA CLI is accessed; fake ha records unexpected invocations.
"""
from __future__ import annotations

import importlib.util
import base64
import gzip
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HAOSInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = tempfile.TemporaryDirectory()
        spec = importlib.util.spec_from_file_location("hads_next_installer_builder", ROOT / "scripts/build_haos_installer.py")
        cls.builder = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.builder)
        cls.info = cls.builder.build_installer(Path(cls.artifacts.name) / "first")
        cls.installer = Path(cls.info["installer"])

    @classmethod
    def tearDownClass(cls):
        cls.artifacts.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.canary = self.root / "ha-was-called"
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        fake_ha = fake_bin / "ha"
        fake_ha.write_text("#!/bin/sh\nprintf 'called\\n' >> \"$HADS_TEST_HA_CANARY\"\nexit 99\n")
        fake_ha.chmod(0o755)
        self.env = {**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
                    "HADS_TEST_HA_CANARY": str(self.canary)}

    def tearDown(self):
        self.temporary.cleanup()

    def run_installer(self, *args, installer=None):
        result = subprocess.run(["bash", str(installer or self.installer), *map(str, args)],
                                capture_output=True, text=True, env=self.env, timeout=20)
        self.assertFalse(self.canary.exists(), "Inspection/invalid arguments unexpectedly invoked ha")
        return result

    def test_payload_is_deterministic_and_contains_only_regular_sources(self):
        second = self.builder.build_installer(Path(self.artifacts.name) / "second")
        self.assertEqual(self.installer.read_bytes(), Path(second["installer"]).read_bytes())
        self.assertEqual(Path(self.info["source_archive"]).read_bytes(), Path(second["source_archive"]).read_bytes())
        with tarfile.open(self.info["source_archive"], "r:gz") as archive:
            members = archive.getmembers()
            self.assertLessEqual(len(members), 1024)
            self.assertLessEqual(sum(item.size for item in members), 4 * 1024 * 1024)
            names = []
            for item in members:
                name = PurePosixPath(item.name)
                self.assertFalse(name.is_absolute())
                self.assertNotIn("..", name.parts)
                self.assertTrue(item.isfile() or item.isdir())
                self.assertFalse(item.issym() or item.islnk())
                self.assertFalse(set(name.parts) & {".git", ".test-tmp", "legacy-rc3", "__pycache__"})
                self.assertFalse(item.name.endswith((".sqlite", ".sqlite-wal", "decision.json", "options.json")))
                names.append(item.name)
            self.assertEqual(len(names), len(set(names)))
            self.assertIn("config.yaml", names)
            self.assertIn("Dockerfile", names)
            for required in ('INTEGRATIONS_CS.md','hads_next/hermes_worker.py','hads_next/music_assistant.py','hads_next/observability.py','hads_next/native_repair.py','hads_next/dashboard.py','hads_next/automatic_reads.py','hads_next/ai_budget.py'):
                self.assertIn(required,names)
            self.assertIn(b'd923a5eb487a17c0a68801bba9ef0f56c81040a8',archive.extractfile('Dockerfile').read())
            self.assertIn('hermes-constraints.txt',names)
            self.assertIn('lab/core-constraints.txt',names)
            self.assertNotIn('lab/core_repair.py',names)

    def test_published_release_paths_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):self.builder.build_installer(ROOT/'releases'/'0.1.0-dev1')

    def test_inspection_extracts_verified_package_without_any_ha_call(self):
        destination = self.root / "inspection with spaces"
        result = self.run_installer("--extract-only", destination)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((destination / "config.yaml").is_file())
        self.assertTrue((destination / "Dockerfile").is_file())
        self.assertFalse((destination / ".git").exists())
        self.assertNotIn("SUPERVISOR_TOKEN=", result.stdout + result.stderr)

    def test_existing_destination_is_preserved_and_never_replaced(self):
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "keep-me"
        sentinel.write_bytes(b"existing local source")
        result = self.run_installer("--extract-only", destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_bytes(), b"existing local source")
        self.assertFalse((destination / "config.yaml").exists())

    def test_destination_symlink_and_symlink_parent_are_refused(self):
        actual = self.root / "actual"
        actual.mkdir()
        linked = self.root / "linked"
        linked.symlink_to(actual, target_is_directory=True)
        for destination in (linked, linked / "child"):
            with self.subTest(destination=destination):
                result = self.run_installer("--extract-only", destination)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list(actual.iterdir()), [])

    def test_missing_or_unknown_arguments_never_begin_installation(self):
        for args in ((), ("--unknown",), ("--extract-only",), ("--extract-only", "relative-path"),
                     ("--extract-only", self.root / "valid", "unexpected")):
            with self.subTest(args=args):
                result = self.run_installer(*args)
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "valid").exists())

    def test_corrupt_embedded_payload_is_refused_before_destination_creation(self):
        source = self.installer.read_text()
        match = re.search(r"<<'?HADS_NEXT_PAYLOAD'?\n(?P<payload>.*?)\nHADS_NEXT_PAYLOAD", source, re.S)
        self.assertIsNotNone(match, "Self-contained payload marker contract changed")
        start, end = match.span("payload")
        data = source[start:end]
        first = next(i for i, char in enumerate(data) if char.isalnum())
        data = data[:first] + ("A" if data[first] != "A" else "B") + data[first+1:]
        corrupted = self.root / "corrupted.sh"
        corrupted.write_text(source[:start] + data + source[end:])
        destination = self.root / "must-not-exist"
        result = self.run_installer("--extract-only", destination, installer=corrupted)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(destination.exists())

    def test_valid_hash_does_not_allow_absolute_member_or_symlink(self):
        original_archive = Path(self.info["source_archive"]).read_bytes()
        original_source = self.installer.read_text()
        canary = self.root / "outside-canary"
        for kind in ("absolute", "symlink"):
            with self.subTest(kind=kind):
                buffer = io.BytesIO()
                with tarfile.open(fileobj=io.BytesIO(original_archive), mode="r:gz") as old, tarfile.open(fileobj=buffer, mode="w") as new:
                    for member in old:
                        new.addfile(member, old.extractfile(member) if member.isfile() else None)
                    extra = tarfile.TarInfo(str(canary) if kind == "absolute" else "unexpected-link")
                    if kind == "absolute":
                        extra.size = 4
                        new.addfile(extra, io.BytesIO(b"oops"))
                    else:
                        extra.type = tarfile.SYMTYPE
                        extra.linkname = str(self.root)
                        new.addfile(extra)
                payload = gzip.compress(buffer.getvalue(), mtime=0)
                source = original_source.replace(hashlib.sha256(original_archive).hexdigest(), hashlib.sha256(payload).hexdigest())
                match = re.search(r"<<'?HADS_NEXT_PAYLOAD'?\n(?P<payload>.*?)\nHADS_NEXT_PAYLOAD", source, re.S)
                self.assertIsNotNone(match)
                start, end = match.span("payload")
                malicious = self.root / (kind + ".sh")
                malicious.write_text(source[:start] + base64.encodebytes(payload).decode().rstrip("\n") + source[end:])
                destination = self.root / (kind + "-output")
                result = self.run_installer("--extract-only", destination, installer=malicious)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(destination.exists())
                self.assertFalse(canary.exists())


if __name__ == "__main__":
    unittest.main()
