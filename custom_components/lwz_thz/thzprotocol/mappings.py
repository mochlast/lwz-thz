"""Value mappings, transcribed from FHEM 00_THZ.pm (%OpMode, %faultmap, ...)."""

from __future__ import annotations

# Global operating mode (pOpMode, dhwOpMode, ...) — FHEM %OpMode.
OP_MODE: dict[int, str] = {
    0: "emergency",
    1: "standby",
    3: "day",
    4: "setback",
    5: "dhw",
    11: "automatic",
    14: "manual",
}
OP_MODE_REVERSE: dict[str, int] = {name: code for code, name in OP_MODE.items()}

# Heating-circuit operating mode — FHEM %OpModeHC.
OP_MODE_HC: dict[int, str] = {
    1: "normal",
    2: "setback",
    3: "standby",
    4: "restart",
    5: "restart",
}

# FHEM %opMode2.
OP_MODE_2: dict[int, str] = {
    0: "manual",
    1: "automatic",
}

# Season mode — FHEM %SomWinMode (keyed on the raw two-nibble string).
SEASON_MODE: dict[str, str] = {
    "01": "winter",
    "02": "summer",
}

# FHEM %weekday (keyed on the raw single nibble).
WEEKDAY: dict[str, str] = {
    "0": "monday",
    "1": "tuesday",
    "2": "wednesday",
    "3": "thursday",
    "4": "friday",
    "5": "saturday",
    "6": "sunday",
}

# Fault codes — FHEM %faultmap (typos like "Preasure" fixed).
FAULT_CODES: dict[int, str] = {
    0: "n.a.",
    1: "F01_AnodeFault",
    2: "F02_SafetyTempDelimiterEngaged",
    3: "F03_HighPressureGuardFault",
    4: "F04_LowPressureGuardFault",
    5: "F05_OutletFanFault",
    6: "F06_InletFanFault",
    7: "F07_MainOutputFanFault",
    11: "F11_LowPressureSensorFault",
    12: "F12_HighPressureSensorFault",
    15: "F15_DHW_TemperatureFault",
    17: "F17_DefrostingDurationExceeded",
    20: "F20_SolarSensorFault",
    21: "F21_OutsideTemperatureSensorFault",
    22: "F22_HotGasTemperatureFault",
    23: "F23_CondenserTemperatureSensorFault",
    24: "F24_EvaporatorTemperatureSensorFault",
    26: "F26_ReturnTemperatureSensorFault",
    28: "F28_FlowTemperatureSensorFault",
    29: "F29_DHW_TemperatureSensorFault",
    30: "F30_SoftwareVersionFault",
    31: "F31_RAMfault",
    32: "F32_EEPromFault",
    33: "F33_ExtractAirHumiditySensor",
    34: "F34_FlowSensor",
    35: "F35_MinFlowCooling",
    36: "F36_MinFlowRate",
    37: "F37_MinWaterPressure",
    40: "F40_FloatSwitch",
    50: "F50_SensorHeatPumpReturn",
    51: "F51_SensorHeatPumpFlow",
    52: "F52_SensorCondenserOutlet",
}
