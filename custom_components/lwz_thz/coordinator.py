"""Poll scheduler: one coordinator, per-group intervals, one serial line.

There is exactly one serial interface that must be served strictly
sequentially, so a single coordinator with a tick-based group scheduler is
used instead of one coordinator per interval. The coordinator keeps a
persistent data dict: groups retain their last values until they are due
again. Data keys are qualified as ``<block>.<field>`` / ``energy.<meter>``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_INTERVAL_ENERGY,
    DEFAULT_INTERVAL_HISTORY,
    DEFAULT_INTERVAL_PARAMS,
    DEFAULT_INTERVAL_STATUS,
    DOMAIN,
    OPT_ENABLE_HC2,
    OPT_ENABLE_SOLAR,
    OPT_INTERVAL_ENERGY,
    OPT_INTERVAL_HISTORY,
    OPT_INTERVAL_PARAMS,
    OPT_INTERVAL_STATUS,
    TICK_INTERVAL,
)
from .thzprotocol import ThzClient, ThzError, ThzNotConnectedError
from .thzprotocol.registers import ENERGY
from .thzprotocol.timing import GROUP_ERROR_BACKOFF, MIN_POLL_INTERVAL
from .thzprotocol.writeparams import WRITE_PARAMS

_LOGGER = logging.getLogger(__name__)

# Entities stay available (showing last values) through short outages; only a
# connection that stays down this long marks them unavailable.
STALE_CONNECTION_TIMEOUT = 900

type ThzConfigEntry = ConfigEntry[ThzCoordinator]


@dataclass
class BlockRead:
    """Read one register block."""

    block_key: str

    async def execute(self, client: ThzClient) -> dict[str, Any]:
        values = await client.read_block(self.block_key)
        return {f"{self.block_key}.{key}": value for key, value in values.items()}


@dataclass
class EnergyRead:
    """Read one energy meter (two telegrams)."""

    meter_key: str

    async def execute(self, client: ThzClient) -> dict[str, Any]:
        return {f"energy.{self.meter_key}": await client.read_energy(self.meter_key)}


@dataclass
class ParamRead:
    """Read the current value of one writable parameter."""

    param_key: str

    async def execute(self, client: ThzClient) -> dict[str, Any]:
        return {f"param.{self.param_key}": await client.read_param(self.param_key)}


@dataclass
class PollGroup:
    """A set of reads sharing one poll interval."""

    key: str
    interval: int
    reads: tuple[BlockRead | EnergyRead, ...]
    next_due: float = 0.0  # monotonic; 0 = due immediately
    consecutive_errors: int = field(default=0, compare=False)


def build_groups(options: dict[str, Any]) -> list[PollGroup]:
    """Build the poll groups from config entry options."""
    status_blocks = ["sGlobal", "sHC1", "sDHW", "sControl", "sFan", "sDisplay"]
    if options.get(OPT_ENABLE_HC2, False):
        status_blocks.append("sHC2")
    if options.get(OPT_ENABLE_SOLAR, False):
        status_blocks.append("sSol")

    def interval(option_key: str, default: int) -> int:
        return max(int(options.get(option_key, default)), MIN_POLL_INTERVAL)

    return [
        PollGroup(
            key="status",
            interval=interval(OPT_INTERVAL_STATUS, DEFAULT_INTERVAL_STATUS),
            reads=tuple(BlockRead(key) for key in status_blocks),
        ),
        PollGroup(
            key="params",
            interval=interval(OPT_INTERVAL_PARAMS, DEFAULT_INTERVAL_PARAMS),
            reads=tuple(ParamRead(key) for key in WRITE_PARAMS),
        ),
        PollGroup(
            key="history",
            interval=interval(OPT_INTERVAL_HISTORY, DEFAULT_INTERVAL_HISTORY),
            reads=(BlockRead("sHistory"), BlockRead("sLast10errors")),
        ),
        PollGroup(
            key="energy",
            interval=interval(OPT_INTERVAL_ENERGY, DEFAULT_INTERVAL_ENERGY),
            reads=tuple(EnergyRead(key) for key in ENERGY),
        ),
    ]


class ThzCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator driving all reads over the shared client."""

    config_entry: ThzConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ThzConfigEntry,
        client: ThzClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=TICK_INTERVAL),
        )
        self.client = client
        self.firmware: str = "unknown"
        self._groups = build_groups(dict(config_entry.options))
        self._disconnected_since: float | None = None

    async def _async_setup(self) -> None:
        try:
            await self.client.connect()
            self.firmware = await self.client.get_firmware()
        except ThzError as err:
            raise UpdateFailed(f"cannot reach heat pump: {err}") from err
        _LOGGER.info("Connected to heat pump, firmware %s", self.firmware)

    async def _async_update_data(self) -> dict[str, Any]:
        data = dict(self.data or {})
        now = time.monotonic()
        any_success = False

        for group in self._groups:
            if now < group.next_due:
                continue
            try:
                for read in group.reads:
                    data.update(await read.execute(self.client))
            except ThzNotConnectedError:
                # Reconnect backoff active — skip the whole tick quietly.
                break
            except ThzError as err:
                group.consecutive_errors += 1
                group.next_due = time.monotonic() + GROUP_ERROR_BACKOFF
                _LOGGER.warning(
                    "Poll group '%s' failed (%d in a row, retry in %ds): %s",
                    group.key,
                    group.consecutive_errors,
                    GROUP_ERROR_BACKOFF,
                    err,
                )
            else:
                group.next_due = time.monotonic() + group.interval
                group.consecutive_errors = 0
                any_success = True

        if any_success or self.client.is_connected:
            self._disconnected_since = None
        elif self._disconnected_since is None:
            self._disconnected_since = time.monotonic()

        if not data:
            raise UpdateFailed("no data received from heat pump yet")
        if (
            self._disconnected_since is not None
            and time.monotonic() - self._disconnected_since > STALE_CONNECTION_TIMEOUT
        ):
            raise UpdateFailed("connection to heat pump lost")
        return data

    async def async_write_param(self, param_key: str, value: float | str) -> None:
        """Write a parameter and push the verified read-back into the data."""
        try:
            readback = await self.client.write_param(param_key, value)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        except ThzError as err:
            raise HomeAssistantError(f"writing {param_key} failed: {err}") from err
        data = dict(self.data or {})
        data[f"param.{param_key}"] = readback
        self.async_set_updated_data(data)
