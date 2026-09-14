"""Optional read-only cloud verification bridge; requires explicit installation."""
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from .verifier import verify

DOMAIN = "hads_rescue"
_LOGGER = logging.getLogger(__name__)
SCHEMA = vol.Schema({vol.Required("config_entry_id"): str,
                     vol.Required("destination_folder"): str, vol.Required("filename"): str})


async def async_setup_entry(hass, entry):
    async def handle(call):
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if not user or not user.is_admin:
                raise HomeAssistantError("HADS rescue verification requires an administrator")
        target = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if not target or target.domain != "onedrive" or target.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError("Requested OneDrive entry is not loaded")
        client = getattr(getattr(target, "runtime_data", None), "client", None)
        if client is None:
            raise HomeAssistantError("OneDrive runtime API is incompatible; no verification performed")
        try:
            return await verify(client, call.data["config_entry_id"], call.data["destination_folder"], call.data["filename"])
        except Exception as exc:
            # SDK exception text may include signed download URLs: never expose it.
            _LOGGER.warning("Rescue readback failed (%s)", type(exc).__name__)
            raise HomeAssistantError("OneDrive independent readback failed; repair must remain blocked") from None
    hass.services.async_register(DOMAIN, "verify", handle, schema=SCHEMA, supports_response=SupportsResponse.ONLY)
    return True


async def async_unload_entry(hass, entry):
    hass.services.async_remove(DOMAIN, "verify")
    return True
