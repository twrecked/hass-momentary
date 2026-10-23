"""Config flow for the momentary integration.

This module implements the config flow and import helpers used to create
config entries for the integration.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import callback

from .cfg import UpgradeCfg
from .const import (
    ATTR_FILE_NAME,
    ATTR_GROUP_NAME,
    ATTR_SWITCHES,
    COMPONENT_DOMAIN,
    CONF_EDITOR_URL,
    DEFAULT_EDITOR_URL,
    DEFAULT_IMPORTED_NAME,
    default_config_file,
)

_LOGGER = logging.getLogger(__name__)


class MomentaryConfigFlow(config_entries.ConfigFlow, domain=COMPONENT_DOMAIN):
    """Handle the config flow for the momentary integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MomentaryOptionsFlowHandler()

    async def validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Validate user input for creating a new config entry.

        Raises an exception if the group name or file name are already used.
        """
        for entry in self.hass.config_entries.async_entries(COMPONENT_DOMAIN):
            if entry.data.get(ATTR_GROUP_NAME) == user_input.get(ATTR_GROUP_NAME):
                raise GroupNameAlreadyUsed
            if entry.data.get(ATTR_FILE_NAME) == user_input.get(ATTR_FILE_NAME):
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
            except GroupNameAlreadyUsed:
                errors["base"] = "group_name_used"
            except FileNameAlreadyUsed:
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

    async def async_step_import(self, import_data: list[dict[str, Any]]) -> ConfigFlowResult:
        """Import momentary config from configuration.yaml."""
        _LOGGER.info("importing YAML switches into default group")
        cfg = UpgradeCfg(self.hass, DEFAULT_IMPORTED_NAME, default_config_file(self.hass))
        for switch in import_data:
            if switch.get(CONF_PLATFORM) == COMPONENT_DOMAIN:
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


class MomentaryOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Momentary integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options step for opening the visual editor."""
        entry = self.config_entry
        editor_url = entry.options.get(CONF_EDITOR_URL, DEFAULT_EDITOR_URL)

        if user_input is not None:
            new_editor_url = user_input.get(CONF_EDITOR_URL, editor_url)
            return self.async_create_entry(
                title="",
                data={CONF_EDITOR_URL: new_editor_url},
            )

        file_name = entry.data.get(ATTR_FILE_NAME, default_config_file(self.hass))
        group_name = entry.data.get(ATTR_GROUP_NAME, "momentary")

        yaml_content = ""

        def _read() -> str:
            path = Path(file_name)
            if path.is_file():
                return path.read_text(encoding="utf-8")
            return ""

        try:
            yaml_content = await self.hass.async_add_executor_job(_read)
        except OSError as err:
            _LOGGER.debug("Could not read %s: %s", file_name, err)

        webhook_id = f"momentary_{entry.entry_id}"
        token = (
            self.hass.data.get(f"{COMPONENT_DOMAIN}_webhooks", {})
            .get(entry.entry_id, {})
            .get("webhook_token", "")
        )

        try:
            webhook_url = webhook.async_generate_url(
                self.hass, webhook_id, allow_internal=True, allow_external=True
            )
        except (exceptions.HomeAssistantError, ValueError, RuntimeError):
            webhook_url = f"/api/webhook/{webhook_id}"

        cb_param = (
            f"{webhook_url}?token={token}" if "?" not in webhook_url else f"{webhook_url}&token={token}"
        )

        encoded_yaml = base64.b64encode(yaml_content.encode()).decode("ascii")
        builder_url = (
            f"{editor_url}/?cb={quote(cb_param, safe='')}"
            f"&token={quote(token)}"
            f"&name={quote(group_name)}"
            f"#data={encoded_yaml}"
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EDITOR_URL, default=editor_url): str,
                }
            ),
            description_placeholders={
                "builder_url": builder_url,
                "group_name": group_name,
                "file_name": file_name,
            },
        )


class GroupNameAlreadyUsed(exceptions.HomeAssistantError):
    """Error indicating group name already used."""


class FileNameAlreadyUsed(exceptions.HomeAssistantError):
    """Error indicating file name already used."""
