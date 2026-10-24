"""Compressor state source per firmware (issue #3).

Firmware 7.02 (Tecalor THZ 5.5 eco) reports sGlobal compressor=1 while the
compressor stands still; there the entity follows the front-display bit.
5.x keeps reading sGlobal. The block data comes from synthetic telegrams
parsed by the real register tables.
"""

from unittest.mock import AsyncMock, patch

from custom_components.lwz_thz.const import DOMAIN
from custom_components.lwz_thz.thzprotocol.registers import (
    SDISPLAY,
    SGLOBAL,
    parse_block,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest


def _sglobal(*, compressor: bool, pel: str) -> dict:
    nibbles = ["0"] * 158
    nibbles[2:4] = "FB"
    nibbles[47] = "8" if compressor else "0"  # bit3 = compressor
    nibbles[102:110] = pel  # actual_power_pel, esp_mant
    return parse_block(SGLOBAL, bytes.fromhex("".join(nibbles)))


def _sdisplay(*, compressor: bool) -> dict:
    status = "0002" if compressor else "0000"  # nibble 11 bit1 = compressor
    return parse_block(SDISPLAY, bytes.fromhex("AB" + "0A0176" + status))


async def _compressor_state(
    hass: HomeAssistant, mock_entry, mock_client, firmware: str
) -> str:
    mock_client.get_firmware = AsyncMock(return_value=firmware)
    mock_entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{mock_entry.entry_id}_compressor"
    )
    assert entity_id
    return hass.states.get(entity_id).state


async def test_fw7_stopped_compressor_reads_off(
    hass: HomeAssistant, mock_entry, mock_client
) -> None:
    # The snapshot from issue #3: sGlobal bit set, no power, display off.
    mock_client.block_data["sGlobal"] = _sglobal(compressor=True, pel="00000000")
    mock_client.block_data["sDisplay"] = _sdisplay(compressor=False)
    assert mock_client.block_data["sGlobal"]["compressor"] is True

    assert await _compressor_state(hass, mock_entry, mock_client, "7.02") == "off"


async def test_fw7_running_compressor_reads_on(
    hass: HomeAssistant, mock_entry, mock_client
) -> None:
    mock_client.block_data["sGlobal"] = _sglobal(compressor=True, pel="40000000")
    mock_client.block_data["sDisplay"] = _sdisplay(compressor=True)

    assert await _compressor_state(hass, mock_entry, mock_client, "7.02") == "on"


@pytest.mark.parametrize(("global_bit", "expected"), [(True, "on"), (False, "off")])
async def test_fw5_still_follows_sglobal(
    hass: HomeAssistant, mock_entry, mock_client, global_bit: bool, expected: str
) -> None:
    # Display bit deliberately disagrees: 5.x must not switch source.
    mock_client.block_data["sGlobal"] = _sglobal(
        compressor=global_bit, pel="40000000" if global_bit else "00000000"
    )
    mock_client.block_data["sDisplay"] = _sdisplay(compressor=not global_bit)

    assert await _compressor_state(hass, mock_entry, mock_client, "5.09") == expected
