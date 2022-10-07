"""Get data from mehr-tanken website"""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['beautifulsoup4==4.6.3']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by mehr-tanken.de"

CONF_INDEX = "0"

CONF_URL = "https://mehr-tanken.de"

CONF_LOCATION = "Berlin"

CONF_TYPE = "Super E10"

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_INDEX): cv.string,
    vol.Required(CONF_TYPE): cv.string,
    vol.Optional(CONF_LOCATION): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the mehr-tanken fuel prices sensor."""
    name = config.get(CONF_NAME)
    address = config.get(CONF_URL)
    index = config.get(CONF_INDEX)
    typ = config.get(CONF_TYPE)
    location = config.get(CONF_LOCATION)
    session = async_get_clientsession(hass)

    async_add_entities([
        MehrTankenSensor(session, name, address, index, typ, location)], True)


class MehrTankenSensor(Entity):
    """Representation of a mehr-tanken sensor."""

    def __init__(self, session, name, address, index, typ, location):
        """Initialize a mehr-tanken sensor."""
        self._name = name
        self._href = address
        self._index = index
        self._typ = typ
        self._location = location
        self._state = None
        self._session = session
        self._unit_of_measurement = 'EUR/l'
        if(self._location != ''):
            self._attrs["location"] = self._location,
        self._attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION,
        self._attrs["typ"] = self._typ,

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs

    async def async_update(self):
        """Get the latest data from the source and updates the state."""
        from bs4 import BeautifulSoup

        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                response = await self._session.get(self._href)

            _LOGGER.debug(
                "Response from mehr-tanken.de: %s", response.status)
            data = await response.text()
            _LOGGER.debug(data)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Can not load data from mehr-tanken.dev")
            return

        raw_data = BeautifulSoup(data, 'html.parser')

        try:
            value_raw = raw_data.select(
                ".PriceList__fuelList.Card.Card__inset.no-margin-top > a:nth-child(%s) > div > div.col-sm-3 > span" % self._index)[0].text
            value = ''.join(value_raw.split()).split('(')[0]
            refresh_raw = raw_data.select(
                ".PriceList__fuelList.Card.Card__inset.no-margin-top > a:nth-child(%s) > div > div.col-sm-7 > div.PriceList__itemSubtitle" % self._index)[0].text
            self._attrs['last_refresh'] = ''.join(refresh_raw.split()).split('(')[0]
        except IndexError:
            _LOGGER.error("Unable to extract data from HTML")
            return

        self._state = value