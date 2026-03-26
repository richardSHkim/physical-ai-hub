#!/usr/bin/env python

import logging
from functools import cached_property
from typing import Any

from lerobot.processor import RobotAction
from lerobot.teleoperators.teleoperator import Teleoperator
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected
from piper_common.constants import _001DEG_TO_RAD
from piper_common.leader_mixin import PiperLeaderMixin

from .config_piper_leader import PiperLeaderConfig

logger = logging.getLogger(__name__)


class PiperLeader(PiperLeaderMixin, Teleoperator):
    """LeRobot Teleoperator plugin for PiPER leader arm."""

    config_class = PiperLeaderConfig
    name = "piper_leader"

    def __init__(self, config: PiperLeaderConfig):
        super().__init__(config)
        self.config = config
        self._arm = None
        self._connected = False

    @cached_property
    def action_features(self) -> dict[str, type]:
        return {
            "joint_1.pos": float,
            "joint_2.pos": float,
            "joint_3.pos": float,
            "joint_4.pos": float,
            "joint_5.pos": float,
            "joint_6.pos": float,
            "gripper.pos": float,
        }

    @cached_property
    def feedback_features(self) -> dict[str, type]:
        return {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        del calibrate
        self._connect_leader()
        self._configure_hand_guiding()
        logger.info("%s connected on %s", self.name, self.config.can_name)

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        return

    @check_if_not_connected
    def configure(self) -> None:
        self._configure_hand_guiding()

    @check_if_not_connected
    def get_action(self) -> RobotAction:
        if self.config.source_mode == "control":
            try:
                joints = self._arm.GetArmJointCtrl().joint_ctrl
            except AttributeError:
                logger.warning(
                    "source_mode=control requested but control frames are unavailable in this piper_sdk build; "
                    "falling back to feedback frames."
                )
                joints = self._arm.GetArmJointMsgs().joint_state
        else:
            joints = self._arm.GetArmJointMsgs().joint_state

        return {
            "joint_1.pos": float(joints.joint_1) * _001DEG_TO_RAD,
            "joint_2.pos": float(joints.joint_2) * _001DEG_TO_RAD,
            "joint_3.pos": float(joints.joint_3) * _001DEG_TO_RAD,
            "joint_4.pos": float(joints.joint_4) * _001DEG_TO_RAD,
            "joint_5.pos": float(joints.joint_5) * _001DEG_TO_RAD,
            "joint_6.pos": float(joints.joint_6) * _001DEG_TO_RAD,
            "gripper.pos": self._read_gripper_action(),
        }

    def send_feedback(self, feedback: dict[str, Any]) -> None:
        del feedback
        return

    @check_if_not_connected
    def disconnect(self) -> None:
        self._disconnect_leader()
        logger.info("%s disconnected", self.name)
