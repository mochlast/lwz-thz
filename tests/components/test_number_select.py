"""Number/select platform tests: writes go through coordinator + client."""

from datetime import timedelta
from unittest.mock import patch

from custom_components.lwz_thz.const import DOMAIN
from custom_components.lwz_thz.thzprotocol.errors import ThzWriteVerifyError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


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


async def _set_number(hass: HomeAssistant, entity_id: str, value: float) -> None:
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )


async def _flush_debounce(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()


class TestNumber:
    async def test_set_value_is_optimistic_then_written(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "number", mock_entry.entry_id, "p01_room_temp_day")
        assert hass.states.get(entity_id).state == "25.0"

        await _set_number(hass, entity_id, 21.5)
        # Displayed immediately, but not yet written (debounce pending).
        assert hass.states.get(entity_id).state == "21.5"
        mock_client.write_param.assert_not_awaited()

        await _flush_debounce(hass)
        mock_client.write_param.assert_awaited_once_with("p01_room_temp_day", 21.5)
        assert hass.states.get(entity_id).state == "21.5"

    async def test_rapid_clicks_write_only_the_final_value(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "number", mock_entry.entry_id, "p01_room_temp_day")

        await _set_number(hass, entity_id, 25.1)
        await _set_number(hass, entity_id, 25.2)
        await _set_number(hass, entity_id, 25.3)
        assert hass.states.get(entity_id).state == "25.3"
        mock_client.write_param.assert_not_awaited()

        await _flush_debounce(hass)
        mock_client.write_param.assert_awaited_once_with("p01_room_temp_day", 25.3)
        assert hass.states.get(entity_id).state == "25.3"

    async def test_failed_write_reverts_to_device_value(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "number", mock_entry.entry_id, "p01_room_temp_day")
        mock_client.write_param.side_effect = ThzWriteVerifyError("mismatch")

        await _set_number(hass, entity_id, 22.0)
        assert hass.states.get(entity_id).state == "22.0"  # optimistic

        await _flush_debounce(hass)
        # Write failed -> revert to the last verified device value.
        assert hass.states.get(entity_id).state == "25.0"


class TestSelect:
    async def test_op_mode_options_and_select(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "select", mock_entry.entry_id, "op_mode")
        state = hass.states.get(entity_id)
        assert state.state == "automatic"
        assert "dhw" in state.attributes["options"]

        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "dhw"},
            blocking=True,
        )
        mock_client.write_param.assert_awaited_once_with("op_mode", "dhw")
        assert hass.states.get(entity_id).state == "dhw"

    async def test_fan_stage_maps_option_to_int(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "select", mock_entry.entry_id, "p07_fan_stage_day")
        assert hass.states.get(entity_id).state == "stage_1"

        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "stage_2"},
            blocking=True,
        )
        mock_client.write_param.assert_awaited_once_with("p07_fan_stage_day", 2)
        assert hass.states.get(entity_id).state == "stage_2"
