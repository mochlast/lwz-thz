"""Writable parameters (FHEM %sets439539common, practice subset).

Each parameter is a standalone 3-byte register: a GET on ``command`` returns
the current value at payload nibble 8 (after checksum + echo), a SET frame
carries ``command + encoded value`` with header 01 80 (FHEM THZ_Set: value
substituted at parse offset - 2). Adding a parameter later is one
``WriteParamDef`` line plus an entity description.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .datatypes import hex2int
from .mappings import OP_MODE, OP_MODE_REVERSE


class WriteType(StrEnum):
    """Value codec, named after the FHEM set types."""

    TEMP5 = "5temp"  # value * 10, 4 nibbles, signed
    GRADIENT6 = "6gradient"  # value * 100, 4 nibbles, unsigned
    CLEAN1 = "1clean"  # integer, 4 nibbles
    CLEAN0 = "0clean"  # integer, 2 nibbles
    OPMODE2 = "2opmode"  # named operating mode, 2 nibbles


_VALUE_NIBBLES = {
    WriteType.TEMP5: 4,
    WriteType.GRADIENT6: 4,
    WriteType.CLEAN1: 4,
    WriteType.CLEAN0: 2,
    WriteType.OPMODE2: 2,
}


@dataclass(frozen=True, slots=True)
class WriteParamDef:
    """One writable register."""

    key: str
    command: str  # 3-byte register address, hex
    type: WriteType
    min: float = 0
    max: float = 0
    step: float = 1


def encode_value(param: WriteParamDef, value: float | str) -> str:
    """Validate and encode a value into the hex field of a SET frame."""
    if param.type is WriteType.OPMODE2:
        if not isinstance(value, str) or value not in OP_MODE_REVERSE:
            raise ValueError(
                f"{param.key}: unknown mode {value!r}, "
                f"expected one of {sorted(OP_MODE_REVERSE)}"
            )
        return f"{OP_MODE_REVERSE[value]:02X}"

    number = float(value)
    if not param.min <= number <= param.max:
        raise ValueError(
            f"{param.key}: value {number} outside range {param.min}..{param.max}"
        )
    if param.type is WriteType.TEMP5:
        return f"{round(number * 10) & 0xFFFF:04X}"
    if param.type is WriteType.GRADIENT6:
        return f"{round(number * 100) & 0xFFFF:04X}"
    if param.type is WriteType.CLEAN1:
        return f"{round(number) & 0xFFFF:04X}"
    return f"{round(number) & 0xFF:02X}"  # CLEAN0


def decode_value(param: WriteParamDef, payload: bytes) -> float | int | str:
    """Decode the current value from a GET response payload."""
    payload_hex = payload.hex().upper()
    raw = payload_hex[8 : 8 + _VALUE_NIBBLES[param.type]]
    if param.type is WriteType.OPMODE2:
        code = int(raw, 16)
        return OP_MODE.get(code, f"unknown_{code}")
    if param.type is WriteType.TEMP5:
        return hex2int(raw) / 10
    if param.type is WriteType.GRADIENT6:
        return int(raw, 16) / 100
    if param.type is WriteType.CLEAN1:
        return hex2int(raw)
    return int(raw, 16)  # CLEAN0


def values_match(
    param: WriteParamDef, requested: float | str, readback: object
) -> bool:
    """Compare a requested value with the read-back at register resolution."""
    if param.type is WriteType.OPMODE2:
        return readback == requested
    if not isinstance(readback, int | float):
        return False
    if param.type is WriteType.TEMP5:
        return round(float(readback) * 10) == round(float(requested) * 10)
    if param.type is WriteType.GRADIENT6:
        return round(float(readback) * 100) == round(float(requested) * 100)
    return round(float(readback)) == round(float(requested))


# Practice set — commands and ranges verified against FHEM %sets439539common.
WRITE_PARAMS: dict[str, WriteParamDef] = {
    param.key: param
    for param in (
        WriteParamDef("op_mode", "0A0112", WriteType.OPMODE2),
        WriteParamDef("p01_room_temp_day", "0B0005", WriteType.TEMP5, 12, 32, 0.1),
        WriteParamDef("p02_room_temp_night", "0B0008", WriteType.TEMP5, 12, 32, 0.1),
        WriteParamDef("p04_dhw_temp_day", "0A0013", WriteType.TEMP5, 10, 55, 0.1),
        WriteParamDef("p05_dhw_temp_night", "0A05BF", WriteType.TEMP5, 10, 55, 0.1),
        WriteParamDef("p07_fan_stage_day", "0A056C", WriteType.CLEAN1, 0, 3),
        WriteParamDef("p08_fan_stage_night", "0A056D", WriteType.CLEAN1, 0, 3),
        WriteParamDef("p09_fan_stage_standby", "0A056F", WriteType.CLEAN1, 0, 3),
        # Watch the numbering twist: p43 = duration for stage 3 ... p46 = stage 0.
        WriteParamDef(
            "p43_unsched_vent_stage3", "0A0574", WriteType.CLEAN1, 0, 1000, 5
        ),
        WriteParamDef(
            "p44_unsched_vent_stage2", "0A0573", WriteType.CLEAN1, 0, 1000, 5
        ),
        WriteParamDef(
            "p45_unsched_vent_stage1", "0A0572", WriteType.CLEAN1, 0, 1000, 5
        ),
        WriteParamDef(
            "p46_unsched_vent_stage0", "0A0571", WriteType.CLEAN1, 0, 1000, 5
        ),
        WriteParamDef("p99_start_unsched_vent", "0A05DD", WriteType.CLEAN1, 0, 3),
        # Heating curve parameters (used by the heating-curve card).
        WriteParamDef("p13_gradient_hc1", "0B010E", WriteType.GRADIENT6, 0.1, 5, 0.01),
        WriteParamDef("p14_low_end_hc1", "0B059E", WriteType.TEMP5, 0, 10, 0.1),
        WriteParamDef("p15_room_influence_hc1", "0B010F", WriteType.CLEAN0, 0, 100, 1),
    )
}
