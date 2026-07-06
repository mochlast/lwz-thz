"""Golden tests for block parsing against hand-built payloads.

Payload layout = checksum + command echo + data (hex nibbles), exactly the
string FHEM's THZ_decode hands to THZ_Parse1 — offsets are FHEM's.
"""

from thzprotocol.registers import (
    BLOCKS,
    ENERGY,
    SDHW,
    SFIRMWARE,
    SGLOBAL,
    SHC1,
    SLAST10ERRORS,
    STIMEDATE,
    parse_block,
    parse_energy_register,
)


def _build_payload(length_nibbles: int, patches: dict[int, str]) -> bytes:
    """Create a zeroed payload hex string and patch values at nibble offsets."""
    nibbles = ["0"] * length_nibbles
    for offset, value in patches.items():
        nibbles[offset : offset + len(value)] = value
    return bytes.fromhex("".join(nibbles))


class TestSGlobal:
    def test_parses_representative_fields(self) -> None:
        payload = _build_payload(
            158,
            {
                0: "FC",  # checksum (not verified by the parser)
                2: "FB",  # command echo
                8: "00E3",  # outside_temp 22.7
                12: "0113",  # flow_temp 27.5
                16: "FF38",  # return_temp -20.0 (signed)
                24: "01F2",  # dhw_temp 49.8
                32: "00D2",  # inside_temp 21.0
                44: "3",  # dhw_pump=1, heating_circuit_pump=1, solar_pump=0
                47: "8",  # compressor=1, window_open=0
                49: "0",  # nbit -> pressure sensors "ok"
                50: "0207",  # output_ventilator_power 51.9
                62: "08C0",  # output_ventilator_speed 2240
                78: "0203",  # rel_humidity 51.5
                90: "0641",  # pressure_high 16.01
                102: "41C80000",  # actual_power_pel 25.0
                110: "04B0",  # flow_rate 12.0
                154: "1388",  # humidity_air_out 50.0
            },
        )
        values = parse_block(SGLOBAL, payload)

        assert values["outside_temp"] == 22.7
        assert values["flow_temp"] == 27.5
        assert values["return_temp"] == -20.0
        assert values["dhw_temp"] == 49.8
        assert values["inside_temp"] == 21.0
        assert values["dhw_pump"] is True
        assert values["heating_circuit_pump"] is True
        assert values["solar_pump"] is False
        assert values["compressor"] is True
        assert values["window_open"] is False
        assert values["high_pressure_sensor"] is True  # nbit: 0 -> True
        assert values["low_pressure_sensor"] is True
        assert values["output_ventilator_power"] == 51.9
        assert values["output_ventilator_speed"] == 2240
        assert values["rel_humidity"] == 51.5
        assert values["pressure_high"] == 16.01
        assert values["actual_power_pel"] == 25.0
        assert values["flow_rate"] == 12.0
        assert values["humidity_air_out"] == 50.0

    def test_covers_all_46_fields(self) -> None:
        payload = _build_payload(158, {})
        assert len(parse_block(SGLOBAL, payload)) == len(SGLOBAL.fields) == 46

    def test_short_payload_skips_missing_fields(self) -> None:
        # Older firmware variants answer with shorter frames; parsing must
        # skip fields beyond the payload instead of raising (FHEM behaviour).
        payload = _build_payload(100, {8: "00E3"})
        values = parse_block(SGLOBAL, payload)
        assert values["outside_temp"] == 22.7
        assert "humidity_air_out" not in values
        assert "actual_power_pel" not in values


class TestSFirmware:
    def test_parses_version(self) -> None:
        payload = bytes.fromhex("FEFD021B")
        assert parse_block(SFIRMWARE, payload) == {"firmware_version": "05.39"}


class TestSHC1:
    def test_parses_key_fields(self) -> None:
        payload = _build_payload(
            72,
            {
                2: "F4",
                4: "0103",  # outside_temp 25.9
                20: "0130",  # flow_temp 30.4
                24: "0113",  # heat_set_temp 27.5
                38: "02",  # season_mode summer
                48: "01",  # hc_op_mode normal
                56: "00D2",  # room_set_temp 21.0
                68: "00E3",  # inside_temp_rc 22.7
            },
        )
        values = parse_block(SHC1, payload)
        assert values["outside_temp"] == 25.9
        assert values["flow_temp"] == 30.4
        assert values["heat_set_temp"] == 27.5
        assert values["season_mode"] == "summer"
        assert values["hc_op_mode"] == "normal"
        assert values["room_set_temp"] == 21.0
        assert values["inside_temp_rc"] == 22.7


class TestSDHW:
    def test_parses_key_fields(self) -> None:
        payload = _build_payload(
            40,
            {
                2: "F3",
                4: "01B4",  # dhw_temp 43.6
                12: "01F4",  # dhw_set_temp 50.0
                34: "03",  # dhw_op_mode standby
            },
        )
        values = parse_block(SDHW, payload)
        assert values["dhw_temp"] == 43.6
        assert values["dhw_set_temp"] == 50.0
        assert values["dhw_op_mode"] == "standby"


class TestSLast10Errors:
    def test_parses_fault_entries(self) -> None:
        payload = _build_payload(
            56,
            {
                2: "D1",
                4: "02",  # number_of_faults
                8: "18",  # F24
                12: "3F07",  # turnhex2time: 073F -> 1855 -> "18:55"
                16: "6C09",  # turnhexdate: 096C -> 2412 -> "24.12"
            },
        )
        values = parse_block(SLAST10ERRORS, payload)
        assert values["number_of_faults"] == 2
        assert values["fault0_code"] == "F24_EvaporatorTemperatureSensorFault"
        assert values["fault0_time"] == "18:55"
        assert values["fault0_date"] == "24.12"


class TestSTimedate:
    def test_parses_clock(self) -> None:
        payload = _build_payload(
            18,
            {
                2: "FC",
                5: "5",  # saturday
                6: "0C",  # 12h
                8: "1E",  # 30min
                10: "2D",  # 45s
                12: "1A",  # 2026
                14: "07",  # july
                16: "04",  # 4th
            },
        )
        assert parse_block(STIMEDATE, payload) == {
            "weekday": "saturday",
            "hour": 12,
            "minute": 30,
            "second": 45,
            "year": 2026,
            "month": 7,
            "day": 4,
        }


class TestEnergy:
    def test_parse_energy_register(self) -> None:
        # Payload: chk + 3-byte echo + 16-bit value at nibble 8.
        payload = bytes.fromhex("AB" + "0A092E" + "01C8")
        assert parse_energy_register(payload) == 456

    def test_all_meters_have_low_high_pairs(self) -> None:
        for meter in ENERGY.values():
            assert meter.cmd_low != meter.cmd_high
            assert len(meter.cmd_low) == len(meter.cmd_high) == 6
            assert meter.unit in ("Wh", "kWh")


class TestRegistryConsistency:
    def test_block_keys_match(self) -> None:
        assert all(key == block.key for key, block in BLOCKS.items())

    def test_field_keys_unique_within_block(self) -> None:
        for block in BLOCKS.values():
            keys = [field.key for field in block.fields]
            assert len(keys) == len(set(keys)), f"duplicate field key in {block.key}"

    def test_fields_do_not_exceed_reasonable_bounds(self) -> None:
        for block in BLOCKS.values():
            for field in block.fields:
                assert field.offset >= 4, f"{field.key} would sit in checksum/echo"
                assert field.length > 0
