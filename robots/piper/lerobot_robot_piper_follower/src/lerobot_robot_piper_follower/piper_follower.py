#!/usr/bin/env python

import logging
import math
from functools import cached_property

from lerobot.cameras.utils import make_cameras_from_configs
from lerobot.processor import RobotAction, RobotObservation
from lerobot.robots.robot import Robot
from lerobot.robots.utils import ensure_safe_goal_position
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected
from piper_common.arm_mixin import PiperArmMixin
from piper_common.constants import RAD_TO_001DEG

from .config_piper_follower import PiperFollowerConfig

logger = logging.getLogger(__name__)


class PiperFollower(PiperArmMixin, Robot):
    """LeRobot Robot plugin for PiPER follower arm."""

    config_class = PiperFollowerConfig
    name = "piper_follower"

    def __init__(self, config: PiperFollowerConfig):
        super().__init__(config)
        self.config = config
        self._arm = None
        self._fk = None
        self._connected = False
        self.cameras = make_cameras_from_configs(config.cameras)

    @property
    def _observation_motors_ft(self) -> dict[str, type]:
        features: dict[str, type] = {
            "joint_1.pos": float,
            "joint_2.pos": float,
            "joint_3.pos": float,
            "joint_4.pos": float,
            "joint_5.pos": float,
            "joint_6.pos": float,
            "gripper.pos": float,
        }
        if self.config.include_endpose_in_observation:
            features.update(
                {
                    "endpose.x": float,
                    "endpose.y": float,
                    "endpose.z": float,
                    "endpose.roll": float,
                    "endpose.pitch": float,
                    "endpose.yaw": float,
                }
            )
        return features

    @property
    def _action_ft(self) -> dict[str, type]:
        return {
            "joint_1.pos": float,
            "joint_2.pos": float,
            "joint_3.pos": float,
            "joint_4.pos": float,
            "joint_5.pos": float,
            "joint_6.pos": float,
            "gripper.pos": float,
        }

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        features = {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3) for cam in self.cameras
        }
        for cam_name, cam_cfg in self.config.cameras.items():
            if getattr(cam_cfg, "use_depth", False):
                features[f"{cam_name}_depth"] = (cam_cfg.height, cam_cfg.width)
        return features

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._observation_motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._action_ft

    @property
    def is_connected(self) -> bool:
        return self._connected and all(cam.is_connected for cam in self.cameras.values())

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        del calibrate
        self._connect_arm(dh_is_offset=self.config.dh_is_offset)
        self._connect_cameras()
        self._configure_arm()
        logger.info("%s connected on %s", self.name, self.config.can_name)

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        return

    @check_if_not_connected
    def configure(self) -> None:
        self._configure_arm()

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        joints = self._read_joint_rad()
        gripper = self._read_gripper_ratio()
        obs_dict: RobotObservation = {
            "joint_1.pos": joints[0],
            "joint_2.pos": joints[1],
            "joint_3.pos": joints[2],
            "joint_4.pos": joints[3],
            "joint_5.pos": joints[4],
            "joint_6.pos": joints[5],
            "gripper.pos": gripper,
        }
        if self.config.include_endpose_in_observation:
            x, y, z, roll, pitch, yaw = self._read_endpose()
            obs_dict.update(
                {
                    "endpose.x": x,
                    "endpose.y": y,
                    "endpose.z": z,
                    "endpose.roll": roll,
                    "endpose.pitch": pitch,
                    "endpose.yaw": yaw,
                }
            )
        for cam_key, cam in self.cameras.items():
            if self.config.camera_read_mode == "latest":
                obs_dict[cam_key] = cam.read_latest()
            else:
                obs_dict[cam_key] = cam.async_read()
            if getattr(cam, "use_depth", False) and hasattr(cam, "read_depth"):
                obs_dict[f"{cam_key}_depth"] = cam.read_depth()

        return obs_dict

    def _predict_endpose_from_joints(self, joints: list[float]) -> tuple[float, float, float, float, float, float]:
        if self._fk is None:
            raise RuntimeError("PiPER forward kinematics is not initialized.")
        pose = self._fk.CalFK(joints)[-1]
        return (
            float(pose[0]) * 1e-3,
            float(pose[1]) * 1e-3,
            float(pose[2]) * 1e-3,
            math.radians(float(pose[3])),
            math.radians(float(pose[4])),
            math.radians(float(pose[5])),
        )

    def _workspace_violations(self, joints: list[float]) -> list[str]:
        if not self.config.workspace_limits:
            return []

        predicted = self._predict_endpose_from_joints(joints)
        predicted_xyz = {"x": predicted[0], "y": predicted[1], "z": predicted[2]}
        violations = []
        for axis, (lo, hi) in self.config.workspace_limits.items():
            value = predicted_xyz[axis]
            if value < lo or value > hi:
                violations.append(f"{axis}={value:.4f} not in [{lo:.4f}, {hi:.4f}]")
        return violations

    def _clip_joints_to_workspace(self, curr: list[float], targets: list[float]) -> list[float]:
        target_violations = self._workspace_violations(targets)
        if not target_violations:
            return targets

        curr_violations = self._workspace_violations(curr)
        if curr_violations:
            logger.warning(
                "PiPER workspace_limits already violated at current pose; keeping current joints. "
                "current=%s target=%s",
                ", ".join(curr_violations),
                ", ".join(target_violations),
            )
            return curr

        lo = 0.0
        hi = 1.0
        clipped = curr
        for _ in range(24):
            alpha = (lo + hi) * 0.5
            candidate = [c + alpha * (t - c) for c, t in zip(curr, targets)]
            if self._workspace_violations(candidate):
                hi = alpha
            else:
                lo = alpha
                clipped = candidate

        clipped_pose = self._predict_endpose_from_joints(clipped)
        logger.warning(
            "Clipped PiPER joint action to satisfy workspace_limits: target=%s clipped_xyz=(%.4f, %.4f, %.4f) alpha=%.3f",
            ", ".join(target_violations),
            clipped_pose[0],
            clipped_pose[1],
            clipped_pose[2],
            lo,
        )
        return clipped

    def _send_joint_action(self, action: RobotAction) -> RobotAction:
        curr = self._read_joint_rad()
        targets = [
            float(action.get("joint_1.pos", curr[0])),
            float(action.get("joint_2.pos", curr[1])),
            float(action.get("joint_3.pos", curr[2])),
            float(action.get("joint_4.pos", curr[3])),
            float(action.get("joint_5.pos", curr[4])),
            float(action.get("joint_6.pos", curr[5])),
        ]
        if self.config.max_relative_target is not None:
            goal_present_pos = {f"joint_{i + 1}": (targets[i], curr[i]) for i in range(6)}
            safe_targets = ensure_safe_goal_position(goal_present_pos, self.config.max_relative_target)
            targets = [float(safe_targets[f"joint_{i + 1}"]) for i in range(6)]
        targets = self._clip_joints_to_workspace(curr, targets)

        self._arm.MotionCtrl_2(0x01, 0x01, int(self.config.speed_ratio), 0x00)
        self._arm.JointCtrl(
            int(round(targets[0] * RAD_TO_001DEG)),
            int(round(targets[1] * RAD_TO_001DEG)),
            int(round(targets[2] * RAD_TO_001DEG)),
            int(round(targets[3] * RAD_TO_001DEG)),
            int(round(targets[4] * RAD_TO_001DEG)),
            int(round(targets[5] * RAD_TO_001DEG)),
        )

        sent: RobotAction = {f"joint_{i + 1}.pos": targets[i] for i in range(6)}
        if "gripper.pos" in action:
            sent["gripper.pos"] = self._set_gripper(float(action["gripper.pos"]))
        return sent

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        has_joint_target = any(
            k in action
            for k in (
                "joint_1.pos",
                "joint_2.pos",
                "joint_3.pos",
                "joint_4.pos",
                "joint_5.pos",
                "joint_6.pos",
            )
        )
        if has_joint_target:
            return self._send_joint_action(action)
        if "gripper.pos" in action:
            return {"gripper.pos": self._set_gripper(float(action["gripper.pos"]))}

        raise ValueError(
            "Unsupported action schema for piper_follower. "
            "Use joint_1.pos..joint_6.pos (+ optional gripper.pos)."
        )

    @check_if_not_connected
    def disconnect(self) -> None:
        try:
            self._disconnect_arm(disable=self.config.disable_torque_on_disconnect)
        finally:
            self._fk = None
            logger.info("%s disconnected", self.name)
