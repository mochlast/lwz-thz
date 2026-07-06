"""Async client for the Stiebel Eltron LWZ / Tecalor THZ serial protocol.

This package is intentionally free of any Home Assistant imports so it can be
extracted to a standalone PyPI library later. Protocol knowledge is derived
from the FHEM module 00_THZ.pm (GPL-2.0, immi / Robert Penz et al.), which
serves as the reverse-engineering reference.
"""

from .client import ThzClient
from .errors import (
    ThzChecksumError,
    ThzConnectionError,
    ThzError,
    ThzNakError,
    ThzNotConnectedError,
    ThzProtocolError,
    ThzTimeoutError,
    ThzTimingError,
    ThzUnknownCommandError,
    ThzUnknownRegisterError,
    ThzWriteVerifyError,
)
from .registers import (
    BLOCKS,
    ENERGY,
    BlockDef,
    EnergyDef,
    FieldDef,
    parse_block,
    parse_energy_register,
)
from .transport import SerialTransport, TcpTransport, Transport
from .writeparams import WRITE_PARAMS, WriteParamDef, WriteType

__all__ = [
    "BLOCKS",
    "ENERGY",
    "WRITE_PARAMS",
    "BlockDef",
    "EnergyDef",
    "FieldDef",
    "SerialTransport",
    "TcpTransport",
    "ThzChecksumError",
    "ThzClient",
    "ThzConnectionError",
    "ThzError",
    "ThzNakError",
    "ThzNotConnectedError",
    "ThzProtocolError",
    "ThzTimeoutError",
    "ThzTimingError",
    "ThzUnknownCommandError",
    "ThzUnknownRegisterError",
    "ThzWriteVerifyError",
    "Transport",
    "WriteParamDef",
    "WriteType",
    "parse_block",
    "parse_energy_register",
]
