#!/usr/bin/env python

from .bi_piper_leader import BiPiperLeader
from .config_bi_piper_leader import BiPiperLeaderConfig

__all__ = ["BiPiperLeader", "BiPiperLeaderConfig"]


def main() -> None:
    print("lerobot_teleoperator_bi_piper_leader plugin is installed.")
