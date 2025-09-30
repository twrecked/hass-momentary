"""Helpers for the Momentary integration."""

from __future__ import annotations

import copy
from datetime import timedelta
import logging
from typing import Any, cast

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import result_as_boolean
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (
    CONF_CANCELLABLE,
    CONF_ID_TOKEN,
    CONF_MODE,
    CONF_NAME,
    CONF_TOGGLE_FOR,
    CONF_YAML_PRESENT,
    CONF_YAML_SWITCH,
    DEFAULT_CANCELLABLE,
    DEFAULT_MODE,
    DEFAULT_TOGGLE_FOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def duration_to_timedelta(value: Any, default: timedelta) -> timedelta:
    """Convert a duration-like value into a timedelta.

    This helper accepts None, a float/int (seconds), or any value accepted by
    homeassistant.helpers.config_validation.time_period and returns a
    datetime.timedelta instance. If value is None the provided default is
    returned unchanged.

    Parameters
    ----------
    value : Any
        The value to convert. May be None, a float (interpreted as seconds),
        or a value accepted by cv.time_period.
    default : timedelta
        The default timedelta to return when value is None.

    Returns
    -------
    timedelta
        The resulting timedelta.

    """
    if value is None:
        return default
    if isinstance(value, timedelta):
        return value
    if isinstance(value, int | float):
        return timedelta(seconds=value)
    return cast("timedelta", cv.time_period(value))


async def async_process_yaml(hass: HomeAssistant, config: ConfigType) -> bool:
    """Process YAML configuration for the momentary integration.

    This function reads the YAML configuration for the integration and creates
    or updates config entries in Home Assistant as needed.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    config : ConfigType
        The YAML configuration mapping for this integration.

    Returns
    -------
    bool
        True when processing completes successfully.

    """
    # _LOGGER.debug("[async_process_yaml] config: %s", config)

    # Start with any switches declared under the integration domain (legacy style):
    # momentary:
    switches: dict[str, Any] = {}
    domain_cfg = config.get(DOMAIN)
    if isinstance(domain_cfg, dict):
        # make a deep copy to avoid mutating the original config
        switches.update(copy.deepcopy(domain_cfg))

    # Also support the platform-style configuration under the switch domain:
    # switch:
    #   - platform: momentary
    #     name: Example
    #     toggle_for: 5
    platform_switches = config.get("switch", []) or []
    for sw in platform_switches:
        try:
            if sw.get("platform") == DOMAIN:
                # Use the slugified name as the variable key so the rest of the
                # code (which expects a mapping of id_token -> fields) continues
                # to work. Copy the switch dict and remove platform to avoid
                # storing HA-specific keys in our entry data.
                name = sw.get(CONF_NAME) or sw.get("name")
                token = slugify(name) if name else None
                if token:
                    sw_copy = copy.deepcopy(sw)
                    sw_copy.pop("platform", None)
                    # ensure name key exists under our CONF_NAME constant
                    if CONF_NAME not in sw_copy and name:
                        sw_copy[CONF_NAME] = name
                    # platform entries should not overwrite explicit domain YAML
                    if token not in switches:
                        switches[token] = sw_copy
        except Exception:  # pragma: no cover - defensive, should not happen
            _LOGGER.exception("Error processing switch entry: %s", sw)

    # _LOGGER.debug("[YAML] switches: %s", switches)
    seen_tokens: set[str] = set()

    for token, switch_fields in switches.items():
        if token is None:
            continue

        # _LOGGER.debug("[YAML] id_token: %s", token)
        # _LOGGER.debug("[YAML] switch_fields: %s", switch_fields)

        # Remove keys with None values while preserving the original dict
        # object so any external references remain valid.
        if isinstance(switch_fields, dict):
            cleaned = {k: v for k, v in switch_fields.items() if v is not None}
            switch_fields.clear()
            switch_fields.update(cleaned)

        if CONF_MODE in switch_fields:
            switch_fields[CONF_MODE] = result_as_boolean(switch_fields[CONF_MODE])

        if token not in {
            entry.data.get(CONF_ID_TOKEN) for entry in hass.config_entries.async_entries(DOMAIN)
        }:
            _LOGGER.warning("[YAML] Creating New Momentary Switch: %s", token)
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_ID_TOKEN: token,
                        CONF_NAME: switch_fields.get(CONF_NAME),
                        CONF_MODE: switch_fields.get(CONF_MODE, DEFAULT_MODE),
                        CONF_TOGGLE_FOR: switch_fields.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR),
                        CONF_CANCELLABLE: switch_fields.get(CONF_CANCELLABLE, DEFAULT_CANCELLABLE),
                    },
                )
            )
            seen_tokens.add(token)
        else:
            entry = None
            for ent in hass.config_entries.async_entries(DOMAIN):
                if token == ent.data.get(CONF_ID_TOKEN):
                    entry = ent
                    break

            if entry:
                _LOGGER.info("[YAML] Updating Existing Momentary Switch: %s", token)
                # _LOGGER.debug("[YAML] entry before: %s", entry.as_dict())

                for m in entry.data:
                    switch_fields.setdefault(m, entry.data[m])
                switch_fields[CONF_YAML_PRESENT] = True
                _LOGGER.debug("[YAML] Updated switch_fields: %s", switch_fields)
                hass.config_entries.async_update_entry(entry, data=switch_fields, options={})
                seen_tokens.add(token)

                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

            else:
                _LOGGER.error("[YAML] Update Error. Could not find entry_id for: %s", token)

    # Clean up YAML entries that are no longer in the configuration
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_YAML_SWITCH) and entry.data.get(CONF_ID_TOKEN) not in seen_tokens:
            _LOGGER.warning(
                "[YAML] Marking switch as removed from YAML: %s",
                entry.data.get(CONF_ID_TOKEN),
            )
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_YAML_PRESENT: False}, options={}
            )
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    return True
