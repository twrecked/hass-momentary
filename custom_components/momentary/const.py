"""Provide constants and helper functions for the momentary integration.

This module defines commonly used string constants and small helpers used
by the integration code.
"""

from datetime import timedelta

from homeassistant.core import HomeAssistant

COMPONENT_DOMAIN = "momentary"
COMPONENT_CONFIG = "momentary-config"
COMPONENT_MANUFACTURER = "twrecked"
COMPONENT_MODEL = "momentary"

ATTR_DEVICES = "devices"
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
CONF_YAML_CONFIG = "yaml_config"

DEFAULT_CANCELLABLE = False
DEFAULT_IMPORTED_NAME = "import"
DEFAULT_MODE = "old"
DEFAULT_TOGGLE_FOR = timedelta(seconds=1)


def default_config_file(hass: HomeAssistant) -> str:
    """Return the default path to the user YAML configuration file."""
    return hass.config.path("momentary.yaml")


def default_meta_file(hass: HomeAssistant) -> str:
    """Return the default path to the integration meta storage file."""
    return hass.config.path(".storage/momentary.meta.json")
