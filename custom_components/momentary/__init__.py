"""
This component provides support for a momentary switch.

"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_SOURCE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.device_registry as dr

from .const import (
    ATTR_FILE_NAME,
    ATTR_GROUP_NAME,
    ATTR_SWITCHES,
    ATTR_UNIQUE_ID,
    CONF_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL
)
from .db import Db


__version__ = '0.7.0a2'

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
    _LOGGER.debug(f'async setup {entry.data}')

    # Database of devices
    group_name = entry.data[ATTR_GROUP_NAME]
    file_name = entry.data[ATTR_FILE_NAME]
    db = Db(group_name, file_name)
    db.load()

    # Load and create devices.
    for switch, values in db.switches.items():
        _LOGGER.debug(f"would try to add {switch}")
        # _LOGGER.debug(f"would try to add {values}")
        await _async_get_or_create_momentary_device_in_registry(hass, entry, switch, values)

    # Delete orphaned entries.
    for switch, values in db.orphaned_switches.items():
        _LOGGER.debug(f"would try to delete {switch}")
        await _async_delete_momentary_device_from_registry(hass, entry, switch, values)

    # Update hass data and queue entry creation.
    hass.data[DOMAIN].update({
        group_name: {
            ATTR_SWITCHES: db.switches,
            ATTR_FILE_NAME: file_name
        }
    })
    _LOGGER.debug(f"update hass data {hass.data[DOMAIN]}")
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SWITCH)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(f"unloading it {entry.data[ATTR_GROUP_NAME]}")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SWITCH])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.data[ATTR_GROUP_NAME])
        Db.delete_group(entry.data[ATTR_GROUP_NAME])
    _LOGGER.debug(f"after hass={hass.data[DOMAIN]}")

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
        _LOGGER.info(f"have orphaned device in meta {unique_id}")
