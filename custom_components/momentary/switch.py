"""Switch platform for the momentary integration.

This module provides the SwitchEntity implementation and platform setup
helpers used by Home Assistant to create momentary switch entities.
"""

from collections.abc import Callable
from datetime import datetime
import logging
import pprint
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as PLATFORM_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HassJob, HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_DEVICE_ID,
    ATTR_GROUP_NAME,
    ATTR_IDLE_STATE,
    ATTR_SWITCHES,
    ATTR_TIMED_STATE,
    ATTR_TOGGLE_UNTIL,
    ATTR_UNIQUE_ID,
    COMPONENT_CONFIG,
    COMPONENT_DOMAIN,
    COMPONENT_MANUFACTURER,
    COMPONENT_MODEL,
    CONF_CANCELLABLE,
    CONF_MODE,
    CONF_NAME,
    CONF_TOGGLE_FOR,
    CONF_YAML_CONFIG,
    DEFAULT_CANCELLABLE,
    DEFAULT_MODE,
    DEFAULT_TOGGLE_FOR,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TOGGLE_UNTIL_STR = "1970-01-01T00:00:00+00:00"
DEFAULT_TOGGLE_UNTIL = datetime.fromisoformat(DEFAULT_TOGGLE_UNTIL_STR)

BASE_SCHEMA = {
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
    vol.Optional(CONF_TOGGLE_FOR, default=DEFAULT_TOGGLE_FOR): vol.All(
        cv.time_period, cv.positive_timedelta
    ),
    vol.Optional(CONF_CANCELLABLE, default=DEFAULT_CANCELLABLE): cv.boolean,
    vol.Optional(ATTR_ENTITY_ID, default=""): cv.string,
    vol.Optional(ATTR_DEVICE_ID, default=""): cv.string,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BASE_SCHEMA)

SWITCH_SCHEMA = vol.Schema(BASE_SCHEMA)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the old-style (YAML) platform.

    This is only used when YAML support is enabled for the integration.
    """
    if hass.data[COMPONENT_CONFIG].get(CONF_YAML_CONFIG, False):
        _LOGGER.debug("setting up old config...")

        switches = [MomentarySwitch(None, config)]
        async_add_entities(switches, True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> None:
    """Set up switch entities from a config entry."""
    _LOGGER.debug("setting up the entries...")

    # create entities
    entities = []
    for switch, values in hass.data[COMPONENT_DOMAIN][entry.data[ATTR_GROUP_NAME]][
        ATTR_SWITCHES
    ].items():
        values = SWITCH_SCHEMA(values)
        _LOGGER.debug("would try to add switch %s/%s", switch, values)
        entities.append(MomentarySwitch(switch, values))

    async_add_entities(entities)


class MomentarySwitch(RestoreEntity, SwitchEntity):
    """Representation of a Momentary switch.

    This entity implements a momentary switch that can be turned on for a
    short period of time and optionally cancelled. The class uses RestoreEntity
    to persist the toggle_until timestamp across restarts.
    """

    def __init__(self, unique_id: str | None, config: dict[str, Any]) -> None:
        """Initialize the Momentary switch device.

        Parameters
        ----------
        unique_id: Optional[str]
            The integration-unique id for this switch (or None for old YAML).
        config: dict
            The configuration dictionary for the switch.

        """
        _LOGGER.debug("%s", config)

        # Get settings.
        self._mode = config.get(CONF_MODE, DEFAULT_MODE)
        self._toggle_for = config.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR)
        self._cancellable = config.get(CONF_CANCELLABLE, DEFAULT_CANCELLABLE)

        # Local defaults
        self._toggle_until = DEFAULT_TOGGLE_UNTIL
        self._idle_state = False
        self._timed_state = True
        self._timer: Callable | None = None

        # Old configuration - only turns on
        if self._mode.lower() == DEFAULT_MODE:
            _LOGGER.debug("old config, idle-state=%s", self._idle_state)

        # New configuration - can be either turn off or on. Base on or off are
        # converted to True and False. We need to handle those.
        else:
            if self._mode.lower() in ["off", "false"]:
                self._idle_state = True
                self._timed_state = False
            _LOGGER.debug("new config, idle-state=%s", self._idle_state)

        if unique_id is None:
            # Old style yaml config.
            # Build name, entity id and unique id. We do this because historically
            # the non-domain piece of the entity_id was prefixed with virtual_ so
            # we build the pieces manually to make sure.
            self._attr_name = config.get(CONF_NAME, "")
            if self._attr_name.startswith("!"):
                self._attr_name = self._attr_name[1:]
                self.entity_id = f"{PLATFORM_DOMAIN}.{slugify(self._attr_name)}"
            else:
                self.entity_id = f"{PLATFORM_DOMAIN}.{COMPONENT_DOMAIN}_{slugify(self._attr_name)}"
            self._attr_unique_id = slugify(self._attr_name)

        else:
            # New style integration config.
            self.entity_id = config[ATTR_ENTITY_ID]
            self._attr_name = config.get(CONF_NAME)
            self._attr_unique_id = unique_id
            self._attr_device_info = DeviceInfo(
                identifiers={(COMPONENT_DOMAIN, config[ATTR_DEVICE_ID])},
                manufacturer=COMPONENT_MANUFACTURER,
                model=COMPONENT_MODEL,
            )

        _LOGGER.info("MomentarySwitch: %s created", self._attr_name)

    def _create_state(self) -> None:
        _LOGGER.info("Momentary %s: creating initial state", self.unique_id)
        self._attr_is_on = self._idle_state
        self._toggle_until = DEFAULT_TOGGLE_UNTIL

    def _restore_state(self, state: State) -> None:
        _LOGGER.info("Momentary %s: restoring state", self.unique_id)
        _LOGGER.debug("Momentary:: %s", pprint.pformat(state.attributes))
        self._toggle_until = datetime.fromisoformat(
            state.attributes.get(ATTR_TOGGLE_UNTIL, DEFAULT_TOGGLE_UNTIL_STR)
        )
        if self._toggle_until > dt_util.utcnow():
            _LOGGER.debug("restoring %s to timed state", self.name)
            self._attr_is_on = self._timed_state
            self._timer = async_track_point_in_time(
                self.hass, HassJob(self._async_stop_activity), self._toggle_until
            )
        else:
            _LOGGER.debug("restoring %s to off state", self.name)
            self._attr_is_on = self._idle_state

    def _update_attributes(self) -> None:
        # Set up some attributes.
        self._attr_extra_state_attributes = {
            ATTR_IDLE_STATE: self._idle_state,
            ATTR_TIMED_STATE: self._timed_state,
            ATTR_TOGGLE_UNTIL: self._toggle_until,
        }
        if _LOGGER.isEnabledFor(logging.DEBUG):
            self._attr_extra_state_attributes.update(
                {
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_UNIQUE_ID: self.unique_id,
                }
            )

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant.

        Restore previous state if available, otherwise create initial state.
        """
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            self._create_state()
        else:
            self._restore_state(state)
        self._update_attributes()

    @callback
    async def _async_stop_activity(self, *_args: Any) -> None:
        """Turn the switch to idle state.

        Before doing that make sure:
         - it's not idle already
         - we're past the toggle time
        """
        if self._attr_is_on == self._timed_state:
            if dt_util.utcnow() >= self._toggle_until:
                _LOGGER.debug("moving %s out of timed state", self.name)
                self._attr_is_on = self._idle_state
                self._toggle_until = DEFAULT_TOGGLE_UNTIL
                self._timer = None
                self._update_attributes()
                self.async_schedule_update_ha_state()
            else:
                _LOGGER.debug("too soon, restarting %s timer", self.name)
                self._timer = async_track_point_in_time(
                    self.hass, HassJob(self._async_stop_activity), self._toggle_until
                )
        else:
            _LOGGER.debug("%s already idle", self.name)

    def _start_activity(self, new_state: bool) -> None:
        """Change the switch state.

        If moving to timed then restart the timer, new toggle_until will be used.
        If moving from timed, then clear out the _toggle_until value.
        """
        # Are we moving to the timed state? If so start a timer to flip it back.
        if self._timed_state == new_state:
            _LOGGER.debug("(re)moving %s to timed state", self.name)
            self._attr_is_on = self._timed_state
            self._toggle_until = dt_util.utcnow() + self._toggle_for
            self._timer = async_track_point_in_time(
                self.hass, HassJob(self._async_stop_activity), self._toggle_until
            )

        # Are we cancelling an timed state? And are we allowed. Then turn it
        # back now, the timer can run without causing a problem.
        elif self._cancellable:
            _LOGGER.debug("cancelling timed state for %s", self.name)
            if self._timer is not None:
                self._timer()
            self._attr_is_on = self._idle_state
            self._toggle_until = DEFAULT_TOGGLE_UNTIL
            self._timer = None

        # Make sure system gets updated.
        self._update_attributes()
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the momentary switch on.

        This triggers the momentary timed state, or simply sets the entity
        to the on/idle state depending on configuration.
        """
        self._start_activity(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the momentary switch off.

        This cancels a timed state if cancellable, or sets the entity to the
        configured idle state.
        """
        self._start_activity(False)
