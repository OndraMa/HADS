from homeassistant import config_entries


class HadsRescueConfigFlow(config_entries.ConfigFlow, domain="hads_rescue"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("hads_rescue_readback")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="HADS Rescue Readback", data={})
        return self.async_show_form(step_id="user")
