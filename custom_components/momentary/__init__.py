"""
This component provides support for a momentary switch.

"""

from __future__ import annotations

import json
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
import homeassistant.helpers.device_registry as dr

__version__ = '0.7.0a1'

_LOGGER = logging.getLogger(__name__)

COMPONENT_DOMAIN = 'momentary'


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an momentary component."""

    hass.data.setdefault(COMPONENT_DOMAIN, {})

    config_entry = _async_find_matching_config_entry(hass)
    if not config_entry:
        _LOGGER.debug('importing a YAML setup')
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                COMPONENT_DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config['switch']
            )
        )
        return True

    _LOGGER.debug('ignoring a YAML setup')
    return True


@callback
def _async_find_matching_config_entry(hass):
    for entry in hass.config_entries.async_entries(COMPONENT_DOMAIN):
        if entry.source == SOURCE_IMPORT:
            return entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug('async setup')

    _LOGGER.debug(f'async set up for {entry.data}')
    with open("/config/m.test", 'r') as configuration_file:
        configuration = json.load(configuration_file)

    # create devices
    switches = configuration.get('switches', {})
    for switch in entry.data.get('switches', {}):
        if switch in switches:
            _LOGGER.info(f"would try to add1 {switch}")
            _LOGGER.info(f"would try to add1 {switches[switch]}")
            await _async_get_or_create_momentary_device_in_registry(hass, entry, switch, switches[switch])

    # create entity
    _LOGGER.info("trying to more to next stage")
    hass.data[COMPONENT_DOMAIN]['switches'] = switches
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SWITCH)

    return True


async def _async_get_or_create_momentary_device_in_registry(
        hass: HomeAssistant, entry: ConfigEntry, unique_id, switch
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(COMPONENT_DOMAIN, unique_id)},
        manufacturer="twrecked",
        name=switch["name"],
        model="momentary",
        sw_version=__version__
    )

