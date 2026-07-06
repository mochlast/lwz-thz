"""Framing tests: checksum, byte stuffing, frame encode/decode."""

import pytest

from thzprotocol import framing
from thzprotocol.errors import (
    ThzChecksumError,
    ThzNakError,
    ThzProtocolError,
    ThzTimingError,
    ThzUnknownCommandError,
    ThzUnknownRegisterError,
)


def _response(
    command: bytes, data: bytes, *, header: bytes = framing.HEADER_GET
) -> bytes:
    """Build a valid raw response frame the way the device would."""
    chk = framing.checksum(header, command + data)
    return header + framing.escape(bytes((chk,)) + command + data) + framing.FOOTER


class TestChecksum:
    def test_get_firmware_request(self) -> None:
        # 01 00 FE FD 10 03 is the canonical sFirmware request.
        assert framing.checksum(framing.HEADER_GET, b"\xfd") == 0xFE

    def test_wraps_mod_256(self) -> None:
        assert (
            framing.checksum(framing.HEADER_GET, b"\xff\xff\xff") == (1 + 3 * 255) % 256
        )


class TestEscaping:
    @pytest.mark.parametrize(
        ("plain", "escaped"),
        [
            (b"\x10", b"\x10\x10"),
            (b"\x2b", b"\x2b\x18"),
            (b"\x10\x2b", b"\x10\x10\x2b\x18"),
            (b"\x01\x02\x03", b"\x01\x02\x03"),
            (b"\x10\x10", b"\x10\x10\x10\x10"),
        ],
    )
    def test_escape(self, plain: bytes, escaped: bytes) -> None:
        assert framing.escape(plain) == escaped
        assert framing.unescape(escaped) == plain

    def test_roundtrip_all_byte_values(self) -> None:
        data = bytes(range(256)) + b"\x10\x2b\x10\x10\x2b\x2b\x03\x18"
        assert framing.unescape(framing.escape(data)) == data


class TestEncodeFrame:
    def test_firmware_request(self) -> None:
        assert framing.encode_frame(b"\xfd") == b"\x01\x00\xfe\xfd\x10\x03"

    def test_sglobal_request(self) -> None:
        assert framing.encode_frame(b"\xfb") == b"\x01\x00\xfc\xfb\x10\x03"

    def test_set_header(self) -> None:
        frame = framing.encode_frame(b"\x0b\x00\x05\x00\xdc", is_set=True)
        assert frame.startswith(b"\x01\x80")
        assert frame.endswith(b"\x10\x03")

    def test_escapes_checksum_byte(self) -> None:
        # Command 0x0F yields checksum 0x10, which must be stuffed.
        assert framing.encode_frame(b"\x0f") == b"\x01\x00\x10\x10\x0f\x10\x03"

    def test_escapes_command_bytes(self) -> None:
        frame = framing.encode_frame(b"\x2b")
        assert frame == b"\x01\x00\x2c\x2b\x18\x10\x03"


class TestDecodeFrame:
    def test_happy_path_payload_keeps_checksum_and_echo(self) -> None:
        raw = _response(b"\xfb", b"\x00\xe3\x01\x13")
        payload = framing.decode_frame(raw)
        # Payload = checksum + command echo + data, so FHEM nibble offsets apply.
        assert payload[1:] == b"\xfb\x00\xe3\x01\x13"
        assert payload[0] == framing.checksum(framing.HEADER_GET, payload[1:])

    def test_unescapes_stuffed_data(self) -> None:
        raw = _response(b"\xfb", b"\x10\x2b\x03")
        assert framing.decode_frame(raw)[1:] == b"\xfb\x10\x2b\x03"

    def test_nak(self) -> None:
        with pytest.raises(ThzNakError):
            framing.decode_frame(b"\x15")

    @pytest.mark.parametrize(
        ("header", "exception"),
        [
            (b"\x01\x01", ThzTimingError),
            (b"\x01\x02", ThzChecksumError),
            (b"\x01\x03", ThzUnknownCommandError),
            (b"\x01\x04", ThzUnknownRegisterError),
        ],
    )
    def test_error_headers(self, header: bytes, exception: type[Exception]) -> None:
        with pytest.raises(exception):
            framing.decode_frame(header + b"\x00" + framing.FOOTER)

    def test_checksum_mismatch(self) -> None:
        raw = _response(b"\xfb", b"\x00\xe3")
        corrupted = raw[:2] + bytes((raw[2] ^ 0x01,)) + raw[3:]
        with pytest.raises(ThzChecksumError):
            framing.decode_frame(corrupted)

    def test_set_response_skips_checksum(self) -> None:
        raw = b"\x01\x80\x00\x0b\x00\x05\x10\x03"  # bogus checksum, still ok
        assert framing.decode_frame(raw) == b"\x00\x0b\x00\x05"

    def test_unknown_header(self) -> None:
        with pytest.raises(ThzProtocolError):
            framing.decode_frame(b"\x02\x42\x00\x00\x10\x03")
