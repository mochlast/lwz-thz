"""Climate and water heater platform tests."""

from unittest.mock import patch

from custom_components.lwz_thz.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def _setup(hass: HomeAssistant, mock_entry, mock_client) -> None:
    mock_entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, domain: str, entry_id: str, suffix: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{entry_id}_{suffix}")
    assert entity_id, f"{domain} entity {suffix} not registered"
    return entity_id


class TestClimate:
    async def test_state_reflects_op_mode_and_temperatures(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "climate", mock_entry.entry_id, "climate_hc1")
        state = hass.states.get(entity_id)
        assert state.state == "auto"  # param.op_mode = automatic
        assert state.attributes["current_temperature"] == 25.0
        assert state.attributes["temperature"] == 25.0  # p01 mock value
        assert state.attributes["min_temp"] == 12
        assert state.attributes["max_temp"] == 32

    async def test_set_temperature_writes_p01(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "climate", mock_entry.entry_id, "climate_hc1")
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": entity_id, "temperature": 21.5},
            blocking=True,
        )
        mock_client.write_param.assert_awaited_once_with("p01_room_temp_day", 21.5)

    async def test_set_hvac_mode_writes_op_mode(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "climate", mock_entry.entry_id, "climate_hc1")
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": entity_id, "hvac_mode": "off"},
            blocking=True,
        )
        mock_client.write_param.assert_awaited_once_with("op_mode", "standby")
        assert hass.states.get(entity_id).state == "off"


class TestWaterHeater:
    async def test_state_and_set_temperature(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(
            hass, "water_heater", mock_entry.entry_id, "water_heater_dhw"
        )
        state = hass.states.get(entity_id)
        assert state.attributes["current_temperature"] == 43.6
        assert state.attributes["temperature"] == 40.0  # p04 mock value

        await hass.services.async_call(
            "water_heater",
            "set_temperature",
            {"entity_id": entity_id, "temperature": 48.0},
            blocking=True,
        )
        mock_client.write_param.assert_awaited_once_with("p04_dhw_temp_day", 48.0)
