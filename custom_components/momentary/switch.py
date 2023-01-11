"""
This component provides support for a momentary switch.

"""

import logging
from datetime import timedelta
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.switch import SwitchEntity, DOMAIN
from homeassistant.helpers.config_validation import (PLATFORM_SCHEMA)
from homeassistant.helpers.event import track_point_in_time
from homeassistant.util import slugify

from . import COMPONENT_DOMAIN


_LOGGER = logging.getLogger(__name__)

DEFAULT_MODE = "old"
DEFAULT_CANCELLABLE = False
TOGGLE_FOR_DEFAULT = timedelta(seconds=1)

ATTR_IDLE_STATE = 'idle_state'
ATTR_TIMED_STATE = 'timed_state'
ATTR_UNIQUE_ID = 'unique_id'

CONF_NAME = "name"
CONF_MODE = "mode"
CONF_ON_FOR = "on_for"
CONF_ALLOW_OFF = "allow_off"
CONF_TOGGLE_FOR = "toggle_for"
CONF_CANCELLABLE = "cancellable"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
    vol.Optional(CONF_ON_FOR, default=TOGGLE_FOR_DEFAULT): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_ALLOW_OFF, default=DEFAULT_CANCELLABLE): cv.boolean,
    vol.Optional(CONF_TOGGLE_FOR, default=TOGGLE_FOR_DEFAULT): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_CANCELLABLE, default=DEFAULT_CANCELLABLE): cv.boolean,
})


async def async_setup_platform(_hass, config, async_add_entities, _discovery_info=None):
    switches = [MomentarySwitch(config)]
    async_add_entities(switches, True)


class MomentarySwitch(SwitchEntity):
    """Representation of a Momentary switch."""

    _mode: str = DEFAULT_MODE
    _cancellable: bool = DEFAULT_CANCELLABLE
    _toggle_for: timedelta = TOGGLE_FOR_DEFAULT
    _idle_state: bool = False
    _timed_state: bool = True

    def __init__(self, config):
        """Initialize the Momentary switch device."""

        # Build name, entity id and unique id. We do this because historically
        # the non-domain piece of the entity_id was prefixed with virtual_ so
        # we build the pieces manually to make sure.
        self._attr_name = config.get(CONF_NAME)
        if self._attr_name.startswith("!"):
            self._attr_name = self._attr_name[1:]
            self.entity_id = f'{DOMAIN}.{slugify(self._attr_name)}'
        else:
            self.entity_id = f'{DOMAIN}.{COMPONENT_DOMAIN}_{slugify(self._attr_name)}'
        self._attr_unique_id = slugify(self._attr_name)

        # Get settings.
        self._mode = config.get(CONF_MODE)
        self._toggle_for = config.get(CONF_ON_FOR)
        self._cancellable = config.get(CONF_ALLOW_OFF)

        # Old configuration - only turns on
        if self._mode.lower() == DEFAULT_MODE:
            _LOGGER.debug(f'old config, idle-state={self._idle_state}')

        # New configuration - can be either turn off or on.
        else:
            if self._mode.lower() != "off":
                self._idle_state = True
                self._timed_state = False
            _LOGGER.debug(f'new config, idle-state={self._idle_state}')

        # Set initial state.
        self._attr_is_on = self._idle_state

        # Set up some attributes.
        self._attr_extra_state_attributes = {
            ATTR_IDLE_STATE: self._idle_state,
            ATTR_TIMED_STATE: self._timed_state,
        }
        if _LOGGER.isEnabledFor(logging.DEBUG):
            self._attr_extra_state_attributes.update({
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_UNIQUE_ID: self.unique_id,
            })

        _LOGGER.info(f'MomentarySwitch: {self.name} created')

    def _stop_activity(self, time_left):
        _LOGGER.debug(f"moving {self.name} out of timed state")
        self._attr_is_on = self._idle_state
        self.async_schedule_update_ha_state()

    def _start_activity(self, on_off):
        """Turn the switch on."""

        # Are we moving to the timed state? If so start a timer to flip it back.
        if self._timed_state == on_off:
            _LOGGER.debug(f"moving {self.name} to timed state")
            self._attr_is_on = self._timed_state
            track_point_in_time(self.hass, self._stop_activity, dt_util.utcnow() + self._toggle_for)

        # Are we cancelling an timed state? And are we allowed. Then turn it
        # back now, the timer can run without causing a problem.
        elif self._cancellable:
            _LOGGER.debug(f"forced {self.name} off")
            self._attr_is_on = self._idle_state

        # Make sure system gets updated.
        self.async_schedule_update_ha_state()

    def turn_on(self, **kwargs):
        self._start_activity(True)

    def turn_off(self, **kwargs):
        self._start_activity(False)
