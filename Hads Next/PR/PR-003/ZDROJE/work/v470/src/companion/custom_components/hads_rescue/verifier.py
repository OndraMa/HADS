"""Read back a HADS rescue object using the already authenticated OneDrive SDK.

No upload/delete/create/rename methods. Never return file contents or credentials.
"""
import asyncio
import hashlib
import re
from urllib.parse import quote

MAX_BYTES = 250 * 1024 * 1024


def checked_path(folder, filename):
    if not isinstance(folder, str) or not re.fullmatch(r"HADS/Repairs(?:/[a-zA-Z0-9_-]+)*", folder):
        raise ValueError("Verifier only reads HADS/Repairs and its subfolders")
    if not isinstance(filename, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+\.zip", filename) or len(filename) > 200:
        raise ValueError("Invalid rescue ZIP name")
    return folder + "/" + filename


async def verify(client, config_entry_id, destination_folder, filename):
    relative = checked_path(destination_folder, filename)
    async with asyncio.timeout(120):
        # OneDrive entry must already be LOADED by the caller, meaning its app
        # root has been initialized. This adapter never creates a missing folder.
        root = await client.get_approot()
        item = await client.get_drive_item(f"{root.id}:/{quote(relative, safe='/')}:")
        if item.name != filename or type(item.size) is not int or not 0 < item.size <= MAX_BYTES:
            raise ValueError("Unexpected remote object name/size")
        stream = await client.download_drive_item(item.id)
        digest, count = hashlib.sha256(), 0
        async for chunk in stream.iter_chunked(64 * 1024):
            count += len(chunk)
            if count > item.size or count > MAX_BYTES:
                raise ValueError("Remote object exceeded verified metadata size")
            digest.update(chunk)
        if count != item.size:
            raise ValueError("Remote download incomplete")
        # Local HADS compares this independently computed hash against its ZIP.
        # Merely echoing the expected hash would not be verification.
        return {"verification_version": 1, "exists": True, "config_entry_id": config_entry_id,
                "destination_folder": destination_folder, "filename": filename, "size": count,
                "sha256": digest.hexdigest(), "remote_item_id": item.id,
                "method": "independent_remote_download_sha256", "restore_tested": False}
