"""Trusted model endpoint configuration. No automatic paid calls or OAuth claim."""
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit
from urllib.request import Request,build_opener

from .observability import _NoRedirect,redact,bounded_body


class ProviderDisabled(ValueError):pass


class AIProvider:
    def __init__(self,data_dir):
        self.path=Path(data_dir)/'ai-provider.json'
        self.lock=threading.RLock()
        self._settings=None
        self._load_error=None
        try:
            if self.path.exists():
                if self.path.is_symlink() or self.path.stat().st_size>8192 or self.path.stat().st_mode & 0o077:
                    raise ProviderDisabled('Soubor poskytovatele nemá bezpečná oprávnění.')
                value=json.loads(self.path.read_text());self._validate(value);self._settings=value
        except (ValueError,OSError):self._load_error='Nastavení AI nelze bezpečně přečíst; sběr důkazů pokračuje bez AI.'

    @staticmethod
    def _validate(value):
        if not isinstance(value,dict) or set(value)!={'endpoint','model','api_key','consent','principal'} \
                or any(not isinstance(value[key],str) for key in ('endpoint','model','api_key','principal')):
            raise ProviderDisabled('Neplatná konfigurace AI.')
        url=urlsplit(value['endpoint'])
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment \
                or not url.path.endswith('/chat/completions'):
            raise ProviderDisabled('Je potřeba pevná HTTPS adresa OpenAI-compatible chat/completions, bez přihlašovacích údajů v URL.')
        if not re.fullmatch(r'[a-zA-Z0-9_./:-]{1,128}',value['model']) or not 8<=len(value['api_key'])<=2048 \
                or any(c in value['api_key'] for c in '\r\n') or type(value['consent']) is not bool or not value['principal']:
            raise ProviderDisabled('Neplatný model, klíč nebo souhlas.')

    def configure(self,*,endpoint,model,api_key,consent,principal):
        with self.lock:
            if self.path.is_symlink():raise ProviderDisabled('Nastavení AI nesmí být symlink.')
            if not api_key and self._settings:
                if endpoint!=self._settings['endpoint'] or model!=self._settings['model']:
                    raise ProviderDisabled('Pro jiný endpoint nebo model zadej klíč znovu.')
                api_key=self._settings['api_key']
            value={'endpoint':endpoint,'model':model,'api_key':api_key,'consent':consent,'principal':principal}
            self._validate(value)
            temporary=self.path.with_name('.ai-provider-'+secrets.token_hex(8))
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                with os.fdopen(fd,'w') as output:
                    json.dump(value,output);output.flush();os.fsync(output.fileno())
                os.replace(temporary,self.path)
            finally:temporary.unlink(missing_ok=True)
            self._settings=value;self._load_error=None

    def public_status(self):
        with self.lock:
            value=self._settings
            return {'configured':value is not None,'enabled':bool(value and value['consent']),
                'endpoint':value['endpoint'] if value else 'https://api.openai.com/v1/chat/completions',
                'model':value['model'] if value else '', 'max_model_calls_per_case':8,'daily_model_call_limit':12,
                'max_output_tokens_per_call':1024,'oauth_supported':False,'last_error':self._load_error}

    def fingerprint(self):
        import hashlib
        with self.lock:return hashlib.sha256(json.dumps(self._settings,sort_keys=True).encode()).hexdigest()

    def sender(self):
        # Bind endpoint, key and model for the entire immutable job policy. An
        # owner editing settings mid-run cannot send an old key to a new host.
        with self.lock:
            if not self._settings or not self._settings['consent']:raise ProviderDisabled('AI je vypnutá; bez výslovného souhlasu se model nevolá.')
            settings=dict(self._settings)
        opener=build_opener(_NoRedirect)
        def send(body):
            with self.lock:
                if self._settings!=settings or not self._settings['consent']:
                    raise ProviderDisabled('Nastavení AI se změnilo; další volání zastavena.')
            messages=body.get('messages')
            if not isinstance(messages,list) or len(messages)>80:raise ProviderDisabled('Kontext modelu překročil limit.')
            payload={'model':settings['model'],'messages':messages,'max_tokens':1024,'stream':False,'n':1}
            if 'tools' in body:payload['tools']=body['tools'];payload['tool_choice']='auto'
            data=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
            if len(data)>192000:raise ProviderDisabled('Kontext modelu překročil limit.')
            request=Request(settings['endpoint'],data=data,method='POST',headers={
                'Authorization':'Bearer '+settings['api_key'],'Content-Type':'application/json'})
            try:
                with opener.open(request,timeout=30) as response:
                    raw=bounded_body(response,128000,30)
                    if response.status!=200:raise ProviderDisabled('Neplatný výsledek poskytovatele.')
                    result=json.loads(raw)
                    if not isinstance(result,dict) or not isinstance(result.get('choices'),list):raise ValueError()
                    return redact(result)
            except Exception:
                raise ProviderDisabled('Volání modelu selhalo. Výsledek a případné účtování ověř u poskytovatele; další pokus není automatický.') from None
        return settings['model'],send
