"""Fixtures for Home Assistant component tests."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.lwz_thz.const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_PORT,
    CONNECTION_SERIAL,
    DOMAIN,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components in tests."""
    return


@pytest.fixture
def mock_client() -> MagicMock:
    """A ThzClient double serving canned block data."""
    client = MagicMock()
    client.is_connected = True
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.get_firmware = AsyncMock(return_value="5.09")
    block_data = {
        "sGlobal": {
            "outside_temp": 25.9,
            "dhw_temp": 43.6,
            "compressor": False,
            "evu_release": True,
        },
        "sHC1": {"heat_set_temp": 8.0, "hc_op_mode": "normal", "inside_temp_rc": 25.0},
        "sDHW": {"dhw_set_temp": 40.0},
        "sControl": {"heat_request": 5},
        "sFan": {"fanstage_airflow_inlet": 0},
        "sDisplay": {"filter_both": True},
        "sHistory": {"compressor_heating": 11301},
        "sLast10errors": {"number_of_faults": 0, "fault0_code": "n.a."},
        "sHC2": {"heat_set_temp": 8.0},
        "sSol": {"collector_temp": -60.0},
    }
    client.read_block = AsyncMock(side_effect=lambda key: dict(block_data[key]))
    client.read_energy = AsyncMock(return_value=63355)
    param_data = {
        "op_mode": "automatic",
        "p01_room_temp_day": 25.0,
        "p04_dhw_temp_day": 40.0,
        "p07_fan_stage_day": 1,
    }
    client.read_param = AsyncMock(side_effect=lambda key: param_data.get(key, 0))
    client.write_param = AsyncMock(side_effect=lambda key, value: value)
    return client


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """A config entry as the serial config flow would create it."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="LWZ/THZ (5.09)",
        unique_id="serial:/dev/lwz304",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
            CONF_PORT: "/dev/lwz304",
            CONF_BAUDRATE: 115200,
        },
    )
