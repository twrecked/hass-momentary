"""Provide helper utilities for the momentary integration.

This module manages loading user configuration and coordinating device and switch
identities with Home Assistant's native registries.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import timedelta
import json
import logging
from pathlib import Path
from typing import Any
import uuid

from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, CONF_NAME, CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
from homeassistant.util import slugify
from homeassistant.util.yaml import dump, parse_yaml

from .const import (
    ATTR_DEVICE_ID,
    ATTR_DEVICES,
    ATTR_SWITCHES,
    ATTR_UNIQUE_ID,
    ATTR_VERSION,
    COMPONENT_DOMAIN,
    default_config_file,
    default_meta_file,
)

_LOGGER = logging.getLogger(__name__)

_meta_lock = asyncio.Lock()


def _fix_value(value: Any) -> Any:
    """Convert values that need to be serialized for YAML storage.

    Currently this normalizes timedelta instances to an integer number of
    seconds (minimum 1) because YAML dumper cannot represent timedelta
    directly in the same way the integration expects.
    """
    if isinstance(value, timedelta):
        return max(value.seconds, 1)
    return value


def _read_file(file_name: str) -> str:
    """Read file content synchronously in executor."""
    return Path(file_name).read_text(encoding="utf-8")


def _write_file(file_name: str, content: str) -> None:
    """Write file content atomically in executor."""
    path = Path(file_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_name(f"{path.name}.tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(path)


async def _async_load_json(hass: HomeAssistant, file_name: str) -> dict[str, Any]:
    _LOGGER.debug("loading JSON %s", file_name)
    try:
        content = await hass.async_add_executor_job(_read_file, file_name)
        return json.loads(content)
    except (FileNotFoundError, PermissionError, json.JSONDecodeError) as err:
        _LOGGER.debug("_async_load_json failed for %s: %s", file_name, err)
        return {}


async def _async_save_json(hass: HomeAssistant, file_name: str, data: dict[str, Any]) -> None:
    _LOGGER.debug("saving JSON %s", file_name)
    try:
        content = json.dumps(data, indent=4)
        await hass.async_add_executor_job(_write_file, file_name, content)
    except (OSError, PermissionError) as err:
        _LOGGER.debug("_async_save_json failed for %s: %s", file_name, err)


async def _async_load_yaml(hass: HomeAssistant, file_name: str) -> Any:
    _LOGGER.debug("loading YAML %s", file_name)
    try:
        content = await hass.async_add_executor_job(_read_file, file_name)
        return parse_yaml(content)
    except (FileNotFoundError, PermissionError, ValueError) as err:
        _LOGGER.debug("_async_load_yaml failed for %s: %s", file_name, err)
        return {}


async def _async_save_yaml(hass: HomeAssistant, file_name: str, data: dict[str, Any]) -> None:
    _LOGGER.debug("saving YAML %s", file_name)
    try:
        content = dump(data)
        await hass.async_add_executor_job(_write_file, file_name, content)
    except (OSError, PermissionError) as err:
        _LOGGER.debug("_async_save_yaml failed for %s: %s", file_name, err)


async def _load_meta_data(
    hass: HomeAssistant, group_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read stored meta data for a given group (legacy fallback).

    Returns a tuple of (devices_meta, switches_meta) for the group.
    """
    async with _meta_lock:
        meta_data = await _async_load_json(hass, default_meta_file(hass))
        return (
            meta_data.get(ATTR_DEVICES, {}).get(group_name, {}),
            meta_data.get(ATTR_SWITCHES, {}).get(group_name, {}),
        )


async def _save_meta_data(
    hass: HomeAssistant,
    group_name: str,
    device_meta_data: dict[str, Any],
    group_switches: dict[str, Any],
) -> None:
    """Save meta data for a particular group name (legacy helper).

    This updates the stored .storage file atomically while holding an
    asyncio lock to prevent concurrent writes.
    """
    async with _meta_lock:
        meta_data = await _async_load_json(hass, default_meta_file(hass))
        devices = meta_data.get(ATTR_DEVICES, {})
        switches = meta_data.get(ATTR_SWITCHES, {})

        _LOGGER.debug("device meta before %s", devices)
        _LOGGER.debug("switch meta before %s", switches)
        switches.update({group_name: group_switches})
        devices.update({group_name: device_meta_data})
        _LOGGER.debug("device meta after %s", devices)
        _LOGGER.debug("switch meta after %s", switches)

        await _async_save_json(
            hass,
            default_meta_file(hass),
            {ATTR_VERSION: 1, ATTR_DEVICES: devices, ATTR_SWITCHES: switches},
        )


async def _delete_meta_data(hass: HomeAssistant, group_name: str) -> None:
    """Delete meta data for a particular group name from storage."""
    async with _meta_lock:
        meta_data = await _async_load_json(hass, default_meta_file(hass))
        devices = meta_data.get(ATTR_DEVICES, {})
        switches = meta_data.get(ATTR_SWITCHES, {})

        _LOGGER.debug("devices meta before %s", devices)
        _LOGGER.debug("switches meta before %s", switches)
        devices.pop(group_name, None)
        switches.pop(group_name, None)
        _LOGGER.debug("devices meta after %s", devices)
        _LOGGER.debug("switches meta after %s", switches)

        await _async_save_json(
            hass,
            default_meta_file(hass),
            {ATTR_VERSION: 1, ATTR_DEVICES: devices, ATTR_SWITCHES: switches},
        )


async def _load_user_data(hass: HomeAssistant, switches_file: str) -> list[dict[str, Any]]:
    entities = await _async_load_yaml(hass, switches_file)
    if not isinstance(entities, dict):
        return []
    switches = entities.get(ATTR_SWITCHES, [])
    if not isinstance(switches, list):
        return []
    return switches


async def _save_user_data(
    hass: HomeAssistant, switches_file: str, switches: dict[str, Any]
) -> None:
    await _async_save_yaml(
        hass, switches_file, {ATTR_VERSION: 1, ATTR_SWITCHES: list(switches.values())}
    )


def _make_original_unique_id(name: str) -> str:
    if name.startswith("!"):
        return slugify(name[1:])
    return slugify(name)


def _make_original_entity_id(platform: Platform, name: str) -> str:
    if name.startswith("!"):
        return f"{platform}.{slugify(name[1:])}"
    return f"{platform}.{COMPONENT_DOMAIN}_{slugify(name)}"


def _map_config_name(name: str) -> str:
    """Fix the name prefix.

    We remove the '!' sign (meaning do not add the integration prefix) and
    add '+' where there was no '!'.
    """
    if name.startswith("!"):
        return name[1:]
    return f"+{name}"


def _make_name(name: str) -> str:
    if name.startswith("+"):
        return name[1:]
    return name


def _make_unique_id() -> str:
    return f"{uuid.uuid4()}.{COMPONENT_DOMAIN}"


def _make_entity_id(platform: str, name: str) -> str:
    if name.startswith("+"):
        return f"{platform}.{COMPONENT_DOMAIN}_{slugify(name[1:])}"
    return f"{platform}.{slugify(name)}"


def _make_device_id(name: str) -> str:
    return f"{slugify(_make_name(name))}"


def _find_matching_device(
    device_name: str,
    clean_device_name: str,
    dev_slug: str,
    existing_devs: list[dr.DeviceEntry] | None,
) -> dr.DeviceEntry | None:
    """Find an existing device in the device registry."""
    if not existing_devs:
        return None
    target_idents = {
        (COMPONENT_DOMAIN, device_name),
        (COMPONENT_DOMAIN, dev_slug),
    }
    target_names = {clean_device_name, device_name}
    for d in existing_devs:
        if any(ident in target_idents for ident in d.identifiers) or d.name in target_names:
            return d
    return None


def _find_matching_entity(
    name: str,
    clean_name: str,
    dev_entities: list[er.RegistryEntry],
    existing_ents: list[er.RegistryEntry] | None,
    clean_device_name: str,
    device_name: str,
    is_group: bool,
) -> er.RegistryEntry | None:
    """Find an existing switch entity in the entity registry."""
    target_names = {clean_name, name}
    if not is_group:
        target_names.update({clean_device_name, device_name})

    for e in dev_entities:
        if e.domain == Platform.SWITCH and e.original_name in target_names:
            return e

    if existing_ents:
        switch_names = {clean_name, name}
        for e in existing_ents:
            if e.domain == Platform.SWITCH and e.original_name in switch_names:
                return e

    return None


class BlendedCfg:
    """Manage the momentary switch configuration and registry coordination.

    Acts as an in-memory hardware bridge and coordinator for a momentary configuration file.
    Loads and parses YAML device definitions, resolves entity IDs and unique IDs against
    Home Assistant's native registries, and supplies structured device and switch payloads to setup.
    """

    def __init__(
        self, hass: HomeAssistant, group_name: str, file: str, entry_id: str | None = None
    ) -> None:
        """Initialize a blended configuration helper.

        Parameters
        ----------
        hass : HomeAssistant
            The Home Assistant instance.
        group_name : str
            The config entry group name.
        file : str
            Path to the user YAML config file.
        entry_id : str | None
            The config entry ID.

        """
        self._hass = hass
        self._group_name = group_name
        self._switches_file = file
        self._entry_id = entry_id
        self._changed: bool = False

        self._devices: dict[str, Any] = {}
        self._dmeta_data: dict[str, Any] = {}
        self._dmeta_data_in: dict[str, Any] = {}
        self._orphaned_devices: dict[str, Any] = {}

        self._switches: dict[str, Any] = {}
        self._smeta_data: dict[str, Any] = {}
        self._smeta_data_in: dict[str, Any] = {}

    def _parse_switches(
        self,
        device_name: str,
        switches: list[Any],
        existing_devs: list[dr.DeviceEntry] | None = None,
        existing_ents: list[er.RegistryEntry] | None = None,
        is_group: bool = False,
    ) -> None:
        clean_device_name = _make_name(device_name)
        dev_slug = slugify(clean_device_name)

        matched_dev = _find_matching_device(device_name, clean_device_name, dev_slug, existing_devs)

        device_id: str | None = None
        if matched_dev:
            for domain, ident in matched_dev.identifiers:
                if domain == COMPONENT_DOMAIN:
                    device_id = ident
                    break

        if device_id is None:
            # Check legacy meta_data (e.g. from momentary.meta.json)
            device_id = self._dmeta_data_in.get(device_name, {}).get(ATTR_DEVICE_ID, None)

        if device_id is None:
            # Deterministic device_id
            device_id = dev_slug

        _LOGGER.debug("working with device %s/%s", device_name, device_id)
        self._devices[device_id] = clean_device_name
        self._dmeta_data[device_name] = {ATTR_DEVICE_ID: device_id}

        dev_entities = (
            [e for e in existing_ents if e.device_id == matched_dev.id]
            if matched_dev and existing_ents
            else []
        )

        # Attach each switch to the device
        for switch in switches:
            if not isinstance(switch, dict) or ATTR_NAME not in switch:
                continue

            name = switch[ATTR_NAME]
            clean_name = _make_name(name)
            switch_slug = slugify(clean_name)

            matched_ent = _find_matching_entity(
                name,
                clean_name,
                dev_entities,
                existing_ents,
                clean_device_name,
                device_name,
                is_group,
            )

            unique_id: str | None = None
            entity_id: str | None = None

            if matched_ent:
                unique_id = matched_ent.unique_id
                entity_id = matched_ent.entity_id

            # 2. Fall back to legacy meta_data candidate keys
            if unique_id is None:
                meta_entry = self._smeta_data_in.get(name) or self._smeta_data_in.get(clean_name)
                if meta_entry:
                    unique_id = meta_entry.get(ATTR_UNIQUE_ID)
                    entity_id = meta_entry.get(ATTR_ENTITY_ID)

            # 3. Deterministic IDs for new entities
            if unique_id is None:
                if is_group:
                    unique_id = f"{dev_slug}_{switch_slug}.{COMPONENT_DOMAIN}"
                    entity_id = _make_entity_id(str(Platform.SWITCH), name)
                else:
                    unique_id = f"{dev_slug}.{COMPONENT_DOMAIN}"
                    entity_id = _make_entity_id(str(Platform.SWITCH), device_name or name)

            if entity_id is None:
                _LOGGER.info("problem creating %s, no entity id", name)
                continue

            self._smeta_data[name] = {
                ATTR_UNIQUE_ID: unique_id,
                ATTR_ENTITY_ID: entity_id,
            }

            _LOGGER.debug("working with entity %s/%s", name, entity_id)
            switch.update(
                {
                    ATTR_DEVICE_ID: device_id,
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_NAME: clean_name,
                }
            )
            self._switches[unique_id] = switch
            if name in self._smeta_data_in:
                self._smeta_data_in.pop(name)

    async def async_load(self) -> None:
        """Load switches from the database.

        They are stored as array because it makes it easier for the user to
        add to the list - they don't need to worry about dictionary key
        clashes - so we have to convert it here. As part of the conversion
        we resolve identities against Home Assistant native registries.
        """
        try:
            self._devices = {}
            self._dmeta_data = {}
            self._orphaned_devices = {}
            self._switches = {}
            self._smeta_data = {}

            # Read in known meta data (legacy fallback)
            self._dmeta_data_in, self._smeta_data_in = await _load_meta_data(
                self._hass, self._group_name
            )

            # Check Home Assistant native registries for existing devices/entities
            dev_reg = dr.async_get(self._hass)
            ent_reg = er.async_get(self._hass)

            existing_devs: list[dr.DeviceEntry] = []
            existing_ents: list[er.RegistryEntry] = []
            if self._entry_id:
                existing_devs = dr.async_entries_for_config_entry(dev_reg, self._entry_id)
                existing_ents = er.async_entries_for_config_entry(ent_reg, self._entry_id)

            # Parse out the user data
            for device_or_switch in await _load_user_data(self._hass, self._switches_file):
                if isinstance(device_or_switch, dict):
                    if CONF_NAME in device_or_switch:
                        device_name = str(device_or_switch[CONF_NAME])
                        self._parse_switches(
                            device_name,
                            [device_or_switch],
                            existing_devs=existing_devs,
                            existing_ents=existing_ents,
                            is_group=False,
                        )
                    else:
                        device_name = list(device_or_switch.keys())[0]
                        children = device_or_switch[device_name]
                        if isinstance(children, list):
                            self._parse_switches(
                                device_name,
                                children,
                                existing_devs=existing_devs,
                                existing_ents=existing_ents,
                                is_group=True,
                            )
                else:
                    _LOGGER.info("malformed device or group: %s", device_or_switch)

            # Build orphaned_devices from legacy meta for backward compatibility if needed
            for device_name, values in self._dmeta_data_in.items():
                if device_name in self._dmeta_data:
                    _LOGGER.debug("still using %s", device_name)
                    continue
                _LOGGER.debug("don't need %s", device_name)
                self._orphaned_devices[values[ATTR_DEVICE_ID]] = device_name

            # Note: We do not write to .storage/momentary.meta.json anymore,
            # as native HA registries now manage persistence.

            self.dump()

        except (FileNotFoundError, PermissionError, json.JSONDecodeError, ValueError) as e:
            _LOGGER.debug("no file to load %s", e)
            self._devices = {}
            self._dmeta_data = {}
            self._orphaned_devices = {}
            self._switches = {}
            self._smeta_data = {}

    @property
    def group(self) -> str:
        """Return the group name for this configuration."""
        return self._group_name

    @property
    def devices(self) -> dict[str, Any]:
        """Return a mapping of device_id to device name for the group."""
        return self._devices

    @property
    def orphaned_devices(self) -> dict[str, Any]:
        """Return a mapping of orphaned device ids to their original names."""
        return self._orphaned_devices

    @property
    def switches(self) -> dict[str, Any]:
        """Return a mapping of unique_id to switch configuration."""
        return self._switches

    @staticmethod
    async def delete_group(hass: HomeAssistant, group_name: str) -> None:
        """Delete stored meta data for the provided group name."""
        await _delete_meta_data(hass, group_name)

    def dump(self) -> None:
        """Log current in-memory configuration for debugging."""
        _LOGGER.debug("dump(load):devices=%s", self._devices)
        _LOGGER.debug("dump(load):devices-meta=%s", self._dmeta_data)
        _LOGGER.debug("dump(load):orphaned-devices=%s", self._orphaned_devices)
        _LOGGER.debug("dump(load):switches=%s", self._switches)
        _LOGGER.debug("dump(load):switches-meta=%s", self._smeta_data)


class UpgradeCfg:
    """Helper used when importing/upgrading YAML config to storage.

    This class collects switches found in legacy YAML and writes both the
    new YAML file and the meta storage file used by the integration.
    """

    def __init__(self, hass: HomeAssistant, group_name: str, file: str) -> None:
        """Initialize the upgrade helper.

        Parameters
        ----------
        hass : HomeAssistant
            The Home Assistant instance.
        group_name : str
            The config entry group name.
        file : str
            Path to the user YAML config file.

        """
        self._hass = hass
        self._group_name = group_name
        self._switches_file = file

        self._dmeta_data: dict[str, Any] = {}
        self._switches: dict[str, Any] = {}
        self._smeta_data: dict[str, Any] = {}

        _LOGGER.debug("new-config-file=%s", default_config_file(self._hass))
        _LOGGER.debug("new-meta-file=%s", default_meta_file(self._hass))

    def import_switch(self, switch: dict[str, Any]) -> None:
        """Import a single original YAML switch entry.

        The function normalizes the entry and populates the in-memory
        structures used when saving the upgraded configuration.
        """
        _LOGGER.debug("import=%s", switch)

        # We remove the platform field.
        switch = copy.deepcopy(switch)
        switch.pop(CONF_PLATFORM, None)

        # Create a unique and entity ids that matches the original version.
        unique_id = _make_original_unique_id(switch[ATTR_NAME])
        entity_id = _make_original_entity_id(Platform.SWITCH, switch[ATTR_NAME])

        # Fix the name by removing a ! or adding a + as needed. Create new device id.
        switch[ATTR_NAME] = _map_config_name(switch[ATTR_NAME])
        device_id = _make_device_id(switch[ATTR_NAME])

        # Fix time deltas
        switch = {k: _fix_value(v) for k, v in switch.items()}

        # Create switch data and meta data.
        self._switches.update({unique_id: switch})
        self._smeta_data.update(
            {switch[ATTR_NAME]: {ATTR_UNIQUE_ID: unique_id, ATTR_ENTITY_ID: entity_id}}
        )
        self._dmeta_data.update({switch[ATTR_NAME]: {ATTR_DEVICE_ID: device_id}})

    @property
    def switch_keys(self) -> list[str]:
        """Return an iterable of the keys (unique ids) for imported switches."""
        return list(self._switches.keys())

    async def async_save(self) -> None:
        """Save upgraded meta and user configurations to disk."""
        await _save_meta_data(self._hass, self._group_name, self._dmeta_data, self._smeta_data)
        await _save_user_data(self._hass, self._switches_file, self._switches)
        self.dump()

    def dump(self) -> None:
        """Log the state of the upgrade helper for debugging."""
        _LOGGER.debug("dump(import):devices-meta=%s", self._dmeta_data)
        _LOGGER.debug("dump(import):switches=%s", self._switches)
        _LOGGER.debug("dump(import):switches-meta=%s", self._smeta_data)
