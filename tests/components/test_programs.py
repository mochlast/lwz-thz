"""Program time/switch platform tests."""

from datetime import time
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


class TestProgramTime:
    async def test_states_from_device(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        start = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_start")
        end = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_end")
        assert hass.states.get(start).state == "07:00:00"
        assert hass.states.get(end).state == "14:00:00"
        # Disabled slot -> unknown
        start2 = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_2_start")
        assert hass.states.get(start2).state == "unknown"

    async def test_set_start_merges_existing_end(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        start = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_start")
        await hass.services.async_call(
            "time",
            "set_value",
            {"entity_id": start, "time": "08:30:00"},
            blocking=True,
        )
        mock_client.write_program.assert_awaited_once_with(
            "dhw_1", time(8, 30), time(14, 0)
        )
        assert hass.states.get(start).state == "08:30:00"

    async def test_set_time_on_disabled_slot_uses_default_other_half(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        start = _entity_id(hass, "time", mock_entry.entry_id, "prog_fan_2_start")
        await hass.services.async_call(
            "time",
            "set_value",
            {"entity_id": start, "time": "12:00:00"},
            blocking=True,
        )
        mock_client.write_program.assert_awaited_once_with(
            "fan_2", time(12, 0), time(22, 0)
        )


class TestProgramSwitch:
    async def test_active_state(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        active1 = _entity_id(hass, "switch", mock_entry.entry_id, "prog_dhw_1_active")
        active2 = _entity_id(hass, "switch", mock_entry.entry_id, "prog_dhw_2_active")
        assert hass.states.get(active1).state == "on"
        assert hass.states.get(active2).state == "off"

    async def test_turn_off_writes_na(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        active = _entity_id(hass, "switch", mock_entry.entry_id, "prog_dhw_1_active")
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": active}, blocking=True
        )
        mock_client.write_program.assert_awaited_once_with("dhw_1", None, None)
        assert hass.states.get(active).state == "off"

    async def test_turn_on_disabled_slot_uses_defaults(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        active = _entity_id(hass, "switch", mock_entry.entry_id, "prog_fan_3_active")
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": active}, blocking=True
        )
        mock_client.write_program.assert_awaited_once_with(
            "fan_3", time(6, 0), time(22, 0)
        )
        assert hass.states.get(active).state == "on"
