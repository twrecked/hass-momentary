import uuid
import json
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.util import slugify

from . import COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'momentary'


class MomentaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    def _make_original_unique_id(self, name):
        if name.startswith("!"):
            return slugify(name[1:])
        else:
            return slugify(name)

    def _make_unique_id(self, name):
        return f'{uuid.uuid4()}.momentary'

    def _make_entity_id(self, platform, name):
        if name.startswith("!"):
            return f'{platform}.{slugify(name[1:])}'
        else:
            return f'{platform}.{COMPONENT_DOMAIN}_{slugify(name)}'

    def _make_name(self, name):
        if name.startswith("!"):
            return name[1:]
        return name

    async def async_step_user(self, user_input):
        _LOGGER.debug(f"showing shit {user_input}")

        if user_input is not None:
            return self.async_create_entry(title="momentary", data=user_input)

        _LOGGER.debug(f"showing shit {user_input}")

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({
                vol.Required("device_name"): str,
                vol.Required("duration"): int,
                vol.Required("inverted", default=False): bool,
            })
        )

    async def async_step_import(self, import_data):
        """Import blink config from configuration.yaml."""

        # Extract the momentary devices in the yaml file. We fix up the name
        # so we can not bother with the "!" overrides for entity ID going
        # forward.
        mswitches = {}
        for switch in import_data:
            if switch['platform'] == 'momentary':
                switch.pop('platform', None)
                switch['entity_id'] = self._make_entity_id('switch', switch['name'])
                switch['name'] = self._make_name(switch['name'])
                switch['original_unique_id'] = slugify(switch['name'])
                mswitches[str(uuid.uuid4())] = switch

        # Write out to new json database. This is done to stop them getting
        # too large inside the config_entries structure.
        json_object = json.dumps({
            'version': 1,
            'switches': mswitches}, indent=4)
        with open("/config/m.test", "w") as outfile:
            outfile.write(json_object)

        # Store keys in momentary config.
        return self.async_create_entry(title="momentary", data={
            "switches": list(mswitches.keys())
        })
