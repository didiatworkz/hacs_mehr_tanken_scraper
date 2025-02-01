import asyncio
import logging
from datetime import timedelta

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from bs4 import BeautifulSoup
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_LOCATION, CONF_NAME, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_PETROL_NAME = "petrol_name"
CONF_PETROL_NUMBER = "petrol_number"
CONF_PETROL_NUMBER_DEFAULT = 0
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_URL): cv.url,
    vol.Required(CONF_PETROL_NUMBER, default=CONF_PETROL_NUMBER_DEFAULT): cv.positive_int,
    vol.Required(CONF_PETROL_NAME): cv.string,
    vol.Optional(CONF_LOCATION, default=""): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the mehr-tanken fuel prices sensor."""
    session = async_get_clientsession(hass)
    async_add_entities([
        MehrTankenSensor(
            session,
            config[CONF_NAME],
            config[CONF_URL],
            config[CONF_PETROL_NUMBER],
            config[CONF_PETROL_NAME],
            config.get(CONF_LOCATION, "")
        )
    ], True)

class MehrTankenSensor(Entity):
    """Representation of a mehr-tanken sensor."""

    def __init__(self, session, name, address, petrol_number, petrol_name, location):
        self._name = name
        self._href = address
        self._petrol_number = petrol_number
        self._petrol_name = petrol_name
        self._state = None
        self._last_refresh = ""
        self._session = session
        self._unit_of_measurement = "EUR/l"
        self._location = location
        self._headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml",
            "Cookie": "cookie_consent=accepted"
        }

    @property
    def name(self):
        return f"mehr_tanken_{self._name}_{self._petrol_name}".replace(" ", "_")

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        return {
            CONF_PETROL_NAME: self._petrol_name,
            CONF_LOCATION: self._location,
            "last_refresh": self._last_refresh,
            "gas_station": self._name,
        }

    async def async_update(self):
        """Fetch data from mehr-tanken website."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.get(self._href, headers=self._headers)
                response.raise_for_status()
                data = await response.text()

            _LOGGER.debug("Response from mehr-tanken.de: %s", response.status)
            raw_data = BeautifulSoup(data, "html.parser")

            value_raw = raw_data.select(
                f"div:nth-child({self._petrol_number}) > div.flex.flex-col.justify-between.space-y-4.gasStationInfo_gas-price__ZW1gM > div.relative.font-skin-primary.text-3xl.text-skin-primary.lg\:text-4xl")
            refresh_raw = raw_data.select(
                f"div:nth-child({self._petrol_number}) > div.flex.flex-col.justify-between.px-4.gasStationInfo_gas-info__5R12f > div > p")

            if value_raw and refresh_raw:
                self._state = value_raw[0].get_text(strip=True)
                self._last_refresh = " ".join(
                    refresh_raw[0].get_text().split()[:3])
            else:
                _LOGGER.warning("No fuel data found.")
                self._state = None
        except (asyncio.TimeoutError, aiohttp.ClientError, IndexError) as e:
            _LOGGER.error("Error fetching data: %s", e)
            self._state = None
