"""Provide the momentary switch integration for Home Assistant.

This module handles setup of the integration and config entry lifecycle.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
import secrets

from aiohttp import web
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_SOURCE, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.yaml import parse_yaml

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

__version__ = "0.8.0-alpha.2"

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
    """Set up the momentary component."""
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


async def _async_handle_builder_webhook(
    hass: HomeAssistant, _webhook_id: str, request: web.Request, entry: ConfigEntry
) -> web.Response:
    """Handle incoming YAML save from Momentary Device Editor."""
    token = request.query.get("token") or request.headers.get("X-Auth-Token")
    expected_token = (
        hass.data.get(COMPONENT_DOMAIN, {})
        .get(entry.entry_id, {})
        .get("webhook_token")
    )
    if not token or token != expected_token:
        _LOGGER.warning("Invalid token received on momentary builder webhook")
        return web.Response(text="Invalid token", status=403)

    body = await request.text()
    if not body:
        return web.Response(text="Empty body", status=400)

    try:
        parsed = parse_yaml(body)
        if not isinstance(parsed, dict):
            return web.Response(text="YAML root must be a dictionary", status=400)
    except (HomeAssistantError, ValueError, TypeError) as err:
        _LOGGER.warning("Invalid YAML received on builder webhook: %s", err)
        return web.Response(text=f"Invalid YAML: {err}", status=400)

    file_name = entry.data.get(ATTR_FILE_NAME)
    if not file_name:
        return web.Response(text="No file_name configured for entry", status=500)

    def _write_yaml() -> None:
        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = path.with_name(f"{path.name}.tmp")
        temp_file.write_text(body, encoding="utf-8")
        temp_file.replace(path)

    await hass.async_add_executor_job(_write_yaml)
    _LOGGER.info("Successfully updated %s from Momentary Device Editor", file_name)

    # Reload config entry asynchronously to pick up changes
    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
    return web.Response(text="OK", status=200)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for the momentary integration.

    This loads stored devices and creates the switch entities for the entry.
    """
    _LOGGER.debug("async setup %s", entry.data)

    if COMPONENT_DOMAIN not in hass.data:
        hass.data[COMPONENT_DOMAIN] = {}
        hass.data[COMPONENT_CONFIG] = {}

    if ATTR_GROUP_NAME not in entry.data or ATTR_FILE_NAME not in entry.data:
        _LOGGER.error("Config entry %s missing required group_name or file_name", entry.title)
        return False

    group_name = entry.data[ATTR_GROUP_NAME]
    file_name = entry.data[ATTR_FILE_NAME]

    # Register builder webhook
    webhook_id = f"momentary_{entry.entry_id}"
    token = secrets.token_hex(16)
    if entry.entry_id not in hass.data[COMPONENT_DOMAIN]:
        hass.data[COMPONENT_DOMAIN][entry.entry_id] = {}
    hass.data[COMPONENT_DOMAIN][entry.entry_id]["webhook_token"] = token
    hass.data[COMPONENT_DOMAIN][entry.entry_id]["webhook_id"] = webhook_id

    async def _handle_webhook(
        hass_instance: HomeAssistant, wh_id: str, req: web.Request
    ) -> web.Response:
        return await _async_handle_builder_webhook(hass_instance, wh_id, req, entry)

    with contextlib.suppress(ValueError):
        webhook.async_register(
            hass,
            COMPONENT_DOMAIN,
            f"Momentary Builder ({group_name})",
            webhook_id,
            _handle_webhook,
            allowed_methods=["POST"],
        )

    # Database of devices
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

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SWITCH])

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    group_name = entry.data.get(ATTR_GROUP_NAME)
    _LOGGER.debug("unloading momentary group %s", group_name)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SWITCH])
    if unload_ok:
        if group_name:
            hass.data.get(COMPONENT_DOMAIN, {}).pop(group_name, None)

        webhook_id = f"momentary_{entry.entry_id}"
        with contextlib.suppress(ValueError, KeyError):
            webhook.async_unregister(hass, webhook_id)
        hass.data.get(COMPONENT_DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    group_name = entry.data.get(ATTR_GROUP_NAME)
    if group_name:
        _LOGGER.debug("removing momentary group meta for %s", group_name)
        await BlendedCfg.delete_group(hass, group_name)


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
