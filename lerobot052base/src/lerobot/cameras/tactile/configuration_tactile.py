# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
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
from pathlib import Path

from ..configs import CameraConfig, ColorMode

__all__ = ["TactileCameraConfig", "ColorMode"]


@CameraConfig.register_subclass("tactile")
@dataclass
class TactileCameraConfig(CameraConfig):
    """Configuration class for tactile sensor cameras using TouchSensor API.

    This class provides configuration options for tactile sensors that process
    raw camera frames into tactile RGB images encoding pressure and flow data.

    The tactile RGB image format:
    - Red channel: Pressure matrix (0-255)
    - Green channel: Optical flow X component (0-255)
    - Blue channel: Optical flow Y component (0-255)

    Example configurations:
    ```python
    # Basic configuration
    TactileCameraConfig(usb_id="/dev/video4", finger_id="tactile")

    # With custom tactile processing parameters
    TactileCameraConfig(
        usb_id="/dev/video4",
        finger_id="tactile",
        fps=30,
        width=640,
        height=480,
        pressure_max=50,
        flow_max=10,
        flow_min=-10,
    )
    ```

    Attributes:
        usb_id: USB device ID or path (e.g., "/dev/video4" or 0)
        finger_id: Unique identifier for this tactile sensor
        config_path: Path to YAML configuration file (optional)
        color_mode: Output color mode (RGB or BGR). Defaults to RGB.
        pressure_max: Maximum pressure value for scaling to 255. Defaults to 50.
        flow_max: Maximum flow value for scaling to 255. Defaults to 10.
        flow_min: Minimum flow value for scaling to 0. Defaults to -10.
        warmup_s: Time reading frames before returning from connect (in seconds)
    """

    usb_id: str | int = "/dev/video4"
    finger_id: str = "tactile"
    config_path: str | Path | None = None
    color_mode: ColorMode = ColorMode.RGB
    pressure_max: float = 50.0
    flow_max: float = 2.0
    flow_min: float = -2.0
    warmup_s: int = 20

    def __post_init__(self) -> None:
        self.color_mode = ColorMode(self.color_mode)
        if self.config_path is not None:
            self.config_path = Path(self.config_path)
