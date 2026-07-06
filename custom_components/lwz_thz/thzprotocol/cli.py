"""Standalone CLI to exercise the protocol against real hardware — no HA needed.

Examples::

    thz_cli.py ports
    thz_cli.py --port /dev/ttyUSB1 get sFirmware sGlobal
    thz_cli.py --port /dev/ttyUSB1 get all --dump
    thz_cli.py --tcp 192.168.1.10:2000 raw FB
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import sys

from .client import ThzClient
from .errors import ThzError
from .registers import BLOCKS, ENERGY
from .transport import SerialTransport, TcpTransport, Transport
from .writeparams import WRITE_PARAMS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thz_cli",
        description="Talk to a Stiebel Eltron LWZ / Tecalor THZ heat pump.",
    )
    parser.add_argument("--port", "-p", help="serial device, e.g. /dev/ttyUSB1")
    parser.add_argument("--tcp", help="ser2net endpoint as host:port")
    parser.add_argument("--baud", type=int, default=115200, help="baudrate")
    parser.add_argument("--json", action="store_true", help="output JSON")
    parser.add_argument("--debug", action="store_true", help="verbose logging")

    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("ports", help="list available serial ports")

    get = sub.add_parser("get", help="read and parse register blocks")
    get.add_argument("blocks", nargs="+", help=f"'all' or: {', '.join(BLOCKS)}")
    get.add_argument(
        "--dump", action="store_true", help="also print the raw payload hex"
    )

    raw = sub.add_parser("raw", help="send a raw get command, print payload hex")
    raw.add_argument("command", help="command hex, e.g. FB or 0A0176")

    energy = sub.add_parser("energy", help="read energy/heat meters")
    energy.add_argument("keys", nargs="+", help=f"'all' or: {', '.join(ENERGY)}")

    sub.add_parser("params", help="read all writable parameters")

    set_cmd = sub.add_parser("set", help="write a parameter (with read-back verify)")
    set_cmd.add_argument("param", help=f"one of: {', '.join(WRITE_PARAMS)}")
    set_cmd.add_argument("value", help="new value (number, or mode name for op_mode)")

    monitor = sub.add_parser(
        "monitor", help="poll status blocks in a loop (Ctrl-C to stop)"
    )
    monitor.add_argument(
        "--interval", type=int, default=60, help="seconds between polls (default 60)"
    )
    monitor.add_argument(
        "--blocks",
        nargs="+",
        default=["sGlobal", "sHC1", "sDHW"],
        help="blocks to poll (default: sGlobal sHC1 sDHW)",
    )
    return parser


def _make_transport(args: argparse.Namespace) -> Transport:
    if args.tcp:
        host, _, port = args.tcp.rpartition(":")
        return TcpTransport(host, int(port))
    if args.port:
        return SerialTransport(args.port, args.baud)
    print("error: --port or --tcp is required for this action", file=sys.stderr)
    raise SystemExit(2)


def _cmd_ports() -> int:
    from serial.tools import list_ports

    ports = sorted(list_ports.comports(), key=lambda p: p.device)
    if not ports:
        print("no serial ports found")
    for port in ports:
        print(f"{port.device}  —  {port.description}")
    return 0


async def _cmd_get(client: ThzClient, args: argparse.Namespace) -> int:
    keys = list(BLOCKS) if args.blocks == ["all"] else args.blocks
    result: dict[str, dict[str, object]] = {}
    for key in keys:
        if key not in BLOCKS:
            print(
                f"unknown block '{key}', available: {', '.join(BLOCKS)}",
                file=sys.stderr,
            )
            return 2
        payload = await client.request(BLOCKS[key].command)
        from .registers import parse_block

        values = parse_block(BLOCKS[key], payload)
        result[key] = values
        if args.json:
            continue
        print(f"=== {key} (cmd {BLOCKS[key].command}) ===")
        if args.dump:
            print(f"payload: {payload.hex(' ')}")
        for field_key, value in values.items():
            print(f"  {field_key:28s} {value}")
    if args.json:
        print(json.dumps(result, indent=2))
    return 0


async def _cmd_raw(client: ThzClient, args: argparse.Namespace) -> int:
    payload = await client.request(args.command)
    print(payload.hex(" "))
    return 0


async def _cmd_energy(client: ThzClient, args: argparse.Namespace) -> int:
    keys = list(ENERGY) if args.keys == ["all"] else args.keys
    result: dict[str, str] = {}
    for key in keys:
        if key not in ENERGY:
            print(
                f"unknown meter '{key}', available: {', '.join(ENERGY)}",
                file=sys.stderr,
            )
            return 2
        value = await client.read_energy(key)
        result[key] = f"{value} {ENERGY[key].unit}"
        if not args.json:
            print(f"  {key:24s} {result[key]}")
    if args.json:
        print(json.dumps(result, indent=2))
    return 0


async def _cmd_params(client: ThzClient, args: argparse.Namespace) -> int:
    result: dict[str, object] = {}
    for key, param in WRITE_PARAMS.items():
        value = await client.read_param(key)
        result[key] = value
        if not args.json:
            print(f"  {key:28s} {value}  (cmd {param.command}, {param.type})")
    if args.json:
        print(json.dumps(result, indent=2))
    return 0


async def _cmd_set(client: ThzClient, args: argparse.Namespace) -> int:
    if args.param not in WRITE_PARAMS:
        print(
            f"unknown parameter '{args.param}', available: {', '.join(WRITE_PARAMS)}",
            file=sys.stderr,
        )
        return 2
    value: float | str = args.value
    with contextlib.suppress(ValueError):  # non-numeric = mode name for op_mode
        value = float(args.value)
    before = await client.read_param(args.param)
    print(f"{args.param}: {before} -> {args.value} ...")
    readback = await client.write_param(args.param, value)
    print(f"verified: {args.param} = {readback}")
    return 0


async def _cmd_monitor(client: ThzClient, args: argparse.Namespace) -> int:
    from datetime import datetime

    from .errors import ThzError as _ThzError

    unknown = [key for key in args.blocks if key not in BLOCKS]
    if unknown:
        print(f"unknown block(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    print(f"polling {', '.join(args.blocks)} every {args.interval}s — Ctrl-C stops")
    cycle = 0
    while True:
        cycle += 1
        stamp = datetime.now().strftime("%H:%M:%S")
        for key in args.blocks:
            try:
                values = await client.read_block(key)
            except _ThzError as err:
                print(f"[{stamp}] {key}: ERROR {type(err).__name__}: {err}")
                continue
            interesting = {
                k: v
                for k, v in values.items()
                if not isinstance(v, bool) or v  # skip False bits for brevity
            }
            line = "  ".join(f"{k}={v}" for k, v in interesting.items())
            print(f"[{stamp}] {key} #{cycle}: {line}")
        await asyncio.sleep(args.interval)


async def _run(args: argparse.Namespace) -> int:
    transport = _make_transport(args)
    client = ThzClient(lambda: transport)
    try:
        await client.connect()
        if args.action == "get":
            return await _cmd_get(client, args)
        if args.action == "energy":
            return await _cmd_energy(client, args)
        if args.action == "params":
            return await _cmd_params(client, args)
        if args.action == "set":
            return await _cmd_set(client, args)
        if args.action == "monitor":
            return await _cmd_monitor(client, args)
        return await _cmd_raw(client, args)
    finally:
        await client.disconnect()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.action == "ports":
        return _cmd_ports()
    try:
        return asyncio.run(_run(args))
    except ThzError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
