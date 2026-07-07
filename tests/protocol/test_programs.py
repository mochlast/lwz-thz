"""Weekly program tests: codec and multi-register write cycle."""

from datetime import time

import pytest

from thzprotocol import client as client_module, framing
from thzprotocol.client import ThzClient
from thzprotocol.errors import ThzWriteVerifyError
from thzprotocol.programs import (
    PROGRAM_SLOTS,
    decode_slot,
    encode_slot,
    normalize_slot,
)

from .fake_transport import FakeTransport


class TestCodec:
    def test_encode_regular_times(self) -> None:
        # 07:00 = 28 quarters (0x1C), 14:00 = 56 (0x38)
        assert encode_slot(time(7, 0), time(14, 0)) == "1C38"

    def test_encode_rounds_to_quarter_hours(self) -> None:
        assert encode_slot(time(7, 14), time(7, 29)) == "1C1D"  # 07:00 / 07:15

    def test_encode_disabled(self) -> None:
        assert encode_slot(None, None) == "8080"

    def test_encode_midnight_end(self) -> None:
        # End >= 23:46 becomes the device's 24:00 marker (0x60).
        assert encode_slot(time(0, 0), time(23, 59)) == "0060"
        assert encode_slot(time(0, 0), time(23, 45)) == "005F"

    def test_decode(self) -> None:
        payload = bytes.fromhex("AB" + "0B1410" + "1C38")
        assert decode_slot(payload) == (time(7, 0), time(14, 0))

    def test_decode_disabled_and_midnight(self) -> None:
        payload = bytes.fromhex("AB" + "0B1410" + "8060")
        assert decode_slot(payload) == (None, time(23, 59))

    def test_roundtrip_via_normalize(self) -> None:
        for start, end in [
            (time(6, 0), time(22, 0)),
            (None, None),
            (time(5, 7), time(23, 59)),
        ]:
            normalized = normalize_slot(start, end)
            payload = bytes.fromhex("AB" + "0B1410" + encode_slot(start, end))
            assert decode_slot(payload) == normalized


class TestRegistry:
    def test_slot_addressing(self) -> None:
        slot = PROGRAM_SLOTS["hc1_2"]  # window 2 -> slot nibble 1
        assert slot.read_command == "0B1411"
        assert slot.write_commands == (
            "0B14A1",  # Mo-So group first (FHEM order)
            "0B1481",  # Mo-Fr group
            "0B1411",
            "0B1421",
            "0B1431",
            "0B1441",
            "0B1451",  # Mo..Fr
            "0B1491",  # Sa-So group
            "0B1461",
            "0B1471",  # Sa, So
        )

    def test_all_programs_present(self) -> None:
        assert {k.split("_")[0] for k in PROGRAM_SLOTS} == {"hc1", "dhw", "fan"}
        assert len(PROGRAM_SLOTS) == 9


def _get_response(command: bytes, data: bytes) -> bytes:
    chk = framing.checksum(framing.HEADER_GET, command + data)
    return (
        framing.HEADER_GET
        + framing.escape(bytes((chk,)) + command + data)
        + framing.FOOTER
    )


_SET_OK = b"\x01\x80\x00\x00\x10\x03"
_SET_HANDSHAKE = [b"\x10", b"\x10\x02", _SET_OK]


@pytest.fixture(autouse=True)
def _fast_timing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(client_module, "SET_READBACK_DELAY", 0)
    monkeypatch.setattr(client_module, "INTER_REQUEST_GAP", 0)


class TestWriteProgram:
    async def test_writes_all_registers_and_verifies(self) -> None:
        readback = _get_response(bytes.fromhex("0A1710"), bytes.fromhex("1C38"))
        transport = FakeTransport(
            [*(_SET_HANDSHAKE * 10), b"\x10", b"\x10\x02", readback]
        )
        client = ThzClient(lambda: transport)
        await client.connect()

        result = await client.write_program("dhw_1", time(7, 0), time(14, 0))
        assert result == (time(7, 0), time(14, 0))

        set_frames = [w for w in transport.writes if w.startswith(b"\x01\x80")]
        assert len(set_frames) == 10
        # First write goes to the Mo-So group register with the encoded value.
        assert set_frames[0] == framing.encode_frame(
            bytes.fromhex("0A17A0" + "1C38"), is_set=True
        )
        # Last write is Sunday.
        assert set_frames[-1] == framing.encode_frame(
            bytes.fromhex("0A1770" + "1C38"), is_set=True
        )

    async def test_verify_mismatch_raises(self) -> None:
        readback = _get_response(bytes.fromhex("0A1710"), bytes.fromhex("8080"))
        transport = FakeTransport(
            [*(_SET_HANDSHAKE * 10), b"\x10", b"\x10\x02", readback]
        )
        client = ThzClient(lambda: transport)
        await client.connect()

        with pytest.raises(ThzWriteVerifyError):
            await client.write_program("dhw_1", time(7, 0), time(14, 0))
