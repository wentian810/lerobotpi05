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

### 激活can0

ip -br link show type can
sudo modprobe gs_usb
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
ip -details link show can0
sudo bash find_all_can_port.sh
sudo bash can_config.sh
sudo bash find_all_can_port.sh

### 映射can0为can_follower

sudo bash can_config.sh
sudo bash find_all_can_port.sh

### 激活can_Leader

bash find_all_can_port.sh
sudo bash find_all_can_port.sh

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

---

## VTLA 触觉传感器与算法改造记录

### 改造目标

- 在**不大改 stouch SDK** 的前提下，为触觉流新增独立后处理模块。
- 保持下游训练/推理接口不变：触觉仍按一个 camera 视角输入。
- 保证输出格式不变：`HxWx3, uint8`。

### 关键结论（兼容性）

- `stouch_sdk` 侧原始输出仍是触觉 RGB（三通道）：
  - `R`: pressure
  - `G`: flow_x
  - `B`: flow_y
- 本次改动只在 `lerobot` 相机封装层新增可开关处理，不改 SDK 输出协议。
- 下游 `observation.images.right_wrist_0_rgb` 的键名、shape、dtype 均保持一致。

### 改动文件（代码）

1. 新增文件：`lerobot052base/src/lerobot/cameras/tactile/tactile_processor.py`

- 新增 `VTLATactileProcessor`，提供：
  - EMA 时域平滑（`ema_alpha`）
  - 高频细节增强（`detail_gain`）
  - 时序差分增强（`temporal_diff_gain`）
  - 压力/光流分通道增益（`pressure_boost` / `flow_boost`）
  - 可选高斯去噪（`denoise_ksize`）
  - 材料域策略（`material_domain=auto|soft|hard`）
  - 轻量自适应归一化（`adaptive_norm`）

2. 修改文件：`lerobot052base/src/lerobot/cameras/tactile/configuration_tactile.py`

- 在 `TactileCameraConfig` 中新增 VTLA 参数：
  - `vtla_enable`
  - `vtla_ema_alpha`
  - `vtla_detail_gain`
  - `vtla_temporal_diff_gain`
  - `vtla_pressure_boost`
  - `vtla_flow_boost`
  - `vtla_denoise_ksize`
  - `vtla_material_domain`
  - `vtla_adaptive_norm`
  - `vtla_norm_momentum`
  - `vtla_norm_eps`

3. 修改文件：`lerobot052base/src/lerobot/cameras/tactile/camera_tactile.py`

- 在 `TactileCamera` 初始化中注入 `VTLATactileProcessor`。
- 在 `_read_from_hardware()` 中对 `get_tactile_rgb()` 结果做后处理。
- 在 `disconnect()` 时重置处理器状态（避免跨 episode 状态污染）。

4. 修改文件：`lerobot052base/src/lerobot/cameras/tactile/__init__.py`

- 导出 `VTLATactileProcessor`。

5. 修改文件：`lerobot052base/src/lerobot/scripts/lerobot_record.py`

- 增加 `from lerobot.cameras.tactile import TactileCameraConfig`（确保 `type: tactile` 与 `vtla_*` 参数可被解析注册）。
- 在脚本示例中增加 VTLA 软/硬物体参数模板。

### 推荐参数模板（数采）

- 软物体（增强弱信号）：

  - `vtla_enable=true`
  - `vtla_ema_alpha=0.28`
  - `vtla_detail_gain=1.35`
  - `vtla_temporal_diff_gain=0.32`
  - `vtla_pressure_boost=1.20`
  - `vtla_flow_boost=1.05`
  - `vtla_denoise_ksize=5`
- 硬物体（更稳更保守）：

  - `vtla_enable=true`
  - `vtla_ema_alpha=0.45`
  - `vtla_detail_gain=1.05`
  - `vtla_temporal_diff_gain=0.10`
  - `vtla_pressure_boost=1.00`
  - `vtla_flow_boost=1.00`
  - `vtla_denoise_ksize=3`

### 使用注意

- `find_all_can_port.sh` 仅查询接口状态，不负责重命名/激活。
- 触觉 VTLA 参数只作用于触觉相机，不影响其它 RGB 相机。
- 若训练目标是兼容软/硬材料，建议分数据目录采集并做混合训练。

---

## 梯度累积功能修改记录

### 概述

为 LeRobot 训练脚本添加了梯度累积（Gradient Accumulation）支持，允许通过多次小批量累积梯度来模拟大批量训练效果。

### 修改的文件

#### 1. `lerobot052base/src/lerobot/configs/train.py`

**位置**: 第 73-79 行（新增）

**修改内容**:

```python
# 在 RA-BC 参数之后添加梯度累积参数
# Gradient accumulation
gradient_accumulation_steps: int = 1  # Number of steps to accumulate gradients before updating weights
```

**说明**: 在 `TrainPipelineConfig` 类中添加了 `gradient_accumulation_steps` 配置项，默认值为 1（即不启用梯度累积）。

---

#### 2. `lerobot052base/src/lerobot/scripts/lerobot_train.py`

##### 修改 1: `update_policy` 函数签名和文档（第 168-202 行）

**新增参数**:

```python
def update_policy(
    ...
    accumulation_step: int = 0,
    gradient_accumulation_steps: int = 1,
) -> tuple[MetricsTracker, dict]:
```

**文档更新**: 在 Docstring 中添加了新参数说明:

```python
Args:
    ...
    accumulation_step: Current gradient accumulation step (0-indexed).
    gradient_accumulation_steps: Total number of gradient accumulation steps.
```

---

##### 修改 2: `update_policy` 函数内部逻辑（第 202-279 行）

**新增代码**:

```python
# Determine if this is the last accumulation step
is_accumulation_last_step = (accumulation_step + 1) % gradient_accumulation_steps == 0
```

**损失缩放修改**:

```python
loss, output_dict = policy.forward(batch)
# Scale loss by gradient accumulation steps to get correct average gradient
loss = loss / gradient_accumulation_steps
```

**梯度更新条件修改**:

- 原代码: 每次调用都执行 optimizer.step()
- 新代码: 只在最后一个累积步执行 optimizer.step() 和 optimizer.zero_grad()
- 累积步骤返回 grad_norm = 0.0
- 报告未缩放的损失值: `train_metrics.loss = loss.item() * gradient_accumulation_steps`

---

##### 修改 3: 训练循环中的有效 batch size 计算（第 534-556 行）

**原代码**:

```python
effective_batch_size = cfg.batch_size * accelerator.num_processes
```

**新代码**:

```python
effective_batch_size = cfg.batch_size * accelerator.num_processes * cfg.gradient_accumulation_steps
```

**MetricsTracker 初始化修改**:

```python
train_tracker = MetricsTracker(
    cfg.batch_size * cfg.gradient_accumulation_steps,  # Report the effective batch size
    ...
)
```

---

##### 修改 4: 训练信息日志输出（第 478-489 行）

**新代码**:

```python
num_processes = accelerator.num_processes
effective_bs = cfg.batch_size * num_processes * cfg.gradient_accumulation_steps
logging.info(f"Per-device batch size: {cfg.batch_size}")
logging.info(f"Number of processes: {num_processes}")
logging.info(f"Gradient accumulation steps: {cfg.gradient_accumulation_steps}")
logging.info(f"Effective batch size: {cfg.batch_size} x {num_processes} x {cfg.gradient_accumulation_steps} = {effective_bs}")
```

---

##### 修改 5: 主训练循环（第 558-610 行）

**新增梯度累积设置**:

```python
# Gradient accumulation setup
gradient_accumulation_steps = cfg.gradient_accumulation_steps
accumulation_step = 0
```

**修改后的训练循环**:

```python
for _ in range(step, cfg.steps):
    ...
    train_tracker, output_dict = update_policy(
        ...
        accumulation_step=accumulation_step,
        gradient_accumulation_steps=gradient_accumulation_steps,
    )

    accumulation_step += 1

    # Only update step counter and perform logging/checkpointing after accumulation is complete
    is_accumulation_last_step = accumulation_step % gradient_accumulation_steps == 0
    if not is_accumulation_last_step:
        continue

    # Reset accumulation counter
    accumulation_step = 0

    # 原有逻辑：step += 1, progbar.update(), 日志记录等
    step += 1
    ...
```

---

### 使用示例

#### 原始命令（等效 batch size = 4）:

```bash
lerobot-train \
    --batch_size=4 \
    --steps=32000 \
    ...
```

#### 使用梯度累积（等效 batch size = 16）:

```bash
lerobot-train \
    --batch_size=4 \
    --gradient_accumulation_steps=4 \
    --steps=32000 \
    ...
```

等效 batch size 计算: `4 (batch_size) × 4 (accumulation_steps) = 16`

---

### 关于 Action Chunk 的配置

要修改 action chunk 大小，使用以下参数：

```bash
lerobot-train \
    --policy.chunk_size=100 \        # 预测的动作步数（默认 50）
    --policy.n_action_steps=100 \    # 执行的动作步数（默认 50）
    ...
```

**注意**: `n_action_steps` 不能大于 `chunk_size`。

---

### 完整的推荐配置示例

```bash
lerobot-train \
    --policy.pretrained_path=/home/stouching/Desktop/lerobot_v1/pi0_base/pi0_base_weight \
    --dataset.repo_id=pi0/dataset \
    --dataset.root=/home/stouching/vla/repo/dataset/merged_test1_test2 \
    --policy.push_to_hub=false \
    --policy.type=pi0 \
    --policy.empty_cameras=1 \
    --policy.device=cuda \
    --policy.dtype=bfloat16 \
    --policy.train_expert_only=true \
    --policy.chunk_size=100 \
    --policy.n_action_steps=100 \
    --output_dir=/home/stouching/Desktop/lerobot_v1/4_21_train_16k \
    --job_name=pi0_piper_pick_box_16k \
    --wandb.enable=true \
    --wandb.project=vla \
    --wandb.entity=zhangchengang2001-southe \
    --wandb.notes="Pi0 expert fine-tuning with grad accum" \
    --steps=32000 \
    --batch_size=4 \
    --gradient_accumulation_steps=4 \
    --save_freq=8000 \
    --log_freq=100 \
    --eval_freq=16000 \
    --optimizer.type=adamw \
    --optimizer.lr=6.25e-6 \
    --optimizer.weight_decay=0.01 \
    --policy.scheduler_warmup_steps=3000 \
    --policy.scheduler_decay_steps=30000 \
    --policy.scheduler_decay_lr=2.5e-6 \
    --seed=42 \
    --num_workers=8
```

---

### 注意事项

1. **学习率调整**: 使用梯度累积时，学习率可能需要相应调整。一般建议保持与大批量训练相同的学习率。
2. **训练步数**: `--steps` 参数指的是**权重更新步数**，不是数据加载步数。实际处理的数据批次为 `steps × gradient_accumulation_steps`。
3. **内存使用**: 梯度累积可以减少 GPU 内存使用，但在累积期间需要保存梯度，会略微增加内存占用。
4. **同步频率**: 日志记录、模型保存和评估只在完成一个完整的累积周期后执行。
5. **与分布式训练兼容**: 梯度累积与 DataParallel/DistributedDataParallel 兼容，有效 batch size = `per_device_batch_size × num_processes × gradient_accumulation_steps`。

---

## PI0.5 触觉能力改造记录（仅代码改动）

> 本节仅记录改了哪些代码与关键修复点，不包含运行指令。

### 一、核心文件改动

1. `lerobot052base/src/lerobot/policies/pi05/configuration_pi05.py`

- 新增触觉相关配置：
  - `tactile_image_keys`
  - `tactile_encoder_num_tokens`

2. `lerobot052base/src/lerobot/policies/pi05/modeling_pi05.py`

- 新增/接入轻量触觉编码分支（`tactile_encoder` + `tactile_projection`）。
- 调整图像预处理流程：将视觉图像与触觉图像分组处理，再在前缀嵌入阶段融合。
- 更新 `embed_prefix` 路径，支持触觉 token 与视觉 token、语言 token 共同输入。

3. `lerobot052base/tests/policies/pi0_pi05/test_pi05.py`

- 增加 PI0.5 触觉观察键相关测试覆盖。

### 二、近期训练报错修复（2026-04-29）

1. 修复 `PI05Policy` 缺少 `tactile_image_keys` 属性导致的异常

- 问题：`_preprocess_images` 里访问了 `self.tactile_image_keys`，但该属性不在 `PI05Policy` 上。
- 修复：改为从配置读取 `getattr(self.config, "tactile_image_keys", [])`，并据此计算视觉/触觉键。

2. 修复 `PI05Pytorch` 缺少 `embed_tactile_image` 方法导致的异常

- 问题：`embed_prefix` 调用了 `self.embed_tactile_image(...)`，但类内无此方法。
- 修复：在 `PI05Pytorch` 中补充 `embed_tactile_image` 实现，接入 `tactile_encoder -> tactile_projection`。

3. 修复触觉嵌入 reshape 维度错误风险

- 在触觉嵌入中使用 `self.tactile_encoder_proj_dim` 进行投影前 reshape，之后再映射到 `self.tactile_encoder_hidden_dim`，与网络结构一致。

### 三、权重加载提示说明

- 当使用不含触觉分支参数的基础权重（如 `pi05_base`）时，加载阶段会提示缺失 `tactile_encoder*` / `tactile_projection*` 参数。
- 该现象属于预期：触觉分支参数会随机初始化并在后续训练中学习。
