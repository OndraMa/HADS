from homeassistant.components.light import LightEntity,ColorMode

async def async_setup_platform(hass,config,async_add_entities,discovery_info=None):
    async_add_entities([EntryLamp()])

class EntryLamp(LightEntity):
    _attr_name='Entry lamp'
    _attr_unique_id='native-lighting-acceptance'
    _attr_is_on=False
    _attr_supported_color_modes={ColorMode.ONOFF}
    _attr_color_mode=ColorMode.ONOFF
    _attr_should_poll=False
    async def async_turn_on(self,**kwargs):self._attr_is_on=True;self.async_write_ha_state()
    async def async_turn_off(self,**kwargs):self._attr_is_on=False;self.async_write_ha_state()
