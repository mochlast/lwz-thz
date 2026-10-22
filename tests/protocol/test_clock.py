"""Device clock: sTimedate telegram, offset and the minimal sync plan."""

from datetime import datetime

import pytest

from thzprotocol import client as client_module, framing
from thzprotocol.client import ThzClient
from thzprotocol.clock import (
    SAFE_SECOND_LIMIT,
    clock_offset_minutes,
    device_clock,
    plan_clock_sync,
    safe_write_delay,
)

from .fake_transport import FakeTransport


def _get_response(command: bytes, data: bytes) -> bytes:
    chk = framing.checksum(framing.HEADER_GET, command + data)
    return (
        framing.HEADER_GET
        + framing.escape(bytes((chk,)) + command + data)
        + framing.FOOTER
    )


@pytest.fixture(autouse=True)
def _fast_timing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(client_module, "INTER_REQUEST_GAP", 0)


class TestReadClock:
    async def test_fc_telegram_over_the_wire(self) -> None:
        # Thursday 22.10.2026 16:43:07. Hour 16 = 0x10 is the DLE byte, so
        # the frame carries it escaped — the decoder must undo that.
        data = bytes((0x03, 16, 43, 7, 26, 10, 22))
        response = _get_response(b"\xfc", data)
        assert b"\x10\x10" in response
        transport = FakeTransport([b"\x10", b"\x10\x02", response])
        client = ThzClient(lambda: transport)
        await client.connect()

        values = await client.read_block("sTimedate")

        assert transport.writes[1] == framing.encode_frame(b"\xfc")
        assert values == {
            "weekday": "thursday",
            "hour": 16,
            "minute": 43,
            "second": 7,
            "year": 2026,
            "month": 10,
            "day": 22,
        }
        assert device_clock(values) == datetime(2026, 10, 22, 16, 43, 7)


class TestDeviceClock:
    def test_invalid_fields_give_none(self) -> None:
        values = {"year": 2026, "month": 2, "day": 30, "hour": 1}
        assert device_clock({**values, "minute": 0, "second": 0}) is None
        assert device_clock({"year": 2026}) is None

    def test_offset_sign_and_rounding(self) -> None:
        now = datetime(2026, 10, 22, 12, 0, 0)
        assert clock_offset_minutes(datetime(2026, 10, 22, 12, 3, 30), now) == 3.5
        assert clock_offset_minutes(datetime(2026, 10, 22, 11, 0, 0), now) == -60.0


NOW = datetime(2026, 10, 22, 11, 1, 10)


class TestPlanClockSync:
    def test_small_offset_writes_nothing(self) -> None:
        assert plan_clock_sync(datetime(2026, 10, 22, 11, 2, 59), NOW) == []
        assert plan_clock_sync(datetime(2026, 10, 22, 10, 59, 20), NOW) == []

    def test_minutes_off_writes_minute_only(self) -> None:
        device = datetime(2026, 10, 22, 11, 5, 40)
        assert plan_clock_sync(device, NOW) == [("clock_minute", 1)]

    def test_summer_time_not_switched_writes_hour_only(self) -> None:
        # 25.10.2026: HA is back on CET, the device still shows CEST.
        now = datetime(2026, 10, 25, 3, 15, 0)
        device = datetime(2026, 10, 25, 4, 15, 20)
        assert plan_clock_sync(device, now) == [("clock_hour", 3)]

    def test_minute_fix_across_the_hour_also_writes_hour(self) -> None:
        device = datetime(2026, 10, 22, 10, 58, 50)
        assert plan_clock_sync(device, NOW) == [
            ("clock_hour", 11),
            ("clock_minute", 1),
        ]

    def test_hour_plus_a_bit_keeps_minutes(self) -> None:
        # 61.5 min ahead just past the hour: shifting by one hour is enough;
        # comparing the hour field alone would have set it two hours back.
        now = datetime(2026, 10, 22, 10, 59, 0)
        device = datetime(2026, 10, 22, 12, 0, 30)
        assert plan_clock_sync(device, now) == [("clock_hour", 11)]

    def test_across_midnight_writes_date_fields(self) -> None:
        now = datetime(2027, 1, 1, 0, 2, 10)
        device = datetime(2026, 12, 31, 23, 58, 0)
        assert plan_clock_sync(device, now) == [
            ("clock_year", 27),
            ("clock_month", 1),
            ("clock_day", 1),
            ("clock_hour", 0),
            ("clock_minute", 2),
        ]


class TestSafeWriteDelay:
    def test_no_wait_early_in_the_minute(self) -> None:
        now = datetime(2026, 10, 22, 11, 1, 10)
        device = datetime(2026, 10, 22, 11, 7, 30)
        assert safe_write_delay(device, now) == 0

    def test_waits_for_both_clocks(self) -> None:
        now = datetime(2026, 10, 22, 11, 1, 50)  # HA late in its minute
        device = datetime(2026, 10, 22, 11, 7, 30)
        delay = safe_write_delay(device, now)
        assert delay == 10  # HA at :00, device at :40
        assert (device.second + delay) % 60 <= SAFE_SECOND_LIMIT

    def test_wait_is_bounded(self) -> None:
        for now_second in range(60):
            for device_second in range(60):
                delay = safe_write_delay(
                    datetime(2026, 1, 1, 0, 0, device_second),
                    datetime(2026, 1, 1, 0, 0, now_second),
                )
                assert delay <= 2 * (59 - SAFE_SECOND_LIMIT) + 1
