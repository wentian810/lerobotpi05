# 松灵 Piper 机械臂 LeRobot 注册日志

> 本文档记录了将松灵 (AgileX) Piper 机械臂注册到 LeRobot 框架的完整过程，包括每个文件的修改内容、修改原因和关键决策。
>
> 注册日期：2026-04-17
>
> 目标项目：`lerobot052piper/`

---

## 1. 注册前状态分析

### 1.1 初始状态

`lerobot052piper/` 项目中的 `piper_follower/` 和 `piper_leader/` 目录已存在，但**文件内容完全是从 OpenArm 机械臂复制过来的占位代码**，尚未改写为 Piper 实现：

| 文件 | 初始状态 | 问题 |
|------|---------|------|
| `piper_follower/config_piper_follower.py` | OpenArm 配置（Damiao 电机） | 类名为 `OpenArmFollowerConfig`，注册名为 `"openarm_follower"` |
| `piper_follower/piper_follower.py` | OpenArm 实现（DamiaoMotorsBus） | 类名为 `OpenArmFollower`，使用 Damiao 电机总线 |
| `piper_follower/__init__.py` | 导出 OpenArm 类 | `from .config_openarm_follower import ...` |
| `piper_leader/config_piper_leader.py` | OpenArm Leader 配置 | 类名为 `OpenArmLeaderConfig`，注册名为 `"openarm_leader"` |
| `piper_leader/piper_leader.py` | OpenArm Leader 实现 | 类名为 `OpenArmLeader`，使用 DamiaoMotorsBus |
| `piper_leader/__init__.py` | 导出 OpenArm 类 | `from .config_openarm_leader import ...` |
| `robots/utils.py` | 无 piper 分支 | 工厂函数中缺少 `piper_follower` 类型 |
| `teleoperators/utils.py` | 无 piper 分支 | 工厂函数中缺少 `piper_leader` 类型 |

### 1.2 Piper 与 OpenArm 的关键差异

| 特性 | OpenArm（原代码） | Piper（目标） |
|------|-------------------|---------------|
| 电机类型 | Damiao (DM8009, DM4340, DM4310) | Piper 内置电机（通过 SDK 控制） |
| 通信方式 | CAN FD + DamiaoMotorsBus | CAN + piper_sdk.C_PiperInterface_V2 |
| 自由度 | 7DOF + 1 夹爪 | 6DOF + 1 夹爪 |
| 角度单位 | 度（通过 MotorNormMode.DEGREES） | 0.001 度（SDK 内部单位），需转弧度 |
| 夹爪单位 | 度 | 0.001 mm（SDK 内部单位），需转米 |
| 标定 | 需要 LeRobot 式标定（MotorCalibration） | 无需标定（SDK 内部处理） |
| 电机使能 | 通过 bus.enable_torque() | 通过 piper.EnablePiper() |
| 控制模式 | MIT 控制（kp/kd 参数） | MOVE J（关节空间运动） |

### 1.3 设计决策

基于以上差异，做出以下关键设计决策：

1. **不使用 LeRobot 的 MotorsBus 抽象**：Piper SDK 提供了完整的控制栈，直接封装 `C_PiperInterface_V2`
2. **跳过标定流程**：`is_calibrated` 始终返回 `True`，`calibrate()` 为空操作
3. **单位统一为 SI 制**：关节角度使用弧度，夹爪位置使用米
4. **使用 `_connected` 标志**：由于 Piper SDK 的 `get_connect_status()` 行为可能不一致，增加内部连接状态跟踪

---

## 2. 修改文件清单

共修改 **13 个文件**：

```
src/lerobot/
├── robots/
│   ├── piper_follower/
│   │   ├── __init__.py                    ← [修改] 更新导出
│   │   ├── config_piper_follower.py       ← [重写] OpenArm → Piper 配置
│   │   └── piper_follower.py              ← [重写] OpenArm → Piper 实现
│   └── utils.py                            ← [修改] 添加工厂分支
│
├── teleoperators/
│   ├── piper_leader/
│   │   ├── __init__.py                    ← [修改] 更新导出
│   │   ├── config_piper_leader.py         ← [重写] OpenArm → Piper 配置
│   │   └── piper_leader.py                ← [重写] OpenArm → Piper 实现
│   └── utils.py                            ← [修改] 添加工厂分支
│
└── scripts/
    ├── lerobot_teleoperate.py             ← [修改] 添加 piper 导入（触发注册）
    ├── lerobot_record.py                  ← [修改] 添加 piper 导入（触发注册）
    ├── lerobot_replay.py                  ← [修改] 添加 piper 导入（触发注册）
    ├── lerobot_calibrate.py               ← [修改] 添加 piper 导入（触发注册）
    └── lerobot_find_joint_limits.py       ← [修改] 添加 piper 导入（触发注册）
```

---

## 3. 详细修改记录

### 3.1 Piper Follower 配置类

**文件**: `src/lerobot/robots/piper_follower/config_piper_follower.py`

**修改类型**: 完全重写

**修改前**（OpenArm 配置）:
- 类名: `OpenArmFollowerConfigBase` / `OpenArmFollowerConfig`
- 注册名: `"openarm_follower"`
- 使用 Damiao 电机配置 (`motor_config` 含 send_id, recv_id, motor_type)
- 包含 CAN FD 参数 (`use_can_fd`, `can_data_bitrate`)
- 包含 MIT 控制参数 (`position_kp`, `position_kd`)
- 包含左右臂限位 (`LEFT_DEFAULT_JOINTS_LIMITS`, `RIGHT_DEFAULT_JOINTS_LIMITS`)
- 7DOF + 1 夹爪

**修改后**（Piper 配置）:
- 类名: `PiperFollowerConfigBase` / `PiperFollowerConfig`
- 注册名: `"piper_follower"`
- 使用 CAN 端口名 (`can_port`) 替代 Damiao 的 `port` + `motor_config`
- 移除所有 Damiao 特有参数（CAN FD、MIT 控制、左右臂）
- 新增 Piper 特有参数: `speed_rate`, `control_period`, `auto_enable`
- 关节限位使用弧度（6DOF + 1 夹爪）
- 夹爪限位使用米（0-0.1m）

**关键代码**:
```python
@dataclass
class PiperFollowerConfigBase:
    can_port: str = "can0"           # CAN 端口名称
    speed_rate: int = 100            # 运动速度百分比
    control_period: float = 0.005    # 控制周期（200Hz）
    auto_enable: bool = True         # 自动使能电机
    joint_limits: dict[str, tuple[float, float]] = field(...)  # 弧度限位
    cameras: dict[str, CameraConfig] = field(default_factory=dict)

@RobotConfig.register_subclass("piper_follower")  # ← 注册名
@dataclass
class PiperFollowerConfig(RobotConfig, PiperFollowerConfigBase):
    pass
```

---

### 3.2 Piper Follower 机器人类

**文件**: `src/lerobot/robots/piper_follower/piper_follower.py`

**修改类型**: 完全重写

**修改前**（OpenArm 实现）:
- 类名: `OpenArmFollower`
- 使用 `DamiaoMotorsBus` 进行电机通信
- 使用 `Motor`, `MotorCalibration`, `MotorNormMode` 等 LeRobot 电机抽象
- 通过 `bus.sync_read_all_states()` 读取状态
- 通过 `bus._mit_control_batch()` 发送控制
- 需要标定流程（`calibrate()` 含用户交互）
- 7DOF + 1 夹爪

**修改后**（Piper 实现）:
- 类名: `PiperFollower`
- 使用 `piper_sdk.C_PiperInterface_V2` 直接通信
- 不依赖 LeRobot 的 MotorsBus 抽象
- 通过 `piper.GetArmJointMsgs()` / `piper.GetArmGripperMsgs()` 读取状态
- 通过 `piper.JointCtrl()` / `piper.GripperCtrl()` 发送控制
- 无需标定（`is_calibrated` 返回 `True`）
- 6DOF + 1 夹爪

**关键修改点**:

#### a) 导入变更
```python
# 移除
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.damiao import DamiaoMotorsBus
from ..utils import ensure_safe_goal_position

# 新增
from piper_sdk import C_PiperInterface_V2, LogLevel
import math
```

#### b) 单位转换常量
```python
RAD_TO_DEG = 180.0 / math.pi
DEG_TO_RAD = math.pi / 180.0
PIPER_ANGLE_FACTOR = 1000.0 * 180.0 / math.pi  # 57295.7795
```

#### c) 初始化 (`__init__`)
```python
# 移除: DamiaoMotorsBus 创建、Motor 对象创建、CAN FD 配置
# 新增: C_PiperInterface_V2 初始化
self.piper = C_PiperInterface_V2(
    can_name=config.can_port,
    judge_flag=False,        # 非官方 CAN 模块
    can_auto_init=True,
    logger_level=LogLevel.WARNING,
)
```

#### d) 连接 (`connect`)
```python
# 移除: bus.connect(), bus.enable_torque(), calibration 检查
# 新增: piper.ConnectPort(), piper.EnablePiper() (带超时)
self.piper.ConnectPort()
while not self.piper.EnablePiper():
    if time.time() - start_time > timeout:
        raise RuntimeError("Failed to enable Piper motors within timeout")
    time.sleep(0.01)
```

#### e) 观测 (`get_observation`)
```python
# 移除: bus.sync_read_all_states() → pos/vel/torque
# 新增: piper.GetArmJointMsgs() → 6 个关节角度（0.001度→弧度）
#       piper.GetArmGripperMsgs() → 夹爪位置（0.001度→米）
joint_msgs = self.piper.GetArmJointMsgs()
joint_positions = [
    joint_msgs.joint_state.joint_1 / 1000.0 * DEG_TO_RAD,
    # ... joint_2 到 joint_6
]
```

#### f) 动作 (`send_action`)
```python
# 移除: MIT 控制 (kp/kd)、bus._mit_control_batch()
# 新增: MotionCtrl_2 + JointCtrl + GripperCtrl
self.piper.MotionCtrl_2(ctrl_mode=0x01, move_mode=0x01, speed_rate=..., delay=0x00)
self.piper.JointCtrl(*joint_targets)  # SDK 单位: 0.001 度
self.piper.GripperCtrl(gripper_pos=..., gripper_force=1000, gripper_code=0x01, delay=0)
```

#### g) 断开 (`disconnect`)
```python
# 移除: bus.disconnect(disable_torque_on_disconnect)
# 新增: piper.DisablePiper() + piper.DisconnectPort()
```

---

### 3.3 Piper Leader 配置类

**文件**: `src/lerobot/teleoperators/piper_leader/config_piper_leader.py`

**修改类型**: 完全重写

**修改前**（OpenArm Leader 配置）:
- 类名: `OpenArmLeaderConfigBase` / `OpenArmLeaderConfig`
- 注册名: `"openarm_leader"`
- 包含 Damiao 电机配置、CAN FD 参数、MIT 控制参数

**修改后**（Piper Leader 配置）:
- 类名: `PiperLeaderConfigBase` / `PiperLeaderConfig`
- 注册名: `"piper_leader"`
- 仅包含: `can_port`, `control_period`, `manual_control`

**关键代码**:
```python
@dataclass
class PiperLeaderConfigBase:
    can_port: str = "can0"
    control_period: float = 0.005
    manual_control: bool = True      # 禁用扭矩，手动拖动

@TeleoperatorConfig.register_subclass("piper_leader")
@dataclass
class PiperLeaderConfig(TeleoperatorConfig, PiperLeaderConfigBase):
    pass
```

---

### 3.4 Piper Leader 遥操作类

**文件**: `src/lerobot/teleoperators/piper_leader/piper_leader.py`

**修改类型**: 完全重写

**修改前**（OpenArm Leader 实现）:
- 类名: `OpenArmLeader`
- 使用 `DamiaoMotorsBus`
- 通过 `bus.sync_read_all_states()` 读取 pos/vel/torque
- 需要标定流程

**修改后**（Piper Leader 实现）:
- 类名: `PiperLeader`
- 使用 `C_PiperInterface_V2`
- 通过 `piper.GetArmJointMsgs()` + `piper.GetArmGripperMsgs()` 读取
- 无需标定

**关键修改点**:

#### a) 连接 (`connect`)
```python
# Leader 连接后禁用电机，允许手动拖动
self.piper.ConnectPort()
if self.config.manual_control:
    self.piper.DisablePiper()  # 禁用扭矩
```

#### b) 获取动作 (`get_action`)
```python
# 读取 6 个关节角度 + 夹爪位置
joint_msgs = self.piper.GetArmJointMsgs()
action[f"{joint_name}.pos"] = joint_msgs.joint_state.joint_X / 1000.0 * DEG_TO_RAD
gripper_msgs = self.piper.GetArmGripperMsgs()
action["gripper.pos"] = gripper_msgs.gripper_state.grippers_angle / (1000.0 * 1000.0)
```

#### c) 反馈 (`send_feedback`)
```python
# Piper 不支持力反馈，空实现（不抛异常）
logger.debug("Piper Leader does not support feedback")
```

---

### 3.5 `__init__.py` 文件

**文件**: `src/lerobot/robots/piper_follower/__init__.py`

**修改内容**:
```python
# 修改前
from .config_openarm_follower import OpenArmFollowerConfig, OpenArmFollowerConfigBase
from .openarm_follower import OpenArmFollower
__all__ = ["OpenArmFollower", "OpenArmFollowerConfig", "OpenArmFollowerConfigBase"]

# 修改后
from .config_piper_follower import PiperFollowerConfig, PiperFollowerConfigBase
from .piper_follower import PiperFollower
__all__ = ["PiperFollower", "PiperFollowerConfig", "PiperFollowerConfigBase"]
```

**文件**: `src/lerobot/teleoperators/piper_leader/__init__.py`

**修改内容**:
```python
# 修改前
from .config_openarm_leader import OpenArmLeaderConfig, OpenArmLeaderConfigBase
from .openarm_leader import OpenArmLeader
__all__ = ["OpenArmLeader", "OpenArmLeaderConfig", "OpenArmLeaderConfigBase"]

# 修改后
from .config_piper_leader import PiperLeaderConfig, PiperLeaderConfigBase
from .piper_leader import PiperLeader
__all__ = ["PiperLeader", "PiperLeaderConfig", "PiperLeaderConfigBase"]
```

---

### 3.6 工厂函数注册

**文件**: `src/lerobot/robots/utils.py`

在 `make_robot_from_config()` 函数中，在 `bi_openarm_follower` 分支之后、`mock_robot` 分支之前添加：

```python
elif config.type == "piper_follower":
    from .piper_follower import PiperFollower
    return PiperFollower(config)
```

**文件**: `src/lerobot/teleoperators/utils.py`

在 `make_teleoperator_from_config()` 函数中，在 `openarm_mini` 分支之后、`else` 分支之前添加：

```python
elif config.type == "piper_leader":
    from .piper_leader import PiperLeader
    return PiperLeader(config)
```

---

## 4. 单位转换说明

### 4.1 关节角度转换

```
Piper SDK 单位 (int)  ←→  LeRobot 单位 (float, 弧度)

SDK → 弧度:  rad = sdk_value / 1000.0 * (π / 180.0)
弧度 → SDK:  sdk_value = int(round(rad * (180.0 / π) * 1000.0))

示例: SDK 值 90000 → 90° → 1.5708 rad
```

### 4.2 夹爪位置转换

```
Piper SDK 单位 (int, 0.001mm)  ←→  LeRobot 单位 (float, 米)

SDK → 米:  m = sdk_value / 1000000.0
米 → SDK:  sdk_value = int(m * 1000.0 * 1000.0)

示例: SDK 值 50000 → 50mm → 0.05m
范围: 0 (闭合) ~ 1000000 (100mm 张开)
```

---

## 5. 注册架构图

```
LeRobot Framework (lerobot052piper)
│
├── 配置层 (draccus.ChoiceRegistry)
│   ├── RobotConfig
│   │   └── @register_subclass("piper_follower")
│   │       └── PiperFollowerConfig
│   │           ├── can_port: str = "can0"
│   │           ├── speed_rate: int = 100
│   │           ├── auto_enable: bool = True
│   │           ├── joint_limits: dict (弧度)
│   │           └── cameras: dict[str, CameraConfig]
│   │
│   └── TeleoperatorConfig
│       └── @register_subclass("piper_leader")
│           └── PiperLeaderConfig
│               ├── can_port: str = "can0"
│               ├── control_period: float = 0.005
│               └── manual_control: bool = True
│
├── 工厂层 (utils.py)
│   ├── make_robot_from_config()
│   │   └── elif config.type == "piper_follower":
│   │       from .piper_follower import PiperFollower
│   │
│   └── make_teleoperator_from_config()
│       └── elif config.type == "piper_leader":
│           from .piper_leader import PiperLeader
│
├── 实现层
│   ├── PiperFollower(Robot)
│   │   ├── config_class = PiperFollowerConfig
│   │   ├── name = "piper_follower"
│   │   ├── piper = C_PiperInterface_V2(...)
│   │   ├── connect() → ConnectPort + EnablePiper
│   │   ├── get_observation() → GetArmJointMsgs + GetArmGripperMsgs + cameras
│   │   ├── send_action() → MotionCtrl_2 + JointCtrl + GripperCtrl
│   │   └── disconnect() → DisablePiper + DisconnectPort
│   │
│   └── PiperLeader(Teleoperator)
│       ├── config_class = PiperLeaderConfig
│       ├── name = "piper_leader"
│       ├── piper = C_PiperInterface_V2(...)
│       ├── connect() → ConnectPort + DisablePiper
│       ├── get_action() → GetArmJointMsgs + GetArmGripperMsgs
│       └── disconnect() → DisablePiper + DisconnectPort
│
└── Piper SDK Layer
    └── C_PiperInterface_V2
        ├── ConnectPort() / DisconnectPort()
        ├── EnablePiper() / DisablePiper()
        ├── MotionCtrl_2(ctrl_mode, move_mode, speed_rate, delay)
        ├── JointCtrl(j1, j2, j3, j4, j5, j6)
        ├── GripperCtrl(pos, force, code, delay)
        ├── GetArmJointMsgs() → joint_state.joint_1~6
        └── GetArmGripperMsgs() → gripper_state.grippers_angle
```

---

## 6. 使用方法

### 6.1 前置条件

```bash
# 1. 安装 Piper SDK
pip install piper_sdk

# 2. 配置 CAN 总线
# 查找 CAN 端口
bash find_all_can_port.sh

# 修改 can_config.sh 中的 USB_PORTS 映射
# 然后激活 CAN
sudo bash can_config.sh
```

### 6.2 Python 使用

```python
from lerobot.robots import make_robot_from_config
from lerobot.teleoperators import make_teleoperator_from_config
from lerobot.robots.piper_follower import PiperFollowerConfig
from lerobot.teleoperators.piper_leader import PiperLeaderConfig

# 创建配置
follower_config = PiperFollowerConfig(can_port="can_follower")
leader_config = PiperLeaderConfig(can_port="can_leader", manual_control=True)

# 创建实例
follower = make_robot_from_config(follower_config)
leader = make_teleoperator_from_config(leader_config)

# 遥操作循环
with leader, follower:
    while True:
        action = leader.get_action()
        follower.send_action(action)
        time.sleep(0.005)  # 200Hz
```

### 6.3 CLI 使用

```bash
# 采集数据
lerobot-record \
  --robot.type=piper_follower \
  --robot.can_port=can_follower \
  --teleoperator.type=piper_leader \
  --teleoperator.can_port=can_leader \
  --dataset.repo_id=your_username/piper_demo

# 训练策略
lerobot-train \
  --policy.type=act \
  --dataset.repo_id=your_username/piper_demo

# 部署推理
lerobot-teleoperate \
  --robot.type=piper_follower \
  --robot.can_port=can_follower
```

---

## 7. 验证清单

- [x] `config_piper_follower.py` — 配置类使用 `@RobotConfig.register_subclass("piper_follower")`
- [x] `piper_follower.py` — 机器人类设置 `config_class = PiperFollowerConfig`, `name = "piper_follower"`
- [x] `config_piper_leader.py` — 配置类使用 `@TeleoperatorConfig.register_subclass("piper_leader")`
- [x] `piper_leader.py` — 遥操作类设置 `config_class = PiperLeaderConfig`, `name = "piper_leader"`
- [x] `robots/utils.py` — 工厂函数包含 `elif config.type == "piper_follower"` 分支
- [x] `teleoperators/utils.py` — 工厂函数包含 `elif config.type == "piper_leader"` 分支
- [x] `piper_follower/__init__.py` — 正确导出 `PiperFollower`, `PiperFollowerConfig`
- [x] `piper_leader/__init__.py` — 正确导出 `PiperLeader`, `PiperLeaderConfig`
- [x] 所有文件无语法错误
- [x] 移除所有 OpenArm/Damiao 相关代码
- [x] 单位转换正确（弧度 ↔ 0.001度，米 ↔ 0.001mm）

---

## 8. 脚本导入注册（关键步骤）

### 8.1 问题说明

LeRobot 使用 `draccus.ChoiceRegistry` 管理配置类的注册。`@register_subclass("piper_follower")` 装饰器只有在**模块被导入时**才会执行注册。

LeRobot 的各个 CLI 脚本（`lerobot-teleoperate`、`lerobot-record` 等）通过**显式导入**各机器人模块来触发注册。如果不在脚本中导入 `piper_follower` / `piper_leader`，CLI 的 `--robot.type` 和 `--teleop.type` 参数将不会包含 piper 选项。

### 8.2 修改的脚本文件

在以下 5 个脚本的 `from lerobot.robots import` 中添加 `piper_follower`，在 `from lerobot.teleoperators import` 中添加 `piper_leader`：

| 脚本文件 | 用途 |
|----------|------|
| `scripts/lerobot_teleoperate.py` | 遥操作控制 |
| `scripts/lerobot_record.py` | 数据采集 |
| `scripts/lerobot_replay.py` | 数据回放 |
| `scripts/lerobot_calibrate.py` | 标定 |
| `scripts/lerobot_find_joint_limits.py` | 关节限位查找 |

### 8.3 修改示例

```python
from lerobot.robots import (  # noqa: F401
    # ...existing imports...
    openarm_follower,
    piper_follower,        # ← 新增
    reachy2,
    # ...
)
from lerobot.teleoperators import (  # noqa: F401
    # ...existing imports...
    openarm_mini,
    piper_leader,          # ← 新增
    reachy2_teleoperator,
    # ...
)
```

> **注意**：`# noqa: F401` 注释表示这些导入虽然在脚本中未直接使用，但它们的副作用（触发 `@register_subclass` 装饰器）是必需的。

---

## 9. 注意事项

### 9.1 CAN 端口名称必须匹配

`can_config.sh` 中配置的接口名称必须与 LeRobot 配置中的 `can_port` 完全一致：

```bash
# can_config.sh 中
USB_PORTS["1-3.1:1.0"]="can_follower:1000000"
USB_PORTS["1-3.2:1.0"]="can_leader:1000000"

# LeRobot 配置中
PiperFollowerConfig(can_port="can_follower")  # ← 必须一致
PiperLeaderConfig(can_port="can_leader")      # ← 必须一致
```

### 9.2 系统重启后需重新配置 CAN

CAN 接口配置不持久，每次系统重启后需要重新运行：

```bash
sudo bash can_config.sh
```

### 9.3 Piper SDK 单例模式

`C_PiperInterface_V2` 使用单例模式，相同 `can_name` 返回同一实例。因此 Leader 和 Follower **必须使用不同的 CAN 端口名称**。

### 9.4 `judge_flag=False` 的原因

设置 `judge_flag=False` 是因为非松灵官方 CAN 模块可能无法通过 SDK 的端口检查。如果使用官方 USB-CAN 适配器，可以设置为 `True`。

### 9.5 特征差异

| 特征 | Piper Follower | Piper Leader | OpenArm (参考) |
|------|---------------|-------------|----------------|
| `joint_X.pos` | ✅ (弧度) | ✅ (弧度) | ✅ (度) |
| `joint_X.vel` | ❌ | ❌ | ✅ |
| `joint_X.torque` | ❌ | ❌ | ✅ |
| `gripper.pos` | ✅ (米) | ✅ (米) | ✅ (度) |

Piper 当前实现仅返回位置信息。如需速度和力矩，可通过 `piper.GetArmMotorDriverInfoHighSpd()` 获取，但需要额外的 SDK 调用开销。

---

## 10. 后续优化建议

1. **添加速度/力矩反馈**：通过 `GetArmMotorDriverInfoHighSpd()` 获取电机速度和电流
2. **添加末端位姿观测**：通过 `GetArmEndPoseMsgs()` 获取笛卡尔空间位姿
3. **支持 MOVE L 模式**：在 `send_action` 中支持直线运动模式
4. **添加力反馈**：如果 Leader 支持力反馈设备，实现 `send_feedback()`
5. **持久化 CAN 配置**：通过 systemd 服务实现 CAN 接口自动配置
6. **添加状态监控**：利用 `GetArmStatus()` 监控机械臂状态（急停、无解等）
