"""
This component provides support for a momentary switch.
"""

import logging
import voluptuous as vol
from typing import Any

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_PLATFORM
from homeassistant.data_entry_flow import FlowResult

from .const import *
from .cfg import UpgradeCfg


_LOGGER = logging.getLogger(__name__)


class MomentaryConfigFlow(config_entries.ConfigFlow, domain=COMPONENT_DOMAIN):

    VERSION = 1

    async def validate_input(self, user_input):
        for group, values in self.hass.data.get(COMPONENT_DOMAIN, {}).items():
            _LOGGER.debug(f"checking {group}")
            if group == user_input[ATTR_GROUP_NAME]:
                raise GroupNameAlreadyUsed
            if values[ATTR_FILE_NAME] == user_input[ATTR_FILE_NAME]:
                raise FileNameAlreadyUsed
        return {
            "title": f"{user_input[ATTR_GROUP_NAME]} - {COMPONENT_DOMAIN}"
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        _LOGGER.debug(f"step user {user_input}")

        errors = {}
        if user_input is not None:
            try:
                info = await self.validate_input(user_input)

                return self.async_create_entry(title=info["title"], data={
                    ATTR_GROUP_NAME: user_input[ATTR_GROUP_NAME],
                    ATTR_FILE_NAME: user_input[ATTR_FILE_NAME],
                })
            except GroupNameAlreadyUsed as _e:
                errors["base"] = "group_name_used"
            except FileNameAlreadyUsed as _e:
                errors["base"] = "file_name_used"

        else:
            # Fill in some defaults.
            user_input = {
                ATTR_GROUP_NAME: DEFAULT_IMPORTED_NAME,
                ATTR_FILE_NAME: default_config_file(self.hass)
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

        # Extract the momentary devices in the yaml file. The import function
        # converts it.
        _LOGGER.info("importing YAML switches into default group")
        cfg = UpgradeCfg(self.hass, DEFAULT_IMPORTED_NAME, default_config_file(self.hass))
        for switch in import_data:
            if switch[CONF_PLATFORM] == COMPONENT_DOMAIN:
                cfg.import_switch(switch)
        await cfg.async_save()

        # Store keys in momentary config.
        return self.async_create_entry(title=f"{DEFAULT_IMPORTED_NAME} {COMPONENT_DOMAIN}", data={
            ATTR_GROUP_NAME: DEFAULT_IMPORTED_NAME,
            ATTR_FILE_NAME: default_config_file(self.hass),
            ATTR_SWITCHES: list(cfg.switch_keys)
        })


class GroupNameAlreadyUsed(exceptions.HomeAssistantError):
    """ Error indicating group name already used. """


class FileNameAlreadyUsed(exceptions.HomeAssistantError):
    """ Error indicating file name already used. """
