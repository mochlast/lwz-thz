"""Program time/switch platform tests (staged, debounced writes)."""

from datetime import time, timedelta
from unittest.mock import patch

from custom_components.lwz_thz.const import DOMAIN
from custom_components.lwz_thz.thzprotocol.errors import ThzProtocolError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


async def _setup(hass: HomeAssistant, mock_entry, mock_client) -> None:
    mock_entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()


async def _flush_writes(hass: HomeAssistant) -> None:
    """Let the write debounce elapse and the staged write run."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
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
        # Optimistic: visible before any serial write happened.
        assert hass.states.get(start).state == "08:30:00"
        mock_client.write_program.assert_not_awaited()
        await _flush_writes(hass)
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
        await _flush_writes(hass)
        mock_client.write_program.assert_awaited_once_with(
            "fan_2", time(12, 0), time(22, 0)
        )

    async def test_rapid_changes_coalesce_into_one_write(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        start = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_start")
        end = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_end")
        await hass.services.async_call(
            "time", "set_value", {"entity_id": start, "time": "08:00:00"}, blocking=True
        )
        await hass.services.async_call(
            "time", "set_value", {"entity_id": end, "time": "15:15:00"}, blocking=True
        )
        # Second edit sees the first one (optimistic data), one write total.
        await _flush_writes(hass)
        mock_client.write_program.assert_awaited_once_with(
            "dhw_1", time(8, 0), time(15, 15)
        )

    async def test_value_snaps_to_quarter_hour_grid(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        start = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_start")
        await hass.services.async_call(
            "time",
            "set_value",
            {"entity_id": start, "time": "08:07:00"},
            blocking=True,
        )
        # Optimistic state already shows what the device will store.
        assert hass.states.get(start).state == "08:00:00"
        await _flush_writes(hass)
        mock_client.write_program.assert_awaited_once_with(
            "dhw_1", time(8, 0), time(14, 0)
        )

    async def test_failed_write_reverts_to_device_value(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        start = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_start")
        mock_client.write_program.side_effect = ThzProtocolError("NAK")
        await hass.services.async_call(
            "time", "set_value", {"entity_id": start, "time": "09:00:00"}, blocking=True
        )
        assert hass.states.get(start).state == "09:00:00"  # optimistic
        await _flush_writes(hass)
        # Reverted to what the device reports (read_program fixture: 07:00).
        assert hass.states.get(start).state == "07:00:00"


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
        assert hass.states.get(active).state == "off"  # optimistic
        await _flush_writes(hass)
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
        assert hass.states.get(active).state == "on"  # optimistic
        await _flush_writes(hass)
        mock_client.write_program.assert_awaited_once_with(
            "fan_3", time(6, 0), time(22, 0)
        )

    async def test_turn_on_restores_last_window(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        active = _entity_id(hass, "switch", mock_entry.entry_id, "prog_dhw_1_active")
        start = _entity_id(hass, "time", mock_entry.entry_id, "prog_dhw_1_start")
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": active}, blocking=True
        )
        await _flush_writes(hass)
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": active}, blocking=True
        )
        await _flush_writes(hass)
        # Restored 07:00-14:00 (the window before turn_off), not 06:00-22:00.
        mock_client.write_program.assert_awaited_with("dhw_1", time(7, 0), time(14, 0))
        assert hass.states.get(start).state == "07:00:00"

    async def test_off_on_bounce_coalesces_to_single_restore_write(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        await _setup(hass, mock_entry, mock_client)
        active = _entity_id(hass, "switch", mock_entry.entry_id, "prog_dhw_1_active")
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": active}, blocking=True
        )
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": active}, blocking=True
        )
        await _flush_writes(hass)
        mock_client.write_program.assert_awaited_once_with(
            "dhw_1", time(7, 0), time(14, 0)
        )
        assert hass.states.get(active).state == "on"
