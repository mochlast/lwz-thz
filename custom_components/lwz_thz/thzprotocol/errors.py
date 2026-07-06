"""Exception hierarchy for the THZ protocol.

Two top-level branches matter to callers:

- ``ThzConnectionError``: the transport is broken (open failed, EOF, OS error).
  The client tears the connection down and reconnects with backoff.
- ``ThzProtocolError``: the request failed but the link is fine (NAK, CRC,
  timeout, unknown register). The connection is kept; only the request fails.
"""


class ThzError(Exception):
    """Base class for all THZ protocol errors."""


class ThzConnectionError(ThzError):
    """Transport-level failure; connection must be re-established."""


class ThzNotConnectedError(ThzConnectionError):
    """Not connected and inside the reconnect-backoff window (fast fail)."""


class ThzProtocolError(ThzError):
    """Protocol-level failure; the connection itself is still usable."""


class ThzTimeoutError(ThzProtocolError):
    """The device did not answer (in time) within a handshake step."""


class ThzNakError(ThzProtocolError):
    """The device rejected a handshake step with NAK (0x15)."""


class ThzChecksumError(ThzProtocolError):
    """Checksum mismatch (response header 01 02 or local verification)."""


class ThzTimingError(ThzProtocolError):
    """The device reported a timing issue (response header 01 01)."""


class ThzUnknownCommandError(ThzProtocolError):
    """The device does not know the command (response header 01 03)."""


class ThzUnknownRegisterError(ThzProtocolError):
    """The device does not know the register (response header 01 04)."""


class ThzWriteVerifyError(ThzError):
    """Read-back after a write returned a different value."""
