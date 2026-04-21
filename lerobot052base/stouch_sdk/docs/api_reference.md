<a id="touchsensor__init__"></a>
# TouchSensor.__init__

初始化触摸传感器实例。

**函数签名：**
```python
def __init__(self, usb_id: int, finger_id: Union[int, str], cap: Optional[cv2.VideoCapture] = None)
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `usb_id` | `int` | USB 摄像头设备 ID（通常为 0, 1, 2...） |
| `finger_id` | `int` 或 `str` | 手指标识符，用于多传感器场景 |
| `cap` | `Optional[cv2.VideoCapture]` | 可选的外部视频捕获对象，支持视频文件 |

**说明：**
- 如果 `cap` 为 `None`，将自动初始化 USB 摄像头
- 初始化过程包括：相机初始化、ROI 自动检测、自动校准
- 支持跨平台（Windows/Linux/macOS）

**示例：**
```python
# 使用 USB 摄像头
sensor = TouchSensor(usb_id=0, finger_id=1)

# 使用视频文件
import cv2
cap = cv2.VideoCapture("video.mp4")
sensor = TouchSensor(usb_id=0, finger_id="test", cap=cap)
```

---


<a id="touchsensorload_config"></a>
# TouchSensor.load_config

从 YAML 配置文件加载参数到实例属性（仅填充当前为 None 的字段）。

**函数签名：**
```python
def load_config(self, config_path: Optional[str] = None) -> None
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `config_path` | `Optional[str]` | 可选配置文件路径，省略则默认读取 `api/params_config.yaml` |

**说明：**
- 仅覆盖属性当前为 None 的字段，用户显式设置的值不会被覆盖
- 支持的键包含光流参数 `params.*`、相机参数 `camera_params.*` 以及 ROI/网格/显示/阈值等标量项

---


<a id="touchsensorcamera_init"></a>
# TouchSensor.camera_init

初始化相机并完成自动配置。

**函数签名：**
```python
def camera_init(self, camera_params: Optional[dict] = None)
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `camera_params` | `Optional[dict]` | 可选的相机参数配置字典，排除 `frame_width` 和 `frame_height` |

**说明：**
- 自动选择平台对应的摄像头后端（Windows: DirectShow, Linux: V4L2, macOS: AVFoundation）
- 自动检测 ROI 区域
- 自动进行传感器校准（采集 5 帧基准数据）
- 设置默认分辨率为 640×480

**示例：**
```python
# 使用默认参数初始化
sensor.camera_init()

# 自定义相机参数
camera_params = {
    'exposure': -6.0,
    'brightness': 10.0,
    'contrast': 60.0
}
sensor.camera_init(camera_params=camera_params)
```

---


<a id="touchsensorsetroi"></a>
# TouchSensor.setRoi

设置感兴趣区域（ROI）。

**函数签名：**
```python
def setRoi(self, x_left: int, x_right: int, y_top: int, y_bottom: int)
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `x_left` | `int` | ROI 左边界（像素） |
| `x_right` | `int` | ROI 右边界（像素） |
| `y_top` | `int` | ROI 上边界（像素） |
| `y_bottom` | `int` | ROI 下边界（像素） |

**示例：**
```python
sensor.setRoi(x_left=100, x_right=540, y_top=50, y_bottom=430)
```

---


<a id="touchsensorsetcellsize"></a>
# TouchSensor.setCellSize

设置网格单元大小。

**函数签名：**
```python
def setCellSize(self, cell_size: int)
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `cell_size` | `int` | 网格单元大小（像素），影响压力矩阵分辨率 |

**说明：**
- 较小的 `cell_size` 提供更高的空间分辨率，但计算量更大
- 默认值为 10 像素
- 设置后会自动更新 `grid_rows` 和 `grid_cols`

**示例：**
```python
sensor.setCellSize(15)  # 设置网格单元为 15×15 像素
```

---


<a id="touchsensorsetscalefactor"></a>
# TouchSensor.setScaleFactor

设置图像缩放因子（用于光流计算加速）。

**函数签名：**
```python
def setScaleFactor(self, scale_factor: float)
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `scale_factor` | `float` | 缩放因子，范围 (0, 1] |

**说明：**
- 较小的值可以加速光流计算，但会降低精度
- 默认值为 0.5
- 建议范围：0.3 - 0.7

**示例：**
```python
sensor.setScaleFactor(0.3)  # 使用 30% 分辨率进行光流计算
```

---


<a id="touchsensorapply_camera_params"></a>
# TouchSensor.apply_camera_params

应用相机参数到底层硬件。

**函数签名：**
```python
def apply_camera_params(self, camera_params: dict) -> bool
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `camera_params` | `dict` | 相机参数字典，支持的键：<br>- `hue`: 色调<br>- `exposure`: 曝光<br>- `contrast`: 对比度<br>- `brightness`: 亮度<br>- `saturation`: 饱和度<br>- `sharpness`: 锐度<br>- `gamma`: 伽马值<br>- `auto_exposure`: 自动曝光<br>- `auto_wb`: 自动白平衡<br>- `white_balance_blue`: 白平衡蓝色 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `bool` | 成功返回 `True`，失败返回 `False` |

**示例：**
```python
camera_params = {
    'exposure': -6.0,
    'brightness': 10.0,
    'contrast': 60.0,
    'saturation': 70.0
}
sensor.apply_camera_params(camera_params)
```

---


<a id="touchsensorpreprocess_frame"></a>
# TouchSensor.preprocess_frame

读取并预处理一帧图像。

**函数签名：**
```python
def preprocess_frame(self) -> np.ndarray
```

**返回值：**

| 类型 | 说明 |
|------|------|
| `np.ndarray[shape=(H, W, 3), dtype=np.uint8]` | 预处理后的 BGR 图像（已裁剪 ROI 并水平翻转） |

**说明：**
- 从摄像头读取一帧
- 裁剪到 ROI 区域
- 水平翻转（镜像）

**示例：**
```python
frame = sensor.preprocess_frame()
cv2.imshow('Frame', frame)
```

---


<a id="touchsensorcalibrate_base_matrix"></a>
# TouchSensor.calibrate_base_matrix

校准压力检测的基准矩阵。

**函数签名：**
```python
def calibrate_base_matrix(self, calibration_frames: int = 5) -> tuple
```

**参数：**

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `calibration_frames` | `int` | `5` | 用于校准的帧数 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(base_matrix, frame)`<br>- `base_matrix`: 基准色调矩阵<br>- `frame`: 最后一帧图像 |

**说明：**
- 校准前确保传感器表面无压力
- 采集多帧图像的平均色调作为基准
- 初始化时自动调用

**示例：**
```python
# 重新校准（环境光线变化时）
base_matrix, frame = sensor.calibrate_base_matrix(calibration_frames=10)
```

---


<a id="touchsensorget_pressure_matrix"></a>
# TouchSensor.get_pressure_matrix

获取压力分布矩阵。

**函数签名：**
```python
def get_pressure_matrix(self, frame: np.ndarray) -> np.ndarray
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `np.ndarray` | 预处理后的图像帧（来自 `preprocess_frame()`） |

**返回值：**

| 类型 | 说明 |
|------|------|
| `np.ndarray[shape=(grid_rows, grid_cols), dtype=np.float32]` | 压力矩阵，每个元素表示对应网格单元的压力值 |

**说明：**
- 基于 HSV 色相变化计算压力
- 使用向量化操作，性能优化
- 自动进行噪声过滤（< 1 的值设为 0）

**示例：**
```python
frame = sensor.preprocess_frame()
pressure = sensor.get_pressure_matrix(frame)
print(f"压力矩阵形状: {pressure.shape}")
print(f"最大压力值: {pressure.max():.2f}")
```

---


<a id="touchsensorget_flow_matrix"></a>
# TouchSensor.get_flow_matrix

计算切向光流场。

**函数签名：**
```python
def get_flow_matrix(self, frame: np.ndarray) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `np.ndarray` | 预处理后的图像帧 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(flow_x, flow_y)`<br>- `flow_x`: X 方向光流分量矩阵<br>- `flow_y`: Y 方向光流分量矩阵 |

**说明：**
- 使用 Farneback 稠密光流算法
- 使用缩放加速（根据 `scale_factor`）
- 与第一帧灰度图进行比较

**示例：**
```python
frame = sensor.preprocess_frame()
flow_x, flow_y = sensor.get_flow_matrix(frame)
print(f"光流矩阵形状: {flow_x.shape}")
```

---


<a id="touchsensorget_total_force"></a>
# TouchSensor.get_total_force

计算总力（3D 力向量）。

**函数签名：**
```python
def get_total_force(
    self,
    frame: Optional[np.ndarray] = None,
    pressure_matrix: Optional[np.ndarray] = None,
    flow_x: Optional[np.ndarray] = None,
    flow_y: Optional[np.ndarray] = None
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `Optional[np.ndarray]` | 可选，输入图像帧 |
| `pressure_matrix` | `Optional[np.ndarray]` | 可选，已计算的压力矩阵 |
| `flow_x` | `Optional[np.ndarray]` | 可选，已计算的 X 方向光流 |
| `flow_y` | `Optional[np.ndarray]` | 可选，已计算的 Y 方向光流 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(fx_total, fy_total, fz_total)`<br>- `fx_total` (float): X 方向总力，单位 N<br>- `fy_total` (float): Y 方向总力，单位 N<br>- `fz_total` (float): Z 方向总力（压力），单位 N |

**说明：**
- 支持两种调用方式：
  1. 传入 `frame`，内部计算压力和光流
  2. 传入已计算的 `pressure_matrix`, `flow_x`, `flow_y`（性能优化）
- 使用偏差补偿算法减少噪声
- 自动触发校准（当检测到偏差时）
- 内部始终调用 `_calculate_total_force_from_data` 完成力的汇总和缩放，本方法只是负责准备数据和选择调用路径

**示例：**
```python
# 方式 1：传入帧
frame = sensor.preprocess_frame()
fx, fy, fz = sensor.get_total_force(frame=frame)

# 方式 2：使用已计算的数据（性能优化）
pressure = sensor.get_pressure_matrix(frame)
flow_x, flow_y = sensor.get_flow_matrix(frame)
fx, fy, fz = sensor.get_total_force(
    pressure_matrix=pressure,
    flow_x=flow_x,
    flow_y=flow_y
)
```

---


<a id="touchsensor_calculate_total_force_from_data"></a>
# TouchSensor._calculate_total_force_from_data

内部方法：基于已计算的数据求和得到三轴总力。

**函数签名：**
```python
def _calculate_total_force_from_data(
    self,
    pressure_matrix: np.ndarray,
    flow_x: np.ndarray,
    flow_y: np.ndarray
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `pressure_matrix` | `np.ndarray` | 压力矩阵 |
| `flow_x` | `np.ndarray` | X 方向光流 |
| `flow_y` | `np.ndarray` | Y 方向光流 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(fx_total, fy_total, fz_total)`

**说明：**
- 对光流按步长采样并进行偏差补偿，再乘以 `fx_scale`/`fy_scale`
- 对压力矩阵求和并乘以 `fz_scale`
- 仅做纯计算，不读取帧；由 `get_total_force` 负责获取/缓存 `pressure_matrix` 与 `flow` 后调用，本方法通常不直接对外使用

---


<a id="touchsensorget_force_angle2d"></a>
# TouchSensor.get_force_angle2D

计算 2D 力的大小和角度。

**函数签名：**
```python
def get_force_angle2D(
    self,
    frame: Optional[np.ndarray] = None,
    flow_x: Optional[np.ndarray] = None,
    flow_y: Optional[np.ndarray] = None
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `Optional[np.ndarray]` | 可选，输入图像帧 |
| `flow_x` | `Optional[np.ndarray]` | 可选，已计算的 X 方向光流 |
| `flow_y` | `Optional[np.ndarray]` | 可选，已计算的 Y 方向光流 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(magnitude, angle_deg)`<br>- `magnitude` (float): 力的大小<br>- `angle_deg` (float): 角度（度），范围 [-180, 180]，相对于 +X 轴 |

**说明：**
- 角度定义：`atan2(fy_total, fx_total)`
- 角度范围：-180° 到 +180°

**示例：**
```python
frame = sensor.preprocess_frame()
magnitude, angle = sensor.get_force_angle2D(frame=frame)
print(f"力大小: {magnitude:.2f} N, 角度: {angle:.2f}°")
```

---


<a id="touchsensorget_force_angle3d"></a>
# TouchSensor.get_force_angle3D

计算 3D 力的大小、方位角和俯仰角。

**函数签名：**
```python
def get_force_angle3D(
    self,
    frame: Optional[np.ndarray] = None,
    fx_total: Optional[float] = None,
    fy_total: Optional[float] = None,
    fz_total: Optional[float] = None
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `Optional[np.ndarray]` | 可选，输入图像帧 |
| `fx_total` | `Optional[float]` | 可选，X 方向总力 |
| `fy_total` | `Optional[float]` | 可选，Y 方向总力 |
| `fz_total` | `Optional[float]` | 可选，Z 方向总力 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(magnitude, azimuth_deg, elevation_deg)`<br>- `magnitude` (float): 3D 力的大小<br>- `azimuth_deg` (float): 方位角（度），在 XY 平面内与 +X 轴的夹角<br>- `elevation_deg` (float): 俯仰角（度），与 XY 平面的夹角 |

**说明：**
- 方位角（azimuth）：`atan2(fy_total, fx_total)`
- 俯仰角（elevation）：`atan2(fz_total, sqrt(fx_total² + fy_total²))`

**示例：**
```python
frame = sensor.preprocess_frame()
magnitude, azimuth, elevation = sensor.get_force_angle3D(frame=frame)
print(f"力大小: {magnitude:.2f} N")
print(f"方位角: {azimuth:.2f}°, 俯仰角: {elevation:.2f}°")
```

---


<a id="touchsensorget_cell_area"></a>
# TouchSensor.get_cell_area

获取有效压力单元格数量（超过阈值的单元格）。

**函数签名：**
```python
def get_cell_area(
    self,
    frame: Optional[np.ndarray] = None,
    pressure_matrix: Optional[np.ndarray] = None
) -> int
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `Optional[np.ndarray]` | 可选，输入图像帧 |
| `pressure_matrix` | `Optional[np.ndarray]` | 可选，已计算的压力矩阵 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `int` | 超过 `pressure_threshold`（默认 5）的单元格数量 |

**示例：**
```python
frame = sensor.preprocess_frame()
area = sensor.get_cell_area(frame=frame)
print(f"有效接触面积: {area} 个单元格")
```

---


<a id="touchsensorget_center_of_gravity"></a>
# TouchSensor.get_center_of_gravity

获取压力分布的质心坐标。

**函数签名：**
```python
def get_center_of_gravity(
    self,
    frame: Optional[np.ndarray] = None,
    pressure_matrix: Optional[np.ndarray] = None
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `Optional[np.ndarray]` | 可选，输入图像帧 |
| `pressure_matrix` | `Optional[np.ndarray]` | 可选，已计算的压力矩阵 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(cx, cy)` 质心坐标（网格单位），如果无压力则返回 `(-1, -1)` |

**示例：**
```python
frame = sensor.preprocess_frame()
cx, cy = sensor.get_center_of_gravity(frame=frame)
if cx != -1:
    print(f"压力质心: ({cx:.2f}, {cy:.2f})")
```

---


<a id="touchsensorget_maximum_force"></a>
# TouchSensor.get_maximum_force

获取最大压力值及其位置。

**函数签名：**
```python
def get_maximum_force(
    self,
    frame: Optional[np.ndarray] = None,
    pressure_matrix: Optional[np.ndarray] = None
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `Optional[np.ndarray]` | 可选，输入图像帧 |
| `pressure_matrix` | `Optional[np.ndarray]` | 可选，已计算的压力矩阵 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(max_value, max_row, max_col)`<br>- `max_value` (float): 最大压力值<br>- `max_row` (int): 最大压力所在行（网格坐标）<br>- `max_col` (int): 最大压力所在列（网格坐标） |

**示例：**
```python
frame = sensor.preprocess_frame()
max_value, row, col = sensor.get_maximum_force(frame=frame)
print(f"最大压力: {max_value:.2f} 位于 ({row}, {col})")
```

---


<a id="touchsensorget_pressure_histogram"></a>
# TouchSensor.get_pressure_histogram

将压力矩阵转换为固定长度的直方图统计数组。

**函数签名：**
```python
def get_pressure_histogram(self, pressure_matrix: np.ndarray, bins: int = 256) -> np.ndarray
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `pressure_matrix` | `np.ndarray` | 来自 `get_pressure_matrix` 的压力矩阵 |
| `bins` | `int` | 直方图区间数量，默认 256 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `np.ndarray` | 长度为 `bins` 的频次统计数组 |

**示例：**
```python
pressure = sensor.get_pressure_matrix(sensor.preprocess_frame())
hist = sensor.get_pressure_histogram(pressure, bins=128)
print(hist[:10])
```

---


<a id="touchsensorvisualize_pressure"></a>
# TouchSensor.visualize_pressure

可视化压力分布矩阵。

**函数签名：**
```python
def visualize_pressure(self) -> np.ndarray
```

**返回值：**

| 类型 | 说明 |
|------|------|
| `np.ndarray[shape=(H, W, 3), dtype=np.uint8]` | BGR 图像，黑底上显示压力数值 |

**说明：**
- 自动调用 `preprocess_frame()` 和 `get_pressure_matrix()`
- 在每个网格单元中心显示压力值（整数）

**示例：**
```python
vis_img = sensor.visualize_pressure()
cv2.imshow('Pressure', vis_img)
cv2.waitKey(0)
```

---


<a id="touchsensorget_touch_status"></a>
# TouchSensor.get_touch_status

基于力和方差阈值的触摸状态机输出当前状态及力。

**函数签名：**
```python
def get_touch_status(
    self,
    frame: Optional[np.ndarray] = None,
    contact_threshold: Optional[float] = None,
    release_threshold: Optional[float] = None,
    slide_threshold: Optional[float] = None
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `frame` | `Optional[np.ndarray]` | 可选输入帧，缺省则内部读取 |
| `contact_threshold` | `Optional[float]` | 接触判定阈值（可覆盖配置值） |
| `release_threshold` | `Optional[float]` | 释放判定阈值 |
| `slide_threshold` | `Optional[float]` | 滑动判定阈值（平面力大小） |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(status, fx_total, fy_total, fz_total, ft)`，其中 `status` 取值 `IDLE/CONTACT/SLIDING/RELEASED` |

**说明：**
- 内部维护 `fz_history` 估计标准差，并用 `slide_force_std_threshold` 判断滑动稳定性
- 若提供阈值参数，会更新实例的阈值配置

---


<a id="touchsensorget_contact_shape"></a>
# TouchSensor.get_contact_shape

根据压力矩阵判定接触形状并返回二值掩膜与最小外接旋转矩形。

**函数签名：**
```python
def get_contact_shape(
    self,
    pressure_matrix: Optional[np.ndarray] = None,
    threshold: Optional[float] = None,
    min_area: int = 15,
    ratio_threshold: float = 2.5
) -> tuple
```

**参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `pressure_matrix` | `Optional[np.ndarray]` | 可选压力矩阵，缺省则内部获取 |
| `threshold` | `Optional[float]` | 二值化阈值，缺省使用 `pressure_threshold` |
| `min_area` | `int` | 最小有效轮廓面积，默认 15 |
| `ratio_threshold` | `float` | 长宽比阈值，大于该值判定为 EDGE，否则 FACE |

**返回值：**

| 类型 | 说明 |
|------|------|
| `tuple` | `(mask, box, label)`，若无有效接触可能返回 `None` |

**说明：**
- 通过阈值化得到掩膜并寻找最大轮廓，过滤小面积噪声
- 使用 `cv2.minAreaRect` 计算旋转矩形，根据长宽比给出接触形状标签

---


<a id="touchsensorget_tactile_rgb"></a>
# TouchSensor.get_tactile_rgb

根据压力矩阵和光流矩阵生成触觉RGB图像。

**函数签名：**
```python
def get_tactile_rgb(
    self,
    pressure_matrix: Optional[np.ndarray] = None,
    flow_matrix: Optional[np.ndarray] = None,
    pressure_max: float = 50,
    flow_max: float = 10,
    flow_min: float = -10
) -> np.ndarray
```

**参数：**

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `pressure_matrix` | `Optional[np.ndarray]` | `None` | 可选，压力矩阵，缺省则内部获取 |
| `flow_matrix` | `Optional[np.ndarray]` | `None` | 可选，光流矩阵 (shape: [H, W, 2])，缺省则内部获取 |
| `pressure_max` | `float` | `50` | 压力矩阵最大值，用于缩放 |
| `flow_max` | `float` | `10` | 光流矩阵最大值，用于缩放 |
| `flow_min` | `float` | `-10` | 光流矩阵最小值，用于缩放 |

**返回值：**

| 类型 | 说明 |
|------|------|
| `np.ndarray[shape=(H, W, 3), dtype=np.uint8]` | RGB图像，通道含义：<br>- R通道：压力值（0-255）<br>- G通道：X方向光流（0-255）<br>- B通道：Y方向光流（0-255） |

**说明：**
- 压力矩阵缩放公式：`clip(pressure / pressure_max * 255, 0, 255)`
- 光流矩阵X分量缩放公式：`clip((flow_x - flow_min) / (flow_max - flow_min) * 255, 0, 255)`
- 光流矩阵Y分量缩放公式同上
- 使用固定参数范围进行缩放，而非动态min-max缩放
- 超出范围的值会被截断到[0, 255]

**示例：**
```python
# 方式1：自动获取压力和光流
rgb_image = sensor.get_tactile_rgb()

# 方式2：使用已计算的矩阵（性能优化）
frame = sensor.preprocess_frame()
pressure = sensor.get_pressure_matrix(frame)
flow_x, flow_y = sensor.get_flow_matrix(frame)
flow = np.stack([flow_x, flow_y], axis=-1)
rgb_image = sensor.get_tactile_rgb(
    pressure_matrix=pressure,
    flow_matrix=flow,
    pressure_max=50,
    flow_max=10,
    flow_min=-10
)

# 显示结果
cv2.imshow('Tactile RGB', rgb_image)
cv2.waitKey(0)
```

---


<a id="touchsensorrelease"></a>
# TouchSensor.release()

释放相机资源。

**函数签名：**
```python
def release(self)
```

**说明：**
- 释放 `cv2.VideoCapture` 对象
- 程序结束前必须调用

**示例：**
```python
sensor.release()
```

---
