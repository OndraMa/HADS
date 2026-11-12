"""Validate analyst proposals and hand supported drafts to the existing planner.

A suggestion is not a RepairPlan or approval. Production execution remains off.
The only bridge is invoked by a trusted laboratory caller with an independently
constructed existing RepairEngine. Nothing here is an AI tool or an HA writer.
"""
from dataclasses import dataclass
import hashlib
import json
import re

from .evidence import canonical
from .observability import redact


def supported_catalog():
    return {'production_operations':[],'native_operations':[{'operation':'enable_lighting_automation','scope':'owner_selected_single_light_state_automation','approval_required':True,'physical_confirmation_required':True,'native_config_write':False,'atomic_CAS':False,'exclusive_editor_confirmation_required':True,'rollback':'disable_future_triggers_only','trigger':'binary_sensor_to_on_or_input_button','action':'light.turn_on_on_one_explicit_light'}],'managed_test_operations':[{'operation':'replace_managed_reference','scope':'integration_owned_virtual_test_reference','server_atomic_CAS':True,'approval_required':True,'companion_required':True}],
        'laboratory_operations':[{'operation':'replace_entity_reference','scope':'isolated_fixture_or_disconnected_virtual_Core_only',
            'approval_required':True,'backup':'verified_single_object_snapshot','functional_verification_required':True,
            'rollback':'single_object_with_separate_approval'}],
        'production_limitation_cs':'Dostupná je pouze vlastní CAS testovací reference a zvlášť povolené nativní zapnutí jednoduché světelné automatizace. Obecné konfigurační a rizikové zásahy jsou zakázané; živá přejímka čeká.'}


@dataclass(frozen=True)
class RepairSuggestion:
    serialized:str

    @property
    def suggestion_id(self):return hashlib.sha256(self.serialized.encode()).hexdigest()

    @property
    def document(self):return json.loads(self.serialized)


def interpret_proposal(proposal,case):
    if proposal is None:return None
    if isinstance(proposal,dict) and proposal.get('operation')=='enable_lighting_automation':return native_enable_suggestion(proposal,case)
    base={'schema':1,'incident_id':case['incident']['id'],'production_executable':False,
        'status':'manual_or_test_required','summary_cs':'Návrh není dostatečně doložený pro podporovanou opravu.',
        'manual_steps_cs':['Ověř zamýšlené chování a doplň chybějící důkazy. Žádná automatická změna není připravena.'],
        'evidence_ids':[],'approval_required':True}
    def fallback(reason):return RepairSuggestion(canonical({**base,'summary_cs':reason}))
    if not isinstance(proposal,dict) or not {'target','change','reason','evidence_ids'}<=set(proposal) or set(proposal)-{
        'operation','target','change','reason','evidence_ids','risk','backup','preconditions','verification','rollback','manual_alternative'}:
        return fallback('Návrh má nepodporovaný nebo neúplný formát. Pokračuj diagnostickým testem.')
    managed=proposal.get('operation')=='replace_managed_reference'
    if proposal.get('operation','replace_entity_reference') not in {'replace_entity_reference','replace_managed_reference'}:return fallback('Tento typ opravy není v ověřeném katalogu. Potřebuje ruční kontrolu nebo další test.')
    target,change,reason,cited=proposal['target'],proposal['change'],proposal['reason'],proposal['evidence_ids']
    if not isinstance(target,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',target) or not isinstance(change,dict) or set(change)!={'from','to'}:
        return fallback('Chybí přesný cíl a jediná změna reference.')
    if not all(isinstance(x,str) and re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z0-9_]+',x) for x in change.values()) or change['from']==change['to']:
        return fallback('Navržená změna entity není platná nebo by nic nezměnila.')
    if not isinstance(reason,str) or not 1<=len(reason)<=2000 or not isinstance(cited,list) or not 1<=len(cited)<=20 or not all(isinstance(x,str) for x in cited):
        return fallback('Chybí kontrolovatelný důvod nebo citace návrhu.')
    evidence=case['evidence'];known={x['evidence_id'] for x in evidence}
    if not set(cited)<=known:return fallback('Návrh odkazuje na neexistující důkazy; nelze jej předat plánovači.')
    def data(row):
        value=row.get('payload',{}).get('data')
        return value if isinstance(value,dict) and row.get('source')=='ha_core' else {}
    if managed:
        from .managed_repair import MISSING,TARGET,ManagedReferenceEngine
        configs=[x for x in evidence if x['kind']=='hads_get_owned_reference' and x.get('source')=='ha_core_ws']
        if not configs or target!='hads_next_reference_test' or change!={'from':MISSING,'to':TARGET}:return fallback('Nepodporovaná vlastní reference.')
        config=configs[-1]
        try:ManagedReferenceEngine._entity(config['payload']['data'])
        except ValueError:return fallback('Neplatná companion reference.')
        actions=[{'action':'input_boolean.turn_on','target':{'entity_id':[config['payload']['data']['action']['target']['entity_id']]}}]
    else:
        configs=[x for x in evidence if x['kind']=='hads_get_automation_config' and data(x).get('id')==target]
        if not configs:return fallback('Před návrhem načti skutečnou konfiguraci automatizace.')
        config=configs[-1];actions=config['payload']['data'].get('actions',[])
    if len(actions)!=1 or actions[0].get('target',{}).get('entity_id')!=[change['from']] or actions[0].get('omitted_fields'):
        return fallback('Konfigurace není jednoduchá podpořená změna jediného odkazu. Potřebuje kontrolu v editoru automatizace.')
    action=actions[0].get('action',actions[0].get('service',''))
    if action not in {'input_boolean.turn_on','light.turn_on','switch.turn_on'}:
        return fallback('Pro tuto akci není připravený ověřený funkční test opravného katalogu.')
    if not change['to'].startswith(action.split('.')[0]+'.'):return fallback('Cílová entita neodpovídá doméně volané akce; je nutná ruční kontrola.')
    missing=[x for x in evidence if x['kind']=='hads_get_entity_state' and data(x).get('entity_id')==change['from']]
    existing=[x for x in evidence if x['kind']=='hads_get_entity_state' and data(x).get('entity_id')==change['to']]
    if not missing or not existing or data(missing[-1]).get('exists') is not False or data(existing[-1]).get('state') not in {'on','off'}:
        return fallback('Nejdříve ověř chybějící původní stav a dostupnost navržené cílové entity. Samotný název entity nestačí.')
    supporting=sorted(set(cited)|{config['evidence_id'],missing[-1]['evidence_id'],existing[-1]['evidence_id']})
    document={**base,'status':'supported_managed_candidate' if managed else 'supported_lab_candidate','catalog_operation':'replace_managed_reference' if managed else 'replace_entity_reference','target':target,
        'original':{'entity_id':change['from']},'change':dict(change),'reason':redact(reason),'evidence_ids':supporting,
        'summary_cs':'Je připravený kontrolovatelný návrh jediné reference. Zamýšlený nový cíl musí potvrdit vlastník.',
        'preconditions':['fresh_full_configuration_read','exact_original_sha256','single_supported_reference',
            'owner_confirms_intended_target','private_isolated_target','unexpired_exact_plan_approval'],
        'risk':{'scope':'isolated_fixture_or_disconnected_virtual_Core_only','production_supported':False},
        'backup':{'required':'independently_read_verified_single_object_snapshot','scope':'not_full_HAOS_restore',
            'production_onedrive_policy':'unchanged_and_not_bypassed'},
        'verification':{'automation_id':target,'entity_id':change['to'],'expected_state':'on','watch_seconds':30,
            'required':'actual_trigger_and_context_linked_target_state_through_entire_watch_window'},
        'rollback':{'supported_in_lab':True,'separate_approval_required':True,'scope':'single_supported_object_only'},
        'manual_steps_cs':['V editoru automatizací otevři automatizaci '+target+'.',
            'Ověř, že zamýšlený cíl je skutečně '+change['to']+'. Pokud si nejsi jistý, nic neměň.',
            'Po vlastní kontrole lze změnit jediný odkaz z '+change['from']+' na '+change['to']+'.',
            'Spusť kontrolovaný funkční test a ověř skutečný cílový stav. Samotné uložení konfigurace nestačí.'],
        'production_limitation_cs':'HADS tuto změnu v domácnosti zatím nevykonává. Návrh není schválení a neobchází zálohové kontroly.'}
    return RepairSuggestion(canonical(document))


def prepare_reference_plan(suggestion,planner,filename,*,watch_seconds=30):
    """Trusted lab entry point; reuses the original planner and all its guards."""
    from .repair import RepairBlocked,RepairEngine
    if not isinstance(suggestion,RepairSuggestion) or not isinstance(planner,RepairEngine):raise RepairBlocked('Neplatné předání plánovači.')
    document=suggestion.document
    if document.get('status') not in {'supported_lab_candidate','supported_managed_candidate'} or document.get('production_executable') is not False or planner._operation not in {
        'fixture.replace_entity_reference','core_lab.replace_entity_reference','core_managed.replace_entity_reference'}:raise RepairBlocked('Tento návrh nebo vykonavatel není podporovaný.')
    if not isinstance(watch_seconds,(int,float)) or isinstance(watch_seconds,bool) or not 1<=watch_seconds<=3600:raise RepairBlocked('Neplatná sledovací doba.')
    if (document['status']=='supported_managed_candidate') != (planner._operation=='core_managed.replace_entity_reference'):raise RepairBlocked('Návrh a katalog se neshodují.')
    fresh=json.loads(planner._read(filename))
    if fresh.get('id')!=document['target']:raise RepairBlocked('Cíl plánovače neodpovídá konkrétnímu návrhu.')
    return planner.prepare_entity_reference(document['incident_id'],filename,document['change']['from'],document['change']['to'],
        document['evidence_ids'],document['reason'],watch_seconds=watch_seconds,target_state=document['verification']['expected_state'])


def native_enable_suggestion(proposal,case):
    target=proposal.get('target');cited=proposal.get('evidence_ids',[])
    evidence={e['evidence_id']:e for e in case['evidence']}
    valid=isinstance(target,str) and re.fullmatch(r'automation\.[a-z0-9_]+',target) and target in case['incident']['components'] and isinstance(cited,list) and bool(cited) and all(isinstance(x,str) and x in evidence for x in cited)
    state=[e for e in case['evidence'] if e['source']=='ha_core' and e['kind']=='hads_get_entity_state' and e['payload'].get('data',{}).get('entity_id')==target]
    valid=valid and bool(state) and state[-1]['payload']['data'].get('state')=='off'
    document={'schema':1,'incident_id':case['incident']['id'],'status':'supported_native_candidate' if valid else 'manual_or_test_required','production_executable':False,'target':target if valid else '','summary_cs':'Vypnutá automatizace může být kandidátem opětovné aktivace. Vlastník musí potvrdit záměr; přesný světelný katalog ověří čerstvou úplnou konfiguraci.' if valid else 'Chybí aktuální důkaz vypnuté automatizace nebo platné citace.','manual_steps_cs':['V HA zkontroluj, zda má být tato automatizace zapnutá.','Ověř jedinou světelnou akci a spouštěč; složitou konfiguraci tento katalog nemění.','Po schválení proveď skutečný trigger a potvrď reakci světla.'],'evidence_ids':cited if valid else [],'approval_required':True}
    return RepairSuggestion(canonical(document))
