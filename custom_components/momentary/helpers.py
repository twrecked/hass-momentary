"""Helpers for the Momentary integration."""

from __future__ import annotations

import copy
from datetime import timedelta
import logging
from typing import Any, cast

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.template import result_as_boolean
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (
    CONF_CANCELLABLE,
    CONF_MODE,
    CONF_NAME,
    CONF_TOGGLE_FOR,
    CONF_UNIQUE_ID,
    CONF_YAML_PRESENT,
    CONF_YAML_SWITCH,
    DEFAULT_CANCELLABLE,
    DEFAULT_MODE,
    DEFAULT_TOGGLE_FOR,
    DOMAIN,
    MS_PER_DAY,
    MS_PER_HOUR,
    MS_PER_MINUTE,
    MS_PER_SECOND,
)

_LOGGER = logging.getLogger(__name__)


def timdelta_to_duration(
    value: timedelta | float | str | dict[str, Any] | None, default: dict[str, Any]
) -> dict[str, Any]:
    """Convert various duration-like inputs into a Home Assistant duration dict.

    This function accepts a datetime.timedelta, a numeric value (seconds),
    a duration string (parseable by homeassistant.helpers.config_validation.time_period
    or in HH:MM:SS(.micro) format), or an already-formed dict of time parts and
    returns a dict containing only the non-zero duration fields suitable for
    Home Assistant (days, hours, minutes, seconds, milliseconds). If the input
    represents a zero duration, {"seconds": 0} is returned.

    Parameters
    ----------
    value : timedelta | float | str | dict[str, Any] | None
        The input duration to convert.
    default : dict[str, Any]
        A default duration mapping to return when the input is invalid, unsupported,
        or when the function needs to fall back (for example {"seconds": 0}).

    Returns
    -------
    dict[str, Any]
        Mapping of non-zero time parts, or {"seconds": 0} for a zero duration.

    Raises
    ------
    TypeError
        If the provided value type is not supported.
    ValueError
        If a duration string has an invalid format.

    """
    if value is None:
        return default

    if isinstance(value, dict):
        # Assume it's already in the correct format
        filtered = {k: v for k, v in value.items() if v != 0}
        return filtered or {"seconds": 0}

    if isinstance(value, timedelta):
        total_seconds = value.total_seconds()

    elif isinstance(value, int | float):
        total_seconds = float(value)

    elif isinstance(value, str):
        # Use HA's built-in parser if possible
        try:
            td = cv.time_period(value)
            total_seconds = td.total_seconds()
        except (TypeError, AttributeError, ValueError, KeyError):
            # Fallback parsing for fractional seconds in HH:MM:SS.ssssss format
            fparts = [float(p) for p in value.split(":")]
            if len(fparts) == 3:  # HH:MM:SS(.micro)
                hours, minutes, seconds = fparts
            elif len(fparts) == 2:  # HH:MM
                hours, minutes = fparts
                seconds = 0
            elif len(fparts) == 1:  # SS
                hours = 0
                minutes = 0
                seconds = fparts[0]
            else:
                _LOGGER.warning("Invalid duration string: %s", value)
                return default
            total_seconds = hours * 3600 + minutes * 60 + seconds

    else:
        _LOGGER.warning("Unsupported type for duration: %s", type(value))
        return default

    td = timedelta(seconds=total_seconds)
    total_ms = int(round(td.total_seconds() * 1000))

    days, rem_ms = divmod(total_ms, MS_PER_DAY)
    hours, rem_ms = divmod(rem_ms, MS_PER_HOUR)
    minutes, rem_ms = divmod(rem_ms, MS_PER_MINUTE)
    seconds, milliseconds = divmod(rem_ms, MS_PER_SECOND)

    parts: dict[str, Any] = {
        "days": int(days),
        "hours": int(hours),
        "minutes": int(minutes),
        "seconds": int(seconds),
        "milliseconds": int(milliseconds),
    }
    filtered = {k: v for k, v in parts.items() if v != 0}

    return filtered or {"seconds": 0}


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

    switches: dict[str, Any] = {}

    # Support the platform-style configuration under the switch domain:
    # switch:
    #   - platform: momentary
    #     name: Example
    #     toggle_for: 5
    platform_switches = config.get("switch", []) or []
    for sw in platform_switches:
        if sw.get("platform") == DOMAIN:
            name = sw.get(CONF_NAME)
            unique_id = sw.get(CONF_UNIQUE_ID, f"momentary_{slugify(name)}" if name else None)
            if unique_id:
                sw_copy = copy.deepcopy(sw)
                sw_copy.pop("platform", None)
                if unique_id not in switches:
                    switches[unique_id] = sw_copy

    # _LOGGER.debug("[YAML] switches: %s", switches)
    seen_unique_ids: set[str] = set()

    for unique_id, switch_fields in switches.items():
        if unique_id is None:
            continue

        # _LOGGER.debug("[YAML] unique_id: %s", unique_id)
        # _LOGGER.debug("[YAML] switch_fields: %s", switch_fields)

        # Remove keys with None values while preserving the original dict
        # object so any external references remain valid.
        if isinstance(switch_fields, dict):
            cleaned = {k: v for k, v in switch_fields.items() if v is not None}
            switch_fields.clear()
            switch_fields.update(cleaned)

        if CONF_MODE in switch_fields:
            switch_fields[CONF_MODE] = result_as_boolean(switch_fields[CONF_MODE])

        if unique_id not in {
            entry.data.get(CONF_UNIQUE_ID) for entry in hass.config_entries.async_entries(DOMAIN)
        }:
            _LOGGER.warning(
                "[YAML] Creating New Momentary Switch: %s", switch_fields.get(CONF_NAME)
            )
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_NAME: switch_fields.get(CONF_NAME),
                        CONF_UNIQUE_ID: unique_id,
                        CONF_MODE: switch_fields.get(CONF_MODE, DEFAULT_MODE),
                        CONF_TOGGLE_FOR: timdelta_to_duration(
                            value=switch_fields.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR),
                            default=DEFAULT_TOGGLE_FOR,
                        ),
                        CONF_CANCELLABLE: switch_fields.get(CONF_CANCELLABLE, DEFAULT_CANCELLABLE),
                    },
                )
            )
            seen_unique_ids.add(unique_id)
        else:
            entry = None
            for ent in hass.config_entries.async_entries(DOMAIN):
                if unique_id == ent.data.get(CONF_UNIQUE_ID):
                    entry = ent
                    break

            if entry:
                _LOGGER.info(
                    "[YAML] Updating Existing Momentary Switch: %s", switch_fields.get(CONF_NAME)
                )
                # _LOGGER.debug("[YAML] entry before: %s", entry.as_dict())

                for m in entry.data:
                    switch_fields.setdefault(m, entry.data[m])
                switch_fields[CONF_YAML_PRESENT] = True
                switch_fields[CONF_TOGGLE_FOR] = timdelta_to_duration(
                    value=switch_fields.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR),
                    default=DEFAULT_TOGGLE_FOR,
                )
                switch_fields[CONF_UNIQUE_ID] = unique_id
                _LOGGER.debug("[YAML] Updated switch_fields: %s", switch_fields)
                hass.config_entries.async_update_entry(entry, data=switch_fields, options={})
                seen_unique_ids.add(unique_id)

                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

            else:
                _LOGGER.error(
                    "[YAML] Update Error. Could not find entry_id for: %s",
                    switch_fields.get(CONF_NAME),
                )

    # Clean up YAML entries that are no longer in the configuration
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_YAML_SWITCH)
            and entry.data.get(CONF_UNIQUE_ID) not in seen_unique_ids
        ):
            _LOGGER.warning(
                "[YAML] Marking switch as removed from YAML: %s",
                entry.data.get(CONF_NAME),
            )
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_YAML_PRESENT: False}, options={}
            )
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    return True
