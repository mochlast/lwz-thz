"""A scriptable in-memory transport for handshake tests."""

from __future__ import annotations

from collections import deque

from thzprotocol.errors import ThzConnectionError, ThzTimeoutError
from thzprotocol.transport import Transport


class FakeTransport(Transport):
    """Feeds pre-scripted incoming chunks and records every write.

    Chunks are handed out lazily: a read primitive only pulls the next chunk
    when the current buffer cannot satisfy it, so chunk boundaries simulate
    fragmented arrival on the wire.
    """

    def __init__(self, incoming: list[bytes] | None = None) -> None:
        self.incoming: deque[bytes] = deque(incoming or [])
        self.writes: list[bytes] = []
        self._buffer = bytearray()
        self._open = False
        self.fail_reads_with: Exception | None = None

    def __str__(self) -> str:
        return "fake"

    async def _open_stream(self):  # pragma: no cover - not used
        raise NotImplementedError

    @property
    def is_open(self) -> bool:
        return self._open

    async def open(self) -> None:
        self._open = True

    async def close(self) -> None:
        self._open = False

    async def write(self, data: bytes) -> None:
        if not self._open:
            raise ThzConnectionError("fake transport is not open")
        self.writes.append(data)

    def _pull(self) -> bool:
        if not self.incoming:
            return False
        self._buffer += self.incoming.popleft()
        return True

    def _check_failure(self) -> None:
        if self.fail_reads_with is not None:
            raise self.fail_reads_with

    async def read_exactly(self, count: int, timeout: float) -> bytes:
        self._check_failure()
        while len(self._buffer) < count:
            if not self._pull():
                raise ThzTimeoutError(f"fake: no data for read_exactly({count})")
        result = bytes(self._buffer[:count])
        del self._buffer[:count]
        return result

    async def read_until(self, separator: bytes, timeout: float) -> bytes:
        self._check_failure()
        while True:
            index = self._buffer.find(separator)
            if index != -1:
                end = index + len(separator)
                result = bytes(self._buffer[:end])
                del self._buffer[:end]
                return result
            if not self._pull():
                raise ThzTimeoutError("fake: separator never arrived")

    async def flush_input(self) -> None:
        self._check_failure()
