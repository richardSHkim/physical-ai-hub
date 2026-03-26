#!/usr/bin/env python

from dataclasses import dataclass

from lerobot.teleoperators.config import TeleoperatorConfig


@dataclass
class PiperLeaderConfigBase:
    """Base configuration for a PiPER leader teleoperator over CAN."""

    can_name: str = "can_leader"
    judge_flag: bool = False
    source_mode: str = "feedback"
    hand_guiding: bool = True
    hand_guiding_mode: str = "free"
    teaching_friction: int = 1  # [1, 10], used when hand_guiding_mode="drag_teach"
    teaching_range_per: int = 100  # [100, 200], used when hand_guiding_mode="drag_teach"
    teaching_max_range_mm: int = 70  # one of {0, 70, 100}, used when hand_guiding_mode="drag_teach"
    gripper_opening_m: float = 0.07


@TeleoperatorConfig.register_subclass("piper_leader")
@dataclass
class PiperLeaderConfig(TeleoperatorConfig, PiperLeaderConfigBase):
    """Configuration for a PiPER leader teleoperator over CAN."""

    def __post_init__(self) -> None:
        if self.source_mode not in {"feedback", "control"}:
            raise ValueError(f"source_mode must be one of 'feedback' or 'control', got {self.source_mode!r}")
        if self.hand_guiding_mode not in {"free", "drag_teach"}:
            raise ValueError(
                f"hand_guiding_mode must be one of 'free' or 'drag_teach', got {self.hand_guiding_mode!r}"
            )
        if self.gripper_opening_m <= 0:
            raise ValueError(f"gripper_opening_m must be > 0, got {self.gripper_opening_m}")
        if not (1 <= int(self.teaching_friction) <= 10):
            raise ValueError(f"teaching_friction must be in [1, 10], got {self.teaching_friction}")
        if not (100 <= int(self.teaching_range_per) <= 200):
            raise ValueError(f"teaching_range_per must be in [100, 200], got {self.teaching_range_per}")
        if int(self.teaching_max_range_mm) not in {0, 70, 100}:
            raise ValueError(
                f"teaching_max_range_mm must be one of 0, 70, 100, got {self.teaching_max_range_mm}"
            )
