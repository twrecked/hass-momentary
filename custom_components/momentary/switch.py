"""
This component provides support for a momentary switch.
"""

import logging
import pprint
import voluptuous as vol
from datetime import datetime
from typing import Any
from collections.abc import Callable

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.switch import (
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HassJob
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import HomeAssistantType

from .const import *


_LOGGER = logging.getLogger(__name__)

DEFAULT_TOGGLE_UNTIL_STR = "1970-01-01T00:00:00+00:00"
DEFAULT_TOGGLE_UNTIL = datetime.fromisoformat(DEFAULT_TOGGLE_UNTIL_STR)

BASE_SCHEMA = {
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
    vol.Optional(CONF_TOGGLE_FOR, default=DEFAULT_TOGGLE_FOR): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_CANCELLABLE, default=DEFAULT_CANCELLABLE): cv.boolean,
    vol.Optional(ATTR_ENTITY_ID, default=""): cv.string,
    vol.Optional(ATTR_DEVICE_ID, default=""): cv.string,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BASE_SCHEMA)

SWITCH_SCHEMA = vol.Schema(BASE_SCHEMA)


async def async_setup_entry(
        hass: HomeAssistantType,
        entry: ConfigEntry,
        async_add_entities: Callable[[list], None],
) -> None:
    _LOGGER.debug("setting up the entries...")

    # create entities
    entities = []
    for switch, values in hass.data[COMPONENT_DOMAIN][entry.data[ATTR_GROUP_NAME]][ATTR_SWITCHES].items():
        values = SWITCH_SCHEMA(values)
        _LOGGER.debug(f"would try to add switch {switch}/{values}")
        entities.append(MomentarySwitch(switch, values, hass))

    async_add_entities(entities)


class MomentarySwitch(RestoreEntity, SwitchEntity):
    """Representation of a Momentary switch."""

    def __init__(self, unique_id, config, hass):
        """Initialize the Momentary switch device."""

        _LOGGER.debug(f'{config}')
        self._hass = hass

        # Get settings.
        self._mode = config.get(CONF_MODE, DEFAULT_MODE)
        self._toggle_for = config.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR)
        self._cancellable = config.get(CONF_CANCELLABLE, DEFAULT_CANCELLABLE)

        # Local defaults
        self._toggle_until = DEFAULT_TOGGLE_UNTIL
        self._idle_state = False
        self._timed_state = True
        self._timer = None

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

        # Home Assistant stuff.
        self.entity_id = config[ATTR_ENTITY_ID]
        self._attr_name = config.get(CONF_NAME)
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(COMPONENT_DOMAIN, config[ATTR_DEVICE_ID])},
            manufacturer=COMPONENT_MANUFACTURER,
            model=COMPONENT_MODEL,
        )

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
            self._timer = async_track_point_in_time(
                self.hass,
                HassJob(
                    self._async_stop_activity
                ),
                self._toggle_until
            )
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
                self._timer = None
                self._update_attributes()
                self.async_schedule_update_ha_state()
            else:
                _LOGGER.debug(f"too soon, restarting {self.name} timer")
                self._timer = async_track_point_in_time(
                    self.hass,
                    HassJob(
                        self._async_stop_activity
                    ),
                    self._toggle_until
                )
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
            self._timer = async_track_point_in_time(
                self.hass,
                HassJob(
                    self._async_stop_activity
                ),
                self._toggle_until
            )

        # Are we cancelling an timed state? And are we allowed. Then turn it
        # back now, the timer can run without causing a problem.
        elif self._cancellable:
            _LOGGER.debug(f"cancelling timed state for {self.name}")
            if self._timer is not None:
                self._timer()
            self._attr_is_on = self._idle_state
            self._toggle_until = DEFAULT_TOGGLE_UNTIL
            self._timer = None

        # Make sure system gets updated.
        self._update_attributes()
        self.async_schedule_update_ha_state()

    def turn_on(self, **kwargs):
        self._start_activity(True)

    def turn_off(self, **kwargs):
        self._start_activity(False)
