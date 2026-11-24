"""Install pinned frontend wheel for native Activity API tests under disk limits.

Core requires frontend for Activity. All wheel Python code and JS assets remain
original; only unused UI translations and JS source maps are omitted. This is
a laboratory asset reduction, never a production Core installation procedure.
"""
import hashlib
from pathlib import Path
import shutil
import sysconfig
import tempfile
from urllib.request import urlopen
import zipfile

URL='https://files.pythonhosted.org/packages/e9/54/7505239a71ab5a850da8ea0283722e26d504a754aa41d8263e1637f02c82/home_assistant_frontend-20261028.4-py3-none-any.whl'
SHA256='e5e59b82e63b288323d35886272f2e490ee62f6c7aaa2c56e7ef45e300d44757'


def main():
    destination=Path(sysconfig.get_path('purelib'))
    with tempfile.TemporaryFile() as wheel:
        digest=hashlib.sha256();size=0
        with urlopen(URL,timeout=30) as response:
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>118000000:raise ValueError('wheel_too_large')
                digest.update(chunk);wheel.write(chunk)
        if digest.hexdigest()!=SHA256:raise ValueError('frontend_sha256_mismatch')
        wheel.seek(0)
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.infolist():
                path=Path(member.filename)
                if path.is_absolute() or '..' in path.parts or path.parts[0] not in {'hass_frontend','home_assistant_frontend-20261028.4.dist-info'}:raise ValueError('invalid_wheel_path')
                if member.filename.endswith('.map') or ('/translations/' in member.filename and not member.filename.endswith(('/en.json','/cs.json'))):continue
                target=destination/path
                if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(member) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
    print('Installed verified frontend 20261028.4 for lab; unused translations and source maps omitted.',flush=True)


if __name__=='__main__':main()
