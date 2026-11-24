#!/usr/bin/env bash
set -euo pipefail
umask 077
VERSION="4.5.0"
TARGET="/addons/hads4"
BACKUP_ROOT="/share/hads4_installer_backups"
EXPECTED_SHA256="f96a2d7c5136d551b35ebda6607412b83b794501dfa938cfb60da1f06f4a8958"
STAMP="$(date +%Y%m%d-%H%M%S)-$$"
for TOOL in python3 tar sha256sum base64 mktemp; do
  command -v "$TOOL" >/dev/null || { echo "Chybí nástroj: $TOOL"; exit 1; }
done
STAGING="$(mktemp -d /tmp/hads4-4.5.0.XXXXXX)"
cleanup() {
  case "$STAGING" in /tmp/hads4-4.5.0.*) rm -rf -- "$STAGING" ;; *) echo "Neplatná dočasná cesta; automatický úklid vynechán." ;; esac
}
trap cleanup EXIT
mkdir "$STAGING/addon"
base64 -d > "$STAGING/hads4.tar.gz" <<'HADS4_PAYLOAD'
dGVzdC1vbmx5LXRlbXBsYXRl
HADS4_PAYLOAD
ACTUAL_SHA256="$(sha256sum "$STAGING/hads4.tar.gz" | awk '{print $1}')"
[ "$ACTUAL_SHA256" = "$EXPECTED_SHA256" ] || { echo 'Nesouhlasí SHA-256 balíku.'; exit 1; }
tar -xzf "$STAGING/hads4.tar.gz" -C "$STAGING/addon"
for FILE in config.yaml hads4.py first_officer.py repair_engine.py tool_adapters.py incident_workflow.py site_tools.py web/app.js web/webmcp.js web/style.css web/index.html; do
  test -f "$STAGING/addon/$FILE"
done
grep -q 'version: "4.5.0"' "$STAGING/addon/config.yaml"
python3 -m py_compile "$STAGING/addon/"*.py

# Extraction is for offline inspection only. It never installs or invokes HA.
if [ "${1:-}" = '--extract-only' ]; then
  [ "$#" = 2 ] || { echo 'Použití: --extract-only /tmp/hads4-inspect-unikatni'; exit 1; }
  [[ "$2" =~ ^/tmp/hads4-inspect-[A-Za-z0-9._-]+$ ]] || { echo 'Rozbalení vyžaduje jediný nový adresář /tmp/hads4-inspect-*'; exit 1; }
  [ ! -e "$2" ] && [ ! -L "$2" ] || { echo 'Cíl již existuje; nic nepřepisuji.'; exit 1; }
  mv "$STAGING/addon" "$2"
  echo "Ověřený payload rozbalen do $2. Nic nebylo nainstalováno."
  exit 0
fi
[ "$#" = 0 ] || { echo 'Neznámé argumenty.'; exit 1; }
command -v ha >/dev/null || { echo 'Instalace vyžaduje HAOS terminál s příkazem ha. Nic nebylo změněno.'; exit 1; }
[ ! -L "$TARGET" ] && [ ! -L "$BACKUP_ROOT" ] || { echo 'Instalační cíl ani zálohy nesmí být symlink.'; exit 1; }

echo 'Vytvářím povinnou plnou HA zálohu včetně databáze. Může trvat několik minut.'
BACKUP_NAME="HADS-4.5.0-pred-instalaci-$STAMP"
ha backups new --name "$BACKUP_NAME" --homeassistant-exclude-database=false --raw-json > "$STAGING/backup-created.json"
BACKUP_SLUG="$(python3 - "$STAGING/backup-created.json" <<'PY'
import json,re,sys
value=json.load(open(sys.argv[1],encoding='utf-8'))
value=value.get('data',value)
slug=value.get('slug','')
if not isinstance(slug,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',slug):
    raise SystemExit('Supervisor nepotvrdil dokončenou zálohu; instalace zastavena.')
print(slug)
PY
)"
ha backups info "$BACKUP_SLUG" --raw-json > "$STAGING/backup-verified.json"
python3 - "$STAGING/backup-verified.json" "$BACKUP_SLUG" "$BACKUP_NAME" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'));v=v.get('data',v)
if not (v.get('slug')==sys.argv[2] and v.get('name')==sys.argv[3] and v.get('type')=='full' and v.get('homeassistant') and v.get('homeassistant_exclude_database') is False and float(v.get('size') or 0)>0):
    raise SystemExit('Nezávislé ověření plné zálohy selhalo; instalace zastavena.')
print('Metadata plné zálohy ověřena. Test obnovy nebyl proveden.')
PY

EXISTING=0
if ha addons info local_hads4 --raw-json > "$STAGING/previous-addon.json" 2>/dev/null; then EXISTING=1; fi
mkdir -p "$BACKUP_ROOT" /addons
BACKUP="$BACKUP_ROOT/hads4_$STAMP"
[ ! -e "$BACKUP" ] || { echo 'Kolize zálohy zdroje; instalace zastavena.'; exit 1; }
if [ -d "$TARGET" ]; then
  mv "$TARGET" "$BACKUP"
  echo "Původní zdroj zachován v $BACKUP"
fi
if ! mv "$STAGING/addon" "$TARGET"; then
  if [ -d "$BACKUP" ] && [ ! -e "$TARGET" ]; then mv "$BACKUP" "$TARGET"; fi
  echo 'Přesun nové verze selhal.'; exit 1
fi
chmod 755 "$TARGET" "$TARGET/web" "$TARGET/dashboard" "$TARGET/translations"
find "$TARGET" -type f -exec chmod 644 {} +
ha addons reload
if [ "$EXISTING" = 1 ]; then
  ha addons rebuild local_hads4
else
  ha addons install local_hads4
fi
ha addons start local_hads4
ha addons info local_hads4 --raw-json > "$STAGING/installed.json"
python3 - "$STAGING/installed.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'));v=v.get('data',v)
if v.get('version')!='4.5.0' or v.get('state')!='started':
    raise SystemExit('Zdroj je připraven, ale běh 4.5.0 nebyl potvrzen. Zkontrolujte log doplňku.')
PY
echo "HADS 4.5.0 spuštěn. Předinstalační HA záloha: $BACKUP_SLUG"
echo 'Obnovte panel Ctrl+F5 a spusťte hlubokou analýzu. Funkčnost oprav ověřte na jednom konkrétním plánu.'
echo 'Databáze HADS ani starší HADS 2/3 nebyly odstraněny. Stav databáze a rozpracovaných rozhodnutí se zachoval; nic se samo nespustilo.'
