"""Real telegrams recorded from the reference device.

Source: LWZ 304 Trend, firmware 05.09, recorded 2026-07-06 via
``thz_cli.py --port /dev/ttyUSB1 get sFirmware sGlobal --dump``
(pump idle, summer, outside 25.9 °C). Payload = checksum + command echo +
data, exactly as returned by ``framing.decode_frame``.
"""

REAL_SFIRMWARE_PAYLOAD = bytes.fromhex("fc fd 01 fd")

# Verbatim from the CLI --dump output (whitespace is accepted by fromhex).
REAL_SGLOBAL_PAYLOAD = bytes.fromhex(
    "8f fb fd a8 01 03 01 30 01 34 01 3d 01 b4 fd a8 fd a8 01 33 01 3d 00 00"
    " 11 00 00 00 00 00 00 00 00 00 00 00 00 00 e8 00 00 00 00 04 ae 04 bf 00"
    " 00 00 00 00 00 00 00 00 00 00 a6 00 00 00 00 01 33 01 2f 01 37 01 31 01"
    " 3b 00 00 00 00 0d aa"
)

# Values shown by the CLI for the sGlobal telegram above (cross-checked
# against the FHEM readings of the same installation).
REAL_SGLOBAL_EXPECTED = {
    "collector_temp": -60.0,  # sensor not connected marker (0xFDA8)
    "outside_temp": 25.9,
    "flow_temp": 30.4,
    "return_temp": 30.8,
    "hot_gas_temp": 31.7,
    "dhw_temp": 43.6,
    "flow_temp_hc2": -60.0,
    "inside_temp": -60.0,
    "evaporator_temp": 30.7,
    "condenser_temp": 31.7,
    "dhw_pump": False,
    "heating_circuit_pump": False,
    "solar_pump": False,
    "mixer_open": False,
    "mixer_closed": False,
    "heat_pipe_valve": False,
    "diverter_valve": False,
    "booster_stage_3": False,
    "booster_stage_2": False,
    "booster_stage_1": False,
    "window_open": False,
    "compressor": False,
    "evu_release": True,
    "oven_fireplace": False,
    "stb": False,
    "quick_air_vent": False,
    "high_pressure_sensor": False,
    "low_pressure_sensor": True,
    "evaporator_ice_monitor": False,
    "signal_anode": False,
    "output_ventilator_power": 0.0,
    "input_ventilator_power": 0.0,
    "main_ventilator_power": 0.0,
    "output_ventilator_speed": 0,
    "input_ventilator_speed": 0,
    "main_ventilator_speed": 0,
    "outside_temp_filtered": 23.2,
    "rel_humidity": 0.0,
    "dew_point": 0.0,
    "pressure_low": 11.98,
    "pressure_high": 12.15,
    "actual_power_qc": 0.0,
    "actual_power_pel": 0.0,
    "flow_rate": 0.0,
    "pressure_hc_water": 1.66,
    "humidity_air_out": 34.98,
}
