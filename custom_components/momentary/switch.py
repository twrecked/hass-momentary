"""
This component provides support for a momentary switch.

"""

import logging
import pprint
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.switch import SwitchEntity, DOMAIN
from homeassistant.helpers.config_validation import (PLATFORM_SCHEMA)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from . import COMPONENT_DOMAIN


_LOGGER = logging.getLogger(__name__)

DEFAULT_MODE = "old"
DEFAULT_CANCELLABLE = False
TOGGLE_FOR_DEFAULT = timedelta(seconds=1)
DEFAULT_TOGGLE_UNTIL_STR = "1970-01-01T00:00:00+00:00"
DEFAULT_TOGGLE_UNTIL = datetime.fromisoformat(DEFAULT_TOGGLE_UNTIL_STR)

ATTR_IDLE_STATE = 'idle_state'
ATTR_TIMED_STATE = 'timed_state'
ATTR_TOGGLE_UNTIL = 'toggle_until'
ATTR_UNIQUE_ID = 'unique_id'

CONF_NAME = "name"
CONF_MODE = "mode"
CONF_TOGGLE_FOR = "toggle_for"
CONF_CANCELLABLE = "cancellable"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
    vol.Optional(CONF_TOGGLE_FOR, default=TOGGLE_FOR_DEFAULT): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_CANCELLABLE, default=DEFAULT_CANCELLABLE): cv.boolean,
})


async def async_setup_platform(_hass, config, async_add_entities, _discovery_info=None):
    switches = [MomentarySwitch(config)]
    async_add_entities(switches, True)


class MomentarySwitch(RestoreEntity, SwitchEntity):
    """Representation of a Momentary switch."""

    _mode: str = DEFAULT_MODE
    _cancellable: bool = DEFAULT_CANCELLABLE
    _toggle_for: timedelta = TOGGLE_FOR_DEFAULT
    _toggle_until: datetime = DEFAULT_TOGGLE_UNTIL
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
        self._toggle_for = config.get(CONF_TOGGLE_FOR)
        self._cancellable = config.get(CONF_CANCELLABLE)

        # Old configuration - only turns on
        if self._mode.lower() == DEFAULT_MODE:
            _LOGGER.debug(f'old config, idle-state={self._idle_state}')

        # New configuration - can be either turn off or on. Base on or off are
        # converted to True and False. We need to handle those.
        else:
            if self._mode.lower() in ['off', 'false']:
                self._idle_state = True
                self._timed_state = False
            _LOGGER.debug(f'new config, idle-state={self._idle_state}')

        _LOGGER.info(f'MomentarySwitch: {self.name} created')

    def _create_state(self):
        _LOGGER.info(f'Momentary {self.unique_id}: creating initial state')
        self._attr_is_on = self._idle_state
        self._toggle_until = DEFAULT_TOGGLE_UNTIL

    def _restore_state(self, state):
        _LOGGER.info(f'Momentary {self.unique_id}: restoring state')
        _LOGGER.debug(f'Momentary:: {pprint.pformat(state.attributes)}')
        self._toggle_until = datetime.fromisoformat(state.attributes.get(ATTR_TOGGLE_UNTIL, DEFAULT_TOGGLE_UNTIL_STR))
        if self._toggle_until > dt_util.utcnow():
            _LOGGER.debug(f"restoring {self.name} to timed state")
            self._attr_is_on = self._timed_state
            async_track_point_in_time(self.hass, self._async_stop_activity, self._toggle_until)
        else:
            _LOGGER.debug(f"restoring {self.name} to off state")
            self._attr_is_on = self._idle_state

    def _update_attributes(self):
        # Set up some attributes.
        self._attr_extra_state_attributes = {
            ATTR_IDLE_STATE: self._idle_state,
            ATTR_TIMED_STATE: self._timed_state,
            ATTR_TOGGLE_UNTIL: self._toggle_until,
        }
        if _LOGGER.isEnabledFor(logging.DEBUG):
            self._attr_extra_state_attributes.update({
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_UNIQUE_ID: self.unique_id,
            })

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            self._create_state()
        else:
            self._restore_state(state)
        self._update_attributes()

    async def _async_stop_activity(self, *_args: Any) -> None:
        """ Turn the switch to idle state.
        Before doing that make sure:
         - it's not idle already
         - we're past the toggle time
        """
        if self._attr_is_on == self._timed_state:
            if dt_util.utcnow() >= self._toggle_until:
                _LOGGER.debug(f"moving {self.name} out of timed state")
                self._attr_is_on = self._idle_state
                self._toggle_until = DEFAULT_TOGGLE_UNTIL
                self._update_attributes()
                self.async_schedule_update_ha_state()
            else:
                _LOGGER.debug(f"too soon, restarting {self.name} timer")
                async_track_point_in_time(self.hass, self._async_stop_activity, self._toggle_until)
        else:
            _LOGGER.debug(f"{self.name} already idle")

    def _start_activity(self, new_state):
        """Change the switch state.
        If moving to timed then restart the timer, new toggle_until will be used.
        If moving from timed, then clear out the _toggle_until value.
        """
        # Are we moving to the timed state? If so start a timer to flip it back.
        if self._timed_state == new_state:
            _LOGGER.debug(f"(re)moving {self.name} to timed state")
            self._attr_is_on = self._timed_state
            self._toggle_until = dt_util.utcnow() + self._toggle_for
            async_track_point_in_time(self.hass, self._async_stop_activity, self._toggle_until)

        # Are we cancelling an timed state? And are we allowed. Then turn it
        # back now, the timer can run without causing a problem.
        elif self._cancellable:
            _LOGGER.debug(f"cancelling timed state for {self.name}")
            self._attr_is_on = self._idle_state
            self._toggle_until = DEFAULT_TOGGLE_UNTIL

        # Make sure system gets updated.
        self._update_attributes()
        self.async_schedule_update_ha_state()

    def turn_on(self, **kwargs):
        self._start_activity(True)

    def turn_off(self, **kwargs):
        self._start_activity(False)
