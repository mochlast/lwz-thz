"""Config flow tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.lwz_thz.const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_PORT,
    CONNECTION_SERIAL,
    DOMAIN,
)
from custom_components.lwz_thz.thzprotocol.errors import (
    ThzConnectionError,
    ThzTimeoutError,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _patch_client(**kwargs) -> patch:
    client = MagicMock()
    client.connect = AsyncMock(**kwargs.get("connect", {}))
    client.disconnect = AsyncMock()
    client.get_firmware = AsyncMock(
        **kwargs.get("get_firmware", {"return_value": "5.09"})
    )
    return patch("custom_components.lwz_thz.config_flow.ThzClient", return_value=client)


def _patch_ports() -> patch:
    return patch(
        "custom_components.lwz_thz.config_flow._scan_serial_ports", return_value=[]
    )


async def _start_serial_step(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "serial"}
    )


async def test_serial_flow_creates_entry(hass: HomeAssistant) -> None:
    with _patch_ports():
        result = await _start_serial_step(hass)
        assert result["type"] is FlowResultType.FORM

        with _patch_client():
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PORT: "/dev/lwz304", CONF_BAUDRATE: "115200"},
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LWZ/THZ (5.09)"
    assert result["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
        CONF_PORT: "/dev/lwz304",
        CONF_BAUDRATE: 115200,
    }


async def test_serial_flow_cannot_connect_shows_error(hass: HomeAssistant) -> None:
    with _patch_ports():
        result = await _start_serial_step(hass)
        with _patch_client(connect={"side_effect": ThzConnectionError("busy")}):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PORT: "/dev/lwz304", CONF_BAUDRATE: "115200"},
            )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_serial_flow_no_response_shows_error(hass: HomeAssistant) -> None:
    with _patch_ports():
        result = await _start_serial_step(hass)
        with _patch_client(get_firmware={"side_effect": ThzTimeoutError("silent")}):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_PORT: "/dev/lwz304", CONF_BAUDRATE: "115200"},
            )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_response"}


async def test_duplicate_port_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="serial:/dev/lwz304",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
            CONF_PORT: "/dev/lwz304",
            CONF_BAUDRATE: 115200,
        },
    ).add_to_hass(hass)

    with _patch_ports():
        result = await _start_serial_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORT: "/dev/lwz304", CONF_BAUDRATE: "115200"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
