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

from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig

from ..config import RobotConfig


@dataclass
class PiperFollowerConfigBase:
    """Base configuration for the AgileX Piper follower robot.

    Piper is a 6DOF + 1 gripper robotic arm that communicates via CAN bus
    using the official piper_sdk (C_PiperInterface_V2).

    Key characteristics:
    - 6 revolute joints + 1 gripper
    - CAN bus communication (1 Mbps)
    - Joint angle unit in SDK: 0.001 degrees (int)
    - Gripper position unit in SDK: 0.001 mm (int, range 0-1000000)
    - Requires explicit motor enable via EnablePiper()
    """

    # ========== CAN Configuration ==========
    # CAN port name (e.g., "can0", "can_follower")
    # Must match the interface name configured by can_config.sh
    can_port: str = "can0"

    # ========== Control Parameters ==========
    # Motion speed percentage (0-100)
    speed_rate: int = 100

    # Control period in seconds. Piper recommends 200Hz (0.005s)
    control_period: float = 0.005

    # Whether to automatically enable motors on connect
    auto_enable: bool = True

    # ========== Safety Limits ==========
    # Joint limits in radians for 6 joints + gripper (in meters)
    joint_limits: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "joint_1": (-2.967, 2.967),    # ±170°
            "joint_2": (-2.967, 2.967),    # ±170°
            "joint_3": (-2.967, 2.967),    # ±170°
            "joint_4": (-2.967, 2.967),    # ±170°
            "joint_5": (-2.967, 2.967),    # ±170°
            "joint_6": (-2.967, 2.967),    # ±170°
            "gripper": (0.0, 0.1),          # 0-100mm in meters
        }
    )

    # ========== Camera Configuration ==========
    cameras: dict[str, CameraConfig] = field(default_factory=dict)


@RobotConfig.register_subclass("piper_follower")
@dataclass
class PiperFollowerConfig(RobotConfig, PiperFollowerConfigBase):
    """Piper Follower configuration class registered with LeRobot."""
    pass
