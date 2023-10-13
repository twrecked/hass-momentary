import copy
import logging
import json
import uuid
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, Platform
from homeassistant.util import slugify
from homeassistant.util.yaml import load_yaml, save_yaml

from .const import (
    ATTR_SWITCHES,
    ATTR_UNIQUE_ID,
    ATTR_VERSION,
    CONF_CANCELLABLE,
    CONF_MODE,
    CONF_NAME,
    CONF_TOGGLE_FOR,
    DEFAULT_CANCELLABLE,
    DEFAULT_MODE,
    DEFAULT_TOGGLE_FOR,
    DB_SWITCHES_FILE,
    DB_SWITCHES_META_FILE,
    DOMAIN
)

_LOGGER = logging.getLogger(__name__)

DB_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
    vol.Optional(CONF_TOGGLE_FOR, default=DEFAULT_TOGGLE_FOR): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_CANCELLABLE, default=DEFAULT_CANCELLABLE): cv.boolean,
})


class Db:
    """ Manage the momentary switch database.
    
    We have 2 data points:
    - DB_SWITCHES_FILE; where the user configures their switches, we create
      this the first time the config flow code is run
    - DB_SWITCHES_META_FILE; where we map the user entries to their unique ids

    When we load we match the user list against our meta list and update
    entries as needed.
    """

    _switches_file: str = DB_SWITCHES_FILE
    _switches = {}
    _switches_meta_data = {}
    _switches_orphaned_meta_data = {}
    _changed: bool = False

    def __init__(self, file=DB_SWITCHES_FILE):
        self._switches_file = file

    def _make_original_unique_id(self, name):
        if name.startswith("!"):
            return slugify(name[1:])
        else:
            return slugify(name)

    def _make_original_entity_id(self, platform, name):
        if name.startswith("!"):
            return f'{platform}.{slugify(name[1:])}'
        else:
            return f'{platform}.{DOMAIN}_{slugify(name)}'

    def _make_original_name(self, name):
        if name.startswith("!"):
            return name[1:]
        return f"{DOMAIN} {name}"

    def _map_config_name(self, name):
        """ Fix the name prefix.
        We remove the ! sign meaning no to add momentary to the name and
        add + where there was no !.
        """
        if name.startswith("!"):
            return name[1:]
        return f"+{name}"

    def _make_name(self, name):
        if name.startswith("+"):
            return name[1:]
        return name

    def _make_unique_id(self):
        return f'{uuid.uuid4()}.{DOMAIN}'

    def _make_entity_id(self, platform, name):
        if name.startswith("+"):
            return f'{platform}.{DOMAIN}_{slugify(name[1:])}'
        return f'{platform}.{slugify(name)}'

    def save_meta_data(self):
        try:
            with open(DB_SWITCHES_META_FILE, 'w') as meta_file:
                json.dump({
                    ATTR_VERSION: 1,
                    ATTR_SWITCHES: self._switches_meta_data
                }, meta_file, indent=4)
            self._changed = False
        except Exception as e:
            _LOGGER.debug(f"couldn't save meta data {str(e)}")

    def save_user_data(self):
        try:
            save_yaml(self._switches_file, {
                ATTR_VERSION: 1,
                ATTR_SWITCHES: list(self._switches.values())
            })
        except Exception as e:
            _LOGGER.debug(f"couldn't save user data {str(e)}")

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

            self._switches = {}
            self._switches_meta_data = {}
            self._switches_orphaned_meta_data = {}

            # Read in the known meta data. We put this into a temporary
            # variable for now. Anything we find in the user list is moved into
            # the permanent variable. Anything left is orphaned.
            meta_data = {}
            try:
                with open(DB_SWITCHES_META_FILE, 'r') as meta_file:
                    meta_data = json.load(meta_file).get(ATTR_SWITCHES, {})
            except Exception as e:
                _LOGGER.debug(f"failed to read meta data {str(e)}")

            # Read in the user data.
            for switch in load_yaml(self._switches_file).get(ATTR_SWITCHES, []):

                # Make sure it looks sane and fix up the defaults.
                switch = DB_SCHEMA(switch)

                # Save yaml name and use for indexing.
                name = switch[ATTR_NAME]
                
                # If there isn't a unique_id we create one. This usually means
                # the user added a new switch to the array.
                unique_id = meta_data.get(name, {}).get(ATTR_UNIQUE_ID, None)
                if unique_id is None:

                    _LOGGER.debug(f"adding {name} to the list of devices")
                    unique_id = self._make_unique_id()
                    meta_data.update({name: {
                        ATTR_UNIQUE_ID: unique_id,
                        ATTR_ENTITY_ID: self._make_entity_id('switch', name)
                    }})
                    self._changed = True

                # Now copy over the entity id of the device. Not having this is a
                # bug.
                entity_id = meta_data.get(name, {}).get(ATTR_ENTITY_ID, None)
                if entity_id is None:
                    _LOGGER.info(f"problem creating {name}, no entity id")
                    continue

                # Update YAML switch with fixed values.
                switch.update({
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_NAME: self._make_name(name)
                })

                # Add into switches dictionary by unique id and move meta data
                # off temporary list.
                self._switches.update({
                    unique_id: switch
                })
                self._switches_meta_data.update({
                    name: meta_data.pop(name)
                })

            # Create orphaned list. If we have anything here we need to update
            # the saved meta data.
            for switch, values in meta_data.items():
                values[ATTR_NAME] = switch
                self._switches_orphaned_meta_data.update({
                    values[ATTR_UNIQUE_ID]: values
                })
                self._changed = True

            # Make sure changes are kept.
            if self._changed:
                self.save_meta_data()

            self.dump("load")

        except Exception as e:
            _LOGGER.debug(f"no file to load {str(e)}")
            self._switches = {}
            self._switches_meta_data = {}
            self._switches_orphaned_meta_data = {}

    def get(self):
        return self._switches

    def orphaned(self):
        return self._switches_orphaned_meta_data

    def import_switch(self, switch):
        """ Import an original YAML entry.
        """

        # We remove the platform field. We deepcopy before doing this to
        # quiet down some startup errors.
        switch = copy.deepcopy(switch)
        switch.pop('platform', None)

        # Create a unique and entity ids that matches the original version.
        # Do this before fixing the name.
        unique_id = self._make_original_unique_id(switch[ATTR_NAME])
        entity_id = self._make_original_entity_id(Platform.SWITCH, switch[ATTR_NAME])

        # Fix the name by removing a ! or adding a + as needed.
        switch[ATTR_NAME] = self._map_config_name(switch[ATTR_NAME])

        # Add into the meta and user data.
        self._switches.update({
            unique_id: switch
        })
        self._switches_meta_data.update({switch[ATTR_NAME]: {
            ATTR_UNIQUE_ID: unique_id,
            ATTR_ENTITY_ID: entity_id
        }})

        # Update both database files.
        self.save_meta_data()
        self.save_user_data()
        self.dump("import")

    def dump(self, prefix):
        _LOGGER.debug(f"dump({prefix}):meta={self._switches_meta_data}")
        _LOGGER.debug(f"dump({prefix}):switches={self._switches}")
        _LOGGER.debug(f"dump({prefix}):orphaned={self._switches_orphaned_meta_data}")
