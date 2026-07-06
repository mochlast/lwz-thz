"""Entity descriptions — HA presentation only, protocol facts live in thzprotocol.

Each description references a coordinator data key (``value_key``, format
``<block>.<field>`` or ``energy.<meter>``). A consistency test asserts that
every referenced key exists in the register tables.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)

from .const import FEATURE_HC2, FEATURE_SOLAR
from .thzprotocol.registers import ENERGY
from .thzprotocol.writeparams import WRITE_PARAMS

HC_OP_MODE_OPTIONS = ["normal", "setback", "standby", "restart"]
SEASON_OPTIONS = ["winter", "summer"]
OP_MODE_OPTIONS = [
    "automatic",
    "day",
    "setback",
    "dhw",
    "standby",
    "manual",
    "emergency",
]
FAN_STAGE_OPTIONS = ["stage_0", "stage_1", "stage_2", "stage_3"]


@dataclass(frozen=True, kw_only=True)
class ThzSensorDescription(SensorEntityDescription):
    """Sensor description bound to a coordinator data key."""

    value_key: str
    feature: str | None = None


@dataclass(frozen=True, kw_only=True)
class ThzBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description bound to a coordinator data key."""

    value_key: str
    feature: str | None = None


def _temp(
    key: str,
    value_key: str,
    *,
    enabled: bool = True,
    feature: str | None = None,
) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
        feature=feature,
    )


def _pressure(key: str, value_key: str) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
    )


def _power_kw(key: str, value_key: str) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    )


def _percent(key: str, value_key: str, *, enabled: bool = True) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _rpm(key: str, value_key: str, *, enabled: bool = True) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _enum(
    key: str, value_key: str, options: list[str], *, feature: str | None = None
) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        device_class=SensorDeviceClass.ENUM,
        options=options,
        feature=feature,
    )


def _hours(key: str, value_key: str, *, enabled: bool = True) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


def _diag(
    key: str, value_key: str, *, enabled: bool = False, unit: str | None = None
) -> ThzSensorDescription:
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        native_unit_of_measurement=unit,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


def _energy(key: str, meter_key: str) -> ThzSensorDescription:
    unit = (
        UnitOfEnergy.KILO_WATT_HOUR
        if ENERGY[meter_key].unit == "kWh"
        else UnitOfEnergy.WATT_HOUR
    )
    return ThzSensorDescription(
        key=key,
        translation_key=key,
        value_key=f"energy.{meter_key}",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )


SENSORS: tuple[ThzSensorDescription, ...] = (
    # sGlobal — temperatures
    _temp("outside_temp", "sGlobal.outside_temp"),
    _temp("outside_temp_filtered", "sGlobal.outside_temp_filtered"),
    _temp("flow_temp", "sGlobal.flow_temp"),
    _temp("return_temp", "sGlobal.return_temp"),
    _temp("hot_gas_temp", "sGlobal.hot_gas_temp"),
    _temp("dhw_temp", "sGlobal.dhw_temp"),
    _temp("evaporator_temp", "sGlobal.evaporator_temp"),
    _temp("condenser_temp", "sGlobal.condenser_temp"),
    _temp("dew_point", "sGlobal.dew_point"),
    _temp("inside_temp", "sGlobal.inside_temp", enabled=False),
    _temp("collector_temp", "sGlobal.collector_temp", enabled=False),
    _temp("flow_temp_hc2", "sGlobal.flow_temp_hc2", enabled=False, feature=FEATURE_HC2),
    # sGlobal — humidity / pressure / power / flow
    ThzSensorDescription(
        key="rel_humidity",
        translation_key="rel_humidity",
        value_key="sGlobal.rel_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ThzSensorDescription(
        key="humidity_air_out",
        translation_key="humidity_air_out",
        value_key="sGlobal.humidity_air_out",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _pressure("pressure_low", "sGlobal.pressure_low"),
    _pressure("pressure_high", "sGlobal.pressure_high"),
    _pressure("pressure_hc_water", "sGlobal.pressure_hc_water"),
    _power_kw("actual_power_qc", "sGlobal.actual_power_qc"),
    _power_kw("actual_power_pel", "sGlobal.actual_power_pel"),
    ThzSensorDescription(
        key="flow_rate",
        translation_key="flow_rate",
        value_key="sGlobal.flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # sGlobal — ventilation
    _percent("output_ventilator_power", "sGlobal.output_ventilator_power"),
    _percent("input_ventilator_power", "sGlobal.input_ventilator_power"),
    _percent("main_ventilator_power", "sGlobal.main_ventilator_power", enabled=False),
    _rpm("output_ventilator_speed", "sGlobal.output_ventilator_speed"),
    _rpm("input_ventilator_speed", "sGlobal.input_ventilator_speed"),
    _rpm("main_ventilator_speed", "sGlobal.main_ventilator_speed", enabled=False),
    # sHC1
    _temp("hc1_heat_set_temp", "sHC1.heat_set_temp"),
    _temp("hc1_room_set_temp", "sHC1.room_set_temp"),
    _temp("hc1_inside_temp_rc", "sHC1.inside_temp_rc"),
    _enum("hc1_season_mode", "sHC1.season_mode", SEASON_OPTIONS),
    _enum("hc1_op_mode", "sHC1.hc_op_mode", HC_OP_MODE_OPTIONS),
    _diag("hc1_integral_heat", "sHC1.integral_heat"),
    _diag("hc1_booster_stage", "sHC1.hc_booster_stage"),
    # sDHW
    _temp("dhw_set_temp", "sDHW.dhw_set_temp"),
    _enum("dhw_op_mode", "sDHW.dhw_op_mode", HC_OP_MODE_OPTIONS),
    _diag("dhw_booster_stage", "sDHW.dhw_booster_stage"),
    # sControl
    _diag("heat_request", "sControl.heat_request", enabled=True),
    _diag("hc_stage", "sControl.hc_stage"),
    _diag("dhw_stage", "sControl.dhw_stage"),
    _diag("comp_block_time", "sControl.comp_block_time", unit=UnitOfTime.MINUTES),
    # sFan
    ThzSensorDescription(
        key="airflow_inlet",
        translation_key="airflow_inlet",
        value_key="sFan.fanstage_airflow_inlet",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ThzSensorDescription(
        key="airflow_outlet",
        translation_key="airflow_outlet",
        value_key="sFan.fanstage_airflow_outlet",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # sHistory — operating hours
    _hours("hours_compressor_heating", "sHistory.compressor_heating"),
    _hours("hours_compressor_cooling", "sHistory.compressor_cooling", enabled=False),
    _hours("hours_compressor_dhw", "sHistory.compressor_dhw"),
    _hours("hours_booster_dhw", "sHistory.booster_dhw"),
    _hours("hours_booster_heating", "sHistory.booster_heating"),
    # sLast10errors
    _diag("number_of_faults", "sLast10errors.number_of_faults", enabled=True),
    _diag("last_fault", "sLast10errors.fault0_code", enabled=True),
    # sHC2 (feature-gated; flow temp comes from sGlobal.flow_temp_hc2)
    _temp("hc2_heat_set_temp", "sHC2.heat_set_temp", feature=FEATURE_HC2),
    _enum("hc2_op_mode", "sHC2.hc_op_mode", HC_OP_MODE_OPTIONS, feature=FEATURE_HC2),
    # sSol (feature-gated)
    _temp("solar_collector_temp", "sSol.collector_temp", feature=FEATURE_SOLAR),
    _temp("solar_dhw_temp", "sSol.dhw_temp", feature=FEATURE_SOLAR),
    # Energy / heat meters (energy dashboard: use the electricity totals)
    _energy("energy_heat_hc_day", "heat_hc_day"),
    _energy("energy_heat_hc_total", "heat_hc_total"),
    _energy("energy_heat_dhw_day", "heat_dhw_day"),
    _energy("energy_heat_dhw_total", "heat_dhw_total"),
    _energy("energy_heat_recovered_day", "heat_recovered_day"),
    _energy("energy_heat_recovered_total", "heat_recovered_total"),
    _energy("energy_electr_hc_day", "electr_hc_day"),
    _energy("energy_electr_hc_total", "electr_hc_total"),
    _energy("energy_electr_dhw_day", "electr_dhw_day"),
    _energy("energy_electr_dhw_total", "electr_dhw_total"),
    _energy("energy_boost_dhw_total", "boost_dhw_total"),
    _energy("energy_boost_hc_total", "boost_hc_total"),
)


def _binary(
    key: str,
    value_key: str,
    *,
    device_class: BinarySensorDeviceClass | None = None,
    enabled: bool = True,
    diagnostic: bool = False,
    feature: str | None = None,
) -> ThzBinarySensorDescription:
    return ThzBinarySensorDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        device_class=device_class,
        entity_registry_enabled_default=enabled,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
        feature=feature,
    )


_RUNNING = BinarySensorDeviceClass.RUNNING
_PROBLEM = BinarySensorDeviceClass.PROBLEM

BINARY_SENSORS: tuple[ThzBinarySensorDescription, ...] = (
    # sGlobal — actuator bits
    _binary("compressor", "sGlobal.compressor", device_class=_RUNNING),
    _binary(
        "heating_circuit_pump", "sGlobal.heating_circuit_pump", device_class=_RUNNING
    ),
    _binary("dhw_pump", "sGlobal.dhw_pump", device_class=_RUNNING),
    _binary(
        "solar_pump", "sGlobal.solar_pump", device_class=_RUNNING, feature=FEATURE_SOLAR
    ),
    _binary("booster_stage_1", "sGlobal.booster_stage_1", device_class=_RUNNING),
    _binary(
        "booster_stage_2",
        "sGlobal.booster_stage_2",
        device_class=_RUNNING,
        enabled=False,
    ),
    _binary(
        "booster_stage_3",
        "sGlobal.booster_stage_3",
        device_class=_RUNNING,
        enabled=False,
    ),
    _binary("diverter_valve", "sGlobal.diverter_valve", enabled=False),
    _binary("heat_pipe_valve", "sGlobal.heat_pipe_valve", enabled=False),
    _binary("mixer_open", "sGlobal.mixer_open", enabled=False),
    _binary("mixer_closed", "sGlobal.mixer_closed", enabled=False),
    _binary("evu_release", "sGlobal.evu_release"),
    _binary(
        "window_open",
        "sGlobal.window_open",
        device_class=BinarySensorDeviceClass.WINDOW,
    ),
    _binary("quick_air_vent", "sGlobal.quick_air_vent", enabled=False),
    _binary("oven_fireplace", "sGlobal.oven_fireplace", enabled=False),
    _binary("stb", "sGlobal.stb", device_class=_PROBLEM, diagnostic=True),
    _binary(
        "high_pressure_sensor",
        "sGlobal.high_pressure_sensor",
        diagnostic=True,
        enabled=False,
    ),
    _binary(
        "low_pressure_sensor",
        "sGlobal.low_pressure_sensor",
        diagnostic=True,
        enabled=False,
    ),
    _binary(
        "evaporator_ice_monitor",
        "sGlobal.evaporator_ice_monitor",
        device_class=BinarySensorDeviceClass.COLD,
        diagnostic=True,
    ),
    _binary("signal_anode", "sGlobal.signal_anode", diagnostic=True, enabled=False),
    # sDisplay — front panel indicators
    _binary("display_filter", "sDisplay.filter_both", device_class=_PROBLEM),
    _binary(
        "display_filter_up",
        "sDisplay.filter_up",
        device_class=_PROBLEM,
        diagnostic=True,
        enabled=False,
    ),
    _binary(
        "display_filter_down",
        "sDisplay.filter_down",
        device_class=_PROBLEM,
        diagnostic=True,
        enabled=False,
    ),
    _binary("display_service", "sDisplay.service", device_class=_PROBLEM),
    _binary("display_defrost", "sDisplay.defrost", device_class=_RUNNING),
    _binary(
        "display_cooling", "sDisplay.cooling", device_class=_RUNNING, enabled=False
    ),
    _binary("display_heating_hc", "sDisplay.heating_hc", device_class=_RUNNING),
    _binary("display_heating_dhw", "sDisplay.heating_dhw", device_class=_RUNNING),
    _binary(
        "display_booster_hc",
        "sDisplay.booster_hc",
        device_class=_RUNNING,
        enabled=False,
    ),
    _binary("display_vent_stage", "sDisplay.vent_stage", enabled=False),
    _binary(
        "display_switching_prog",
        "sDisplay.switching_prog",
        diagnostic=True,
        enabled=False,
    ),
)


@dataclass(frozen=True, kw_only=True)
class ThzNumberDescription(NumberEntityDescription):
    """Number description bound to a writable parameter."""

    param_key: str
    value_key: str
    feature: str | None = None


@dataclass(frozen=True, kw_only=True)
class ThzSelectDescription(SelectEntityDescription):
    """Select description bound to a writable parameter.

    ``option_to_value`` maps the HA option string to the raw value the
    protocol layer expects (and returns on read-back).
    """

    param_key: str
    value_key: str
    option_to_value: dict[str, float | str]
    feature: str | None = None


def _setpoint(
    key: str, *, category: EntityCategory | None = None
) -> ThzNumberDescription:
    param = WRITE_PARAMS[key]
    return ThzNumberDescription(
        key=key,
        translation_key=key,
        param_key=key,
        value_key=f"param.{key}",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=param.min,
        native_max_value=param.max,
        native_step=param.step,
        mode=NumberMode.BOX,
        entity_category=category,
    )


def _duration_number(key: str) -> ThzNumberDescription:
    param = WRITE_PARAMS[key]
    return ThzNumberDescription(
        key=key,
        translation_key=key,
        param_key=key,
        value_key=f"param.{key}",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=param.min,
        native_max_value=param.max,
        native_step=param.step,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    )


def _stage_select(
    key: str, *, category: EntityCategory | None = None
) -> ThzSelectDescription:
    return ThzSelectDescription(
        key=key,
        translation_key=key,
        param_key=key,
        value_key=f"param.{key}",
        options=FAN_STAGE_OPTIONS,
        option_to_value={
            option: index for index, option in enumerate(FAN_STAGE_OPTIONS)
        },
        entity_category=category,
    )


def _curve_param(key: str, *, unit: str | None = None) -> ThzNumberDescription:
    param = WRITE_PARAMS[key]
    return ThzNumberDescription(
        key=key,
        translation_key=key,
        param_key=key,
        value_key=f"param.{key}",
        native_unit_of_measurement=unit,
        native_min_value=param.min,
        native_max_value=param.max,
        native_step=param.step,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    )


NUMBERS: tuple[ThzNumberDescription, ...] = (
    _setpoint("p01_room_temp_day"),
    _setpoint("p02_room_temp_night"),
    _setpoint("p04_dhw_temp_day"),
    _setpoint("p05_dhw_temp_night"),
    _duration_number("p43_unsched_vent_stage3"),
    _duration_number("p44_unsched_vent_stage2"),
    _duration_number("p45_unsched_vent_stage1"),
    _duration_number("p46_unsched_vent_stage0"),
    # Heating curve
    _curve_param("p13_gradient_hc1"),
    _curve_param("p14_low_end_hc1", unit="K"),
    _curve_param("p15_room_influence_hc1", unit=PERCENTAGE),
)

SELECTS: tuple[ThzSelectDescription, ...] = (
    ThzSelectDescription(
        key="op_mode",
        translation_key="op_mode",
        param_key="op_mode",
        value_key="param.op_mode",
        options=OP_MODE_OPTIONS,
        option_to_value={mode: mode for mode in OP_MODE_OPTIONS},
    ),
    _stage_select("p07_fan_stage_day"),
    _stage_select("p08_fan_stage_night"),
    _stage_select("p09_fan_stage_standby", category=EntityCategory.CONFIG),
    _stage_select("p99_start_unsched_vent"),
)
