#!/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import math
import time
from typing import Any

from lerobot.types import RobotAction
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..teleoperator import Teleoperator
from .config_piper_leader import PiperLeaderConfig

# Import Piper SDK
try:
    from piper_sdk import C_PiperInterface_V2, LogLevel
except ImportError:
    raise ImportError(
        "Piper SDK not installed. Please install it with: pip install piper_sdk"
    )

logger = logging.getLogger(__name__)

# Unit conversion constants
RAD_TO_DEG = 180.0 / math.pi
DEG_TO_RAD = math.pi / 180.0


class PiperLeader(Teleoperator):
    """
    AgileX Piper Leader (teleoperator) implementation.

    Used for master-slave teleoperation mode:
    - Motors are disabled (torque off) so the arm can be moved by hand
    - Reads joint positions in real-time
    - Sends positions to the Follower arm for execution

    This teleoperator uses the official Piper SDK (C_PiperInterface_V2)
    to communicate via CAN bus. It does NOT use LeRobot's MotorsBus abstraction.

    Usage:
        leader = PiperLeader(PiperLeaderConfig(can_port="can_leader"))
        follower = PiperFollower(PiperFollowerConfig(can_port="can_follower"))

        with leader, follower:
            while True:
                action = leader.get_action()
                follower.send_action(action)
    """

    config_class = PiperLeaderConfig
    name = "piper_leader"

    # Joint names for the 6DOF arm
    JOINT_NAMES = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]

    def __init__(self, config: PiperLeaderConfig):
        super().__init__(config)
        self.config = config

        # Initialize Piper SDK interface
        logger.info(f"Initializing Piper Leader on {config.can_port}")
        self.piper = C_PiperInterface_V2(
            can_name=config.can_port,
            judge_flag=False,           # Set False for non-official CAN adapters
            can_auto_init=True,
            logger_level=LogLevel.WARNING,
        )

        self._connected = False

    # ========== Feature Definitions ==========

    @property
    def action_features(self) -> dict[str, type]:
        """Action features produced by this teleoperator."""
        features: dict[str, type] = {}
        for joint in self.JOINT_NAMES:
            features[f"{joint}.pos"] = float
        features["gripper.pos"] = float
        return features

    @property
    def feedback_features(self) -> dict[str, type]:
        """Feedback features (Piper Leader does not support force feedback)."""
        return {}

    # ========== Connection Management ==========

    @property
    def is_connected(self) -> bool:
        """Check if teleoperator is connected."""
        return self._connected

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """
        Connect to the Piper Leader.

        Leader defaults to motors disabled (torque off) for manual dragging.
        """
        logger.info(f"Connecting Piper Leader on {self.config.can_port}...")

        # Connect CAN port
        self.piper.ConnectPort()

        # Disable motors for manual control (hand-guided teleoperation)
        if self.config.manual_control:
            logger.info("Disabling motors for manual control...")
            self.piper.DisablePiper()
            logger.info("Motors disabled, arm is now free to move")

        self._connected = True
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        """Piper does not require LeRobot-style calibration."""
        return True

    def calibrate(self) -> None:
        """Piper does not require calibration - no-op."""
        logger.info("Piper Leader does not require calibration")

    def configure(self) -> None:
        """Configure Leader - disable torque if manual control."""
        if self.config.manual_control:
            self.piper.DisablePiper()

    # ========== Core Interface ==========

    @check_if_not_connected
    def get_action(self) -> RobotAction:
        """
        Get current action from the leader arm (joint positions).

        Reads joint angles and gripper position from the Piper SDK.
        Joint angles are returned in radians, gripper position in meters.

        Returns:
            dict: Action dictionary with joint positions and gripper position
        """
        start = time.perf_counter()

        action: dict[str, Any] = {}

        # Read joint angles from Piper SDK
        joint_msgs = self.piper.GetArmJointMsgs()
        joint_positions = [
            joint_msgs.joint_state.joint_1 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_2 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_3 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_4 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_5 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_6 / 1000.0 * DEG_TO_RAD,
        ]

        for i, joint_name in enumerate(self.JOINT_NAMES):
            action[f"{joint_name}.pos"] = joint_positions[i]

        # Read gripper position
        gripper_msgs = self.piper.GetArmGripperMsgs()
        # SDK unit: 0.001 degrees for angle, convert to meters (approximate)
        gripper_pos_m = gripper_msgs.gripper_state.grippers_angle / (1000.0 * 1000.0)
        action["gripper.pos"] = gripper_pos_m

        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} get_action took: {dt_ms:.1f}ms")



        return action

    def send_feedback(self, feedback: dict[str, float]) -> None:
        """
        Send feedback to the teleoperator.

        Piper Leader does not support force feedback - this is a no-op.
        """
        logger.debug("Piper Leader does not support feedback")

    @check_if_not_connected
    def disconnect(self) -> None:
        """Disconnect from teleoperator, ensure motors are disabled."""
        logger.info(f"Disconnecting {self}...")

        # Ensure motors are disabled before disconnecting (safety)
        self.piper.DisablePiper()
        self.piper.DisconnectPort()

        self._connected = False
        logger.info(f"{self} disconnected.")
