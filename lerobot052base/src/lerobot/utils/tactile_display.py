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

"""
Tactile sensor real-time display helper for teleoperation and recording.

Provides a large OpenCV window showing the tactile RGB image with overlaid
force information (pressure, shear, touch status) to help the operator
monitor grasp force during teleoperation.
"""

import logging

import cv2
import numpy as np

from lerobot.robots import Robot

logger = logging.getLogger(__name__)


class TactileDisplayHelper:
    """
    Displays tactile sensor data in a large local OpenCV window with force overlays.

    Usage:
        helper = TactileDisplayHelper(robot)
        helper.update()   # call every frame in the control loop
        helper.close()    # cleanup when done
    """

    WINDOW_NAME = "Tactile Feedback (Press 'q' in any OpenCV window to quit)"
    PRESSURE_MAX = 50.0  # match TactileCameraConfig.pressure_max default

    def __init__(self, robot: Robot):
        self.robot = robot
        self.tactile_cam = None
        self.tactile_cam_name = None

        # Find the tactile camera among robot cameras
        if hasattr(robot, "cameras"):
            for cam_name, cam in robot.cameras.items():
                if hasattr(cam, "touch_sensor") and cam.touch_sensor is not None:
                    self.tactile_cam = cam
                    self.tactile_cam_name = cam_name
                    break

        if self.tactile_cam is not None:
            cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.WINDOW_NAME, 800, 600)
            logger.info(
                f"TactileDisplayHelper: tactile camera '{cam_name}' detected. "
                "Large overlay window enabled."
            )
        else:
            logger.info("TactileDisplayHelper: no tactile camera found in robot config.")

    def update(self):
        """Update the display window. Call this in every control-loop iteration."""
        if self.tactile_cam is None:
            return

        try:
            # Peek the latest frame without blocking (max 500 ms old)
            img = self.tactile_cam.read_latest(max_age_ms=500)
        except Exception as e:
            logger.debug(f"TactileDisplayHelper: failed to read latest frame: {e}")
            return

        try:
            # Convert RGB -> BGR for OpenCV drawing if necessary
            if (
                hasattr(self.tactile_cam, "color_mode")
                and str(self.tactile_cam.color_mode).upper() == "RGB"
            ):
                display_img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            else:
                display_img = img.copy()

            ts = self.tactile_cam.touch_sensor

            # Retrieve force & status from the SDK
            fx, fy, fz = ts.get_total_force_filtered()
            status, _, _, _, ft, _ = ts.get_touch_status()
            shear_mag = float((fx**2 + fy**2) ** 0.5)

            h, w = display_img.shape[:2]
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.7
            thickness = 2

            # ---------- 1. Dark overlay for text readability ----------
            overlay = display_img.copy()
            cv2.rectangle(overlay, (10, 10), (430, 170), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, display_img, 0.4, 0, display_img)

            # ---------- 2. Status-dependent colours ----------
            status_lower = str(status).lower()
            if status_lower == "idle":
                status_color = (0, 255, 0)       # green
            elif status_lower == "contact":
                status_color = (0, 255, 255)     # yellow
            elif status_lower == "sliding":
                status_color = (0, 0, 255)       # red
            else:
                status_color = (255, 255, 255)   # white

            texts = [
                (f"Status : {status}", status_color),
                (f"Pressure (fz) : {fz:6.2f}", (255, 255, 255)),
                (f"Shear   (fx,fy): {fx:6.2f}, {fy:6.2f}", (255, 255, 255)),
                (f"Shear Magnitude: {shear_mag:6.2f}", (255, 255, 255)),
                (f"Total Force    : {ft:6.2f}", (255, 255, 255)),
            ]

            y0 = 40
            line_gap = 26
            for i, (txt, col) in enumerate(texts):
                cv2.putText(
                    display_img, txt, (20, y0 + i * line_gap),
                    font, scale, col, thickness, cv2.LINE_AA,
                )

            # ---------- 3. Vertical pressure bar (right side) ----------
            bar_x = w - 70
            bar_y = 50
            bar_h = h - 100
            bar_w = 35

            # Background
            cv2.rectangle(
                display_img,
                (bar_x, bar_y),
                (bar_x + bar_w, bar_y + bar_h),
                (50, 50, 50),
                -1,
            )

            # Fill level (clamp 0..PRESSURE_MAX)
            ratio = min(max(float(fz) / self.PRESSURE_MAX, 0.0), 1.0)
            fill_h = int(bar_h * ratio)
            fill_y = bar_y + bar_h - fill_h

            # Colour gradient: green -> yellow -> red
            if ratio < 0.3:
                bar_color = (0, 255, 0)
            elif ratio < 0.6:
                bar_color = (0, 255, 255)
            else:
                bar_color = (0, 0, 255)

            cv2.rectangle(
                display_img,
                (bar_x, fill_y),
                (bar_x + bar_w, bar_y + bar_h),
                bar_color,
                -1,
            )

            # Ticks
            cv2.putText(display_img, f"{self.PRESSURE_MAX:.0f}", (bar_x + bar_w + 6, bar_y + 14),
                        font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(display_img, f"{self.PRESSURE_MAX/2:.0f}", (bar_x + bar_w + 6, bar_y + bar_h // 2 + 5),
                        font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(display_img, "0", (bar_x + bar_w + 6, bar_y + bar_h),
                        font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

            # ---------- 4. Show ----------
            cv2.imshow(self.WINDOW_NAME, display_img)
            cv2.waitKey(1)  # 1 ms, non-blocking

        except Exception as e:
            logger.debug(f"TactileDisplayHelper: overlay drawing failed: {e}")

    def close(self):
        """Destroy the OpenCV window."""
        if self.tactile_cam is not None:
            try:
                cv2.destroyWindow(self.WINDOW_NAME)
            except Exception:
                pass
            logger.info("TactileDisplayHelper: window closed.")
