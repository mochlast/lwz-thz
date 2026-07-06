"""Converter tests — expected values cross-checked against FHEM THZ_Parse1."""

import pytest

from thzprotocol.datatypes import FieldType, convert, hex2int


class TestHex2Int:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("0000", 0),
            ("01E4", 484),
            ("7FFF", 32767),
            ("8000", -32768),
            ("FDA8", -600),
            ("FFFF", -1),
        ],
    )
    def test_signed_16bit(self, value: str, expected: int) -> None:
        assert hex2int(value) == expected


class TestConvert:
    def test_temperature_with_divisor(self) -> None:
        assert convert(FieldType.HEX2INT, "00E3", divisor=10) == 22.7
        assert convert(FieldType.HEX2INT, "FF38", divisor=10) == -20.0

    def test_hex_unsigned(self) -> None:
        assert convert(FieldType.HEX, "0207", divisor=10) == 51.9
        assert convert(FieldType.HEX, "04B0", divisor=100) == 12.0

    def test_year(self) -> None:
        assert convert(FieldType.YEAR, "1A") == 2026

    @pytest.mark.parametrize(
        ("value", "bit", "expected"),
        [("08", 3, True), ("07", 3, False), ("01", 0, True), ("02", 0, False)],
    )
    def test_bit(self, value: str, bit: int, expected: bool) -> None:
        assert convert(FieldType.BIT, value, bit=bit) is expected

    def test_nbit_inverts(self) -> None:
        assert convert(FieldType.NBIT, "00", bit=0) is True
        assert convert(FieldType.NBIT, "01", bit=0) is False

    def test_bit_ignores_divisor(self) -> None:
        assert convert(FieldType.BIT, "08", divisor=10, bit=3) is True

    def test_opmode(self) -> None:
        assert convert(FieldType.OPMODE, "0B") == "automatic"
        assert convert(FieldType.OPMODE, "05") == "dhw"
        assert convert(FieldType.OPMODE, "63") == "unknown_99"

    def test_opmodehc(self) -> None:
        assert convert(FieldType.OPMODEHC, "01") == "normal"

    def test_somwinmode_uses_raw_string_key(self) -> None:
        assert convert(FieldType.SOMWINMODE, "01") == "winter"
        assert convert(FieldType.SOMWINMODE, "02") == "summer"

    def test_weekday(self) -> None:
        assert convert(FieldType.WEEKDAY, "0") == "monday"
        assert convert(FieldType.WEEKDAY, "6") == "sunday"

    def test_faultmap(self) -> None:
        assert (
            convert(FieldType.FAULTMAP, "18") == "F24_EvaporatorTemperatureSensorFault"
        )
        assert convert(FieldType.FAULTMAP, "00") == "n.a."

    def test_esp_mant_is_float_bits(self) -> None:
        # FHEM: unpack('f', pack('L', hex)) — 0x41C80000 is IEEE-754 for 25.0
        assert convert(FieldType.ESP_MANT, "41C80000") == 25.0
        assert convert(FieldType.ESP_MANT, "00000000") == 0.0

    def test_swver(self) -> None:
        assert convert(FieldType.SWVER, "010A") == "1.10"

    def test_hexdate_is_decimal_split(self) -> None:
        # FHEM: sprintf("%02u.%02u", v/100, v%100) — 0x021B = 539 -> "05.39"
        assert convert(FieldType.HEXDATE, "021B") == "05.39"

    def test_turnhexdate_swaps_bytes_first(self) -> None:
        assert convert(FieldType.TURNHEXDATE, "1B02") == "05.39"

    def test_hex2time_is_decimal_split(self) -> None:
        # 0x04CE = 1230 -> "12:30"
        assert convert(FieldType.HEX2TIME, "04CE") == "12:30"

    def test_turnhex2time(self) -> None:
        assert convert(FieldType.TURNHEX2TIME, "CE04") == "12:30"

    def test_quater(self) -> None:
        assert convert(FieldType.QUATER, "1E") == "07:30"  # 30 quarters
        assert convert(FieldType.QUATER, "00") == "00:00"

    def test_raw(self) -> None:
        assert convert(FieldType.RAW, "BEEF") == "BEEF"

    def test_hex2ascii(self) -> None:
        assert convert(FieldType.HEX2ASCII, "4C575A") == "LWZ"
