#!/usr/bin/env python

from dataclasses import dataclass, field

from lerobot.robots.config import RobotConfig
from lerobot_robot_piper_follower.config_piper_follower import PiperFollowerConfigBase


@RobotConfig.register_subclass("bi_piper_follower")
@dataclass
class BiPiperFollowerConfig(RobotConfig):
    """Configuration for a dual-arm PiPER follower robot."""

    left_arm_config: PiperFollowerConfigBase = field(default_factory=PiperFollowerConfigBase)
    right_arm_config: PiperFollowerConfigBase = field(default_factory=PiperFollowerConfigBase)
