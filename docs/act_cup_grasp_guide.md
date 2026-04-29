# ACT 抓取纸杯任务 — 完整指南

> 本文档针对使用 LeRobot + ACT 策略训练 Piper 机械臂抓取纸杯任务，涵盖数据采样、ACT 代码修正、训练配置与常见问题。

---

## 一、ACT 代码是否需要修正？

### 结论：需要添加一个小但重要的改进

当前 LeRobot 中的 ACT 实现**在功能上是正确的**，它是原始 ALOHA 论文的忠实复现。但我们在深入分析后发现一个**影响小数据集训练效率的缺陷**：

**ACTConfig 缺少 `drop_n_last_frames` 字段。**

- Diffusion Policy、SARM、Multi-task DiT 等策略都定义了这个字段
- 它的作用是：在训练时跳过 episode 末尾的若干帧，避免模型学习大量被 `action_is_pad` 掩盖的无效动作
- ACT 默认 `chunk_size=100`，意味着每个训练样本要预测未来 100 帧的动作
- 在 episode 末尾，这些未来动作大多会被 clamp 并标记为 `action_is_pad=True`
- 虽然 loss mask 会忽略它们，但模型仍然被迫"预测 padding"，在小数据场景下会引入噪声

### 已做的修改

我们在 `configuration_act.py` 中添加了：

```python
drop_n_last_frames: int = 0
```

并在训练脚本中将其设为 **25**（对于 8-12 秒的 episode，仅丢弃约 8% 的数据，但显著减少边界 padding 噪声）。

### 不需要修改的地方

| 项目 | 是否需要修改 | 原因 |
|------|-------------|------|
| `n_decoder_layers=1` | ❌ 不需要 | 这是故意复现原始 ACT 代码中的 bug，以保持与 ALOHA 结果一致 |
| `chunk_size=100` | ⚠️ 可调整 | 默认 100 帧@30fps = 3.3 秒。抓取任务足够，但可缩短 |
| VAE 相关代码 | ❌ 不需要 | 小数据场景下 VAE 是核心防过拟合机制 |
| Loss mask (`action_is_pad`) | ❌ 不需要 | 已经正确工作 |

---

## 二、数据采样策略（最重要）

ACT 是一种**行为克隆 (Behavior Cloning)** 方法。它的性能上限直接取决于数据质量。对于抓取纸杯这种简单接触操作任务，遵循以下原则：

### 2.1 Episode 数量

- **最低要求：20 个成功的 episode**
- **推荐：30-50 个成功的 episode**
- 原始 ALOHA 论文每个任务使用 ~50 个 demonstrations
- ACT 的 VAE 正则化 (`kl_weight=10.0`) 让它在小数据下表现较好，但数据太少仍会欠拟合

### 2.2 Episode 时长

```
chunk_size=100  @ 30 fps  =>  3.3 秒动作预测窗口
建议 episode 时长: 8-12 秒 (240-360 帧)
```

**原因**：
- 太短（< 6 秒）：episode 末尾大量帧的动作 chunk 会被 padding，有效训练数据少
- 太长（> 15 秒）：抓取动作本身不需要这么久，多余动作会让模型困惑
- 8-12 秒的时间分配示例：
  - 0-3 秒：手臂从初始位置移动到纸杯上方
  - 3-5 秒：缓慢下降、调整姿态
  - 5-6 秒：闭合夹爪抓取
  - 6-8 秒：提起并移动到目标位置

### 2.3 多样性（比数量更重要）

**纸杯位置多样性**：
- 在桌面上随机放置纸杯（x-y 平面至少 5-8 个不同位置）
- 如果可能，尝试 2-3 种不同的纸杯朝向

**起始姿态多样性**：
- 每个 episode 开始前，将主臂（leader）放在**不同的起始姿态**
- 不要每次都从同一个位置开始，否则模型会过拟合到特定轨迹

**轨迹多样性**：
- 不要刻意走"最优直线"
- 有时从左边绕，有时从右边绕
- 下降速度有时快有时慢

### 2.4 成功率

- **尽量保证 100% 成功**。ACT 学习的是"平均行为"，失败的演示会拉低性能
- 如果某个 episode 中途碰撞或滑落，**删除该 episode**，不要保留
- 夹爪闭合时机要一致：建议在接触纸杯后再闭合，不要在空中提前闭合

### 2.5 相机视角

- **至少 2 个相机**：
  - `top`（俯视）：提供纸杯在桌面上的位置信息
  - `wrist`（腕部）：提供接近和抓取的近景细节
- 如果使用触觉相机，确保它在抓取过程中能清晰看到接触区域

### 2.6 单任务描述

记录时使用清晰、一致的任务描述：

```bash
--dataset.single_task="Grasp the white paper cup and lift it 10 cm above the table."
```

不要混合不同任务（比如有时抓取、有时推动），ACT 没有内置的任务条件机制（不像 SARM 或 DiT）。

---

## 三、推荐的录制命令

```bash
cd /home/stouching/vla/repo/lerobot052base
source .venv/bin/activate

lerobot-record \
    --robot.type=piper_follower \
    --robot.can_port=can_follower \
    --robot.cameras='{
        top: {type: opencv, index_or_path: /dev/video17, width: 640, height: 480, fps: 30, warmup_s: 60},
        wrist: {type: opencv, index_or_path: /dev/video7, width: 640, height: 480, fps: 30, warmup_s: 60}
    }' \
    --teleop.type=piper_leader \
    --teleop.can_port=can_leader \
    --dataset.repo_id=pi0/cup_grasp \
    --dataset.single_task="Grasp the white paper cup and lift it." \
    --dataset.root=/home/stouching/vla/repo/dataset/cup_grasp \
    --dataset.streaming_encoding=true \
    --dataset.encoder_threads=2 \
    --dataset.num_episodes=50 \
    --dataset.episode_time_s=10 \
    --dataset.reset_time_s=10 \
    --dataset.push_to_hub=false \
    --play_sounds=false \
    --display_data=true
```

**关键参数解释**：
- `episode_time_s=10`：每个 episode 10 秒，足够完成抓取+提起
- `reset_time_s=10`：episode 之间有 10 秒手动复位时间
- `warmup_s=60`：相机预热 60 秒，避免前几帧黑屏/模糊
- `num_episodes=50`：目标录制 50 个 episode

### 录制流程建议

```
第 1-5 个 episode：纸杯放在桌面中央偏左
第 6-10 个 episode：纸杯放在桌面中央偏右
第 11-15 个 episode：纸杯放在桌面靠前位置
第 16-20 个 episode：纸杯放在桌面靠后位置
第 21-30 个 episode：混合上述位置，变化起始姿态
第 31-50 个 episode：继续混合，刻意变化接近角度和速度
```

---

## 四、训练命令

### 使用 lerobot-train CLI（直接复制粘贴运行）

```bash
cd /home/stouching/vla/repo/lerobot052base
source .venv/bin/activate

lerobot-train \
    --policy.type=act \
    --policy.chunk_size=100 \
    --policy.n_action_steps=100 \
    --policy.drop_n_last_frames=25 \
    --policy.use_vae=true \
    --policy.kl_weight=10.0 \
    --policy.tactile_encoder=false \
    --policy.push_to_hub=false \
    --policy.optimizer_lr=1e-5 \
    --policy.optimizer_lr_backbone=1e-5 \
    --dataset.repo_id=pi0/cup_grasp \
    --dataset.root=/home/stouching/vla/repo/dataset/test01 \
    --dataset.streaming=false \
    --output_dir=/home/stouching/vla/repo/lerobot052base/outputs/train/act_piper_cup_grasp \
    --job_name=act_piper_cup_grasp \
    --steps=20000 \
    --batch_size=4 \
    --gradient_accumulation_steps=4 \
    --num_workers=4 \
    --save_freq=2000 \
    --log_freq=100 \
    --eval_freq=0 \
    --seed=42 \
    --wandb.enable=true \
    --wandb.project=vla \
    --wandb.entity=zhangchengang2001-southe \
    --wandb.notes="ACT cup grasp bs16(4x4) lr1e-5 chunk100 drop25 tactile_share_resnet"
```

如果方案 A 效果不够好，开启 tactile 独立 encoder（方案 B）：

```bash
cd /home/stouching/vla/repo/lerobot052base
source .venv/bin/activate

lerobot-train \
    --policy.type=act \
    --policy.chunk_size=100 \
    --policy.n_action_steps=100 \
    --policy.drop_n_last_frames=25 \
    --policy.use_vae=true \
    --policy.kl_weight=10.0 \
    --policy.tactile_encoder=true \
    --policy.tactile_features='["observation.images.right_wrist_0_rgb"]' \
    --policy.push_to_hub=false \
    --policy.optimizer_lr=1e-5 \
    --policy.optimizer_lr_backbone=1e-5 \
    --dataset.repo_id=pi0/cup_grasp \
    --dataset.root=/home/stouching/vla/repo/dataset/test01 \
    --dataset.streaming=false \
    --output_dir=/home/stouching/vla/repo/lerobot052base/outputs/train/act_piper_cup_grasp_tactile \
    --job_name=act_piper_cup_grasp_tactile \
    --steps=20000 \
    --batch_size=4 \
    --gradient_accumulation_steps=4 \
    --num_workers=4 \
    --save_freq=2000 \
    --log_freq=100 \
    --eval_freq=0 \
    --seed=42 \
    --wandb.enable=true \
    --wandb.project=vla \
    --wandb.entity=zhangchengang2001-southe \
    --wandb.notes="ACT cup grasp bs16(4x4) lr1e-5 chunk100 drop25 tactile_separate_encoder"
```

### 关键超参数说明

| 参数 | 设置 | 原因 |
|------|------|------|
| `chunk_size=100` | 默认 | 3.3 秒预测窗口，足够覆盖 reach+grasp+lift |
| `n_action_steps=100` | = chunk_size | 执行完整个 chunk 再重新查询（最简单） |
| `drop_n_last_frames=25` | 新增 | 跳过 episode 末尾 25 帧，减少 padding 噪声 |
| `use_vae=true` | 必须 | 小数据防过拟合 |
| `kl_weight=10.0` | 默认 | VAE 正则化强度，小数据保持高值 |
| `batch_size=8` | 推荐 | 50 个 episode × 300 帧 = 15000 帧，batch_size=8 合理 |
| `steps=20000` | 推荐 | 约 20000 / (15000/8) ≈ 11 个 epoch，足够收敛 |
| `optimizer_lr=1e-5` | 默认 | ACT 使用较低学习率，避免破坏预训练 ResNet |

### 如果你只有 20 个 episode（小数据保守训练）

```bash
cd /home/stouching/vla/repo/lerobot052base
source .venv/bin/activate

lerobot-train \
    --policy.type=act \
    --policy.chunk_size=50 \
    --policy.n_action_steps=50 \
    --policy.drop_n_last_frames=10 \
    --policy.use_vae=true \
    --policy.kl_weight=10.0 \
    --policy.optimizer_lr=1e-5 \
    --dataset.repo_id=pi0/cup_grasp \
    --dataset.root=/home/stouching/vla/repo/dataset/cup_grasp \
    --output_dir=/home/stouching/vla/repo/lerobot052base/outputs/train/act_cup_grasp_small \
    --steps=10000 \
    --batch_size=4 \
    --gradient_accumulation_steps=4 \
    --num_workers=4 \
    --save_freq=2000 \
    --log_freq=100 \
    --eval_freq=0 \
    --seed=42 \
    --wandb.enable=true \
    --wandb.project=vla \
    --wandb.entity=zhangchengang2001-southe \
    --wandb.notes="ACT cup grasp small bs16(4x4) chunk50"
```

**调整**：
- `chunk_size=50`：缩短为 1.7 秒，减少 episode 末尾 padding 问题
- `batch_size=4`：小数据用小 batch
- `steps=10000`：防止过拟合

---

## 五、评估与部署

### 评估训练效果

查看训练日志中的 loss：

```bash
tail -f /home/stouching/vla/repo/lerobot052base/outputs/train/act_piper_cup_grasp/logs.txt
```

期望看到：
- `l1_loss` 快速下降到 < 0.01（归一化后的 L1 loss）
- `kld_loss` 稳定在某个值（VAE 正则项，不需要降到 0）

### 在真实机器人上运行

```bash
uv run lerobot-eval \
    --policy.path=/home/stouching/vla/repo/lerobot052base/outputs/train/act_piper_cup_grasp/checkpoints/last \
    --robot.type=piper_follower \
    --robot.can_port=can_follower \
    --robot.cameras='{
        top: {type: opencv, index_or_path: /dev/video17, width: 640, height: 480, fps: 30},
        wrist: {type: opencv, index_or_path: /dev/video7, width: 640, height: 480, fps: 30}
    }' \
    --dataset.repo_id=pi0/cup_grasp \
    --dataset.root=/home/stouching/vla/repo/dataset/cup_grasp \
    --eval.n_episodes=10 \
    --eval.batch_size=1
```

**注意**：
- ACT 是开环执行（在 `chunk_size` 内不重新观察），所以环境必须相对稳定
- 如果纸杯位置与训练分布差异太大，可能会失败
- 首次运行时准备随时按急停

---

## 六、常见问题排查

### Q1: 训练 loss 不下降
- 检查数据量是否足够（至少 20 个成功 episode）
- 检查是否有相机黑帧（查看 dataset 中的视频）
- 尝试降低 `chunk_size` 到 50

### Q2: 模型在训练集上好，但机器人执行失败
- 检查 `drop_n_last_frames` 是否设置合理
- 检查 eval 时的相机参数是否与训练完全一致（分辨率、帧率）
- 可能是过拟合：增加数据多样性，或减小 `steps`

### Q3: 从臂动作抖动或不连贯
- 增加数据量，确保轨迹平滑
- 检查 leader 遥操作时是否有抖动（人类操作要慢而稳）
- 尝试启用 `temporal_ensemble_coeff=0.01`（需要将 `n_action_steps` 改为 1）

### Q4: 夹爪总是提前/滞后闭合
- 在录制时统一抓取时机（比如都等到夹爪下降到位后再闭合）
- 增加 wrist 相机的录制，让模型看到夹爪与纸杯的相对位置

---

## 七、总结

| 步骤 | 行动 | 预期结果 |
|------|------|---------|
| 1 | 录制 30-50 个成功的抓取 episode，每个 8-10 秒 | 高质量行为克隆数据集 |
| 2 | 确保 ACTConfig 已添加 `drop_n_last_frames` | 我们已完成此修改 ✅ |
| 3 | 使用 `train_act_piper_cup_grasp.sh` 训练 | 约 30-60 分钟收敛 |
| 4 | 在机器人上评估 | 成功率应 > 70%（如果数据质量好） |

> **核心原则**：ACT 的性能 80% 取决于数据质量，20% 取决于模型。花时间在多样化、高质量的数据采集上，比调参更有效。
