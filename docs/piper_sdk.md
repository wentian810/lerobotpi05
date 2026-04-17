# 松灵 Piper 机械臂 SDK 技术文档

> 本文档详细介绍松灵 (AgileX) Piper 机械臂 Python SDK 的架构、API 和使用方法。
> 
> 适用版本：Piper SDK V2 (协议版本 V2)
> 
> 源码位置：`lerobot052base/piper_sdk/`

---

## 1. 概述

### 1.1 什么是 Piper SDK

Piper SDK 是松灵机器人 (AgileX Robotics) 为其 Piper 系列 6DOF+1 机械臂提供的官方 Python 开发工具包。该 SDK 通过 CAN 总线与机械臂通信，提供完整的运动控制、状态反馈和数据采集功能。

### 1.2 硬件要求

| 组件 | 要求 |
|------|------|
| 机械臂 | Piper 6DOF+1 机械臂（含夹爪） |
| 通信接口 | USB-CAN 适配器（官方推荐） |
| 操作系统 | Ubuntu 18.04/20.04/22.04 |
| Python | 3.6 / 3.8 / 3.10 |

### 1.3 主要功能

- **关节控制**：支持关节空间的位置控制
- **笛卡尔控制**：支持末端位姿控制（X, Y, Z, RX, RY, RZ）
- **夹爪控制**：独立控制夹爪开合
- **运动模式**：MOVE P/J/L/C/M 多种运动模式
- **状态反馈**：关节角度、末端位姿、电机状态、故障信息
- **正运动学**：内置 FK 计算
- **主从模式**：支持示教和主从跟随
- **MIT 控制**：支持关节级力控（高级功能）

---

## 2. 安装与环境配置

### 2.1 安装依赖

```bash
# 安装 python-can (必须 >= 3.3.4)
pip3 install python-can

# 安装 CAN 工具
sudo apt update
sudo apt install can-utils ethtool iproute2
```

### 2.2 安装 SDK

**方法 1：通过 PyPI 安装**

```bash
pip3 install piper_sdk
```

**方法 2：从源码安装**

```bash
git clone https://github.com/agilexrobotics/piper_sdk.git
cd piper_sdk
pip3 install .
```

**方法 3：通过 whl 文件安装**

```bash
pip3 install piper_sdk-X.X.X-py3-none-any.whl
```

### 2.3 验证安装

```bash
pip3 show piper_sdk
```

---

## 3. CAN 总线配置

### 3.1 查找 CAN 模块

```bash
# 使用 SDK 提供的脚本
cd piper_sdk
bash find_all_can_port.sh
```

**正常输出示例：**
```
Both ethtool and can-utils are installed.
Interface can0 is connected to USB port 3-1.4:1.0
```

### 3.2 激活单个 CAN 模块

**场景 A：只有一个 CAN 模块**

```bash
bash can_activate.sh can0 1000000
```

**场景 B：多个 CAN 模块，指定其中一个**

```bash
# 1. 先查找目标 CAN 模块的 USB 端口
bash find_all_can_port.sh
# 记录输出，如：Interface can0 is connected to USB port 3-1.4:1.0

# 2. 激活指定端口的 CAN 设备
bash can_activate.sh can_piper 1000000 "3-1.4:1.0"
```

### 3.3 激活多个 CAN 模块

编辑 `can_muti_activate.sh` 文件：

```bash
# 修改 USB_PORTS 数组
USB_PORTS["3-1.4:1.0"]="can_left:1000000"
USB_PORTS["3-1.1:1.0"]="can_right:1000000"
```

然后执行：

```bash
bash can_muti_activate.sh
```

验证激活状态：

```bash
ifconfig
# 应看到 can0 或 can_piper 接口
```

---

## 4. SDK 架构

### 4.1 架构层次

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│         C_PiperInterface_V2 (主接口类)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  - 连接管理 (ConnectPort/DisconnectPort)             │   │
│  │  - 运动控制 (JointCtrl/EndPoseCtrl)                  │   │
│  │  - 状态获取 (GetArmStatus/GetArmJointMsgs)           │   │
│  │  - 正运动学 (C_PiperForwardKinematics)               │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Protocol Layer                            │
│              C_PiperParserV2 (协议解析器)                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  - CAN 帧解码 (DecodeMessage)                        │   │
│  │  - CAN 帧编码 (EncodeMessage)                        │   │
│  │  - 消息类型映射 (ArmMessageMapping)                  │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Hardware Layer                            │
│                 C_STD_CAN (CAN 总线封装)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  - CAN 总线初始化/关闭 (Init/Close)                  │   │
│  │  - 消息收发 (SendCanMessage/ReadCanMessage)          │   │
│  │  - 状态检测 (is_can_bus_ok)                          │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    CAN Bus Hardware                          │
│              USB-CAN Adapter ←→ Piper Arm                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 关键类说明

| 类名 | 文件位置 | 职责 |
|------|---------|------|
| `C_PiperInterface_V2` | `interface/piper_interface_v2.py` | 主接口类，提供完整的机械臂控制 API |
| `C_PiperParserV2` | `protocol/protocol_v2/piper_protocol_v2.py` | 协议解析器，处理 CAN 帧编解码 |
| `C_STD_CAN` | `hardware_port/can_encapsulation.py` | CAN 总线底层封装 |
| `PiperMessage` | `piper_msgs/msg_v2/arm_messages.py` | 统一消息容器 |
| `C_PiperForwardKinematics` | `kinematics/piper_fk.py` | 正运动学计算 |

---

## 5. 核心接口：C_PiperInterface_V2

### 5.1 构造函数

```python
from piper_sdk import *

piper = C_PiperInterface_V2(
    can_name="can0",              # CAN 端口名称
    judge_flag=True,              # 是否检查 CAN 端口
    can_auto_init=True,           # 是否自动初始化 CAN
    dh_is_offset=0x01,            # DH 参数偏移 (0=旧版, 1=新版)
    start_sdk_joint_limit=False,  # 是否启用软件关节限位
    start_sdk_gripper_limit=False,# 是否启用软件夹爪限位
    logger_level=LogLevel.WARNING,# 日志级别
    log_to_file=False,            # 是否写入日志文件
    log_file_path=None            # 日志文件路径
)
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `can_name` | str | "can0" | CAN 端口名称 |
| `judge_flag` | bool | True | 实例化时是否检查 CAN 端口状态（非官方模块设为 False） |
| `can_auto_init` | bool | True | 是否自动初始化 CAN 总线 |
| `dh_is_offset` | int | 0x01 | DH 参数版本（0=旧版，1=新版） |
| `start_sdk_joint_limit` | bool | False | 启用 SDK 软件关节限位 |
| `start_sdk_gripper_limit` | bool | False | 启用 SDK 软件夹爪限位 |
| `logger_level` | LogLevel | WARNING | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL/SILENT) |
| `log_to_file` | bool | False | 启用文件日志 |

### 5.2 单例模式

`C_PiperInterface_V2` 使用单例模式管理实例：

```python
# 相同 can_name 返回同一实例
piper1 = C_PiperInterface_V2("can0")
piper2 = C_PiperInterface_V2("can0")
print(piper1 is piper2)  # True

# 不同 can_name 创建不同实例
piper_left = C_PiperInterface_V2("can_left")
piper_right = C_PiperInterface_V2("can_right")
```

### 5.3 连接管理

```python
# 连接 CAN 端口并启动线程
piper.ConnectPort(
    can_init=False,      # 是否重新初始化 CAN
    piper_init=True,     # 是否执行机械臂初始化
    start_thread=True    # 是否启动读取线程
)

# 检查连接状态
is_connected = piper.get_connect_status()

# 断开连接
piper.DisconnectPort(thread_timeout=0.1)
```

**ConnectPort 内部流程：**
1. 初始化 CAN 总线
2. 启动 ReadCan 线程（持续读取 CAN 消息）
3. 启动 CanMonitor 线程（监控 CAN 状态）
4. 执行 PiperInit（查询电机参数、固件版本）

### 5.4 线程模型

SDK 内部创建两个守护线程：

```
Main Thread                    Worker Threads
     │                              │
     ├─ ConnectPort() ─────────────┤
     │                              ├─ ReadCan Thread
     │                              │   └─ 持续调用 bus.recv()
     │                              │   └─ 回调 ParseCANFrame()
     │                              │
     │                              └─ CanMonitor Thread
     │                                  └─ 监控 CAN 状态
     │                                  └─ 计算消息 FPS
     │
     ├─ GetArmJointMsgs() ◄─────────┤
     │                              │   (读取已解析的数据)
```

---

## 6. 控制模式

### 6.1 关节控制

```python
# 角度转 SDK 单位的系数
factor = 57295.7795  # 1000 * 180 / π

# 目标关节角度（弧度）
joint_positions = [0.0, 0.2, -0.2, 0.3, -0.2, 0.5]  # 6 个关节

# 转换为 SDK 单位
joint_0 = round(joint_positions[0] * factor)
joint_1 = round(joint_positions[1] * factor)
joint_2 = round(joint_positions[2] * factor)
joint_3 = round(joint_positions[3] * factor)
joint_4 = round(joint_positions[4] * factor)
joint_5 = round(joint_positions[5] * factor)

# 设置运动模式
piper.MotionCtrl_2(
    ctrl_mode=0x01,      # 0x01=CAN 控制模式
    move_mode=0x01,      # 0x01=MOVE J
    speed_rate=100,      # 速度百分比
    delay=0x00           # 延时
)

# 发送关节目标
piper.JointCtrl(joint_0, joint_1, joint_2, joint_3, joint_4, joint_5)
```

### 6.2 笛卡尔控制

```python
# 目标位姿
x, y, z = 0.3, 0.0, 0.4        # 位置 (米)
rx, ry, rz = 0, 0, 0           # 姿态 (弧度)

# 转换为 SDK 单位 (0.001mm, 0.001度)
x_int = int(x * 1000 * 1000)
y_int = int(y * 1000 * 1000)
z_int = int(z * 1000 * 1000)
rx_int = int(rx * 1000 * 180 / 3.14159)
ry_int = int(ry * 1000 * 180 / 3.14159)
rz_int = int(rz * 1000 * 180 / 3.14159)

# 设置 MOVE L 模式
piper.MotionCtrl_2(0x01, 0x02, 100, 0x00)

# 发送末端位姿
piper.EndPoseCtrl(x_int, y_int, z_int, rx_int, ry_int, rz_int)
```

### 6.3 运动模式说明

| move_mode | 值 | 说明 |
|-----------|-----|------|
| MOVE P | 0x00 | 点到点运动（直线插补） |
| MOVE J | 0x01 | 关节空间运动 |
| MOVE L | 0x02 | 直线运动 |
| MOVE C | 0x03 | 圆弧运动 |
| MOVE M | 0x04 | 多段轨迹运动 (V1.5-2+) |
| MOVE CPV | 0x05 | 连续路径速度模式 (V1.6.5+) |

### 6.4 夹爪控制

```python
# 控制夹爪开合
# 参数：位置(0-1000000)，力(0-1000)，状态(0x01=启用)，延时
piper.GripperCtrl(
    gripper_pos=500000,    # 开合位置（0=闭合，1000000=张开）
    gripper_force=1000,    # 夹持力
    gripper_code=0x01,     # 0x01=启用控制
    delay=0
)

# 夹爪位置单位：0.001mm
# 0 = 完全闭合
# 1000000 = 完全张开 (约 100mm)
```

### 6.5 电机使能/失能

```python
# 使能电机（上电，抱闸打开）
piper.EnablePiper()

# 失能电机（断电，抱闸闭合）
piper.DisablePiper()

# 循环等待使能成功
while not piper.EnablePiper():
    time.sleep(0.01)
```

---

## 7. 读取反馈数据

### 7.1 获取机械臂状态

```python
arm_status = piper.GetArmStatus()

print(f"时间戳: {arm_status.time_stamp}")
print(f"消息频率: {arm_status.Hz} Hz")
print(f"控制模式: {arm_status.arm_status.ctrl_mode}")
print(f"机械臂状态: {arm_status.arm_status.arm_status}")
print(f"运动模式: {arm_status.arm_status.mode_feed}")
print(f"运动状态: {arm_status.arm_status.motion_status}")
```

**ArmStatus 字段说明：**

| 字段 | 说明 |
|------|------|
| `ctrl_mode` | 0x00=待机, 0x01=CAN 控制, 0x02=示教模式 |
| `arm_status` | 0x00=正常, 0x01=急停, 0x02=无解, ... |
| `mode_feed` | 0x00=MOVE P, 0x01=MOVE J, ... |
| `motion_status` | 0x00=到位, 0x01=运动中 |

### 7.2 获取关节角度

```python
joint_msgs = piper.GetArmJointMsgs()

print(f"时间戳: {joint_msgs.time_stamp}")
print(f"频率: {joint_msgs.Hz} Hz")

# 关节角度（SDK 单位，需转换）
joint_1 = joint_msgs.joint_state.joint_1 / 1000  # 转度
joint_2 = joint_msgs.joint_state.joint_2 / 1000
# ...

# 转换为弧度
joint_1_rad = joint_1 * 3.14159 / 180
```

### 7.3 获取末端位姿

```python
pose_msgs = piper.GetArmEndPoseMsgs()

x = pose_msgs.end_pose.X_axis / 1000000    # 米
y = pose_msgs.end_pose.Y_axis / 1000000
z = pose_msgs.end_pose.Z_axis / 1000000
rx = pose_msgs.end_pose.RX_axis / 1000     # 度
ry = pose_msgs.end_pose.RY_axis / 1000
rz = pose_msgs.end_pose.RZ_axis / 1000
```

### 7.4 获取夹爪状态

```python
gripper_msgs = piper.GetArmGripperMsgs()

angle = gripper_msgs.gripper_state.grippers_angle / 1000  # 度
effort = gripper_msgs.gripper_state.grippers_effort       # 力
status = gripper_msgs.gripper_state.status_code           # 状态码
```

### 7.5 获取电机驱动器信息

```python
# 高速反馈（速度、电流、位置）
high_spd = piper.GetArmMotorDriverInfoHighSpd()
motor_1_speed = high_spd.motor_1.motor_speed  # rpm
motor_1_current = high_spd.motor_1.current    # mA
motor_1_pos = high_spd.motor_1.pos            # 编码器值

# 低速反馈（电压、温度）
low_spd = piper.GetArmMotorDriverInfoLowSpd()
motor_1_vol = low_spd.motor_1.vol             # mV
motor_1_temp = low_spd.motor_1.foc_temp       # 摄氏度
```

---

## 8. 消息协议

### 8.1 CAN ID 映射

| CAN ID | 名称 | 说明 |
|--------|------|------|
| 0x2A1 | ARM_STATUS_FEEDBACK | 机械臂状态反馈 |
| 0x2A2 | ARM_END_POSE_FEEDBACK_1 | 末端位姿 X,Y |
| 0x2A3 | ARM_END_POSE_FEEDBACK_2 | 末端位姿 Z,RX |
| 0x2A4 | ARM_END_POSE_FEEDBACK_3 | 末端位姿 RY,RZ |
| 0x2A5 | ARM_JOINT_FEEDBACK_12 | 关节 1,2 反馈 |
| 0x2A6 | ARM_JOINT_FEEDBACK_34 | 关节 3,4 反馈 |
| 0x2A7 | ARM_JOINT_FEEDBACK_56 | 关节 5,6 反馈 |
| 0x2A8 | ARM_GRIPPER_FEEDBACK | 夹爪反馈 |
| 0x150 | ARM_MOTION_CTRL_1 | 运动控制指令 1 |
| 0x151 | ARM_MOTION_CTRL_2 | 运动控制指令 2 |
| 0x152 | ARM_JOINT_CTRL | 关节控制指令 |
| 0x153 | ARM_GRIPPER_CTRL | 夹爪控制指令 |

### 8.2 PiperMessage 结构

```python
class PiperMessage:
    def __init__(self):
        # 反馈消息
        self.arm_status_msgs              # 机械臂状态
        self.arm_joint_feedback           # 关节反馈
        self.gripper_feedback             # 夹爪反馈
        self.arm_end_pose                 # 末端位姿
        self.arm_high_spd_feedback_1~6    # 电机高速反馈
        self.arm_low_spd_feedback_1~6     # 电机低速反馈
        
        # 发送消息
        self.arm_motion_ctrl_1            # 运动控制 1
        self.arm_motion_ctrl_2            # 运动控制 2
        self.arm_joint_ctrl               # 关节控制
        self.arm_gripper_ctrl             # 夹爪控制
```

---

## 9. 正运动学

### 9.1 启用 FK 计算

```python
# 启用正运动学计算
piper.EnableFkCal()

# 检查是否启用
is_enabled = piper.isCalFk()

# 禁用 FK 计算
piper.DisableFkCal()
```

### 9.2 获取 FK 结果

```python
# 获取反馈消息的正解（当前实际位置）
fk_feedback = piper.GetPiperFKFeedback()

# 获取控制消息的正解（目标位置）
fk_ctrl = piper.GetPiperFKCtrl()
```

### 9.3 DH 参数

SDK 内置 DH 参数表，支持两种版本：
- `dh_is_offset=0`：旧版参数（S-V1.6-3 之前固件）
- `dh_is_offset=1`：新版参数（S-V1.6-3 及之后固件，J1-J2 有 2° 偏移补偿）

---

## 10. 主从模式

### 10.1 配置主从模式

```python
# 设置为主臂模式（示教模式）
piper.MasterSlaveConfig(
    master_slave_mode=0xFC,  # 0xFC=主臂模式
    tracking_mode=0,
    following_mode=0,
    delay=0
)

# 设置为从臂模式
piper.MasterSlaveConfig(0xFD, 0, 0, 0)

# 退出主从模式
piper.MasterSlaveConfig(0x00, 0, 0, 0)
```

### 10.2 示教模式使用流程

```python
# 1. 主臂读取动作
action = piper_leader.GetArmJointMsgs()

# 2. 从臂执行动作
piper_follower.JointCtrl(
    action.joint_state.joint_1,
    action.joint_state.joint_2,
    # ...
)
```

---

## 11. 完整示例

### 11.1 基础关节控制

```python
import time
from piper_sdk import *

# 初始化
piper = C_PiperInterface_V2("can0")
piper.ConnectPort()

# 等待使能
while not piper.EnablePiper():
    time.sleep(0.01)

# 运动到零点
factor = 57295.7795
piper.MotionCtrl_2(0x01, 0x01, 100, 0x00)

while True:
    # 读取当前状态
    status = piper.GetArmStatus()
    joints = piper.GetArmJointMsgs()
    
    print(f"状态: {status.arm_status.arm_status}")
    print(f"关节: {[joints.joint_state.joint_1/1000, joints.joint_state.joint_2/1000, ...]}")
    
    # 发送目标
    piper.JointCtrl(0, 0, 0, 0, 0, 0)
    
    time.sleep(0.005)  # 200Hz
```

### 11.2 完整的控制循环

```python
import time
from piper_sdk import *

def main():
    # 1. 初始化
    piper = C_PiperInterface_V2(
        can_name="can0",
        judge_flag=False,  # 非官方 CAN 模块设为 False
        logger_level=LogLevel.INFO
    )
    
    # 2. 连接
    piper.ConnectPort()
    print("Connected to Piper!")
    
    # 3. 使能
    print("Enabling motors...")
    while not piper.EnablePiper():
        time.sleep(0.01)
    print("Motors enabled!")
    
    # 4. 控制参数
    factor = 57295.7795
    positions = [
        [0, 0, 0, 0, 0, 0],
        [0.5, 0.2, -0.3, 0.1, -0.2, 0.4],
        [0, 0, 0, 0, 0, 0],
    ]
    
    # 5. 控制循环
    count = 0
    pos_idx = 0
    
    try:
        while True:
            count += 1
            
            # 切换目标位置
            if count % 500 == 0:
                pos_idx = (pos_idx + 1) % len(positions)
                print(f"Target: {positions[pos_idx]}")
            
            pos = positions[pos_idx]
            
            # 设置运动模式
            piper.MotionCtrl_2(0x01, 0x01, 100, 0x00)
            
            # 发送关节控制
            piper.JointCtrl(
                round(pos[0] * factor),
                round(pos[1] * factor),
                round(pos[2] * factor),
                round(pos[3] * factor),
                round(pos[4] * factor),
                round(pos[5] * factor)
            )
            
            # 夹爪控制
            piper.GripperCtrl(500000, 1000, 0x01, 0)
            
            # 读取反馈
            joints = piper.GetArmJointMsgs()
            print(f"Current: {[joints.joint_state.joint_1/1000, joints.joint_state.joint_2/1000, ...]}")
            
            time.sleep(0.005)  # 200Hz
            
    except KeyboardInterrupt:
        print("\nStopping...")
        piper.DisablePiper()
        piper.DisconnectPort()

if __name__ == "__main__":
    main()
```

---

## 12. API 参考

### 12.1 连接管理

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `ConnectPort(can_init, piper_init, start_thread)` | bool, bool, bool | None | 连接并启动线程 |
| `DisconnectPort(thread_timeout)` | float | None | 断开连接 |
| `get_connect_status()` | - | bool | 获取连接状态 |
| `CreateCanBus(can_name, bustype, expected_bitrate, judge_flag)` | str, str, int, bool | None | 创建 CAN 总线 |

### 12.2 运动控制

| 方法 | 参数 | 说明 |
|------|------|------|
| `MotionCtrl_2(ctrl_mode, move_mode, speed_rate, delay)` | int, int, int, int | 运动控制指令 |
| `JointCtrl(joint_1~6)` | int x6 | 关节控制 |
| `EndPoseCtrl(x, y, z, rx, ry, rz)` | int x6 | 末端位姿控制 |
| `GripperCtrl(pos, force, code, delay)` | int, int, int, int | 夹爪控制 |

### 12.3 状态获取

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `GetArmStatus()` | ArmStatus | 机械臂状态 |
| `GetArmJointMsgs()` | ArmJoint | 关节角度 |
| `GetArmEndPoseMsgs()` | ArmEndPose | 末端位姿 |
| `GetArmGripperMsgs()` | ArmGripper | 夹爪状态 |
| `GetArmMotorDriverInfoHighSpd()` | ArmMotorDriverInfoHighSpd | 电机高速反馈 |
| `GetArmMotorDriverInfoLowSpd()` | ArmMotorDriverInfoLowSpd | 电机低速反馈 |
| `GetCanFps()` | float | CAN 消息频率 |

### 12.4 参数设置

| 方法 | 说明 |
|------|------|
| `EnablePiper()` | 使能机械臂 |
| `DisablePiper()` | 失能机械臂 |
| `MasterSlaveConfig(mode, track, follow, delay)` | 主从模式配置 |
| `EnableFkCal()` | 启用 FK 计算 |
| `DisableFkCal()` | 禁用 FK 计算 |

---

## 13. 故障排除

### 13.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `CAN socket does not exist` | CAN 未激活 | 运行 `can_activate.sh` |
| `CAN port is not UP` | CAN 接口未启动 | 检查 `ifconfig` |
| `bitrate mismatch` | 波特率不匹配 | 确保使用 1000000 |
| `Message NOT sent` | CAN 连接断开 | 检查硬件连接，重新上电 |
| 无法读取反馈 | 机械臂未使能 | 调用 `EnablePiper()` |

### 13.2 调试技巧

```python
# 启用 DEBUG 日志
piper = C_PiperInterface_V2(
    can_name="can0",
    logger_level=LogLevel.DEBUG,
    log_to_file=True,
    log_file_path="/tmp/piper.log"
)

# 检查 CAN 帧率
fps = piper.GetCanFps()
print(f"CAN FPS: {fps}")

# 检查机械臂状态
status = piper.GetArmStatus()
print(f"Arm status: {status.arm_status.arm_status}")
print(f"Ctrl mode: {status.arm_status.ctrl_mode}")
```

### 13.3 固件版本

```python
# 读取固件版本
piper.SearchPiperFirmwareVersion()
time.sleep(0.025)  # 等待反馈
version = piper.GetPiperFirmwareVersion()
print(version)
```

---

## 14. 参考资源

- **GitHub**: <https://github.com/agilexrobotics/piper_sdk>
- **新 SDK**: <https://github.com/agilexrobotics/pyAgxArm>
- **官方文档**: `asserts/V2/INTERFACE_V2.MD`
- **DEMO 代码**: `piper_sdk/demo/V2/`
- **Q&A**: `asserts/Q&A.MD`
- **Discord**: <https://discord.gg/wrKYTxwDBd>
