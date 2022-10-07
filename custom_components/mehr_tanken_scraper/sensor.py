"""Get data from mehr-tanken website"""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CONF_URL, CONF_LOCATION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['beautifulsoup4==4.6.3']

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION_DEFAULT = ''
CONF_PETROL_NAME = 'petrol_name'
CONF_PETROL_NUMBER = 'petrol_number'
CONF_PETROL_NUMBER_DEFAULT = 0

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_URL): cv.url,
    vol.Required(CONF_PETROL_NUMBER, default=CONF_PETROL_NUMBER_DEFAULT): cv.positive_int,
    vol.Required(CONF_PETROL_NAME): cv.string,
    vol.Optional(CONF_LOCATION, default=CONF_LOCATION_DEFAULT): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the mehr-tanken fuel prices sensor."""
    name = config.get(CONF_NAME)
    address = config.get(CONF_URL)
    petrol_number = config.get(CONF_PETROL_NUMBER)
    petrol_name = config.get(CONF_PETROL_NAME)
    location = config.get(CONF_LOCATION)
    session = async_get_clientsession(hass)

    async_add_entities([
        MehrTankenSensor(session, name, address, petrol_number, petrol_name, location)], True)


class MehrTankenSensor(Entity):
    """Representation of a mehr-tanken sensor."""

    def __init__(self, session, name, address, petrol_number, petrol_name, location):
        """Initialize a mehr-tanken sensor."""
        self._name = name
        self._href = address
        self._petrol_number = petrol_number
        self._petrol_name = petrol_name
        self._state = None
        self._session = session
        self._unit_of_measurement = 'EUR/l'
        self._location = location

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
        attrs = {CONF_PETROL_NAME: self._petrol_name, CONF_LOCATION: self._location}
        attrs.update(super().extra_state_attributes)
        return attrs

    async def async_update(self):
        """Get the latest data from the source and updates the state."""
        from bs4 import BeautifulSoup

        try:
            with async_timeout.timeout(10):
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
                ".PriceList__fuelList.Card.Card__inset.no-margin-top > a:nth-child(%s) > div > div.col-sm-3 > span" % self._petrol_number)[0].text
            value = ''.join(value_raw.split()).split('(')[0]
            refresh_raw = raw_data.select(
                ".PriceList__fuelList.Card.Card__inset.no-margin-top > a:nth-child(%s) > div > div.col-sm-7 > div.PriceList__itemSubtitle" % self._petrol_number)[0].text
            self._attrs['last_refresh'] = ''.join(refresh_raw.split()).split('(')[0]
        except IndexError:
            _LOGGER.error("Unable to extract data from HTML")
            return

        self._state = value