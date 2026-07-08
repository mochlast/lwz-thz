"""Poll scheduler: one coordinator, per-group intervals, one serial line.

There is exactly one serial interface that must be served strictly
sequentially, so a single coordinator with a tick-based group scheduler is
used instead of one coordinator per interval. The coordinator keeps a
persistent data dict: groups retain their last values until they are due
again. Data keys are qualified as ``<block>.<field>`` / ``energy.<meter>``.

Program writes are staged: the new window is pushed into the data
immediately (optimistic, all three entities of a slot update at once) and
the ~10-telegram serial write runs debounced in the background, so rapid
UI clicks coalesce into one write. Verified read-backs are shielded
against poll ticks that read the register before the write finished.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta
from functools import partial
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
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
    WRITE_DEBOUNCE,
)
from .thzprotocol import ThzClient, ThzError, ThzNotConnectedError
from .thzprotocol.programs import PROGRAM_SLOTS, normalize_slot
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


def _program_data(slot_key: str, start, end) -> dict[str, Any]:
    return {
        f"prog.{slot_key}.start": start.strftime("%H:%M") if start else None,
        f"prog.{slot_key}.end": end.strftime("%H:%M") if end else None,
    }


@dataclass
class ProgramRead:
    """Read one weekly program window (Mo-So, Monday register)."""

    slot_key: str

    async def execute(self, client: ThzClient) -> dict[str, Any]:
        start, end = await client.read_program(self.slot_key)
        return _program_data(self.slot_key, start, end)


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
            reads=tuple(ParamRead(key) for key in WRITE_PARAMS)
            + tuple(ProgramRead(key) for key in PROGRAM_SLOTS),
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
        # Staged program writes: slot -> target window, debounce timer, lock.
        self._prog_pending: dict[str, tuple[dt_time | None, dt_time | None]] = {}
        self._prog_flush_cancel: dict[str, CALLBACK_TYPE] = {}
        self._prog_locks: dict[str, asyncio.Lock] = {}
        # Verified write results, shielded against in-flight poll ticks.
        self._write_overrides: dict[str, tuple[float, Any]] = {}
        # Last enabled window per slot ("HH:MM" strings), for turn_on restore.
        self._last_windows: dict[str, tuple[str, str]] = {}

    async def _async_setup(self) -> None:
        try:
            await self.client.connect()
            self.firmware = await self.client.get_firmware()
        except ThzError as err:
            raise UpdateFailed(f"cannot reach heat pump: {err}") from err
        _LOGGER.info("Connected to heat pump, firmware %s", self.firmware)

    async def _async_update_data(self) -> dict[str, Any]:
        tick_start = time.monotonic()
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

        # A write that finished while this tick was collecting reads is newer
        # than whatever the tick read before it — the read-back wins.
        for key, (stamp, value) in list(self._write_overrides.items()):
            if stamp >= tick_start:
                data[key] = value
            else:
                del self._write_overrides[key]
        # Staged-but-unwritten program changes always win over polled state.
        for slot_key, (start, end) in self._prog_pending.items():
            data.update(_program_data(slot_key, start, end))
        self._remember_windows(data)
        return data

    async def async_shutdown(self) -> None:
        for cancel in self._prog_flush_cancel.values():
            cancel()
        self._prog_flush_cancel.clear()
        if self._prog_pending:
            _LOGGER.warning(
                "shutdown drops unwritten program changes: %s",
                ", ".join(self._prog_pending),
            )
            self._prog_pending.clear()
        await super().async_shutdown()

    def _push_write_data(self, updates: dict[str, Any]) -> None:
        """Push verified values and shield them from in-flight poll merges."""
        stamp = time.monotonic()
        for key, value in updates.items():
            self._write_overrides[key] = (stamp, value)
        self._remember_windows(updates)
        data = dict(self.data or {})
        data.update(updates)
        self.async_set_updated_data(data)

    def _remember_windows(self, data: dict[str, Any]) -> None:
        for slot_key in PROGRAM_SLOTS:
            start = data.get(f"prog.{slot_key}.start")
            end = data.get(f"prog.{slot_key}.end")
            if start and end:
                self._last_windows[slot_key] = (start, end)

    def last_window(self, slot_key: str) -> tuple[str, str] | None:
        """Last known enabled window of a slot as ``HH:MM`` strings."""
        return self._last_windows.get(slot_key)

    async def async_write_param(self, param_key: str, value: float | str) -> None:
        """Write a parameter and push the verified read-back into the data."""
        try:
            readback = await self.client.write_param(param_key, value)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        except ThzError as err:
            raise HomeAssistantError(f"writing {param_key} failed: {err}") from err
        self._push_write_data({f"param.{param_key}": readback})

    def stage_program(
        self, slot_key: str, start: dt_time | None, end: dt_time | None
    ) -> None:
        """Apply a program window optimistically and debounce the write.

        All entities of the slot (switch, start, end) update immediately;
        the ~10-telegram serial write starts after WRITE_DEBOUNCE seconds
        of click silence, so rapid changes coalesce into one write.
        """
        start, end = normalize_slot(start, end)
        self._prog_pending[slot_key] = (start, end)
        data = dict(self.data or {})
        data.update(_program_data(slot_key, start, end))
        self.async_set_updated_data(data)
        if (cancel := self._prog_flush_cancel.pop(slot_key, None)) is not None:
            cancel()
        self._prog_flush_cancel[slot_key] = async_call_later(
            self.hass, WRITE_DEBOUNCE, partial(self._async_flush_program, slot_key)
        )

    async def _async_flush_program(self, slot_key: str, _now: datetime) -> None:
        self._prog_flush_cancel.pop(slot_key, None)
        lock = self._prog_locks.setdefault(slot_key, asyncio.Lock())
        async with lock:
            target = self._prog_pending.get(slot_key)
            if target is None:
                return
            try:
                readback = await self.client.write_program(slot_key, *target)
            except ThzError as err:
                _LOGGER.warning("Writing program %s failed: %s", slot_key, err)
                if self._prog_pending.get(slot_key) != target:
                    return  # a newer change is staged; its flush will retry
                self._prog_pending.pop(slot_key, None)
                await self._async_reread_program(slot_key)
                return
            if self._prog_pending.get(slot_key) != target:
                return  # superseded while writing; the newer flush follows
            self._prog_pending.pop(slot_key, None)
            self._push_write_data(_program_data(slot_key, *readback))

    async def _async_reread_program(self, slot_key: str) -> None:
        """Revert optimistic state to device truth after a failed write."""
        try:
            start, end = await self.client.read_program(slot_key)
        except ThzError:
            return  # stays optimistic until the next params poll corrects it
        self._push_write_data(_program_data(slot_key, start, end))
