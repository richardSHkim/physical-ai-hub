"""Mixin providing shared PiPER follower arm hardware interaction methods.

The host class must provide:
  - ``self.config`` with attributes: ``can_name``, ``judge_flag``, ``speed_ratio``,
    ``gripper_effort``, ``gripper_opening_m``, ``startup_enable_timeout_s``, ``cameras``
  - ``self._arm``: will be set to a :class:`C_PiperInterface_V2` instance
  - ``self._connected``: ``bool``
  - ``self.cameras``: ``dict`` of camera instances
"""

from __future__ import annotations

import logging
import time

from .constants import M_TO_001MM, _001DEG_TO_RAD, _001MM_TO_M, RAD_TO_001DEG
from .utils import clamp

logger = logging.getLogger(__name__)


class PiperArmMixin:
    """Shared low-level helpers for PiPER follower arm variants."""

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect_arm(self, *, dh_is_offset: int | None = None) -> None:
        """Create a :class:`C_PiperInterface_V2`, optionally a FK solver, and connect."""
        from piper_sdk import C_PiperInterface_V2

        kwargs: dict = {}
        if dh_is_offset is not None:
            kwargs["dh_is_offset"] = int(dh_is_offset)

        self._arm = C_PiperInterface_V2(self.config.can_name, self.config.judge_flag, **kwargs)

        if dh_is_offset is not None:
            from piper_sdk import C_PiperForwardKinematics

            self._fk = C_PiperForwardKinematics(int(dh_is_offset))

        self._arm.ConnectPort()
        self._connected = True

    def _connect_cameras(self) -> None:
        for cam in self.cameras.values():
            cam.connect()

    # ------------------------------------------------------------------
    # Enable / configure
    # ------------------------------------------------------------------

    def _wait_enable(self) -> None:
        deadline = time.time() + self.config.startup_enable_timeout_s
        while time.time() < deadline:
            if self._arm.EnablePiper():
                return
            time.sleep(0.05)
        raise RuntimeError(
            f"PiPER follower enable timeout after {self.config.startup_enable_timeout_s:.1f}s"
        )

    def _configure_arm(self) -> None:
        self._arm.MotionCtrl_2(0x01, 0x01, int(self.config.speed_ratio), 0x00)
        self._wait_enable()
        self._arm.GripperCtrl(0, int(self.config.gripper_effort), 0x01, 0x00)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def _read_joint_rad(self) -> list[float]:
        joints = self._arm.GetArmJointMsgs().joint_state
        return [
            float(joints.joint_1) * _001DEG_TO_RAD,
            float(joints.joint_2) * _001DEG_TO_RAD,
            float(joints.joint_3) * _001DEG_TO_RAD,
            float(joints.joint_4) * _001DEG_TO_RAD,
            float(joints.joint_5) * _001DEG_TO_RAD,
            float(joints.joint_6) * _001DEG_TO_RAD,
        ]

    def _read_gripper_ratio(self) -> float:
        raw = float(self._arm.GetArmGripperMsgs().gripper_state.grippers_angle) * _001MM_TO_M
        return clamp(raw / self.config.gripper_opening_m, 0.0, 1.0)

    def _read_endpose(self) -> tuple[float, float, float, float, float, float]:
        end_pose = self._arm.GetArmEndPoseMsgs().end_pose
        return (
            float(end_pose.X_axis) * _001MM_TO_M,
            float(end_pose.Y_axis) * _001MM_TO_M,
            float(end_pose.Z_axis) * _001MM_TO_M,
            float(end_pose.RX_axis) * _001DEG_TO_RAD,
            float(end_pose.RY_axis) * _001DEG_TO_RAD,
            float(end_pose.RZ_axis) * _001DEG_TO_RAD,
        )

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def _set_gripper(self, ratio: float) -> float:
        ratio = clamp(float(ratio), 0.0, 1.0)
        stroke_001mm = int(round(ratio * self.config.gripper_opening_m * M_TO_001MM))
        self._arm.GripperCtrl(abs(stroke_001mm), int(self.config.gripper_effort), 0x01, 0x00)
        return ratio

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    def _disconnect_arm(self, *, disable: bool = False) -> None:
        try:
            if disable:
                self._arm.DisableArm(7)
        finally:
            for cam in self.cameras.values():
                cam.disconnect()
            if self._arm is not None:
                self._arm.DisconnectPort()
            self._connected = False
