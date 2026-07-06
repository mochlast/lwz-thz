"""Byte transports: serial (USB) and TCP (ser2net).

All reads use exact framing primitives (``readexactly`` / ``readuntil``) —
never ``read(n)``, which returns early and caused framing races in earlier
implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import contextlib

from .errors import ThzConnectionError, ThzTimeoutError

_FLUSH_IDLE = 0.02  # port considered drained after this much silence
_READ_LIMIT = 4096  # StreamReader buffer limit; frames are < 200 bytes


class Transport(ABC):
    """A connected byte stream to the heat pump."""

    _reader: asyncio.StreamReader | None = None
    _writer: asyncio.StreamWriter | None = None

    @abstractmethod
    async def _open_stream(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Open the underlying connection."""

    @property
    def is_open(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def open(self) -> None:
        try:
            self._reader, self._writer = await self._open_stream()
        except (TimeoutError, OSError) as err:
            raise ThzConnectionError(f"cannot open {self}: {err}") from err

    async def close(self) -> None:
        writer, self._reader, self._writer = self._writer, None, None
        if writer is None:
            return
        writer.close()
        with contextlib.suppress(TimeoutError, OSError):  # already dead — fine
            await writer.wait_closed()

    def _require_reader(self) -> asyncio.StreamReader:
        if self._reader is None:
            raise ThzConnectionError(f"{self} is not open")
        return self._reader

    async def write(self, data: bytes) -> None:
        if self._writer is None:
            raise ThzConnectionError(f"{self} is not open")
        try:
            self._writer.write(data)
            await self._writer.drain()
        except (OSError, ConnectionError) as err:
            raise ThzConnectionError(f"write failed: {err}") from err

    async def read_exactly(self, count: int, timeout: float) -> bytes:
        reader = self._require_reader()
        try:
            return await asyncio.wait_for(reader.readexactly(count), timeout)
        except TimeoutError as err:
            raise ThzTimeoutError(
                f"no response within {timeout:.1f}s (expected {count} byte(s))"
            ) from err
        except asyncio.IncompleteReadError as err:
            raise ThzConnectionError("connection closed while reading") from err
        except (OSError, ConnectionError) as err:
            raise ThzConnectionError(f"read failed: {err}") from err

    async def read_until(self, separator: bytes, timeout: float) -> bytes:
        reader = self._require_reader()
        try:
            return await asyncio.wait_for(reader.readuntil(separator), timeout)
        except TimeoutError as err:
            raise ThzTimeoutError(
                f"incomplete frame: separator {separator.hex(' ')} not seen "
                f"within {timeout:.1f}s"
            ) from err
        except asyncio.IncompleteReadError as err:
            raise ThzConnectionError("connection closed while reading") from err
        except asyncio.LimitOverrunError as err:
            raise ThzConnectionError(f"read buffer overrun: {err}") from err
        except (OSError, ConnectionError) as err:
            raise ThzConnectionError(f"read failed: {err}") from err

    async def flush_input(self) -> None:
        """Discard stale bytes left over from an aborted previous exchange."""
        reader = self._require_reader()
        while True:
            try:
                data = await asyncio.wait_for(reader.read(_READ_LIMIT), _FLUSH_IDLE)
            except TimeoutError:
                return
            except (OSError, ConnectionError) as err:
                raise ThzConnectionError(f"read failed: {err}") from err
            if not data:
                raise ThzConnectionError("connection closed while flushing")


class SerialTransport(Transport):
    """Serial port transport (also accepts pyserial URL handlers)."""

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        self._port = port
        self._baudrate = baudrate

    def __str__(self) -> str:
        return f"serial {self._port}@{self._baudrate}"

    async def _open_stream(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        try:
            from serial_asyncio_fast import open_serial_connection
        except ImportError:  # pragma: no cover - fallback for dev environments
            from serial_asyncio import open_serial_connection

        import serial

        try:
            return await open_serial_connection(
                url=self._port,
                baudrate=self._baudrate,
                bytesize=8,
                parity="N",
                stopbits=1,
                limit=_READ_LIMIT,
            )
        except serial.SerialException as err:
            raise ThzConnectionError(f"cannot open {self}: {err}") from err


class TcpTransport(Transport):
    """TCP transport for ser2net-style serial-over-network bridges."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def __str__(self) -> str:
        return f"tcp {self._host}:{self._port}"

    async def _open_stream(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port, limit=_READ_LIMIT),
            timeout=10,
        )
