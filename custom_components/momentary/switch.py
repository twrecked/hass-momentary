"""Switch platform for the momentary integration.

This module provides the SwitchEntity implementation and platform setup
helpers used by Home Assistant to create momentary switch entities.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as PLATFORM_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State, callback
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
    if hass.data.get(COMPONENT_CONFIG, {}).get(CONF_YAML_CONFIG, False):
        _LOGGER.debug("setting up old config...")

        switches = [MomentarySwitch(None, config)]
        async_add_entities(switches, True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    _LOGGER.debug("setting up the entries...")

    # create entities
    entities: list[MomentarySwitch] = []
    group_data = hass.data.get(COMPONENT_DOMAIN, {}).get(entry.data[ATTR_GROUP_NAME], {})
    switches_dict = group_data.get(ATTR_SWITCHES, {})
    for switch, values in switches_dict.items():
        validated_values = SWITCH_SCHEMA(values)
        _LOGGER.debug("would try to add switch %s/%s", switch, validated_values)
        entities.append(MomentarySwitch(switch, validated_values))

    async_add_entities(entities)


class MomentarySwitch(RestoreEntity, SwitchEntity):
    """Representation of a Momentary switch.

    This entity implements a momentary switch that can be turned on for a
    short period of time and optionally cancelled. The class uses RestoreEntity
    to persist the toggle_until timestamp across restarts.
    """

    _attr_should_poll = False

    def __init__(self, unique_id: str | None, config: dict[str, Any]) -> None:
        """Initialize the Momentary switch device.

        Parameters
        ----------
        unique_id: str | None
            The integration-unique id for this switch (or None for old YAML).
        config: dict[str, Any]
            The configuration dictionary for the switch.

        """
        _LOGGER.debug("%s", config)

        # Get settings.
        self._mode = str(config.get(CONF_MODE, DEFAULT_MODE))
        self._toggle_for = config.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR)
        self._cancellable = bool(config.get(CONF_CANCELLABLE, DEFAULT_CANCELLABLE))

        # Local defaults
        self._toggle_until: datetime = DEFAULT_TOGGLE_UNTIL
        self._idle_state: bool = False
        self._timed_state: bool = True
        self._timer: Callable[[], None] | None = None

        # Determine states based on mode
        if self._mode.lower() not in [DEFAULT_MODE, "on", "true"]:
            if self._mode.lower() in ["off", "false"]:
                self._idle_state = True
                self._timed_state = False
            _LOGGER.debug("configured idle-state=%s for %s", self._idle_state, self._mode)
        else:
            _LOGGER.debug("default idle-state=%s for %s", self._idle_state, self._mode)

        if unique_id is None:
            # Old style yaml config.
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
        raw_until = state.attributes.get(ATTR_TOGGLE_UNTIL)
        parsed_until: datetime | None = None

        if raw_until is not None:
            if isinstance(raw_until, datetime):
                parsed_until = raw_until
            elif isinstance(raw_until, str):
                try:
                    parsed_until = dt_util.parse_datetime(raw_until)
                except (ValueError, TypeError):
                    parsed_until = None

        if parsed_until is not None:
            if parsed_until.tzinfo is None:
                parsed_until = parsed_until.replace(tzinfo=UTC)
            self._toggle_until = parsed_until
        else:
            self._toggle_until = DEFAULT_TOGGLE_UNTIL

        now = dt_util.utcnow()
        if self._toggle_until > now:
            _LOGGER.debug("restoring %s to timed state until %s", self.name, self._toggle_until)
            self._attr_is_on = self._timed_state
            self._timer = async_track_point_in_time(
                self.hass, self._handle_timer_expired, self._toggle_until
            )
        else:
            _LOGGER.debug("restoring %s to idle state", self.name)
            self._attr_is_on = self._idle_state
            self._toggle_until = DEFAULT_TOGGLE_UNTIL

    def _update_attributes(self) -> None:
        self._attr_extra_state_attributes = {
            ATTR_IDLE_STATE: self._idle_state,
            ATTR_TIMED_STATE: self._timed_state,
            ATTR_TOGGLE_UNTIL: self._toggle_until.isoformat(),
        }

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

    async def async_will_remove_from_hass(self) -> None:
        """Clean up resources when entity is being removed from Home Assistant."""
        if self._timer is not None:
            self._timer()
            self._timer = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_timer_expired(self, _now: datetime) -> None:
        """Turn the switch to idle state when countdown expires."""
        self._timer = None
        if self._attr_is_on == self._timed_state:
            now = dt_util.utcnow()
            if now >= self._toggle_until:
                _LOGGER.debug("moving %s out of timed state", self.name)
                self._attr_is_on = self._idle_state
                self._toggle_until = DEFAULT_TOGGLE_UNTIL
                self._update_attributes()
                self.async_write_ha_state()
            else:
                _LOGGER.debug("too soon, restarting %s timer", self.name)
                self._timer = async_track_point_in_time(
                    self.hass, self._handle_timer_expired, self._toggle_until
                )
        else:
            _LOGGER.debug("%s already idle", self.name)

    @callback
    def _start_activity(self, new_state: bool) -> None:
        """Change the switch state on the event loop.

        If moving to timed then restart the timer, new toggle_until will be used.
        If moving from timed, then clear out the _toggle_until value.
        """
        # Are we moving to the timed state? If so start a timer to flip it back.
        if self._timed_state == new_state:
            _LOGGER.debug("(re)moving %s to timed state", self.name)
            # Cancel existing timer callback before assigning a new one
            if self._timer is not None:
                self._timer()
                self._timer = None

            self._attr_is_on = self._timed_state
            self._toggle_until = dt_util.utcnow() + self._toggle_for
            self._timer = async_track_point_in_time(
                self.hass, self._handle_timer_expired, self._toggle_until
            )

        # Are we cancelling a timed state? And are we allowed.
        elif self._cancellable:
            _LOGGER.debug("cancelling timed state for %s", self.name)
            if self._timer is not None:
                self._timer()
                self._timer = None
            self._attr_is_on = self._idle_state
            self._toggle_until = DEFAULT_TOGGLE_UNTIL

        # Make sure system gets updated immediately on the event loop
        self._update_attributes()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the momentary switch on.

        This triggers the momentary timed state, or sets the entity
        to on depending on configuration.
        """
        self._start_activity(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the momentary switch off.

        This cancels a timed state if cancellable, or sets the entity to off
        depending on configuration.
        """
        self._start_activity(False)
