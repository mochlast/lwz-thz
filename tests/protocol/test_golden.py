"""Golden tests against telegrams recorded from the real LWZ 304 Trend."""

from thzprotocol import framing
from thzprotocol.registers import BLOCKS, SFIRMWARE, SGLOBAL, parse_block

from .fixtures.telegrams import (
    REAL_SFIRMWARE_PAYLOAD,
    REAL_SGLOBAL_EXPECTED,
    REAL_SGLOBAL_PAYLOAD,
)


class TestRealSGlobal:
    def test_checksum_matches_device(self) -> None:
        # The device-sent checksum byte must match our own algorithm.
        assert REAL_SGLOBAL_PAYLOAD[0] == framing.checksum(
            framing.HEADER_GET, REAL_SGLOBAL_PAYLOAD[1:]
        )

    def test_command_echo(self) -> None:
        assert REAL_SGLOBAL_PAYLOAD[1] == 0xFB

    def test_all_values(self) -> None:
        assert parse_block(SGLOBAL, REAL_SGLOBAL_PAYLOAD) == REAL_SGLOBAL_EXPECTED


class TestRealSFirmware:
    def test_checksum_matches_device(self) -> None:
        assert REAL_SFIRMWARE_PAYLOAD[0] == framing.checksum(
            framing.HEADER_GET, REAL_SFIRMWARE_PAYLOAD[1:]
        )

    def test_version(self) -> None:
        assert parse_block(SFIRMWARE, REAL_SFIRMWARE_PAYLOAD) == {
            "firmware_version": "05.09"
        }


class TestRegistryCompleteness:
    def test_all_439_profile_blocks_present(self) -> None:
        expected = {
            "sGlobal",
            "sHC1",
            "sHC2",
            "sDHW",
            "sControl",
            "sFan",
            "sSol",
            "sHistory",
            "sLast10errors",
            "sTimedate",
            "sFirmware",
            "sFirmwareId",
            "sDisplay",
        }
        assert set(BLOCKS) == expected
