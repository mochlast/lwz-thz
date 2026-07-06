"""Field type converters, semantically identical to FHEM's THZ_Parse1.

All converters operate on the hex-nibble substring extracted from the
response payload (payload = checksum + command echo + data, as returned by
``framing.decode_frame``). Offsets and lengths are counted in nibbles,
exactly like FHEM's %parsinghash.
"""

from __future__ import annotations

from enum import StrEnum
import struct
from typing import Any

from . import mappings


class FieldType(StrEnum):
    """Converter selector; values match the FHEM parsing type names."""

    HEX = "hex"
    HEX2INT = "hex2int"
    YEAR = "year"
    BIT = "bit"  # FHEM bit0..bit3 (bit index carried separately)
    NBIT = "nbit"  # FHEM nbit0/nbit1 (inverted bit)
    OPMODE = "opmode"
    OPMODE2 = "opmode2"
    OPMODEHC = "opmodehc"
    SOMWINMODE = "somwinmode"
    WEEKDAY = "weekday"
    FAULTMAP = "faultmap"
    ESP_MANT = "esp_mant"
    SWVER = "swver"
    HEX2ASCII = "hex2ascii"
    HEXDATE = "hexdate"
    TURNHEXDATE = "turnhexdate"
    HEX2TIME = "hex2time"
    TURNHEX2TIME = "turnhex2time"
    QUATER = "quater"
    RAW = "raw"


def hex2int(value: str) -> int:
    """Signed 16-bit two's complement, like FHEM hex2int."""
    number = int(value, 16)
    return number - 0x10000 if number >= 0x8000 else number


def _swap_words(value: str) -> str:
    return value[2:4] + value[0:2]


def _decimal_pair(value: str, separator: str) -> str:
    number = int(value, 16)
    return f"{number // 100:02d}{separator}{number % 100:02d}"


def convert(
    field_type: FieldType,
    value: str,
    *,
    divisor: float = 1,
    bit: int = 0,
) -> Any:
    """Convert one raw hex-nibble string to its typed value."""
    match field_type:
        case FieldType.HEX:
            result: Any = int(value, 16)
        case FieldType.HEX2INT:
            result = hex2int(value)
        case FieldType.YEAR:
            result = int(value, 16) + 2000
        case FieldType.BIT:
            result = bool((int(value, 16) >> bit) & 1)
        case FieldType.NBIT:
            result = not ((int(value, 16) >> bit) & 1)
        case FieldType.OPMODE:
            result = mappings.OP_MODE.get(int(value, 16), f"unknown_{int(value, 16)}")
        case FieldType.OPMODE2:
            result = mappings.OP_MODE_2.get(int(value, 16), f"unknown_{int(value, 16)}")
        case FieldType.OPMODEHC:
            result = mappings.OP_MODE_HC.get(
                int(value, 16), f"unknown_{int(value, 16)}"
            )
        case FieldType.SOMWINMODE:
            result = mappings.SEASON_MODE.get(value, f"unknown_{value}")
        case FieldType.WEEKDAY:
            result = mappings.WEEKDAY.get(value, f"unknown_{value}")
        case FieldType.FAULTMAP:
            result = mappings.FAULT_CODES.get(
                int(value, 16), f"unknown_F{int(value, 16):02d}"
            )
        case FieldType.ESP_MANT:
            # FHEM: unpack('f', pack('L', hex($value))) — reinterpret the
            # 32-bit register value as IEEE-754 float bits.
            result = round(struct.unpack(">f", bytes.fromhex(value))[0], 3)
        case FieldType.SWVER:
            result = f"{int(value[0:2], 16)}.{int(value[2:4], 16):02d}"
        case FieldType.HEX2ASCII:
            result = bytes.fromhex(value).decode("ascii", errors="replace").upper()
        case FieldType.HEXDATE:
            result = _decimal_pair(value, ".")
        case FieldType.TURNHEXDATE:
            result = _decimal_pair(_swap_words(value), ".")
        case FieldType.HEX2TIME:
            result = _decimal_pair(value, ":")
        case FieldType.TURNHEX2TIME:
            result = _decimal_pair(_swap_words(value), ":")
        case FieldType.QUATER:
            quarters = int(value, 16)
            result = f"{quarters // 4:02d}:{quarters % 4 * 15:02d}"
        case FieldType.RAW:
            result = value
        case _:  # pragma: no cover - exhaustive over FieldType
            raise ValueError(f"unhandled field type: {field_type}")

    if (
        divisor != 1
        and isinstance(result, int | float)
        and not isinstance(result, bool)
    ):
        return result / divisor
    return result
