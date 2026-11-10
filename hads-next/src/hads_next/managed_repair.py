"""Existing executor specialized for the companion's atomic owned reference.

No native automation configuration POST is permitted. This operation changes
only the bounded mapping used by a manually installed virtual test automation.
"""
import json
from .repair import RepairEngine,RepairBlocked,canonical,digest

MISSING='input_boolean.hads_next_test_missing'
TARGET='input_boolean.hads_next_test_target'

class ManagedReferenceEngine(RepairEngine):
    _operation='core_managed.replace_entity_reference'
    _risk='low_owned_virtual_test_reference'
    _snapshot_scope='single_owned_reference_not_HAOS'
    _preconditions=('server_atomic_revision_and_value','owned_virtual_test_reference','unexpired_owner_approval','verified_reference_snapshot')
    FILENAME='hads_reference.json'

    def __init__(self,db_path,root,transport,*,owner):
        self.transport=transport
        super().__init__(db_path,root,allowed_files={self.FILENAME},owner=owner)

    @staticmethod
    def _entity(document):
        try:
            if set(document)!={'id','scope','revision','action'} or document['id']!='hads_next_reference_test' or document['scope']!='integration_owned_virtual_test_reference' or type(document['revision']) is not int or document['revision']<0:raise ValueError()
            if set(document['action'])!={'service','target'} or document['action']['service']!='input_boolean.turn_on' or set(document['action']['target'])!={'entity_id'}:raise ValueError()
            entity=document['action']['target']['entity_id']
            if entity not in {MISSING,TARGET}:raise ValueError()
            return entity
        except (KeyError,TypeError,ValueError):raise RepairBlocked('Nepodporovaný objekt: povolená je pouze vlastní virtuální testovací reference.') from None

    def _read(self,filename):
        if filename!=self.FILENAME:raise RepairBlocked('Nepovolený cíl.')
        value=self.transport({'type':'hads_reference/read'});self._entity(value)
        return canonical(value).encode()

    @classmethod
    def _change_entity(cls,document,new_entity_id):
        cls._entity(document)
        changed=json.loads(canonical(document));changed['action']['target']['entity_id']=new_entity_id;changed['revision']+=1;cls._entity(changed);return changed

    def _replace(self,filename,content):
        value=json.loads(content);target=self._entity(value)
        result=self.transport({'type':'hads_reference/cas','expected_revision':value['revision']-1,
            'expected_entity':MISSING if target==TARGET else TARGET,'entity_id':target,'operation_id':digest(content)})
        if result!=value:raise RepairBlocked('CAS nepotvrdilo přesně schválenou změnu. Žádný automatický retry.')

    def _manual_alternative(self,filename,expected_old,new_entity_id):
        return 'Pouze v oddělené testovací instalaci zkontroluj HADS companion referenci. Obecnou konfiguraci automatizací toto API nemění.'
