"""
This component provides support for a momentary switch.
"""

import copy
import logging
import json
import threading
import uuid

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    CONF_PLATFORM,
    Platform
)
from homeassistant.util import slugify
from homeassistant.util.yaml import load_yaml, save_yaml

from .const import *


_LOGGER = logging.getLogger(__name__)

DB_LOCK = threading.Lock()


def _fix_value(value):
    """ If needed, convert value into a type that can be stored in yaml.
    """
    if isinstance(value, timedelta):
        return max(value.seconds, 1)
    return value


def _load_meta_data(group_name: str):
    """Read in meta data for a particular group.
    """
    with DB_LOCK:
        try:
            with open(DB_DEFAULT_SWITCHES_META_FILE, "r") as meta_file:
                meta_data = json.load(meta_file)
                return (
                    meta_data.get(ATTR_DEVICES, {}).get(group_name, {}),
                    meta_data.get(ATTR_SWITCHES, {}).get(group_name, {})
                )
        except Exception as e:
            _LOGGER.debug(f"failed to read meta data {str(e)}")
    return {}


def _save_meta_data(group_name: str, device_meta_data, group_switches):
    """Save meta data for a particular group name.
    """
    with DB_LOCK:

        # Read in current meta data
        switches = {}
        devices = {}
        try:
            with open(DB_DEFAULT_SWITCHES_META_FILE, "r") as meta_file:
                meta_data = json.load(meta_file)
                devices = meta_data.get(ATTR_DEVICES, {})
                switches = meta_data.get(ATTR_SWITCHES, {})
        except Exception as e:
            _LOGGER.debug(f"no meta data yet {str(e)}")

        # Update (or add) the group piece.
        _LOGGER.debug(f"device meta before {devices}")
        _LOGGER.debug(f"switch meta before {switches}")
        switches.update({
            group_name: group_switches
        })
        devices.update({
            group_name: device_meta_data
        })
        _LOGGER.debug(f"device meta after {devices}")
        _LOGGER.debug(f"switch meta after {switches}")

        # Write it back out.
        try:
            with open(DB_DEFAULT_SWITCHES_META_FILE, "w") as meta_file:
                json.dump({
                    ATTR_VERSION: 1,
                    ATTR_DEVICES: devices,
                    ATTR_SWITCHES: switches
                }, meta_file, indent=4)
        except Exception as e:
            _LOGGER.debug(f"couldn't save meta data {str(e)}")


def _delete_meta_data(group_name: str):
    """Save meta data for a particular group name.
    """
    with DB_LOCK:

        # Read in current meta data
        switches = {}
        try:
            with open(DB_DEFAULT_SWITCHES_META_FILE, "r") as meta_file:
                meta_data = json.load(meta_file)
                devices = meta_data.get(ATTR_DEVICES, {})
                switches = meta_data.get(ATTR_SWITCHES, {})
        except Exception as e:
            _LOGGER.debug(f"no meta data yet {str(e)}")

        # Remove the group.
        _LOGGER.debug(f"devices meta before {devices}")
        _LOGGER.debug(f"switches meta before {switches}")
        devices.pop(group_name)
        switches.pop(group_name)
        _LOGGER.debug(f"devices meta after {devices}")
        _LOGGER.debug(f"switches meta after {switches}")

        # Write it back out.
        try:
            with open(DB_DEFAULT_SWITCHES_META_FILE, "w") as meta_file:
                json.dump({
                    ATTR_VERSION: 1,
                    ATTR_DEVICES: devices,
                    ATTR_SWITCHES: switches
                }, meta_file, indent=4)
        except Exception as e:
            _LOGGER.debug(f"couldn't save meta data {str(e)}")


def _load_user_data(switches_file: str):
    try:
        return load_yaml(switches_file).get(ATTR_SWITCHES, [])
    except Exception as e:
        _LOGGER.debug(f"failed to read switch data {str(e)}")
    return {}


def _save_user_data(switches_file: str, switches):
    try:
        save_yaml(switches_file, {
            ATTR_VERSION: 1,
            ATTR_SWITCHES: list(switches.values())
        })
    except Exception as e:
        _LOGGER.debug(f"couldn't save user data {str(e)}")


def _make_original_unique_id(name):
    if name.startswith("!"):
        return slugify(name[1:])
    else:
        return slugify(name)


def _make_original_entity_id(platform, name):
    if name.startswith("!"):
        return f"{platform}.{slugify(name[1:])}"
    else:
        return f"{platform}.{COMPONENT_DOMAIN}_{slugify(name)}"


def _make_original_name(name):
    if name.startswith("!"):
        return name[1:]
    return f"{COMPONENT_DOMAIN} {name}"


def _map_config_name(name):
    """ Fix the name prefix.
    We remove the ! sign meaning no to add momentary to the name and
    add + where there was no !.
    """
    if name.startswith("!"):
        return name[1:]
    return f"+{name}"


def _make_name(name):
    if name.startswith("+"):
        return name[1:]
    return name


def _make_unique_id():
    return f"{uuid.uuid4()}.{COMPONENT_DOMAIN}"


def _make_entity_id(platform, name):
    if name.startswith("+"):
        return f"{platform}.{COMPONENT_DOMAIN}_{slugify(name[1:])}"
    return f"{platform}.{slugify(name)}"


def _make_device_id(name):
    return f"{slugify(_make_name(name))}"


class BlendedCfg:
    """ Manage the momentary switch database.
    
    We have 2 data points:
    - DB_DEFAULT_SWITCHES_FILE; where the user configures their switches, we create
      this the first time the config flow code is run
    - DB_DEFAULT_SWITCHES_META_FILE; where we map the user entries to their unique ids

    When we load we match the user list against our meta list and update
    entries as needed.
    """

    def __init__(self, group_name: str, file: str):
        self._group_name = group_name
        self._switches_file = file
        self._changed: bool = False

        self._devices = {}
        self._dmeta_data = {}
        self._dmeta_data_in = {}
        self._orphaned_devices = {}

        self._switches = {}
        self._smeta_data = {}
        self._smeta_data_in = {}

    def _parse_switches(self, device_name, switches) -> None:

        # Look up the device ID. If we don't have one we create it now.
        device_id = self._dmeta_data_in.get(device_name, {}).get(ATTR_DEVICE_ID, None)
        if device_id is None:
            _LOGGER.debug(f"adding '{device_name}' to the list of devices")
            # device_id = slugify(f"{COMPONENT_DOMAIN}.{self._group_name}.{device_name}")
            device_id = _make_unique_id()
            self._dmeta_data_in.update({device_name: {
                ATTR_DEVICE_ID: device_id
            }})
            self._changed = True

        # Update the device list and active device meta data.
        _LOGGER.debug(f"working with device {device_name}/{device_id}")
        self._devices.update({
            device_id: _make_name(device_name)
        })
        self._dmeta_data.update({
            device_name: self._dmeta_data_in[device_name]
        })

        # Now attach each switch to a device.
        for switch in switches:
            name = switch[ATTR_NAME]

            # If there isn't a unique_id we create one. This usually means
            # the user added a new switch to the array.
            unique_id = self._smeta_data_in.get(name, {}).get(ATTR_UNIQUE_ID, None)
            if unique_id is None:

                _LOGGER.debug(f"adding {name} to the list of entities")
                unique_id = _make_unique_id()
                self._smeta_data_in.update({name: {
                    ATTR_UNIQUE_ID: unique_id,
                    ATTR_ENTITY_ID: _make_entity_id(str(Platform.SWITCH), name)
                }})
                self._changed = True

            # Now copy over the entity id of the device. Not having this is a
            # bug.
            entity_id = self._smeta_data_in.get(name, {}).get(ATTR_ENTITY_ID, None)
            if entity_id is None:
                _LOGGER.info(f"problem creating {name}, no entity id")
                continue

            # Finalize the switch values - add in fixed pieces and update
            # the dictionary, note down the meta data is still active.
            _LOGGER.debug(f"working with entity {name}/{entity_id}")
            switch.update({
                ATTR_DEVICE_ID: device_id,
                ATTR_ENTITY_ID: entity_id,
                ATTR_NAME: _make_name(name)
            })
            self._switches.update({
                unique_id: switch
            })
            self._smeta_data.update({
                name: self._smeta_data_in.pop(name)
            })

    def load(self) -> None:
        """ Load switches from the database.

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
            self._dmeta_data_in, self._smeta_data_in = _load_meta_data(self._group_name)

            # Parse out the user data. We have 2 formats:
            # - `name:` this indicates a device/entity with a one to one mapping
            # - `a device name:`, any key other than `name`, this indicates a
            #   device with multiple entities, we use the key to find the device
            for device_or_switch in _load_user_data(self._switches_file):
                if CONF_NAME in device_or_switch:
                    device_name = device_or_switch[CONF_NAME]
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
                    _LOGGER.debug(f"still using {device_name}")
                    continue
                _LOGGER.debug(f"don't need {device_name}")
                self._orphaned_devices.update({
                    values[ATTR_DEVICE_ID]: device_name
                })
                self._changed = True

            # Make sure changes are kept.
            if self._changed:
                _save_meta_data(self._group_name, self._dmeta_data, self._smeta_data)
                self._changed = False

            self.dump()

        except Exception as e:
            _LOGGER.debug(f"no file to load {str(e)}")
            self._devices = {}
            self._dmeta_data = {}
            self._orphaned_devices = {}
            self._switches = {}
            self._smeta_data = {}

    @property
    def group(self):
        return self._group_name

    @property
    def devices(self):
        return self._devices

    @property
    def orphaned_devices(self):
        return self._orphaned_devices

    @property
    def switches(self):
        return self._switches

    @staticmethod
    def delete_group(group_name: str):
        _delete_meta_data(group_name)

    def dump(self):
        _LOGGER.debug(f"dump(load):devices={self._devices}")
        _LOGGER.debug(f"dump(load):devices-meta={self._dmeta_data}")
        _LOGGER.debug(f"dump(load):orphaned-devices={self._orphaned_devices}")
        _LOGGER.debug(f"dump(load):switches={self._switches}")
        _LOGGER.debug(f"dump(load):switches-meta={self._smeta_data}")


class UpgradeCfg:

    def __init__(self, group_name: str, file: str):
        self._group_name = group_name
        self._switches_file = file

        self._dmeta_data = {}
        self._switches = {}
        self._smeta_data = {}

    def import_switch(self, switch):
        """ Import an original YAML entry.
        """

        _LOGGER.debug(f"import={switch}")

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
        self._switches.update({
            unique_id: switch
        })
        self._smeta_data.update({switch[ATTR_NAME]: {
            ATTR_UNIQUE_ID: unique_id,
            ATTR_ENTITY_ID: entity_id
        }})
        self._dmeta_data.update({switch[ATTR_NAME]: {
            ATTR_DEVICE_ID: device_id
        }})

    @property
    def switch_keys(self):
        return self._switches.keys()

    def save(self):
        # Update both database files.
        _save_meta_data(self._group_name, self._dmeta_data, self._smeta_data)
        _save_user_data(self._switches_file, self._switches)
        self.dump()

    def dump(self):
        _LOGGER.debug(f"dump(import):devices-meta={self._dmeta_data}")
        _LOGGER.debug(f"dump(import):switches={self._switches}")
        _LOGGER.debug(f"dump(import):switches-meta={self._smeta_data}")
