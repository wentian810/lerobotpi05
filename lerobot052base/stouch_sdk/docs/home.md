# TouchSensor Wiki

TouchSensor 是一个基于 USB 摄像头的视觉触觉传感系统：通过 HSV 色相变化估计压力分布，并使用 Farneback 稠密光流算法计算切向力。

本 Wiki 用于快速上手、参数配置与 API 查询。

---

## 快速开始

1. 安装依赖：`pip install -r requirements.txt`
2. 启动 GUI：`python GUI/demo_gui.py`
3. 选择 USB 端口后，建议点击 `Calibrate`（或按 `C`）完成基准校准

## 文档导航（按任务）

- GUI 使用与参数配置：请看 [user_guide.md](user_guide.md)
- API 方法与返回值：请看 [api_reference.md](api_reference.md)

---

## 推荐阅读路径

- 初次使用：快速开始 → [user_guide.md](user_guide.md)
- API 调用/二次开发： [api_reference.md](api_reference.md) → [user_guide.md](user_guide.md)
