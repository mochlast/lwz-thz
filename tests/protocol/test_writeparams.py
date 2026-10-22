"""Write path tests: value codec and write-verify cycle."""

import pytest

from thzprotocol import client as client_module, framing
from thzprotocol.client import ThzClient
from thzprotocol.errors import ThzWriteVerifyError
from thzprotocol.writeparams import (
    ALL_PARAMS,
    CLOCK_PARAMS,
    WRITE_PARAMS,
    decode_value,
    encode_value,
    values_match,
)

from .fake_transport import FakeTransport


class TestEncodeValue:
    def test_temp5(self) -> None:
        param = WRITE_PARAMS["p01_room_temp_day"]
        assert encode_value(param, 22.0) == "00DC"
        assert encode_value(param, 12.5) == "007D"

    def test_temp5_range_check(self) -> None:
        param = WRITE_PARAMS["p01_room_temp_day"]
        with pytest.raises(ValueError):
            encode_value(param, 9.9)
        with pytest.raises(ValueError):
            encode_value(param, 32.1)

    def test_dhw_setpoint_reaches_manual_maximum(self) -> None:
        # The operating manuals allow 10..65 °C for WW-Soll-Tag/-Nacht; FHEM's
        # 55 was the temperature the unit reaches, not the settable range.
        for key in ("p04_dhw_temp_day", "p05_dhw_temp_night"):
            param = WRITE_PARAMS[key]
            assert encode_value(param, 65.0) == "028A"
            with pytest.raises(ValueError):
                encode_value(param, 65.1)

    def test_clean1(self) -> None:
        assert encode_value(WRITE_PARAMS["p07_fan_stage_day"], 2) == "0002"
        assert encode_value(WRITE_PARAMS["p43_unsched_vent_stage3"], 1000) == "03E8"

    def test_opmode(self) -> None:
        param = WRITE_PARAMS["op_mode"]
        assert encode_value(param, "automatic") == "0B"
        assert encode_value(param, "dhw") == "05"
        assert encode_value(param, "standby") == "01"
        with pytest.raises(ValueError):
            encode_value(param, "party")

    def test_gradient(self) -> None:
        param = WRITE_PARAMS["p13_gradient_hc1"]
        assert encode_value(param, 0.31) == "001F"
        assert encode_value(param, 5) == "01F4"
        with pytest.raises(ValueError):
            encode_value(param, 5.1)

    def test_room_influence_clean0(self) -> None:
        assert encode_value(WRITE_PARAMS["p15_room_influence_hc1"], 80) == "50"

    def test_clock_registers_match_fhem(self) -> None:
        commands = {key: param.command for key, param in CLOCK_PARAMS.items()}
        assert commands == {
            "clock_day": "0A0122",
            "clock_month": "0A0123",
            "clock_year": "0A0124",
            "clock_hour": "0A0125",
            "clock_minute": "0A0126",
        }

    def test_clock_year_beyond_fhem_cap(self) -> None:
        # FHEM's argMax 20 is stale; 2026 must be writable.
        param = CLOCK_PARAMS["clock_year"]
        assert encode_value(param, 26) == "1A"
        assert encode_value(param, 99) == "63"
        with pytest.raises(ValueError):
            encode_value(param, 100)

    def test_clock_ranges(self) -> None:
        assert encode_value(CLOCK_PARAMS["clock_hour"], 23) == "17"
        assert encode_value(CLOCK_PARAMS["clock_minute"], 0) == "00"
        with pytest.raises(ValueError):
            encode_value(CLOCK_PARAMS["clock_hour"], 24)
        with pytest.raises(ValueError):
            encode_value(CLOCK_PARAMS["clock_minute"], 60)
        with pytest.raises(ValueError):
            encode_value(CLOCK_PARAMS["clock_day"], 0)

    def test_clock_params_are_not_polled(self) -> None:
        # The clock is read as one sTimedate block; the registers are
        # write-only for the sync and must not join the params poll group.
        assert not set(CLOCK_PARAMS) & set(WRITE_PARAMS)
        assert ALL_PARAMS == WRITE_PARAMS | CLOCK_PARAMS


class TestDecodeValue:
    def test_temp5(self) -> None:
        payload = bytes.fromhex("AB" + "0B0005" + "00DC")
        assert decode_value(WRITE_PARAMS["p01_room_temp_day"], payload) == 22.0

    def test_opmode(self) -> None:
        payload = bytes.fromhex("AB" + "0A0112" + "0B")
        assert decode_value(WRITE_PARAMS["op_mode"], payload) == "automatic"

    def test_clean1(self) -> None:
        payload = bytes.fromhex("AB" + "0A056C" + "0002")
        assert decode_value(WRITE_PARAMS["p07_fan_stage_day"], payload) == 2

    def test_clock_minute(self) -> None:
        payload = bytes.fromhex("AB" + "0A0126" + "1B")
        assert decode_value(CLOCK_PARAMS["clock_minute"], payload) == 27


class TestValuesMatch:
    def test_temp_resolution(self) -> None:
        param = WRITE_PARAMS["p01_room_temp_day"]
        assert values_match(param, 22.0, 22.0)
        assert not values_match(param, 22.0, 22.1)

    def test_opmode(self) -> None:
        param = WRITE_PARAMS["op_mode"]
        assert values_match(param, "dhw", "dhw")
        assert not values_match(param, "dhw", "automatic")


def _get_response(command: bytes, data: bytes) -> bytes:
    chk = framing.checksum(framing.HEADER_GET, command + data)
    return (
        framing.HEADER_GET
        + framing.escape(bytes((chk,)) + command + data)
        + framing.FOOTER
    )


_SET_OK = b"\x01\x80\x00\x00\x10\x03"


@pytest.fixture(autouse=True)
def _fast_timing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(client_module, "SET_READBACK_DELAY", 0)
    monkeypatch.setattr(client_module, "INTER_REQUEST_GAP", 0)


class TestWriteParam:
    async def test_write_and_verify(self) -> None:
        # SET cycle, then read-back GET cycle answering with the new value.
        transport = FakeTransport(
            [
                *(b"\x10", b"\x10\x02", _SET_OK),
                *(
                    b"\x10",
                    b"\x10\x02",
                    _get_response(bytes.fromhex("0A056C"), b"\x00\x02"),
                ),
            ]
        )
        client = ThzClient(lambda: transport)
        await client.connect()

        assert await client.write_param("p07_fan_stage_day", 2) == 2
        # The SET frame must carry header 01 80 and command + encoded value.
        assert transport.writes[1] == framing.encode_frame(
            bytes.fromhex("0A056C0002"), is_set=True
        )

    async def test_write_verify_mismatch_raises(self) -> None:
        transport = FakeTransport(
            [
                *(b"\x10", b"\x10\x02", _SET_OK),
                *(
                    b"\x10",
                    b"\x10\x02",
                    _get_response(bytes.fromhex("0A056C"), b"\x00\x01"),
                ),
            ]
        )
        client = ThzClient(lambda: transport)
        await client.connect()

        with pytest.raises(ThzWriteVerifyError):
            await client.write_param("p07_fan_stage_day", 2)

    async def test_write_clock_minute(self) -> None:
        # FHEM's monthly "set pClockMinutes 27", through the same verify path.
        transport = FakeTransport(
            [
                *(b"\x10", b"\x10\x02", _SET_OK),
                *(
                    b"\x10",
                    b"\x10\x02",
                    _get_response(bytes.fromhex("0A0126"), b"\x1b"),
                ),
            ]
        )
        client = ThzClient(lambda: transport)
        await client.connect()

        assert await client.write_param("clock_minute", 27) == 27
        assert transport.writes[1] == framing.encode_frame(
            bytes.fromhex("0A01261B"), is_set=True
        )

    async def test_out_of_range_sends_nothing(self) -> None:
        transport = FakeTransport()
        client = ThzClient(lambda: transport)
        await client.connect()

        with pytest.raises(ValueError):
            await client.write_param("p07_fan_stage_day", 4)
        assert transport.writes == []
