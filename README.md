# Stiebel Eltron LWZ / Tecalor THZ — Home Assistant Integration

Home Assistant custom integration for **Stiebel Eltron LWZ** and **Tecalor
THZ** integral heat pumps (e.g. LWZ/THZ 303/304/404) connected via their
**serial service interface** (USB, 115200 baud) — no ISG/IP module required.

Protocol knowledge is derived from the FHEM module 00_THZ.pm (GPL-2.0,
immi / Robert Penz et al.). This project is a clean re-implementation, not a
port: one declarative register table, strict telegram serialization, robust
reconnect handling and per-group poll intervals.

## Features

- **~50 sensors**: all temperatures, pressures, humidity, fan speeds,
  thermal/electrical power, flow rate, operating hours, fault memory
- **~30 binary sensors**: compressor, pumps, booster stages, valves,
  EVU release, defrost, filter-change and service indicators
- **Write access** (verified with read-back): operating mode, room and DHW
  setpoints, fan stages, unscheduled ventilation, heating-curve parameters
- **climate** entity (heating circuit thermostat) and **water_heater** entity
- **12 energy/heat meters**, energy-dashboard ready
- **Configurable poll intervals** per register group (status / parameters /
  history / energy) — the serial interface is served strictly one telegram
  at a time, mirroring the field-proven FHEM timing
- Config flow with connection test, options flow, diagnostics, en/de
  translations
- Extras in `dashboard/`: a control dashboard, FHEM-style graph dashboard
  templates and a heating-curve custom card

## Requirements

- Home Assistant 2026.6 or newer
- The heat pump's USB service port mapped into the HA container
  (e.g. `devices: ["/dev/lwz304:/dev/lwz304"]` in docker-compose, ideally
  via a udev alias) — or a ser2net bridge (TCP)
- **Exclusive port access**: stop FHEM or any other reader first

Tested on a LWZ 304 Trend (firmware 5.09). Firmware profile 4.39/5.39
(LWZ/THZ 30x/40x); the 2.x firmware family is not supported.

## Installation

### HACS (recommended)

1. HACS → Custom repositories → add `https://github.com/mochlast/lwz-thz`
   as type *Integration*
2. Install **Stiebel Eltron LWZ / Tecalor THZ**, restart Home Assistant

### Manual

Copy `custom_components/lwz_thz/` into your HA `config/custom_components/`
directory and restart.

### Setup

Settings → Devices & Services → Add integration → *Stiebel Eltron LWZ /
Tecalor THZ* → pick serial port (or ser2net host) — the connection is
verified by reading the firmware version. Poll intervals and HC2/solar
support are configurable via the integration's *Configure* dialog.

## CLI (no Home Assistant required)

The protocol layer is HA-independent and ships with a CLI for bring-up and
debugging:

```sh
uv run scripts/thz_cli.py ports
uv run scripts/thz_cli.py --port /dev/ttyUSB1 get sFirmware sGlobal
uv run scripts/thz_cli.py --port /dev/ttyUSB1 get all --dump
uv run scripts/thz_cli.py --port /dev/ttyUSB1 energy all
uv run scripts/thz_cli.py --port /dev/ttyUSB1 params
uv run scripts/thz_cli.py --port /dev/ttyUSB1 set p07_fan_stage_day 2
uv run scripts/thz_cli.py --port /dev/ttyUSB1 monitor --interval 60
```

## Development

Uses [uv](https://docs.astral.sh/uv/):

```sh
uv sync            # venv with dev dependencies (incl. HA test harness)
uv run pytest -q   # 130+ tests: protocol golden tests, HA component tests
uv run ruff check .
```

Repository layout:

- `custom_components/lwz_thz/` — the integration
  - `thzprotocol/` — HA-independent async protocol library (framing,
    handshake, transports, register tables, CLI); extractable to PyPI
- `scripts/thz_cli.py` — CLI wrapper
- `tests/` — pytest suite
- `dashboard/` — dashboard templates + heating-curve custom card. The
  control dashboard (`heizung.json`) is a Lovelace template built on the
  HACS cards **Mushroom**, **button-card** and **stack-in-card**; its
  advanced settings (weekly time programs, unscheduled-ventilation
  durations) open in **browser_mod** popups, so install browser_mod and
  add its integration before importing the dashboard.

## Credits & License

This integration stands on the shoulders of the FHEM community, which
reverse-engineered and maintained the THZ/LWZ serial protocol for over a
decade:

- [00_THZ.pm](https://svn.fhem.de/trac/browser/trunk/fhem/FHEM/00_THZ.pm) —
  the FHEM THZ module by *immi*, based on the protocol analysis by
  [Robert Penz](https://robert.penz.name/heat-pump-lwz/)
- [FHEM wiki: Tecalor THZ Wärmepumpe](https://wiki.fhem.de/wiki/Tecalor_THZ_W%C3%A4rmepumpe)
- [FHEM forum thread](https://forum.fhem.de/index.php?topic=13132.0) —
  years of register documentation and firmware findings

License: [GPL-2.0](LICENSE) (inherited from the FHEM reference).

*This project is not affiliated with Stiebel Eltron or Tecalor. Writing
parameters to your heat pump is at your own risk.*
