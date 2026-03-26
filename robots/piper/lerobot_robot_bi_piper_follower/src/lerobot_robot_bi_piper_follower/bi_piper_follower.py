#!/usr/bin/env python

from functools import cached_property

from lerobot.processor import RobotAction, RobotObservation
from lerobot.robots.robot import Robot
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected
from lerobot_robot_piper_follower import PiperFollower, PiperFollowerConfig

from .config_bi_piper_follower import BiPiperFollowerConfig


class BiPiperFollower(Robot):
    """LeRobot Robot plugin for a dual PiPER follower setup."""

    config_class = BiPiperFollowerConfig
    name = "bi_piper_follower"

    def __init__(self, config: BiPiperFollowerConfig):
        super().__init__(config)
        self.config = config

        self.left_arm = PiperFollower(self._make_arm_config(config.left_arm_config, "left"))
        self.right_arm = PiperFollower(self._make_arm_config(config.right_arm_config, "right"))

        # Compatibility with paths that expect robot.cameras.
        self.cameras = {
            **{f"left_{name}": cam for name, cam in self.left_arm.cameras.items()},
            **{f"right_{name}": cam for name, cam in self.right_arm.cameras.items()},
        }

    def _make_arm_config(self, arm_config: PiperFollowerConfig, side: str) -> PiperFollowerConfig:
        return PiperFollowerConfig(
            id=f"{self.config.id}_{side}" if self.config.id else None,
            calibration_dir=self.config.calibration_dir,
            can_name=arm_config.can_name,
            judge_flag=arm_config.judge_flag,
            dh_is_offset=arm_config.dh_is_offset,
            speed_ratio=arm_config.speed_ratio,
            gripper_effort=arm_config.gripper_effort,
            gripper_opening_m=arm_config.gripper_opening_m,
            startup_enable_timeout_s=arm_config.startup_enable_timeout_s,
            disable_torque_on_disconnect=arm_config.disable_torque_on_disconnect,
            disable_on_disconnect=arm_config.disable_on_disconnect,
            max_relative_target=arm_config.max_relative_target,
            workspace_limits=arm_config.workspace_limits,
            include_endpose_in_observation=arm_config.include_endpose_in_observation,
            camera_read_mode=arm_config.camera_read_mode,
            cameras=arm_config.cameras,
        )

    @property
    def _motors_ft(self) -> dict[str, type]:
        return {
            **{f"left_{key}": value for key, value in self.left_arm._observation_motors_ft.items()},
            **{f"right_{key}": value for key, value in self.right_arm._observation_motors_ft.items()},
        }

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        return {
            **{f"left_{key}": value for key, value in self.left_arm._cameras_ft.items()},
            **{f"right_{key}": value for key, value in self.right_arm._cameras_ft.items()},
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return {
            **{f"left_{key}": value for key, value in self.left_arm._action_ft.items()},
            **{f"right_{key}": value for key, value in self.right_arm._action_ft.items()},
        }

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
    def get_observation(self) -> RobotObservation:
        left_obs = self.left_arm.get_observation()
        right_obs = self.right_arm.get_observation()
        return {
            **{f"left_{key}": value for key, value in left_obs.items()},
            **{f"right_{key}": value for key, value in right_obs.items()},
        }

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        left_action = {
            key.removeprefix("left_"): value for key, value in action.items() if key.startswith("left_")
        }
        right_action = {
            key.removeprefix("right_"): value for key, value in action.items() if key.startswith("right_")
        }

        sent_action: RobotAction = {}
        if left_action:
            sent_left = self.left_arm.send_action(left_action)
            sent_action.update({f"left_{key}": value for key, value in sent_left.items()})
        if right_action:
            sent_right = self.right_arm.send_action(right_action)
            sent_action.update({f"right_{key}": value for key, value in sent_right.items()})
        return sent_action

    @check_if_not_connected
    def disconnect(self) -> None:
        self.left_arm.disconnect()
        self.right_arm.disconnect()
