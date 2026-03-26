#!/usr/bin/env python

from functools import cached_property
from typing import Any

from lerobot.processor import RobotAction
from lerobot.teleoperators.teleoperator import Teleoperator
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected
from lerobot_teleoperator_piper_leader import PiperLeader, PiperLeaderConfig

from .config_bi_piper_leader import BiPiperLeaderConfig


class BiPiperLeader(Teleoperator):
    """LeRobot Teleoperator plugin for a dual PiPER leader setup."""

    config_class = BiPiperLeaderConfig
    name = "bi_piper_leader"

    def __init__(self, config: BiPiperLeaderConfig):
        super().__init__(config)
        self.config = config
        self.left_arm = PiperLeader(self._make_arm_config(config.left_arm_config, "left"))
        self.right_arm = PiperLeader(self._make_arm_config(config.right_arm_config, "right"))

    def _make_arm_config(self, arm_config: PiperLeaderConfig, side: str) -> PiperLeaderConfig:
        return PiperLeaderConfig(
            id=f"{self.config.id}_{side}" if self.config.id else None,
            calibration_dir=self.config.calibration_dir,
            can_name=arm_config.can_name,
            judge_flag=arm_config.judge_flag,
            source_mode=arm_config.source_mode,
            hand_guiding=arm_config.hand_guiding,
            hand_guiding_mode=arm_config.hand_guiding_mode,
            teaching_friction=arm_config.teaching_friction,
            teaching_range_per=arm_config.teaching_range_per,
            teaching_max_range_mm=arm_config.teaching_max_range_mm,
            gripper_opening_m=arm_config.gripper_opening_m,
        )

    @cached_property
    def action_features(self) -> dict[str, type]:
        return {
            **{f"left_{key}": value for key, value in self.left_arm.action_features.items()},
            **{f"right_{key}": value for key, value in self.right_arm.action_features.items()},
        }

    @cached_property
    def feedback_features(self) -> dict[str, type]:
        return {}

    @property
    def is_connected(self) -> bool:
        return self.left_arm.is_connected and self.right_arm.is_connected

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        self.left_arm.connect(calibrate)
        self.right_arm.connect(calibrate)

    @property
    def is_calibrated(self) -> bool:
        return self.left_arm.is_calibrated and self.right_arm.is_calibrated

    def calibrate(self) -> None:
        self.left_arm.calibrate()
        self.right_arm.calibrate()

    def configure(self) -> None:
        self.left_arm.configure()
        self.right_arm.configure()

    @check_if_not_connected
    def get_action(self) -> RobotAction:
        left_action = self.left_arm.get_action()
        right_action = self.right_arm.get_action()
        return {
            **{f"left_{key}": value for key, value in left_action.items()},
            **{f"right_{key}": value for key, value in right_action.items()},
        }

    def send_feedback(self, feedback: dict[str, Any]) -> None:
        left_feedback = {
            key.removeprefix("left_"): value for key, value in feedback.items() if key.startswith("left_")
        }
        right_feedback = {
            key.removeprefix("right_"): value for key, value in feedback.items() if key.startswith("right_")
        }
        if left_feedback:
            self.left_arm.send_feedback(left_feedback)
        if right_feedback:
            self.right_arm.send_feedback(right_feedback)

    @check_if_not_connected
    def disconnect(self) -> None:
        self.left_arm.disconnect()
        self.right_arm.disconnect()
