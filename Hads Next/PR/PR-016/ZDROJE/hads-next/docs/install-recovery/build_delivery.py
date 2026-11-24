"""Rebuild the recovery download without changing any released RC3 file."""
import hashlib,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
DOC=ROOT/'hads-next/docs/install-recovery'
EVIDENCE=ROOT/'hads-next/docs/evidence/install-recovery-1'
OUT=ROOT/'KE_STAZENI/HADS_Next_RC3_obnova'
sha=lambda data:hashlib.sha256(data).hexdigest()

def main():
    acceptance=json.loads((EVIDENCE/'ACCEPTANCE.json').read_text())
    helper=(ROOT/'hads-next/scripts/recover_rc3.py').read_bytes()
    installer=(ROOT/'KE_STAZENI/HADS_Next_1.0.0-rc3/HADS_Next_install_1.0.0-rc3.sh').read_bytes()
    assert sha(helper)==acceptance['helper_sha256']
    assert sha(installer)==acceptance['original_RC3_installer_sha256']
    for architecture in ('amd64','arm64'):
        tests=json.loads((EVIDENCE/architecture/'offline-tests.json').read_text())
        report=json.loads((EVIDENCE/architecture/f'recovery-{architecture}.json').read_text())
        assert tests['passed'] and tests['tests_run']==195 and report['passed'] and not report['live_haos']
        assert tests['input_sha256']['scripts/recover_rc3.py']==sha(helper)
    files={
        'HADS_Next_obnovit_instalaci_RC3.py':helper,
        'HADS_Next_install_1.0.0-rc3.sh':installer,
        'README_CS.md':(DOC/'DOWNLOAD_CS.md').read_bytes(),
        'PODROBNY_POSTUP_CS.md':(DOC/'README_CS.md').read_bytes(),
        'ACCEPTANCE.json':(EVIDENCE/'ACCEPTANCE.json').read_bytes(),
    }
    files['SOUBORY_SHA256SUMS.txt']=''.join(f'{sha(data)}  {name}\n' for name,data in sorted(files.items())).encode()
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():(OUT/name).write_bytes(data)
    bundle=OUT/'HADS_Next_RC3_obnova.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,13,0,0,0))
            info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert all(archive.read(name)==data for name,data in files.items())
    (OUT/'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.name}\n' for p in sorted(OUT.iterdir()) if p.name!='SHA256SUMS'))
    print(json.dumps({'bundle':str(bundle.relative_to(ROOT)),'sha256':sha(bundle.read_bytes()),'files':len(files),'live_haos':False}))

if __name__=='__main__':main()
