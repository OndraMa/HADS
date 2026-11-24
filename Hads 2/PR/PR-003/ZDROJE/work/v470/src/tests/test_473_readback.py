import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
import hads4

spec = importlib.util.spec_from_file_location("readback_verifier", Path(__file__).resolve().parents[1] / "companion/custom_components/hads_rescue/verifier.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class Stream:
    def __init__(self, content):
        self.content = content

    async def iter_chunked(self, size):
        yield self.content[:2]
        yield self.content[2:]


class ReadbackTests(unittest.IsolatedAsyncioTestCase):
    def client(self, content=b"fixture", size=7, name="HADS_REPAIR.zip"):
        return SimpleNamespace(get_approot=mock.AsyncMock(return_value=SimpleNamespace(id="app")),
            get_drive_item=mock.AsyncMock(return_value=SimpleNamespace(id="remote", name=name, size=size)),
            download_drive_item=mock.AsyncMock(return_value=Stream(content)))

    async def test_hash_is_computed_from_remote_stream(self):
        client = self.client()
        result = await verifier.verify(client, "account", "HADS/Repairs", "HADS_REPAIR.zip")
        self.assertEqual(hashlib.sha256(b"fixture").hexdigest(), result["sha256"])
        self.assertTrue(result["exists"])
        self.assertFalse(result["restore_tested"])
        client.get_drive_item.assert_awaited_once_with("app:/HADS/Repairs/HADS_REPAIR.zip:")

    async def test_missing_remote_file_does_not_verify(self):
        client = self.client()
        client.get_drive_item.side_effect = FileNotFoundError()
        with self.assertRaises(FileNotFoundError):
            await verifier.verify(client, "account", "HADS/Repairs", "HADS_REPAIR.zip")
        client.download_drive_item.assert_not_awaited()

    async def test_truncated_stream_does_not_verify(self):
        with self.assertRaises(ValueError):
            await verifier.verify(self.client(size=20), "account", "HADS/Repairs", "HADS_REPAIR.zip")

    async def test_larger_stream_does_not_verify(self):
        with self.assertRaises(ValueError):
            await verifier.verify(self.client(size=2), "account", "HADS/Repairs", "HADS_REPAIR.zip")

    async def test_wrong_filename_does_not_verify(self):
        with self.assertRaises(ValueError):
            await verifier.verify(self.client(name="other.zip"), "account", "HADS/Repairs", "HADS_REPAIR.zip")

    async def test_rejects_path_escape_and_non_rescue_scope(self):
        for folder, file in [("HADS/Repairs/../Personal", "HADS_REPAIR.zip"), ("Personal", "a.zip"), ("HADS/Repairs", "../secrets.yaml"), ("HADS/Repairs", "a.zip?x=1")]:
            client = self.client()
            with self.assertRaises(ValueError):
                await verifier.verify(client, "account", folder, file)
            client.get_approot.assert_not_awaited()

    async def test_oversized_file_not_downloaded(self):
        client = self.client(size=verifier.MAX_BYTES+1)
        with self.assertRaises(ValueError):
            await verifier.verify(client, "account", "HADS/Repairs", "HADS_REPAIR.zip")
        client.download_drive_item.assert_not_awaited()


class DiscoveryTests(unittest.TestCase):
    def test_does_not_guess_read_services_by_name(self):
        services = [{"domain": "onedrive", "services": {"verify_and_delete": {}, "stat": {}}},
                    {"domain": "hads_rescue", "services": {"verify": {}}}]
        with mock.patch.object(hads4, "options", return_value={}), mock.patch.object(hads4, "supervisor_request", return_value=services):
            self.assertEqual(["hads_rescue.verify"], hads4._onedrive_verifier_services())
