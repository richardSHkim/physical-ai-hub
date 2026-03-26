#!/usr/bin/env python

from dataclasses import dataclass, field

from lerobot.teleoperators.config import TeleoperatorConfig
from lerobot_teleoperator_piper_leader.config_piper_leader import PiperLeaderConfigBase


@TeleoperatorConfig.register_subclass("bi_piper_leader")
@dataclass
class BiPiperLeaderConfig(TeleoperatorConfig):
    """Configuration for a dual-arm PiPER leader teleoperator."""

    left_arm_config: PiperLeaderConfigBase = field(default_factory=PiperLeaderConfigBase)
    right_arm_config: PiperLeaderConfigBase = field(default_factory=PiperLeaderConfigBase)
