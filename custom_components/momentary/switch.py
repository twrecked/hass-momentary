"""
This component provides support for a momentary switch.

"""

import logging
import time
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.config_validation import (PLATFORM_SCHEMA)
from homeassistant.helpers.event import track_point_in_time

_LOGGER = logging.getLogger(__name__)

MODE = "old"
CANCELLABLE = False
TOGGLE_FOR_DEFAULT = timedelta(seconds=1)

CONF_NAME = "name"
CONF_MODE = "mode"
CONF_ON_FOR = "on_for"
CONF_ALLOW_OFF = "allow_off"
CONF_TOGGLE_FOR = "toggle_for"
CONF_CANCELLABLE = "cancellable"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MODE, default=MODE): cv.string,
    vol.Optional(CONF_ON_FOR, default=TOGGLE_FOR_DEFAULT): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_ALLOW_OFF, default=CANCELLABLE): cv.boolean,
    vol.Optional(CONF_TOGGLE_FOR, default=TOGGLE_FOR_DEFAULT): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_CANCELLABLE, default=CANCELLABLE): cv.boolean,
})


async def async_setup_platform(_hass, config, async_add_entities, _discovery_info=None):
    switches = [MomentarySwitch(config)]
    async_add_entities(switches, True)


class MomentarySwitch(SwitchEntity):
    """Representation of a Momentary switch."""

    def __init__(self, config):
        """Initialize the Momentary switch device."""
        self._name = config.get(CONF_NAME)

        # Are we adding the domain or not?
        self.no_domain_ = self._name.startswith("!")
        if self.no_domain_:
            self._name = self.name[1:]
        self._unique_id = self._name.lower().replace(' ', '_')

        self._mode = config.get(CONF_MODE)
        self._toggle_until = None

        # Old configuration - only turns on
        if self._mode == "old":
            self._toggle_for = config.get(CONF_ON_FOR)
            self._cancellable = config.get(CONF_ALLOW_OFF)
            self._toggled = "on"
            self._not_toggled = "off"
            _LOGGER.debug('old config, turning on')

        # New configuration - can be either turn off or on.
        else:
            self._toggle_for = config.get(CONF_TOGGLE_FOR)
            self._cancellable = config.get(CONF_CANCELLABLE)
            if self._mode == "True":
                self._toggled = "on"
                self._not_toggled = "off"
            else:
                self._toggled = "off"
                self._not_toggled = "on"
            _LOGGER.debug('new config, turning {}'.format(self._toggled))

        _LOGGER.info('MomentarySwitch: {} created'.format(self._name))

    @property
    def name(self):
        if self.no_domain_:
            return self._name
        else:
            return super().name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the switch."""
        if self._toggle_until is not None:
            if self._toggle_until > time.monotonic():
                return self._toggled
            _LOGGER.debug('turned off')
            self._toggle_until = None
        return self._not_toggled

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.state == "on"

    @property
    def is_off(self):
        """Return true if switch is on."""
        return not self.is_on

    def turn_on(self, **kwargs):
        self._activate("on")

    def turn_off(self, **kwargs):
        self._activate("off")

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {
            'friendly_name': self._name,
            'unique_id': self._unique_id,
        }
        return attrs

    def _activate(self, on_off):
        """Turn the switch on."""
        if self._toggled == on_off:
            self._toggle_until = time.monotonic() + self._toggle_for.total_seconds()
            track_point_in_time(self.hass, self.async_update_ha_state, dt_util.utcnow() + self._toggle_for)
            _LOGGER.debug('turned on')
        elif self._cancellable:
            self._toggle_until = None
            _LOGGER.debug('forced off')
        self.async_schedule_update_ha_state()
