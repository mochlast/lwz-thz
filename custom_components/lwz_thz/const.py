"""Constants for the Stiebel Eltron LWZ / Tecalor THZ integration."""

from __future__ import annotations

DOMAIN = "lwz_thz"

# Config entry data
CONF_CONNECTION_TYPE = "connection_type"
CONNECTION_SERIAL = "serial"
CONNECTION_TCP = "tcp"
CONF_PORT = "port"
CONF_BAUDRATE = "baudrate"
CONF_HOST = "host"
CONF_TCP_PORT = "tcp_port"

DEFAULT_BAUDRATE = 115200
DEFAULT_TCP_PORT = 2000

# Options (poll intervals in seconds, feature toggles)
OPT_INTERVAL_STATUS = "interval_status"
OPT_INTERVAL_PARAMS = "interval_params"
OPT_INTERVAL_HISTORY = "interval_history"
OPT_INTERVAL_ENERGY = "interval_energy"
OPT_ENABLE_HC2 = "enable_hc2"
OPT_ENABLE_SOLAR = "enable_solar"

DEFAULT_INTERVAL_STATUS = 300
DEFAULT_INTERVAL_PARAMS = 600
DEFAULT_INTERVAL_HISTORY = 3600
# Hourly so the energy dashboard gets a proper per-hour breakdown
# (24 meter telegrams/h — negligible next to the status polling).
DEFAULT_INTERVAL_ENERGY = 3600

# The coordinator ticks at this rate and only polls groups that are due.
TICK_INTERVAL = 30

# Seconds of click silence before a debounced write goes to the pump
# (numbers and program windows update optimistically in between).
WRITE_DEBOUNCE = 1.0

# Feature identifiers used by entity descriptions
FEATURE_HC2 = "hc2"
FEATURE_SOLAR = "solar"
