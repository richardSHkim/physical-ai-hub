"""Shared utility functions for PiPER plugins."""


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp *x* to the closed interval [lo, hi]."""
    return min(max(x, lo), hi)
