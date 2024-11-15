"""Get data from mehr-tanken website"""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION, CONF_LOCATION, CONF_NAME,
                                 CONF_URL)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
        self._last_refresh = ''
        self._session = session
        self._unit_of_measurement = 'EUR/l'
        self._location = location

    @property
    def friendly_name(self):
        """Return the friendly_name of the sensor."""
        return self._name.replace('_', ' ')

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        name = 'mehr_tanken_' + self._name + '_' + self._petrol_name
        return name.replace(' ', '_')

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attrs = super().extra_state_attributes
        
        if self._state:
            if attrs is None:
                attrs = {}

            attrs[CONF_PETROL_NAME] = self._petrol_name
            attrs[CONF_LOCATION] = self._location
            attrs['last_refresh'] = self._last_refresh
            attrs['gas_station'] = self._name
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
            _LOGGER.error("Can not load data from mehr-tanken.de")
            return

        raw_data = BeautifulSoup(data, 'html.parser')

        try:
            value_raw = raw_data.select("#maincol_article > div.va-maincol.lg\:w-maincol.px-4.lg\:px-0.mb-9 > div.borer-skin-grey-medium.mb-4.border-t.border-solid.detailServiceStation_border__w8k48 > div:nth-child(" + str(
                self._petrol_number) + ") > div.flex.flex-col.justify-between.space-y-4.gasStationInfo_gas-price__ZW1gM > div.relative.font-skin-primary.text-3xl.text-skin-primary.lg\:text-4xl")
            value = value_raw[0].get_text()
            refresh_raw = raw_data.select("#maincol_article > div.va-maincol.lg\:w-maincol.px-4.lg\:px-0.mb-9 > div.borer-skin-grey-medium.mb-4.border-t.border-solid.detailServiceStation_border__w8k48 > div:nth-child(" + str(
                self._petrol_number) + ") > div.flex.flex-col.justify-between.px-4.gasStationInfo_gas-info__5R12f > div > p")
            rval = refresh_raw[0].get_text().split(' ')
            self._last_refresh = rval[0] + ' ' + rval[1] + ' ' + rval[2]
        except IndexError:
            _LOGGER.error("Unable to extract data from HTML")
            value = 0.00
            return

        self._state = value
