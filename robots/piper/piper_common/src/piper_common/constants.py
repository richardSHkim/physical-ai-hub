"""Shared unit-conversion constants for the PiPER robot arm."""

import math

RAD_TO_001DEG = 180000.0 / math.pi
_001DEG_TO_RAD = math.pi / 180000.0
M_TO_001MM = 1_000_000.0
_001MM_TO_M = 1.0 / 1_000_000.0

_STATUS_READY_TIMEOUT_S = 5.0
_STATUS_POLL_INTERVAL_S = 0.1
