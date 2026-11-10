"""Package the exact accepted 0.2 installer, committed docs and source for Windows.

Never rebuild or relabel the tested payload. No ignored files, databases or
credentials enter the repository ZIP. Output files must not already exist.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.2.0-dev1"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def build(ref, package, output, version=VERSION):
    VERSION=version
    commit = git("rev-parse", "--verify", ref + "^{commit}").decode().strip()
    def blob(path):
        return git("show", commit + ":" + path)
    accepted = json.loads(blob("hads-next/docs/evidence/installation-" + VERSION + "/ACCEPTANCE.json"))
    if accepted.get("both_passed") is not True or accepted.get("live_haos") is not False:
        raise ValueError("Missing explicit container acceptance boundary")
    package, output = Path(package), Path(output)
    installer = "HADS_Next_install_" + VERSION + ".sh"
    source = "HADS_Next_" + VERSION + "-source.tar.gz"
    assets = {name: (package / name).read_bytes() for name in (installer, source, "SHA256SUMS")}
    for name, key in ((installer, "installer_sha256"), (source, "source_archive_sha256")):
        if hashlib.sha256(assets[name]).hexdigest() != accepted[key]:
            raise ValueError("Package differs from accepted bytes: " + name)
    expected = "".join(hashlib.sha256(assets[name]).hexdigest() + "  " + name + "\n" for name in (installer, source))
    if assets["SHA256SUMS"].decode() != expected:
        raise ValueError("Package checksum manifest differs")
    with tarfile.open(fileobj=io.BytesIO(assets[source]), mode="r:gz") as archive:
        manifest = json.load(archive.extractfile("PACKAGE_MANIFEST.json"))
        if manifest["source_revision_at_build"] != accepted["source_commit"]:
            raise ValueError("Source revision differs from acceptance")
        for name, metadata in manifest["files"].items():
            data = archive.extractfile(name).read()
            original = git("show", accepted["source_commit"] + ":hads-next/" + metadata["source"])
            if data != original or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
                raise ValueError("Payload source mismatch: " + name)
        assets["HADS_Next_" + VERSION + "-navod-CS.md"] = archive.extractfile("DOCS.md").read()
    assets["VYSLEDKY_A_OMEZENI_CS.md"] = blob("hads-next/docs/FINAL_DELIVERY.md" if VERSION=="1.0.0-rc1" else "hads-next/docs/results.md")
    if VERSION=="1.0.0-rc1":
        companion=io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(assets[source]),mode="r:gz") as archive,zipfile.ZipFile(companion,"w",compression=zipfile.ZIP_DEFLATED) as target:
            for member in archive:
                if member.name.startswith('companion/') and member.isfile():
                    entry=zipfile.ZipInfo(member.name.removeprefix('companion/'),(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16
                    target.writestr(entry,archive.extractfile(member).read())
        assets['HADS_companion_'+VERSION+'.zip']=companion.getvalue()
    assets["AKCEPTACE_HAOS_CS.md"] = blob("hads-next/docs/haos-acceptance.md")
    assets["ACCEPTANCE.json"] = json.dumps(accepted, indent=2).encode() + b"\n"
    quick = ("HADS Next " + VERSION + " — kandidát pro oddělený testovací HAOS\n\n"
        "Instalátor: " + installer + " (nespouštět ve Windows).\n"
        "Český návod: HADS_Next_" + VERSION + "-navod-CS.md\n"
        "Nejprve porovnej SHA-256, potom v odpovídajícím testovacím terminálu:\n"
        "  bash " + installer + " --verify\n"
        "  bash " + installer + " --install-dev\n\n"
        "Původní Hermes je součástí aplikace. Kontrola runtime nepotřebuje model.\n"
        "AI i veřejný výzkum vyžadují zvláštní souhlas. Produkční zápisy jsou vypnuté.\n"
        "AMD64 a ARM64: nativní kontejnerové testy prošly, model byl skriptovaný.\n"
        "Živý HAOS, skutečný LLM a fyzická zařízení NEJSOU ověřené.\n"
        "Nová aplikace zachovává RC3 i starý Next. Nejde o produkční RC.\n\n"
        "Přesný testovaný zdrojový commit: " + accepted["source_commit"] + "\n"
        "Commit dokumentace a verzovaného repozitáře v tomto ZIPu: " + commit + "\n"
        "Historické archivy uvnitř zdrojovy-repozitar/ nejsou aktuální instalátor.\n"
        "Návody a stav přejímky čti nejprve v kořeni tohoto balíčku.\n")
    if VERSION=="1.0.0-rc1":quick=quick.replace("Produkční zápisy jsou vypnuté.","Obecné produkční zápisy jsou zakázané.");quick+="\nJediná podporovaná zapisovací oprava mění vlastní virtuální referenci přes companion CAS. Potřebuje instalaci přiložené integrace a zvláštní schválení každého plánu. Nativní automatizace se obecně nepřepisují.\n"
    assets["CTI_ME_NEJDRIVE_CS.txt"] = quick.encode("utf-8-sig")
    files = dict(assets)
    with zipfile.ZipFile(io.BytesIO(git("archive", "--format=zip", "--prefix=zdrojovy-repozitar/", commit))) as archive:
        for member in archive.infolist():
            if not member.is_dir():
                files[member.filename] = archive.read(member)
    if len(files) > 3000 or sum(map(len, files.values())) > 50 * 1024 * 1024:
        raise ValueError("Unexpected bundle size")
    files["MANIFEST_SHA256.txt"] = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            member = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            archive.writestr(member, data)
    assets["HADS_Next_" + VERSION + "-komplet.zip"] = stream.getvalue()
    assets["HADS_Next_" + VERSION + "-SHA256SUMS.txt"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in sorted(assets.items())).encode()
    if any((output / name).exists() or (output / name).is_symlink() for name in assets):
        raise ValueError("Refusing to overwrite existing download files")
    if output.is_symlink() or output.resolve().is_relative_to(ROOT / "hads-next/releases"):
        raise ValueError("Published release archives are immutable")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        with (output / name).open("xb") as target:
            target.write(data)
    return {"source_commit": accepted["source_commit"], "documentation_commit": commit,
        "output": str(output), "files": sorted(assets), "zip_files": len(files)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--version",default=VERSION,choices=["0.2.0-dev1","1.0.0-rc1"])
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.ref, args.package_dir, args.output_dir,args.version), indent=2))
