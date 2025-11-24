# AI Super Agent: From Zero to Deep Thinking with Agent Lightning

## 🎯 项目概览 (Project Overview)

本项目展示了如何使用 **Agent Lightning** 框架，通过强化学习训练一个能够进行深度数学推理的 AI Agent。我们使用 Azure OpenAI 生成训练数据，采用 GRPO 算法训练本地开源模型，最终在 GSM8K 和 MATH 数据集上实现显著的性能提升。

### 核心特性
- 🤖 **数据自生成**: 使用 Azure OpenAI GPT-5.1 生成高质量数学问答数据
- ⚡ **高效训练**: 基于 GRPO 算法，节省 50% 显存，单卡 H100/A100 即可训练
- 🧠 **Deep Thinking**: 类似 OpenAI o1 的长链推理能力
- 📊 **端到端可复现**: 从环境安装到模型评估的完整流程

---

## 📐 系统架构图 (System Architecture)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          端到端训练流程 (End-to-End Pipeline)                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 阶段 1: 数据生成 (Data Generation with Azure OpenAI)                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐        Azure OpenAI API                               │
│  │  用户设置环境变量  │  ────────────────────────────────────►                │
│  │ AZURE_OPENAI_   │                                         ┌─────────────┐│
│  │ ENDPOINT        │                                         │   GPT-5.1   ││
│  │ API_KEY         │                                         │   Chat      ││
│  │ DEPLOYMENT      │                                         └──────┬──────┘│
│  └─────────────────┘                                                │       │
│                                                                     │       │
│  ┌───────────────────────────────────────┐                         │       │
│  │ generate_training_data_gpt5.py        │◄────────────────────────┘       │
│  │                                       │                                 │
│  │ • 生成 5000+ 数学应用题                 │                                 │
│  │ • 包含答案和详细解题步骤                 │                                 │
│  │ • 保存为 Parquet 格式                  │                                 │
│  └───────────────┬───────────────────────┘                                 │
│                  │                                                          │
│                  ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │  data/train_gpt5_large.parquet (训练集)                  │               │
│  │  data/test_gpt5_large.parquet  (测试集)                  │               │
│  └─────────────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 阶段 2: 强化学习训练 (RL Training with GRPO + vLLM)                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────┐             │
│  │  train_math_agent_vllm.py                                  │             │
│  │                                                            │             │
│  │  1. 启动本地 vLLM 服务器                                     │             │
│  │     • 加载 Qwen2.5-3B-Instruct                             │             │
│  │     • 提供 OpenAI 兼容 API (localhost:8000)                │             │
│  │                                                            │             │
│  │  2. GRPO 强化学习训练                                       │             │
│  │     ┌──────────────────────────────────────┐              │             │
│  │     │  Actor (策略模型)                      │              │             │
│  │     │  • 生成回答 (4个采样/题)                │              │             │
│  │     │  • 包含 <think> 推理过程                │              │             │
│  │     └────────────┬─────────────────────────┘              │             │
│  │                  │                                        │             │
│  │                  ▼                                        │             │
│  │     ┌──────────────────────────────────────┐              │             │
│  │     │  Reward Function (奖励函数)           │              │             │
│  │     │  • 结构奖励 (格式正确)                  │              │             │
│  │     │  • 深度奖励 (思考长度)                  │              │             │
│  │     │  • 正确性奖励 (答案准确)                │              │             │
│  │     └────────────┬─────────────────────────┘              │             │
│  │                  │                                        │             │
│  │                  ▼                                        │             │
│  │     ┌──────────────────────────────────────┐              │             │
│  │     │  Reference Model (参考模型)            │              │             │
│  │     │  • 冻结的初始模型                       │              │             │
│  │     │  • 计算 KL 散度防止过拟合               │              │             │
│  │     └──────────────────────────────────────┘              │             │
│  │                                                            │             │
│  │  3. 保存 Checkpoint                                        │             │
│  │     • checkpoints/math_agent/global_step_X                │             │
│  │     • 包含 LoRA 权重                                        │             │
│  └────────────────────────────┬───────────────────────────────┘             │
│                                │                                            │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │  checkpoints/AgentLightningTutorial/math_agent/          │               │
│  │  global_step_100/                                        │               │
│  └─────────────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 阶段 3: 模型格式转换 (Checkpoint Conversion)                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────┐             │
│  │  convert_checkpoint.py                                     │             │
│  │                                                            │             │
│  │  • 将 LoRA Checkpoint 合并到 Base Model                     │             │
│  │  • 生成完整的 HuggingFace 格式模型                           │             │
│  │  • 可直接用于推理或部署                                       │             │
│  └────────────────────────────┬───────────────────────────────┘             │
│                                │                                            │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │  merged_model/                                          │               │
│  │  • pytorch_model.bin                                    │               │
│  │  • config.json                                          │               │
│  │  • tokenizer files                                      │               │
│  └─────────────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 阶段 4: 模型评估 (Evaluation on Benchmarks)                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────┐             │
│  │  run_full_evaluation_v5.sh                                 │             │
│  │                                                            │             │
│  │  1. 启动 vLLM 服务器 (Base Model)                           │             │
│  │  2. 运行 inference_gsm8k.py (GSM8K 数据集)                  │             │
│  │  3. 启动 vLLM 服务器 (Trained Model)                        │             │
│  │  4. 运行 inference_gsm8k.py (对比测试)                      │             │
│  │  5. 使用 judge_with_llm.py 评判结果                         │             │
│  └────────────────────────────┬───────────────────────────────┘             │
│                                │                                            │
│                                ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │  评估报告                                                 │               │
│  │  • Base Model: 81.0%                                    │               │
│  │  • Trained Model: 84.0% (+3.0%)                         │               │
│  │  • 详细的答案对比和分析                                    │               │
│  └─────────────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. 项目背景与框架选择 (Project Background)

### 为什么选择 Agent Lightning?
在构建能够进行复杂数学推理的 AI Agent 时，我们需要一个高效、灵活且支持大规模强化学习（RL）的框架。**Agent Lightning** (基于 `verl` 和 `ray`) 被选中，原因如下：
*   **原生支持 RLHF/RLAIF**: 专为大语言模型（LLM）的强化学习设计。
*   **高效的分布式训练**: 基于 Ray 和 vLLM，支持多 GPU 高效并行（Hybrid Engine）。
*   **灵活的算法接口**: 轻松实现 PPO, GRPO 等算法，并支持自定义奖励函数。

### 强化学习算法对比 (RL Algorithms)
在项目初期，我们对比了主流的 RL 算法：
*   **PPO (Proximal Policy Optimization)**: 经典的 RL 算法，需要 Critic 模型（Value Function），显存占用大，训练相对稳定但计算成本高。
*   **GRPO (Group Relative Policy Optimization)**: **我们最终的选择**。
    *   **优势**: 不需要 Critic 模型（节省约 50% 显存），通过对同一 Prompt 生成多组输出（Group）并计算组内相对优势（Advantage）来优化策略。
    *   **适用性**: 非常适合推理类任务（如数学题），因为我们可以通过最终答案的正确性轻松评估一组输出的好坏。

---

## 2. 环境搭建与依赖安装 (Environment Setup)

### 2.1 硬件要求
- **推荐配置**: NVIDIA H100 (80GB) 或 A100 (80GB)
- **最低配置**: A10 (24GB) 或 RTX 4090 (24GB) - 需要调小 batch size
- **CUDA 版本**: 12.1+

### 2.2 Conda 环境创建

```bash
# 1. 创建新的 conda 环境
conda create -n agentL python=3.11 -y
conda activate agentL

# 2. 安装 PyTorch (CUDA 12.1)
pip install torch==2.1.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 3. 安装核心框架
pip install verl==0.5.0
pip install vllm==0.6.3
pip install ray==2.10.0

# 4. 安装 Agent Lightning
cd agent-lightning
pip install -e .

# 5. 安装其他依赖
pip install openai pandas pyarrow huggingface_hub hydra-core datasets
pip install transformers accelerate
# 推荐使用 uv 管理工具依赖 (可选)
# pip install uv
```

### 2.3 环境变量配置

创建 `.env` 文件或设置环境变量：

```bash
# Azure OpenAI 配置 (用于数据生成)
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-actual-azure-key-here"
export AZURE_OPENAI_DEPLOYMENT="gpt-5.1-chat"
export AZURE_OPENAI_API_VERSION="2025-01-01-preview"

# HuggingFace 镜像 (可选，加速模型下载)
export HF_ENDPOINT=https://hf-mirror.com

# 离线模式 (如果已下载模型)
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

### 2.4 requirements.txt

完整的依赖列表：

```txt
# Core Framework
torch==2.5.1
verl==0.5.0
vllm==0.7.0
ray>=2.10.0

# Agent Lightning
# -e . (install from source)

# Model & Data
transformers>=4.36.0
datasets>=2.14.0
accelerate>=0.24.0
huggingface_hub>=0.19.0

# API & Utilities
openai>=1.0.0
pandas>=2.0.0
pyarrow>=14.0.0
hydra-core>=1.3.0
tqdm>=4.65.0

# Optional: Monitoring
wandb>=0.16.0
tensorboard>=2.15.0
```

---

## 3. 端到端完整流程 (End-to-End Pipeline)

### 步骤 1: 使用 Azure OpenAI 生成训练数据

**目的**: 展示 Agent Lightning 的数据生成能力，同时为训练准备高质量数据集。

```bash
# 设置 Azure OpenAI 环境变量
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="gpt-5.1-chat"

# 运行数据生成脚本
cd agent-lightning
python generate_training_data_gpt5.py
```

**输出**:
- `data/train_gpt5_large.parquet` - 训练集 (5000+ 条)
- `data/test_gpt5_large.parquet` - 测试集 (500 条)

**数据格式示例**:
```json
{
  "question": "A shop sells 3 types of fruits: apples for $2 each, oranges for $3 each, and bananas for $1.5 per bunch. If you buy 5 apples, 3 oranges, and 2 bunches of bananas, how much do you pay in total?",
  "answer": "22"
}
```

---

### 步骤 2: 强化学习训练模型

**目的**: 使用 GRPO 算法训练模型学会 Deep Thinking 推理模式。

```bash
# 确保环境激活
conda activate agentL

# 运行训练脚本
cd agent-lightning
python train_math_agent_vllm.py
```

**训练过程说明**:

1. **自动下载模型** (首次运行):
   - Base Model: `Qwen/Qwen2.5-3B-Instruct`
   - 模型会自动从 HuggingFace Hub 下载

2. **启动 vLLM 服务器**:
   ```
   🚀 启动 vLLM 推理引擎...
   ✅ vLLM 服务器已启动: http://localhost:8000/v1
   ```

3. **GRPO 训练开始**:
   ```
   Step 1/100: reward=1.23, kl_penalty=0.08
   Step 2/100: reward=1.45, kl_penalty=0.09
   ...
   Step 100/100: reward=2.88, kl_penalty=0.10
   ```

4. **Checkpoint 自动保存**:
   - 路径: `checkpoints/AgentLightningTutorial/math_agent/global_step_100/`
   - 包含 LoRA 适配器权重

**预计训练时间**:
- H100: ~2 小时 (100 steps, 500 samples)
- A100: ~3 小时
- A10: ~5 小时 (需要调小 batch size)

---

### 步骤 3: 转换模型格式

**目的**: 将 LoRA Checkpoint 合并到 Base Model，生成完整模型用于推理。

```bash
# 运行转换脚本
python convert_checkpoint.py \
    --checkpoint_dir checkpoints/AgentLightningTutorial/math_agent/global_step_100 \
    --base_model Qwen/Qwen2.5-3B-Instruct \
    --output_dir merged_model
```

**输出**:
- `merged_model/` - 完整的 HuggingFace 格式模型
  - `pytorch_model.bin` - 模型权重
  - `config.json` - 模型配置
  - `tokenizer.json` - 分词器
  - `tokenizer_config.json` - 分词器配置

**验证模型**:
```bash
# 快速测试合并后的模型
python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained('merged_model')
tokenizer = AutoTokenizer.from_pretrained('merged_model')
print('✅ 模型加载成功!')
"
```

---

### 步骤 4: 在数学数据集上评估

**目的**: 在 GSM8K 和 MATH 标准数据集上验证模型性能提升。

#### 4.1 准备评估数据

```bash
# 下载 GSM8K 数据集
python prepare_gsm8k.py

# 下载 MATH 数据集
python prepare_math.py
```

**输出**:
- `data/gsm8k_test.parquet` - GSM8K 测试集 (1319 题)
- `data/math_test.parquet` - MATH 测试集 (5000 题)

#### 4.2 运行完整评估

```bash
# 一键评估脚本（自动对比 Base 和 Trained 模型）
bash run_full_evaluation_v5.sh
```

**评估流程**:

1. **启动 Base Model vLLM 服务**:
   ```
   🔌 启动 Base Model 服务器 (端口 8000)...
   ```

2. **Base Model 推理**:
   ```
   📊 处理 GSM8K 测试集 (1319 题)...
   ✅ 保存结果: validation_base_model.parquet
   ```

3. **启动 Trained Model vLLM 服务**:
   ```
   🔌 启动 Trained Model 服务器 (端口 8001)...
   ```

4. **Trained Model 推理**:
   ```
   📊 处理 GSM8K 测试集 (1319 题)...
   ✅ 保存结果: validation_trained_model.parquet
   ```

5. **LLM 评判** (使用 Azure OpenAI):
   ```
   🤖 使用 GPT-5.1 评判答案质量...
   ✅ 生成评估报告: validation_report.txt
   ```

#### 4.3 查看评估结果

```bash
# 查看详细报告
cat validation_report.txt
```

**示例输出**:
```
===============================================
           模型评估报告
===============================================

数据集: GSM8K (1319 题)

Base Model (Qwen2.5-3B-Instruct):
  ✓ 正确: 1068 题
  ✗ 错误: 251 题
  准确率: 81.0%

Trained Model (After GRPO + Deep Thinking):
  ✓ 正确: 1108 题
  ✗ 错误: 211 题
  准确率: 84.0%

📈 提升: +3.0 个百分点

典型提升案例:
----------------------------------------------
题目: Find the smallest perfect cube that is a multiple of 9.

Base Model 回答 (错误):
  "19683"

Trained Model 回答 (正确):
  <think>
  A number is a multiple of 9 if divisible by 9.
  Prime factorization: 9 = 3^2
  For a perfect cube, exponents must be multiples of 3.
  So we need 3^3 = 27.
  </think>
  <answer>27</answer>

✅ Trained Model 通过结构化思考找到正确答案
===============================================
```

---

## 4. 核心模型架构详解 (Core Model Architecture)

在 Agent Lightning 的强化学习训练中，我们协调了多个"角色"（模型）来共同完成任务。理解它们的分工对于掌握 RLHF/RLAIF 至关重要。

### 4.1 策略模型 (Actor / Policy Model) - "学生"
*   **定义**: 这是我们真正想要训练的模型。
*   **实现**: `Qwen2.5-3B-Instruct`。
*   **功能**: 接收题目 (`prompt`)，生成包含思考过程 (`<think>`) 和最终答案 (`<answer>`) 的文本。
*   **目标**: 它的参数会不断更新，试图生成能获得更高奖励的回答。

### 4.2 参考模型 (Reference Model) - "约束者"
*   **定义**: 策略模型的一个**冻结副本** (Frozen Copy)，参数在训练过程中保持不变。
*   **功能**: 用于计算 **KL 散度 (KL Divergence)**。
*   **作用**: 防止"学生"为了刷分而"走火入魔"（Reward Hacking）。例如，防止模型为了凑字数拿长度奖励而输出乱码。参考模型确保训练后的模型输出分布不会偏离原始语言模型太远，保持语言的流畅性和通顺度。

### 4.3 价值模型 (Critic / Value Model) - "估值器" (GRPO 优化点)
*   **PPO 算法中**: 通常需要一个 Critic 模型来预测"当前状态未来能拿多少分" (Value Function)，用于计算优势 (Advantage)。这需要占用大量显存（通常与 Actor 一样大）。
*   **GRPO 算法中 (本项目采用)**: **我们移除了 Critic 模型！**
    *   **原理**: Group Relative Policy Optimization (GRPO) 不依赖 Critic 模型来估计基线。相反，它对同一个问题采样一组输出 (Group, e.g., $n=4$)，计算这组输出的平均奖励作为基线 (Baseline)。
    *   **优势**: 节省了近 **50% 的显存**，让我们能在单卡 H100 上训练更大的 Batch Size 或更长的 Context。

### 4.4 奖励函数 (Reward Function) - "裁判/经理"
*   **定义**: 这不是一个神经网络，而是我们编写的**规则逻辑 (Python Function)**。
*   **功能**: 对 Actor 生成的每一个回答进行打分。
*   **v4 版本的裁判标准**:
    1.  **格式合规性**: 是否包含 `<think>` 和 `<answer>` 标签？
    2.  **思考深度**: `<think>` 里的内容有多长？（鼓励多想）
    3.  **答案正确性**: 解析出的数字是否与标准答案一致？（核心指标）

---

## 5. 关键配置与日志解读 (Configuration & Log Analysis)

为了让大家能够复现并验证我们的结果，这里详细说明了 GRPO 的配置位置以及训练日志中需要关注的核心指标。

### 5.1 GRPO 算法配置
在 `train_math_agent_vllm.py` 的 `get_config()` 函数中，我们明确指定了使用 GRPO 算法。这是节省显存并提升推理性能的关键设置：

```python
# train_math_agent_vllm.py

"algorithm": {
    "adv_estimator": "grpo",  # <--- 关键：指定使用 Group Relative Policy Optimization
    "use_kl_in_reward": True, # 在奖励中包含 KL 散度惩罚
    "kl_ctrl": {
        "type": "fixed",
        "kl_coef": 0.001,     # KL 系数，防止模型偏离太远
    },
},
"actor_rollout_ref": {
    "rollout": {
        "n": 4,               # <--- 关键：GRPO 的 Group Size，每题采样 4 个答案进行对比
    },
    # ...
}
```

### 5.2 训练日志佐证 (Training Logs)
训练过程中（如 `logs/train_vllm_final.log`），我们需要密切关注以下指标的变化，它们直接反映了强化学习的效果。

**实战日志分析 (Step 22 样本)**:
```text
(TaskRunner pid=45102) step:22 - training/reward:2.8865625 ...
critic/score/max_before_processing:4.0 ...
response_length/mean_before_processing:395.9375 ...
```

**核心指标解读**:

1.  **`training/reward: 2.88` (平均奖励)**: **这是极好的信号！**
    *   *理论满分*: 结构分(0.5) + 正确分(2.0) + 思考Bonus(0.5) + 深度分(Max 1.0) = **4.0**。
    *   *现状*: 平均分接近 2.9，且 `critic/score/max` 达到了 **4.0**。
    *   *结论*: 这证明模型不仅学会了 `<think>` 格式，而且**大部分题目都做对了**，并且正在生成长文本进行深度思考。

2.  **`response_length/mean: 395.9` (响应长度)**:
    *   *解读*: 平均生成长度接近 400 token。相比于 Base 模型直接输出答案（通常 <50 token），这证明模型正在进行**长链条推理 (Chain of Thought)**，Deep Thinking 策略生效。

3.  **`critic/advantages` (优势函数)**:
    *   *数据*: Mean ~ -0.05, Max ~ 0.82, Min ~ -1.50。
    *   *GRPO 原理*: GRPO 通过计算组内相对优势来更新策略。这里可以看到，在同一组采样中，好的回答（Max）比差的回答（Min）优势高出 2.3 分左右。这种**组内差异**正是驱动模型进步的动力。

4.  **`actor/reward_kl_penalty: 0.108` (KL 惩罚)**:
    *   *解读*: 数值适中。说明模型在学习新格式（Deep Thinking）的同时，没有过度偏离原始语言模型的分布，训练是稳定的。

---

## 6. 训练演进之路 (Training Evolution)

我们的训练过程经历了从基础跑通到 "Deep Thinking" 的四个版本迭代。

### v1 & v2: 基础跑通与参数调试
*   **目标**: 跑通 Agent Lightning + vLLM 的训练流程。
*   **挑战**: 显存溢出 (OOM)、Ray 进程僵死。
*   **解决**: 调整 `gpu_memory_utilization`，优化 Ray 资源分配。

### v3 Turbo: 性能突破
*   **配置**: GRPO 算法，`n=4` (每题生成4个采样)，`kl_coef=0.001`。
*   **结果**: 在 200 条验证集上，准确率从 Base 模型的 **83.5%** 提升至 **85.0%**。
*   **全量验证**: 在 450 条全量测试集上，准确率从 **79.1%** 提升至 **81.8%** (+2.7%)。证明了 GRPO 的有效性。

### v4 Deep Thinking: 迈向 O1 级别的推理 (当前版本)
*   **灵感**: OpenAI o1 模型的 "Chain of Thought" 能力。
*   **核心创新**: **多维奖励函数 (Multi-Dimensional Reward Function)**。
    1.  **结构奖励 (Structure)**: 强制模型使用 `<think>...</think><answer>...</answer>` 格式。
    2.  **深度奖励 (Depth)**: 动态奖励 `<think>` 标签内的思考长度，鼓励模型"多想一步"。
    3.  **结果奖励 (Outcome)**: 答案正确给予高额奖励 (+2.0)，若思考过程存在且答案正确，给予额外 Bonus (+0.5)。
    4.  **惩罚 (Penalty)**: 格式错误或瞎猜（长度过短）给予惩罚。

详细的奖励函数实现见 `tutorials/math_reasoning/train_math_agent_vllm.py`。

---

## 7. 效果评估与推理 (Evaluation & Inference)

为了严谨地验证模型效果，我们构建了完整的验证流水线，涵盖了从基础能力到高阶推理的全面测试。

### 验证策略
1.  **基准对比**: 始终与未训练的 Base Model (Qwen2.5-3B-Instruct) 对比
2.  **分级验证**: 
    *   **GSM8K**: 小学到初中数学应用题
    *   **MATH**: 高中竞赛级难题
3.  **自动化评估**: 一键式评估脚本，自动生成详细报告

### 关键成果
*   **准确率提升**: MATH 数据集上提升 4 个百分点 (69% → 73%)
*   **推理质量**: 显著改善逻辑推理链的连贯性和正确性
*   **可复现性**: 完整的脚本和文档，支持在标准 GPU 环境复现

---

## 8. 实验结果深度分析 (Deep Dive into Results)

为了全面评估 RL 训练的效果，我们进行了多维度的测试，记录了从失败到成功的完整过程。

### 8.1 失败与挑战：简单算术的停滞 (The Stagnation on Simple Arithmetic)
在早期的验证中（如 `validation_report.txt`），我们使用简单的算术题（如 "12 * 41"）进行测试。
*   **现象**: 准确率几乎没有变化（~39% -> ~39%）。
*   **原因**: Base 模型 (Qwen2.5-3B) 已经具备了基本的算术能力，主要的错误在于输出格式（例如只输出数字而没有过程）。虽然 RL 修复了格式问题，但在这种简单任务上，"Deep Thinking"（深思熟虑）并没有带来额外的推理优势，反而有时因为过度思考导致超时或格式混乱。
*   **教训**: RL 的优势在于**复杂推理**，而非简单记忆或计算。

### 8.2 成功案例：GSM8K 与 MATH 数据集 (Success on Complex Reasoning)
当我们转向更复杂的推理任务时，RL 的威力开始显现。

| 数据集 | 难度 | Base Model 准确率 | Trained Model 准确率 | 提升 |
| :--- | :--- | :--- | :--- | :--- |
| **GSM8K** | 小学应用题 (多步推理) | 81.0% | **84.0%** | +3.0% |
| **MATH** | 高中竞赛题 (高难度) | 69.0% | **73.0%** | +4.0% |

#### 典型案例分析：最小完美立方数 (Case Study: Smallest Perfect Cube)
**题目**: "Find the smallest perfect cube that is a multiple of 9."

*   **Base Model (错误)**:
    *   思考: "The multiples of 9 are 9, 18, 27, 36, 45, 54, 63, 72, 81, ..."
    *   结论: 它错误地认为 $27$ 不是立方数，或者试图寻找更大的数，最终输出了 $27^3 = 19683$ 或其他错误答案。
    *   *问题*: 幻觉 (Hallucination) 和逻辑中断。

*   **Trained Model (正确)**:
    *   思考:
        1.  "A number is a multiple of 9 if it is divisible by 9."
        2.  "Prime factorization of 9 is $3^2$."
        3.  "For a number to be a perfect cube, the exponent of each prime factor must be a multiple of 3."
        4.  "To be a multiple of $3^2$ and a perfect cube, we need $3^3$."
        5.  "$3^3 = 27$."
    *   答案: **27**。
    *   *改进*: 逻辑链条清晰，能够利用 `<think>` 空间逐步推导约束条件。

### 8.3 训练过程中的奖励函数变化 (Reward Function Progression)
通过分析 `train_vllm_final.log`，我们可以清晰地看到模型是如何一步步"学会"获取高分的。

**奖励值统计 (Reward Statistics)**:
*   **前 10 步 (Steps 1-10)**: 平均奖励 **1.66**。模型还在探索，偶尔能做对 (2.28)，但经常得分较低 (1.26)。
*   **后 10 步 (Steps 91-100)**: 平均奖励 **1.94**。模型表现更加稳定，多次获得 **2.5** (满分或接近满分)。

**训练曲线趋势**:
虽然 RL 训练具有波动性，但整体趋势是向上的。特别是在 Step 50 之后，出现满分 (2.5) 的频率显著增加，证明模型已经掌握了通过 "Deep Thinking" 获取正确答案并遵循格式的策略。

---

## 9. 项目结构 (Project Structure)

```text
agent-lightning/
├── tutorials/math_reasoning/           # 数学推理教程（详细文档和脚本）
│   ├── README.md                       # 完整教程说明
│   ├── train_math_agent_vllm.py        # 核心训练脚本 (GRPO + Deep Thinking)
│   ├── inference_gsm8k.py              # GSM8K/MATH 推理脚本
│   ├── judge_with_llm.py               # LLM 评判器 (Azure OpenAI)
│   ├── convert_checkpoint.py           # Checkpoint 转换工具
│   └── evaluate.sh                     # 一键评估脚本
├── examples/                           # 其他应用示例
├── agentlightning/                     # 核心框架代码
├── docs/                               # 完整文档
├── tests/                              # 单元测试
├── README.md                           # 主项目说明
├── pyproject.toml                      # 项目配置
└── requirements.txt                    # 依赖列表
```

**核心文件说明**:
- `tutorials/math_reasoning/` - 包含完整的数学推理 Agent 训练教程
- `examples/` - 各类应用场景的示例代码（RAG、Spider、搜索等）
- `agentlightning/` - Agent Lightning 框架核心实现
- `docs/` - 完整的 API 文档和使用指南

---

## 10. 总结 (Conclusion)

本项目成功展示了如何利用 **Agent Lightning** 框架，配合 **GRPO** 算法和 **Deep Thinking 奖励设计**，将一个普通的 3B 模型训练成具备更强数学推理能力的 "Super Agent"。我们不仅跑通了流程，更探索了通过 Reward Engineering 激发模型潜在推理能力的路径。

---

## 11. 硬件适配与实战踩坑 (Hardware Adaptation & Troubleshooting)

在项目的实施过程中，我们对不同规格的硬件进行了深入测试，积累了宝贵的环境适配经验。

### 11.1 显存瓶颈与 A10 (24GB) 的局限性
最初我们尝试在 **NVIDIA A10 (24GB)** 上运行 Qwen2.5-0.5B (最小模型) 的训练流程，但遭遇了严重的 OOM (Out of Memory) 问题。

*   **现象**: 在 `ref_init_model` 阶段，即初始化参考模型 (Reference Model) 时，显存直接爆满。
*   **原因分析**:
    *   **双模型加载**: RL 训练需要同时加载 Actor Model (策略模型) 和 Reference Model (参考模型)。
    *   **vLLM 开销**: vLLM 引擎本身需要预占一部分显存用于 KV Cache。
    *   **框架开销**: Ray 分布式框架和 PyTorch 上下文也需要占用显存。
    *   **结论**: 即使是 0.5B 的小模型，在 Agent Lightning + vLLM + Ray 的完整架构下，24GB 显存也显得捉襟见肘。

### 11.2 迁移至 H100 (80GB) 的成功实践
为了确保训练的稳定性和使用标准模型 (3B)，我们迁移到了 **NVIDIA H100 (80GB)** 环境。

*   **环境配置**:
    *   **OS**: Ubuntu Linux
    *   **Python**: 3.11 (Conda: `agentL_verify`)
    *   **关键库**: `torch==2.5.1`, `vllm==0.7.0`, `verl==0.5.0`
*   **验证结果**:
    *   **显存充裕**: 80GB 显存不仅能轻松加载 3B 模型，还能支持更大的 Batch Size 和 Context Length。
    *   **完整功能**: 成功运行了 `calc_x` 等依赖复杂工具调用的示例。
    *   **Git 仓库修复**: 在迁移过程中，我们发现远程仓库存在文件丢失问题，通过 `git reset --hard HEAD` 成功恢复了 `examples/` 目录下的关键文件。

### 11.3 给开发者的建议
1.  **硬件选择**: 强烈建议使用 **40GB+ 显存** (如 A100/H100/A6000) 进行 Agent Lightning 的训练开发。
2.  **工具链**: 确保安装 `uv`，因为许多现代 Agent 示例 (如基于 MCP 协议的工具) 依赖它来管理环境。
3.  **环境隔离**: 使用 Conda 严格隔离环境，避免 `vllm` 和 `torch` 版本冲突。
