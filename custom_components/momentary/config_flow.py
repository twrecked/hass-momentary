"""Config flow for the momentary integration.

This module implements the config flow and import helpers used to create
config entries for the integration.
"""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PLATFORM

from .cfg import UpgradeCfg
from .const import (
    ATTR_FILE_NAME,
    ATTR_GROUP_NAME,
    ATTR_SWITCHES,
    COMPONENT_DOMAIN,
    DEFAULT_IMPORTED_NAME,
    default_config_file,
)

_LOGGER = logging.getLogger(__name__)


class MomentaryConfigFlow(config_entries.ConfigFlow, domain=COMPONENT_DOMAIN):
    """Handle the config flow for the momentary integration."""

    VERSION = 1

    async def validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Validate user input for creating a new config entry.

        Raises an exception if the group name or file name are already used.
        """
        for group, values in self.hass.data.get(COMPONENT_DOMAIN, {}).items():
            _LOGGER.debug("checking %s", group)
            if group == user_input[ATTR_GROUP_NAME]:
                raise GroupNameAlreadyUsed
            if values[ATTR_FILE_NAME] == user_input[ATTR_FILE_NAME]:
                raise FileNameAlreadyUsed
        return {"title": f"{user_input[ATTR_GROUP_NAME]} - {COMPONENT_DOMAIN}"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step of the config flow where the user provides input."""
        _LOGGER.debug("step user %s", user_input)

        errors = {}
        if user_input is not None:
            try:
                info = await self.validate_input(user_input)

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        ATTR_GROUP_NAME: user_input[ATTR_GROUP_NAME],
                        ATTR_FILE_NAME: user_input[ATTR_FILE_NAME],
                    },
                )
            except GroupNameAlreadyUsed as _e:
                errors["base"] = "group_name_used"
            except FileNameAlreadyUsed as _e:
                errors["base"] = "file_name_used"

        else:
            # Fill in some defaults.
            user_input = {
                ATTR_GROUP_NAME: DEFAULT_IMPORTED_NAME,
                ATTR_FILE_NAME: default_config_file(self.hass),
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_GROUP_NAME, default=user_input[ATTR_GROUP_NAME]): str,
                    vol.Required(ATTR_FILE_NAME, default=user_input[ATTR_FILE_NAME]): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: list) -> ConfigFlowResult:
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
        return self.async_create_entry(
            title=f"{DEFAULT_IMPORTED_NAME} {COMPONENT_DOMAIN}",
            data={
                ATTR_GROUP_NAME: DEFAULT_IMPORTED_NAME,
                ATTR_FILE_NAME: default_config_file(self.hass),
                ATTR_SWITCHES: list(cfg.switch_keys),
            },
        )


class GroupNameAlreadyUsed(exceptions.HomeAssistantError):
    """Error indicating group name already used."""


class FileNameAlreadyUsed(exceptions.HomeAssistantError):
    """Error indicating file name already used."""
