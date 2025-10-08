"""Provide the momentary switch integration for Home Assistant.

This module handles setup of the integration and config entry lifecycle.
"""

from __future__ import annotations

import contextlib
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device import async_remove_stale_devices_links_keep_current_device
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICE_ID, CONF_NAME, CONF_YAML_PRESENT, CONF_YAML_SWITCH, DOMAIN
from .helpers import async_process_yaml

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the momentary integration and register services.

    This initializes integration data structures on hass.data and registers
    a reload service that can reprocess YAML configuration when requested.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    config : ConfigType
        The configuration passed from Home Assistant.

    Returns
    -------
    bool
        True if setup succeeded and YAML processing completed, False otherwise.

    """
    hass.data.setdefault(DOMAIN, {})

    async def _async_reload_service_handler(service: ServiceCall) -> None:
        _LOGGER.info("Service %s.reload called. Reloading YAML integration", DOMAIN)
        reload_config = None
        with contextlib.suppress(HomeAssistantError):
            reload_config = await async_integration_yaml_config(hass, DOMAIN)
        if reload_config is None:
            return
        # _LOGGER.debug("reload_config: %s", reload_config)
        await async_process_yaml(hass, reload_config)

    hass.services.async_register(DOMAIN, SERVICE_RELOAD, _async_reload_service_handler)
    # _LOGGER.debug("[async_setup] config: %s", config)
    return await async_process_yaml(hass, config)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for the momentary integration.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    entry : ConfigEntry
        The configuration entry being set up.

    Returns
    -------
    bool
        True if the entry was successfully set up, False otherwise.

    """
    # _LOGGER.debug("[async_setup_entry] entry: %s", entry.data)

    async_remove_stale_devices_links_keep_current_device(
        hass,
        entry.entry_id,
        entry.data.get(CONF_DEVICE_ID),
    )

    if entry.data.get(CONF_YAML_SWITCH, False):
        if not entry.data.get(CONF_YAML_PRESENT, False):
            _LOGGER.warning(
                "[YAML] YAML Entry no longer exists. Deleting entry in HA: %s",
                entry.data.get(CONF_NAME),
            )
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
            return False
        hass_data = {key: value for key, value in entry.data.items() if key != CONF_YAML_PRESENT}
    else:
        hass_data = dict(entry.data)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = hass_data
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SWITCH])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry for the momentary integration.

    This cleans up the entry by unloading its platforms and removing stored
    data for the entry from hass.data.

    Parameters
    ----------
    hass : HomeAssistant
        The Home Assistant instance.
    entry : ConfigEntry
        The configuration entry being unloaded.

    Returns
    -------
    bool
        True if the platforms were unloaded successfully, False otherwise.

    """

    _LOGGER.info("Unloading: %s", entry.data)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SWITCH])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
