"""High-level client: serialization, reconnect with backoff, block reads.

Design rules (lessons from the unstable first migration attempt):

- Strictly one telegram at a time (``asyncio.Lock``) with a minimum gap
  between telegrams, so the heat pump controller is never overwhelmed.
- Every transport-level error tears the connection down *completely*; the
  next request reconnects lazily, gated by an exponential backoff window.
- Protocol-level errors (NAK, CRC, timeout) keep the connection and only
  fail the current request, after a short settle pause.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time
from typing import Any

from .errors import (
    ThzConnectionError,
    ThzNotConnectedError,
    ThzProtocolError,
    ThzWriteVerifyError,
)
from .programs import PROGRAM_SLOTS, decode_slot, encode_slot, normalize_slot
from .protocol import ThzProtocol
from .registers import BLOCKS, ENERGY, parse_block, parse_energy_register
from .timing import (
    ERROR_SETTLE,
    INTER_REQUEST_GAP,
    RECONNECT_BACKOFF,
    SET_READBACK_DELAY,
)
from .transport import Transport
from .writeparams import WRITE_PARAMS, decode_value, encode_value, values_match

_LOGGER = logging.getLogger(__name__)


class ThzClient:
    """Async client for one Stiebel Eltron LWZ / Tecalor THZ device."""

    def __init__(self, transport_factory: Callable[[], Transport]) -> None:
        self._transport_factory = transport_factory
        self._transport: Transport | None = None
        self._protocol: ThzProtocol | None = None
        self._lock = asyncio.Lock()
        self._last_request_end = 0.0
        self._fail_streak = 0
        self._backoff_until = 0.0

    @property
    def is_connected(self) -> bool:
        return self._transport is not None and self._transport.is_open

    async def connect(self) -> None:
        async with self._lock:
            await self._connect_locked()

    async def disconnect(self) -> None:
        async with self._lock:
            await self._teardown_locked()

    async def _connect_locked(self) -> None:
        if self.is_connected:
            return
        transport = self._transport_factory()
        try:
            await transport.open()
        except ThzConnectionError:
            self._register_failure()
            raise
        self._transport = transport
        self._protocol = ThzProtocol(transport)
        if self._fail_streak:
            _LOGGER.info(
                "reconnected to %s after %d failure(s)", transport, self._fail_streak
            )
        else:
            _LOGGER.debug("connected to %s", transport)
        self._fail_streak = 0
        self._backoff_until = 0.0

    async def _teardown_locked(self) -> None:
        transport, self._transport, self._protocol = self._transport, None, None
        if transport is not None:
            await transport.close()

    def _register_failure(self) -> None:
        delay = RECONNECT_BACKOFF[min(self._fail_streak, len(RECONNECT_BACKOFF) - 1)]
        self._fail_streak += 1
        self._backoff_until = time.monotonic() + delay
        _LOGGER.debug(
            "connection failure #%d, backing off %.0fs", self._fail_streak, delay
        )

    async def _ensure_connected_locked(self) -> None:
        if self.is_connected:
            return
        if time.monotonic() < self._backoff_until:
            raise ThzNotConnectedError(
                f"reconnecting in {self._backoff_until - time.monotonic():.0f}s "
                f"(failure #{self._fail_streak})"
            )
        await self._connect_locked()

    async def request(self, command: bytes | str, *, is_set: bool = False) -> bytes:
        """Run one serialized telegram cycle and return the decoded payload."""
        if isinstance(command, str):
            command = bytes.fromhex(command)
        async with self._lock:
            await self._ensure_connected_locked()
            gap = INTER_REQUEST_GAP - (time.monotonic() - self._last_request_end)
            if gap > 0:
                await asyncio.sleep(gap)
            assert self._protocol is not None
            try:
                return await self._protocol.request(command, is_set=is_set)
            except ThzConnectionError:
                await self._teardown_locked()
                self._register_failure()
                raise
            except ThzProtocolError:
                await asyncio.sleep(ERROR_SETTLE)
                raise
            finally:
                self._last_request_end = time.monotonic()

    async def read_block(self, block_key: str) -> dict[str, Any]:
        """Read and parse one register block, e.g. ``sGlobal``."""
        block = BLOCKS[block_key]
        payload = await self.request(block.command)
        return parse_block(block, payload)

    async def read_energy(self, energy_key: str) -> int:
        """Read one energy meter (two telegrams, ``high * 1000 + low``)."""
        meter = ENERGY[energy_key]
        low = parse_energy_register(await self.request(meter.cmd_low))
        high = parse_energy_register(await self.request(meter.cmd_high))
        return high * 1000 + low

    async def read_param(self, param_key: str) -> float | int | str:
        """Read the current value of a writable parameter."""
        param = WRITE_PARAMS[param_key]
        payload = await self.request(param.command)
        return decode_value(param, payload)

    async def write_param(
        self, param_key: str, value: float | str
    ) -> float | int | str:
        """Write a parameter and verify it by reading it back (FHEM THZ_Set).

        Raises ``ValueError`` for out-of-range values and
        ``ThzWriteVerifyError`` when the device reports success but the
        read-back does not match the requested value.
        """
        param = WRITE_PARAMS[param_key]
        encoded = encode_value(param, value)
        await self.request(param.command + encoded, is_set=True)
        await asyncio.sleep(SET_READBACK_DELAY)
        readback = await self.read_param(param_key)
        if not values_match(param, value, readback):
            raise ThzWriteVerifyError(
                f"{param_key}: wrote {value!r}, device reports {readback!r}"
            )
        _LOGGER.info("wrote %s = %r (verified)", param_key, readback)
        return readback

    async def read_program(self, slot_key: str):
        """Read a weekly program window (Monday register) -> (start, end)."""
        slot = PROGRAM_SLOTS[slot_key]
        payload = await self.request(slot.read_command)
        return decode_slot(payload)

    async def write_program(self, slot_key: str, start, end):
        """Write a program window to the Mo-So group and all day registers.

        ~10 telegrams (FHEM does the same for Mo-So sets); afterwards the
        Monday register is read back and verified.
        """
        slot = PROGRAM_SLOTS[slot_key]
        value_hex = encode_slot(start, end)
        for command in slot.write_commands:
            await self.request(command + value_hex, is_set=True)
        await asyncio.sleep(SET_READBACK_DELAY)
        readback = await self.read_program(slot_key)
        expected = normalize_slot(start, end)
        if readback != expected:
            raise ThzWriteVerifyError(
                f"program {slot_key}: wrote {expected}, device reports {readback}"
            )
        _LOGGER.info("wrote program %s = %s (verified)", slot_key, readback)
        return readback

    async def get_firmware(self) -> str:
        """Read the firmware version, e.g. ``5.39``."""
        values = await self.read_block("sFirmware")
        return values["firmware_version"].lstrip("0")
