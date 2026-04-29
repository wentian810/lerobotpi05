# PI0.5 触觉传感器集成文档

## 概述

本项目已成功将 `stouch_sdk` 触觉传感器集成到 LeRobot 的 PI0.5 (Pi0.5) 策略中。通过添加轻量级触觉编码器，PI0.5 策略现在可以处理触觉图像输入，实现更丰富的感知能力。

## 修改内容

### 核心修改文件

1. **`src/lerobot/policies/pi05/configuration_pi05.py`**
   - 添加了 `tactile_image_keys` 配置参数
   - 添加了 `tactile_encoder_num_tokens` 配置参数

2. **`src/lerobot/policies/pi05/modeling_pi05.py`**
   - 添加了 `TactileEncoder` 类（轻量级触觉编码器）
   - 修改了 `_preprocess_images` 方法，将视觉和触觉图像分开处理
   - 添加了 `embed_tactile_image` 方法
   - 更新了 `embed_prefix` 方法，整合触觉嵌入
   - 修改了 `forward` 和 `sample_actions` 方法，支持触觉输入

3. **`tests/policies/pi0_pi05/test_pi05.py`**
   - 添加了触觉观察键的测试配置
   - 注册了触觉图像键到测试中

### 运行脚本示例更新

4. **`src/lerobot/scripts/lerobot_record.py`**
   - 添加了 pi0.5 触觉录制示例命令

5. **`src/lerobot/scripts/lerobot_train.py`**
   - 添加了 pi0.5 触觉训练示例命令

6. **`examples/rtc/eval_with_real_robot.py`**
   - 添加了 pi0.5 触觉真实机器人评估示例命令

## 技术实现细节

### 触觉编码器架构

- **输入**: 触觉图像 (RGB格式, 640x480)
- **处理**: 轻量级卷积网络，输出固定数量的token
- **集成**: 与视觉嵌入并行处理，通过 `embed_prefix` 整合到语言模型输入中

### 数据流

1. **录制阶段**: 触觉摄像头作为 `type: tactile` 配置，数据存储为 `observation.images.<camera_key>`
2. **训练阶段**: 通过 `--policy.tactile_image_keys` 指定触觉图像键
3. **推理阶段**: 触觉图像通过预处理器标准化后输入策略

## 使用指南

### 1. 数据录制

```bash
lerobot-record \
  --robot.type=piper_follower \
  --robot.can_port=can_follower \
  --robot.cameras='{base_0_rgb: {type: opencv, index_or_path: /dev/video17, width: 640, height: 480, fps: 30, warmup_s: 60}, left_wrist_0_rgb: {type: opencv, index_or_path: /dev/video12, width: 640, height: 480, fps: 30, warmup_s: 60}, right_wrist_0_rgb: {type: tactile, usb_id: /dev/video5, finger_id: tactile, width: 640, height: 480, fps: 15}}' \
  --teleop.type=piper_leader \
  --teleop.can_port=can_leader \
  --dataset.repo_id=pi05/dataset \
  --dataset.single_task="Pick up the white box and place it in the cardboard box beside it." \
  --dataset.root=/home/stouching/vla/repo/dataset/pi05_tactile \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  --dataset.num_episodes=30 \
  --dataset.episode_time_s=500 \
  --dataset.reset_time_s=15 \
  --dataset.push_to_hub=false \
  --play_sounds=false \
  --display_data=false
```

### 2. 模型训练

如果你的 Python 环境没有安装 `lerobot-train` 命令行入口，建议直接使用模块方式启动：

```bash
python -m lerobot.scripts.lerobot_train \
    --policy.pretrained_path=lerobot/pi05_base \
    --dataset.repo_id=pi05/dataset \
    --dataset.root=/home/stouching/vla/repo/dataset/pi05_tactile \
    --policy.push_to_hub=false \
    --policy.type=pi05 \
    --policy.device=cuda \
    --policy.dtype=bfloat16 \
    --policy.train_expert_only=true \
    --policy.chunk_size=100 \
    --policy.n_action_steps=100 \
    --policy.tactile_image_keys='["observation.images.right_wrist_0_rgb"]' \
    --output_dir=/home/stouching/Desktop/lerobot_v1/pi05_tactile_train \
    --job_name=pi05_piper_tactile_train \
    --wandb.enable=true \
    --wandb.project=vla \
    --wandb.entity=zhangchengang2001-southe \
    --wandb.notes="Pi0.5 tactile fine-tuning bs4 lr1e-5 chunk100" \
    --steps=32000 \
    --batch_size=4 \
    --gradient_accumulation_steps=4 \
    --save_freq=8000 \
    --log_freq=100 \
    --eval_freq=16000 \
    --optimizer.type=adamw \
    --optimizer.lr=1e-5 \
    --optimizer.weight_decay=0.01 \
    --policy.scheduler_warmup_steps=3000 \
    --policy.scheduler_decay_steps=32000 \
    --policy.scheduler_decay_lr=1e-6 \
    --seed=42 \
    --num_workers=8
```

**注意**: `--steps=32000` 表示32000次优化器更新步数。由于 `--gradient_accumulation_steps=4`，总前向传播次数为128000次。

### 3. 真实机器人评估

```bash
uv run examples/rtc/eval_with_real_robot.py \
    --policy.path=/home/stouching/Desktop/lerobot_v1/pi05_tactile_model \
    --policy.device=cuda \
    --policy.dtype=bfloat16 \
    --policy.type=pi05 \
    --policy.tactile_image_keys='["observation.images.right_wrist_0_rgb"]' \
    --rtc.enabled=true \
    --rtc.execution_horizon=20 \
    --robot.type=piper_follower \
    --robot.can_port=can_follower \
    --robot.cameras='{base_0_rgb: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30, warmup_s: 10}, left_wrist_0_rgb: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30, warmup_s: 10}, right_wrist_0_rgb: {type: tactile, usb_id: /dev/video5, finger_id: tactile, width: 640, height: 480, fps: 15}}' \
    --task="Pick up the white box and place it in the cardboard box beside it." \
    --duration=300 \
    --action_queue_size_to_get_new_actions=40 \
    --fps=20
```

## 配置参数

### 策略配置

- `tactile_image_keys`: 触觉图像键列表，例如 `["observation.images.right_wrist_0_rgb"]`
- `tactile_encoder_num_tokens`: 触觉编码器输出token数量（默认256）

### 摄像头配置

触觉摄像头配置示例：
```json
{
  "right_wrist_0_rgb": {
    "type": "tactile",
    "usb_id": "/dev/video5",
    "finger_id": "tactile",
    "width": 640,
    "height": 480,
    "fps": 15
  }
}
```

## 测试验证

运行测试以验证修改：
```bash
python -m pytest tests/policies/pi0_pi05/test_pi05.py -v
```

## 兼容性

- **LeRobot版本**: 基于 lerobot052base
- **Python版本**: 3.8+
- **PyTorch版本**: 2.0+
- **硬件**: 支持触觉传感器的机器人（如Piper）

## 贡献

如有问题或改进建议，请提交Issue或Pull Request。

## 更新日志

- **2024-04-28**: 初始版本，完成PI0.5触觉传感器集成
  - 添加轻量级触觉编码器
  - 更新配置和模型文件
  - 添加运行示例到相关脚本
- **2024-04-28**: 修复梯度累积训练循环bug
  - 修改训练循环逻辑，确保 `--steps` 正确表示优化器更新步数
  - 修复内外层循环问题，现在 `--steps=32000` `--gradient_accumulation_steps=4` 正确执行32000次更新

---

*本文档由GitHub Copilot生成，基于项目修改内容整理。*