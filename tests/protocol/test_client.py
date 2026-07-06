"""Client tests: serialization, error classification, backoff behaviour."""

import pytest

from thzprotocol import framing
from thzprotocol.client import ThzClient
from thzprotocol.errors import (
    ThzConnectionError,
    ThzNotConnectedError,
    ThzTimeoutError,
)

from .fake_transport import FakeTransport


def _response(command: bytes, data: bytes) -> bytes:
    chk = framing.checksum(framing.HEADER_GET, command + data)
    return (
        framing.HEADER_GET
        + framing.escape(bytes((chk,)) + command + data)
        + framing.FOOTER
    )


def _handshake(command: bytes, data: bytes) -> list[bytes]:
    return [b"\x10", b"\x10\x02", _response(command, data)]


class TestReads:
    async def test_get_firmware(self) -> None:
        transport = FakeTransport(_handshake(b"\xfd", b"\x02\x1b"))
        client = ThzClient(lambda: transport)
        await client.connect()
        assert await client.get_firmware() == "5.39"
        await client.disconnect()

    async def test_read_block_sglobal(self) -> None:
        data = bytearray(77)  # zeroed sGlobal answer, 158 payload nibbles total
        data[2:4] = b"\x00\xe3"  # outside_temp at payload nibble 8
        transport = FakeTransport(_handshake(b"\xfb", bytes(data)))
        client = ThzClient(lambda: transport)
        await client.connect()
        values = await client.read_block("sGlobal")
        assert values["outside_temp"] == 22.7
        assert values["compressor"] is False

    async def test_read_energy_combines_low_and_high_word(self) -> None:
        # heat_hc_total: low register 456 kWh + high register 3 -> 3456 kWh
        transport = FakeTransport(
            _handshake(bytes.fromhex("0A0930"), b"\x01\xc8")
            + _handshake(bytes.fromhex("0A0931"), b"\x00\x03")
        )
        client = ThzClient(lambda: transport)
        await client.connect()
        assert await client.read_energy("heat_hc_total") == 3456

    async def test_sequential_requests_share_one_connection(self) -> None:
        transport = FakeTransport(
            _handshake(b"\xfd", b"\x02\x1b") + _handshake(b"\xfd", b"\x02\x1b")
        )
        client = ThzClient(lambda: transport)
        await client.connect()
        assert await client.get_firmware() == "5.39"
        assert await client.get_firmware() == "5.39"


class TestErrorHandling:
    async def test_connection_error_tears_down_and_backs_off(self) -> None:
        transport = FakeTransport()
        transport.fail_reads_with = ThzConnectionError("USB yanked")
        client = ThzClient(lambda: transport)
        await client.connect()

        with pytest.raises(ThzConnectionError):
            await client.request(b"\xfb")
        assert not client.is_connected

        # Inside the backoff window the client fails fast instead of retrying.
        with pytest.raises(ThzNotConnectedError):
            await client.request(b"\xfb")

    async def test_protocol_error_keeps_connection(self) -> None:
        transport = FakeTransport()  # no scripted bytes -> handshake timeout
        client = ThzClient(lambda: transport)
        await client.connect()

        with pytest.raises(ThzTimeoutError):
            await client.request(b"\xfb")
        assert client.is_connected

    async def test_reconnects_after_backoff_window(self) -> None:
        broken = FakeTransport()
        broken.fail_reads_with = ThzConnectionError("USB yanked")
        healthy = FakeTransport(_handshake(b"\xfd", b"\x02\x1b"))
        transports = [broken, healthy]
        client = ThzClient(lambda: transports.pop(0))

        await client.connect()
        with pytest.raises(ThzConnectionError):
            await client.request(b"\xfb")
        assert not client.is_connected

        client._backoff_until = 0.0  # fast-forward past the backoff window
        assert await client.get_firmware() == "5.39"
        assert client.is_connected
        assert client._fail_streak == 0  # reset after successful reconnect

    async def test_failed_connect_sets_backoff(self) -> None:
        class RefusingTransport(FakeTransport):
            async def open(self) -> None:
                raise ThzConnectionError("port busy")

        client = ThzClient(RefusingTransport)
        with pytest.raises(ThzConnectionError):
            await client.connect()
        with pytest.raises(ThzNotConnectedError):
            await client.request(b"\xfb")
