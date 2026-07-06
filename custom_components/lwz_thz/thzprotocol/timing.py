"""Timing constants, derived from the field-proven FHEM module 00_THZ.pm.

The THZ serial interface is timing sensitive. These values mirror what FHEM
uses in production (see THZ_ReadAnswer / THZ_Get_Comunication / THZ_Set):
changing them risks sporadic NAKs and timeouts.
"""

# One handshake step: wait for the ACK/first byte (FHEM simpleReadTimeout,
# user config uses 0.8s).
ACK_TIMEOUT = 0.8

# Upper bound for receiving one complete response frame (FHEM reassembles
# fragments in a bounded double-read loop).
FRAME_TIMEOUT = 2.0

# Settle time after a protocol error before the next request (FHEM sleeps
# 0.1s after every failed handshake step).
ERROR_SETTLE = 0.1

# Wait between a confirmed write and the verification read-back (FHEM: 0.25s).
SET_READBACK_DELAY = 0.25

# Minimum gap between two telegrams so the heat pump controller is never
# hammered (FHEM staggers polls seconds apart; 0.3s keeps a full block sweep
# fast while staying gentle).
INTER_REQUEST_GAP = 0.3

# Reconnect backoff schedule in seconds; the last value repeats.
RECONNECT_BACKOFF = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0)

# Extra delay applied by the poll scheduler to a group after it failed
# (FHEM reschedules failed getters +200s).
GROUP_ERROR_BACKOFF = 200

# Minimum configurable poll interval (FHEM enforces >= 60s).
MIN_POLL_INTERVAL = 60
