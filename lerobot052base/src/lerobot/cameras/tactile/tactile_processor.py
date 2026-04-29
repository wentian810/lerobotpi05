#!/usr/bin/env python

# Copyright 2026 The HuggingFace Inc. team. All rights reserved.
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

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass
class VTLATactileProcessor:
    """Post-processing module for VTLA tactile stream.

    This processor is designed to run after `TouchSensor.get_tactile_rgb()` and keeps
    the exact same tensor contract for downstream code:
    - input:  HxWx3, uint8
    - output: HxWx3, uint8

    Channel convention is preserved:
    - R: pressure
    - G: flow-x
    - B: flow-y
    """

    enabled: bool = False
    ema_alpha: float = 0.35
    detail_gain: float = 1.2
    temporal_diff_gain: float = 0.25
    pressure_boost: float = 1.1
    flow_boost: float = 1.0
    denoise_ksize: int = 3
    material_domain: str = "auto"
    adaptive_norm: bool = False
    norm_momentum: float = 0.05
    norm_eps: float = 1e-3

    def __post_init__(self) -> None:
        self._ema_frame: NDArray[np.float32] | None = None
        self._running_mean = np.array([127.5, 127.5, 127.5], dtype=np.float32)
        self._running_var = np.array([1024.0, 1024.0, 1024.0], dtype=np.float32)

    def reset(self) -> None:
        self._ema_frame = None
        self._running_mean = np.array([127.5, 127.5, 127.5], dtype=np.float32)
        self._running_var = np.array([1024.0, 1024.0, 1024.0], dtype=np.float32)

    def _apply_material_profile(self) -> tuple[float, float, float, float]:
        """Return tuned gains for soft/hard materials with auto fallback."""
        domain = (self.material_domain or "auto").lower()
        if domain == "soft":
            return (max(self.detail_gain, 1.25), max(self.temporal_diff_gain, 0.30), max(self.pressure_boost, 1.12), self.flow_boost)
        if domain == "hard":
            return (min(self.detail_gain, 1.10), min(self.temporal_diff_gain, 0.12), min(self.pressure_boost, 1.02), self.flow_boost)
        return (self.detail_gain, self.temporal_diff_gain, self.pressure_boost, self.flow_boost)

    def _update_running_stats(self, x: NDArray[np.float32]) -> None:
        # x: HxWx3 float32
        mean = x.reshape(-1, 3).mean(axis=0)
        var = x.reshape(-1, 3).var(axis=0)
        m = float(self.norm_momentum)
        self._running_mean = (1.0 - m) * self._running_mean + m * mean
        self._running_var = (1.0 - m) * self._running_var + m * var

    def _adaptive_normalize(self, x: NDArray[np.float32]) -> NDArray[np.float32]:
        """Lightweight per-channel running normalization, mapped back to image range."""
        self._update_running_stats(x)
        std = np.sqrt(self._running_var + float(self.norm_eps))
        x_norm = (x - self._running_mean.reshape(1, 1, 3)) / std.reshape(1, 1, 3)
        return np.clip(x_norm * 32.0 + 127.5, 0, 255)

    def process(self, tactile_rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
        if not self.enabled:
            return tactile_rgb

        if tactile_rgb.ndim != 3 or tactile_rgb.shape[2] != 3:
            raise ValueError(f"Expected HxWx3 tactile image, got shape={tactile_rgb.shape}")
        if tactile_rgb.dtype != np.uint8:
            raise ValueError(f"Expected uint8 tactile image, got dtype={tactile_rgb.dtype}")

        current = tactile_rgb.astype(np.float32)

        if self._ema_frame is None:
            self._ema_frame = current.copy()

        self._ema_frame = self.ema_alpha * current + (1.0 - self.ema_alpha) * self._ema_frame
        low_freq = self._ema_frame
        high_freq = current - low_freq

        detail_gain, temporal_diff_gain, pressure_boost, flow_boost = self._apply_material_profile()

        enhanced = low_freq + detail_gain * high_freq
        enhanced += temporal_diff_gain * (current - low_freq)

        # Channel-wise gains while preserving original channel semantics.
        enhanced[..., 0] *= pressure_boost
        enhanced[..., 1] *= flow_boost
        enhanced[..., 2] *= flow_boost

        if self.adaptive_norm:
            enhanced = self._adaptive_normalize(enhanced)

        if self.denoise_ksize >= 3 and self.denoise_ksize % 2 == 1:
            enhanced = cv2.GaussianBlur(enhanced, (self.denoise_ksize, self.denoise_ksize), 0)

        return np.clip(enhanced, 0, 255).astype(np.uint8)
