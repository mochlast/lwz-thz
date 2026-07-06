"""Handshake state-machine tests against the scriptable FakeTransport."""

import pytest

from thzprotocol import framing
from thzprotocol.errors import ThzChecksumError, ThzNakError, ThzProtocolError
from thzprotocol.protocol import ThzProtocol

from .fake_transport import FakeTransport


def _response(command: bytes, data: bytes) -> bytes:
    chk = framing.checksum(framing.HEADER_GET, command + data)
    return (
        framing.HEADER_GET
        + framing.escape(bytes((chk,)) + command + data)
        + framing.FOOTER
    )


async def _run(
    incoming: list[bytes], command: bytes = b"\xfb"
) -> tuple[bytes, FakeTransport]:
    transport = FakeTransport(incoming)
    await transport.open()
    payload = await ThzProtocol(transport).request(command)
    return payload, transport


class TestHappyPath:
    async def test_full_cycle(self) -> None:
        response = _response(b"\xfb", b"\x00\xe3\x01\x13")
        payload, transport = await _run([b"\x10", b"\x10\x02", response])

        assert payload[1:] == b"\xfb\x00\xe3\x01\x13"
        assert transport.writes == [
            b"\x02",  # step 0: STX
            framing.encode_frame(b"\xfb"),  # step 1: framed command
            b"\x10",  # step 2: clear to receive
            b"\x10",  # final ACK
        ]

    async def test_step1_bare_stx(self) -> None:
        # Some firmwares answer step 1 with a bare 02 instead of 10 02.
        response = _response(b"\xfd", b"\x02\x1b")
        payload, _ = await _run([b"\x10", b"\x02", response], command=b"\xfd")
        assert payload[1:] == b"\xfd\x02\x1b"

    async def test_step1_delayed_stx(self) -> None:
        # FW 2.x quirk: 10 arrives first, the 02 trails in a later chunk.
        response = _response(b"\xfb", b"\x01")
        payload, _ = await _run([b"\x10", b"\x10", b"\x02", response])
        assert payload[1:] == b"\xfb\x01"


class TestFrameReassembly:
    async def test_stuffed_dle_before_data_etx_is_not_a_footer(self) -> None:
        # Data 10 03: on the wire the 10 is stuffed -> 10 10 03, which looks
        # like a footer. The parity rule must keep reading until the real one.
        data = b"\x99\x10\x03\x77"
        response = _response(b"\xfb", data)
        misleading_end = response.index(b"\x10\x10\x03") + 3
        chunks = [
            b"\x10",
            b"\x10\x02",
            response[:misleading_end],
            response[misleading_end:],
        ]
        payload, _ = await _run(chunks)
        assert payload[1:] == b"\xfb" + data

    async def test_fragmented_frame_is_reassembled(self) -> None:
        response = _response(b"\xfb", bytes(range(40)))
        payload, _ = await _run([b"\x10", b"\x10\x02", response[:7], response[7:]])
        assert payload[1:] == b"\xfb" + bytes(range(40))


class TestErrors:
    async def test_nak_in_step0(self) -> None:
        transport = FakeTransport([b"\x15"])
        await transport.open()
        with pytest.raises(ThzNakError):
            await ThzProtocol(transport).request(b"\xfb")

    async def test_nak_in_step1(self) -> None:
        transport = FakeTransport([b"\x10", b"\x15"])
        await transport.open()
        with pytest.raises(ThzNakError):
            await ThzProtocol(transport).request(b"\xfb")

    async def test_garbage_ack_in_step0(self) -> None:
        transport = FakeTransport([b"\x42"])
        await transport.open()
        with pytest.raises(ThzProtocolError):
            await ThzProtocol(transport).request(b"\xfb")

    async def test_device_error_header(self) -> None:
        frame = b"\x01\x02" + b"\x00" + framing.FOOTER
        transport = FakeTransport([b"\x10", b"\x10\x02", frame])
        await transport.open()
        with pytest.raises(ThzChecksumError):
            await ThzProtocol(transport).request(b"\xfb")

    async def test_corrupted_checksum(self) -> None:
        response = bytearray(_response(b"\xfb", b"\x00\xe3"))
        response[2] ^= 0x01
        transport = FakeTransport([b"\x10", b"\x10\x02", bytes(response)])
        await transport.open()
        with pytest.raises(ThzChecksumError):
            await ThzProtocol(transport).request(b"\xfb")
