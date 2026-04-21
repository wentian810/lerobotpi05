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
