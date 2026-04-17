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

from dataclasses import dataclass

from ..config import TeleoperatorConfig


@dataclass
class PiperLeaderConfigBase:
    """Base configuration for the AgileX Piper Leader (teleoperator).

    The Leader arm is used for manual teleoperation:
    - Motors are disabled (torque off) so the arm can be moved by hand
    - Joint positions are read and sent to the Follower arm
    - Communicates via CAN bus using the official Piper SDK
    """

    # CAN port name (e.g., "can0", "can_leader")
    # Must match the interface name configured by can_config.sh
    can_port: str = "can0"

    # Control period in seconds. Piper recommends 200Hz (0.005s)
    control_period: float = 0.005

    # Whether to disable motors for manual dragging mode
    # True = torque disabled, arm can be moved by hand (default for Leader)
    manual_control: bool = True


@TeleoperatorConfig.register_subclass("piper_leader")
@dataclass
class PiperLeaderConfig(TeleoperatorConfig, PiperLeaderConfigBase):
    """Piper Leader configuration class registered with LeRobot."""
    pass
