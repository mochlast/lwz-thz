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
- **Compressor start diagnostics**: heating integral and the switch-on/off
  hysteresis steps (sHC1) — they show how a start builds up
- **Write access** (verified with read-back): operating mode, room and DHW
  setpoints, fan stages, unscheduled ventilation, heating-curve parameters.
  Ranges follow the Stiebel Eltron operating manuals rather than the narrower
  FHEM constants, and the unit itself has the last word — see below.
- **Control parameters** (disabled by default, enable to read and write):
  hysteresis 1–5 and asymmetry, integral component, flow proportion HC1,
  summer mode threshold and hysteresis, DHW setpoint for manual mode. These
  decide when the compressor starts; here the narrower of FHEM and manual
  range applies
- **Passive cooling** (p75) as a select: off, exhaust air, supply air,
  bypass module, summer cassette (manual LWZ 304/404 Trend; 4.x firmware
  offers the first three)
- **Solar** (option *Solar system installed*): collector, solar DHW and solar
  flow temperature, solar pump, *Solar enabled* (p80) and the solar DHW
  setpoint (p83)
- **Device clock**: the unit's own clock (its time programs run on it) as a
  timestamp sensor plus its offset to Home Assistant in minutes. A button
  syncs it on demand and writes only the fields that are off (minute ≥ 2 min
  off, hour e.g. when summer time was not switched, date across midnight) —
  there is no automatic sync, call the button from an automation if wanted
- **climate** entity (heating circuit thermostat) and **water_heater** entity
- **12 energy/heat meters**, energy-dashboard ready
- **Configurable poll intervals** per register group (status / parameters /
  history / energy / clock) — the serial interface is served strictly one telegram
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
(LWZ/THZ 30x/40x); the 2.x firmware family is not supported. On firmware
7.x (e.g. Tecalor THZ 5.5 eco) the compressor sensor reads the front-display
bit, because the sGlobal bit stays set there while the compressor is off, and
the electrical power (Pel) comes in W instead of kW and is converted.

## Installation

### HACS (recommended)

This integration is part of the HACS default list, so no custom repository
is needed:

1. HACS → search for **Stiebel Eltron LWZ / Tecalor THZ**
2. Download it, then restart Home Assistant

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mochlast&repository=lwz-thz&category=integration)

### Manual

Copy `custom_components/lwz_thz/` into your HA `config/custom_components/`
directory and restart.

### Setup

Settings → Devices & Services → Add integration → *Stiebel Eltron LWZ /
Tecalor THZ* → pick serial port (or ser2net host) — the connection is
verified by reading the firmware version. The last step asks which unit this
is: the service interface reports a firmware version but no model, so the
name shown in the device registry cannot be detected. Model, poll intervals
and HC2/solar support are all changeable later via the integration's
*Configure* dialog.

### Write ranges

The entities offer what the operating manuals list — DHW setpoints, for
instance, run from 10 to 65 °C ("WW-Soll-Tag", identical in the manuals for
LWZ 304 Integral/Trend, LWZ 304/404 SOL and LWZ 5/8 CS Premium).

**Your unit may accept less than that.** Its firmware enforces its own limits
on the service interface, and they can be narrower than what its display
offers. A LWZ 304 Trend on firmware 5.09 takes a DHW setpoint of 55.0 °C but
refuses 56.0 and above — even though 65 can be dialled in at the unit itself.

A refused value is never silently lost. Every write is read back, so:

- the **water heater** card raises the error straight into the UI
- a **number** entity snaps back to the value the pump reports, and the reason
  lands in the log:
  `writing p04_dhw_temp_day = 60.0 failed: device refused this value — …`

Also worth knowing: above roughly 55 °C the compressor alone no longer reaches
the target, and the electric booster (NE) runs — which costs a lot of
electricity.

## Raw telegrams for other firmware

To help support a firmware that is not tested yet, capture the raw telegrams
inside Home Assistant (no serial port juggling, works on Home Assistant OS):

1. *Settings → Devices & services → LWZ/THZ → ⋮ → Enable debug logging*
2. Wait for one status poll (every 5 minutes by default).
3. *⋮ → Disable debug logging*: the browser downloads the log. Lines like
   `FB -> 8f fb fd a8 …` are the raw answers per command.

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
uv run scripts/thz_cli.py --port /dev/ttyUSB1 get sTimedate
uv run scripts/thz_cli.py --port /dev/ttyUSB1 set clock_minute 27
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
