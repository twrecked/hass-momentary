"""
This component provides support for a momentary switch.

"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_SOURCE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.device_registry as dr

from .const import (
    ATTR_SWITCHES,
    DOMAIN,
    MANUFACTURER,
    MODEL
)
from .db import Db


__version__ = '0.7.0a1'

_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an momentary component.
    """

    hass.data.setdefault(DOMAIN, {})

    # See if we have already imported the data. If we haven't then do it now.
    config_entry = _async_find_matching_config_entry(hass)
    if not config_entry:
        _LOGGER.debug('importing a YAML setup')
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={CONF_SOURCE: SOURCE_IMPORT},
                data=config[Platform.SWITCH]
            )
        )
        return True

    _LOGGER.debug('ignoring a YAML setup')
    return True


@callback
def _async_find_matching_config_entry(hass):
    """ If we have anything in config_entries for momentary we consider it
    configured and will ignore the YAML.
    """
    for entry in hass.config_entries.async_entries(DOMAIN):
        # if entry.source == SOURCE_IMPORT:
        return entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug('async setup')

    # Load and create devices.
    _LOGGER.debug(f"entry={entry}")
    switches = Db().load()
    for switch in entry.data.get(ATTR_SWITCHES, {}):
        if switch in switches:
            _LOGGER.info(f"would try to add1 {switch}")
            _LOGGER.info(f"would try to add1 {switches[switch]}")
            await _async_get_or_create_momentary_device_in_registry(hass, entry, switch, switches[switch])
        else:
            _LOGGER.info(f"failed to find {switch}")

    # create entity
    _LOGGER.info("trying to move to next stage")
    hass.data[DOMAIN][ATTR_SWITCHES] = switches
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SWITCH)

    return True


async def _async_get_or_create_momentary_device_in_registry(
        hass: HomeAssistant, entry: ConfigEntry, unique_id, switch
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        manufacturer=MANUFACTURER,
        name=switch[CONF_NAME],
        model=MODEL,
        sw_version=__version__
    )

