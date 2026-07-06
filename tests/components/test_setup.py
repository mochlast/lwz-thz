"""End-to-end setup test: config entry -> device -> entities with states."""

from unittest.mock import patch

from custom_components.lwz_thz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_setup_creates_device_and_entities(
    hass: HomeAssistant, mock_entry, mock_client
) -> None:
    mock_entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, mock_entry.entry_id)})
    assert device is not None
    assert device.sw_version == "5.09"
    assert device.manufacturer == "Stiebel Eltron / Tecalor"

    entity_registry = er.async_get(hass)

    def state_of(unique_suffix: str):
        entry = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{mock_entry.entry_id}_{unique_suffix}"
        ) or entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{mock_entry.entry_id}_{unique_suffix}"
        )
        assert entry, f"entity {unique_suffix} not registered"
        return hass.states.get(entry)

    assert state_of("outside_temp").state == "25.9"
    assert state_of("dhw_temp").state == "43.6"
    assert state_of("compressor").state == "off"
    assert state_of("evu_release").state == "on"
    assert state_of("display_filter").state == "on"
    assert state_of("hours_compressor_heating").state == "11301"
    assert state_of("energy_heat_hc_total").state == "63355"

    # Values missing from coordinator data -> unavailable, not a crash.
    assert state_of("pressure_low").state == "unavailable"


async def test_unload_entry(hass: HomeAssistant, mock_entry, mock_client) -> None:
    mock_entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.disconnect.assert_awaited()
