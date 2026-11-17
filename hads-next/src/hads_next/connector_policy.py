"""Reviewed operation semantics. Upstream readOnlyHint is never permission."""
from .tool_registry import object_schema,ENTITY,ID

READS={
 'ha_get_state':object_schema({'entity_id':ENTITY}),
 'ha_get_device':object_schema({'entity_id':ENTITY}),
 'ha_config_get_automation':object_schema({'entity_id':ENTITY}),
 'ha_get_system_health':object_schema({'include':{'type':'string','enum':['repairs','zha_network','supervisor']}},[]),
}
WRITES={
 'ha_config_set_automation':object_schema({'entity_id':ENTITY,'config':{'type':'object'},'config_hash':{'type':'string','minLength':16,'maxLength':128},
     'run_actions':{'const':False},'wait':{'const':True}}),
}
HAMSTER_READS={'hass/config/entity_registry/get','hass/get_states','hass/config/entity_registry/list','hass/config/device_registry/list','hass/repairs/list_issues','hass/system_log/list'}


def policy(provider,name):
    if provider=='ha_mcp':
        if name in READS:return 'read','allowed',READS[name],None
        if name in WRITES:return 'write','allowed',WRITES[name],'replace_automation_reference'
    if provider=='native_mcp' and name in {'GetLiveContext','homeassistant__GetLiveContext'}:return 'read','allowed',object_schema(),None
    if provider=='hamster_mcp' and name in HAMSTER_READS:return 'read','allowed',object_schema({'entity_id':ENTITY}) if name.endswith('/get') else object_schema(),None
    return 'unknown','blocked',None,None


def descriptor(name,schema,*,effect='read',policy='allowed',executor=None,contract='',risk=None,**extra):
    return {'name':name,'schema':schema,'effect':effect,'policy':policy,'executor':executor,
            'risk':risk or ('none_local_read' if effect=='read' else 'configuration_change'),
            'permissions':['HA admin'] if effect=='write' else ['provider diagnostic access'],
            'preconditions':['current_catalog','validated_arguments','incident_scope']+(['exact_immutable_owner_approval','current_original','verified_backup'] if effect=='write' else []),
            'verification':'predefined functional observation after change' if effect=='write' else 'valid actual response with source time and provenance',
            'rollback':'separately approved exact inverse with current-state guard' if executor else None,
            'contract':contract,**extra}
