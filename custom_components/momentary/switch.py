"""
This component provides support for a momentary switch.

"""

import logging
import time
import pprint
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.config_validation import (PLATFORM_SCHEMA)
from homeassistant.helpers.event import track_point_in_time

from . import ( DOMAIN )

_LOGGER = logging.getLogger(__name__)

CONF_NAME = "name"
CONF_ON_FOR = "on_for"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required( CONF_NAME ): cv.string,
    vol.Required( CONF_ON_FOR ): vol.All(cv.time_period, cv.positive_timedelta),
})

async def async_setup_platform(hass, config, async_add_entities, _discovery_info=None):
    switches = []
    switches.append( MomentarySwitch( config ) )
    async_add_entities(switches, True)


class MomentarySwitch(SwitchDevice):
    """Representation of a Momentary switch."""

    def __init__(self, config ):
        """Initialize the Momentary switch device."""
        self._name = config.get( CONF_NAME )
        self._unique_id = self._name.lower().replace(' ', '_')
        self._on_for = config.get( CONF_ON_FOR )
        self._on_until = None
        _LOGGER.info('MomentarySwitch: {} created'.format(self._name))

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the switch."""
        if self._on_until is not None:
            if self._on_until > time.monotonic():
                return "on"
            _LOGGER.debug( 'turned off' )
            self._on_until = None
        return "off"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._on_until = time.monotonic() + self._on_for.total_seconds()
        self.async_schedule_update_ha_state()
        track_point_in_time(self.hass, self.async_update_ha_state, dt_util.utcnow() + self._on_for)
        _LOGGER.debug( 'turned on' )

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        pass

