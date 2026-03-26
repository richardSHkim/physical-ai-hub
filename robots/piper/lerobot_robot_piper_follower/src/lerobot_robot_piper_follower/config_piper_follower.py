#!/usr/bin/env python

from dataclasses import dataclass, field
from typing import Literal

from lerobot.cameras import CameraConfig
from lerobot.robots.config import RobotConfig


@dataclass
class PiperFollowerArmFields:
    """Common arm configuration fields shared by all PiPER follower variants."""

    can_name: str = "can_follower"
    judge_flag: bool = False
    speed_ratio: int = 60
    gripper_effort: int = 1000
    gripper_opening_m: float = 0.07
    startup_enable_timeout_s: float = 5.0
    # Keep servo holding by default on script exit to avoid gravity drop.
    disable_torque_on_disconnect: bool = False
    # Backward-compatible alias for older configs.
    disable_on_disconnect: bool | None = None
    cameras: dict[str, CameraConfig] = field(default_factory=dict)


@dataclass
class PiperFollowerConfigBase(PiperFollowerArmFields):
    """Extended configuration for a PiPER follower arm with joint control."""

    dh_is_offset: int = 0x01
    # Per-step max delta (rad) for joint targets to reduce sudden jumps.
    # Can be scalar or per-joint mapping {"joint_1": 0.1, ...}.
    max_relative_target: float | dict[str, float] | None = None
    # Predicted FK workspace bounds in meters. Supported keys: x, y, z.
    # Example: {"x": (0.20, 0.55), "y": (-0.25, 0.25), "z": (0.05, 0.45)}
    workspace_limits: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "x": (-0.031239, 0.549567),
            "y": (-0.331784, 0.284741),
            "z": (0.140518, 1e9),
        }
    )
    # If False, endpose.* is excluded from observation features and samples.
    # This is useful when training with joint-only state inputs.
    include_endpose_in_observation: bool = False
    camera_read_mode: Literal["async", "latest"] = "latest"


@RobotConfig.register_subclass("piper_follower")
@dataclass
class PiperFollowerConfig(RobotConfig, PiperFollowerConfigBase):
    """Configuration for a PiPER follower arm controlled over CAN."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.disable_on_disconnect is not None:
            self.disable_torque_on_disconnect = bool(self.disable_on_disconnect)
        if int(self.dh_is_offset) not in {0, 1}:
            raise ValueError(f"dh_is_offset must be 0 or 1, got {self.dh_is_offset}")
        if not 0 <= int(self.speed_ratio) <= 100:
            raise ValueError(f"speed_ratio must be in [0, 100], got {self.speed_ratio}")
        if self.gripper_opening_m <= 0:
            raise ValueError(f"gripper_opening_m must be > 0, got {self.gripper_opening_m}")
        if self.startup_enable_timeout_s <= 0:
            raise ValueError(
                f"startup_enable_timeout_s must be > 0, got {self.startup_enable_timeout_s}"
            )
        invalid_axes = set(self.workspace_limits) - {"x", "y", "z"}
        if invalid_axes:
            raise ValueError(f"workspace_limits only supports x, y, z keys, got {sorted(invalid_axes)}")
        for axis, bounds in self.workspace_limits.items():
            if len(bounds) != 2:
                raise ValueError(f"workspace_limits[{axis!r}] must be a (min, max) pair, got {bounds!r}")
            lo, hi = float(bounds[0]), float(bounds[1])
            if lo >= hi:
                raise ValueError(
                    f"workspace_limits[{axis!r}] must satisfy min < max, got {(lo, hi)!r}"
                )
