#!/usr/bin/env python3
"""Wrapper so the protocol CLI runs straight from the repo checkout."""

from pathlib import Path
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "custom_components" / "lwz_thz")
)

from thzprotocol.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
