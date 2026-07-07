"""Weekly time programs (FHEM 7prog registers), Mo-So variant.

Register scheme ``<prefix><day-nibble><slot-nibble>`` with day nibbles
Mo=1..So=7, Mo-Fr=8, Sa-So=9, Mo-So=A (FHEM %sets439539common lines
499-618). One register holds two bytes: window start and end in quarter
hours since midnight; 0x80 means "n.a." (window disabled), 0x60 encodes
24:00 (end only).

We expose the Mo-So program: reads come from the Monday register (the
authoritative per-day state), writes go to the Mo-So group register AND
all sub-groups/single days — mirroring FHEM's recursion, because the
device does not reliably propagate group writes itself.

The HA ``time`` entity cannot express 24:00, so 0x60 decodes to 23:59
and any end time >= 23:46 encodes back to 0x60 (lossless round trip).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

NA_BYTE = 0x80
MIDNIGHT_BYTE = 0x60  # 96 quarters = 24:00


@dataclass(frozen=True, slots=True)
class ProgramSlotDef:
    """One weekly program window (Mo-So)."""

    key: str
    read_command: str  # Monday register
    write_commands: tuple[str, ...]  # Mo-So group, sub-groups, single days


def _slot(key: str, prefix: str, slot: int) -> ProgramSlotDef:
    nibble = str(slot)
    # FHEM order for Mo-So: group, Mo-Fr group, Mo..Fr, Sa-So group, Sa, So
    days = ["A", "8", "1", "2", "3", "4", "5", "9", "6", "7"]
    return ProgramSlotDef(
        key=key,
        read_command=f"{prefix}1{nibble}",
        write_commands=tuple(f"{prefix}{day}{nibble}" for day in days),
    )


PROGRAM_SLOTS: dict[str, ProgramSlotDef] = {
    slot.key: slot
    for slot in (
        _slot("hc1_1", "0B14", 0),
        _slot("hc1_2", "0B14", 1),
        _slot("hc1_3", "0B14", 2),
        _slot("dhw_1", "0A17", 0),
        _slot("dhw_2", "0A17", 1),
        _slot("dhw_3", "0A17", 2),
        _slot("fan_1", "0A1D", 0),
        _slot("fan_2", "0A1D", 1),
        _slot("fan_3", "0A1D", 2),
    )
}


def _byte_to_time(value: int) -> time | None:
    if value == NA_BYTE or value > 96:
        return None
    if value == MIDNIGHT_BYTE:
        return time(23, 59)
    return time(value // 4, (value % 4) * 15)


def _time_to_byte(value: time | None, *, is_end: bool) -> int:
    if value is None:
        return NA_BYTE
    if is_end and (value.hour, value.minute) >= (23, 46):
        return MIDNIGHT_BYTE
    return min(value.hour * 4 + value.minute // 15, 95)


def decode_slot(payload: bytes) -> tuple[time | None, time | None]:
    """Decode start/end from a GET response payload (nibbles 8-9 / 10-11)."""
    payload_hex = payload.hex().upper()
    start = _byte_to_time(int(payload_hex[8:10], 16))
    end = _byte_to_time(int(payload_hex[10:12], 16))
    return start, end


def encode_slot(start: time | None, end: time | None) -> str:
    """Encode start/end as the 4-nibble value field of a SET frame."""
    return (
        f"{_time_to_byte(start, is_end=False):02X}{_time_to_byte(end, is_end=True):02X}"
    )


def normalize_slot(
    start: time | None, end: time | None
) -> tuple[time | None, time | None]:
    """What the device will report back after writing (15-min grid)."""
    return (
        _byte_to_time(_time_to_byte(start, is_end=False)),
        _byte_to_time(_time_to_byte(end, is_end=True)),
    )
