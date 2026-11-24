"""Explicit RC3 source upgrade using native Supervisor lifecycle and backup. Never accesses app /data."""
import fcntl,hashlib,json,os,shutil,stat,subprocess,sys,tarfile,uuid
from pathlib import Path

SLUG='local_hads_next_practical'
VERSION='1.0.0-rc4'
RC3_MANIFEST='4d62ee8f2d90e973a7fae1413a3bb0c9dd3a5bf4364666720a6d8df819453c74'

class UpgradeBlocked(ValueError):pass

def digest(data):return hashlib.sha256(data).hexdigest()

def verify_tree(root,version,expected_manifest=None):
    root=Path(root)
    if root.is_symlink() or not root.is_dir() or root.resolve()!=root:raise UpgradeBlocked('Zdrojový adresář není bezpečný.')
    manifest_path=root/'PACKAGE_MANIFEST.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():raise UpgradeBlocked('Chybí původní manifest. Ruční instalaci nepřepisuji.')
    raw=manifest_path.read_bytes()
    if expected_manifest and digest(raw)!=expected_manifest:raise UpgradeBlocked('Původ neodpovídá vydanému RC3; žádné soubory se nepřepisují.')
    manifest=json.loads(raw)
    if manifest.get('version')!=version or manifest.get('slug')!='hads_next_practical':raise UpgradeBlocked('Jiná verze nebo identita aplikace.')
    files=manifest['files']
    if not isinstance(files,dict) or not 20<=len(files)<=1024:raise UpgradeBlocked('Neplatný seznam zdrojů.')
    actual=set()
    for item in root.rglob('*'):
        if item.is_symlink() or not (item.is_dir() or item.is_file()):raise UpgradeBlocked('Nepovolený typ souboru.')
        if item.is_file():actual.add(str(item.relative_to(root)))
    if actual!=set(files)|{'PACKAGE_MANIFEST.json'}:raise UpgradeBlocked('Adresář obsahuje cizí nebo chybějící soubory; vlastní úpravy nepřepisuji.')
    for name,meta in files.items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts:raise UpgradeBlocked('Neplatná cesta manifestu.')
        data=(root/name).read_bytes()
        if len(data)!=meta['bytes'] or digest(data)!=meta['sha256']:raise UpgradeBlocked('Zdroj se změnil; automatickou aktualizaci odmítám.')
    return manifest


def cli_call(command):
    result=subprocess.run(['ha',*command],capture_output=True,text=True,timeout=1800)
    if result.returncode:raise UpgradeBlocked('HA CLI odmítl krok '+command[1]+'. Zachovej zálohu zdrojů a protokol aplikace; žádný automatický retry.')
    if '--raw-json' not in command:return None
    try:value=json.loads(result.stdout)
    except ValueError:raise UpgradeBlocked('HA CLI nevrátil podporovaný JSON.') from None
    if not isinstance(value,dict) or value.get('result','ok')!='ok':raise UpgradeBlocked('Supervisor čtení nebo operaci nepotvrdil.')
    return value.get('data',value)


def upgrade(app_root,command,new_source,call=cli_call):
    root=Path(app_root);target=root/'hads_next_practical';new_source=Path(new_source)
    if root.is_symlink() or root.resolve()!=root or command not in {'apps','addons'}:raise UpgradeBlocked('Neplatný lokální kořen.')
    descriptor=os.open(root/'.hads-next-upgrade.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode) or os.fstat(descriptor).st_nlink!=1:raise UpgradeBlocked('Neplatný zámek.')
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        marker=root/'.hads-next-upgrade-pending.json'
        if marker.exists() or marker.is_symlink():raise UpgradeBlocked('Dřívější upgrade není dokončený; automatické opakování je zakázané.')
        recovery=root/'.hads-next-recovery-pending.json'
        if recovery.exists() or recovery.is_symlink():raise UpgradeBlocked('Dřívější obnova není dokončená. Marker ani data nemaž.')
        verify_tree(target,'1.0.0-rc3',RC3_MANIFEST);verify_tree(new_source,VERSION)
        call([command,'update','--help'])
        info=call([command,'info',SLUG,'--raw-json'])
        if not isinstance(info,dict) or info.get('version')!='1.0.0-rc3' or info.get('state') not in {'started','stopped'}:raise UpgradeBlocked('Potřebuji potvrzený Next RC3 ve stavu started nebo stopped. Stav error nepovažuji za zastavení; nic neodinstalovávej.')
        initial_state=info['state']
        identity=uuid.uuid4().hex
        backup=root/('.hads-next-rc3-sources-'+identity+'.tar.gz')
        with tarfile.open(backup,'x:gz') as archive:
            for item in sorted(target.rglob('*')):
                if item.is_file():archive.add(item,arcname=str(item.relative_to(target)),recursive=False)
        with tarfile.open(backup) as archive:
            for member in archive:
                if digest(archive.extractfile(member).read())!=digest((target/member.name).read_bytes()):raise UpgradeBlocked('Zálohu zdrojů se nepodařilo ověřit.')
        stage=root/('.hads-next-stage-'+identity);previous=root/('.hads-next-previous-'+identity)
        shutil.copytree(new_source,stage);verify_tree(stage,VERSION)
        verify_tree(target,'1.0.0-rc3',RC3_MANIFEST)
        receipt={'schema':1,'target':SLUG,'from':'1.0.0-rc3','to':VERSION,'source_backup':str(backup),'backup_scope':'sources_only_not_app_data_or_HAOS','phase':'intent','automatic_retry':False}
        with marker.open('x') as out:json.dump(receipt,out);out.flush();os.fsync(out.fileno())
        target.rename(previous)
        # The retained original is not a second app in the local app store.
        (previous/'config.yaml').rename(previous/'config.yaml.rc3-snapshot')
        stage.rename(target)
        call(['store','reload'])
        info=call([command,'info',SLUG,'--raw-json'])
        if not isinstance(info,dict) or info.get('version')!='1.0.0-rc3' or info.get('version_latest')!=VERSION or info.get('state')!=initial_state:raise UpgradeBlocked('Supervisor nepotvrdil přesný přechod RC3 → RC4. Dále nepokračuji.')
        verify_tree(target,VERSION)
        # Native app update creates its own partial data backup. The source
        # snapshot above is never presented as an app-data or HAOS restore.
        call([command,'update',SLUG,'--backup','--raw-json'])
        info=call([command,'info',SLUG,'--raw-json'])
        if isinstance(info,dict) and info.get('version')==VERSION and info.get('state')=='stopped' and initial_state=='started':
            call([command,'start',SLUG]);info=call([command,'info',SLUG,'--raw-json'])
        if not isinstance(info,dict) or info.get('version')!=VERSION or info.get('state')!=initial_state:raise UpgradeBlocked('Cílová verze nebo stav RC4 nejsou potvrzené. Zachovej důkazy; žádná automatická obnova ani opakování.')
        receipt['phase']='version_confirmed';receipt['state']=initial_state
        completed=root/('.hads-next-upgrade-completed-'+identity+'.json')
        with completed.open('x') as out:json.dump(receipt,out);out.flush();os.fsync(out.fileno())
        marker.unlink()
        return receipt
    finally:os.close(descriptor)


if __name__=='__main__':
    try:
        if len(sys.argv)!=4 or sys.argv[1] not in {'/addons','/local_apps'}:raise UpgradeBlocked('Nepodporovaný kořen místních aplikací.')
        result=upgrade(*sys.argv[1:]);print('RC4 potvrzené, stav '+result['state']+'. Záloha původních zdrojů: '+result['source_backup'])
    except (UpgradeBlocked,OSError,ValueError,KeyError) as error:raise SystemExit(str(error))
