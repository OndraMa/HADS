#!/usr/bin/env python3
"""Recover an uninstalled HADS Next with preserved local source; stdlib only.

Default inspection is read-only. Never uninstalls/stops a registered app, never
accesses app /data, and never executes an unverified installer.
"""
import argparse,fcntl,hashlib,json,os,stat,subprocess,tarfile,uuid
from pathlib import Path

SLUG='local_hads_next_practical'
INSTALLER_SHA256='8a23625c688b4282f2661e6b24000a8e5ce3e7886705b4dd02f33805fe5b13d1'
SOURCE_MANIFESTS={
 '1.0.0-rc2':'6ddca2d1deb6fdc0e7ada5dbdd503d6168de79c55334826371898b88a89fc5bf',
 '1.0.0-rc3':'4d62ee8f2d90e973a7fae1413a3bb0c9dd3a5bf4364666720a6d8df819453c74',
}

class RecoveryBlocked(ValueError):pass

def sha(data):return hashlib.sha256(data).hexdigest()

def ha_call(args):
    try:r=subprocess.run(['ha',*args],capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired):raise RecoveryBlocked('HA CLI není dostupné nebo čtení vypršelo. Nic nepřesouvej.') from None
    if r.returncode:raise RecoveryBlocked('Supervisor nepotvrdil čtení seznamu aplikací. Nelze předpokládat, že je aplikace odinstalovaná.')
    try:value=json.loads(r.stdout)
    except ValueError:raise RecoveryBlocked('HA CLI nevrátil podporovaný JSON. Nic nepřesouvej.') from None
    if not isinstance(value,dict) or value.get('result','ok')!='ok':raise RecoveryBlocked('Supervisor čtení odmítl.')
    return value.get('data',value)

def installed(command,call):
    value=call([command,'--raw-json'])
    rows=value.get('addons') if isinstance(value,dict) else None
    if not isinstance(rows,list) or any(not isinstance(row,dict) or not isinstance(row.get('slug'),str) for row in rows):raise RecoveryBlocked('Neočekávaný seznam aplikací. Zásah je zablokovaný.')
    return next(({k:row.get(k) for k in ('slug','version','state')} for row in rows if row['slug']==SLUG),None)

def verify_source(target):
    if target.is_symlink() or not target.is_dir() or target.resolve()!=target:raise RecoveryBlocked('Zdrojová cesta není bezpečný skutečný adresář.')
    manifest=target/'PACKAGE_MANIFEST.json'
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>65536:raise RecoveryBlocked('Chybí ověřitelný manifest. Ruční nebo neznámé zdroje nepřesouvám.')
    raw=manifest.read_bytes();version=next((v for v,h in SOURCE_MANIFESTS.items() if sha(raw)==h),None)
    if version is None:raise RecoveryBlocked('Manifest není z vydaného Next RC2/RC3. Nic nepřesouvám.')
    data=json.loads(raw)
    if data.get('version')!=version or data.get('slug')!='hads_next_practical':raise RecoveryBlocked('Nesouhlasí identita zdrojů.')
    files=data['files'];observed=set();total=0
    for item in target.rglob('*'):
        if item.is_symlink() or not (item.is_file() or item.is_dir()):raise RecoveryBlocked('Nepovolený typ souboru; nic nepřesouvám.')
        if item.is_file():
            total+=item.stat().st_size;observed.add(str(item.relative_to(target)))
            if total>4*1024*1024 or len(observed)>1024:raise RecoveryBlocked('Zdrojový adresář přesahuje limit.')
    if observed!=set(files)|{'PACKAGE_MANIFEST.json'} or 'config.yaml' not in files:raise RecoveryBlocked('Ve zdrojích jsou další nebo chybějící soubory. Vlastní úpravy nepřesouvám.')
    hashes={'PACKAGE_MANIFEST.json':sha(raw)}
    for name,meta in files.items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts:raise RecoveryBlocked('Neplatná cesta manifestu.')
        contents=(target/name).read_bytes()
        if len(contents)!=meta['bytes'] or sha(contents)!=meta['sha256']:raise RecoveryBlocked('Původní zdroje byly změněné; nic nepřesouvám.')
        hashes[name]=sha(contents)
    return version,hashes

def verify_installer(path):
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size>2*1024*1024:raise RecoveryBlocked('Instalátor RC3 musí být existující absolutní soubor, například /config/HADS_Next_install_1.0.0-rc3.sh.')
    if sha(path.read_bytes())!=INSTALLER_SHA256:raise RecoveryBlocked('SHA-256 nesouhlasí s vydaným RC3. Stáhni přesný soubor přes Download raw file; žádná změna se neprovede.')

def no_pending(root):
    for name in ('.hads-next-upgrade-pending.json','.hads-next-recovery-pending.json'):
        p=root/name
        if p.exists() or p.is_symlink():raise RecoveryBlocked('Existuje nedokončený zásah '+str(p)+'. Automatické opakování je zakázané; marker nemaž.')

def inspect(root,command,call=ha_call):
    current=installed(command,call);target=root/'hads_next_practical'
    result={'installed_app':current,'source_path':str(target),'source_exists':target.exists() or target.is_symlink(),'mode':'read_only'}
    if result['source_exists']:
        try:result['verified_source_version']=verify_source(target)[0]
        except (RecoveryBlocked,OSError,ValueError,KeyError):result['verified_source_version']=None
    return result

def run_installer(path):
    return subprocess.run(['bash',str(path),'--install-dev']).returncode

def recover(root,command,installer,call=ha_call,run=run_installer):
    root=Path(root);installer=Path(installer)
    if root.is_symlink() or not root.is_dir() or root.resolve()!=root or command not in {'apps','addons'}:raise RecoveryBlocked('Neplatný kořen místních aplikací.')
    verify_installer(installer)
    current=installed(command,call)
    if current:raise RecoveryBlocked('HADS Next je stále nainstalovaný (stav '+str(current['state'])+'). Zdroje nepřesouvám. Stav error není důkaz odinstalování; nic dalšího neodinstalovávej.')
    no_pending(root)
    target=root/'hads_next_practical'
    original=verify_source(target) if target.exists() or target.is_symlink() else None
    fd=os.open(root/'.hads-next-recovery.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_nlink!=1:raise RecoveryBlocked('Neplatný zámek obnovy.')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);no_pending(root)
        if installed(command,call):raise RecoveryBlocked('Seznam aplikací se změnil. Nic nepřesouvám.')
        identity=uuid.uuid4().hex;archive=None;preserved=None
        if original:
            version,hashes=verify_source(target)
            if original!=(version,hashes):raise RecoveryBlocked('Zdroje se změnily; zásah je zablokovaný.')
            archive=root/('.hads-next-recovery-sources-'+identity+'.tar.gz')
            with tarfile.open(archive,'x:gz') as out:
                for name in sorted(hashes):out.add(target/name,arcname=name,recursive=False)
            with tarfile.open(archive) as saved:
                members=saved.getmembers()
                if {m.name for m in members}!=set(hashes) or any(not m.isfile() or sha(saved.extractfile(m).read())!=hashes[m.name] for m in members):raise RecoveryBlocked('Archiv původních zdrojů nebyl ověřen; adresář ponechávám.')
            preserved=root/('.hads-next-preserved-source-'+identity)
        if installed(command,call):raise RecoveryBlocked('Aplikace byla mezitím nainstalovaná. Zdrojový adresář nepřesouvám.')
        receipt={'schema':1,'target':SLUG,'phase':'intent','source_backup':str(archive) if archive else None,'preserved_source_directory':str(preserved) if preserved else None,'installer_sha256':INSTALLER_SHA256,'automatic_retry':False,'previous_app_data_restore_proven':False}
        marker=root/'.hads-next-recovery-pending.json'
        with marker.open('x') as out:json.dump(receipt,out);out.flush();os.fsync(out.fileno())
        if original:
            verify_source(target)
            (target/'config.yaml').rename(target/'config.yaml.source-backup')
            target.rename(preserved)
        verify_installer(installer)
        if run(installer)!=0:raise RecoveryBlocked('RC3 instalátor nedokončil instalaci. Původní zdroje jsou uschované a marker zachovaný; neopakuj zásah naslepo.')
        current=installed(command,call)
        if not current or current.get('version')!='1.0.0-rc3' or current.get('state')!='started':raise RecoveryBlocked('Spuštěná verze RC3 není potvrzená. Zachovej marker a výstup, žádný automatický retry.')
        receipt['phase']='installed_RC3_verified'
        completed=root/('.hads-next-recovery-completed-'+identity+'.json')
        with completed.open('x') as out:json.dump(receipt,out);out.flush();os.fsync(out.fileno())
        marker.unlink();return receipt
    finally:os.close(fd)

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description='Kontrola nebo bezpečná obnova již odinstalovaného HADS Next. Nic nemaže v /data ani v konfiguraci domácnosti.')
    group=parser.add_mutually_exclusive_group();group.add_argument('--inspect',action='store_true');group.add_argument('--recover-and-install',type=Path,metavar='ABSOLUTNI_RC3_INSTALLER')
    args=parser.parse_args()
    root=next((p for p in (Path('/local_apps'),Path('/addons')) if p.is_dir() and not p.is_symlink()),None)
    if root is None:raise RecoveryBlocked('Chybí připojený adresář /local_apps nebo /addons.')
    command=None
    for name in ('apps','addons'):
        if subprocess.run(['ha',name,'--help'],capture_output=True,timeout=15).returncode==0:command=name;break
    if command is None:raise RecoveryBlocked('HA CLI neposkytuje podporovanou správu aplikací.')
    if args.recover_and_install:
        if os.geteuid()!=0:raise RecoveryBlocked('Obnova potřebuje správce místních zdrojů; spusť ji ve stejném HA terminálu jako původní instalátor.')
        result=recover(root,command,args.recover_and_install)
        print('Spuštěné RC3 je potvrzené. Původní zdroje: '+str(result['source_backup']))
        print('AI ponech vypnutou. Tento nástroj neobnovuje databázi případně odstraněnou při odinstalování.')
    else:print(json.dumps(inspect(root,command),ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (RecoveryBlocked,OSError,ValueError,KeyError,subprocess.TimeoutExpired) as error:raise SystemExit(str(error))
