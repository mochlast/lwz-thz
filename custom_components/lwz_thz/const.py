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

# Device model. Asked once in the config flow, editable in the options flow —
# the protocol has no reliable model identifier, only a firmware version.
OPT_MODEL = "model"
DEFAULT_MODEL = "LWZ / THZ"

# Suggestions for the model dropdown. Free text stays allowed (SelectSelector
# custom_value=True), so this list need not be exhaustive.
KNOWN_MODELS = [
    "LWZ 303 SOL",
    "LWZ 403 SOL",
    "LWZ 304 Integral",
    "LWZ 304 Trend",
    "LWZ 404 Trend",
    "LWZ 304 SOL",
    "LWZ 404 SOL",
    "LWZ 504",
    "LWZ 5 CS Premium",
    "LWZ 8 CS Premium",
    "THZ 303 SOL",
    "THZ 403 SOL",
    "THZ 304 eco",
    "THZ 404 eco",
    "THZ 304 SOL",
    "THZ 404 SOL",
    "THZ 504",
    "THZ 5.5 eco",
    "THZ 8.5 eco",
]


def suggest_model(firmware: str | None) -> str:
    """Pre-select a model from the firmware profile — a hint, not a fact.

    4.x ships on the older 30x/40x family, 5.x on the 304/404 family; the
    version alone never names a single unit, so the user can overrule this.
    """
    if firmware and firmware.startswith("4."):
        return "THZ 303 SOL"
    if firmware and firmware.startswith("5."):
        return "LWZ 304 Trend"
    return DEFAULT_MODEL


def manufacturer_for(model: str) -> str:
    """LWZ is sold by Stiebel Eltron, the identical THZ by Tecalor."""
    if model.upper().startswith("THZ"):
        return "Tecalor"
    if model.upper().startswith("LWZ"):
        return "Stiebel Eltron"
    return "Stiebel Eltron / Tecalor"
