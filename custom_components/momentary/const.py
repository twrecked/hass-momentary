from datetime import timedelta

DOMAIN = 'momentary'

ATTR_FILE_NAME = 'file_name'
ATTR_IDLE_STATE = 'idle_state'
ATTR_SWITCH = 'switch'
ATTR_SWITCHES = 'switches'
ATTR_TIMED_STATE = 'timed_state'
ATTR_TOGGLE_UNTIL = 'toggle_until'
ATTR_UNIQUE_ID = 'unique_id'
ATTR_VERSION = 'version'

CONF_NAME = "name"
CONF_MODE = "mode"
CONF_TOGGLE_FOR = "toggle_for"
CONF_CANCELLABLE = "cancellable"

DEFAULT_MODE = "old"
DEFAULT_CANCELLABLE = False
DEFAULT_TOGGLE_FOR = timedelta(seconds=1)

DB_SWITCHES_FILE = '/config/momentary.yaml'
DB_SWITCHES_META_FILE = '/config/.storage/momentary.meta.json'

MANUFACTURER = "twrecked"
MODEL = "momentary"
