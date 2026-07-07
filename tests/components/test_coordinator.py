"""Coordinator group scheduling tests (mocked client, no serial I/O)."""

from unittest.mock import MagicMock

from custom_components.lwz_thz.const import OPT_ENABLE_SOLAR, OPT_INTERVAL_STATUS
from custom_components.lwz_thz.coordinator import ThzCoordinator, build_groups
from custom_components.lwz_thz.thzprotocol.errors import ThzTimeoutError
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


class TestBuildGroups:
    def test_default_groups(self) -> None:
        groups = {group.key: group for group in build_groups({})}
        assert set(groups) == {"status", "params", "history", "energy"}
        assert groups["status"].interval == 300
        assert groups["params"].interval == 600
        assert groups["history"].interval == 3600
        assert groups["energy"].interval == 3600
        status_blocks = [read.block_key for read in groups["status"].reads]
        assert "sGlobal" in status_blocks
        assert "sSol" not in status_blocks
        assert "sHC2" not in status_blocks

    def test_feature_toggles_and_minimum_interval(self) -> None:
        groups = {
            group.key: group
            for group in build_groups({OPT_ENABLE_SOLAR: True, OPT_INTERVAL_STATUS: 10})
        }
        status_blocks = [read.block_key for read in groups["status"].reads]
        assert "sSol" in status_blocks
        assert groups["status"].interval == 60  # clamped to MIN_POLL_INTERVAL


async def _make_coordinator(
    hass: HomeAssistant, mock_entry: MockConfigEntry, mock_client: MagicMock
) -> ThzCoordinator:
    mock_entry.add_to_hass(hass)
    return ThzCoordinator(hass, mock_entry, mock_client)


class TestUpdateData:
    async def test_first_update_reads_all_groups(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        coordinator = await _make_coordinator(hass, mock_entry, mock_client)
        data = await coordinator._async_update_data()
        assert data["sGlobal.outside_temp"] == 25.9
        assert data["sHistory.compressor_heating"] == 11301
        assert data["energy.heat_hc_total"] == 63355
        assert data["param.op_mode"] == "automatic"
        # 6 status blocks + 2 history blocks
        assert mock_client.read_block.await_count == 8
        assert mock_client.read_param.await_count == 16
        assert mock_client.read_program.await_count == 9
        assert mock_client.read_energy.await_count == 12

    async def test_groups_not_due_are_skipped(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        coordinator = await _make_coordinator(hass, mock_entry, mock_client)
        first = await coordinator._async_update_data()
        coordinator.data = first
        mock_client.read_block.reset_mock()
        mock_client.read_energy.reset_mock()

        second = await coordinator._async_update_data()
        assert mock_client.read_block.await_count == 0
        assert mock_client.read_energy.await_count == 0
        assert second == first  # values retained

    async def test_group_error_backs_off_and_keeps_data(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        coordinator = await _make_coordinator(hass, mock_entry, mock_client)
        first = await coordinator._async_update_data()
        coordinator.data = first

        # Make the status group due again, but failing.
        status = coordinator._groups[0]
        status.next_due = 0.0
        mock_client.read_block.side_effect = ThzTimeoutError("no answer")

        second = await coordinator._async_update_data()
        assert second["sGlobal.outside_temp"] == 25.9  # stale value retained
        assert status.consecutive_errors == 1
        assert status.next_due > 0.0  # error backoff scheduled

    async def test_total_failure_without_any_data_raises(
        self, hass: HomeAssistant, mock_entry, mock_client
    ) -> None:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        coordinator = await _make_coordinator(hass, mock_entry, mock_client)
        mock_client.read_block.side_effect = ThzTimeoutError("dead")
        mock_client.read_param.side_effect = ThzTimeoutError("dead")
        mock_client.read_energy.side_effect = ThzTimeoutError("dead")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
