from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PiperHardwareConfig:
    can_name: str
    base_serial: str
    wrist_serial: str
    width: int
    height: int
    fps: int
    use_depth: bool
    robot_id: str = "piper_follower_01"
    speed_ratio: int = 60
    gripper_opening_m: float = 0.07
    startup_enable_timeout_s: float = 5.0
    max_relative_target: float | None = None


def make_piper_follower(config: PiperHardwareConfig, *, use_ee_pose: bool = False) -> Any:
    from rollout._paths import ensure_local_sources_on_path

    ensure_local_sources_on_path()

    from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
    from lerobot_robot_piper_follower.config_piper_follower import PiperFollowerConfig
    from lerobot_robot_piper_follower.piper_follower import PiperFollower

    robot_config = PiperFollowerConfig(
        id=config.robot_id,
        can_name=config.can_name,
        speed_ratio=config.speed_ratio,
        gripper_opening_m=config.gripper_opening_m,
        startup_enable_timeout_s=config.startup_enable_timeout_s,
        max_relative_target=config.max_relative_target,
        include_endpose_in_observation=use_ee_pose,
        cameras={
            "base": RealSenseCameraConfig(
                serial_number_or_name=config.base_serial,
                width=config.width,
                height=config.height,
                fps=config.fps,
                use_depth=config.use_depth,
            ),
            "wrist": RealSenseCameraConfig(
                serial_number_or_name=config.wrist_serial,
                width=config.width,
                height=config.height,
                fps=config.fps,
                use_depth=config.use_depth,
            ),
        },
    )
    return PiperFollower(robot_config)


def observation_to_openpi_input(
    observation: dict[str, Any],
    task: str,
    *,
    use_ee_pose: bool = False,
) -> dict[str, Any]:
    if use_ee_pose:
        state = np.asarray(
            [
                observation["endpose.x"],
                observation["endpose.y"],
                observation["endpose.z"],
                observation["endpose.roll"],
                observation["endpose.pitch"],
                observation["endpose.yaw"],
                observation["gripper.pos"],
            ],
            dtype=np.float32,
        )
    else:
        state = np.asarray(
            [
                observation["joint_1.pos"],
                observation["joint_2.pos"],
                observation["joint_3.pos"],
                observation["joint_4.pos"],
                observation["joint_5.pos"],
                observation["joint_6.pos"],
                observation["gripper.pos"],
            ],
            dtype=np.float32,
        )
    return {
        "images/base": np.asarray(observation["base"]),
        "images/wrist": np.asarray(observation["wrist"]),
        "state": state,
        "prompt": task,
    }


def action_dict_to_vector(action_dict: dict[str, Any]) -> np.ndarray:
    if "actions" not in action_dict:
        raise KeyError("OpenPI response is missing the 'actions' field.")
    action = np.asarray(action_dict["actions"], dtype=np.float32)
    if action.ndim == 1:
        if action.shape[0] != 7:
            raise ValueError(f"Expected a 7D action, got shape {action.shape}.")
        return action
    if action.ndim == 2:
        if action.shape[1] != 7:
            raise ValueError(f"Expected chunk actions with trailing dim 7, got shape {action.shape}.")
        return action
    raise ValueError(f"Unsupported action tensor shape: {action.shape}")


def vector_to_robot_action(action: np.ndarray, *, use_ee_pose: bool = False) -> dict[str, float]:
    if action.shape != (7,):
        raise ValueError(f"Expected one Piper action with shape (7,), got {action.shape}.")
    if use_ee_pose:
        return {
            "endpose.x": float(action[0]),
            "endpose.y": float(action[1]),
            "endpose.z": float(action[2]),
            "endpose.roll": float(action[3]),
            "endpose.pitch": float(action[4]),
            "endpose.yaw": float(action[5]),
            "gripper.pos": float(action[6]),
        }
    return {
        "joint_1.pos": float(action[0]),
        "joint_2.pos": float(action[1]),
        "joint_3.pos": float(action[2]),
        "joint_4.pos": float(action[3]),
        "joint_5.pos": float(action[4]),
        "joint_6.pos": float(action[5]),
        "gripper.pos": float(action[6]),
    }
