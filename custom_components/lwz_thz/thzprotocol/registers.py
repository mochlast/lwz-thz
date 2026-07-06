"""Declarative register tables — the single source of truth for protocol facts.

Transcribed from FHEM 00_THZ.pm %parsinghash / %getsonly439/539 for the
firmware profile 4.39/5.39 (Stiebel Eltron LWZ 304/404 Trend, Tecalor THZ).
The user's LWZ 304 Trend (firmware 5.09) runs FHEM's default 4.39 profile,
so the base (non-206/214) parser variants apply.

Offsets and lengths are in HEX NIBBLES relative to the response payload
(checksum + command echo + data) — identical to FHEM, so every entry can be
diffed line by line against the Perl original. Anonymous debug fields
(FHEM ``x08``, ``out``, ``sensorBits`` ...) are deliberately omitted.

Field keys are unique per block; consumers that flatten several blocks into
one namespace (e.g. the HA coordinator) qualify them as ``<block>.<field>``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datatypes import FieldType, convert


@dataclass(frozen=True, slots=True)
class FieldDef:
    """One value inside a block response."""

    key: str
    offset: int  # nibbles, FHEM %parsinghash position
    length: int  # nibbles
    type: FieldType
    divisor: float = 1
    bit: int = 0  # for FieldType.BIT / NBIT


@dataclass(frozen=True, slots=True)
class BlockDef:
    """A register block read with a single get command."""

    key: str
    command: str  # hex string, e.g. "FB"
    fields: tuple[FieldDef, ...]


@dataclass(frozen=True, slots=True)
class EnergyDef:
    """An energy/heat meter split over two registers (low/high word).

    Total value = ``high * 1000 + low`` (FHEM THZ_Get cmd2/cmd3 handling);
    each register answers a plain signed 16-bit at payload nibble 8.
    """

    key: str
    cmd_low: str  # FHEM cmd2
    cmd_high: str  # FHEM cmd3
    unit: str  # "Wh" or "kWh"


def parse_block(block: BlockDef, payload: bytes) -> dict[str, Any]:
    """Parse a decoded response payload into ``{field_key: value}``.

    Fields beyond the end of the payload are skipped, mirroring FHEM's
    THZ_Parse1 behaviour for firmware variants with shorter responses.
    """
    payload_hex = payload.hex().upper()
    values: dict[str, Any] = {}
    for field in block.fields:
        if field.offset + field.length > len(payload_hex):
            continue
        raw = payload_hex[field.offset : field.offset + field.length]
        values[field.key] = convert(
            field.type, raw, divisor=field.divisor, bit=field.bit
        )
    return values


def parse_energy_register(payload: bytes) -> int:
    """Parse one energy register (FHEM type ``1clean``: nibble 8, len 4)."""
    payload_hex = payload.hex().upper()
    value = int(payload_hex[8:12], 16)
    return value - 0x10000 if value >= 0x8000 else value


def _bit(key: str, offset: int, bit: int) -> FieldDef:
    return FieldDef(key, offset, 1, FieldType.BIT, bit=bit)


def _nbit(key: str, offset: int, bit: int) -> FieldDef:
    return FieldDef(key, offset, 1, FieldType.NBIT, bit=bit)


def _temp(key: str, offset: int) -> FieldDef:
    return FieldDef(key, offset, 4, FieldType.HEX2INT, divisor=10)


def _u8(key: str, offset: int) -> FieldDef:
    return FieldDef(key, offset, 2, FieldType.HEX)


def _i16(key: str, offset: int) -> FieldDef:
    return FieldDef(key, offset, 4, FieldType.HEX2INT)


# FHEM "FBglob" — the main status block, 46 values in one telegram.
SGLOBAL = BlockDef(
    key="sGlobal",
    command="FB",
    fields=(
        _temp("collector_temp", 4),
        _temp("outside_temp", 8),
        _temp("flow_temp", 12),
        _temp("return_temp", 16),
        _temp("hot_gas_temp", 20),
        _temp("dhw_temp", 24),
        _temp("flow_temp_hc2", 28),
        _temp("inside_temp", 32),
        _temp("evaporator_temp", 36),
        _temp("condenser_temp", 40),
        _bit("dhw_pump", 44, 0),
        _bit("heating_circuit_pump", 44, 1),
        _bit("solar_pump", 44, 3),
        _bit("mixer_open", 45, 0),
        _bit("mixer_closed", 45, 1),
        _bit("heat_pipe_valve", 45, 2),
        _bit("diverter_valve", 45, 3),
        _bit("booster_stage_3", 46, 0),
        _bit("booster_stage_2", 46, 1),
        _bit("booster_stage_1", 46, 2),
        _bit("window_open", 47, 2),
        _bit("compressor", 47, 3),
        _bit("evu_release", 48, 0),
        _bit("oven_fireplace", 48, 1),
        _bit("stb", 48, 2),
        _bit("quick_air_vent", 48, 3),
        _nbit("high_pressure_sensor", 49, 0),
        _nbit("low_pressure_sensor", 49, 1),
        _bit("evaporator_ice_monitor", 49, 2),
        _bit("signal_anode", 49, 3),
        FieldDef("output_ventilator_power", 50, 4, FieldType.HEX, divisor=10),
        FieldDef("input_ventilator_power", 54, 4, FieldType.HEX, divisor=10),
        FieldDef("main_ventilator_power", 58, 4, FieldType.HEX, divisor=10),
        FieldDef("output_ventilator_speed", 62, 4, FieldType.HEX),
        FieldDef("input_ventilator_speed", 66, 4, FieldType.HEX),
        FieldDef("main_ventilator_speed", 70, 4, FieldType.HEX),
        _temp("outside_temp_filtered", 74),
        FieldDef("rel_humidity", 78, 4, FieldType.HEX2INT, divisor=10),
        _temp("dew_point", 82),
        FieldDef("pressure_low", 86, 4, FieldType.HEX2INT, divisor=100),  # P_Nd
        FieldDef("pressure_high", 90, 4, FieldType.HEX2INT, divisor=100),  # P_Hd
        # The device reports Qc in W but Pel in kW (verified live on a
        # LWZ 304 during a DHW run: Qc 3834.6 at 22 l/min / ΔT 2.5 K,
        # Pel 2.945). Normalize Qc to kW; FHEM shows both raw.
        FieldDef("actual_power_qc", 94, 8, FieldType.ESP_MANT, divisor=1000),
        FieldDef("actual_power_pel", 102, 8, FieldType.ESP_MANT),
        FieldDef("flow_rate", 110, 4, FieldType.HEX, divisor=100),
        FieldDef("pressure_hc_water", 114, 4, FieldType.HEX, divisor=100),  # p_HCw
        FieldDef("humidity_air_out", 154, 4, FieldType.HEX, divisor=100),
    ),
)

# FHEM "F4hc1" — heating circuit 1.
SHC1 = BlockDef(
    key="sHC1",
    command="F4",
    fields=(
        _temp("outside_temp", 4),
        _temp("return_temp", 12),
        _i16("integral_heat", 16),
        _temp("flow_temp", 20),
        _temp("heat_set_temp", 24),
        _temp("heat_temp", 28),
        _u8("on_hysteresis_no", 32),
        _u8("off_hysteresis_no", 34),
        _u8("hc_booster_stage", 36),
        FieldDef("season_mode", 38, 2, FieldType.SOMWINMODE),
        _i16("integral_switch", 44),
        FieldDef("hc_op_mode", 48, 2, FieldType.OPMODEHC),
        _temp("room_set_temp", 56),
        _temp("inside_temp_rc", 68),
    ),
)

# FHEM "F5hc2" — heating circuit 2 (feature-gated in HA).
SHC2 = BlockDef(
    key="sHC2",
    command="F5",
    fields=(
        _temp("outside_temp", 4),
        _temp("return_temp", 8),
        _temp("flow_temp", 12),
        _temp("heat_set_temp", 16),
        _temp("heat_temp", 20),
        _temp("actuation", 24),  # FHEM "stellgroesse"
        FieldDef("season_mode", 30, 2, FieldType.SOMWINMODE),
        FieldDef("hc_op_mode", 36, 2, FieldType.OPMODEHC),
    ),
)

# FHEM "F3dhw" — domestic hot water.
SDHW = BlockDef(
    key="sDHW",
    command="F3",
    fields=(
        _temp("dhw_temp", 4),
        _temp("outside_temp", 8),
        _temp("dhw_set_temp", 12),
        _i16("comp_block_time", 16),
        _i16("heat_block_time", 24),
        _u8("dhw_booster_stage", 28),
        _u8("pasteurisation_mode", 32),
        FieldDef("dhw_op_mode", 34, 2, FieldType.OPMODEHC),
    ),
)

# FHEM "F2ctrl" — controller state and actuator bits.
SCONTROL = BlockDef(
    key="sControl",
    command="F2",
    fields=(
        _u8("heat_request", 4),  # 0=DHW 2=heat 5=off 6=defrostEva
        _u8("hc_stage", 8),  # 0=off 1=solar 2=heatPump 3..5=boost1..3
        _u8("dhw_stage", 10),  # 0=off 1=solar 2=heatPump 3=boostMax
        _i16("comp_block_time", 14),
        _u8("pasteurisation_mode", 18),
        FieldDef("defrost_evaporator", 20, 2, FieldType.RAW),  # 10=off 30=defrost
        _bit("compressor", 22, 0),
        _bit("booster_stage_1", 22, 1),
        _bit("solar_pump", 22, 2),
        _bit("booster_stage_2", 22, 3),
        _bit("heating_circuit_pump", 23, 0),
        _bit("dhw_pump", 23, 1),
        _bit("diverter_valve", 23, 2),
        _bit("heat_pipe_valve", 23, 3),
        _bit("mixer_closed", 25, 0),
        _bit("mixer_open", 25, 1),
        _i16("boost_block_time_after_pump_start", 30),
        _i16("boost_block_time_after_hd", 34),
    ),
)

# FHEM "E8fan" — ventilation details.
SFAN = BlockDef(
    key="sFan",
    command="E8",
    fields=(
        _u8("input_fan_speed", 58),
        _u8("output_fan_speed", 60),
        FieldDef("fanstage_airflow_inlet", 62, 4, FieldType.HEX),  # m3/h
        FieldDef("fanstage_airflow_outlet", 66, 4, FieldType.HEX),  # m3/h
        _u8("input_fan_power", 70),
        _u8("output_fan_power", 72),
    ),
)

# FHEM "16sol" — solar (feature-gated in HA).
SSOL = BlockDef(
    key="sSol",
    command="16",
    fields=(
        _temp("collector_temp", 4),
        _temp("dhw_temp", 8),
        _temp("flow_temp", 12),
        FieldDef("ed_sol_pump", 16, 2, FieldType.HEX2INT),
    ),
)

# FHEM "09his" — operating hours counters.
SHISTORY = BlockDef(
    key="sHistory",
    command="09",
    fields=(
        FieldDef("compressor_heating", 4, 4, FieldType.HEX),
        FieldDef("compressor_cooling", 8, 4, FieldType.HEX),
        FieldDef("compressor_dhw", 12, 4, FieldType.HEX),
        FieldDef("booster_dhw", 16, 4, FieldType.HEX),
        FieldDef("booster_heating", 20, 4, FieldType.HEX),
    ),
)

# FHEM "D1last" — fault memory (last 4 faults).
SLAST10ERRORS = BlockDef(
    key="sLast10errors",
    command="D1",
    fields=(
        _u8("number_of_faults", 4),
        FieldDef("fault0_code", 8, 2, FieldType.FAULTMAP),
        FieldDef("fault0_time", 12, 4, FieldType.TURNHEX2TIME),
        FieldDef("fault0_date", 16, 4, FieldType.TURNHEXDATE),
        FieldDef("fault1_code", 20, 2, FieldType.FAULTMAP),
        FieldDef("fault1_time", 24, 4, FieldType.TURNHEX2TIME),
        FieldDef("fault1_date", 28, 4, FieldType.TURNHEXDATE),
        FieldDef("fault2_code", 32, 2, FieldType.FAULTMAP),
        FieldDef("fault2_time", 36, 4, FieldType.TURNHEX2TIME),
        FieldDef("fault2_date", 40, 4, FieldType.TURNHEXDATE),
        FieldDef("fault3_code", 44, 2, FieldType.FAULTMAP),
        FieldDef("fault3_time", 48, 4, FieldType.TURNHEX2TIME),
        FieldDef("fault3_date", 52, 4, FieldType.TURNHEXDATE),
    ),
)

# FHEM "FCtime" — device clock.
STIMEDATE = BlockDef(
    key="sTimedate",
    command="FC",
    fields=(
        FieldDef("weekday", 5, 1, FieldType.WEEKDAY),
        _u8("hour", 6),
        _u8("minute", 8),
        _u8("second", 10),
        FieldDef("year", 12, 2, FieldType.YEAR),
        _u8("month", 14),
        _u8("day", 16),
    ),
)

# FHEM "FDfirm" — firmware version, e.g. "05.09".
SFIRMWARE = BlockDef(
    key="sFirmware",
    command="FD",
    fields=(FieldDef("firmware_version", 4, 4, FieldType.HEXDATE),),
)

# FHEM "FEfirmId" — hardware/software identification.
SFIRMWARE_ID = BlockDef(
    key="sFirmwareId",
    command="FE",
    fields=(
        _u8("hardware", 30),
        FieldDef("software", 32, 4, FieldType.SWVER),
        FieldDef("build_date", 36, 22, FieldType.HEX2ASCII),
    ),
)

# FHEM "0A0176Dis" — front display status bits.
SDISPLAY = BlockDef(
    key="sDisplay",
    command="0A0176",
    fields=(
        _bit("filter_up", 8, 0),
        _bit("filter_down", 8, 1),
        _bit("filter_both", 9, 0),
        _bit("vent_stage", 9, 1),
        _bit("pump_hc", 9, 2),
        _bit("defrost", 9, 3),
        _bit("heating_dhw", 10, 0),
        _bit("booster_hc", 10, 1),
        _bit("service", 10, 2),
        _bit("switching_prog", 11, 0),
        _bit("compressor", 11, 1),
        _bit("heating_hc", 11, 2),
        _bit("cooling", 11, 3),
    ),
)

BLOCKS: dict[str, BlockDef] = {
    block.key: block
    for block in (
        SGLOBAL,
        SHC1,
        SHC2,
        SDHW,
        SCONTROL,
        SFAN,
        SSOL,
        SHISTORY,
        SLAST10ERRORS,
        STIMEDATE,
        SFIRMWARE,
        SFIRMWARE_ID,
        SDISPLAY,
    )
}

# Energy/heat meters — FHEM %getsonly439 cmd2/cmd3 pairs.
ENERGY: dict[str, EnergyDef] = {
    meter.key: meter
    for meter in (
        EnergyDef("heat_hc_day", "0A092E", "0A092F", "Wh"),
        EnergyDef("heat_hc_total", "0A0930", "0A0931", "kWh"),
        EnergyDef("heat_dhw_day", "0A092A", "0A092B", "Wh"),
        EnergyDef("heat_dhw_total", "0A092C", "0A092D", "kWh"),
        EnergyDef("heat_recovered_day", "0A03AE", "0A03AF", "Wh"),
        EnergyDef("heat_recovered_total", "0A03B0", "0A03B1", "kWh"),
        EnergyDef("electr_hc_day", "0A091E", "0A091F", "Wh"),
        EnergyDef("electr_hc_total", "0A0920", "0A0921", "kWh"),
        EnergyDef("electr_dhw_day", "0A091A", "0A091B", "Wh"),
        EnergyDef("electr_dhw_total", "0A091C", "0A091D", "kWh"),
        EnergyDef("boost_dhw_total", "0A0924", "0A0925", "kWh"),
        EnergyDef("boost_hc_total", "0A0928", "0A0929", "kWh"),
    )
}
