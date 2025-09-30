"""Switch platform for the momentary integration.

This module provides the SwitchEntity implementation and platform setup
helpers used by Home Assistant to create momentary switch entities.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HassJob, HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import result_as_boolean
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_IDLE_STATE,
    ATTR_TIMED_STATE,
    ATTR_TOGGLE_UNTIL,
    CONF_CANCELLABLE,
    CONF_DEVICE_ID,
    CONF_ID_TOKEN,
    CONF_MODE,
    CONF_NAME,
    CONF_TOGGLE_FOR,
    DEFAULT_CANCELLABLE,
    DEFAULT_MODE,
    DEFAULT_TOGGLE_FOR,
    DEFAULT_TOGGLE_FOR_TIMEDELTA,
    DEFAULT_TOGGLE_UNTIL,
    DEFAULT_TOGGLE_UNTIL_STR,
    DOMAIN,
)
from .helpers import duration_to_timedelta

_LOGGER = logging.getLogger(__name__)
PLATFORM = Platform.SWITCH
ENTITY_ID_FORMAT = PLATFORM + ".momentary_{}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
        vol.Optional(CONF_TOGGLE_FOR, default=DEFAULT_TOGGLE_FOR): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(CONF_CANCELLABLE, default=DEFAULT_CANCELLABLE): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Process legacy YAML configuration and set up momentary switch entities.

    This function is called by Home Assistant when the platform is set up
    via YAML configuration (legacy). Even though the YAML is actually processed
    from the async_setup function in __init__.py, this function is still needed
    to satisfy Home Assistant's expectations for platform setup.
    """


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up switch entities from a config entry."""

    config = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    unique_id = config_entry.entry_id
    # _LOGGER.debug("[Switch async_setup_entry] config_entry: %s", config_entry.as_dict())
    # _LOGGER.debug("[Switch async_setup_entry] config: %s", config)
    # _LOGGER.debug("[Switch async_setup_entry] unique_id: %s", unique_id)

    async_add_entities([MomentarySwitch(hass=hass, unique_id=unique_id, config=config)])

    return True


class MomentarySwitch(RestoreEntity, SwitchEntity):
    """Representation of a Momentary switch.

    This entity implements a momentary switch that can be turned on for a
    short period of time and optionally cancelled. The class uses RestoreEntity
    to persist the toggle_until timestamp across restarts.
    """

    def __init__(self, hass: HomeAssistant, unique_id: str, config: dict[str, Any]) -> None:
        """Initialize the Momentary switch device.

        Parameters
        ----------
        hass: HomeAssistant
            The Home Assistant instance.
        unique_id: Optional[str]
            The integration-unique id for this switch (or None for old YAML).
        config: dict
            The configuration dictionary for the switch.

        """
        _LOGGER.debug("[Momentary Switch] config: %s", config)

        # Get settings.
        self._mode: bool = result_as_boolean(config.get(CONF_MODE, DEFAULT_MODE))
        self._toggle_for: timedelta = duration_to_timedelta(
            config.get(CONF_TOGGLE_FOR, DEFAULT_TOGGLE_FOR), DEFAULT_TOGGLE_FOR_TIMEDELTA
        )
        self._cancellable: bool = config.get(CONF_CANCELLABLE, DEFAULT_CANCELLABLE)

        # Local defaults
        self._toggle_until: datetime = DEFAULT_TOGGLE_UNTIL

        self._attr_name = config.get(CONF_NAME)
        self._attr_unique_id = unique_id
        registry = er.async_get(hass)
        current_entity_id = registry.async_get_entity_id(PLATFORM, DOMAIN, self._attr_unique_id)
        if current_entity_id is not None:
            self.entity_id = current_entity_id
        else:
            self.entity_id = generate_entity_id(
                ENTITY_ID_FORMAT, config.get(CONF_ID_TOKEN), hass=hass
            )

        device_id = config.get(CONF_DEVICE_ID)
        if device_id:
            self._attr_device_info = async_device_info_to_link_from_device_id(
                hass=hass, device_id=device_id
            )
        # else:
        #     self._attr_device_info = DeviceInfo(
        #         name=str(self.name),
        #         identifiers={(DOMAIN, unique_id)},
        #         model=str(self.name),
        #         manufacturer="Momentary Switch",
        #         sw_version=VERSION,
        #     )

        _LOGGER.info("[Momentary Switch] Created: %s (%s)", self.name, self.entity_id)

        self._timer: Callable | None = None
        self._timed_state: bool = self._mode
        self._idle_state: bool = not self._mode

        _LOGGER.debug(
            "[Momentary Switch] Mode: %s, Timed State: %s, Idle State: %s, Toggle Duration: %s, Cancellable: %s",
            self._mode,
            self._timed_state,
            self._idle_state,
            self._toggle_for,
            self._cancellable,
        )

    def _create_state(self) -> None:
        # _LOGGER.info("[create_state] unique_id: %s", self.unique_id)
        self._attr_is_on = self._idle_state
        self._toggle_until = DEFAULT_TOGGLE_UNTIL

    def _restore_state(self, state: State) -> None:
        # _LOGGER.info("[restore_state] unique_id: %s", self.unique_id)
        # _LOGGER.debug("[restore_state] attributes: %s", state.attributes)
        try:
            self._toggle_until = datetime.fromisoformat(
                state.attributes.get(ATTR_TOGGLE_UNTIL, DEFAULT_TOGGLE_UNTIL_STR)
            )
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid toggle_until datetime, using default")
            self._toggle_until = DEFAULT_TOGGLE_UNTIL
        if self._toggle_until > dt_util.utcnow():
            _LOGGER.debug("[restore_state] %s: Restoring to timed state", self.name)
            self._attr_is_on = self._timed_state
            self._timer = async_track_point_in_time(
                self.hass, HassJob(self._async_stop_activity), self._toggle_until
            )
        else:
            _LOGGER.debug("[restore_state] %s: Restoring to idle state", self.name)
            self._attr_is_on = self._idle_state

    def _update_attributes(self) -> None:
        # Set up some attributes.
        self._attr_extra_state_attributes = {
            ATTR_IDLE_STATE: "On" if self._idle_state else "Off",
            ATTR_TIMED_STATE: "On" if self._timed_state else "Off",
            CONF_CANCELLABLE: self._cancellable,
            CONF_TOGGLE_FOR: str(self._toggle_for),
        }
        if self._attr_is_on == self._timed_state:
            self._attr_extra_state_attributes[ATTR_TOGGLE_UNTIL] = datetime.isoformat(
                self._toggle_until
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
                _LOGGER.debug("[async_stop_activity] %s: Moving out of timed state", self.name)
                self._attr_is_on = self._idle_state
                self._toggle_until = DEFAULT_TOGGLE_UNTIL
                # Cancel any existing scheduled timer
                if self._timer is not None:
                    try:
                        self._timer()
                    except (
                        TypeError,
                        RuntimeError,
                    ):
                        _LOGGER.debug(
                            "[async_stop_activity] %s: existing timer cancellation raised",
                            self.name,
                        )
                self._timer = None
                self._update_attributes()
                self.async_schedule_update_ha_state()
            else:
                _LOGGER.debug("[async_stop_activity] %s: Too soon, restarting timer", self.name)
                # Cancel any previously scheduled timer before scheduling a new one
                if self._timer is not None:
                    try:
                        self._timer()
                    except (TypeError, RuntimeError):
                        _LOGGER.debug(
                            "[async_stop_activity] %s: existing timer cancellation raised",
                            self.name,
                        )
                self._timer = async_track_point_in_time(
                    self.hass, HassJob(self._async_stop_activity), self._toggle_until
                )
        else:
            _LOGGER.debug("[async_stop_activity] %s: Already idle", self.name)

    def _start_activity(self, new_state: bool) -> None:
        """Change the switch state.

        If moving to timed then restart the timer, new toggle_until will be used.
        If moving from timed, then clear out the _toggle_until value.
        """
        # Are we moving to the timed state? If so start a timer to flip it back.
        if self._timed_state == new_state:
            _LOGGER.debug("[start_activity] %s: (Re)moving to timed state", self.name)
            self._attr_is_on = self._timed_state
            self._toggle_until = dt_util.utcnow() + self._toggle_for
            if self._timer is not None:
                try:
                    self._timer()
                except (TypeError, RuntimeError):
                    _LOGGER.debug(
                        "[start_activity] %s: previous timer cancellation raised",
                        self.name,
                    )
            self._timer = async_track_point_in_time(
                self.hass, HassJob(self._async_stop_activity), self._toggle_until
            )

        # Are we cancelling an timed state? And are we allowed. Then turn it
        # back now, the timer can run without causing a problem.
        elif self._cancellable:
            _LOGGER.debug("[start_activity] %s: Cancelling timed state", self.name)
            if self._timer is not None:
                try:
                    self._timer()
                except (TypeError, RuntimeError) as e:
                    _LOGGER.debug("Timer cancellation error (likely already fired): %s", e)
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
