"""The per-telegram handshake state machine (FHEM THZ_Get_Comunication).

One request/response cycle::

    -> 02                 (STX: request to send)
    <- 10                 (DLE: clear to send; 15 = NAK)
    -> 01 00|80 CHK CMD 10 03
    <- 10 02  (or bare 02; some firmwares send the 02 slightly delayed)
    -> 10
    <- 01 00|80 CHK CMD DATA 10 03
    -> 10                 (final ACK)
"""

from __future__ import annotations

import time

from .errors import ThzNakError, ThzProtocolError
from .framing import DLE, FOOTER, NAK, STX, decode_frame, encode_frame
from .timing import ACK_TIMEOUT, FRAME_TIMEOUT
from .transport import Transport

_DLE_BYTES = bytes((DLE,))
_STX_BYTES = bytes((STX,))


def _footer_is_genuine(buffer: bytes) -> bool:
    """True if the trailing ``10 03`` is a real footer, not stuffed data.

    Inside the frame every data ``10`` is stuffed to ``10 10``. Count the run
    of ``10`` bytes immediately before the final ``03``: an odd count means
    the last ``10`` is unpaired and thus a genuine DLE starting the footer;
    an even count means all of them are escape pairs and the ``03`` is a
    plain data byte.
    """
    run = 0
    for byte in reversed(buffer[:-1]):
        if byte != DLE:
            break
        run += 1
    return run % 2 == 1


class ThzProtocol:
    """Runs handshake cycles on a connected transport."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def request(self, command: bytes, *, is_set: bool = False) -> bytes:
        """Execute one full telegram cycle; returns the decoded payload."""
        transport = self._transport
        await transport.flush_input()

        # Step 0: announce request.
        await transport.write(_STX_BYTES)
        await self._expect_dle("step 0 (STX)")

        # Step 1: send the framed command.
        await transport.write(encode_frame(command, is_set=is_set))
        ack = await transport.read_exactly(1, ACK_TIMEOUT)
        if ack == bytes((NAK,)):
            raise ThzNakError("device rejected command (step 1)")
        if ack == _DLE_BYTES:
            follow = await transport.read_exactly(1, ACK_TIMEOUT)
            if follow != _STX_BYTES:
                raise ThzProtocolError(
                    f"step 1: expected STX after DLE, got {follow.hex()}"
                )
        elif ack != _STX_BYTES:
            raise ThzProtocolError(f"step 1: unexpected response {ack.hex()}")

        # Step 2: clear to receive, read the frame, final ACK.
        await transport.write(_DLE_BYTES)
        raw = await self._read_frame()
        await transport.write(_DLE_BYTES)
        return decode_frame(raw)

    async def _expect_dle(self, step: str) -> None:
        byte = await self._transport.read_exactly(1, ACK_TIMEOUT)
        if byte == bytes((NAK,)):
            raise ThzNakError(f"device sent NAK in {step}")
        if byte != _DLE_BYTES:
            raise ThzProtocolError(f"{step}: expected DLE, got {byte.hex()}")

    async def _read_frame(self) -> bytes:
        """Read one raw frame, reassembling until a genuine footer arrives."""
        buffer = bytearray()
        deadline = time.monotonic() + FRAME_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ThzProtocolError(
                    f"frame not completed within {FRAME_TIMEOUT:.1f}s: "
                    f"{bytes(buffer).hex(' ')}"
                )
            buffer += await self._transport.read_until(FOOTER, remaining)
            if _footer_is_genuine(buffer):
                return bytes(buffer)
