"""
This component provides support for a momentary switch.
"""

from datetime import timedelta

COMPONENT_DOMAIN = "momentary"
COMPONENT_MANUFACTURER = "twrecked"
COMPONENT_MODEL = "momentary"

ATTR_DEVICE_ID = "device_id"
ATTR_FILE_NAME = "file_name"
ATTR_GROUP_NAME = "group_name"
ATTR_IDLE_STATE = "idle_state"
ATTR_SWITCH = "switch"
ATTR_SWITCHES = "switches"
ATTR_TIMED_STATE = "timed_state"
ATTR_TOGGLE_UNTIL = "toggle_until"
ATTR_UNIQUE_ID = "unique_id"
ATTR_VERSION = "version"

CONF_CANCELLABLE = "cancellable"
CONF_MODE = "mode"
CONF_NAME = "name"
CONF_TOGGLE_FOR = "toggle_for"

DEFAULT_CANCELLABLE = False
DEFAULT_IMPORTED_NAME = "import"
DEFAULT_MODE = "old"
DEFAULT_TOGGLE_FOR = timedelta(seconds=1)

DB_DEFAULT_SWITCHES_FILE = "/config/momentary.yaml"
DB_DEFAULT_SWITCHES_META_FILE = "/config/.storage/momentary.meta.json"
