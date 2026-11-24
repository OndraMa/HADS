"""Build Windows-friendly release downloads from an exact Git commit, offline.

No untracked files, working credentials, local databases or ignored fixtures are
read. This script prepares assets; publishing is a separate authorized action.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

REPOSITORY = Path(__file__).resolve().parents[2]
VERSION = "0.1.0-dev1"


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPOSITORY), *args])


def build(ref, output):
    commit = git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    def blob(path):
        return git("show", commit + ":" + path)
    root = "hads-next/releases/" + VERSION + "/"
    installer = "HADS_Next_install_" + VERSION + ".sh"
    source = "HADS_Next_" + VERSION + "-source.tar.gz"
    manual = "HADS_Next_" + VERSION + "-navod-CS.md"
    quick = "CTI_ME_NEJDRIVE_CS.txt"
    quick_bytes = ("HADS Next " + VERSION + " — vývojová verze\n\n"
        "1. Instalátor je soubor " + installer + ". Nespouštěj jej ve Windows.\n"
        "2. Podrobný postup je v souboru " + manual + ".\n"
        "3. V terminálové/SSH aplikaci testovacího HAOS s ha, bash a python3 spusť:\n\n"
        "   bash " + installer + " --verify\n"
        "   bash " + installer + " --install-dev\n\n"
        "Aplikace se přidá vedle RC3. Hermes a živé opravy nejsou aktivní.\n"
        "Živá HAOS a ARM64/RPi přejímka zatím neproběhla. Nejde o produkční RC.\n\n"
        "zdrojovy-repozitar/ obsahuje VŠECHNY verzované soubory vybraného Git commitu,\n"
        "včetně zdrojů, dokumentace a testů. Starý 4.6.3 uvnitř historických souborů\n"
        "není nový instalátor; používej výše uvedený instalátor HADS Next v kořeni ZIPu.\n\n"
        "Commit zdrojů a dokumentace: " + commit + "\n"
        "Repozitář je soukromý; pro další stažení se přihlas do GitHubu.\n").encode("utf-8-sig")
    assets = {installer: blob(root + installer), source: blob(root + source),
              manual: blob("hads-next/haos/DOCS.md"), quick: quick_bytes}
    files = {**assets, "SHA256SUMS": blob(root + "SHA256SUMS")}
    archived = git("archive", "--format=zip", "--prefix=zdrojovy-repozitar/", commit)
    with zipfile.ZipFile(io.BytesIO(archived)) as repository:
        for item in repository.infolist():
            if not item.is_dir():
                files[item.filename] = repository.read(item)
    if len(files) > 2000 or sum(map(len, files.values())) > 50 * 1024 * 1024:
        raise ValueError("Unexpected repository archive size")
    files["MANIFEST_SHA256.txt"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in sorted(files.items())).encode()
    bundle = "HADS_Next_" + VERSION + "-komplet.zip"
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            archive.writestr(info, data)
    assets[bundle] = zipped.getvalue()
    checksum = "HADS_Next_" + VERSION + "-SHA256SUMS.txt"
    assets[checksum] = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n"
                               for name, data in sorted(assets.items())).encode()
    for name, data in assets.items():
        (output / name).write_bytes(data)
    return {"commit": commit, "output": str(output), "assets": sorted(assets), "zip_files": len(files)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY / "hads-next/.test-tmp/github-release")
    args = parser.parse_args()
    print(json.dumps(build(args.ref, args.output_dir), indent=2))
