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
    ATTR_UNIQUE_ID,
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

    # Database of devices
    db = Db()
    db.load()
    switches = db.get()
    orphaned = db.orphaned()

    # Load and create devices.
    _LOGGER.debug(f"entry={entry}")
    for switch, values in switches.items():
        _LOGGER.info(f"would try to add {switch}")
        _LOGGER.info(f"would try to add {values}")
        await _async_get_or_create_momentary_device_in_registry(hass, entry, switch, values)

    # Delete orphaned entries.
    for switch, values in orphaned.items():
        _LOGGER.info(f"would try to delete {switch}")
        await _async_delete_momentary_device_from_registry(hass, entry, switch, values)

    # create entity
    _LOGGER.info("trying to move to next stage")
    hass.data[DOMAIN][ATTR_SWITCHES] = switches
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SWITCH)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("unloading it all")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SWITCH])
    if unload_ok:
        hass.data[DOMAIN] = {}

    return unload_ok


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


async def _async_delete_momentary_device_from_registry(
        hass: HomeAssistant, entry: ConfigEntry, unique_id, switch
) -> None:
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, unique_id)},
    )
    if device:
        _LOGGER.debug(f"found something to delete! {device.id}")
        device_registry.async_remove_device(device.id)
    else:
        _LOGGER.debug(f"have orphaned device in meta {unique_id}")
