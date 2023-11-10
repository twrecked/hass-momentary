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

from .const import *
from .cfg import BlendedCfg


__version__ = '0.7.0a3'

_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an momentary component.
    """
    hass.data.setdefault(COMPONENT_DOMAIN, {})

    # See if we have already imported the data. If we haven't then do it now.
    config_entry = _async_find_matching_config_entry(hass)
    if not config_entry:
        _LOGGER.debug('importing a YAML setup')
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                COMPONENT_DOMAIN,
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
    for entry in hass.config_entries.async_entries(COMPONENT_DOMAIN):
        return entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug(f'async setup {entry.data}')

    # Database of devices
    group_name = entry.data[ATTR_GROUP_NAME]
    file_name = entry.data[ATTR_FILE_NAME]
    cfg = BlendedCfg(group_name, file_name)
    cfg.load()

    # Load and create devices.
    for switch, values in cfg.switches.items():
        _LOGGER.debug(f"would try to add {switch}")
        # _LOGGER.debug(f"would try to add {values}")
        await _async_get_or_create_momentary_device_in_registry(hass, entry, switch, values)

    # Delete orphaned entries.
    for switch, values in cfg.orphaned_switches.items():
        _LOGGER.debug(f"would try to delete {switch}")
        await _async_delete_momentary_device_from_registry(hass, entry, switch, values)

    # Update hass data and queue entry creation.
    hass.data[COMPONENT_DOMAIN].update({
        group_name: {
            ATTR_SWITCHES: cfg.switches,
            ATTR_FILE_NAME: file_name
        }
    })
    _LOGGER.debug(f"update hass data {hass.data[COMPONENT_DOMAIN]}")
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SWITCH)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(f"unloading it {entry.data[ATTR_GROUP_NAME]}")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SWITCH])
    if unload_ok:
        hass.data[COMPONENT_DOMAIN].pop(entry.data[ATTR_GROUP_NAME])
        BlendedCfg.delete_group(entry.data[ATTR_GROUP_NAME])
    _LOGGER.debug(f"after hass={hass.data[COMPONENT_DOMAIN]}")

    return unload_ok


async def _async_get_or_create_momentary_device_in_registry(
        hass: HomeAssistant, entry: ConfigEntry, unique_id, switch
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(COMPONENT_DOMAIN, unique_id)},
        manufacturer=COMPONENT_MANUFACTURER,
        name=switch[CONF_NAME],
        model=COMPONENT_MODEL,
        sw_version=__version__
    )


async def _async_delete_momentary_device_from_registry(
        hass: HomeAssistant, _entry: ConfigEntry, unique_id, _switch
) -> None:
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(COMPONENT_DOMAIN, unique_id)},
    )
    if device:
        _LOGGER.debug(f"found something to delete! {device.id}")
        device_registry.async_remove_device(device.id)
    else:
        _LOGGER.info(f"have orphaned device in meta {unique_id}")
