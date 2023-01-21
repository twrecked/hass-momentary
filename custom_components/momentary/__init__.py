"""
This component provides support for a momentary switch.

"""

import logging

__version__ = '0.6.3'

_LOGGER = logging.getLogger(__name__)

COMPONENT_DOMAIN = 'momentary'


def setup(_hass, _config):
    """Set up an momentary component."""
    _LOGGER.debug('setup')
    return True
