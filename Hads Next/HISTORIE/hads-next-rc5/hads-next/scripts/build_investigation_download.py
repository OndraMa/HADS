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
    assets["VYSLEDKY_A_OMEZENI_CS.md"] = blob("hads-next/docs/RC5_DELIVERY_CS.md" if VERSION=="1.0.0-rc5" else "hads-next/docs/RC4_DELIVERY_CS.md" if VERSION=="1.0.0-rc4" else "hads-next/docs/RC3_DELIVERY_CS.md" if VERSION=="1.0.0-rc3" else "hads-next/docs/PRACTICAL_ACCEPTANCE.md" if VERSION=="1.0.0-rc2" else "hads-next/docs/FINAL_DELIVERY.md" if VERSION=="1.0.0-rc1" else "hads-next/docs/results.md")
    if VERSION in {"1.0.0-rc1","1.0.0-rc2","1.0.0-rc3","1.0.0-rc4","1.0.0-rc5"}:
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
    if VERSION in {"1.0.0-rc2","1.0.0-rc3","1.0.0-rc4","1.0.0-rc5"}:
        quick=quick.replace("Produkční zápisy jsou vypnuté.","Obecné a rizikové zápisy jsou zakázané.")
        quick+="\nPraktická oprava umí po přesném schválení zapnout vybranou jednoduchou světelnou automatizaci nativní službou. Konfiguraci nepřepisuje; služba nemá CAS. Potřebuje výlučnou práci s cílem a funkční i fyzické ověření. Návrat vypne budoucí triggery, nevrací fyzické účinky. Živá přejímka je v UI.\n"
    assets["CTI_ME_NEJDRIVE_CS.txt"] = quick.encode("utf-8-sig")
    if VERSION in {"1.0.0-rc3","1.0.0-rc4","1.0.0-rc5"}:
        assets['INTEGRATIONS_CS.md']=blob('hads-next/haos/INTEGRATIONS_CS.md')
        quick=quick.replace('Nová aplikace zachovává RC3 i starý Next.','Starý Hermes 2.0.0-rc3 se nemění. RC3 lze výslovně aktualizovat z ověřeného zastaveného Next RC2.')
        quick=quick.replace('Historické archivy uvnitř zdrojovy-repozitar/ nejsou aktuální instalátor.','ZIP obsahuje aktuální HADS Next zdroje a dokumentaci; historické release ZIPy zůstávají samostatně na GitHubu.')
        quick+='\nPro existující RC2 nejprve zastav pouze HADS Next a použij --upgrade-rc2. Data se zachovají; nativní update vytváří částečnou zálohu aplikace. Potom spusť HADS Next ručně. Nepoužívej uninstall ani mazání /data. Úplná nezávislá obnovitelnost HAOS/OneDrive tím není doložená.\n'
        assets['CTI_ME_NEJDRIVE_CS.txt']=quick.encode('utf-8-sig')
    if VERSION=="1.0.0-rc4":
        quick=("HADS Next 1.0.0-rc4 — automatická nativní diagnostika\n\n"
            "Pro běžící RC3 ulož instalátor do /config a spusť pouze úvodní aktualizaci:\n"
            "  bash /config/HADS_Next_install_1.0.0-rc4.sh --verify\n"
            "  bash /config/HADS_Next_install_1.0.0-rc4.sh --upgrade-rc3\n\n"
            "RC3 předem nezastavuj ani neodinstalovávej. Supervisor aktualizuje jen HADS Next s částečnou zálohou.\n"
            "Potom otevři HADS. Nativní zdroje, statistiky a diagnostické pokračování čte samo.\n"
            "Další diagnostické příkazy od tebe nepotřebuje; AI klíč pro tato čtení není potřeba.\n"
            "Původní Hermes je v obrazu. Jeho načtení hlídá paměťová rezerva 576 MiB.\n"
            "Malý AI test povol až později v nastavení: 3 požadavky / klouzavých 24 h, max. 512 výstupních tokenů; bez automatické placené fronty.\n"
            "Limit požadavků není dolarový strop. Klíč neposílej do chatu nebo GitHubu.\n"
            "Zdrojový commit: "+accepted['source_commit']+"\n"
            "Nativní kontejnery ARM64 i AMD64 a skutečný Hermes se skriptovaným modelem jsou ověřené; živý HAOS, LLM a fyzické přístroje stále čekají.\n"
            "Podrobný návod: HADS_Next_1.0.0-rc4-navod-CS.md. Při chybě zachovej hlášku a marker; nic nemaž a neodinstalovávej.\n")
        assets['CTI_ME_NEJDRIVE_CS.txt']=quick.encode('utf-8-sig')
    if VERSION=="1.0.0-rc5":
        quick=("HADS Next 1.0.0-rc5 — ověřování doplňků a soukromý návrh připojení\n\n"
            "Pro běžící RC4 ulož instalátor do /config a spusť pouze úvodní aktualizaci:\n"
            "  bash /config/HADS_Next_install_1.0.0-rc5.sh --upgrade-rc4\n\n"
            "RC4 předem nezastavuj ani neodinstalovávej. Supervisor aktualizuje pouze HADS Next s částečnou zálohou.\n"
            "Po aktualizaci otevři Doplňky a ověření. Nativní kontrola běží automaticky bez AI.\n"
            "Volitelný přenos z Hermes 2.0.0-rc3 uloží pouze neaktivní soukromý návrh spojení. Konektory tím nejsou aktivované ani ověřené.\n"
            "MCP funkční čtení a zapisovací adaptéry Spook/HA-MCP ještě nejsou hotové; přehled je neoznačí jako funkční. HASK je vynechaný.\n"
            "AI zůstává vypnutá, paměťová rezerva 576 MiB platí. Klíče nepatří do chatu nebo GitHubu.\n"
            "Zdrojový commit: "+accepted['source_commit']+"\n"
            "Nativní kontejnery a skriptovaný model nejsou živá HAOS přejímka ani ověření funkce doplňků.\n"
            "Podrobný návod: HADS_Next_1.0.0-rc5-navod-CS.md. Při chybě nic nemaž, neodinstalovávej a zachovej hlášku.\n")
        assets['CTI_ME_NEJDRIVE_CS.txt']=quick.encode('utf-8-sig')
    files = dict(assets)
    archive_args=["archive","--format=zip","--prefix=zdrojovy-repozitar/",commit]
    if VERSION in {"1.0.0-rc3","1.0.0-rc4","1.0.0-rc5"}:archive_args+=['--','hads-next','.github','README.md']
    with zipfile.ZipFile(io.BytesIO(git(*archive_args))) as archive:
        for member in archive.infolist():
            if not member.is_dir() and not (VERSION in {"1.0.0-rc3","1.0.0-rc4","1.0.0-rc5"} and member.filename.startswith("zdrojovy-repozitar/hads-next/releases/")):
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
    parser.add_argument("--version",default=VERSION,choices=["0.2.0-dev1","1.0.0-rc1","1.0.0-rc2","1.0.0-rc3","1.0.0-rc4","1.0.0-rc5"])
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.ref, args.package_dir, args.output_dir,args.version), indent=2))
