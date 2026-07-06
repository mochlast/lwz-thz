"""Options flow and diagnostics tests."""

from unittest.mock import patch

from custom_components.lwz_thz.const import (
    OPT_ENABLE_HC2,
    OPT_ENABLE_SOLAR,
    OPT_INTERVAL_ENERGY,
    OPT_INTERVAL_HISTORY,
    OPT_INTERVAL_PARAMS,
    OPT_INTERVAL_STATUS,
)
from custom_components.lwz_thz.diagnostics import async_get_config_entry_diagnostics
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def _setup(hass: HomeAssistant, mock_entry, mock_client) -> None:
    mock_entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()


async def test_options_flow_updates_and_reloads(
    hass: HomeAssistant, mock_entry, mock_client
) -> None:
    await _setup(hass, mock_entry, mock_client)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_options = {
        OPT_INTERVAL_STATUS: 120,
        OPT_INTERVAL_PARAMS: 900,
        OPT_INTERVAL_HISTORY: 7200,
        OPT_INTERVAL_ENERGY: 43200,
        OPT_ENABLE_HC2: False,
        OPT_ENABLE_SOLAR: True,
    }
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_options
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(mock_entry.options) == new_options

    # The reload rebuilt the coordinator with the new group config.
    coordinator = mock_entry.runtime_data
    groups = {group.key: group for group in coordinator._groups}
    assert groups["status"].interval == 120
    status_blocks = [read.block_key for read in groups["status"].reads]
    assert "sSol" in status_blocks


async def test_diagnostics_snapshot(
    hass: HomeAssistant, mock_entry, mock_client
) -> None:
    await _setup(hass, mock_entry, mock_client)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)
    assert diagnostics["firmware"] == "5.09"
    assert diagnostics["connected"] is True
    assert diagnostics["data"]["sGlobal.outside_temp"] == 25.9
    group_keys = {group["key"] for group in diagnostics["poll_groups"]}
    assert group_keys == {"status", "params", "history", "energy"}
