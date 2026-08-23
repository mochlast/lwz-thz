"""Device registry entry: the model comes from the config entry, not the code."""

from unittest.mock import patch

from custom_components.lwz_thz.const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_PORT,
    CONNECTION_SERIAL,
    DEFAULT_MODEL,
    DOMAIN,
    OPT_MODEL,
    manufacturer_for,
    suggest_model,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


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
        options=options,
    )


async def _device(hass: HomeAssistant, entry, mock_client) -> dr.DeviceEntry:
    entry.add_to_hass(hass)
    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device({(DOMAIN, entry.entry_id)})
    assert device is not None
    return device


async def test_model_option_names_the_device(hass: HomeAssistant, mock_client) -> None:
    device = await _device(hass, _entry(**{OPT_MODEL: "THZ 404 eco"}), mock_client)
    assert device.name == "THZ 404 eco"
    assert device.model == "THZ 404 eco"
    assert device.manufacturer == "Tecalor"


async def test_entry_without_model_option_falls_back(
    hass: HomeAssistant, mock_client
) -> None:
    """Entries created before 0.8.0 have no model option."""
    device = await _device(hass, _entry(), mock_client)
    assert device.name == DEFAULT_MODEL
    assert device.model == DEFAULT_MODEL


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("LWZ 304 Trend", "Stiebel Eltron"),
        ("THZ 404 eco", "Tecalor"),
        ("thz 504", "Tecalor"),
        (DEFAULT_MODEL, "Stiebel Eltron"),
        ("Selbstbau", "Stiebel Eltron / Tecalor"),
    ],
)
def test_manufacturer_for(model: str, expected: str) -> None:
    assert manufacturer_for(model) == expected


@pytest.mark.parametrize(
    ("firmware", "expected"),
    [
        ("5.09", "LWZ 304 Trend"),
        ("5.39", "LWZ 304 Trend"),
        ("4.39", "THZ 303 SOL"),
        ("2.06", DEFAULT_MODEL),
        (None, DEFAULT_MODEL),
    ],
)
def test_suggest_model(firmware: str | None, expected: str) -> None:
    assert suggest_model(firmware) == expected


async def test_changing_the_model_option_renames_the_device(
    hass: HomeAssistant, mock_client
) -> None:
    entry = _entry(**{OPT_MODEL: "LWZ 304 Trend"})
    device = await _device(hass, entry, mock_client)
    assert device.name == "LWZ 304 Trend"

    with patch("custom_components.lwz_thz.ThzClient", return_value=mock_client):
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, OPT_MODEL: "LWZ 404 Trend"}
        )
        await hass.async_block_till_done()

    device = dr.async_get(hass).async_get_device({(DOMAIN, entry.entry_id)})
    assert device.name == "LWZ 404 Trend"
    assert device.model == "LWZ 404 Trend"
