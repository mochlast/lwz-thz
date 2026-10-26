"""Write path tests: value codec and write-verify cycle."""

import pytest

from thzprotocol import client as client_module, framing
from thzprotocol.client import ThzClient
from thzprotocol.errors import ThzValueRejectedError, ThzWriteVerifyError
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


# Control parameters: FHEM %sets439539common name, register, the value
# Marc's FHEM logged for this unit (2022..2026, never changed) and its
# 4-nibble encoding.
CONTROL_CASES = [
    ("p11_dhw_temp_manual", "p11DHWsetManualTemp", "0A0580", 55.0, "0226"),
    ("p19_flow_proportion_hc1", "p19FlowProportionHC1", "0B059D", 30, "001E"),
    ("p21_hyst1", "p21Hyst1", "0A05C0", 4.0, "0028"),
    ("p22_hyst2", "p22Hyst2", "0A05C1", 3.0, "001E"),
    ("p23_hyst3", "p23Hyst3", "0A05C2", 3.0, "001E"),
    ("p24_hyst4", "p24Hyst4", "0A05C3", 2.0, "0014"),
    ("p25_hyst5", "p25Hyst5", "0A05C4", 2.0, "0014"),
    ("p29_hyst_asymmetry", "p29HystAsymmetry", "0A05C5", 2, "0002"),
    ("p30_integral_component", "p30integralComponent", "0A0162", 100, "0064"),
    ("p49_summer_mode_temp", "p49SummerModeTemp", "0A0116", 18.0, "00B4"),
    ("p50_summer_mode_hysteresis", "p50SummerModeHysteresis", "0A05A2", 4.0, "0028"),
]


class TestControlParams:
    @pytest.mark.parametrize(
        ("key", "fhem", "command", "value", "encoded"), CONTROL_CASES
    )
    def test_register_and_encoding(self, key, fhem, command, value, encoded) -> None:
        param = WRITE_PARAMS[key]
        assert param.command == command, fhem
        assert encode_value(param, value) == encoded

    @pytest.mark.parametrize(
        ("key", "fhem", "command", "value", "encoded"), CONTROL_CASES
    )
    def test_decoding(self, key, fhem, command, value, encoded) -> None:
        payload = bytes.fromhex("AB" + command + encoded)
        assert decode_value(WRITE_PARAMS[key], payload) == value

    @pytest.mark.parametrize(
        ("key", "low", "high", "below", "above"),
        [
            ("p11_dhw_temp_manual", 10, 55, 9.9, 55.1),
            ("p19_flow_proportion_hc1", 0, 100, -1, 101),
            ("p21_hyst1", 0, 10, -0.1, 10.1),
            ("p22_hyst2", 0, 10, -0.1, 10.1),
            ("p23_hyst3", 0, 5, -0.1, 5.1),
            ("p24_hyst4", 0, 5, -0.1, 5.1),
            ("p25_hyst5", 0, 5, -0.1, 5.1),
            ("p29_hyst_asymmetry", 1, 5, 0, 6),
            ("p30_integral_component", 10, 999, 9, 1000),
            ("p49_summer_mode_temp", 10, 24, 9.9, 24.1),
            ("p50_summer_mode_hysteresis", 1, 5, 0.9, 5.1),
        ],
    )
    def test_ranges(self, key, low, high, below, above) -> None:
        param = WRITE_PARAMS[key]
        encode_value(param, low)
        encode_value(param, high)
        with pytest.raises(ValueError):
            encode_value(param, below)
        with pytest.raises(ValueError):
            encode_value(param, above)

    def test_hysteresis_resolution(self) -> None:
        param = WRITE_PARAMS["p21_hyst1"]
        assert encode_value(param, 4.5) == "002D"
        assert values_match(param, 4.5, 4.5)
        assert not values_match(param, 4.5, 4.0)

    def test_integral_component_resolution(self) -> None:
        param = WRITE_PARAMS["p30_integral_component"]
        assert values_match(param, 150, 150)
        assert not values_match(param, 150, 100)


# Issue #5: passive cooling and solar. Same columns as CONTROL_CASES; the
# values are what Marc's FHEM logged for this unit (2022, never changed).
ISSUE5_CASES = [
    ("p75_passive_cooling", "p75passiveCooling", "0A0575", 0, "0000"),
    ("p80_enable_solar", "p80EnableSolar", "0A03C1", 0, "0000"),
    ("p83_dhw_temp_solar", "p83DHWsetSolarTemp", "0A05BE", 60.0, "0258"),
]


class TestPassiveCoolingSolar:
    @pytest.mark.parametrize(
        ("key", "fhem", "command", "value", "encoded"), ISSUE5_CASES
    )
    def test_register_and_codec(self, key, fhem, command, value, encoded) -> None:
        param = WRITE_PARAMS[key]
        assert param.command == command, fhem
        assert encode_value(param, value) == encoded
        assert decode_value(param, bytes.fromhex("AB" + command + encoded)) == value

    @pytest.mark.parametrize(
        ("key", "low", "high", "below", "above"),
        [
            ("p75_passive_cooling", 0, 4, -1, 5),  # manual: five options
            ("p80_enable_solar", 0, 1, -1, 2),
            ("p83_dhw_temp_solar", 10, 75, 9.9, 75.1),  # FHEM
        ],
    )
    def test_ranges(self, key, low, high, below, above) -> None:
        param = WRITE_PARAMS[key]
        encode_value(param, low)
        encode_value(param, high)
        with pytest.raises(ValueError):
            encode_value(param, below)
        with pytest.raises(ValueError):
            encode_value(param, above)

    def test_passive_cooling_options_encode_in_manual_order(self) -> None:
        param = WRITE_PARAMS["p75_passive_cooling"]
        assert [encode_value(param, v) for v in range(5)] == [
            "0000",
            "0001",
            "0002",
            "0003",
            "0004",
        ]


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

    async def test_write_control_param_and_verify(self) -> None:
        transport = FakeTransport(
            [
                *(b"\x10", b"\x10\x02", _SET_OK),
                *(
                    b"\x10",
                    b"\x10\x02",
                    _get_response(bytes.fromhex("0A0162"), b"\x00\x96"),
                ),
            ]
        )
        client = ThzClient(lambda: transport)
        await client.connect()

        assert await client.write_param("p30_integral_component", 150) == 150
        assert transport.writes[1] == framing.encode_frame(
            bytes.fromhex("0A01620096"), is_set=True
        )

    async def test_refused_control_param_is_reported(self) -> None:
        # Same answer shape as the refused DHW setpoint in test_framing:
        # header 01 05, valid checksum, register echoed without a value.
        command = bytes.fromhex("0A05C0")
        refused = (
            b"\x01\x05"
            + bytes((framing.checksum(b"\x01\x05", command),))
            + command
            + framing.FOOTER
        )
        transport = FakeTransport([b"\x10", b"\x10\x02", refused])
        client = ThzClient(lambda: transport)
        await client.connect()

        with pytest.raises(ThzValueRejectedError, match="refused this value"):
            await client.write_param("p21_hyst1", 9.0)

    async def test_out_of_range_sends_nothing(self) -> None:
        transport = FakeTransport()
        client = ThzClient(lambda: transport)
        await client.connect()

        with pytest.raises(ValueError):
            await client.write_param("p07_fan_stage_day", 4)
        assert transport.writes == []
