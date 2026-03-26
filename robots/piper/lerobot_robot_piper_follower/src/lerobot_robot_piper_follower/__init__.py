#!/usr/bin/env python

from .config_piper_follower import PiperFollowerArmFields, PiperFollowerConfig, PiperFollowerConfigBase
from .piper_follower import PiperFollower

__all__ = ["PiperFollowerArmFields", "PiperFollowerConfig", "PiperFollowerConfigBase", "PiperFollower"]


def main() -> None:
    print("lerobot_robot_piper_follower plugin is installed.")
