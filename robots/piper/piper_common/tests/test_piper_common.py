"""Unit tests for piper_common (no hardware required)."""

import math

from piper_common.constants import (
    M_TO_001MM,
    RAD_TO_001DEG,
    _001DEG_TO_RAD,
    _001MM_TO_M,
    _STATUS_POLL_INTERVAL_S,
    _STATUS_READY_TIMEOUT_S,
)
from piper_common.utils import clamp


class TestConstants:
    def test_rad_deg_roundtrip(self):
        angle_rad = 1.0
        assert math.isclose(angle_rad * RAD_TO_001DEG * _001DEG_TO_RAD, angle_rad, rel_tol=1e-12)

    def test_m_mm_roundtrip(self):
        distance_m = 0.5
        assert math.isclose(distance_m * M_TO_001MM * _001MM_TO_M, distance_m, rel_tol=1e-12)

    def test_status_constants_positive(self):
        assert _STATUS_READY_TIMEOUT_S > 0
        assert _STATUS_POLL_INTERVAL_S > 0


class TestClamp:
    def test_within_range(self):
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_below_range(self):
        assert clamp(-1.0, 0.0, 10.0) == 0.0

    def test_above_range(self):
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_at_boundaries(self):
        assert clamp(0.0, 0.0, 10.0) == 0.0
        assert clamp(10.0, 0.0, 10.0) == 10.0
