# LeRobot 中文说明文档

> 项目地址：`huggingface/lerobot`  
> 当前包版本：`0.5.2`  
> Python 要求：`>=3.12`

---

## 1. 项目是什么

**LeRobot** 是 Hugging Face 面向现实机器人学习（Real-World Robotics）打造的一套开源 Python / PyTorch 工具链。它并不是单一模型或单一机械臂驱动包，而是一整套围绕 **机器人数据集、策略训练、仿真评测、真实硬件控制、Hub 分发共享** 构建的统一基础设施。

项目的核心目标可以概括为四点：

1. **统一机器人接口**：为不同机器人、相机、电机、遥操作器提供尽量一致的控制抽象。
2. **统一数据格式**：使用 `LeRobotDataset` 规范机器人数据存储、读取、切分、可视化与上传。
3. **统一训练/评测流程**：通过标准 CLI 和配置系统训练、评估不同策略模型。
4. **统一生态分发**：深度集成 Hugging Face Hub，便于共享模型、数据集与环境。

如果把它理解成一个“机器人机器学习操作系统”会更容易：

- **底层**：机器人、相机、电机、传输、遥操作；
- **中层**：数据采集、数据处理、特征映射、标准数据集；
- **上层**：策略模型、训练器、评测器、可视化工具；
- **云侧**：Hub 上的数据集、预训练模型、环境与文档。

---

## 2. 项目解决什么问题

机器人学习经常面临以下痛点：

- 不同机器人硬件接口完全不同，代码不可复用；
- 数据格式碎片化，视频、状态、动作、任务描述彼此脱节；
- 模型训练脚本与评测脚本风格不统一；
- 不同环境（真实机器人 / 仿真 / 基准测试）切换成本高；
- 社区中已有数据和模型难以复现与共享。

LeRobot 对这些问题的回答是：

- 用统一抽象封装硬件与环境；
- 用标准的 `Parquet + JSON + MP4` 数据组织方式承载机器人数据；
- 用 dataclass + CLI 的配置体系统一实验入口；
- 用处理流水线（processor pipeline）打通“环境/机器人数据”和“策略输入输出”之间的转换；
- 用 Hugging Face Hub 作为模型和数据的共享后端。

---

## 3. 核心能力总览

LeRobot 的能力大致可分为以下几类。

### 3.1 机器人控制与硬件接入

项目支持或适配多种机器人与外设，包括但不限于：

- SO100 / SO101
- LeKiwi
- Koch
- HopeJR
- OMX
- EarthRover
- Reachy2
- OpenARM
- Unitree G1
- Gamepad / Keyboard / Phone 等遥操作设备

这部分能力主要分布在：

- `src/lerobot/robots/`
- `src/lerobot/motors/`
- `src/lerobot/cameras/`
- `src/lerobot/teleoperators/`
- `src/lerobot/transport/`

### 3.2 标准机器人数据集格式

LeRobot 提供 `LeRobotDataset`，用于：

- 从本地读取数据集；
- 从 Hugging Face Hub 下载数据集；
- 处理视频流与状态/动作对齐；
- 存储统计信息、任务描述和 episode 元数据；
- 为训练与可视化提供统一输入接口。

### 3.3 策略模型与训练

项目已集成多类策略模型，包括：

- 模仿学习：`ACT`、`Diffusion`、`VQ-BeT`、`Multi-task DiT`
- 强化学习：`TDMPC`、`SAC`、`HIL-SERL`
- VLA / 多模态策略：`PI0`、`PI0.5`、`Pi0Fast`、`SmolVLA`、`GR00T`、`XVLA`、`Wall-X`
- 奖励 / 过程建模：`SARM`、`reward_classifier`

### 3.4 仿真与评测

支持常见机器人学习环境与 benchmark，例如：

- `ALOHA`
- `PushT`
- `LIBERO`
- `MetaWorld`
- Hub 托管环境

统一通过 `lerobot-eval` 等脚本进行评测。

### 3.5 工具化 CLI

项目将常用操作做成命令行工具，包括：

- `lerobot-train`
- `lerobot-eval`
- `lerobot-record`
- `lerobot-replay`
- `lerobot-teleoperate`
- `lerobot-calibrate`
- `lerobot-dataset-viz`
- `lerobot-edit-dataset`
- `lerobot-info`

这些命令都在 `pyproject.toml` 的 `[project.scripts]` 中注册，对应实现位于 `src/lerobot/scripts/`。

---

## 4. 技术栈与依赖设计

## 4.1 语言与运行时

- **Python**：要求 `>=3.12`
- **PyTorch**：核心深度学习框架
- **TorchVision / TorchCodec / AV**：图像与视频处理

## 4.2 机器学习与生态依赖

- `torch` / `torchvision`
- `accelerate`：分布式训练与混合精度
- `transformers`
- `diffusers`
- `peft`
- `safetensors`

## 4.3 配置与工程化

- `draccus`：dataclass 配置解析与 CLI 映射
- `ruff`：格式与静态检查
- `mypy`：渐进式类型检查
- `pytest`：测试框架
- `pre-commit`：提交前质量校验

## 4.4 数据与 Hub

- `datasets`
- `pyarrow`
- `pandas`
- `huggingface-hub`
- `jsonlines`

## 4.5 仿真与机器人相关依赖

- `gymnasium`
- `gym-aloha`
- `gym-pusht`
- `hf-libero`
- `metaworld`
- `mujoco`
- `dm-control`
- `placo`
- `pyrealsense2`
- `dynamixel-sdk`
- `feetech-servo-sdk`

## 4.6 为什么依赖拆成 extras

LeRobot 的一个重要工程特点是：**大量功能都通过 optional extras 按需安装**。

例如：

- `lerobot[dataset]`
- `lerobot[training]`
- `lerobot[hardware]`
- `lerobot[aloha]`
- `lerobot[libero]`
- `lerobot[pi]`
- `lerobot[smolvla]`
- `lerobot[all]`

这样设计有几个优点：

1. 避免把全部仿真、硬件、模型依赖都强塞给每个用户；
2. 降低安装失败概率；
3. 明确不同功能域的依赖边界；
4. 便于 CI 按场景拆分测试。

---

## 5. 目录结构与模块职责

下面结合仓库结构说明各模块的职责。

### 5.1 根目录关键文件

- `README.md`：英文总览文档
- `README_CN.md`：中文总览文档（本文）
- `pyproject.toml`：项目核心元数据、依赖、脚本入口、工具配置
- `setup.py`：补充打包逻辑，主要用于动态读取 `README.md` 生成长描述
- `requirements-ubuntu.txt`：锁定后的 Ubuntu 依赖清单
- `Makefile`：端到端测试等命令
- `CLAUDE.md` / `AGENTS.md`：面向 AI 代理的仓库说明
- `AI_POLICY.md`：AI 使用与贡献规范
- `SECURITY.md`：安全策略与远程模型使用建议

### 5.2 `src/lerobot/` 核心源码

#### `configs/`

配置系统核心。几乎所有 CLI 都依赖这里的 dataclass 配置对象。

关键点：

- `PreTrainedConfig`：策略配置基类
- `TrainPipelineConfig`：训练总配置
- 环境、优化器、scheduler、PEFT、WandB 等都有对应配置类
- 使用 `draccus.ChoiceRegistry` 实现多态配置注册

#### `policies/`

策略模型实现与工厂层。

关键设计：

- `PreTrainedPolicy` 是策略基类，继承 `torch.nn.Module`
- 支持 `save_pretrained()` / `from_pretrained()`
- 权重采用 `safetensors`
- 通过 `factory.py` 做动态加载，避免一次性导入全部策略与依赖

#### `datasets/`

机器人数据格式与读写核心。

关键对象：

- `LeRobotDataset`
- `LeRobotDatasetMetadata`
- `DatasetReader`
- `DatasetWriter`

#### `processor/`

这是 LeRobot 的中枢之一。它解决“环境/机器人原始数据”和“策略实际输入输出”之间的适配问题。

包含：

- 归一化 / 反归一化
- 相对动作 / 绝对动作转换
- 图像裁剪与缩放
- 环境特定处理（如 LIBERO、IsaacLab）
- 机器人动作与策略动作桥接
- tokenizer / 批处理 / 设备搬运等步骤

#### `envs/`

环境配置与实例化层。

关键设计：

- `EnvConfig` 为环境配置抽象基类
- 通过 `register_subclass` 注册不同环境
- 支持单任务 env 与 benchmark env
- 默认以 Gymnasium VectorEnv 封装批量环境

#### `robots/` / `motors/` / `cameras/` / `teleoperators/`

用于真实机器人控制链路：

- 机器人本体抽象
- 电机通信与标定
- 相机接入与数据采集
- 手柄、键盘、手机等遥操作设备

#### `scripts/`

CLI 入口实现。用户平时最常接触的功能几乎都从这里进入。

#### `common/`

训练、日志、WandB、checkpoint 等跨模块公共功能。

#### `optim/`

优化器与学习率调度器配置和工厂。

#### `rl/`

强化学习相关模块。

#### `async_inference/`

异步推理相关功能。

#### `transport/`

底层通信抽象。

### 5.3 `tests/`

测试代码按模块分类组织，包含：

- 配置测试
- 数据集测试
- 环境测试
- 机器人测试
- 策略测试
- 脚本测试
- 传输层测试

同时包含：

- `fixtures/`：测试数据
- `mocks/`：模拟对象
- `artifacts/`：测试工件

### 5.4 `docs/`

官方文档源文件，主要是 Hugging Face Docs 风格的 `.mdx` 文档，覆盖：

- 安装
- 数据集
- 各种策略说明
- 不同机器人接入
- benchmark 使用
- processor 机制

### 5.5 `examples/`

示例工程与教程脚本，适合用户快速上手不同场景，例如：

- 数据集处理
- 训练
- HIL
- notebook
- 电话遥操作
- 教学示例

---

## 6. 配置系统设计细节

LeRobot 大量采用 **dataclass + draccus** 组合，这是项目架构的关键。

### 6.1 为什么选 dataclass 配置

优点：

- 类型明确；
- 结构清晰；
- 支持默认值；
- 便于序列化到 JSON；
- 便于 CLI 参数直接覆写字段。

### 6.2 `ChoiceRegistry` 多态注册

许多配置类不是单一实现，而是一组“可选子类型”，如：

- 不同策略配置：`act`、`diffusion`、`pi0`、`smolvla`...
- 不同环境配置：`aloha`、`pusht`、`libero`...

这通过 `draccus.ChoiceRegistry` 实现：

- 配置中只需要给出 `type`
- 系统即可反序列化到对应子类

这也是 CLI 中常见 `--policy.type=...`、`--env.type=...` 能工作的基础。

### 6.3 训练配置 `TrainPipelineConfig`

训练配置不仅包括策略与数据集，还包括：

- 输出目录
- resume 逻辑
- batch size / steps / eval frequency
- optimizer / scheduler
- wandb
- PEFT
- RABC（Reward-Aligned Behavior Cloning）

其中 `validate()` 会做很多实际运行前的修正和检查，例如：

- 从预训练路径加载策略配置；
- 自动补全 `output_dir`；
- 根据策略预设生成 optimizer 和 scheduler；
- 检查推送到 Hub 所需字段；
- 自动推断 RABC 文件位置。

---

## 7. 策略系统设计细节

## 7.1 `PreTrainedPolicy`

所有策略模型共享统一基类 `PreTrainedPolicy`，它定义了几个重要能力：

- 必须持有 `config`
- 必须实现 `forward()`
- 必须实现 `select_action()`
- 必须实现 `predict_action_chunk()`（适用于 action chunking 策略）
- 必须实现 `reset()`
- 必须实现 `get_optim_params()`

这意味着无论底层是 Transformer、Diffusion 还是 RL policy，它们在框架层面都能被统一调度。

## 7.2 预训练模型读写

策略支持标准化存取：

- `save_pretrained()`
- `from_pretrained()`
- `push_to_hub()`

关键实现特点：

- 配置走 `config.json`
- 权重走 `model.safetensors`
- 加载时支持本地路径与 Hub 仓库两种来源
- 默认加载后进入 `eval()` 模式

## 7.3 动态策略工厂

`src/lerobot/policies/factory.py` 中的 `get_policy_class()` 按名称动态导入策略实现，而不是在模块加载时一次性导入全部模型。

这样做有两个好处：

1. 启动更快；
2. 某些策略依赖是可选包，不会因为用户没安装某个模型的依赖就导致整个包导入失败。

## 7.4 策略特征约束

`PreTrainedConfig` 中通过 `input_features` 和 `output_features` 描述策略需要的输入输出特征。

典型特征类型包括：

- `STATE`
- `VISUAL`
- `ENV`
- `ACTION`

这让不同数据源、环境和模型之间的对接更加可检查、可推断。

---

## 8. 数据集系统设计细节

## 8.1 `LeRobotDataset` 的定位

`LeRobotDataset` 是整个项目最核心的基础设施之一。它既是：

- 本地/远程数据集加载器；
- 机器人数据标准格式定义；
- 训练数据读取接口；
- 录制数据写入的目标格式。

## 8.2 数据格式结构

一个典型数据集目录包含：

- `data/`：主数据 parquet 分块
- `meta/`：元数据、统计、任务描述、episode 信息
- `videos/`：每个视觉观测键对应的视频文件

这种结构的优点：

1. **高可移植性**：底层都是通用文件格式；
2. **大规模友好**：采用 chunk 组织，利于大数据集；
3. **流式可读**：Hub 拉取时更适合缓存和分块下载；
4. **多模态统一**：状态、动作、任务、视频保持同步。

## 8.3 数据访问模式

`LeRobotDataset` 支持两种主要模式：

1. **读取现有数据集**
	- 从本地目录读取；
	- 或从 Hugging Face Hub 下载并缓存。

2. **创建/续写数据集**
	- 用于数据采集；
	- 用于把已有外部数据迁移到 LeRobot 格式。

## 8.4 视频处理设计

视频是机器人数据中的关键部分。LeRobot 在这里做了很多工程化处理：

- 支持多种解码后端；
- 支持同步检查，确保帧率和时间戳一致；
- 支持编码参数控制；
- 支持流式编码与批量编码；
- 将视觉帧与 parquet 中的状态/动作对齐。

## 8.5 与 Hub 的关系

数据集可以直接来自 Hugging Face Hub，`LeRobotDataset` 内部会处理：

- revision 选择；
- 本地缓存；
- snapshot 下载；
- 版本兼容检查。

这让“共享数据集—训练—评测—复现”流程统一起来。

---

## 9. Processor 流水线机制

这是 LeRobot 的一个非常重要、也非常有技术含量的设计点。

### 9.1 为什么需要 processor

现实中，策略模型要求的数据形式，与环境/机器人实际给出的原始数据几乎总是不一致的。例如：

- 环境给出 `pixels/top`，模型需要 `observation.images.top`
- 动作是相对位移，但机器人控制器需要绝对位姿
- 图像尺寸不一致，需要裁剪和缩放
- 输入需要归一化，输出需要反归一化
- 有些 benchmark 还需要特殊字段映射

如果这些逻辑直接散落在训练/推理脚本里，会很快失控。

### 9.2 LeRobot 的做法

LeRobot 将它们拆成一个个 **ProcessorStep**，再串成 **Pipeline**：

- `PolicyProcessorPipeline`
- `RobotProcessorPipeline`
- `DataProcessorPipeline`

每个 step 只做一件事，例如：

- 归一化
- 重命名 key
- 动作坐标系转换
- 图像裁剪
- numpy / torch 转换
- 设备迁移

### 9.3 带来的收益

- 结构清晰；
- 便于复用；
- 便于序列化配置；
- 便于不同环境和策略拼装；
- 便于推理和训练共用同一转换逻辑。

### 9.4 环境与策略的桥接

例如在 `policies/factory.py` 中，策略创建时会自动构造前处理与后处理 pipeline，并处理：

- 数据集特征映射到策略特征；
- 环境特征映射到策略特征；
- 相对动作与绝对动作 step 的重新连接；
- 反序列化后的 processor 恢复。

这说明 LeRobot 不是“只有模型”，而是非常强调 **数据流可组合性**。

---

## 10. 环境系统设计细节

### 10.1 `EnvConfig`

环境层的统一抽象是 `EnvConfig`。它定义了：

- `task`
- `fps`
- `features`
- `features_map`
- `gym_id`
- `gym_kwargs`
- `create_envs()`

### 10.2 Gymnasium VectorEnv

LeRobot 默认使用批量环境：

- `SyncVectorEnv`
- `AsyncVectorEnv`

这样评测和训练时可以并行 rollout，提高吞吐。

### 10.3 环境特征映射

环境中的观测键未必与策略侧一致，所以每个环境会定义：

- 特征集合 `features`
- 逻辑映射 `features_map`

例如：

- `pixels/top` 映射到视觉观测
- `agent_pos` 映射到状态观测
- `environment_state` 映射到环境状态

### 10.4 Hub 托管环境

LeRobot 还支持 `HubEnvConfig`，允许环境逻辑托管在 Hugging Face Hub 上，通过远程代码构造环境。

这增强了可扩展性，但也意味着需要注意远程代码安全。仓库在 `SECURITY.md` 中明确建议：

- 尽量使用安全格式；
- 审核远程代码；
- 固定 revision 避免不受控更新。

---

## 11. 训练流程技术细节

`lerobot-train` 是训练主入口，对应 `src/lerobot/scripts/lerobot_train.py`。

它的高层流程如下：

1. 解析 `TrainPipelineConfig`
2. 做配置验证 `cfg.validate()`
3. 初始化 `Accelerator`
4. 创建数据集
5. 创建评测环境（如果需要）
6. 创建策略模型
7. 按策略预设创建 optimizer / scheduler
8. 进入训练循环
9. 周期性记录日志、保存 checkpoint、执行评测
10. 需要时推送模型到 Hub

### 11.1 Accelerate 集成

训练脚本集成了 `accelerate`，用于：

- 单机 / 分布式训练统一封装；
- 自动混合精度；
- DDP 包装；
- 梯度同步与梯度裁剪。

### 11.2 训练更新逻辑

`update_policy()` 负责单步更新，主要过程包括：

- 前向计算
- loss 构造
- accelerator.backward
- 梯度裁剪
- optimizer.step
- scheduler.step

### 11.3 RABC 支持

训练脚本中内置了 **RA-BC / Reward-Aligned Behavior Cloning** 支持，可根据每个样本的奖励权重加权 loss。

这表明项目不仅支持普通监督学习，也在尝试更高级的“奖励引导模仿学习”训练范式。

### 11.4 Checkpoint 管理

训练支持：

- 自动保存 checkpoint
- resume 继续训练
- 维护 last checkpoint
- 训练期间定期评测

这部分逻辑主要位于 `src/lerobot/common/`。

---

## 12. 评测流程技术细节

`lerobot-eval` 对应 `src/lerobot/scripts/lerobot_eval.py`。

### 12.1 评测目标

给定一个策略与一个环境，运行多 episode rollout，并输出：

- reward
- success
- done
- 可选 observation 轨迹

### 12.2 rollout 机制

评测流程中的 `rollout()` 做了几件关键事情：

1. reset policy 和 env
2. 预处理 observation
3. 推断任务描述 `task`
4. 经过 env preprocessor 与 policy preprocessor
5. 调用 `policy.select_action()`
6. 动作经过 postprocessor 再送入环境
7. 收集 reward / success / done
8. 持续直到所有环境结束或到达最大步数

### 12.3 为什么评测也依赖 processor

因为环境和模型接口不一定天然一致。评测和训练共用 processor 设计，能保证：

- 特征处理一致；
- 输入输出格式一致；
- benchmark 特定适配一致。

### 12.4 视频与可视化

评测侧还支持保存 rollout 视频，便于人工检查策略行为质量。

---

## 13. Hugging Face Hub 集成细节

LeRobot 与 Hugging Face Hub 的整合非常深，不是简单“下载模型文件”。

### 13.1 `HubMixin`

`HubMixin` 为多个对象提供统一能力：

- `save_pretrained()`
- `from_pretrained()`
- `push_to_hub()`

这个 mixin 被配置类、策略类等复用。

### 13.2 Hub 侧内容类型

LeRobot 可以与 Hub 上的以下资源协同：

- 数据集
- 预训练策略
- checkpoint 配置
- 模型卡片 / README
- 环境代码（某些场景）

### 13.3 安全格式与建议

仓库在 `SECURITY.md` 中强调：

- 模型优先使用 `safetensors`
- 谨慎使用 `trust_remote_code=True`
- 最好固定 `revision`

这对涉及真实机器人控制的项目尤其重要。

---

## 14. CLI 工具体系

从 `pyproject.toml` 可见，项目暴露了较完整的命令行工具集。

### 14.1 训练与评测

- `lerobot-train`
- `lerobot-train-tokenizer`
- `lerobot-eval`

### 14.2 数据集相关

- `lerobot-dataset-viz`
- `lerobot-edit-dataset`
- `convert_dataset_v21_to_v30.py`
- `augment_dataset_quantile_stats.py`

### 14.3 硬件与采集

- `lerobot-record`
- `lerobot-replay`
- `lerobot-teleoperate`
- `lerobot-calibrate`
- `lerobot-setup-motors`
- `lerobot-setup-can`
- `lerobot-find-port`
- `lerobot-find-cameras`
- `lerobot-find-joint-limits`

### 14.4 信息与调试

- `lerobot-info`
- `lerobot-imgtransform-viz`

这意味着 LeRobot 不只是“库”，也是一个成熟的命令行工作台。

---

## 15. 打包、发布与安装机制

### 15.1 `pyproject.toml` 是单一事实来源

项目使用 `pyproject.toml` 管理：

- 包元数据
- 依赖声明
- extras
- 脚本入口
- Ruff / Mypy / Bandit / Typos 配置

### 15.2 `setup.py` 的作用

`setup.py` 很精简，主要用于：

- 读取 `pyproject.toml` 中版本号；
- 读取 `README.md`；
- 将 README 中本地图片链接替换为 GitHub raw URL；
- 供打包时生成 PyPI 长描述。

这是一种比较务实的做法：核心配置放 `pyproject.toml`，少量兼容逻辑放 `setup.py`。

### 15.3 安装建议

项目文档建议优先使用：

- `pip install lerobot`
- 或开发环境用 `uv sync --locked ...`

对于不同平台和完整依赖场景，也提供了：

- `requirements-ubuntu.txt`
- `requirements-macos.txt`

---

## 16. 代码质量、测试与类型系统

### 16.1 Ruff

项目使用 Ruff 负责：

- 风格检查
- import 排序
- 常见 bug 检测
- pyupgrade
- 简化建议

目标 Python 版本为 `py312`。

### 16.2 Mypy 渐进式启用

项目当前采用**渐进式类型检查**策略，并未全仓开启 strict。当前更严格的模块包括：

- `lerobot.envs`
- `lerobot.configs`
- `lerobot.optim`
- `lerobot.model`
- `lerobot.cameras`
- `lerobot.motors`
- `lerobot.transport`

这说明仓库在持续推进类型安全，但兼顾历史代码与迭代速度。

### 16.3 测试组织

测试位于 `tests/`，按功能域细分，适合针对模块开发做局部回归。

仓库说明中推荐的关键命令包括：

- `uv run pytest tests -svv --maxfail=10`
- `DEVICE=cuda make test-end-to-end`
- `pre-commit run --all-files`

---

## 17. 文档与示例生态

LeRobot 的文档不仅说明 API，还覆盖了大量实际场景：

- 各种机器人接入文档
- benchmark 文档
- processor 介绍
- 数据集格式说明
- 多 GPU / PEFT / VLA 模型训练说明

示例目录 `examples/` 则提供了更贴近用户操作的代码样板。

因此，项目学习路径通常是：

1. 阅读本 README 了解全局；
2. 进入 `docs/source/` 对应主题深入；
3. 参考 `examples/` 落地；
4. 再阅读 `src/lerobot/` 具体模块源码。

---

## 18. 项目的工程特点总结

从源码实现看，LeRobot 有几个很鲜明的工程特征。

### 18.1 强调统一抽象，而不是单点脚本

它不是“若干训练脚本的堆砌”，而是围绕以下抽象构建：

- Config
- Policy
- Dataset
- Env
- Processor
- HubMixin

这些抽象相互解耦，又能通过工厂函数拼接。

### 18.2 强调可组合性

通过 processor pipeline、ChoiceRegistry、多种 extras，项目允许用户自由组合：

- 数据源
- 环境
- 模型
- 硬件
- 训练策略

### 18.3 强调真实机器人与研究工作流兼容

这个项目同时服务：

- 研究人员做 benchmark 和模型对比；
- 工程人员做真实硬件接入；
- 社区用户共享数据和模型；
- 开发者扩展新机器人/新策略/新环境。

### 18.4 强调 Hub 原生协作

很多项目把“模型上传”当附加功能，而 LeRobot 把 Hub 直接当作工作流的一部分。

---

## 19. 适合哪些用户

LeRobot 特别适合以下人群：

### 19.1 机器人学习研究者

如果你关注：

- imitation learning
- VLA
- offline / online policy training
- benchmark evaluation

那么 LeRobot 提供了比较完整的基线基础设施。

### 19.2 真实机器人开发者

如果你需要：

- 接入机械臂与相机
- 采集 demonstration 数据
- 做 teleoperation
- 统一控制接口

LeRobot 也有对应模块支持。

### 19.3 数据集与模型共享者

如果你想把机器人数据集和策略模型发布到 Hugging Face Hub，并保持标准格式和可复现性，这个项目非常合适。

---

## 20. 使用与阅读建议

对于第一次接触该项目的用户，建议按以下顺序理解：

### 路线 A：想快速使用

1. 阅读 `README.md` / `README_CN.md`
2. 查看安装文档 `docs/source/installation.mdx`
3. 运行 `lerobot-info`
4. 选择一个现成数据集和策略跑通 `lerobot-eval`
5. 再尝试 `lerobot-train`

### 路线 B：想研究架构

1. 先看 `pyproject.toml` 理解依赖与脚本入口
2. 看 `configs/` 理解配置系统
3. 看 `policies/pretrained.py` 与 `policies/factory.py`
4. 看 `datasets/lerobot_dataset.py`
5. 看 `processor/` 理解数据流桥接
6. 看 `scripts/lerobot_train.py` / `lerobot_eval.py`

### 路线 C：想扩展项目

1. 新增策略：参考 `policies/` 下现有实现
2. 新增环境：参考 `envs/configs.py` 的注册方式
3. 新增处理步骤：参考 `processor/` 中各类 `ProcessorStep`
4. 新增机器人硬件：参考 `robots/`、`motors/`、`cameras/`

---

## 21. 结语

LeRobot 的价值不只在于“提供几个现成机器人模型”，而在于它把机器人学习中最难统一的几件事——**硬件接口、数据格式、训练流程、评测流程、共享分发**——放进了一个一致的工程框架中。

从源码层面看，它具备几个非常成熟的技术特征：

- 以 `dataclass + draccus` 构建的配置驱动架构；
- 以 `PreTrainedPolicy` 为中心的模型统一接口；
- 以 `LeRobotDataset` 为中心的数据标准化；
- 以 `ProcessorPipeline` 为中心的数据流桥接机制；
- 以 Hugging Face Hub 为中心的开放协作模式。

如果你希望：

- 系统理解整个 LeRobot 项目；
- 在其基础上训练或评测机器人策略；
- 接入自己的机器人、环境或模型；
- 参与开源贡献；

那么这个仓库已经提供了非常扎实的基础设施。

---

## 22. 参考入口

- 英文总览：`README.md`
- 中文文档：`README_CN.md`
- 安装与官方文档：`docs/source/`
- 示例代码：`examples/`
- 核心源码：`src/lerobot/`
- 测试目录：`tests/`
- AI 使用规范：`AI_POLICY.md`
- 安全说明：`SECURITY.md`

欢迎结合源码与官方文档继续深入阅读。
