"""Device clock: decode the sTimedate block and plan a minimal clock sync.

The LWZ keeps its own wall clock — its time programs run on it — and
switches summer time itself (menu "Sommerzeit Automatik"). Every register
write ends up in the controller's EEPROM, so a sync writes only the clock
fields that are actually off. All datetimes here are naive local wall-clock
times; the caller supplies "now" in the same time zone.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

# Offsets below this are left alone: the clock has no seconds register, and
# FHEM's monthly cron job did nothing finer than resetting the minutes.
SYNC_THRESHOLD = timedelta(minutes=2)

# A sync writes up to five registers with read-back (~1 s each). Writes
# start only while both clocks are at most this second of their minute, so
# neither rolls over its minute (or hour, or day) half-way through.
SAFE_SECOND_LIMIT = 40

_HOUR = timedelta(hours=1)


def device_clock(values: Mapping[str, Any]) -> datetime | None:
    """Naive local datetime from parsed sTimedate fields (None if invalid)."""
    try:
        return datetime(
            values["year"],
            values["month"],
            values["day"],
            values["hour"],
            values["minute"],
            values["second"],
        )
    except (KeyError, TypeError, ValueError):
        return None


def clock_offset_minutes(device: datetime, now: datetime) -> float:
    """Device clock minus wall clock in minutes (positive = device ahead)."""
    return round((device - now).total_seconds() / 60, 1)


def plan_clock_sync(device: datetime, now: datetime) -> list[tuple[str, int]]:
    """Clock registers (key, value) to write so the device shows ``now``.

    Nothing is written below SYNC_THRESHOLD. An offset of whole hours (summer
    time not switched) only rewrites the hour; otherwise the minute is set
    from ``now`` too. Date fields are written only when the corrected time
    lands on another day. Order: most significant field first.
    """
    offset = device - now
    if abs(offset) < SYNC_THRESHOLD:
        return []
    hours = round(offset / _HOUR)
    if abs(offset - hours * _HOUR) < SYNC_THRESHOLD:
        target = device - hours * _HOUR
    else:
        target = now.replace(second=device.second, microsecond=device.microsecond)
    fields = (
        ("clock_year", device.year - 2000, target.year - 2000),
        ("clock_month", device.month, target.month),
        ("clock_day", device.day, target.day),
        ("clock_hour", device.hour, target.hour),
        ("clock_minute", device.minute, target.minute),
    )
    return [(key, new) for key, old, new in fields if old != new]


def safe_write_delay(device: datetime, now: datetime) -> int:
    """Whole seconds to wait until both clocks are early in their minute."""
    for delay in range(60):
        if (now.second + delay) % 60 <= SAFE_SECOND_LIMIT and (
            device.second + delay
        ) % 60 <= SAFE_SECOND_LIMIT:
            return delay
    return 0  # pragma: no cover - a 40 s window always overlaps within 60 s
