"""Provide constants for the momentary integration.

This module defines commonly used constants for configuration,
defaults, and attributes used by the integration.
"""

from datetime import datetime, timedelta

from homeassistant.const import CONF_DEVICE_ID, CONF_NAME  # noqa: F401

VERSION = "0.7.0b13"
DOMAIN = "momentary"

ATTR_IDLE_STATE = "idle_state"
ATTR_TIMED_STATE = "timed_state"
ATTR_TOGGLE_UNTIL = "toggle_until"

CONF_CANCELLABLE = "cancellable"
CONF_MODE = "mode"
CONF_TOGGLE_FOR = "toggle_for"
CONF_ID_TOKEN = "id_token"
CONF_YAML_PRESENT = "yaml_present"
CONF_YAML_SWITCH = "yaml_switch"
CONF_DEVICE_ASSOCIATION = "device_association"
CONF_CLEAR_DEVICE_ID = "clear_device_id"

DEFAULT_CANCELLABLE = False
DEFAULT_MODE = True
DEFAULT_MODE_STR = "on"
DEFAULT_TOGGLE_FOR = {"hours": 0, "minutes": 0, "seconds": 1}
DEFAULT_TOGGLE_FOR_TIMEDELTA = timedelta(**DEFAULT_TOGGLE_FOR)
DEFAULT_CLEAR_DEVICE_ID = False

DEFAULT_TOGGLE_UNTIL_STR = "1970-01-01T00:00:00+00:00"
DEFAULT_TOGGLE_UNTIL = datetime.fromisoformat(DEFAULT_TOGGLE_UNTIL_STR)
