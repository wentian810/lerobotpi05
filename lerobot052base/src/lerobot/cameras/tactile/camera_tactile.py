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

"""
Provides the TactileCamera class for capturing processed tactile sensor images.
"""

import logging
import time
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

import cv2
from numpy.typing import NDArray

from lerobot.cameras.camera import Camera
from lerobot.cameras.configs import ColorMode
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected
from lerobot.utils.errors import DeviceNotConnectedError

from .configuration_tactile import TactileCameraConfig

# Import TouchSensor from stouch_sdk
try:
    from stouch_sdk.api.touch_sensor import TouchSensor
except ImportError:
    TouchSensor = None

logger = logging.getLogger(__name__)


class TactileCamera(Camera):
    """
    Manages tactile sensor interactions using TouchSensor SDK.

    This class provides a high-level interface to connect to, configure, and read
    processed tactile images from sensors. It wraps the TouchSensor API which
    processes raw camera frames into RGB images encoding pressure and flow data.

    The tactile RGB image format:
    - Red channel: Pressure matrix (0-255)
    - Green channel: Optical flow X component (0-255)
    - Blue channel: Optical flow Y component (0-255)

    An TactileCamera instance requires a USB device ID (e.g., '/dev/video4' on Linux
    or 0 for device index). The TouchSensor SDK handles the low-level camera
    communication and tactile processing.
    """

    def __init__(self, config: TactileCameraConfig):
        """
        Initializes the TactileCamera instance.

        Args:
            config: The configuration settings for the tactile sensor.

        Raises:
            ImportError: If stouch_sdk is not installed.
        """
        super().__init__(config)

        if TouchSensor is None:
            raise ImportError(
                "stouch_sdk is not installed. Please install it to use TactileCamera."
            )

        self.config = config
        self.usb_id = config.usb_id
        self.finger_id = config.finger_id
        self.config_path = config.config_path
        self.color_mode = config.color_mode
        self.pressure_max = config.pressure_max
        self.flow_max = config.flow_max
        self.flow_min = config.flow_min
        self.warmup_s = config.warmup_s

        self.touch_sensor: TouchSensor | None = None

        # Threading components for async reading
        self.thread: Thread | None = None
        self.stop_event: Event | None = None
        self.frame_lock: Lock = Lock()
        self.latest_frame: NDArray[Any] | None = None
        self.latest_timestamp: float | None = None
        self.new_frame_event: Event = Event()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.usb_id}, finger_id={self.finger_id})"

    @property
    def is_connected(self) -> bool:
        """Checks if the tactile sensor is currently connected and opened."""
        return (
            self.touch_sensor is not None
            and self.touch_sensor.cap is not None
            and self.touch_sensor.cap.isOpened()
        )

    @check_if_already_connected
    def connect(self, warmup: bool = True) -> None:
        """
        Connects to the tactile sensor specified in the configuration.

        Initializes the TouchSensor object, performs calibration, starts the
        background reading thread and performs initial checks.
        """
        logger.info(f"Initializing TouchSensor on {self.usb_id}...")

        try:
            # Initialize TouchSensor
            # Note: TouchSensor handles its own camera initialization via camera_init()
            self.touch_sensor = TouchSensor(
                usb_id=self.usb_id,
                finger_id=self.finger_id,
            )
            
            # If config_path is provided, reload config
            if self.config_path is not None:
                self.touch_sensor.load_config(str(self.config_path))

        except Exception as e:
            raise ConnectionError(
                f"Failed to initialize TouchSensor on {self.usb_id}: {e}"
            ) from e

        # Start background reading thread
        self._start_read_thread()

        if warmup and self.warmup_s > 0:
            start_time = time.time()
            while time.time() - start_time < self.warmup_s:
                try:
                    self.async_read(timeout_ms=self.warmup_s * 1000)
                    time.sleep(0.1)
                except TimeoutError:
                    continue
            
            with self.frame_lock:
                if self.latest_frame is None:
                    raise ConnectionError(
                        f"{self} failed to capture frames during warmup."
                    )

        logger.info(f"{self} connected.")

    def _read_from_hardware(self) -> NDArray[Any]:
        """
        Reads a raw frame from the tactile sensor and converts to tactile RGB.

        Returns:
            np.ndarray: The tactile RGB image.
        """
        if self.touch_sensor is None:
            raise DeviceNotConnectedError(f"{self} touch_sensor is not initialized")

        # Step 1: Preprocess frame (reads from camera and applies preprocessing)
        self.touch_sensor.preprocess_frame()

        # Step 2: Generate tactile RGB image with target size
        # Note: target_size is (width, height) as per OpenCV convention
        tactile_rgb = self.touch_sensor.get_tactile_rgb(
            pressure_max=self.pressure_max,
            flow_max=self.flow_max,
            flow_min=self.flow_min,
            target_size=(self.config.width, self.config.height),
        )

        return tactile_rgb

    def _postprocess_image(self, image: NDArray[Any]) -> NDArray[Any]:
        """
        Applies color conversion to match the configured color mode.

        Args:
            image: The raw tactile RGB image (RGB format from TouchSensor).

        Returns:
            np.ndarray: The processed image in the configured color mode.
        """
        processed_image = image
        
        # TouchSensor.get_tactile_rgb() returns RGB by default
        # Convert to BGR if requested
        if self.color_mode == ColorMode.BGR:
            processed_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        return processed_image

    def _read_loop(self) -> None:
        """
        Internal loop run by the background thread for asynchronous reading.
        """
        if self.stop_event is None:
            raise RuntimeError(f"{self}: stop_event is not initialized before starting read loop.")

        failure_count = 0
        while not self.stop_event.is_set():
            try:
                raw_frame = self._read_from_hardware()
                processed_frame = self._postprocess_image(raw_frame)
                capture_time = time.perf_counter()

                with self.frame_lock:
                    self.latest_frame = processed_frame
                    self.latest_timestamp = capture_time
                self.new_frame_event.set()
                failure_count = 0

            except DeviceNotConnectedError:
                break
            except Exception as e:
                if failure_count <= 10:
                    failure_count += 1
                    logger.warning(f"Error reading frame in background thread for {self}: {e}")
                else:
                    raise RuntimeError(f"{self} exceeded maximum consecutive read failures.") from e

    def _start_read_thread(self) -> None:
        """Starts or restarts the background read thread if it's not running."""
        self._stop_read_thread()

        self.stop_event = Event()
        self.thread = Thread(target=self._read_loop, args=(), name=f"{self}_read_loop")
        self.thread.daemon = True
        self.thread.start()
        time.sleep(0.1)

    def _stop_read_thread(self) -> None:
        """Signals the background read thread to stop and waits for it to join."""
        if self.stop_event is not None:
            self.stop_event.set()

        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        self.thread = None
        self.stop_event = None

        with self.frame_lock:
            self.latest_frame = None
            self.latest_timestamp = None
            self.new_frame_event.clear()

    @check_if_not_connected
    def read(self, color_mode: ColorMode | None = None) -> NDArray[Any]:
        """
        Reads a single frame synchronously from the tactile sensor.

        This is a blocking call. It waits for the next available processed frame.

        Returns:
            np.ndarray: The captured tactile RGB frame as a NumPy array.
        """
        start_time = time.perf_counter()

        if color_mode is not None:
            logger.warning(
                f"{self} read() color_mode parameter is deprecated and will be removed in future versions."
            )

        if self.thread is None or not self.thread.is_alive():
            raise RuntimeError(f"{self} read thread is not running.")

        self.new_frame_event.clear()
        frame = self.async_read(timeout_ms=10000)

        read_duration_ms = (time.perf_counter() - start_time) * 1e3
        logger.debug(f"{self} read took: {read_duration_ms:.1f}ms")

        return frame

    @check_if_not_connected
    def async_read(self, timeout_ms: float = 200) -> NDArray[Any]:
        """
        Reads the latest available frame asynchronously.

        This method retrieves the most recent frame captured by the background
        read thread.

        Args:
            timeout_ms (float): Maximum time in milliseconds to wait for a frame.

        Returns:
            np.ndarray: The latest captured tactile RGB frame.
        """
        if self.thread is None or not self.thread.is_alive():
            raise RuntimeError(f"{self} read thread is not running.")

        if not self.new_frame_event.wait(timeout=timeout_ms / 1000.0):
            raise TimeoutError(
                f"Timed out waiting for frame from camera {self} after {timeout_ms} ms. "
                f"Read thread alive: {self.thread.is_alive()}."
            )

        with self.frame_lock:
            frame = self.latest_frame
            self.new_frame_event.clear()

        if frame is None:
            raise RuntimeError(f"Internal error: Event set but no frame available for {self}.")

        return frame

    @check_if_not_connected
    def read_latest(self, max_age_ms: int = 500) -> NDArray[Any]:
        """
        Return the most recent frame captured immediately (Peeking).

        This method is non-blocking and returns whatever is currently in the
        memory buffer.

        Returns:
            NDArray[Any]: The frame image (numpy array).
        """
        if self.thread is None or not self.thread.is_alive():
            raise RuntimeError(f"{self} read thread is not running.")

        with self.frame_lock:
            frame = self.latest_frame
            timestamp = self.latest_timestamp

        if frame is None or timestamp is None:
            raise RuntimeError(f"{self} has not captured any frames yet.")

        age_ms = (time.perf_counter() - timestamp) * 1e3
        if age_ms > max_age_ms:
            raise TimeoutError(
                f"{self} latest frame is too old: {age_ms:.1f} ms (max allowed: {max_age_ms} ms)."
            )

        return frame

    def disconnect(self) -> None:
        """
        Disconnects from the tactile sensor and cleans up resources.
        """
        if not self.is_connected and self.thread is None:
            raise DeviceNotConnectedError(f"{self} not connected.")

        if self.thread is not None:
            self._stop_read_thread()

        if self.touch_sensor is not None:
            self.touch_sensor.release()
            self.touch_sensor = None

        with self.frame_lock:
            self.latest_frame = None
            self.latest_timestamp = None
            self.new_frame_event.clear()

        logger.info(f"{self} disconnected.")

    @staticmethod
    def find_cameras() -> list[dict[str, Any]]:
        """
        Detects available tactile sensors connected to the system.

        On Linux, it scans '/dev/video*' paths to find potential tactile sensors.
        Note: This is a best-effort detection and may require manual configuration.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing information
            about detected potential tactile sensors.
        """
        found_cameras_info = []

        # On Linux, scan video devices
        if platform.system() == "Linux":
            from pathlib import Path
            possible_paths = sorted(Path("/dev").glob("video*"), key=lambda p: p.name)
            
            for path in possible_paths:
                camera = cv2.VideoCapture(str(path))
                if camera.isOpened():
                    default_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                    default_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    default_fps = camera.get(cv2.CAP_PROP_FPS)

                    camera_info = {
                        "name": f"Potential Tactile Sensor @ {path}",
                        "type": "Tactile",
                        "id": str(path),
                        "default_stream_profile": {
                            "width": default_width,
                            "height": default_height,
                            "fps": default_fps,
                        },
                        "note": "Verify this is a tactile sensor before using.",
                    }

                    found_cameras_info.append(camera_info)
                    camera.release()

        return found_cameras_info
