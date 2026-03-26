"""Mixin providing shared PiPER leader teleoperator logic.

The host class must provide:
  - ``self.config`` with attributes: ``can_name``, ``judge_flag``, ``hand_guiding``,
    ``hand_guiding_mode``, ``teaching_friction``, ``teaching_range_per``,
    ``teaching_max_range_mm``, ``gripper_opening_m``, ``source_mode``
  - ``self._arm``: will be set to a :class:`C_PiperInterface_V2` instance
  - ``self._connected``: ``bool``
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from .constants import _001MM_TO_M, _STATUS_POLL_INTERVAL_S, _STATUS_READY_TIMEOUT_S
from .utils import clamp

logger = logging.getLogger(__name__)


class PiperLeaderMixin:
    """Shared low-level helpers for PiPER leader arm variants."""

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect_leader(self) -> None:
        from piper_sdk import C_PiperInterface_V2

        self._arm = C_PiperInterface_V2(self.config.can_name, self.config.judge_flag)
        self._arm.ConnectPort()
        self._connected = True

    # ------------------------------------------------------------------
    # Hand-guiding configuration
    # ------------------------------------------------------------------

    def _configure_hand_guiding(self) -> None:
        """Set up hand-guiding mode (free or drag-teach).

        Call this from the host class's ``configure()`` method.
        """
        if not self.config.hand_guiding:
            return

        if self.config.hand_guiding_mode == "free":
            self._arm.DisableArm(7)
            return

        if self.config.hand_guiding_mode != "drag_teach":
            raise ValueError(
                f"Unsupported hand_guiding_mode={self.config.hand_guiding_mode!r}. "
                "Use 'free' or 'drag_teach'."
            )

        self._validate_hand_guiding_params()

        self._arm.ModeCtrl(0x01, 0x01, 0, 0x00)
        self._arm.EnableArm(7)
        self._wait_for_arm_status()
        self._arm.GripperTeachingPendantParamConfig(
            teaching_range_per=int(self.config.teaching_range_per),
            max_range_config=int(self.config.teaching_max_range_mm),
            teaching_friction=int(self.config.teaching_friction),
        )
        self._wait_for_drag_teach_params()
        self._arm.MotionCtrl_1(0x00, 0x00, 0x01)
        self._wait_for_drag_teach_mode()

    def _validate_hand_guiding_params(self) -> None:
        if not (1 <= int(self.config.teaching_friction) <= 10):
            raise ValueError(
                f"teaching_friction={self.config.teaching_friction} out of range [1, 10]"
            )
        if not (100 <= int(self.config.teaching_range_per) <= 200):
            raise ValueError(
                f"teaching_range_per={self.config.teaching_range_per} out of range [100, 200]"
            )
        if int(self.config.teaching_max_range_mm) not in {0, 70, 100}:
            raise ValueError(
                f"teaching_max_range_mm={self.config.teaching_max_range_mm} invalid. Use one of 0, 70, 100."
            )

    # ------------------------------------------------------------------
    # Polling helpers
    # ------------------------------------------------------------------

    def _wait_until(self, description: str, predicate: Callable[[], bool]) -> None:
        deadline = time.monotonic() + _STATUS_READY_TIMEOUT_S
        last_error = None

        while time.monotonic() < deadline:
            try:
                if predicate():
                    logger.info("%s confirmed", description)
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(_STATUS_POLL_INTERVAL_S)

        if last_error is not None:
            raise RuntimeError(f"Timed out while waiting for {description}") from last_error
        raise RuntimeError(f"Timed out while waiting for {description}")

    def _wait_for_arm_status(self) -> None:
        self._wait_until(
            description="arm status feedback after enabling arm",
            predicate=lambda: getattr(self._arm.GetArmStatus(), "Hz", 0) > 0,
        )

    def _wait_for_drag_teach_params(self) -> None:
        prev_feedback = self._arm.GetGripperTeachingPendantParamFeedback()
        prev_timestamp = float(getattr(prev_feedback, "time_stamp", 0.0) or 0.0)
        self._arm.ArmParamEnquiryAndConfig(param_enquiry=0x04)

        def params_applied() -> bool:
            feedback = self._arm.GetGripperTeachingPendantParamFeedback()
            params = getattr(feedback, "arm_gripper_teaching_param_feedback", None)
            feedback_timestamp = float(getattr(feedback, "time_stamp", 0.0) or 0.0)
            if params is None or feedback_timestamp <= prev_timestamp:
                return False
            return (
                int(getattr(params, "teaching_range_per", -1)) == int(self.config.teaching_range_per)
                and int(getattr(params, "max_range_config", -1)) == int(self.config.teaching_max_range_mm)
                and int(getattr(params, "teaching_friction", -1)) == int(self.config.teaching_friction)
            )

        self._wait_until(
            description="drag-teach parameter feedback",
            predicate=params_applied,
        )

    def _wait_for_drag_teach_mode(self) -> None:
        def drag_teach_active() -> bool:
            status = self._arm.GetArmStatus()
            arm_status = getattr(status, "arm_status", None)
            teach_status = getattr(arm_status, "teach_status", None)
            return int(getattr(teach_status, "value", teach_status)) == 0x01

        self._wait_until(
            description="drag-teach mode activation",
            predicate=drag_teach_active,
        )

    # ------------------------------------------------------------------
    # Gripper read
    # ------------------------------------------------------------------

    def _read_gripper_action(self) -> float:
        """Read gripper value using the configured ``source_mode``."""
        if self.config.source_mode == "control":
            try:
                gripper = self._arm.GetArmGripperCtrl().gripper_ctrl
            except AttributeError:
                gripper = self._arm.GetArmGripperMsgs().gripper_state
        else:
            gripper = self._arm.GetArmGripperMsgs().gripper_state
        gripper_raw = float(gripper.grippers_angle)
        return clamp((gripper_raw * _001MM_TO_M) / self.config.gripper_opening_m, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    def _disconnect_leader(self) -> None:
        if self.config.hand_guiding and self.config.hand_guiding_mode == "drag_teach":
            self._arm.MotionCtrl_1(0x00, 0x00, 0x02)
        self._arm.DisconnectPort()
        self._connected = False
