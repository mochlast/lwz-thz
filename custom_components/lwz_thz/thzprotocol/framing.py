r"""Frame encoding/decoding for the THZ serial protocol (pure functions).

Frame layout (both directions)::

    01 00|80  CHK  CMD [DATA...]  10 03
    \______/  \______________/    \___/
     header    escaped region     footer

- Header ``01 00`` = get, ``01 80`` = set. Error responses carry ``01 01``
  (timing), ``01 02`` (CRC error in request), ``01 03`` (unknown command),
  ``01 04`` (unknown register). A bare ``15`` is a NAK.
- CHK = sum of all bytes (header + CMD + DATA, checksum position excluded,
  footer excluded) mod 256.
- Byte stuffing inside the escaped region: ``10 -> 10 10``, ``2B -> 2B 18``.

Reference: FHEM 00_THZ.pm THZ_encodecommand / THZ_decode / THZ_checksum /
THZ_replacebytes.
"""

from __future__ import annotations

from .errors import (
    ThzChecksumError,
    ThzNakError,
    ThzProtocolError,
    ThzTimingError,
    ThzUnknownCommandError,
    ThzUnknownRegisterError,
)

STX = 0x02
ETX = 0x03
DLE = 0x10
NAK = 0x15

HEADER_GET = bytes((0x01, 0x00))
HEADER_SET = bytes((0x01, 0x80))
FOOTER = bytes((DLE, ETX))

_ERROR_HEADERS: dict[bytes, tuple[type[ThzProtocolError], str]] = {
    bytes((0x01, 0x01)): (ThzTimingError, "device reported timing issue"),
    bytes((0x01, 0x02)): (ThzChecksumError, "device reported CRC error in request"),
    bytes((0x01, 0x03)): (ThzUnknownCommandError, "device does not know this command"),
    bytes((0x01, 0x04)): (
        ThzUnknownRegisterError,
        "device does not know this register",
    ),
}


def checksum(header: bytes, body: bytes) -> int:
    """Checksum over header and body (command echo + data)."""
    return (sum(header) + sum(body)) % 256


def escape(data: bytes) -> bytes:
    """Apply byte stuffing: 10 -> 10 10, 2B -> 2B 18."""
    out = bytearray()
    for byte in data:
        out.append(byte)
        if byte == DLE:
            out.append(DLE)
        elif byte == 0x2B:
            out.append(0x18)
    return bytes(out)


def unescape(data: bytes) -> bytes:
    """Reverse byte stuffing: 10 10 -> 10, 2B 18 -> 2B."""
    out = bytearray()
    i = 0
    length = len(data)
    while i < length:
        byte = data[i]
        out.append(byte)
        if i + 1 < length and (
            (byte == DLE and data[i + 1] == DLE)
            or (byte == 0x2B and data[i + 1] == 0x18)
        ):
            i += 2
        else:
            i += 1
    return bytes(out)


def encode_frame(command: bytes, *, is_set: bool = False) -> bytes:
    """Build a request frame for a command (register address [+ set data])."""
    header = HEADER_SET if is_set else HEADER_GET
    chk = checksum(header, command)
    return header + escape(bytes((chk,)) + command) + FOOTER


def decode_frame(raw: bytes) -> bytes:
    """Validate a raw response frame and return its payload.

    The payload starts with the checksum byte followed by the command echo
    and data — exactly the string FHEM's THZ_decode hands to the parser, so
    all FHEM %parsinghash offsets apply unchanged to ``payload.hex()``.
    """
    data = unescape(raw)
    if data == bytes((NAK,)):
        raise ThzNakError("NAK received instead of response frame")
    if len(data) < 4:
        raise ThzProtocolError(f"response frame too short: {data.hex(' ')}")

    header = data[:2]
    if header in _ERROR_HEADERS:
        exc_type, message = _ERROR_HEADERS[header]
        raise exc_type(message)
    if header not in (HEADER_GET, HEADER_SET):
        raise ThzProtocolError(f"unknown response header: {data.hex(' ')}")

    if not data.endswith(FOOTER):
        raise ThzProtocolError(f"response frame without footer: {data.hex(' ')}")
    payload = data[2:-2]

    # FHEM verifies the checksum for get responses only.
    if header == HEADER_GET:
        expected = checksum(header, payload[1:])
        if payload[0] != expected:
            raise ThzChecksumError(
                f"checksum mismatch: got {payload[0]:02X}, expected {expected:02X}"
            )
    return payload
