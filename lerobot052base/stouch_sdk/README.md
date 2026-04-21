# 视塔科技视触觉传感器 SDK 

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.12-green.svg)](https://opencv.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15-orange.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

##  项目简介

该传感器是一个视触觉传感器，通过USB摄像头实时检测并且可视化**压力分布**和**切向力**。该系统利用**光学流算法**（Optical Flow）和**色相变化分析**（HSV Hue Shift）来计算触摸表面的力学特性，并提供专业的3D可视化界面。

### 核心特性

-  **切向力场检测** - 使用Farneback光流算法计算切向力矢量
-  **力历史曲线绘制** - 实时显示Fx、Fy、Fz三轴力数据
-  **参数动态配置** - GUI内实时调整光流、网格、缩放等参数
-  **跨平台摄像头支持** - 支持Windows/Linux/macOS
-  **USB端口自动扫描** - 智能检测可用摄像头设备

---

##  环境部署

### 环境要求

- **Python**: 3.9 或更高版本
- **操作系统**: Windows / Linux / macOS
- **硬件**: USB摄像头（用于触觉传感）

### 安装步骤

#### 1. 配置环境
#### 
```bash
# 安装系统级依赖
sudo apt-get update
# 安装 OpenGL 和系统库支持
sudo apt-get install python3-venv libgl1 libegl1 libxkbcommon-x11-0
# 创建工作目录
cd SDK
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

**依赖列表**：
```
opencv-python==4.12.0.88      # 计算机视觉和光流算法
numpy==2.0.2                  # 数值计算
PyQt5==5.15.11                # GUI框架
pyqtgraph==0.13.7             # 科学绘图和3D可视化
matplotlib==3.9.4             # 数据绘图
PyOpenGL==3.1.10              # OpenGL 3D渲染
PyOpenGL-accelerate==3.1.10   # OpenGL加速
numpy-stl==3.2.0              # STL 3D模型加载
pillow==11.3.0                # 图像处理
```

#### 2. 连接USB摄像头

确保USB摄像头已连接到电脑，系统可以识别设备。

#### 3. 运行主程序

```bash
# 从项目根目录运行
cd SDK
python GUI/demo_gui.py
```

---

## 使用指南

### 主应用程序 (GUI/demo_gui.py)

#### 启动流程

1. **运行程序**
   ```bash
   python GUI/demo_gui.py
   ```

2. **USB端口选择**
   - 程序启动后会弹出USB端口选择对话框
   - 自动扫描可用的USB摄像头（端口0-9）
   - 显示每个端口的分辨率和帧率信息
   - 可预览摄像头画面
   - 选择目标端口后点击"确定"

3. **传感器初始化**
   - 自动检测有效区域（ROI）
   - 校准基准矩阵（采集30帧静态背景）
   - 初始化3D可视化窗口

4. **实时监测**
   - 3D压力表面：显示实时压力分布
   - 切向力场：显示光流矢量箭头
   - 力历史曲线：显示最近10秒的Fx、Fy、Fz数据


---

### 示例程序

项目提供3个简单的示例程序，用于快速测试和学习API用法。

#### 示例1: 压力矩阵可视化 (demo_pressure.py)

显示实时压力分布矩阵（OpenCV窗口）。

```bash
python samples/demo_pressure_opencv.py
```

#### 示例2: 切向光流可视化 (demo_flow.py)

显示实时光流矢量场（OpenCV窗口）。

```bash
python samples/demo_flow_opencv.py
```

#### 示例3: 3D力数据实时绘图 (demo_3DForce.py)

使用matplotlib绘制Fx、Fy、Fz三轴力的实时曲线。

```bash
python samples/demo_3DForce.py
```

---

##  核心API使用

### TouchSensor 类

#### 初始化

```python
from api import TouchSensor

sensor = TouchSensor(usb_id=0, finger_id="index")
```

**参数说明**：
- `usb_id` (int): USB摄像头ID（通常为0, 1, 2...）
- `finger_id` (str): 手指标识符（用于多传感器场景）
- `cap` (cv2.VideoCapture, 可选): 外部视频捕获对象

#### 主要方法

##### 1. 获取预处理帧

```python
frame = sensor.preprocess_frame()
# 返回: numpy.ndarray - 预处理后的BGR图像
```

##### 2. 校准基准矩阵

```python
sensor.calibrate_base_matrix(frames=30)
# frames: 采集帧数（默认30）
```

**使用场景**：
- 程序启动时自动调用
- 环境光线变化时手动重新校准

##### 3. 获取压力矩阵

```python
pressure_matrix = sensor.get_pressure_matrix(frame)
# 返回: numpy.ndarray - 二维压力矩阵 (grid_rows × grid_cols)
```

**原理**：基于HSV色相偏移量计算压力值

##### 4. 获取光流矩阵

```python
flow_matrix = sensor.get_flow_matrix(frame)
# 返回: numpy.ndarray - 光流矢量矩阵 (H × W × 2)
# flow_matrix[:,:,0] = x方向流动
# flow_matrix[:,:,1] = y方向流动
```

**原理**：Farneback稠密光流算法

##### 5. 获取总力

```python
fx, fy, fz = sensor.get_total_force()
# 返回: (float, float, float) - 三轴力分量
# fx: x方向总力
# fy: y方向总力
# fz: z方向总压力
```

##### 6. 释放资源

```python
sensor.release()
```

---

##  故障排除

### 问题1: 找不到USB摄像头

**症状**：USB端口扫描对话框显示"无可用端口"

**解决方案**：
1. 检查摄像头是否正确连接
2. 在系统设备管理器中确认摄像头被识别
3. 尝试其他USB端口
4. 检查摄像头权限（Linux: 加入video用户组）

```bash
# Linux下检查摄像头设备
ls /dev/video*

# 添加用户到video组
sudo usermod -a -G video $USER
# 注销后重新登录
```

### 问题2: ModuleNotFoundError

**症状**：`ModuleNotFoundError: No module named 'api'`

**解决方案**：
```bash
# 确保从项目根目录运行
cd /path/to/SDK
python GUI/demo_gui.py

# 而不是
cd GUI
python demo_gui.py  # ❌ 这样会找不到api模块
```

### 问题3: 摄像头初始化失败

**症状**：`错误: 无法打开摄像头 USB ID X`

**解决方案**：
1. 确认摄像头没有被其他程序占用
2. 尝试不同的USB ID（0, 1, 2...）
3. 更新OpenCV版本：`pip install --upgrade opencv-python`
4. Windows下：安装DirectShow编解码器

### 问题4: 3D可视化性能慢

**症状**：3D表面更新卡顿，帧率低

**解决方案**：
1. 降低网格分辨率（增大 `cell_size`）
2. 降低图像 `scale_factor`（例如0.3）
3. 关闭STL模型显示
4. 确保系统支持OpenGL 2.0+

### 问题5: 光流检测不准确

**症状**：切向力场显示异常或噪声过大

**解决方案**：
1. 重新校准传感器（按 `C` 键）
2. 调整光流参数：
   - 增大 `winsize`（提高稳定性）
   - 增加 `iterations`（提高精度）
   - 调整 `pyr_scale`（适应运动幅度）
3. 检查光照条件是否稳定

---

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| **帧率** | 20-30 FPS（取决于硬件） |
| **压力分辨率** | 25×25网格（默认） |
| **光流计算延迟** | < 50ms（720p） |
| **内存占用** | ~200MB |
| **CPU占用** | 单核30-50%（i5以上） |

**优化建议**：
- 使用GPU加速的OpenCV版本（`opencv-contrib-python`）
- 降低摄像头分辨率
- 减少网格密度

---

##  常见问题 (FAQ)

**Q1: 可以使用视频文件代替摄像头吗？**

A: 可以！使用外部 `VideoCapture` 对象：

```python
import cv2
from api import TouchSensor

cap = cv2.VideoCapture("video.mp4")
sensor = TouchSensor(usb_id=0, finger_id="test", cap=cap)
```

**Q2: 如何获取原始的压力数据矩阵？**

A: 使用 `get_pressure_matrix()` 方法：

```python
pressure_matrix = sensor.get_pressure_matrix(frame)
print(pressure_matrix)  # numpy数组
```

**Q3: 可以同时连接多个传感器吗？**

A: 可以！为每个传感器分配不同的 `usb_id` 和 `finger_id`：

```python
sensor1 = TouchSensor(usb_id=0, finger_id="index")
sensor2 = TouchSensor(usb_id=1, finger_id="thumb")
```

**Q4: 参数配置保存在哪里？**

A: 保存在 `GUI/parameter_config/sensor_config.json`

**Q5: 如何提高检测灵敏度？**

A:
1. 减小 `cell_size`（提高空间分辨率）
2. 增大 `scale_factor`（使用更高分辨率图像）
3. 调整光流 `winsize` 参数

---