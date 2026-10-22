"""Device clock sensors and the sync button (mocked client, frozen time)."""

from datetime import datetime
from unittest.mock import patch

from custom_components.lwz_thz.const import DOMAIN
from custom_components.lwz_thz.thzprotocol.errors import ThzWriteVerifyError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest

# The canned sTimedate block (conftest) says 22.10.2026 16:43:07.
DEVICE_TIME = datetime(2026, 10, 22, 16, 43, 7)


def _freeze_local(freezer: FrozenDateTimeFactory, local: datetime) -> None:
    freezer.move_to(local.replace(tzinfo=dt_util.get_default_time_zone()))


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


def _apply_clock_writes(mock_client) -> None:
    """Let write_param move the canned device clock like the real device."""
    fields = {
        "clock_year": ("year", 2000),
        "clock_month": ("month", 0),
        "clock_day": ("day", 0),
        "clock_hour": ("hour", 0),
        "clock_minute": ("minute", 0),
    }

    def write(key, value):
        field, base = fields[key]
        mock_client.block_data["sTimedate"][field] = value + base
        return value

    mock_client.write_param.side_effect = write


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )


class TestClockSensors:
    async def test_device_time_and_offset(
        self, hass: HomeAssistant, mock_entry, mock_client, freezer
    ) -> None:
        _freeze_local(freezer, datetime(2026, 10, 22, 16, 40, 7))
        await _setup(hass, mock_entry, mock_client)
        entry_id = mock_entry.entry_id

        clock = hass.states.get(_entity_id(hass, "sensor", entry_id, "device_clock"))
        expected = DEVICE_TIME.replace(tzinfo=dt_util.get_default_time_zone())
        assert dt_util.parse_datetime(clock.state) == expected
        offset = hass.states.get(_entity_id(hass, "sensor", entry_id, "clock_offset"))
        assert offset.state == "3.0"
        assert offset.attributes["unit_of_measurement"] == "min"

    async def test_invalid_device_date_is_unknown(
        self, hass: HomeAssistant, mock_entry, mock_client, freezer
    ) -> None:
        _freeze_local(freezer, datetime(2026, 10, 22, 16, 40, 7))
        mock_client.block_data["sTimedate"]["day"] = 0
        await _setup(hass, mock_entry, mock_client)
        entity_id = _entity_id(hass, "sensor", mock_entry.entry_id, "clock_offset")
        assert hass.states.get(entity_id).state == "unknown"


class TestSyncButton:
    async def test_writes_only_the_minute_and_rereads(
        self, hass: HomeAssistant, mock_entry, mock_client, freezer
    ) -> None:
        _freeze_local(freezer, datetime(2026, 10, 22, 16, 40, 7))
        await _setup(hass, mock_entry, mock_client)
        _apply_clock_writes(mock_client)
        mock_client.read_block.reset_mock()

        await _press(
            hass, _entity_id(hass, "button", mock_entry.entry_id, "sync_clock")
        )

        mock_client.write_param.assert_awaited_once_with("clock_minute", 40)
        assert mock_client.read_block.await_count == 2  # fresh read + read-back
        offset = _entity_id(hass, "sensor", mock_entry.entry_id, "clock_offset")
        assert hass.states.get(offset).state == "0.0"

    async def test_summer_time_missed_writes_the_hour(
        self, hass: HomeAssistant, mock_entry, mock_client, freezer
    ) -> None:
        _freeze_local(freezer, datetime(2026, 10, 22, 15, 43, 0))
        await _setup(hass, mock_entry, mock_client)
        _apply_clock_writes(mock_client)

        await _press(
            hass, _entity_id(hass, "button", mock_entry.entry_id, "sync_clock")
        )

        mock_client.write_param.assert_awaited_once_with("clock_hour", 15)

    async def test_in_sync_writes_nothing(
        self, hass: HomeAssistant, mock_entry, mock_client, freezer
    ) -> None:
        _freeze_local(freezer, datetime(2026, 10, 22, 16, 42, 0))
        await _setup(hass, mock_entry, mock_client)
        mock_client.read_block.reset_mock()

        await _press(
            hass, _entity_id(hass, "button", mock_entry.entry_id, "sync_clock")
        )

        mock_client.write_param.assert_not_awaited()
        assert mock_client.read_block.await_count == 1

    async def test_verify_failure_is_raised(
        self, hass: HomeAssistant, mock_entry, mock_client, freezer
    ) -> None:
        _freeze_local(freezer, datetime(2026, 10, 22, 16, 40, 7))
        await _setup(hass, mock_entry, mock_client)
        mock_client.write_param.side_effect = ThzWriteVerifyError("mismatch")

        with pytest.raises(HomeAssistantError, match="clock sync failed"):
            await _press(
                hass, _entity_id(hass, "button", mock_entry.entry_id, "sync_clock")
            )
