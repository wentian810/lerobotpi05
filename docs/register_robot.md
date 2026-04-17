# LeRobot 机械臂与遥操作器注册指南

> 本指南介绍如何将新的机械臂（Follower）及其遥操作器（Leader）注册到 LeRobot 框架中。
> 
> 参考实现：`lerobot/src/lerobot/robots/openarm_follower/` 和 `lerobot/src/lerobot/teleoperators/openarm_leader/`

---

## 1. 概述

LeRobot 使用分层注册机制管理机器人和遥操作设备：

```
配置层 ────────────────────────────────
│
├── RobotConfig / TeleoperatorConfig    ← draccus.ChoiceRegistry
│       └── @register_subclass("type_name")
│
工厂层 ────────────────────────────────
│
├── make_robot_from_config()            ← utils.py 工厂函数
│       └── elif config.type == "type_name"
│
├── make_teleoperator_from_config()     ← utils.py 工厂函数
│       └── elif config.type == "type_name"
│
实现层 ────────────────────────────────
│
├── YourRobot(Robot)                    ← 机器人实现
│       └── config_class = YourRobotConfig
│
└── YourTeleoperator(Teleoperator)      ← 遥操作器实现
        └── config_class = YourTeleoperatorConfig
```

---

## 2. 机器人（Follower）注册

### 2.1 创建配置类

**文件**: `src/lerobot/robots/your_robot/config_your_robot.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

from dataclasses import dataclass, field
from lerobot.cameras import CameraConfig
from ..config import RobotConfig

# 定义默认关节限位（可选）
DEFAULT_JOINTS_LIMITS: dict[str, tuple[float, float]] = {
    "joint_1": (-180.0, 180.0),
    "joint_2": (-90.0, 90.0),
    # ... 其他关节
}


@dataclass
class YourRobotConfigBase:
    """机器人配置基类，包含所有可配置参数。"""
    
    # ========== 通信接口 ==========
    port: str                              # 串口/端口路径，如 "/dev/ttyACM0"
    
    # ========== 电机配置 ==========
    # 电机名称映射到 (电机ID, 电机型号)
    motor_config: dict[str, tuple[int, str]] = field(
        default_factory=lambda: {
            "joint_1": (1, "xl430-w250"),   # (ID, 型号)
            "joint_2": (2, "xl430-w250"),
            "joint_3": (3, "xl330-m288"),
            # ...
        }
    )
    
    # ========== 安全限位 ==========
    # 可为每个关节设置最小/最大角度限制
    joint_limits: dict[str, tuple[float, float]] = field(
        default_factory=lambda: DEFAULT_JOINTS_LIMITS
    )
    
    # ========== 相机配置 ==========
    cameras: dict[str, CameraConfig] = field(default_factory=dict)
    
    # ========== 其他参数 ==========
    fps: int = 30                          # 控制频率
    max_relative_target: float | None = None  # 相对目标限制（安全）


# ========== 关键：注册到 RobotConfig ==========
@RobotConfig.register_subclass("your_robot")  # ← 注册名称，用于 CLI/YAML 识别
@dataclass
class YourRobotConfig(RobotConfig, YourRobotConfigBase):
    """机器人配置类，继承 RobotConfig 以获得 draccus 选择注册功能。"""
    pass
```

**关键要点**:
- 使用 `@RobotConfig.register_subclass("your_robot")` 将配置注册到选择注册表
- `RobotConfig` 继承自 `draccus.ChoiceRegistry`，支持通过 `type` 字段自动反序列化
- `port` 是必需参数（无默认值），强制用户在配置时指定
- `cameras` 使用 `field(default_factory=dict)` 避免可变默认值问题

---

### 2.2 创建机器人类

**文件**: `src/lerobot/robots/your_robot/your_robot.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

import logging
import time
from functools import cached_property
from typing import Any

from lerobot.cameras import make_cameras_from_configs
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.dynamixel import DynamixelMotorsBus  # 或其他总线
from lerobot.types import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..robot import Robot
from ..utils import ensure_safe_goal_position
from .config_your_robot import YourRobotConfig

logger = logging.getLogger(__name__)


class YourRobot(Robot):
    """
    你的机械臂实现。
    
    描述机械臂的基本信息：
    - DOF（自由度数量）
    - 使用的电机类型
    - 通信协议
    - 支持的相机类型
    """
    
    # ========== 类属性：必须设置 ==========
    config_class = YourRobotConfig          # ← 关联配置类
    name = "your_robot"                     # ← 机器人标识名称

    def __init__(self, config: YourRobotConfig):
        super().__init__(config)
        self.config = config

        # ========== 1. 创建电机总线 ==========
        motors: dict[str, Motor] = {}
        for motor_name, (motor_id, motor_model) in config.motor_config.items():
            motors[motor_name] = Motor(
                motor_id, 
                motor_model, 
                MotorNormMode.DEGREES  # 或 RANGE_0_100, RANGE_M100_100
            )

        self.bus = DynamixelMotorsBus(
            port=self.config.port,
            motors=motors,
            calibration=self.calibration,
        )

        # ========== 2. 初始化相机 ==========
        self.cameras = make_cameras_from_configs(config.cameras)

    # ========== 特征定义 ==========
    
    @property
    def _motors_ft(self) -> dict[str, type]:
        """定义电机相关观测/动作特征。"""
        features: dict[str, type] = {}
        for motor in self.bus.motors:
            features[f"{motor}.pos"] = float      # 位置
            features[f"{motor}.vel"] = float      # 速度（可选）
            features[f"{motor}.torque"] = float   # 力矩（可选）
        return features

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        """定义相机观测特征（图像尺寸）。"""
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3)
            for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        """组合观测特征（电机 + 相机）。"""
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        """动作特征（通常与电机特征相同）。"""
        return self._motors_ft

    # ========== 连接管理 ==========
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接。"""
        return self.bus.is_connected and all(
            cam.is_connected for cam in self.cameras.values()
        )

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """
        连接机器人。
        
        流程：
        1. 连接电机总线
        2. 检查/执行标定
        3. 连接相机
        4. 配置电机参数
        5. 使能扭矩
        """
        logger.info(f"Connecting robot on {self.config.port}...")
        
        # 1. 连接电机
        self.bus.connect()
        
        # 2. 标定检查
        if not self.is_calibrated and calibrate:
            logger.info("Calibration needed, running calibration...")
            self.calibrate()
        
        # 3. 连接相机
        for cam in self.cameras.values():
            cam.connect()
        
        # 4. 配置电机
        self.configure()
        
        # 5. 设置零位（如果已标定）
        if self.is_calibrated:
            self.bus.set_zero_position()
        
        # 6. 使能扭矩
        self.bus.enable_torque()
        
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        """检查是否已标定。"""
        return self.bus.is_calibrated

    def calibrate(self) -> None:
        """
        执行标定流程。
        
        典型流程：
        1. 禁用扭矩
        2. 引导用户将机械臂置于零位
        3. 记录零位偏移
        4. 记录各关节运动范围
        5. 保存标定数据
        """
        if self.calibration:
            # 已有标定文件，询问是否使用
            user_input = input(
                f"Press ENTER to use calibration file for {self.id}, "
                "or type 'c' to recalibrate: "
            )
            if user_input.strip().lower() != "c":
                self.bus.write_calibration(self.calibration)
                return

        logger.info(f"\nRunning calibration for {self}")
        self.bus.disable_torque()

        # 引导用户将机械臂置于零位
        input(
            "\nCalibration: Set Zero Position\n"
            "Position the arm in zero position (e.g., all joints at 0°)\n"
            "Press ENTER when ready..."
        )

        # 设置零位
        self.bus.set_zero_position()
        logger.info("Zero position set.")

        # 记录运动范围
        input(
            "\nMove each joint to its minimum position, then press ENTER..."
        )
        # ... 记录最小值
        
        input(
            "\nMove each joint to its maximum position, then press ENTER..."
        )
        # ... 记录最大值

        # 保存标定
        for motor_name, motor in self.bus.motors.items():
            self.calibration[motor_name] = MotorCalibration(
                id=motor.id,
                drive_mode=0,
                homing_offset=0,
                range_min=-180,
                range_max=180,
            )

        self.bus.write_calibration(self.calibration)
        self._save_calibration()
        logger.info(f"Calibration saved to {self.calibration_fpath}")

    def configure(self) -> None:
        """配置电机参数（PID、工作模式等）。"""
        with self.bus.torque_disabled():
            self.bus.configure_motors()

    def setup_motors(self) -> None:
        """
        电机ID设置（如果需要）。
        对于某些电机，可能需要通过厂商工具设置ID。
        """
        raise NotImplementedError(
            "Motor ID configuration is typically done via manufacturer tools."
        )

    # ========== 核心控制接口 ==========
    
    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        """
        获取当前观测。
        
        返回包含：
        - 各关节位置、速度、力矩
        - 相机图像
        """
        start = time.perf_counter()
        obs_dict: dict[str, Any] = {}

        # 读取电机状态
        states = self.bus.sync_read_all_states()
        for motor in self.bus.motors:
            state = states.get(motor, {})
            obs_dict[f"{motor}.pos"] = state.get("position", 0.0)
            obs_dict[f"{motor}.vel"] = state.get("velocity", 0.0)
            obs_dict[f"{motor}.torque"] = state.get("torque", 0.0)

        # 读取相机
        for cam_key, cam in self.cameras.items():
            obs_dict[cam_key] = cam.read_latest()

        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} get_observation took: {dt_ms:.1f}ms")

        return obs_dict

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        """
        发送动作指令。
        
        Args:
            action: 动作字典，如 {"joint_1.pos": 10.0, "joint_2.pos": -5.0}
        
        Returns:
            实际发送的动作（可能经过裁剪）
        """
        # 提取目标位置
        goal_pos = {
            key.removesuffix(".pos"): val 
            for key, val in action.items() 
            if key.endswith(".pos")
        }

        # 应用关节限位
        for motor_name, position in goal_pos.items():
            if motor_name in self.config.joint_limits:
                min_limit, max_limit = self.config.joint_limits[motor_name]
                clipped = max(min_limit, min(max_limit, position))
                if clipped != position:
                    logger.debug(f"Clipped {motor_name} from {position:.2f}° to {clipped:.2f}°")
                goal_pos[motor_name] = clipped

        # 应用相对目标限制（安全）
        if self.config.max_relative_target is not None:
            present_pos = self.bus.sync_read("Present_Position")
            goal_present = {
                key: (g_pos, present_pos[key]) 
                for key, g_pos in goal_pos.items()
            }
            goal_pos = ensure_safe_goal_position(
                goal_present, 
                self.config.max_relative_target
            )

        # 发送指令到电机
        self.bus.sync_write("Goal_Position", goal_pos)

        return {f"{motor}.pos": val for motor, val in goal_pos.items()}

    @check_if_not_connected
    def disconnect(self) -> None:
        """断开连接，清理资源。"""
        self.bus.disconnect(disable_torque=True)
        for cam in self.cameras.values():
            cam.disconnect()
        logger.info(f"{self} disconnected.")
```

**关键要点**:
- 必须设置 `config_class` 和 `name` 类属性
- 继承 `Robot` 基类，实现所有抽象方法
- 使用 `@check_if_already_connected` 和 `@check_if_not_connected` 装饰器进行状态检查
- `get_observation()` 和 `send_action()` 是核心控制接口
- 支持上下文管理器 (`with robot:`) 自动管理连接

---

### 2.3 注册到工厂函数

**文件**: `src/lerobot/robots/utils.py`

在 `make_robot_from_config()` 函数中添加分支：

```python
def make_robot_from_config(config: RobotConfig) -> Robot:
    # ... 其他机器人分支 ...
    
    elif config.type == "your_robot":                    # ← 匹配配置 type
        from .your_robot import YourRobot                # ← 延迟导入
        return YourRobot(config)
    
    # ... 其他分支 ...
    else:
        raise ValueError(f"Unknown robot type: {config.type}")
```

---

## 3. 遥操作器（Leader）注册

### 3.1 创建遥操作配置类

**文件**: `src/lerobot/teleoperators/your_leader/config_your_leader.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

from dataclasses import dataclass, field
from ..config import TeleoperatorConfig


@dataclass
class YourLeaderConfigBase:
    """遥操作器配置基类。"""
    
    # 通信接口
    port: str                              # 串口路径
    
    # 电机配置（与 Follower 类似）
    motor_config: dict[str, tuple[int, str]] = field(
        default_factory=lambda: {
            "joint_1": (1, "xl430-w250"),
            "joint_2": (2, "xl430-w250"),
            # ...
        }
    )
    
    # 手动控制模式（Leader 通常为手动，扭矩禁用）
    manual_control: bool = True


@TeleoperatorConfig.register_subclass("your_leader")  # ← 注册遥操作器
@dataclass
class YourLeaderConfig(TeleoperatorConfig, YourLeaderConfigBase):
    pass
```

---

### 3.2 创建遥操作类

**文件**: `src/lerobot/teleoperators/your_leader/your_leader.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

import logging
import time
from typing import Any

from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.dynamixel import DynamixelMotorsBus
from lerobot.types import RobotAction
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..teleoperator import Teleoperator
from .config_your_leader import YourLeaderConfig

logger = logging.getLogger(__name__)


class YourLeader(Teleoperator):
    """
    遥操作器（主臂）实现。
    
    Leader 用于人工操作，通常：
    - 扭矩禁用，可手动拖动
    - 读取位置作为 Follower 的目标
    - 可选：接收力反馈
    """
    
    config_class = YourLeaderConfig
    name = "your_leader"

    def __init__(self, config: YourLeaderConfig):
        super().__init__(config)
        self.config = config

        # 创建电机总线
        motors: dict[str, Motor] = {}
        for motor_name, (motor_id, motor_model) in config.motor_config.items():
            motors[motor_name] = Motor(
                motor_id, 
                motor_model, 
                MotorNormMode.DEGREES
            )

        self.bus = DynamixelMotorsBus(
            port=self.config.port,
            motors=motors,
            calibration=self.calibration,
        )

    # ========== 特征定义 ==========
    
    @property
    def action_features(self) -> dict[str, type]:
        """遥操作产生的动作特征。"""
        return {
            f"{motor}.pos": float for motor in self.bus.motors
        }

    @property
    def feedback_features(self) -> dict[str, type]:
        """期望的反馈特征（如力反馈）。"""
        return {}  # 如果支持力反馈，定义此处

    # ========== 连接管理 ==========
    
    @property
    def is_connected(self) -> bool:
        return self.bus.is_connected

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """连接遥操作器。Leader 通常禁用扭矩以便手动操作。"""
        logger.info(f"Connecting teleoperator on {self.config.port}...")
        
        self.bus.connect()
        
        if not self.is_calibrated and calibrate:
            self.calibrate()
        
        self.configure()  # 这会禁用扭矩（如果 manual_control=True）
        
        if self.is_calibrated:
            self.bus.set_zero_position()
        
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        return self.bus.is_calibrated

    def calibrate(self) -> None:
        """执行标定。"""
        if self.calibration:
            user_input = input(
                f"Use existing calibration for {self.id}? "
                "Press ENTER to use, 'c' to recalibrate: "
            )
            if user_input.strip().lower() != "c":
                self.bus.write_calibration(self.calibration)
                return

        logger.info(f"\nCalibrating {self}")
        self.bus.disable_torque()

        input(
            "\nSet the leader arm to zero position, then press ENTER..."
        )
        
        self.bus.set_zero_position()
        
        # 记录标定数据
        for motor_name, motor in self.bus.motors.items():
            self.calibration[motor_name] = MotorCalibration(
                id=motor.id,
                drive_mode=0,
                homing_offset=0,
                range_min=-180,
                range_max=180,
            )

        self.bus.write_calibration(self.calibration)
        self._save_calibration()
        logger.info(f"Calibration saved to {self.calibration_fpath}")

    def configure(self) -> None:
        """配置：Leader 禁用扭矩以便手动拖动。"""
        if self.config.manual_control:
            self.bus.disable_torque()
        else:
            self.bus.configure_motors()

    # ========== 核心接口 ==========
    
    @check_if_not_connected
    def get_action(self) -> RobotAction:
        """
        获取遥操作动作。
        
        这是 Leader 的核心方法：读取当前位置作为 Follower 的目标。
        """
        start = time.perf_counter()
        
        states = self.bus.sync_read_all_states()
        action = {}
        
        for motor in self.bus.motors:
            state = states.get(motor, {})
            action[f"{motor}.pos"] = state.get("position", 0.0)
        
        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} get_action took: {dt_ms:.1f}ms")
        
        return action

    def send_feedback(self, feedback: dict[str, float]) -> None:
        """
        发送反馈到遥操作器（如力反馈）。
        
        如果 Leader 支持力反馈（如触觉设备），在此处实现。
        """
        raise NotImplementedError("Feedback not implemented for YourLeader.")

    @check_if_not_connected
    def disconnect(self) -> None:
        """断开连接。"""
        # Leader 断开前确保扭矩禁用（安全）
        self.bus.disconnect(disable_torque=True)
        logger.info(f"{self} disconnected.")
```

---

### 3.3 注册到工厂函数

**文件**: `src/lerobot/teleoperators/utils.py`

在 `make_teleoperator_from_config()` 函数中添加：

```python
def make_teleoperator_from_config(config: TeleoperatorConfig) -> "Teleoperator":
    # ... 其他遥操作器分支 ...
    
    elif config.type == "your_leader":
        from .your_leader import YourLeader
        return YourLeader(config)
    
    # ... 其他分支 ...
```

---

## 4. 目录结构

创建以下文件结构：

```
src/lerobot/
├── robots/
│   ├── your_robot/
│   │   ├── __init__.py
│   │   ├── config_your_robot.py      # 配置类
│   │   └── your_robot.py             # 机器人类
│   └── utils.py                       # 修改工厂函数
│
└── teleoperators/
    ├── your_leader/
    │   ├── __init__.py
    │   ├── config_your_leader.py     # 遥操作配置
    │   └── your_leader.py            # 遥操作类
    └── utils.py                       # 修改工厂函数
```

---

## 5. 使用示例

### 5.1 配置 YAML 文件

```yaml
# robot_config.yaml
robot:
  type: your_robot
  id: arm_001
  port: /dev/ttyACM0
  cameras:
    cam_high:
      type: opencv
      index_or_path: 0
      fps: 30
      width: 640
      height: 480

teleoperator:
  type: your_leader
  id: leader_001
  port: /dev/ttyACM1
  manual_control: true
```

### 5.2 Python 代码使用

```python
from lerobot.robots import make_robot_from_config
from lerobot.teleoperators import make_teleoperator_from_config
from lerobot.robots.your_robot import YourRobotConfig
from lerobot.teleoperators.your_leader import YourLeaderConfig

# 创建配置
robot_config = YourRobotConfig(
    port="/dev/ttyACM0",
    cameras={...}
)

leader_config = YourLeaderConfig(
    port="/dev/ttyACM1",
    manual_control=True
)

# 创建实例
robot = make_robot_from_config(robot_config)
leader = make_teleoperator_from_config(leader_config)

# 遥操作循环
with robot, leader:
    while True:
        # 1. 读取遥操作动作
        action = leader.get_action()
        
        # 2. 发送给机器人执行
        robot.send_action(action)
        
        # 3. 获取观测（可选：用于记录数据集）
        obs = robot.get_observation()
```

### 5.3 使用 CLI

```bash
# 采集数据
lerobot-record \
  --robot.type=your_robot \
  --robot.port=/dev/ttyACM0 \
  --teleoperator.type=your_leader \
  --teleoperator.port=/dev/ttyACM1 \
  --dataset.repo_id=your_username/your_dataset

# 训练策略
lerobot-train \
  --policy.type=act \
  --dataset.repo_id=your_username/your_dataset

# 部署推理
lerobot-teleoperate \
  --robot.type=your_robot \
  --robot.port=/dev/ttyACM0 \
  --policy.path=path/to/checkpoint
```

---

## 6. 不同电机总线选择

LeRobot 支持多种电机通信协议：

| 电机类型 | 总线类 | 适用场景 |
|---------|--------|---------|
| Dynamixel (XL430, XM540等) | `DynamixelMotorsBus` | 大多数消费级机械臂 |
| Feetech (STS3215等) | `FeetechMotorsBus` | 经济型机械臂 (SO100) |
| Damiao (DM8009, DM4310等) | `DamiaoMotorsBus` | CAN FD 总线机械臂 (OpenARM) |

**更换电机总线**：

```python
from lerobot.motors.damiao import DamiaoMotorsBus  # CAN FD

self.bus = DamiaoMotorsBus(
    port="can0",                  # CAN 接口
    motors=motors,
    calibration=self.calibration,
    can_interface="socketcan",
    use_can_fd=True,
    bitrate=1000000,
    data_bitrate=5000000,
)
```

---

## 7. 调试技巧

### 7.1 检查配置是否正确注册

```python
from lerobot.robots.config import RobotConfig

# 查看所有注册的机器人类型
print(RobotConfig.get_known_choices())
# 输出: {'koch_follower', 'so100_follower', 'your_robot', ...}
```

### 7.2 检查标定文件

标定文件默认保存在：
- Linux: `~/.local/share/lerobot/calibration/robots/{robot_name}/{robot_id}.json`
- 或 `~/.cache/lerobot/calibration/...`

### 7.3 日志调试

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 8. 参考资源

- **基类定义**: `src/lerobot/robots/robot.py`, `src/lerobot/teleoperators/teleoperator.py`
- **完整示例**: `src/lerobot/robots/openarm_follower/`, `src/lerobot/teleoperators/openarm_leader/`
- **其他参考**: `src/lerobot/robots/koch_follower/`, `src/lerobot/robots/so_follower/`
