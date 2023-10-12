
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PLATFORM

from .const import (
    ATTR_SWITCHES,
    ATTR_FILE_NAME,
    DB_SWITCHES_FILE,
    DOMAIN
)
from .db import Db

_LOGGER = logging.getLogger(__name__)


class MomentaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    async def async_step_user(self, user_input):
        _LOGGER.debug(f"showing shit {user_input}")
        _LOGGER.debug(f"showing shit {self.hass.data.get(DOMAIN)}")

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if self.hass.data.get(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            #
            db = Db(user_input['file_name'])
            db.load()
            return self.async_create_entry(title=DOMAIN, data={
                ATTR_FILE_NAME: user_input['file_name'],
                ATTR_SWITCHES: list(db.get().keys())
            })

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({
                vol.Required("file_name", default=DB_SWITCHES_FILE): str
            })
        )

    async def async_step_import(self, import_data):
        """Import momentary config from configuration.yaml."""

        # Set up the new database.
        db = Db()

        # Extract the momentary devices in the yaml file. The import function
        # converts it.
        for switch in import_data:
            if switch[CONF_PLATFORM] == DOMAIN:
                db.import_switch(switch)

        # Store keys in momentary config.
        return self.async_create_entry(title=DOMAIN, data={
            ATTR_FILE_NAME: DB_SWITCHES_FILE,
            ATTR_SWITCHES: list(db.get().keys())
        })
