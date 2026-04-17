# 松灵 Piper 机械臂 LeRobot 注册指南

> 本指南介绍如何将松灵 (AgileX) Piper 机械臂通过其官方 SDK 注册到 LeRobot 框架中，同时支持作为机械臂（Follower）和遥操作器（Leader）使用。
>
> 前置知识：建议先阅读 `docs/regist_robot.md` 了解 LeRobot 注册机制，以及 `docs/piper_sdk.md` 了解 Piper SDK。

---

## 1. 概述

### 1.1 Piper 与 LeRobot 的集成架构

```
LeRobot Framework
│
├── 配置层 (Config)
│   ├── PiperRobotConfig ──────┐
│   └── PiperLeaderConfig ─────┤
│                              │
├── 实现层 (Implementation)    │
│   ├── PiperRobot ────────────┤ ← 封装 piper_sdk.C_PiperInterface_V2
│   │   │                      │   (Follower - 执行动作)
│   │   └── piper_interface    │
│   │                          │
│   └── PiperLeader ───────────┤ ← 封装 piper_sdk.C_PiperInterface_V2
│       │                      │   (Leader - 读取位置)
│       └── piper_interface    │
│                              │
└── Piper SDK Layer            │
    └── C_PiperInterface_V2 ←──┘
        │
        ├── JointCtrl()        ← 关节控制
        ├── GripperCtrl()      ← 夹爪控制
        ├── GetArmJointMsgs()  ← 读取关节状态
        ├── EnablePiper()      ← 电机使能
        └── DisablePiper()     ← 电机失能
```

### 1.2 Piper 在 LeRobot 中的特殊性

| 特性 | Piper SDK | LeRobot 适配要点 |
|------|-----------|------------------|
| 通信方式 | CAN 总线 | 通过 Piper SDK 封装，无需关心底层 |
| 关节单位 | 0.001 度 (int) | 需要弧度 ↔ SDK 单位转换 |
| 夹爪 | 0-1000000 (0.001mm) | 需要归一化处理 |
| 电机使能 | 需显式调用 EnablePiper() | 在 connect() 中自动处理 |
| 主从模式 | 内置主从支持 | Leader 禁用扭矩，Follower 使能扭矩 |
| 运动模式 | MOVE J/P/L/C | Follower 使用 MOVE J |

---

## 2. 目录结构

创建以下文件结构：

```
src/lerobot/
├── robots/
│   ├── piper_follower/
│   │   ├── __init__.py
│   │   ├── config_piper_follower.py    # 机器人配置类
│   │   └── piper_follower.py           # 机器人类（Follower）
│   └── utils.py                         # 需要添加工厂函数分支
│
└── teleoperators/
    ├── piper_leader/
    │   ├── __init__.py
    │   ├── config_piper_leader.py      # 遥操作配置类
    │   └── piper_leader.py             # 遥操作类（Leader）
    └── utils.py                         # 需要添加工厂函数分支
```

---

## 3. 机器人（Follower）实现

### 3.1 配置类

**文件**: `src/lerobot/robots/piper_follower/config_piper_follower.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

from dataclasses import dataclass, field
from lerobot.cameras import CameraConfig
from ..config import RobotConfig


@dataclass
class PiperFollowerConfigBase:
    """Piper 机械臂 Follower 配置。
    
    Piper 机械臂特性：
    - 6DOF + 1 夹爪
    - CAN 总线通信
    - 关节角度单位：0.001 度
    - 夹爪单位：0.001mm (0-1000000)
    """
    
    # ========== CAN 配置 ==========
    can_port: str = "can0"                 # CAN 端口名称
    
    # ========== 控制参数 ==========
    # 运动速度百分比 (0-100)
    speed_rate: int = 100
    
    # 控制周期 (秒)，Piper 推荐 200Hz
    control_period: float = 0.005
    
    # 是否自动使能电机
    auto_enable: bool = True
    
    # ========== 安全限位 ==========
    # 关节限位 (弧度)
    joint_limits: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "joint_1": (-2.967, 2.967),    # ±170°
            "joint_2": (-2.967, 2.967),    # ±170°
            "joint_3": (-2.967, 2.967),    # ±170°
            "joint_4": (-2.967, 2.967),    # ±170°
            "joint_5": (-2.967, 2.967),    # ±170°
            "joint_6": (-2.967, 2.967),    # ±170°
            "gripper": (0.0, 0.1),          # 0-100mm，转米
        }
    )
    
    # ========== 相机配置 ==========
    cameras: dict[str, CameraConfig] = field(default_factory=dict)


@RobotConfig.register_subclass("piper_follower")
@dataclass
class PiperFollowerConfig(RobotConfig, PiperFollowerConfigBase):
    """Piper Follower 配置类。"""
    pass
```

### 3.2 机器人类

**文件**: `src/lerobot/robots/piper_follower/piper_follower.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

import logging
import time
import math
from functools import cached_property
from typing import Any

from lerobot.cameras import make_cameras_from_configs
from lerobot.types import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..robot import Robot
from .config_piper_follower import PiperFollowerConfig

# 导入 Piper SDK
try:
    from piper_sdk import C_PiperInterface_V2, LogLevel
except ImportError:
    raise ImportError(
        "Piper SDK not installed. Please install it with: pip install piper_sdk"
    )

logger = logging.getLogger(__name__)

# 单位转换常量
RAD_TO_DEG = 180.0 / math.pi
DEG_TO_RAD = math.pi / 180.0
PIPER_ANGLE_FACTOR = 1000.0 * 180.0 / math.pi  # 57295.7795, 弧度转 SDK 单位


class PiperFollower(Robot):
    """
    松灵 Piper 机械臂 Follower 实现。
    
    特性：
    - 6DOF + 1 夹爪
    - CAN 总线通信
    - 支持关节空间控制
    - 自动电机使能管理
    
    使用示例：
        config = PiperFollowerConfig(can_port="can0")
        robot = PiperFollower(config)
        with robot:
            obs = robot.get_observation()
            action = {"joint_1.pos": 0.5, "gripper.pos": 0.05}
            robot.send_action(action)
    """
    
    config_class = PiperFollowerConfig
    name = "piper_follower"
    
    # 关节名称列表
    JOINT_NAMES = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]

    def __init__(self, config: PiperFollowerConfig):
        super().__init__(config)
        self.config = config
        
        # 初始化 Piper 接口
        logger.info(f"Initializing Piper interface on {config.can_port}")
        self.piper = C_PiperInterface_V2(
            can_name=config.can_port,
            judge_flag=False,           # 非官方 CAN 模块设为 False
            can_auto_init=True,
            logger_level=LogLevel.WARNING,
        )
        
        # 初始化相机
        self.cameras = make_cameras_from_configs(config.cameras)
        
        # 状态缓存
        self._last_joint_positions = [0.0] * 6
        self._last_gripper_position = 0.0

    # ========== 特征定义 ==========
    
    @property
    def _joints_ft(self) -> dict[str, type]:
        """定义关节特征。"""
        features = {}
        for joint in self.JOINT_NAMES:
            features[f"{joint}.pos"] = float
        features["gripper.pos"] = float
        return features

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        """定义相机特征。"""
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3)
            for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        """观测特征 = 关节 + 相机。"""
        return {**self._joints_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        """动作特征与观测特征相同。"""
        return self._joints_ft

    # ========== 连接管理 ==========
    
    @property
    def is_connected(self) -> bool:
        """检查连接状态。"""
        return self.piper.get_connect_status() and all(
            cam.is_connected for cam in self.cameras.values()
        )

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """
        连接 Piper 机械臂。
        
        流程：
        1. 连接 CAN 端口
        2. 使能电机
        3. 连接相机
        """
        logger.info(f"Connecting Piper on {self.config.can_port}...")
        
        # 1. 连接 CAN 端口
        self.piper.ConnectPort()
        
        # 2. 使能电机（如果需要）
        if self.config.auto_enable:
            logger.info("Enabling Piper motors...")
            timeout = 5.0
            start_time = time.time()
            while not self.piper.EnablePiper():
                if time.time() - start_time > timeout:
                    raise RuntimeError("Failed to enable Piper motors within timeout")
                time.sleep(0.01)
            logger.info("Piper motors enabled")
        
        # 3. 连接相机
        for cam in self.cameras.values():
            cam.connect()
        
        logger.info(f"{self} connected")

    @property
    def is_calibrated(self) -> bool:
        """Piper 机械臂无需 LeRobot 式标定，直接返回 True。"""
        return True

    def calibrate(self) -> None:
        """Piper 无需额外标定。"""
        logger.info("Piper does not require calibration")

    def configure(self) -> None:
        """配置 Piper 参数。"""
        pass

    def setup_motors(self) -> None:
        """Piper 电机在出厂时已配置好。"""
        pass

    # ========== 核心控制接口 ==========
    
    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        """
        获取当前观测（关节角度 + 相机图像）。
        
        Returns:
            dict: 包含关节位置和相机图像的字典
        """
        start = time.perf_counter()
        obs_dict: dict[str, Any] = {}
        
        # 1. 读取关节角度
        joint_msgs = self.piper.GetArmJointMsgs()
        joint_positions = [
            joint_msgs.joint_state.joint_1 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_2 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_3 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_4 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_5 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_6 / 1000.0 * DEG_TO_RAD,
        ]
        
        for i, joint_name in enumerate(self.JOINT_NAMES):
            obs_dict[f"{joint_name}.pos"] = joint_positions[i]
        
        # 2. 读取夹爪位置
        gripper_msgs = self.piper.GetArmGripperMsgs()
        gripper_pos_mm = gripper_msgs.gripper_state.grippers_angle / 1000.0
        obs_dict["gripper.pos"] = gripper_pos_mm / 1000.0  # 转米
        
        # 3. 读取相机
        for cam_key, cam in self.cameras.items():
            obs_dict[cam_key] = cam.read_latest()
        
        # 更新缓存
        self._last_joint_positions = joint_positions
        self._last_gripper_position = gripper_pos_mm / 1000.0
        
        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} get_observation took: {dt_ms:.1f}ms")
        
        return obs_dict

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        """
        发送动作指令到 Piper。
        
        Args:
            action: 动作字典，如：
                {
                    "joint_1.pos": 0.5,      # 弧度
                    "joint_2.pos": -0.3,
                    ...
                    "gripper.pos": 0.05,      # 米（0-0.1）
                }
        
        Returns:
            实际发送的动作
        """
        # 1. 提取关节目标（弧度转 SDK 单位）
        joint_targets = []
        for joint_name in self.JOINT_NAMES:
            key = f"{joint_name}.pos"
            if key in action:
                # 弧度 → 0.001度
                target_deg = action[key] * RAD_TO_DEG
                target_sdk = int(round(target_deg * 1000))
                
                # 应用限位
                if joint_name in self.config.joint_limits:
                    min_rad, max_rad = self.config.joint_limits[joint_name]
                    min_sdk = int(min_rad * RAD_TO_DEG * 1000)
                    max_sdk = int(max_rad * RAD_TO_DEG * 1000)
                    target_sdk = max(min_sdk, min(max_sdk, target_sdk))
                
                joint_targets.append(target_sdk)
            else:
                # 使用当前位置
                joint_targets.append(int(self._last_joint_positions[len(joint_targets)] * PIPER_ANGLE_FACTOR))
        
        # 2. 提取夹爪目标
        gripper_target = 500000  # 默认半开
        if "gripper.pos" in action:
            # 米 → 0.001mm
            gripper_m = action["gripper.pos"]
            if "gripper" in self.config.joint_limits:
                min_m, max_m = self.config.joint_limits["gripper"]
                gripper_m = max(min_m, min(max_m, gripper_m))
            gripper_target = int(gripper_m * 1000 * 1000)
        
        # 3. 设置运动模式（MOVE J - 关节空间运动）
        self.piper.MotionCtrl_2(
            ctrl_mode=0x01,              # CAN 控制模式
            move_mode=0x01,              # MOVE J
            speed_rate=self.config.speed_rate,
            delay=0x00
        )
        
        # 4. 发送关节控制指令
        self.piper.JointCtrl(*joint_targets)
        
        # 5. 发送夹爪控制
        self.piper.GripperCtrl(
            gripper_pos=gripper_target,
            gripper_force=1000,          # 最大力
            gripper_code=0x01,           # 启用控制
            delay=0
        )
        
        # 6. 构造返回值
        result = {}
        for i, joint_name in enumerate(self.JOINT_NAMES):
            result[f"{joint_name}.pos"] = joint_targets[i] / (1000.0 * RAD_TO_DEG)
        result["gripper.pos"] = gripper_target / (1000.0 * 1000.0)
        
        return result

    @check_if_not_connected
    def disconnect(self) -> None:
        """断开连接，禁用电机。"""
        logger.info(f"Disconnecting {self}...")
        
        # 禁用电机
        self.piper.DisablePiper()
        
        # 断开 CAN 端口
        self.piper.DisconnectPort()
        
        # 断开相机
        for cam in self.cameras.values():
            cam.disconnect()
        
        logger.info(f"{self} disconnected")
```

---

## 4. 遥操作器（Leader）实现

### 4.1 配置类

**文件**: `src/lerobot/teleoperators/piper_leader/config_piper_leader.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

from dataclasses import dataclass, field
from ..config import TeleoperatorConfig


@dataclass
class PiperLeaderConfigBase:
    """Piper 机械臂 Leader（遥操作器）配置。
    
    Leader 用于手动拖动示教，特点：
    - 电机失能（可手动拖动）
    - 读取关节位置发送给 Follower
    """
    
    # CAN 端口
    can_port: str = "can0"
    
    # 控制周期
    control_period: float = 0.005
    
    # 是否禁用电机（手动拖动模式）
    manual_control: bool = True


@TeleoperatorConfig.register_subclass("piper_leader")
@dataclass
class PiperLeaderConfig(TeleoperatorConfig, PiperLeaderConfigBase):
    """Piper Leader 配置类。"""
    pass
```

### 4.2 遥操作类

**文件**: `src/lerobot/teleoperators/piper_leader/piper_leader.py`

```python
#!/usr/bin/env python
# Copyright 2025 The HuggingFace Inc. team. All rights reserved.

import logging
import time
import math
from typing import Any

from lerobot.types import RobotAction
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..teleoperator import Teleoperator
from .config_piper_leader import PiperLeaderConfig

try:
    from piper_sdk import C_PiperInterface_V2, LogLevel
except ImportError:
    raise ImportError(
        "Piper SDK not installed. Please install it with: pip install piper_sdk"
    )

logger = logging.getLogger(__name__)

RAD_TO_DEG = 180.0 / math.pi
DEG_TO_RAD = math.pi / 180.0


class PiperLeader(Teleoperator):
    """
    松灵 Piper 机械臂 Leader（遥操作器）实现。
    
    用于主从遥教模式：
    - 电机失能，可手动拖动
    - 实时读取关节位置
    - 发送位置给 Follower 执行
    
    使用示例：
        leader = PiperLeader(PiperLeaderConfig(can_port="can0"))
        follower = PiperFollower(PiperFollowerConfig(can_port="can1"))
        
        with leader, follower:
            while True:
                action = leader.get_action()
                follower.send_action(action)
    """
    
    config_class = PiperLeaderConfig
    name = "piper_leader"
    
    JOINT_NAMES = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]

    def __init__(self, config: PiperLeaderConfig):
        super().__init__(config)
        self.config = config
        
        # 初始化 Piper 接口
        logger.info(f"Initializing Piper Leader on {config.can_port}")
        self.piper = C_PiperInterface_V2(
            can_name=config.can_port,
            judge_flag=False,
            can_auto_init=True,
            logger_level=LogLevel.WARNING,
        )

    # ========== 特征定义 ==========
    
    @property
    def action_features(self) -> dict[str, type]:
        """遥操作产生的动作特征。"""
        features = {}
        for joint in self.JOINT_NAMES:
            features[f"{joint}.pos"] = float
        features["gripper.pos"] = float
        return features

    @property
    def feedback_features(self) -> dict[str, type]:
        """期望的反馈特征（Piper Leader 暂不支持力反馈）。"""
        return {}

    # ========== 连接管理 ==========
    
    @property
    def is_connected(self) -> bool:
        """检查连接状态。"""
        return self.piper.get_connect_status()

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """
        连接 Piper Leader。
        
        Leader 默认禁用电机，以便手动拖动。
        """
        logger.info(f"Connecting Piper Leader on {self.config.can_port}...")
        
        # 连接 CAN 端口
        self.piper.ConnectPort()
        
        # 禁用电机（手动拖动模式）
        if self.config.manual_control:
            logger.info("Disabling motors for manual control...")
            self.piper.DisablePiper()
            logger.info("Motors disabled, arm is now free to move")
        
        logger.info(f"{self} connected")

    @property
    def is_calibrated(self) -> bool:
        """Piper 无需标定。"""
        return True

    def calibrate(self) -> None:
        """Piper 无需标定。"""
        logger.info("Piper Leader does not require calibration")

    def configure(self) -> None:
        """配置 Leader。"""
        if self.config.manual_control:
            self.piper.DisablePiper()

    # ========== 核心接口 ==========
    
    @check_if_not_connected
    def get_action(self) -> RobotAction:
        """
        获取遥操作动作（当前关节位置）。
        
        Returns:
            dict: 包含关节位置的字典，单位：弧度
        """
        start = time.perf_counter()
        
        # 读取关节角度
        joint_msgs = self.piper.GetArmJointMsgs()
        action = {}
        
        joint_positions = [
            joint_msgs.joint_state.joint_1 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_2 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_3 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_4 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_5 / 1000.0 * DEG_TO_RAD,
            joint_msgs.joint_state.joint_6 / 1000.0 * DEG_TO_RAD,
        ]
        
        for i, joint_name in enumerate(self.JOINT_NAMES):
            action[f"{joint_name}.pos"] = joint_positions[i]
        
        # 读取夹爪位置
        gripper_msgs = self.piper.GetArmGripperMsgs()
        gripper_pos_m = gripper_msgs.gripper_state.grippers_angle / (1000.0 * 1000.0)
        action["gripper.pos"] = gripper_pos_m
        
        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} get_action took: {dt_ms:.1f}ms")
        
        return action

    def send_feedback(self, feedback: dict[str, float]) -> None:
        """
        发送反馈到遥操作器。
        
        Piper 暂不支持力反馈，此方法为空实现。
        """
        logger.debug("Piper Leader does not support feedback")

    @check_if_not_connected
    def disconnect(self) -> None:
        """断开连接。"""
        logger.info(f"Disconnecting {self}...")
        
        # Leader 断开前确保电机禁用（安全）
        self.piper.DisablePiper()
        self.piper.DisconnectPort()
        
        logger.info(f"{self} disconnected")
```

---

## 5. 注册到工厂函数

### 5.1 机器人工厂

**文件**: `src/lerobot/robots/utils.py`

```python
def make_robot_from_config(config: RobotConfig) -> Robot:
    # ... 其他机器人分支 ...
    
    elif config.type == "piper_follower":
        from .piper_follower import PiperFollower
        return PiperFollower(config)
    
    # ... 其他分支 ...
```

### 5.2 遥操作器工厂

**文件**: `src/lerobot/teleoperators/utils.py`

```python
def make_teleoperator_from_config(config: TeleoperatorConfig) -> "Teleoperator":
    # ... 其他遥操作器分支 ...
    
    elif config.type == "piper_leader":
        from .piper_leader import PiperLeader
        return PiperLeader(config)
    
    # ... 其他分支 ...
```

---

## 6. 使用示例

### 6.1 单臂控制

```python
from lerobot.robots import make_robot_from_config
from lerobot.robots.piper_follower import PiperFollowerConfig

# 创建配置
config = PiperFollowerConfig(
    can_port="can0",
    speed_rate=100,
    cameras={
        "cam_high": OpenCVCameraConfig(
            index_or_path=0,
            fps=30,
            width=640,
            height=480
        )
    }
)

# 创建并连接
robot = make_robot_from_config(config)

with robot:
    # 获取当前观测
    obs = robot.get_observation()
    print(f"Current joints: {[obs[f'joint_{i}.pos'] for i in range(1, 7)]}")
    
    # 发送动作（运动到零点）
    action = {f"joint_{i}.pos": 0.0 for i in range(1, 7)}
    action["gripper.pos"] = 0.05  # 5cm
    robot.send_action(action)
    
    time.sleep(2.0)
```

### 6.2 主从遥操作

```python
from lerobot.robots import make_robot_from_config
from lerobot.teleoperators import make_teleoperator_from_config
from lerobot.robots.piper_follower import PiperFollowerConfig
from lerobot.teleoperators.piper_leader import PiperLeaderConfig

# 创建 Leader（主臂）和 Follower（从臂）
leader_config = PiperLeaderConfig(
    can_port="can0",      # 连接主臂的 CAN
    manual_control=True   # 手动拖动模式
)

follower_config = PiperFollowerConfig(
    can_port="can1",      # 连接从臂的 CAN
    speed_rate=100
)

leader = make_teleoperator_from_config(leader_config)
follower = make_robot_from_config(follower_config)

# 启动遥操作
with leader, follower:
    print("Teleoperation started. Move the leader arm to control follower.")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            # 1. 读取主臂位置
            action = leader.get_action()
            
            # 2. 发送给从臂执行
            follower.send_action(action)
            
            # 3. 控制频率
            time.sleep(0.005)  # 200Hz
            
    except KeyboardInterrupt:
        print("\nTeleoperation stopped")
```

### 6.3 使用 CLI 采集数据

```bash
# 使用 Piper 机械臂采集数据
lerobot-record \
  --robot.type=piper_follower \
  --robot.can_port=can0 \
  --robot.cameras.cam_high.type=opencv \
  --robot.cameras.cam_high.index_or_path=0 \
  --robot.cameras.cam_high.fps=30 \
  --teleoperator.type=piper_leader \
  --teleoperator.can_port=can1 \
  --dataset.repo_id=your_username/piper_demo \
  --dataset.num_episodes=10

# 训练策略
lerobot-train \
  --policy.type=act \
  --dataset.repo_id=your_username/piper_demo

# 部署推理
lerobot-teleoperate \
  --robot.type=piper_follower \
  --robot.can_port=can0 \
  --policy.path=path/to/checkpoint
```

---

## 7. 配置文件示例

### 7.1 YAML 配置

```yaml
# piper_config.yaml
robot:
  type: piper_follower
  can_port: can0
  speed_rate: 100
  control_period: 0.005
  auto_enable: true
  cameras:
    cam_high:
      type: opencv
      index_or_path: 0
      fps: 30
      width: 640
      height: 480

teleoperator:
  type: piper_leader
  can_port: can1
  manual_control: true
```

### 7.2 Python 配置

```python
from lerobot.robots.piper_follower import PiperFollowerConfig
from lerobot.teleoperators.piper_leader import PiperLeaderConfig
from lerobot.cameras.opencv import OpenCVCameraConfig

# Follower 配置
follower_config = PiperFollowerConfig(
    can_port="can0",
    speed_rate=100,
    joint_limits={
        "joint_1": (-2.967, 2.967),
        "joint_2": (-2.967, 2.967),
        "joint_3": (-2.967, 2.967),
        "joint_4": (-2.967, 2.967),
        "joint_5": (-2.967, 2.967),
        "joint_6": (-2.967, 2.967),
        "gripper": (0.0, 0.1),
    },
    cameras={
        "cam_high": OpenCVCameraConfig(
            index_or_path=0,
            fps=30,
            width=640,
            height=480
        )
    }
)

# Leader 配置
leader_config = PiperLeaderConfig(
    can_port="can1",
    manual_control=True
)
```

---

## 8. CAN 配置脚本

在使用 Piper 机械臂之前，必须先配置和激活 CAN 总线。以下是两个辅助脚本：

### 8.1 脚本说明

| 脚本 | 作用 | 使用时机 |
|------|------|----------|
| `find_all_can_port.sh` | 发现系统中的 CAN 接口及其 USB 端口地址 | 首次配置或更换 USB 端口时 |
| `can_config.sh` | 激活 CAN 接口、设置波特率、重命名接口 | 每次系统重启后 |

### 8.2 find_all_can_port.sh

**文件**: `lerobot052piper/find_all_can_port.sh`

**作用**：检测系统中所有 CAN 接口，显示接口名称、USB 端口地址和激活状态。

```bash
#!/bin/sh
# 检查系统是否安装了 can-utils。
if ! dpkg -l | grep -q "can-utils"; then
    echo "错误: 系统未检测到 can-utils."
    echo "请使用以下命令安装 can-utils:"
    echo "sudo apt update && sudo apt install can-utils"
    exit 1
fi

# 获取所有 CAN 接口的名称。
can_interfaces=$(ip -br link show type can | awk '{print $1}')

# 如果没有找到任何 CAN 接口，输出提示信息。
if [ -z "$can_interfaces" ]; then
    echo "提示: 系统中未找到任何 CAN 接口."
    exit 0
fi

# 遍历所有 CAN 接口。
for iface in $can_interfaces; do
    # 使用 ethtool 获取 bus-info（端口号）。
    BUS_INFO=$(ethtool -i "$iface" | grep "bus-info" | awk '{print $2}')
    
    # 如果 bus-info 为空，则输出错误。
    if [ -z "$BUS_INFO" ]; then
        echo "错误: 无法获取接口 $iface 的 bus-info."
        continue
    fi

    # 检查接口是否已激活。
    IS_LINK_UP=$(ip link show "$iface" | grep -q "UP" && echo "True" || echo "False")

    # 输出接口信息。
    echo "接口名称: $iface"
    echo "端口号: $BUS_INFO"
    echo "是否已激活: $IS_LINK_UP"
done
```

**使用示例**：
```bash
bash find_all_can_port.sh

# 输出示例：
# 接口名称: can0
# 端口号: 1-3.1:1.0
# 是否已激活: False
```

### 8.3 can_config.sh

**文件**: `lerobot052piper/can_config.sh`

**作用**：自动配置和激活 CAN 接口，支持单模块和多模块模式，可根据 USB 端口地址重命名接口。

```bash
#!/bin/bash

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then 
    echo "错误：此脚本需要 root 权限才能运行。"
    echo "请尝试以下方式运行："
    echo "  1. sudo bash can_config.sh"
    echo "  2. su -c 'bash can_config.sh'"
    exit 1
fi

# 预定义的 CAN 模块数量（根据实际需求修改）
EXPECTED_CAN_COUNT=2

# 单个 CAN 模块时的默认参数
if [ "$EXPECTED_CAN_COUNT" -eq 1 ]; then
    DEFAULT_CAN_NAME="${1:-can0}"
    DEFAULT_BITRATE="${2:-1000000}"
    USB_ADDRESS="${3}"
fi

# 多个 CAN 模块时的 USB 端口映射（根据实际硬件修改）
if [ "$EXPECTED_CAN_COUNT" -ne 1 ]; then
    declare -A USB_PORTS 
    USB_PORTS["1-3.1:1.0"]="can_follower:1000000"   # Follower 机械臂
    USB_PORTS["1-3.2:1.0"]="can_leader:1000000"     # Leader 遥操作器
fi

# 获取当前系统中的 CAN 模块数量
CURRENT_CAN_COUNT=$(ip link show type can | grep -c "link/can")

# 检查当前系统中的 CAN 模块数量是否符合预期
if [ "$CURRENT_CAN_COUNT" -ne "$EXPECTED_CAN_COUNT" ]; then
    echo "错误: 检测到的 CAN 模块数量 ($CURRENT_CAN_COUNT) 与预期数量 ($EXPECTED_CAN_COUNT) 不符。"
    exit 1
fi

# 加载 gs_usb 模块
modprobe gs_usb
if [ $? -ne 0 ]; then
    echo "错误: 无法加载 gs_usb 模块。"
    exit 1
fi

# 判断是否只需要处理一个 CAN 模块
if [ "$EXPECTED_CAN_COUNT" -eq 1 ]; then
    if [ -n "$USB_ADDRESS" ]; then
        # 使用指定的 USB 地址查找对应的 CAN 接口
        INTERFACE_NAME=""
        for iface in $(ip -br link show type can | awk '{print $1}'); do
            BUS_INFO=$(sudo ethtool -i "$iface" | grep "bus-info" | awk '{print $2}')
            if [ "$BUS_INFO" = "$USB_ADDRESS" ]; then
                INTERFACE_NAME="$iface"
                break
            fi
        done
        
        if [ -z "$INTERFACE_NAME" ]; then
            echo "错误: 无法找到与 USB 硬件地址 $USB_ADDRESS 对应的 CAN 接口。"
            exit 1
        fi
    else
        # 获取唯一的 CAN 接口
        INTERFACE_NAME=$(ip -br link show type can | awk '{print $1}')
    fi

    # 设置接口比特率并激活
    ip link set "$INTERFACE_NAME" down
    ip link set "$INTERFACE_NAME" type can bitrate $DEFAULT_BITRATE
    ip link set "$INTERFACE_NAME" up
    
    # 重命名接口为默认名称
    if [ "$INTERFACE_NAME" != "$DEFAULT_CAN_NAME" ]; then
        ip link set "$INTERFACE_NAME" down
        ip link set "$INTERFACE_NAME" name "$DEFAULT_CAN_NAME"
        ip link set "$DEFAULT_CAN_NAME" up
    fi
    
    echo "接口 $DEFAULT_CAN_NAME 已配置完成，比特率 $DEFAULT_BITRATE"
else
    # 处理多个 CAN 模块
    for iface in $(ip -br link show type can | awk '{print $1}'); do
        BUS_INFO=$(ethtool -i "$iface" | grep "bus-info" | awk '{print $2}')
        
        if [ -n "${USB_PORTS[$BUS_INFO]}" ]; then
            IFS=':' read -r TARGET_NAME TARGET_BITRATE <<< "${USB_PORTS[$BUS_INFO]}"
            
            # 设置接口比特率并激活
            ip link set "$iface" down
            ip link set "$iface" type can bitrate $TARGET_BITRATE
            ip link set "$iface" up
            
            # 重命名接口为目标名称
            if [ "$iface" != "$TARGET_NAME" ]; then
                ip link set "$iface" down
                ip link set "$iface" name "$TARGET_NAME"
                ip link set "$TARGET_NAME" up
            fi
            
            echo "接口 $TARGET_NAME (USB: $BUS_INFO) 已配置完成"
        else
            echo "错误: 未知的 USB 端口 $BUS_INFO 对应接口 $iface。"
            exit 1
        fi
    done
fi

echo "所有 CAN 接口已成功配置并激活。"
```

### 8.4 使用步骤

#### 步骤 1：获取 USB 端口地址

```bash
# 先插入一个 CAN 模块
bash find_all_can_port.sh

# 记录输出中的端口号，如：1-3.1:1.0
# 再插入第二个 CAN 模块，重复上述步骤
```

#### 步骤 2：修改 can_config.sh

根据实际硬件配置修改脚本中的关键参数：

```bash
# 如果是单机械臂
EXPECTED_CAN_COUNT=1

# 如果是主从双机械臂
EXPECTED_CAN_COUNT=2
declare -A USB_PORTS 
USB_PORTS["你的USB地址1"]="can_follower:1000000"
USB_PORTS["你的USB地址2"]="can_leader:1000000"
```

#### 步骤 3：运行配置脚本

```bash
# 单模块模式
sudo bash can_config.sh can0 1000000

# 或多模块模式
sudo bash can_config.sh
```

#### 步骤 4：验证配置

```bash
ifconfig
# 应看到 can_follower 和 can_leader 接口
```

### 8.5 与 LeRobot 的集成

**配置对应关系**：

| 脚本配置 | LeRobot 配置 | 说明 |
|----------|-------------|------|
| `USB_PORTS["1-3.1:1.0"]="can_follower:1000000"` | `can_port="can_follower"` | 名称必须一致 |
| `USB_PORTS["1-3.2:1.0"]="can_leader:1000000"` | `can_port="can_leader"` | 名称必须一致 |

**完整工作流**：

```
1. 插入 USB-CAN 适配器
         ↓
2. bash find_all_can_port.sh  (获取 USB 地址)
         ↓
3. 修改 can_config.sh 中的 USB_PORTS
         ↓
4. sudo bash can_config.sh  (激活 CAN)
         ↓
5. LeRobot 配置 can_port 与脚本名称一致
         ↓
6. 运行 lerobot-record / lerobot-train
```

### 8.6 注意事项

1. **名称必须匹配**：脚本中的接口名称必须与 LeRobot 配置中的 `can_port` 完全一致
2. **重启后需重新运行**：`can_config.sh` 的配置不持久，系统重启后需要重新执行
3. **root 权限**：配置脚本必须使用 `sudo` 运行
4. **波特率固定**：Piper 机械臂使用 1Mbps (1000000)，不可更改

### 8.7 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `CAN socket does not exist` | CAN 未激活 | 先运行 `can_config.sh` |
| `无法加载 gs_usb 模块` | 驱动未安装 | `sudo apt install linux-modules-extra-$(uname -r)` |
| `检测到的 CAN 模块数量不符` | USB 未识别 | 检查 USB 连接，重新插拔 |
| `未知的 USB 端口` | USB_PORTS 配置错误 | 使用 `find_all_can_port.sh` 获取正确地址 |
| 配置后接口名不对 | 名称不匹配 | 检查 LeRobot 配置中的 `can_port` |

---

## 9. 故障排除

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `Piper SDK not installed` | 未安装 piper_sdk | `pip install piper_sdk` |
| `CAN socket does not exist` | CAN 未激活 | 运行 `can_activate.sh can0 1000000` |
| `Failed to enable motors` | 机械臂未上电或故障 | 检查电源，重启机械臂 |
| 动作不执行 | 电机未使能 | 检查 `auto_enable=True` 或手动调用 `EnablePiper()` |
| 读取数据为 0 | 机械臂在待机模式 | 确保机械臂已使能 |
| 关节角度跳动 | CAN 通信不稳定 | 检查 CAN 线连接，降低控制频率 |

### 8.2 调试技巧

```python
import logging

# 启用 DEBUG 日志
logging.basicConfig(level=logging.DEBUG)

# 检查机械臂状态
from piper_sdk import C_PiperInterface_V2

piper = C_PiperInterface_V2("can0")
piper.ConnectPort()

# 读取状态
status = piper.GetArmStatus()
print(f"Control mode: {status.arm_status.ctrl_mode}")  # 应为 0x01 (CAN 控制)
print(f"Arm status: {status.arm_status.arm_status}")   # 应为 0x00 (正常)

# 检查 CAN 帧率
fps = piper.GetCanFps()
print(f"CAN FPS: {fps}")  # 正常应在 200Hz 左右
```

### 8.3 单位转换参考

| 物理量 | Piper SDK 单位 | LeRobot 单位 | 转换公式 |
|--------|---------------|--------------|----------|
| 关节角度 | 0.001 度 (int) | 弧度 (float) | `rad = sdk / 1000 * π/180` |
| 夹爪位置 | 0.001 mm (int) | 米 (float) | `m = sdk / 1000000` |
| 末端位置 | 0.001 mm (int) | 米 (float) | `m = sdk / 1000000` |
| 末端姿态 | 0.001 度 (int) | 弧度 (float) | `rad = sdk / 1000 * π/180` |

---

## 10. 参考资源

- **Piper SDK 文档**: `docs/piper_sdk.md`
- **LeRobot 注册指南**: `docs/regist_robot.md`
- **Piper SDK GitHub**: <https://github.com/agilexrobotics/piper_sdk>
- **松灵官方文档**: `asserts/V2/INTERFACE_V2.MD`
- **LeRobot 官方文档**: <https://huggingface.co/docs/lerobot>
