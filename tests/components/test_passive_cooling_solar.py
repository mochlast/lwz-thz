"""Issue #5: passive cooling (p75) and the solar entities."""

from unittest.mock import AsyncMock, patch

from custom_components.lwz_thz.const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_PORT,
    CONNECTION_SERIAL,
    DOMAIN,
    OPT_ENABLE_SOLAR,
    OPT_MODEL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

ALL_OPTIONS = ["off", "exhaust_air", "supply_air", "bypass", "summer_cassette"]


def _entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="LWZ/THZ (5.09)",
        unique_id="serial:/dev/lwz304",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
            CONF_PORT: "/dev/lwz304",
            CONF_BAUDRATE: 115200,
        },
        options={OPT_MODEL: "LWZ 304 Trend", **options},
    )


async def _setup(hass: HomeAssistant, entry, mock_client, firmware="5.09") -> None:
    mock_client.get_firmware = AsyncMock(return_value=firmware)
    entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, domain: str, entry, suffix: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{entry.entry_id}_{suffix}"
    )


def _params(mock_client, **values) -> None:
    mock_client.read_param.side_effect = lambda key: values.get(key, 0)


class TestPassiveCooling:
    async def test_options_and_current_value(
        self, hass: HomeAssistant, mock_client
    ) -> None:
        _params(mock_client, p75_passive_cooling=2)
        entry = _entry()
        await _setup(hass, entry, mock_client)
        state = hass.states.get(
            _entity_id(hass, "select", entry, "p75_passive_cooling")
        )
        assert state.attributes["options"] == ALL_OPTIONS
        assert state.state == "supply_air"

    async def test_select_writes_register_value(
        self, hass: HomeAssistant, mock_client
    ) -> None:
        entry = _entry()
        await _setup(hass, entry, mock_client)
        entity_id = _entity_id(hass, "select", entry, "p75_passive_cooling")
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "exhaust_air"},
            blocking=True,
        )
        mock_client.write_param.assert_awaited_once_with("p75_passive_cooling", 1)
        assert hass.states.get(entity_id).state == "exhaust_air"

    async def test_fw4_offers_only_the_first_three(
        self, hass: HomeAssistant, mock_client
    ) -> None:
        entry = _entry()
        await _setup(hass, entry, mock_client, firmware="4.39")
        state = hass.states.get(
            _entity_id(hass, "select", entry, "p75_passive_cooling")
        )
        assert state.attributes["options"] == ALL_OPTIONS[:3]


class TestSolar:
    async def test_hidden_without_solar_option(
        self, hass: HomeAssistant, mock_client
    ) -> None:
        entry = _entry()
        await _setup(hass, entry, mock_client)
        assert _entity_id(hass, "switch", entry, "p80_enable_solar") is None
        assert _entity_id(hass, "number", entry, "p83_dhw_temp_solar") is None
        assert _entity_id(hass, "sensor", entry, "solar_flow_temp") is None

    async def test_solar_entities(self, hass: HomeAssistant, mock_client) -> None:
        _params(mock_client, p80_enable_solar=1, p83_dhw_temp_solar=60.0)
        mock_client.block_data["sSol"] = {
            "collector_temp": 41.5,
            "dhw_temp": 52.3,
            "flow_temp": 45.0,
        }
        entry = _entry(**{OPT_ENABLE_SOLAR: True})
        await _setup(hass, entry, mock_client)

        switch_id = _entity_id(hass, "switch", entry, "p80_enable_solar")
        assert hass.states.get(switch_id).state == "on"
        number_id = _entity_id(hass, "number", entry, "p83_dhw_temp_solar")
        assert hass.states.get(number_id).state == "60.0"
        flow_id = _entity_id(hass, "sensor", entry, "solar_flow_temp")
        assert hass.states.get(flow_id).state == "45.0"

    async def test_enable_solar_switch_writes_0_and_1(
        self, hass: HomeAssistant, mock_client
    ) -> None:
        _params(mock_client, p80_enable_solar=1)
        entry = _entry(**{OPT_ENABLE_SOLAR: True})
        await _setup(hass, entry, mock_client)
        switch_id = _entity_id(hass, "switch", entry, "p80_enable_solar")

        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": switch_id}, blocking=True
        )
        mock_client.write_param.assert_awaited_with("p80_enable_solar", 0)
        assert hass.states.get(switch_id).state == "off"

        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch_id}, blocking=True
        )
        mock_client.write_param.assert_awaited_with("p80_enable_solar", 1)
        assert hass.states.get(switch_id).state == "on"
