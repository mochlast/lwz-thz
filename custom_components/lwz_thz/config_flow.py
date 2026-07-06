"""Config flow: pick serial port (or ser2net endpoint), verify by reading sFirmware."""

from __future__ import annotations

import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
import voluptuous as vol

from . import make_transport_factory
from .const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_HOST,
    CONF_PORT,
    CONF_TCP_PORT,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_INTERVAL_ENERGY,
    DEFAULT_INTERVAL_HISTORY,
    DEFAULT_INTERVAL_PARAMS,
    DEFAULT_INTERVAL_STATUS,
    DEFAULT_TCP_PORT,
    DOMAIN,
    OPT_ENABLE_HC2,
    OPT_ENABLE_SOLAR,
    OPT_INTERVAL_ENERGY,
    OPT_INTERVAL_HISTORY,
    OPT_INTERVAL_PARAMS,
    OPT_INTERVAL_STATUS,
)
from .thzprotocol import ThzClient, ThzConnectionError, ThzError

_LOGGER = logging.getLogger(__name__)

_BAUDRATES = ["115200", "57600", "19200", "9600"]


def _scan_serial_ports() -> list[str]:
    """List candidate serial ports; stable /dev/serial/by-id paths first."""
    entries: list[str] = []
    seen: set[str] = set()

    by_id = "/dev/serial/by-id"
    if os.path.isdir(by_id):
        for name in sorted(os.listdir(by_id)):
            path = os.path.join(by_id, name)
            entries.append(path)
            seen.add(os.path.realpath(path))

    from serial.tools import list_ports

    for port in sorted(list_ports.comports(), key=lambda p: p.device):
        if os.path.realpath(port.device) in seen:
            continue
        entry = port.device
        if port.description and port.description != "n/a":
            entry = f"{port.device} ({port.description})"
        entries.append(entry)
    return entries


class LwzThzConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> LwzThzOptionsFlow:
        return LwzThzOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="user", menu_options=[CONNECTION_SERIAL, CONNECTION_TCP]
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_CONNECTION_TYPE: CONNECTION_SERIAL,
                CONF_PORT: user_input[CONF_PORT],
                CONF_BAUDRATE: int(user_input[CONF_BAUDRATE]),
            }
            await self.async_set_unique_id(f"serial:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            firmware, errors = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(title=f"LWZ/THZ ({firmware})", data=data)

        ports = await self.hass.async_add_executor_job(_scan_serial_ports)
        schema = vol.Schema(
            {
                vol.Required(CONF_PORT): TextSelector(),
                vol.Required(
                    CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=_BAUDRATES, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="serial",
            data_schema=schema,
            errors=errors,
            description_placeholders={"ports": ", ".join(ports) if ports else "—"},
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_CONNECTION_TYPE: CONNECTION_TCP,
                CONF_HOST: user_input[CONF_HOST],
                CONF_TCP_PORT: int(user_input[CONF_TCP_PORT]),
            }
            await self.async_set_unique_id(
                f"tcp:{data[CONF_HOST]}:{data[CONF_TCP_PORT]}"
            )
            self._abort_if_unique_id_configured()
            firmware, errors = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(title=f"LWZ/THZ ({firmware})", data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): TextSelector(),
                vol.Required(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="tcp", data_schema=schema, errors=errors)

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[str | None, dict[str, str]]:
        """Open a real connection and read the firmware version."""
        client = ThzClient(make_transport_factory(data))
        try:
            await client.connect()
            return await client.get_firmware(), {}
        except ThzConnectionError as err:
            _LOGGER.debug("validation: cannot connect: %s", err)
            return None, {"base": "cannot_connect"}
        except ThzError as err:
            # Port opened but the pump did not answer — most likely another
            # reader (FHEM?) still owns the line or wrong port.
            _LOGGER.debug("validation: no response: %s", err)
            return None, {"base": "no_response"}
        except Exception:
            _LOGGER.exception("validation: unexpected error")
            return None, {"base": "unknown"}
        finally:
            await client.disconnect()


def _interval_selector(maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=60,
            max=maximum,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="s",
        )
    )


class LwzThzOptionsFlow(OptionsFlow):
    """Poll intervals and feature toggles."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    OPT_INTERVAL_STATUS,
                    default=options.get(OPT_INTERVAL_STATUS, DEFAULT_INTERVAL_STATUS),
                ): _interval_selector(3600),
                vol.Required(
                    OPT_INTERVAL_PARAMS,
                    default=options.get(OPT_INTERVAL_PARAMS, DEFAULT_INTERVAL_PARAMS),
                ): _interval_selector(86400),
                vol.Required(
                    OPT_INTERVAL_HISTORY,
                    default=options.get(OPT_INTERVAL_HISTORY, DEFAULT_INTERVAL_HISTORY),
                ): _interval_selector(86400),
                vol.Required(
                    OPT_INTERVAL_ENERGY,
                    default=options.get(OPT_INTERVAL_ENERGY, DEFAULT_INTERVAL_ENERGY),
                ): _interval_selector(604800),
                vol.Required(
                    OPT_ENABLE_HC2, default=options.get(OPT_ENABLE_HC2, False)
                ): BooleanSelector(),
                vol.Required(
                    OPT_ENABLE_SOLAR, default=options.get(OPT_ENABLE_SOLAR, False)
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
