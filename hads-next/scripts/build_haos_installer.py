"""Deterministic, self-contained HAOS development installer. Never runs HA CLI."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0-rc10"
SLUG = "hads_next_practical"

EXTRACTOR = r'''
import hashlib, json, os, pathlib, sys, tarfile
archive, expected, destination = sys.argv[1:]
raw = pathlib.Path(archive).read_bytes()
if len(raw) > 2 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected:
    raise SystemExit('Nesouhlasí SHA-256 vloženého balíčku. Nic nebylo nainstalováno.')
with tarfile.open(archive, 'r:gz') as tar:
    members = tar.getmembers()
    if len(members) > 1024 or sum(m.size for m in members) > 4 * 1024 * 1024:
        raise SystemExit('Balíček překročil bezpečný limit.')
    contents = {}
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if (not member.isfile() or path.is_absolute() or '..' in path.parts
            or str(path) != member.name or member.name in contents or '\\' in member.name
            or member.size > 1024 * 1024):
            raise SystemExit('Nepovolená cesta nebo typ člena balíčku.')
        contents[member.name] = tar.extractfile(member).read()
manifest = json.loads(contents.pop('PACKAGE_MANIFEST.json'))
if manifest.get('version') != '@@VERSION@@' or manifest.get('slug') != '@@SLUG@@':
    raise SystemExit('Nesouhlasí identita balíčku.')
files = manifest.get('files', {})
if set(files) != set(contents) or not {'Dockerfile','config.yaml','run.sh','hads_next/addon_server.py'} <= set(files):
    raise SystemExit('Nesouhlasí obsah balíčku.')
for name, data in contents.items():
    if hashlib.sha256(data).hexdigest() != files[name]['sha256'] or len(data) != files[name]['bytes']:
        raise SystemExit('Nesouhlasí obsah souboru: ' + name)
if destination == '--verify':
    print('Vložený balíček a všechny zdroje jsou ověřené. HAOS instalace nebyla provedena.')
    raise SystemExit(0)
target = pathlib.Path(destination)
if (not target.is_absolute() or '..' in target.parts or target.exists() or target.is_symlink()
    or not target.parent.is_dir() or target.parent.resolve() != target.parent):
    raise SystemExit('Cíl musí být nový absolutní adresář pod skutečným existujícím rodičem bez symlinků.')
target.mkdir(mode=0o755)
for name, data in contents.items():
    path = target / name
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(0o755 if name == 'run.sh' else 0o644)
with (target / 'PACKAGE_MANIFEST.json').open('xb') as stream:
    stream.write((json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2)+'\n').encode())
os.chmod(target / 'PACKAGE_MANIFEST.json', 0o644)
print('Ověřené zdroje rozbaleny do ' + str(target))
'''

TEMPLATE = r'''#!/usr/bin/env bash
set -euo pipefail
umask 077
VERSION="@@VERSION@@"
EXPECTED_SHA256="@@SHA@@"
usage() {
  cat <<'HADS_NEXT_USAGE'
HADS Next @@VERSION@@ — samostatná vývojová aplikace, nikoli produkční RC.
Použití:
  bash HADS_Next_install_@@VERSION@@.sh --verify
  bash HADS_Next_install_@@VERSION@@.sh --extract-only /absolutni/novy-adresar
  bash HADS_Next_install_@@VERSION@@.sh --install-dev
  bash HADS_Next_install_@@VERSION@@.sh --upgrade
Nová instalace přidá local_@@SLUG@@. Výslovný --upgrade aktualizuje ověřený Next RC6 až RC9 přes nativní Supervisor update a zachová /data. Podle zadání nevytváří novou předinstalační HA/OneDrive zálohu. Povinné zálohy před opravami zůstávají. Starý Hermes 2.0.0-rc3 se nemění.
Původní Hermes je součástí balíčku. AI i vlastní testovací opravný katalog vyžadují výslovný souhlas. Obecné produkční zápisy jsou zakázané. Živá HAOS přejímka čeká.
HADS_NEXT_USAGE
}
MODE="${1:-}"
case "$MODE" in
  --help) [ "$#" = 1 ] || exit 2; usage; exit 0 ;;
  --verify|--install-dev|--upgrade|--upgrade-rc6|--upgrade-rc7) [ "$#" = 1 ] || { usage; exit 2; } ;;
  --extract-only) [ "$#" = 2 ] || { usage; exit 2; } ;;
  *) usage; exit 2 ;;
esac
command -v python3 >/dev/null || { echo 'Chybí python3 v terminálové aplikaci. Podrobnosti jsou v návodu DOCS.md.' >&2; exit 1; }
command -v base64 >/dev/null || { echo 'Chybí base64.' >&2; exit 1; }
STAGING="$(mktemp -d /tmp/hads-next-install.XXXXXX)"
cleanup() {
  case "$STAGING" in /tmp/hads-next-install.*) rm -rf -- "$STAGING" ;; esac
}
trap cleanup EXIT
base64 -d > "$STAGING/payload.tar.gz" <<'HADS_NEXT_PAYLOAD'
@@PAYLOAD@@
HADS_NEXT_PAYLOAD
extract_payload() {
python3 - "$STAGING/payload.tar.gz" "$EXPECTED_SHA256" "$1" <<'HADS_NEXT_PYTHON'
@@EXTRACTOR@@
HADS_NEXT_PYTHON
}
if [ "$MODE" = '--verify' ]; then extract_payload --verify; exit 0; fi
if [ "$MODE" = '--extract-only' ]; then extract_payload "$2"; exit 0; fi

command -v ha >/dev/null || { echo 'Chybí HA CLI. Použij Terminál/SSH v testovacím HAOS.' >&2; exit 1; }
[ "$(id -u)" = 0 ] || { echo 'Instalace potřebuje vlastníka kořenové složky místních aplikací.' >&2; exit 1; }
if [ -d /local_apps ] && [ ! -L /local_apps ]; then APP_ROOT=/local_apps
elif [ -d /addons ] && [ ! -L /addons ]; then APP_ROOT=/addons
else echo 'Chybí připojený adresář /local_apps nebo /addons. Nic neměním.' >&2; exit 1
fi
TARGET="$APP_ROOT/@@SLUG@@"
if [ "$MODE" = '--install-dev' ] && { [ -e "$TARGET" ] || [ -L "$TARGET" ]; }; then
  echo 'HADS Next již má zdrojový adresář. Pro ověřený RC6–RC9 použij --upgrade. Neodinstalovávej aplikaci ani nemaž data.' >&2
  exit 1
fi
if ha apps --help >/dev/null 2>&1; then APP_COMMAND=apps
elif ha addons --help >/dev/null 2>&1; then APP_COMMAND=addons
else echo 'HA CLI neposkytuje podporovanou správu aplikací.' >&2; exit 1
fi
if [ "$MODE" = '--upgrade' ] || [ "$MODE" = '--upgrade-rc6' ] || [ "$MODE" = '--upgrade-rc7' ]; then
  extract_payload "$STAGING/candidate-source"
  python3 - "$APP_ROOT" "$APP_COMMAND" "$STAGING/candidate-source" <<'HADS_NEXT_UPGRADE'
@@UPGRADER@@
HADS_NEXT_UPGRADE
  exit 0
fi
[ ! -e "$TARGET" ] && [ ! -L "$TARGET" ] || { echo 'HADS Next již má zdrojový adresář. Pro ověřený RC6 až RC9 použij --upgrade.' >&2; exit 1; }
# The list must succeed. A failed authorization is never treated as absence.
ha "$APP_COMMAND" --raw-json > "$STAGING/apps.json"
python3 - "$STAGING/apps.json" <<'HADS_NEXT_APPS'
import json, sys
data=json.load(open(sys.argv[1],encoding='utf-8'))
if not isinstance(data,dict) or data.get('result','ok') != 'ok':
    raise SystemExit('Supervisor nepotvrdil seznam instalovaných aplikací.')
data=data.get('data',data)
apps=data.get('addons',data.get('apps')) if isinstance(data,dict) else None
if not isinstance(apps,list) or any(not isinstance(x,dict) or not isinstance(x.get('slug'),str) for x in apps):
    raise SystemExit('Nerozpoznaný seznam aplikací. Instalace je zastavena.')
if any(x['slug']=='local_@@SLUG@@' for x in apps):
    raise SystemExit('Tato aplikace je již instalována; její data ani verzi nepřepisuji.')
HADS_NEXT_APPS
extract_payload "$TARGET"
echo 'Přidány samostatné zdroje. Obnovuji katalog a stavím vývojovou aplikaci.'
echo 'Při selhání zůstanou zdroje zachovány. Žádný automatický uninstall se neprovádí.'
ha store reload
ha "$APP_COMMAND" install local_@@SLUG@@
ha "$APP_COMMAND" start local_@@SLUG@@
ha "$APP_COMMAND" info local_@@SLUG@@ --raw-json > "$STAGING/installed.json"
python3 - "$STAGING/installed.json" <<'HADS_NEXT_INSTALLED'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'));v=v.get('data',v)
if v.get('version')!='@@VERSION@@' or v.get('state')!='started':
    raise SystemExit('Spuštění této verze nebylo potvrzeno. Zachovej zdroje a zkontroluj log aplikace.')
HADS_NEXT_INSTALLED
echo 'HADS Next @@VERSION@@ spuštěn. Otevři jeho webové rozhraní v Nastavení → Aplikace.'
echo 'V rozhraní potvrď vlastníka ověřeného Home Assistantem. Potom ověř zdroje a Hermes bez volání modelu.'
echo 'Starý Hermes 2.0.0-rc3 zůstává zachovaný. Vytvoření ani obnovitelnost HAOS/OneDrive zálohy tento instalátor nepotvrzuje.'
echo 'Úspěšné spuštění není dokladem živé přejímky ani plné funkčnosti HADS Next.'
'''


def build_installer(output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    resolved=output_dir.resolve()
    if resolved.is_relative_to(ROOT/"releases") or resolved.is_relative_to(ROOT.parent/"KE_STAZENI"):
        raise ValueError("Existing published archives are immutable; build into a new candidate directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = {p.name: p for p in (ROOT / "haos").iterdir() if p.is_file()}
    sources["hermes-constraints.txt"]=ROOT/"docs/evidence/hermes-dependencies.txt"
    sources["lab/core-constraints.txt"]=ROOT/"lab/core-constraints.txt"
    sources["lab/service-requirements.txt"]=ROOT/"lab/service-requirements.txt"
    sources.update({"companion/"+str(p.relative_to(ROOT/"companion")):p for p in (ROOT/"companion").rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc"})
    sources.update({"hads_next/" + p.name: p for p in (ROOT / "src/hads_next").glob("*.py")})
    if any(path.is_symlink() for path in sources.values()):
        raise ValueError("Source symlinks are forbidden")
    for name in ('ORCHESTRATION_SETUP_CS.md','ORCHESTRATION_REVIEW_CS.md','ORCHESTRATION_LIVE_ACCEPTANCE_CS.md','ORCHESTRATION_ACCEPTANCE_CS.md','RC10_CONNECTORS_CS.md','PR19_ACCEPTANCE_MATRIX_CS.md','RESTORE_VERIFIER_CONTRACT.md'):
        source=ROOT/'docs'/name
        if source.is_file():sources['docs/'+name]=source
    contents = {name: path.read_bytes() for name, path in sources.items()}
    try:
        revision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
        dependencies=set(sources.values())|{Path(__file__).resolve(),ROOT/'scripts/upgrade_next.py'}
        dirty=False
        for path in sorted(dependencies):
            try:previous=subprocess.check_output(['git','show',revision+':hads-next/'+str(path.relative_to(ROOT))],cwd=ROOT,stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:dirty=True;break
            if previous!=path.read_bytes():dirty=True;break
    except (OSError,subprocess.CalledProcessError):revision=None;dirty=None
    build_id=hashlib.sha256(json.dumps({'version':VERSION,'source':revision,'files':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(contents.items())}},sort_keys=True).encode()).hexdigest()
    manifest = {"version": VERSION, "slug": SLUG, "build_id":build_id,"scope": "haos_practical_repair_acceptance_candidate",
                "development_base_commit": "5fb2ba17cf0b50d483128bc0ccb834cc126dee47",
                "source_revision_at_build":revision,"worktree_modified_at_build":dirty,
                "installer_backup_policy":"no_preinstall_HA_or_cloud_backup_user_requested",
                "approved_provider_operations":["ha_mcp.ha_config_set_automation:single_proven_lighting_reference","spook.homeassistant.enable_entity:owner_intent"],
                "independent_restore_proof_required":True,
                "hermes_upstream_revision":"d923a5eb487a17c0a68801bba9ef0f56c81040a8",
                "live_haos_verified":False,"production_writes_enabled":False,"owned_virtual_reference_CAS_available":True,"selected_native_lighting_enable_available":True,"native_config_writes_enabled":False,
                "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                   "source": str(sources[name].relative_to(ROOT))} for name, data in sorted(contents.items())}}
    contents["PACKAGE_MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(contents.items()):
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.mtime = len(data), 0o755 if name == "run.sh" else 0o644, 0
            tar.addfile(item, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0) as gz:
        gz.write(buffer.getvalue())
    payload = compressed.getvalue()
    archive = output_dir / f"HADS_Next_{VERSION}-source.tar.gz"
    archive.write_bytes(payload)
    encoded = base64.encodebytes(payload).decode().rstrip("\n")
    script = TEMPLATE.replace("@@UPGRADER@@",(ROOT/"scripts/upgrade_next.py").read_text()).replace("@@EXTRACTOR@@", EXTRACTOR.strip()).replace("@@VERSION@@", VERSION).replace("@@SLUG@@",SLUG).replace("@@SHA@@", hashlib.sha256(payload).hexdigest()).replace("@@PAYLOAD@@", encoded)
    installer = output_dir / f"HADS_Next_install_{VERSION}.sh"
    installer.write_text(script)
    installer.chmod(0o755)
    hashes = output_dir / "SHA256SUMS"
    hashes.write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in (installer, archive)))
    return {"installer": str(installer), "source_archive": str(archive), "sha_manifest": str(hashes)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".test-tmp" / "haos-candidate" / VERSION)
    args = parser.parse_args()
    print(json.dumps(build_installer(args.output_dir), indent=2))
