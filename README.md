# LeRobot-052-Piper

## LeRobot 版本

- 官网下载 LeRobot-0.5.2

## UV虚拟环境

- 在leRobot052base文件夹下,激活uv虚拟环境命令为 source ./.venv/bin/activate
- 注意先退出conda虚拟环境，conda deactivate XXX
- uv虚拟环境退出指令为 deactivate
- 激活后虚拟环境名为lerobot052base

## Tokenizer本地路径

- 若使用本地权重，policy_preprocessor.json文件中的tokenizer_name指向本地路径

## Find_can

- bash find_all_can_port.sh
- sudo bash find_all_can_port.sh

## Pi0 模型改动

### 1. configuration_pi0.py

新增配置字段 `freeze_lm_layers`：

- `0` = 不冻结（默认，和之前行为完全一样）
- `>0` = 冻结语言模型除最后 N 层外的所有层

### 2. modeling_pi0.py

- 构造函数接收新参数 `freeze_lm_layers`
- `_set_requires_grad()` 中添加了按层冻结逻辑
- `train()` 方法中保持被冻结层为 `eval()` 模式
- 创建模型时传入新参数

## Piper 机械臂低通滤波改造

### 改动文件

`lerobot052base/src/lerobot/robots/piper_follower/piper_follower.py`

### 1. 添加缓存变量（`__init__` 方法）

```python
# Low-pass filter cache for joint targets (SDK units)
self._last_joint_targets_sdk = [0] * 6
# Smoothing weight: 0.5 = equal weight for current and previous action
self._action_smoothing_weight = 0.5
```

### 2. 低通滤波逻辑（`send_action` 方法）

在关节目标转换后、发送控制命令前，添加滤波处理：

```python
# 1.5 Apply low-pass filter for action smoothing
# Formula: filtered = weight * current + (1 - weight) * previous
w = self._action_smoothing_weight
for i in range(len(joint_targets)):
    current = joint_targets[i]
    previous = self._last_joint_targets_sdk[i] if self._last_joint_targets_sdk[i] != 0 else current
    filtered = int(w * current + (1 - w) * previous)
    joint_targets[i] = filtered
    # Update cache for next iteration
    self._last_joint_targets_sdk[i] = filtered
```

### 工作原理

- **滤波公式**: `filtered = 0.5 * current + 0.5 * previous`
- **作用**: 对动作进行平滑处理，减少抖动
- **权重调整**: 修改 `_action_smoothing_weight` 可改变平滑程度
  - `0.7` = 更依赖当前动作（较少平滑）
  - `0.5` = 当前和历史动作各占一半（默认）
  - `0.3` = 更依赖历史动作（较多平滑）
