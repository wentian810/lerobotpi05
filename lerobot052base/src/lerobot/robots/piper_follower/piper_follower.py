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
from functools import cached_property
from typing import Any

from lerobot.cameras import make_cameras_from_configs
from lerobot.types import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..robot import Robot
from .config_piper_follower import PiperFollowerConfig

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
PIPER_ANGLE_FACTOR = 1000.0 * 180.0 / math.pi  # 57295.7795, radians to SDK units (0.001 degrees)


class PiperFollower(Robot):
    """
    AgileX Piper 6DOF+1 robotic arm Follower implementation.

    This robot uses the official Piper SDK (C_PiperInterface_V2) to communicate
    with the arm via CAN bus. It does NOT use LeRobot's MotorsBus abstraction,
    as Piper has its own complete control stack.

    Key characteristics:
    - 6 revolute joints + 1 gripper
    - CAN bus communication at 1 Mbps
    - Joint angles in radians (converted to/from SDK's 0.001 degree units)
    - Gripper position in meters (converted to/from SDK's 0.001 mm units)
    - No LeRobot-style calibration needed (is_calibrated always True)

    Usage:
        config = PiperFollowerConfig(can_port="can0")
        robot = PiperFollower(config)
        with robot:
            obs = robot.get_observation()
            robot.send_action({"joint_1.pos": 0.5, "gripper.pos": 0.05})
    """

    config_class = PiperFollowerConfig
    name = "piper_follower"

    # Joint names for the 6DOF arm
    JOINT_NAMES = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]

    def __init__(self, config: PiperFollowerConfig):
        super().__init__(config)
        self.config = config

        # Initialize Piper SDK interface
        logger.info(f"Initializing Piper interface on {config.can_port}")
        self.piper = C_PiperInterface_V2(
            can_name=config.can_port,
            judge_flag=False,           # Set False for non-official CAN adapters
            can_auto_init=True,
            logger_level=LogLevel.WARNING,
        )

        # Initialize cameras
        self.cameras = make_cameras_from_configs(config.cameras)

        # State cache for last known positions
        self._last_joint_positions = [0.0] * 6
        self._last_gripper_position = 0.0
        self._connected = False

    # ========== Feature Definitions ==========

    @property
    def _joints_ft(self) -> dict[str, type]:
        """Joint features for observation and action spaces."""
        features: dict[str, type] = {}
        for joint in self.JOINT_NAMES:
            features[f"{joint}.pos"] = float
        features["gripper.pos"] = float
        return features

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        """Camera features for observation space."""
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3)
            for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        """Combined observation features (joints + cameras)."""
        return {**self._joints_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        """Action features match joint features."""
        return self._joints_ft

    # ========== Connection Management ==========

    @property
    def is_connected(self) -> bool:
        """Check if robot is connected."""
        return self._connected and all(
            cam.is_connected for cam in self.cameras.values()
        )

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """
        Connect to the Piper arm.

        Flow:
        1. Connect CAN port and start SDK threads
        2. Enable motors (with timeout)
        3. Connect cameras
        """
        logger.info(f"Connecting Piper Follower on {self.config.can_port}...")

        # 1. Connect CAN port
        self.piper.ConnectPort()

        # 2. Enable motors if configured
        if self.config.auto_enable:
            logger.info("Enabling Piper motors...")
            timeout = 5.0
            start_time = time.time()
            while not self.piper.EnablePiper():
                if time.time() - start_time > timeout:
                    raise RuntimeError(
                        "Failed to enable Piper motors within timeout. "
                        "Check power supply and CAN connection."
                    )
                time.sleep(0.01)
            logger.info("Piper motors enabled")

        # 3. Connect cameras
        for cam in self.cameras.values():
            cam.connect()

        self._connected = True
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        """Piper does not require LeRobot-style calibration."""
        return True

    def calibrate(self) -> None:
        """Piper does not require calibration - no-op."""
        logger.info("Piper does not require calibration")

    def configure(self) -> None:
        """Configure Piper parameters - handled by SDK."""
        pass

    def setup_motors(self) -> None:
        """Piper motors are factory-configured."""
        raise NotImplementedError(
            "Piper motor configuration is done via the official SDK tools."
        )

    # ========== Core Control Interface ==========

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        """
        Get current observation (joint angles + camera images).

        Joint angles are returned in radians.
        Gripper position is returned in meters.

        Returns:
            dict: Observation dictionary with joint positions and camera images
        """
        start = time.perf_counter()
        obs_dict: dict[str, Any] = {}

        # 1. Read joint angles from Piper SDK
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
            obs_dict[f"{joint_name}.pos"] = joint_positions[i]

        # 2. Read gripper position
        gripper_msgs = self.piper.GetArmGripperMsgs()
        # SDK unit: 0.001 degrees for angle, convert to meters (approximate)
        gripper_pos_mm = gripper_msgs.gripper_state.grippers_angle / 1000.0
        obs_dict["gripper.pos"] = gripper_pos_mm / 1000.0  # Convert to meters

        # 3. Read camera images
        for cam_key, cam in self.cameras.items():
            obs_dict[cam_key] = cam.read_latest()

        # Update state cache
        self._last_joint_positions = joint_positions
        self._last_gripper_position = gripper_pos_mm / 1000.0

        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} get_observation took: {dt_ms:.1f}ms")

        return obs_dict

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        """
        Send action command to Piper arm.

        Args:
            action: Action dictionary with joint positions in radians and
                    gripper position in meters. Example:
                    {
                        "joint_1.pos": 0.5,      # radians
                        "joint_2.pos": -0.3,
                        ...
                        "gripper.pos": 0.05,      # meters (0-0.1)
                    }

        Returns:
            The action actually sent (potentially clipped by joint limits)
        """
        # 1. Extract and convert joint targets (radians -> SDK units: 0.001 degrees)
        joint_targets = []
        for idx, joint_name in enumerate(self.JOINT_NAMES):
            key = f"{joint_name}.pos"
            if key in action:
                target_rad = action[key]

                # Apply joint limits (in radians)
                if joint_name in self.config.joint_limits:
                    min_rad, max_rad = self.config.joint_limits[joint_name]
                    clipped = max(min_rad, min(max_rad, target_rad))
                    if clipped != target_rad:
                        logger.debug(
                            f"Clipped {joint_name} from {target_rad:.4f} rad to {clipped:.4f} rad"
                        )
                    target_rad = clipped

                # Convert radians -> 0.001 degrees (SDK unit)
                target_sdk = int(round(float(target_rad) * RAD_TO_DEG * 1000))
                joint_targets.append(target_sdk)
            else:
                # Use cached last position
                target_sdk = int(round(float(self._last_joint_positions[idx]) * RAD_TO_DEG * 1000))
                joint_targets.append(target_sdk)

        # 2. Extract and convert gripper target (meters -> SDK units: 0.001 mm)
        gripper_target = 500000  # Default: half open
        if "gripper.pos" in action:
            gripper_m = action["gripper.pos"]
            # Apply gripper limits
            if "gripper" in self.config.joint_limits:
                min_m, max_m = self.config.joint_limits["gripper"]
                gripper_m = max(min_m, min(max_m, gripper_m))
            # Convert meters -> 0.001 mm
            gripper_target = int(float(gripper_m) * 1000 * 1000)

        # 3. Set motion mode (MOVE J - joint space motion)
        self.piper.MotionCtrl_2(
            ctrl_mode=0x01,              # CAN control mode
            move_mode=0x01,              # MOVE J (joint space)
            move_spd_rate_ctrl=self.config.speed_rate,
            is_mit_mode=0x00,
        )

        # 4. Send joint control command
        self.piper.JointCtrl(*joint_targets)

        # 5. Send gripper control
        self.piper.GripperCtrl(
            gripper_angle=gripper_target,
            gripper_effort=1000,         # Maximum force
            gripper_code=0x01,           # Enable control
            set_zero=0
        )

        # 6. Build return value (actual sent values in original units)
        result: dict[str, float] = {}
        for i, joint_name in enumerate(self.JOINT_NAMES):
            result[f"{joint_name}.pos"] = joint_targets[i] / 1000.0 * DEG_TO_RAD
        result["gripper.pos"] = gripper_target / (1000.0 * 1000.0)

        return result

    @check_if_not_connected
    def disconnect(self) -> None:
        """Disconnect from Piper arm, disable motors for safety."""
        logger.info(f"Disconnecting {self}...")

        # Disable motors
        self.piper.DisablePiper()

        # Disconnect CAN port
        self.piper.DisconnectPort()

        # Disconnect cameras
        for cam in self.cameras.values():
            cam.disconnect()

        self._connected = False
        logger.info(f"{self} disconnected.")
