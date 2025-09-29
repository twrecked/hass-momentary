"""Provide the momentary switch integration for Home Assistant.

This module handles setup of the integration and config entry lifecycle.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_SOURCE, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .cfg import BlendedCfg
from .const import (
    ATTR_DEVICES,
    ATTR_FILE_NAME,
    ATTR_GROUP_NAME,
    ATTR_SWITCHES,
    COMPONENT_CONFIG,
    COMPONENT_DOMAIN,
    COMPONENT_MANUFACTURER,
    COMPONENT_MODEL,
    CONF_YAML_CONFIG,
)

__version__ = "0.7.0b13"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        COMPONENT_DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_YAML_CONFIG, default=False): cv.boolean,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an momentary component."""
    # hass.data.setdefault(COMPONENT_DOMAIN, {})

    if COMPONENT_DOMAIN not in hass.data:
        hass.data[COMPONENT_DOMAIN] = {}
        hass.data[COMPONENT_CONFIG] = {}

    # See if yaml support was enabled.
    if not config.get(COMPONENT_DOMAIN, {}).get(CONF_YAML_CONFIG, False):
        # New style. We import old config if needed.
        _LOGGER.debug("setting up new momentary components")
        hass.data[COMPONENT_CONFIG][CONF_YAML_CONFIG] = False

        # See if we have already imported the data. If we haven't then do it now.
        config_entry = _async_find_matching_config_entry(hass)
        if not config_entry:
            _LOGGER.debug("importing a YAML setup")
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    COMPONENT_DOMAIN,
                    context={CONF_SOURCE: SOURCE_IMPORT},
                    data=config.get(Platform.SWITCH, []),
                )
            )

            async_create_issue(
                hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{COMPONENT_DOMAIN}",
                is_fixable=False,
                issue_domain=COMPONENT_DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": COMPONENT_DOMAIN,
                    "integration_title": "Momentary",
                },
            )

        else:
            _LOGGER.debug("ignoring a YAML setup")

    else:
        _LOGGER.debug("setting up old momentary components")
        hass.data[COMPONENT_CONFIG][CONF_YAML_CONFIG] = True

    return True


@callback
def _async_find_matching_config_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return a matching config entry for this integration.

    If a config entry exists for the integration we consider the integration
    configured and will ignore any YAML configuration.
    """
    for entry in hass.config_entries.async_entries(COMPONENT_DOMAIN):
        return entry
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for the momentary integration.

    This loads stored devices and creates the switch entities for the entry.
    """
    _LOGGER.debug("async setup %s", entry.data)

    if COMPONENT_DOMAIN not in hass.data:
        hass.data[COMPONENT_DOMAIN] = {}
        hass.data[COMPONENT_CONFIG] = {}

    # Database of devices
    group_name = entry.data[ATTR_GROUP_NAME]
    file_name = entry.data[ATTR_FILE_NAME]
    cfg = BlendedCfg(hass, group_name, file_name)
    await cfg.async_load()

    # Load and create devices.
    for device, name in cfg.devices.items():
        _LOGGER.debug("would try to add device %s/%s", device, name)
        await _async_get_or_create_momentary_device_in_registry(hass, entry, device, name)

    # Delete orphaned devices.
    for switch, values in cfg.orphaned_devices.items():
        _LOGGER.debug("would try to delete %s/%s", switch, values)
        await _async_delete_momentary_device_from_registry(hass, entry, switch, values)

    # Update hass data and queue entry creation.
    hass.data[COMPONENT_DOMAIN].update(
        {
            group_name: {
                ATTR_DEVICES: cfg.devices,
                ATTR_SWITCHES: cfg.switches,
                ATTR_FILE_NAME: file_name,
            }
        }
    )
    _LOGGER.debug("update hass data %s", hass.data[COMPONENT_DOMAIN])
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SWITCH])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("unloading it %s", entry.data[ATTR_GROUP_NAME])
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SWITCH])
    if unload_ok:
        await BlendedCfg.delete_group(hass, entry.data[ATTR_GROUP_NAME])
        cfg = hass.data[COMPONENT_DOMAIN].pop(entry.data[ATTR_GROUP_NAME])
        for device, name in cfg[ATTR_DEVICES].items():
            await _async_delete_momentary_device_from_registry(hass, entry, device, name)
    _LOGGER.debug("after hass=%s", hass.data[COMPONENT_DOMAIN])

    return unload_ok


async def _async_get_or_create_momentary_device_in_registry(
    hass: HomeAssistant, entry: ConfigEntry, device_id: str, name: str
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(COMPONENT_DOMAIN, device_id)},
        manufacturer=COMPONENT_MANUFACTURER,
        name=name,
        model=COMPONENT_MODEL,
        sw_version=__version__,
    )


async def _async_delete_momentary_device_from_registry(
    hass: HomeAssistant, _entry: ConfigEntry, device_id: str, _name: str
) -> None:
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(COMPONENT_DOMAIN, device_id)},
    )
    if device:
        _LOGGER.debug("found something to delete! %s", device.id)
        device_registry.async_remove_device(device.id)
    else:
        _LOGGER.info("have orphaned device in meta %s", device_id)
