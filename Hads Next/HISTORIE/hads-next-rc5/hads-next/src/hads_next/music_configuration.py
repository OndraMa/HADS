"""Owner-only private optional MA connection, disabled by default."""
import json
import os
from pathlib import Path
import secrets

from .music_assistant import MusicMCP,MusicAssistantReader


class MusicConfiguration:
    def __init__(self,data_dir):
        self.path=Path(data_dir)/'music-assistant.json'
        self.value=None;self.error=None
        try:
            if self.path.exists():
                if self.path.is_symlink() or self.path.stat().st_size>8192 or self.path.stat().st_mode&0o077:raise ValueError()
                self.value=json.loads(self.path.read_text());self._reader(self.value)
        except (OSError,ValueError,TypeError):
            self.value=None;self.error='Připojení Music Assistantu nelze bezpečně načíst.'

    @staticmethod
    def _reader(value):
        if not isinstance(value,dict) or set(value)!={'endpoint','token','mapping','enabled','principal'} or type(value['enabled']) is not bool or not isinstance(value['principal'],str) or not value['principal']:
            raise ValueError('Neplatné nastavení Music Assistantu.')
        return MusicAssistantReader(MusicMCP(value['endpoint'],value['token']),value['mapping'])

    def reader(self):
        return self._reader(self.value) if self.value and self.value['enabled'] else None

    def public_status(self):
        value=self.value
        return {'enabled':bool(value and value['enabled']),'endpoint':value['endpoint'] if value else '',
                'mapping':value['mapping'] if value else {},'last_error':self.error}

    def configure(self,*,endpoint,token,mapping,enabled,principal):
        if self.path.is_symlink():raise ValueError('Neplatná cesta nastavení.')
        if not token and self.value:
            if endpoint!=self.value['endpoint']:raise ValueError('Pro jinou adresu zadej nový token.')
            token=self.value['token']
        value={'endpoint':endpoint,'token':token,'mapping':mapping,'enabled':enabled,'principal':principal}
        self._reader(value)
        raw=json.dumps(value)
        if len(raw.encode())>8192:raise ValueError('Nastavení je příliš velké.')
        temporary=self.path.with_name('.ma-'+secrets.token_hex(8))
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'w') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:temporary.unlink(missing_ok=True)
        self.value=value;self.error=None
