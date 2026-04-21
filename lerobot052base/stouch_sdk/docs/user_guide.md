# 环境部署
## 环境要求

- **Python**: 3.9 或更高版本
- **操作系统**: Windows / Linux / macOS
- **硬件**: USB摄像头（用于触觉传感）

## 安装步骤

### 1. 进入项目工作文件

```bash
cd /path/to/your/workspace
cd SDK
```

### 2. 安装依赖

```bash
# 使用pip安装所有依赖
pip install -r requirements.txt
```

## 依赖列表
```
opencv-python-headless        # 计算机视觉和光流算法(headless版本防止与PyQt5产生冲突)
numpy==2.0.2                  # 数值计算
pyqtgraph==0.13.7             # 科学绘图和3D可视化
PyQt5==5.15.11                # GUI框架
matplotlib==3.9.4             # 数据绘图
numpy-stl==3.2.0              # STL 3D模型加载
PyOpenGL==3.1.10              # OpenGL 3D渲染
PyOpenGL-accelerate==3.1.10   # OpenGL加速
pillow==11.3.0                # 图像处理
pyyaml==6.0.2                 # 配置文件加载
```

---


# GUI使用指南

## 快速启动
- 确认依赖已安装
- 进入项目工作目录
- 运行以下指令开启GUI
    ```
    python GUI/demo_gui.py
    ```
- 预览后选择正确的 USB 端口进入主界面
- 首次进入建议点击 Calibrate（或按 `C` 键）完成基准校准

## 界面布局与功能
- 上方左侧：压力图（灰度/伪彩热力图）
- 上方右侧：切向力光流箭头视图
- 下方：3D压力函数图（Fx/Fy/Fz）

## 参数配置
- 点击“参数配置”按钮进入配置页面
- 保存：立即应用到传感器但不写入配置文件
- 保存并应用：立即应用到传感器同时写入配置文件

## 常见操作
- 重新校准：设备移动或环境变化后点击 `Calibrate`（或按 `C` 键）完成基准校准
- 聚焦区域：调整 ROI 以覆盖关注的触觉区域
- 噪声抑制：适当提高压力阈值或平滑参数
- 退出GUI：点击 `Quit`（或按 `Q` 键）完成退出

---


# 示例使用指南

默认使用 usb_id，阈值或 ROI/网格参数通过配置文件 api/params_config.yaml 进行调整，以匹配实际设备与场景。Qt 可视化示例需桌面环境。

## demo_2Ddirection
- 示例功能：实时打印二维力模长与方向
- 运行指令：`python samples/demo_2Ddirection.py`

## demo_3Ddirection
- 示例功能：实时打印三维力模长、方位角、俯仰角
- 运行指令：`python samples/demo_3Ddirection.py`

## demo_3Dforce_cli
- 示例功能：实时打印 Fx/Fy/Fz 总力
- 运行指令：`python samples/demo_3Dforce_cli.py`

## demo_cell_area
- 示例功能：计算接触压力区域面积（网格 cell 数）
- 运行指令：`python samples/demo_cell_area.py`

## demo_center_of_gravity
- 示例功能：输出接触压力的质心坐标
- 运行指令：`python samples/demo_center_of_gravity.py`

## demo_contact_shape
- 示例功能：接触/滑动状态下判断形态（棱/面）
- 运行指令：`python samples/demo_contact_shape.py`

## demo_edge_angle
- 示例功能：估计接触棱与传感器 y 轴夹角（示例函数未封装进 API）
- 运行指令：`python samples/demo_edge_angle.py`

## demo_flow_Qtv2
- 示例功能：Qt 窗口实时显示切向光流箭头场
- 运行指令：`python samples/demo_flow_Qtv2.py`

## demo_pressure_Qtv2
- 示例功能：Qt 窗口显示 HSV 分量示例（压力可视化思路）
- 运行指令：`python samples/demo_pressure_Qtv2.py`

## demo_max_force_print
- 示例功能：打印压力矩阵的最大值及所在网格坐标
- 运行指令：`python samples/demo_max_force_print.py`

## demo_port_scan_print
- 示例功能：扫描可用 USB 摄像头端口（示例函数未封装进 API）
- 运行指令：`python samples/demo_port_scan_print.py`

## demo_status_detect
- 示例功能：基于总力阈值打印触摸状态（IDLE/CONTACT/SLIDING/RELEASED）
- 运行指令：`python samples/demo_status_detect.py`

---


# GUI参数配置

GUI 支持在运行时调整超参数，并可保存到配置文件 `api/params_config.yaml`。该文件同时被 API 层读取，因此 **GUI/CLI 示例共用同一份配置**。

## 配置文件位置与生效方式

- 配置文件路径：`api/params_config.yaml`
- GUI 中“应用/保存并应用”的区别：
    - **应用**：立即把参数应用到当前传感器实例，不写入 YAML 配置文件
    - **保存并应用**：立即应用，同时写回 `api/params_config.yaml`

> 注意：GUI 启动时会弹出端口选择器。此时实际打开的摄像头端口以 GUI 选择为准，参数配置文件中的 `usb_id` 主要用于默认/脚本场景。

## 推荐调参顺序

1. **相机参数**：先使亮度/曝光/白平衡稳定，避免3D压力函数图和光流可视化图漂移。
2. **ROI**：把 ROI 框选到期望识别的区域，减少背景干扰。
3. **网格与显示**：`cell_size`、`pressure_scale`、显示模式等。
4. **光流参数**：在画面与压力稳定后，再调 Farneback 参数抑制抖动/提升跟随性能。
5. **触摸状态判断阈值**：最后根据实际载荷标定 `contact/release/slide` 等阈值。（GUI中不可调整，需要在 YAML 配置文件中手动调整）

## 基本布局参数

### ROI 区域（640×480 分辨率坐标）

- `roi_x1`：ROI 左侧边界
- `roi_x2`：ROI 右侧边界
- `roi_y1`：ROI 上侧边界
- `roi_y2`：ROI 下侧边界
    - **含义**：从摄像头 640×480 图像中裁剪用于计算的矩形区域。
    - **影响**：ROI 越小，计算越快、抗干扰更强，但有效触觉区域更小。
    - **调节建议**：
        - 优先把 ROI 覆盖“触觉膜/有效接触区域”，尽量避开边缘反光、背景。
        - ROI 变更后建议重新校准（Calibrate / 按 C）。

### 网格与采样

- `cell_size`
    - **含义**：将 ROI 划分为压力网格的单元像素大小。
    - **调节方式**：
        - 想要更细的空间分辨率（更精细的压力形状/质心）：减小 `cell_size`（计算量会上升）。
        - 想要更高帧率：增大 `cell_size`。
        - 实际压力网格大小的计算方式：
            `grid_cols = ROI宽度 / cell_size`，`grid_rows = ROI高度 / cell_size`。

- `optical_flow_step`
    - **含义**：光流箭头（切向力场）采样步长（像素）。
    - **调节方式**：
        - 箭头太密 / CPU 占用高：增大 `optical_flow_step`。
        - 想查看更细小的局部方向变化：减小 `optical_flow_step`。

### 压力显示与缩放

- `pressure_scale`
    - **含义**：压力数值放大系数（用于压力图可视化的强度缩放）。
    - **调节方式**：
        - 显示偏暗、细节不明显：适当增大。
        - 容易“全白/饱和”(大片 255)：减小。

- `pressure_form_switch`
    - **含义**：压力图显示模式开关（`0 = 灰度图显示`，`1 = 热力图显示`）。
    - **调节方式**：想更直观观察强弱分布可切到彩色；想看数值线性变化可用灰度。可在GUI中点击切换按钮进行显示模式的切换。

- `scale_factor`
    - **含义**：显示缩放因子，影响 GUI 预览显示的缩放比例。
    - **调节方式**：
        - 机器性能较弱或只需要粗看：降低。
        - 需要更清晰的预览细节：提高（同时会产生较高的算力消耗）。

- `display_angle`
    - **含义**：显示旋转角度（°）。
    - **调节方式**：如果画面方向与实际传感器方向不一致，可按需要旋转到方便观察的角度。

### 触摸状态判断阈值

- `contact_threshold`
    - **含义**：判断从“空闲`IDLE`”状态进入“接触`CONTACT`”状态的阈值。
    - **调节方式**：
        - 仅可在 YAML 配置文件中手动调整，文件路径：`./api/params_config.yaml`。
        - 误触发（即在没有施加压力的情况下判定为接触`CONTACT`状态）：提高。
        - 触发不灵敏（即在施加压力的情况下判定为空闲`IDLE`状态）：降低。

- `release_threshold`
    - **含义**：判断从“接触`CONTACT`/滑动`SLIDE`”状态回到“释放`RELEASE`/空闲`IDLE`”状态的阈值。
    - **调节方式**：通常`release_threshold` **<** `contact_threshold`，形成滞回，避免临界点来回抖动。

- `slide_threshold`
    - **含义**：滑动`SLIDE`状态判定阈值，通常与切向量/光流幅值相关。
    - **调节方式**：
        - 轻微抖动就被判滑动：提高。
        - 明显滑动却无法被判断：降低。

- `slide_force_std_threshold`
    - **含义**：滑动稳定性阈值（用于区分“稳定滑动”和“噪声/抖动”）。
    - **调节方式**：
        - 噪声导致滑动状态频繁闪烁：提高。
        - 滑动很稳定但判定过于保守：降低。

## 光流参数

以下参数对应 OpenCV Farneback 光流计算，主要影响切向力计算稳定性稳定性与光流箭头跟随性。

- `pyr_scale`
    - **含义**：金字塔每层缩放比例。
    - **调节方式**：位移更大/变化更快时可适当降低以增强跨尺度跟随；想更细致则适当提高。

- `levels`
    - **含义**：金字塔层数。
    - **调节方式**：大位移/快速滑动跟不上可增大；性能不足时可减小。

- `winsize`
    - **含义**：搜索窗口大小。
    - **调节方式**：
        - 箭头抖动/噪声多：增大（更平滑，但细节更少、更慢）。
        - 想要更敏感的局部变化：减小（更敏感但更易噪）。

- `iterations`
    - **含义**：每层迭代次数。
    - **调节方式**：精度不够可增加；帧率不足可减少。

- `poly_n`
    - **含义**：多项式拟合邻域大小（常用 5 或 7）。
    - **调节方式**：想更平滑可增大；想保留细节可减小。

- `poly_sigma`
    - **含义**：多项式拟合的高斯标准差。
    - **调节方式**：抖动/噪声大可增大；画面过于糊可减小。

- `flags`
    - **含义**：光流计算的标志位（OpenCV flags）。
    - **注意**：该值属于高级参数，需要在 YAML 配置文件中更改。

## 相机参数

相机参数会影响图像稳定性，从而显著影响“压力映射”和“光流”的稳定性。

> 提示：不同操作系统/摄像头驱动对参数支持程度不同，某些 `cap.set(...)` 可能不会生效。

- `auto_exposure` / `exposure`
    - **含义**：自动曝光开关与曝光值。
    - **调节方式**：优先关闭自动曝光并固定曝光，减少亮度漂移导致的压力漂移。

- `auto_wb` / `white_balance_blue`
    - **含义**：自动白平衡与蓝通道白平衡。
    - **调节方式**：优先关闭自动白平衡并固定白平衡，减少颜色漂移（对基于 Hue 的压力映射非常关键）。

- `brightness`
    - **含义**：亮度，影响画面整体明暗。
    - **调节方式**：画面整体偏暗可提高；若高亮区域接近“发白/过曝”，应降低。

- `contrast`
    - **含义**：对比度，影响明暗层次差异。
    - **调节方式**：细节偏“灰雾”可提高；若边缘反光区域细节丢失明显，可降低。

- `gamma`
    - **含义**：伽马，影响暗部/亮部的非线性映射。
    - **调节方式**：暗部细节太少可适当提高；若整体层次被压平或噪声被放大，可降低。

- `saturation`
    - **含义**：饱和度，影响颜色“浓淡”。
    - **调节方式**：颜色变化不明显、Hue 分量动态范围过小可适当提高；若彩噪明显或颜色失真，可降低。

- `hue`
    - **含义**：色调，影响颜色整体偏移。
    - **调节方式**：仅在颜色整体偏移导致压力映射不稳定时微调；一般保持默认即可。

- `sharpness`
    - **含义**：锐度。
    - **调节方式**：过高会放大噪声影响光流；过低会细节不足。建议从中等值开始微调。


# 性能指标

| *指标* | *数值* |
|------|------|
| 帧率 | 20-30 FPS（取决于硬件） |
| 压力分辨率 | 640 $\times$ 480网格（默认为摄像头分辨率） |
| 光流计算延迟 | < 50ms（720p） |
| 内存占用 | ~200MB |
| CPU占用 | 单核30-50%（i5以上） |

**优化建议**：
- 使用GPU加速的OpenCV版本：`opencv-contrib-python`
- 降低摄像头分辨率
- 减少网格密度

---


# 常见问题 （FAQ）

**Q1: 可以使用视频文件代替摄像头吗？**

A: 可以使用外部 `VideoCapture` 获取视频对象

使用示例：
```python
import cv2
from api import TouchSensor

cap = cv2.VideoCapture("video.mp4")
sensor = TouchSensor(usb_id=0, finger_id="test", cap=cap)
```

**Q2: 如何获取原始的压力数据矩阵？**

A: 使用 `get_pressure_matrix()` 方法

使用示例：
```python
pressure_matrix = sensor.get_pressure_matrix(frame)
print(pressure_matrix)  # numpy数组
```

**Q3: 可以同时连接多个传感器吗？**

A: 可以为每个传感器分配不同的 `usb_id` 和 `finger_id`

使用示例：
```python
sensor1 = TouchSensor(usb_id=0, finger_id="index")
sensor2 = TouchSensor(usb_id=1, finger_id="thumb")
```

**Q4: 参数配置保存在哪里？**

A: 保存在 `api/params_config.yaml`

**Q5: 如何提高检测灵敏度？**

A: 使用如下几种常用方法
1. 减小 `cell_size`（提高空间分辨率）
2. 增大 `scale_factor`（使用更高分辨率图像）
3. 调整光流 `winsize` 参数

---
