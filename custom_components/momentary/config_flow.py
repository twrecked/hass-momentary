
import logging
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_PLATFORM

from .const import (
    ATTR_FILE_NAME,
    ATTR_GROUP_NAME,
    ATTR_SWITCHES,
    DB_DEFAULT_SWITCHES_FILE,
    DEFAULT_IMPORTED_NAME,
    DOMAIN
)
from .db import Db


_LOGGER = logging.getLogger(__name__)


class MomentaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def validate_input(self, user_input):
        for group, values in self.hass.data.get(DOMAIN, {}).items():
            _LOGGER.debug(f"checking {group}")
            if group == user_input[ATTR_GROUP_NAME]:
                raise GroupNameAlreadyUsed
            if values[ATTR_FILE_NAME] == user_input[ATTR_FILE_NAME]:
                raise FileNameAlreadyUsed
        return {
            "title": f"{user_input[ATTR_GROUP_NAME]} - {DOMAIN}"
        }

    async def async_step_user(self, user_input):
        _LOGGER.debug(f"step user {user_input}")

        errors = {}
        if user_input is not None:
            try:
                info = await self.validate_input(user_input)

                db = Db(user_input[ATTR_GROUP_NAME], user_input[ATTR_FILE_NAME])
                db.load()
                return self.async_create_entry(title=info["title"], data={
                    ATTR_GROUP_NAME: user_input[ATTR_GROUP_NAME],
                    ATTR_FILE_NAME: user_input[ATTR_FILE_NAME],
                    ATTR_SWITCHES: list(db.switches.keys())
                })
            except GroupNameAlreadyUsed as e:
                errors["base"] = "group_name_used"
            except FileNameAlreadyUsed as e:
                errors["base"] = "file_name_used"

        else:
            # Fill in some defaults.
            user_input = {
                ATTR_GROUP_NAME: DEFAULT_IMPORTED_NAME,
                ATTR_FILE_NAME: DB_DEFAULT_SWITCHES_FILE
            }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({
                vol.Required(ATTR_GROUP_NAME, default=user_input[ATTR_GROUP_NAME]): str,
                vol.Required(ATTR_FILE_NAME, default=user_input[ATTR_FILE_NAME]): str
            }),
            errors=errors
        )

    async def async_step_import(self, import_data):
        """Import momentary config from configuration.yaml."""

        # Set up the new database.
        _LOGGER.info("importing YAML switches into default group")
        db = Db(DEFAULT_IMPORTED_NAME, DB_DEFAULT_SWITCHES_FILE)

        # Extract the momentary devices in the yaml file. The import function
        # converts it.
        for switch in import_data:
            if switch[CONF_PLATFORM] == DOMAIN:
                db.import_switch(switch)

        # Store keys in momentary config.
        return self.async_create_entry(title=f"{DEFAULT_IMPORTED_NAME} {DOMAIN}", data={
            ATTR_GROUP_NAME: DEFAULT_IMPORTED_NAME,
            ATTR_FILE_NAME: DB_DEFAULT_SWITCHES_FILE,
            ATTR_SWITCHES: list(db.switches.keys())
        })


class GroupNameAlreadyUsed(exceptions.HomeAssistantError):
    """ Error indicating group name already used. """


class FileNameAlreadyUsed(exceptions.HomeAssistantError):
    """ Error indicating file name already used. """
