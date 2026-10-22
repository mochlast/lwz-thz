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


# Practice set. Commands come from FHEM %sets439539common, but the min/max
# ranges follow the Stiebel Eltron operating manuals ("Menüstruktur" tables of
# LWZ 304 Integral/Trend, LWZ 304/404 SOL and LWZ 5/8 CS Premium — all three
# agree). FHEM's hand-set argMin/argMax are narrower in several places; its
# DHW cap of 55 °C is the temperature the unit reaches in normal operation,
# not the settable range, which is 10..65 °C on every documented model.
WRITE_PARAMS: dict[str, WriteParamDef] = {
    param.key: param
    for param in (
        WriteParamDef("op_mode", "0A0112", WriteType.OPMODE2),
        WriteParamDef("p01_room_temp_day", "0B0005", WriteType.TEMP5, 10, 32, 0.1),
        WriteParamDef("p02_room_temp_night", "0B0008", WriteType.TEMP5, 10, 32, 0.1),
        WriteParamDef("p04_dhw_temp_day", "0A0013", WriteType.TEMP5, 10, 65, 0.1),
        WriteParamDef("p05_dhw_temp_night", "0A05BF", WriteType.TEMP5, 10, 65, 0.1),
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
        WriteParamDef("p13_gradient_hc1", "0B010E", WriteType.GRADIENT6, 0, 5, 0.01),
        WriteParamDef("p14_low_end_hc1", "0B059E", WriteType.TEMP5, 0, 20, 0.1),
        WriteParamDef("p15_room_influence_hc1", "0B010F", WriteType.CLEAN0, 0, 100, 1),
        # Control parameters: when the compressor starts and stops. Unlike
        # the setpoints above, FHEM and the manual (Bedienung LWZ 304 Integral/
        # Trend, 404 Trend, A 312030-38606-9039, "Menüstruktur") are both
        # consulted and the narrower range wins — these are not everyday
        # settings, and the firmware may refuse values its display offers.
        # Manual 10..65 °C, FHEM 10..55 °C like its other DHW setpoints.
        WriteParamDef("p11_dhw_temp_manual", "0A0580", WriteType.TEMP5, 10, 55, 0.1),
        # Weight of the flow (vs. return) temperature in the heating-circuit
        # actual value the hysteresis and integral work on. Both 0..100 %.
        WriteParamDef("p19_flow_proportion_hc1", "0B059D", WriteType.CLEAN1, 0, 100),
        # Below setpoint - Hyst1 the next stage switches on (stage 1 is the
        # compressor, then the boosters), - Hyst1 - Hyst2 one more. Manual
        # and FHEM agree: 0..10 K for 1..2, 0..5 K for 3..5.
        WriteParamDef("p21_hyst1", "0A05C0", WriteType.TEMP5, 0, 10, 0.1),
        WriteParamDef("p22_hyst2", "0A05C1", WriteType.TEMP5, 0, 10, 0.1),
        WriteParamDef("p23_hyst3", "0A05C2", WriteType.TEMP5, 0, 5, 0.1),
        WriteParamDef("p24_hyst4", "0A05C3", WriteType.TEMP5, 0, 5, 0.1),
        WriteParamDef("p25_hyst5", "0A05C4", WriteType.TEMP5, 0, 5, 0.1),
        # Divides the hysteresis above the setpoint (switch-off side). 1..5.
        WriteParamDef("p29_hyst_asymmetry", "0A05C5", WriteType.CLEAN1, 1, 5),
        # Threshold of the heating integral in K·min: when sHC1.integral_heat
        # reaches it, one stage switches up or down and the integral resets.
        # sHC1.integral_switch mirrors it. Manual 1..999, FHEM 10..999.
        WriteParamDef("p30_integral_component", "0A0162", WriteType.CLEAN1, 10, 999),
        # Manual 10..25 °C, FHEM 10..24 °C.
        WriteParamDef("p49_summer_mode_temp", "0A0116", WriteType.TEMP5, 10, 24, 0.1),
        # Manual 1..7 K; FHEM 0.5..5 K (set table) and 1..5 K (pHeat2).
        WriteParamDef(
            "p50_summer_mode_hysteresis", "0A05A2", WriteType.TEMP5, 1, 5, 0.1
        ),
    )
}

# Device clock (FHEM pClockDay/Month/Year/Hour/Minutes). Not part of the
# polled practice set: the clock is read in one telegram via sTimedate (FC)
# and these registers are only written by the clock sync, field by field.
# FHEM caps the two-digit year at 20, a leftover from when the module was
# written; the register is a plain byte, so any 20xx year fits.
CLOCK_PARAMS: dict[str, WriteParamDef] = {
    param.key: param
    for param in (
        WriteParamDef("clock_day", "0A0122", WriteType.CLEAN0, 1, 31),
        WriteParamDef("clock_month", "0A0123", WriteType.CLEAN0, 1, 12),
        WriteParamDef("clock_year", "0A0124", WriteType.CLEAN0, 12, 99),
        WriteParamDef("clock_hour", "0A0125", WriteType.CLEAN0, 0, 23),
        WriteParamDef("clock_minute", "0A0126", WriteType.CLEAN0, 0, 59),
    )
}

# Everything the client can read and write by key.
ALL_PARAMS: dict[str, WriteParamDef] = WRITE_PARAMS | CLOCK_PARAMS
