"""Config flow for the momentary integration.

This module implements the config flow and import helpers used to create
config entries for the integration.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import result_as_boolean

from .const import (
    CONF_CANCELLABLE,
    CONF_CLEAR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_TOGGLE_FOR,
    CONF_YAML_PRESENT,
    CONF_YAML_SWITCH,
    DEFAULT_CANCELLABLE,
    DEFAULT_CLEAR_DEVICE_ID,
    DEFAULT_MODE_STR,
    DEFAULT_TOGGLE_FOR,
    DOMAIN,
)
from .helpers import timdelta_to_duration

_LOGGER = logging.getLogger(__name__)


def _build_user_input_schema(
    user_input: dict[str, Any] | None,
    fallback: dict[str, Any] | None = None,
    options: bool = False,
) -> vol.Schema:
    """Build a voluptuous schema for the config flow user input.

    Parameters
    ----------
    user_input : dict[str, Any] | None
        The partial user input to use as defaults when rendering the form.
    fallback : dict[str, Any] | None
        Fallback values used when keys are missing from user_input.
    options : bool, optional
        If True, include options-specific fields (such as clearing the device
        id) in the returned schema; defaults to False.

    Returns
    -------
    vol.Schema
        A voluptuous Schema describing the expected configuration fields
        for the momentary integration config flow.

    """
    if user_input is None:
        user_input = {}
    if fallback is None:
        fallback = {}

    mode = user_input.get(CONF_MODE, fallback.get(CONF_MODE, DEFAULT_MODE_STR))
    if mode is None:
        mode = DEFAULT_MODE_STR
    elif isinstance(mode, bool):
        mode = "on" if mode else "off"
    elif isinstance(mode, str):
        mode = mode.lower()
        if mode not in ("on", "off"):
            mode = DEFAULT_MODE_STR
    else:
        mode = DEFAULT_MODE_STR

    schema = vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=user_input.get(CONF_NAME, fallback.get(CONF_NAME, ""))
            ): cv.string,
            vol.Optional(
                CONF_MODE,
                default=mode,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["on", "off"],
                    translation_key=CONF_MODE,
                    multiple=False,
                    custom_value=False,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(
                CONF_TOGGLE_FOR,
                default=user_input.get(
                    CONF_TOGGLE_FOR, fallback.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR)
                ),
            ): selector.DurationSelector(
                selector.DurationSelectorConfig(
                    enable_day=False, enable_millisecond=True, allow_negative=False
                )
            ),
            vol.Optional(
                CONF_CANCELLABLE,
                default=user_input.get(
                    CONF_CANCELLABLE, fallback.get(CONF_CANCELLABLE, DEFAULT_CANCELLABLE)
                ),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            vol.Optional(
                CONF_DEVICE_ID,
                default=user_input.get(CONF_DEVICE_ID, fallback.get(CONF_DEVICE_ID, "")),
            ): selector.DeviceSelector(selector.DeviceSelectorConfig()),
        }
    )
    if options:
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_CLEAR_DEVICE_ID, default=DEFAULT_CLEAR_DEVICE_ID
                ): selector.BooleanSelector(selector.BooleanSelectorConfig())
            }
        )
    return schema


class MomentaryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow handler for the momentary integration.

    This class implements the configuration flow used by Home Assistant to set
    up the momentary integration via the UI and to import configurations from
    YAML. It presents the user form, validates and normalizes input, and
    creates a config entry for the integration.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None, yaml_switch: bool = False
    ) -> ConfigFlowResult:
        """Handle the user configuration step for the momentary integration.

        This step presents the UI form, validates and normalizes submitted values,
        and creates a config entry for the integration when the input is valid.

        Parameters
        ----------
        user_input : dict[str, Any] | None
            Partial user input provided by the UI, or None when first showing the form.
        yaml_switch : bool
            True when the configuration was provided via YAML import.

        Returns
        -------
        ConfigFlowResult
            The result of the config flow step: show form, create entry, or abort.

        """
        errors: dict[str, Any] = {}
        if user_input is not None:
            user_input[CONF_YAML_SWITCH] = yaml_switch
            if yaml_switch:
                user_input[CONF_YAML_PRESENT] = True
            if user_input.get(CONF_DEVICE_ID) == "":
                user_input.pop(CONF_DEVICE_ID, None)
            # _LOGGER.debug("[async_step_user] user_input: %s", user_input)

            if not errors or yaml_switch:
                mode_bool = result_as_boolean(user_input.get(CONF_MODE))
                user_input[CONF_MODE] = mode_bool
                user_input[CONF_TOGGLE_FOR] = timdelta_to_duration(
                    value=user_input.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR),
                    default=DEFAULT_TOGGLE_FOR,
                )
                # _LOGGER.debug("[async_step_user] Final user_input: %s", user_input)
                return self.async_create_entry(title=user_input.get(CONF_NAME, ""), data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_input_schema(user_input=user_input),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import configuration from YAML and forward it to the user step.

        This method is called when configuration is provided via YAML; it logs
        the imported configuration and delegates to async_step_user with
        yaml_switch=True so that the import is handled the same way as a
        user-provided configuration.

        Parameters
        ----------
        import_config : dict[str, Any] | None
            The configuration dictionary imported from YAML.

        Returns
        -------
        ConfigFlowResult
            The result of the delegated async_step_user call.

        """
        # _LOGGER.debug("[async_step_import] import_config: %s", import_config)
        return await self.async_step_user(user_input=import_config, yaml_switch=True)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MomentaryOptionsFlowHandler:
        """Return an options flow handler for the provided config entry.

        Parameters
        ----------
        config_entry : ConfigEntry
            The config entry for which to create the options flow handler.

        Returns
        -------
        MomentaryOptionsFlowHandler
            A new options flow handler instance tied to the given config entry.

        """
        return MomentaryOptionsFlowHandler()


class MomentaryOptionsFlowHandler(OptionsFlow):
    """Options flow handler for the momentary integration.

    This handler provides the options UI for an existing config entry created
    by the integration (it aborts for YAML-defined switches). It exposes the
    init step to present and validate option changes.
    """

    def __init__(self) -> None:
        """Initialize the options flow handler."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial options step for the config entry.

        Presents the options form for an existing config entry (aborting if the
        switch was created via YAML) and validates/normalizes submitted values.

        Parameters
        ----------
        user_input : dict[str, Any] | None
            Partial user input provided by the UI, or None when first showing the form.

        Returns
        -------
        ConfigFlowResult
            The result of the options flow step (form, create entry, or abort).

        """

        if self.config_entry.data.get(CONF_YAML_SWITCH):
            _LOGGER.debug("[YAML] No Options for YAML Created Momentary Switches")
            return self.async_abort(reason="yaml_switch")

        errors: dict[str, Any] = {}
        config = dict(self.config_entry.data)
        if user_input is not None:
            # _LOGGER.debug("[async_step_init] user_input: %s", user_input)
            config.update(user_input)
            if (
                config.get(CONF_CLEAR_DEVICE_ID, DEFAULT_CLEAR_DEVICE_ID)
                or config.get(CONF_DEVICE_ID) == ""
            ):
                config.pop(CONF_DEVICE_ID, None)
            config.pop(CONF_CLEAR_DEVICE_ID, None)

            if not errors:
                mode_bool = result_as_boolean(config.get(CONF_MODE))
                config[CONF_MODE] = mode_bool
                config[CONF_TOGGLE_FOR] = timdelta_to_duration(
                    value=config.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR),
                    default=DEFAULT_TOGGLE_FOR,
                )
                # _LOGGER.debug("[async_step_init] Final user_input: %s", config)

                self.hass.config_entries.async_update_entry(entry=self.config_entry, data=config)
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(data=config)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_user_input_schema(
                user_input=user_input, fallback=config, options=True
            ),
            errors=errors,
        )
