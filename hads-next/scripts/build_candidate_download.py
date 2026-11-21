"""Package exact CI-tested assets plus source and Czech instructions for GitHub."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]


def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])


def zip_add(archive,name,data):
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
    info.external_attr=0o100644<<16;archive.writestr(info,data)


def build(ref,package,output):
    commit=git('rev-parse',ref+'^{commit}').decode().strip();package=Path(package);output=Path(output)
    if output.exists():raise ValueError('Candidate output must be a new directory; released archives are immutable.')
    archive=next(package.glob('HADS_Next_*-source.tar.gz'))
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        if any(not m.isfile() or m.size>1024*1024 for m in members):raise ValueError('Invalid payload')
        manifest=json.loads(tar.extractfile('PACKAGE_MANIFEST.json').read())
        if manifest['source_revision_at_build']!=commit or manifest['worktree_modified_at_build'] is not False:raise ValueError('Source provenance differs')
        if {m.name for m in members}!=set(manifest['files'])|{'PACKAGE_MANIFEST.json'}:raise ValueError('Payload membership differs')
        for name,meta in manifest['files'].items():
            data=tar.extractfile(name).read()
            if hashlib.sha256(data).hexdigest()!=meta['sha256'] or data!=git('show',commit+':hads-next/'+meta['source']):raise ValueError('Payload differs from Git source: '+name)
        manual=tar.extractfile('DOCS.md').read()
    version=manifest['version'];installer=package/('HADS_Next_install_'+version+'.sh')
    subprocess.run(['bash',str(installer),'--verify'],check=True,capture_output=True)
    assets={installer.name:installer.read_bytes(),archive.name:archive.read_bytes(),
        'PACKAGE_MANIFEST.json':(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode(),
        'NAVOD_CS.md':manual}
    for name in ('RC10_CONNECTORS_CS.md','PR19_ACCEPTANCE_MATRIX_CS.md','ORCHESTRATION_SETUP_CS.md','RESTORE_VERIFIER_CONTRACT.md','ORCHESTRATION_LIVE_ACCEPTANCE_CS.md','orchestration-matrix.json'):
        assets[name]=git('show',commit+':hads-next/docs/'+name)
    assets['CTI_ME_NEJDRIVE_CS.txt']=(f'HADS Next {version} — instalační kandidát, živá přejímka čeká.\nZdroj: {commit}\nSestavení: {manifest["build_id"]}\n\n'
        'Pro ověřené RC6–RC9 použij --upgrade, neodinstalovávej aplikaci. Přesný postup je v NAVOD_CS.md.\n'
        'Nevytváří se nová předinstalační HA/OneDrive záloha; zálohové ochrany oprav zůstávají.\n'
        'Soukromé adresy a klíče nejsou součástí balíčku. Žádné placené volání se tím neschvaluje.\n'
        'Obecné statistické/registry/skriptové/Zigbee opravy nejsou implementované automatické operace.\n'
        'Aktuální testy a živá omezení jsou na větvi PR #19.\n').encode('utf-8-sig')
    source_paths=git('ls-tree','-r','--name-only',commit,'--','hads-next/src','hads-next/tests','hads-next/scripts','hads-next/lab','hads-next/haos','hads-next/companion','hads-next/pyproject.toml','.github/workflows/hads-next-orchestration.yml').decode().splitlines()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as zip:
        for name in sorted(source_paths):zip_add(zip,name,git('show',commit+':'+name))
    assets['ZDROJE_A_TESTY.zip']=stream.getvalue()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as zip:
        for name,data in sorted(assets.items()):zip_add(zip,name,data)
    assets['HADS_Next_'+version+'-komplet-kandidat.zip']=stream.getvalue()
    assets['SHA256SUMS']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(assets.items())).encode()
    output.mkdir(parents=True)
    for name,data in assets.items():(output/name).write_bytes(data)
    return {'source_commit':commit,'version':version,'build_id':manifest['build_id'],'files':len(assets),'output':str(output)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ref',required=True);parser.add_argument('--package',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(build(args.ref,args.package,args.output),indent=2))
