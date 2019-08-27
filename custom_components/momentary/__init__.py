"""
This component provides support for a momentary switch.

"""

import logging

__version__ = '0.0.1'

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'momentary'

def setup(hass, config):
    """Set up an momentary component."""
    _LOGGER.debug( 'setup' )
    return True

