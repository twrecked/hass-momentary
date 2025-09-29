"""Provide helper utilities for the momentary integration.

This module manages loading and saving user and meta configuration for the
momentary integration.
"""

import asyncio
import copy
from datetime import timedelta
import json
import logging
from typing import Any
import uuid

import aiofiles

from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, CONF_NAME, CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
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


async def _async_load_json(file_name: str) -> dict[str, Any]:
    _LOGGER.debug("_async_load_yaml1 file_name for %s", file_name)
    try:
        async with aiofiles.open(file_name) as meta_file:
            _LOGGER.debug("_async_load_yaml2 file_name for %s", file_name)
            contents = await meta_file.read()
            _LOGGER.debug("_async_load_yaml3 file_name for %s", file_name)
            return json.loads(contents)
    except (FileNotFoundError, PermissionError, json.JSONDecodeError) as err:
        _LOGGER.debug("_async_load_json failed for %s: %s", file_name, err)
        return {}


async def _async_save_json(file_name: str, data: dict[str, Any]) -> None:
    _LOGGER.debug("_async_save_yaml1 file_name for %s", file_name)
    try:
        async with aiofiles.open(file_name, "w") as meta_file:
            data_str: str = json.dumps(data, indent=4)
            await meta_file.write(data_str)
    except (OSError, PermissionError) as err:
        _LOGGER.debug("_async_save_json failed for %s: %s", file_name, err)


async def _async_load_yaml(file_name: str) -> list | str | dict[str, Any]:
    _LOGGER.debug("_async_load_yaml1 file_name for %s", file_name)
    try:
        async with aiofiles.open(file_name) as meta_file:
            _LOGGER.debug("_async_load_yaml2 file_name for %s", file_name)
            contents = await meta_file.read()
            _LOGGER.debug("_async_load_yaml3 file_name for %s", file_name)
            return parse_yaml(contents)
    except (FileNotFoundError, PermissionError, ValueError) as err:
        _LOGGER.debug("_async_load_yaml failed for %s: %s", file_name, err)
        return {}


async def _async_save_yaml(file_name: str, data: dict[str, Any]) -> None:
    _LOGGER.debug("_async_save_yaml1 file_name for %s", file_name)
    try:
        async with aiofiles.open(file_name, "w") as meta_file:
            data_str = dump(data)
            await meta_file.write(data_str)
    except (OSError, PermissionError) as err:
        _LOGGER.debug("_async_save_yaml failed for %s: %s", file_name, err)


async def _load_meta_data(
    hass: HomeAssistant, group_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read stored meta data for a given group.

    Returns a tuple of (devices_meta, switches_meta) for the group.
    """
    async with _meta_lock:
        meta_data = await _async_load_json(default_meta_file(hass))
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
    """Save meta data for a particular group name.

    This updates the stored .storage file atomically while holding an
    asyncio lock to prevent concurrent writes.
    """
    async with _meta_lock:
        # Read in current meta data
        meta_data = await _async_load_json(default_meta_file(hass))
        devices = meta_data.get(ATTR_DEVICES, {})
        switches = meta_data.get(ATTR_SWITCHES, {})

        # Update (or add) the group piece.
        _LOGGER.debug("device meta before %s", devices)
        _LOGGER.debug("switch meta before %s", switches)
        switches.update({group_name: group_switches})
        devices.update({group_name: device_meta_data})
        _LOGGER.debug("device meta after %s", devices)
        _LOGGER.debug("switch meta after %s", switches)

        await _async_save_json(
            default_meta_file(hass),
            {ATTR_VERSION: 1, ATTR_DEVICES: devices, ATTR_SWITCHES: switches},
        )


async def _delete_meta_data(hass: HomeAssistant, group_name: str) -> None:
    """Delete meta data for a particular group name from storage."""
    async with _meta_lock:
        # Read in current meta data
        meta_data = await _async_load_json(default_meta_file(hass))
        devices = meta_data.get(ATTR_DEVICES, {})
        switches = meta_data.get(ATTR_SWITCHES, {})

        # Remove the group.
        _LOGGER.debug("devices meta before %s", devices)
        _LOGGER.debug("switches meta before %s", switches)
        devices.pop(group_name)
        switches.pop(group_name)
        _LOGGER.debug("devices meta after %s", devices)
        _LOGGER.debug("switches meta after %s", switches)

        await _async_save_json(
            default_meta_file(hass),
            {ATTR_VERSION: 1, ATTR_DEVICES: devices, ATTR_SWITCHES: switches},
        )


async def _load_user_data(switches_file: str) -> dict[str, Any]:
    entities = await _async_load_yaml(switches_file)
    if not isinstance(entities, dict):
        return {}
    return entities.get(ATTR_SWITCHES, {})


async def _save_user_data(switches_file: str, switches: dict[str, Any]) -> None:
    await _async_save_yaml(switches_file, {ATTR_VERSION: 1, ATTR_SWITCHES: list(switches.values())})


def _make_original_unique_id(name: str) -> str:
    if name.startswith("!"):
        return slugify(name[1:])
    return slugify(name)


def _make_original_entity_id(platform: Platform, name: str) -> str:
    if name.startswith("!"):
        return f"{platform}.{slugify(name[1:])}"
    return f"{platform}.{COMPONENT_DOMAIN}_{slugify(name)}"


def _make_original_name(name: str) -> str:
    if name.startswith("!"):
        return name[1:]
    return f"{COMPONENT_DOMAIN} {name}"


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


class BlendedCfg:
    """Manage the momentary switch database.

    We have 2 data points:
    - default_config_file(self.hass); where the user configures their switches, we create
      this the first time the config flow code is run
    - default_meta_file(hass); where we map the user entries to their unique ids

    When we load we match the user list against our meta list and update
    entries as needed.
    """

    def __init__(self, hass: HomeAssistant, group_name: str, file: str) -> None:
        """Initialize a blended configuration helper.

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
        self._changed: bool = False

        self._devices: dict[str, Any] = {}
        self._dmeta_data: dict[str, Any] = {}
        self._dmeta_data_in: dict[str, Any] = {}
        self._orphaned_devices: dict[str, Any] = {}

        self._switches: dict[str, Any] = {}
        self._smeta_data: dict[str, Any] = {}
        self._smeta_data_in: dict[str, Any] = {}

    def _parse_switches(self, device_name: str, switches: list) -> None:
        # Look up the device ID. If we don't have one we create it now.
        device_id = self._dmeta_data_in.get(device_name, {}).get(ATTR_DEVICE_ID, None)
        if device_id is None:
            _LOGGER.debug("adding '%s' to the list of devices", device_name)
            # device_id = slugify(f"{COMPONENT_DOMAIN}.{self._group_name}.{device_name}")
            device_id = _make_unique_id()
            self._dmeta_data_in.update({device_name: {ATTR_DEVICE_ID: device_id}})
            self._changed = True

        # Update the device list and active device meta data.
        _LOGGER.debug("working with device %s/%s", device_name, device_id)
        self._devices.update({device_id: _make_name(device_name)})
        self._dmeta_data.update({device_name: self._dmeta_data_in[device_name]})

        # Now attach each switch to a device.
        for switch in switches:
            name = switch[ATTR_NAME]

            # If there isn't a unique_id we create one. This usually means
            # the user added a new switch to the array.
            unique_id = self._smeta_data_in.get(name, {}).get(ATTR_UNIQUE_ID, None)
            if unique_id is None:
                _LOGGER.debug("adding %s to the list of entities", name)
                unique_id = _make_unique_id()
                self._smeta_data_in.update(
                    {
                        name: {
                            ATTR_UNIQUE_ID: unique_id,
                            ATTR_ENTITY_ID: _make_entity_id(str(Platform.SWITCH), name),
                        }
                    }
                )
                self._changed = True

            # Now copy over the entity id of the device. Not having this is a
            # bug.
            entity_id = self._smeta_data_in.get(name, {}).get(ATTR_ENTITY_ID, None)
            if entity_id is None:
                _LOGGER.info("problem creating %s, no entity id", name)
                continue

            # Finalize the switch values - add in fixed pieces and update
            # the dictionary, note down the meta data is still active.
            _LOGGER.debug("working with entity %s/%s", name, entity_id)
            switch.update(
                {ATTR_DEVICE_ID: device_id, ATTR_ENTITY_ID: entity_id, ATTR_NAME: _make_name(name)}
            )
            self._switches.update({unique_id: switch})
            self._smeta_data.update({name: self._smeta_data_in.pop(name)})

    async def async_load(self) -> None:
        """Load switches from the database.

        They are stored as array because it makes it easier for the user to
        add to the list - they don't need to worry about dictionary key
        clashes - so we have to convert it here. As part of the conversion
        we will fix up new entries.

        This doesn't have to worry about upgrades, that is handled in the
        config_flow piece.
        """
        try:
            self._devices = {}
            self._dmeta_data = {}
            self._orphaned_devices = {}
            self._switches = {}
            self._smeta_data = {}

            # Read in the known meta data. We put this into a temporary
            # variable for now. Anything we find in the user list is moved into
            # the permanent variable. Anything left is orphaned.
            self._dmeta_data_in, self._smeta_data_in = await _load_meta_data(
                self._hass, self._group_name
            )

            # Parse out the user data. We have 2 formats:
            # - `name:` this indicates a device/entity with a one to one mapping
            # - `a device name:`, any key other than `name`, this indicates a
            #   device with multiple entities, we use the key to find the device
            for device_or_switch in await _load_user_data(self._switches_file):
                if CONF_NAME in device_or_switch:
                    # TODO: Need to fix typing here.
                    device_name = device_or_switch[CONF_NAME]  # type: ignore[index]
                    self._parse_switches(device_name, [device_or_switch])

                elif isinstance(device_or_switch, dict):
                    device_name = list(device_or_switch.keys())[0]
                    self._parse_switches(device_name, device_or_switch[device_name])

                else:
                    _LOGGER.info("malformed device or group")

            # Create orphaned list. If we have anything here we need to update
            # the saved meta data.
            for device_name, values in self._dmeta_data_in.items():
                if device_name in self._dmeta_data:
                    _LOGGER.debug("still using %s", device_name)
                    continue
                _LOGGER.debug("don't need %s", device_name)
                self._orphaned_devices.update({values[ATTR_DEVICE_ID]: device_name})
                self._changed = True

            # Make sure changes are kept.
            if self._changed:
                await _save_meta_data(
                    self._hass, self._group_name, self._dmeta_data, self._smeta_data
                )
                self._changed = False

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

        # We remove the platform field. We deepcopy before doing this to
        # quiet down some startup errors.
        switch = copy.deepcopy(switch)
        switch.pop(CONF_PLATFORM, None)

        # Create a unique and entity ids that matches the original version.
        # Do this before fixing the name.
        unique_id = _make_original_unique_id(switch[ATTR_NAME])
        entity_id = _make_original_entity_id(Platform.SWITCH, switch[ATTR_NAME])

        # Fix the name by removing a ! or adding a + as needed. Create new
        # device id.
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
        # Update both database files.
        await _save_meta_data(self._hass, self._group_name, self._dmeta_data, self._smeta_data)
        await _save_user_data(self._switches_file, self._switches)
        self.dump()

    def dump(self) -> None:
        """Log the state of the upgrade helper for debugging."""
        _LOGGER.debug("dump(import):devices-meta=%s", self._dmeta_data)
        _LOGGER.debug("dump(import):switches=%s", self._switches)
        _LOGGER.debug("dump(import):switches-meta=%s", self._smeta_data)
