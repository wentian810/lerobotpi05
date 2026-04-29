import typing as _t

from api.touch_sensor import TouchSensor


class MultiSensorManager:
    """持有多路 TouchSensor，并提供对称的辅助方法。"""

    def __init__(
        self,
        usb_ids: _t.Sequence[_t.Any],
        *,
        finger_ids: _t.Optional[_t.Sequence[str]] = None,
        caps: _t.Optional[_t.Sequence[_t.Any]] = None,
        param_apply_fn: _t.Optional[_t.Callable[[TouchSensor], None]] = None,
    ) -> None:
        """
        参数:
            usb_ids: 每路摄像头的 USB 标识列表。
            finger_ids: 可选的传感器标签（用于日志/调试）；提供时长度需与 usb_ids 一致。
            caps: 可选的已创建 VideoCapture 列表；提供时长度需与 usb_ids 一致。
            param_apply_fn: 可选回调，在初始化后对每个传感器应用参数（如 ParameterManager().apply_to_sensor）。
        """
        if finger_ids is not None and len(finger_ids) != len(usb_ids):
            raise ValueError("finger_ids length must match usb_ids length")
        if caps is not None and len(caps) != len(usb_ids):
            raise ValueError("caps length must match usb_ids length")

        self.sensors: list[TouchSensor] = []
        for idx, usb_id in enumerate(usb_ids):
            finger_id = finger_ids[idx] if finger_ids is not None else f"cam{idx+1}"
            cap = caps[idx] if caps is not None else None
            sensor = TouchSensor(usb_id=usb_id, finger_id=finger_id, cap=cap)
            if param_apply_fn is not None:
                param_apply_fn(sensor)
            self.sensors.append(sensor)

    def count(self) -> int:
        return len(self.sensors)

    def get_sensor(self, index: int) -> TouchSensor:
        try:
            return self.sensors[index]
        except IndexError as exc:  # 简短保护
            raise ValueError(f"index out of range: {index}") from exc

    def read_frame(self, index: int):
        return self.get_sensor(index).preprocessed_frame

    def compute_pressure_and_flow(self, index: int, frame=None):
        sensor = self.get_sensor(index)
        if frame is None:
            frame = sensor.preprocessed_frame
        pressure_matrix = sensor.get_pressure_matrix(frame)
        flow_x, flow_y = sensor.get_flow_matrix(frame)
        return frame, pressure_matrix, flow_x, flow_y

    def calibrate_all(self, frames: int = 5) -> None:
        for sensor in self.sensors:
            sensor.calibrate_base_matrix(frames)

    def release_all(self) -> None:
        for sensor in self.sensors:
            sensor.release()
