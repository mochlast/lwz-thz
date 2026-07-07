"""Stiebel Eltron LWZ / Tecalor THZ integration (serial service interface)."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_HOST,
    CONF_PORT,
    CONF_TCP_PORT,
    CONNECTION_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_TCP_PORT,
)
from .coordinator import ThzConfigEntry, ThzCoordinator
from .thzprotocol import SerialTransport, TcpTransport, ThzClient, Transport

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.WATER_HEATER,
]


def make_transport_factory(data: dict) -> Callable[[], Transport]:
    """Build the transport factory from config entry data."""
    if data.get(CONF_CONNECTION_TYPE) == CONNECTION_TCP:
        host: str = data[CONF_HOST]
        tcp_port: int = data.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)
        return lambda: TcpTransport(host, tcp_port)
    port: str = data[CONF_PORT]
    baudrate: int = data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
    return lambda: SerialTransport(port, baudrate)


async def async_setup_entry(hass: HomeAssistant, entry: ThzConfigEntry) -> bool:
    client = ThzClient(make_transport_factory(dict(entry.data)))
    coordinator = ThzCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ThzConfigEntry) -> None:
    """Reload on options change (rebuilds the poll groups)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ThzConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.client.disconnect()
    return unload_ok
