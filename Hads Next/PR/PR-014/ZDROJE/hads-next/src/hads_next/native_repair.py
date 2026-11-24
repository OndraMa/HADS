"""Fixed native automation state service. No configuration or general service API."""
import json,re
from urllib.request import Request,build_opener
from urllib.parse import urlsplit
from .repair import RepairEngine,RepairBlocked,canonical,digest
from .observability import _NoRedirect,bounded_body

class AutomationStateTransport:
    def __init__(self,origin,token,*,supervisor=False,loopback=False):
        p=urlsplit(origin)
        if p.username or p.password or p.query or p.fragment or p.path not in {'','/'}:raise ValueError('Pevný Core origin bez přihlašovacích údajů.')
        if not (p.scheme=='https' or supervisor and origin=='http://supervisor' or loopback and p.scheme=='http' and p.hostname=='127.0.0.1'):raise ValueError('HTTPS required')
        self.origin,self.token,self.prefix=origin,token,'/core' if supervisor else ''
        self.opener=build_opener(_NoRedirect)
    def set_enabled(self,entity_id,enabled):
        if not re.fullmatch(r'automation\.[a-z0-9_]+',entity_id) or type(enabled) is not bool:raise RepairBlocked('Nepovolená služba nebo cíl.')
        data={'entity_id':entity_id}
        if not enabled:data['stop_actions']=False
        request=Request(self.origin+self.prefix+'/api/services/automation/'+('turn_on' if enabled else 'turn_off'),data=canonical(data).encode(),method='POST',headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with self.opener.open(request,timeout=10) as response:
                value=json.loads(bounded_body(response,128000,10))
                if response.status!=200 or not isinstance(value,list):raise ValueError()
        except Exception:raise RepairBlocked('Nativní stavová služba nebyla potvrzena. Výsledek je neznámý; žádný automatický retry.') from None


def lighting_policy(configuration):
    """Positive exact shape; never enable templates, blueprints or risky services."""
    if not isinstance(configuration,dict) or set(configuration)-{'id','alias','description','mode','triggers','conditions','actions','initial_state'}:raise RepairBlocked('Nepodporovaný tvar automatizace.')
    if not isinstance(configuration.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',configuration['id']):raise RepairBlocked('Neplatné ID automatizace.')
    if configuration.get('initial_state') is False or configuration.get('mode','single')!='single' or configuration.get('conditions',[])!=[]:raise RepairBlocked('Podporována je jednoduchá světelná automatizace bez podmínek.')
    triggers=configuration.get('triggers');actions=configuration.get('actions')
    if not isinstance(triggers,list) or len(triggers)!=1 or not isinstance(actions,list) or len(actions)!=1:raise RepairBlocked('Jeden trigger a jediná světelná akce.')
    trigger=triggers[0];action=actions[0]
    if set(trigger)-{'trigger','entity_id','to','from'} or trigger.get('trigger')!='state' or not re.fullmatch(r'(binary_sensor|input_button)\.[a-z0-9_]+',str(trigger.get('entity_id',''))):raise RepairBlocked('Nepodporovaný spouštěč.')
    if trigger['entity_id'].startswith('binary_sensor.') and trigger.get('to')!='on':raise RepairBlocked('Senzor musí spouštět jen při přechodu na on.')
    if set(action)!={'action','target'} or action['action']!='light.turn_on' or not isinstance(action['target'],dict) or set(action['target'])!={'entity_id'} or not re.fullmatch(r'light\.[a-z0-9_]+',str(action['target']['entity_id'])):raise RepairBlocked('Katalog dovoluje pouze light.turn_on na jednom explicitním světle.')
    return trigger['entity_id'],action['target']['entity_id']

class AutomationEnableEngine(RepairEngine):
    _operation='core.enable_lighting_automation'
    _risk='bounded_native_lighting_enable'
    _snapshot_scope='automation_configuration_and_enable_state_not_HAOS'
    _preconditions=('owner_declared_expected_enabled','fresh_exact_configuration_and_state','no_running_actions','one_explicit_light','no_concurrent_editor_confirmed','unexpired_owner_approval')
    def __init__(self,db,root,app,entity_id):
        if not re.fullmatch(r'automation\.[a-z0-9_]+',entity_id):raise RepairBlocked('Neplatný cíl.')
        self.app,self.entity_id=app,entity_id
        self.filename=digest(entity_id)+'.json'
        super().__init__(db,root,allowed_files={self.filename},owner=app.owner())
    def _read(self,filename):
        if filename!=self.filename or self.app.core is None:raise RepairBlocked('Nedostupný Core nebo cizí cíl.')
        state=self.app.core.states(self.entity_id)
        if not isinstance(state,dict) or state.get('state') not in {'on','off'}:raise RepairBlocked('Stav automatizace není čitelný.')
        config_id=state.get('attributes',{}).get('id')
        if not isinstance(config_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',config_id):raise RepairBlocked('Automatizace nemá čitelné ID konfigurace.')
        config=self.app.core.automation_config(config_id);trigger,light=lighting_policy(config)
        if config['id']!=config_id or state.get('attributes',{}).get('current',0)!=0:raise RepairBlocked('Konfigurace se neshoduje nebo běží akce.')
        light_state=self.app.core.states(light);trigger_state=self.app.core.states(trigger)
        # An input_button has no timestamp before its first press. Its normal
        # initial state is unknown, unlike an unavailable entity or sensor.
        rejected_trigger_states={'unavailable'} if trigger.startswith('input_button.') else {'unavailable','unknown'}
        if not isinstance(light_state,dict) or light_state.get('state') not in {'on','off'} or not isinstance(trigger_state,dict) or not isinstance(trigger_state.get('state'),str) or trigger_state.get('state') in rejected_trigger_states:raise RepairBlocked('Cíl nebo spouštěč nejsou dostupné.')
        return canonical({'id':config_id,'entity_id':self.entity_id,'configuration':config,'enabled':state['state']=='on',
            'state_context':state.get('context',{}).get('id'),'last_changed':state.get('last_changed'),'light':light,'trigger':trigger}).encode()
    def _valid_transition(self,original,proposed):
        return type(original.get('enabled')) is bool and proposed=={**original,'enabled':not original['enabled']}
    def _replace(self,filename,content):
        if filename!=self.filename or self.app.automation_writer is None:raise RepairBlocked('Nativní vykonavatel není připojený.')
        value=json.loads(content)
        # Read once more immediately before the fixed native state service.
        current=json.loads(self._read(filename))
        if any(current.get(k)!=value.get(k) for k in current if k!='enabled') or current['enabled']==value['enabled']:raise RepairBlocked('Předpoklady se změnily; nevykonávám službu.')
        self.app.automation_writer.set_enabled(self.entity_id,value['enabled'])
    def _readback_matches(self,proposed,current):
        # Native enable creates a new context/time; it is not a config CAS.
        return current['enabled']==proposed['enabled'] and all(current[k]==proposed[k] for k in ('id','entity_id','configuration','light','trigger'))
    def prepare_enable(self,incident_id,evidence_ids,*,rollback_of=None):
        raw=self._read(self.filename);original=json.loads(raw)
        if original['enabled'] and not rollback_of:raise RepairBlocked('Automatizace už je zapnutá.')
        if not original['enabled'] and rollback_of:raise RepairBlocked('Automatizace už je vypnutá.')
        proposed={**original,'enabled':not original['enabled']}
        document={'schema':1,'operation':self._operation,'incident_id':incident_id,'target':{'root':str(self.root),'filename':self.filename,'automation_id':original['id'],'entity_id':self.entity_id},'original':original,'proposed':proposed,'original_sha256':digest(raw),'reason':'Vlastník očekává aktivní světelnou automatizaci; skutečný stav je vypnutý.' if not rollback_of else 'Samostatně schválený návrat pouze aktivace automatizace.','evidence_ids':sorted(set(evidence_ids)),'risk':self._risk,'backup':{'required':'verified_local_snapshot','scope':self._snapshot_scope,'onedrive_required':False},'preconditions':list(self._preconditions),'expected_result':'Automatizace bude aktivní. Její skutečný trigger musí následně rozsvítit schválené světlo.','verification':{'automation_id':original['id'],'automation_entity_id':self.entity_id,'entity_id':original['light'],'state':'on','watch_seconds':10,'physical_confirmation_required':True},'rollback':{'supported':True,'separate_approval_required':True,'scope':'enable_state_only_no_physical_undo','rollback_of':rollback_of},'manual_alternative':'V HA otevři tuto automatizaci, zkontroluj trigger a světlo a po vlastní kontrole ji zapni. Jiné nastavení neměň.','non_atomic_state_service':True,'concurrency_limitation':'Není to config CAS. Po dobu schválení nepoužívej jiný editor cíle; služba konfiguraci nepřepisuje. Při zjištěném konfliktu se další zásahy zastaví.'}
        if not evidence_ids:raise RepairBlocked('Chybí důkazy.')
        return self._register_plan(document,raw)
