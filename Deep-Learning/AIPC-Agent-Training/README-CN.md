# AIPC Agent 训练飞轮

基于 **DPO + GRPO 飞轮** 的领域专用 AI Agent 训练方案，以 AIPC（AI PC）客服场景为例。

## 🎯 核心理念

```
┌─────────────────────────────────────────────────────────────────┐
│                         飞轮循环                                 │
│                                                                 │
│   V1 (SFT)  ──►  上线部署  ──►  用户反馈 (👍/👎)               │
│       ▲                              │                          │
│       │                              ▼                          │
│   V(n+1)    ◄──  DPO + GRPO  ◄──  反馈数据                     │
│                                                                 │
│   • DPO: 学习边界（什么是错的）                                  │
│   • GRPO: 优化质量（什么是更好的）                               │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 训练数据策略

### DPO 数据（累积）
| 版本 | DPO 训练数据 |
|------|-------------|
| V2 | V1 反馈中的错误 |
| V3 | V1 + V2 反馈中的错误 |
| V4 | V1 + V2 + V3 反馈中的错误 |

**关键**: DPO 数据**累积** —— 模型不应该忘记学过的边界。

### GRPO Prompts（数量恒定，内容演进）
| 版本 | GRPO Prompts 组成 | 总数 |
|------|------------------|------|
| V2 | V1 错题 (50) + 新注入问题 (50) | **100** |
| V3 | V2 错题 (30) + 新注入问题 (70) | **100** |
| V4 | V3 错题 (15) + 新注入问题 (85) | **100** |

**关键**: GRPO prompts 保持**数量恒定**但内容演进：
- 旧错题减少（模型学会了）
- 新问题注入（持续进化）
- 模型**每轮实时生成新答案**（不复用旧回答）

## 🔄 完整工作流

### 阶段 1: 冷启动 (V1)
```bash
# 用种子数据训练 V1（人工标注）
python train_sft.py \
    --data data/cold_start.jsonl \
    --output output/v1_model
```

### 阶段 2: 收集反馈（模拟 V1 上线）
```bash
# 模拟用户对 V1 回答的反馈
python generate_feedback_data.py \
    --model output/v1_model \
    --questions data/test_questions.jsonl \
    --output-dpo data/dpo_v2.jsonl \
    --output-grpo-prompts data/grpo_prompts_v2.jsonl
```

**输出:**
- `dpo_v2.jsonl`: 偏好对 (prompt, chosen, rejected)
- `grpo_prompts_v2.jsonl`: **只有问题**（模型在 GRPO 训练时实时生成答案）

### 阶段 3: DPO + GRPO 训练 (V2)
```bash
# 第一步: DPO - 学习边界
python train_dpo.py \
    --base-model output/v1_model \
    --data data/dpo_v2.jsonl \
    --output output/v2_dpo

# 第二步: GRPO - 优化质量（实时采样！）
python train_grpo.py \
    --base-model output/v2_dpo \
    --prompts data/grpo_prompts_v2.jsonl \
    --judge-endpoint $AZURE_OPENAI_ENDPOINT \
    --output output/v2_model
```

### 阶段 4: 迭代
```bash
# 准备下一轮迭代的 prompts
python prepare_grpo_prompts.py \
    --old-errors data/v2_errors.jsonl \
    --new-questions data/new_questions.jsonl \
    --output data/grpo_prompts_v3.jsonl \
    --target-count 100

# 继续飞轮...
```

## 📁 仓库结构

```
AIPC-Agent-Training/
├── data/
│   ├── cold_start.jsonl        # V1 SFT 种子数据 (50 条)
│   ├── test_questions.jsonl    # 评估问题集
│   ├── dpo_v2.jsonl            # V2 的 DPO 偏好对
│   ├── grpo_prompts_v2.jsonl   # V2 的 GRPO prompts（只有问题！）
│   └── new_questions.jsonl     # 每轮注入的新问题
│
├── train_sft.py                # V1 冷启动 SFT
├── train_dpo.py                # DPO 偏好训练
├── train_grpo.py               # GRPO 实时采样 + 打分
├── train_iteration.py          # 完整 DPO→GRPO 迭代
│
├── generate_feedback_data.py   # 模拟用户反馈 → DPO + GRPO prompts
├── prepare_grpo_prompts.py     # 合并旧错题 + 新问题
├── evaluate.py                 # 模型评估
│
├── gradio_demo.py              # 交互演示界面
└── requirements.txt
```

## 🔑 关键设计决策

### 1. 为什么用 DPO + GRPO（而不是只用一个）？
- **DPO**: 教模型"不要这样做"（从错误中学习）
- **GRPO**: 教模型"这样更好"（在正确答案中优化）

### 2. 为什么 GRPO 用实时采样？
```python
# ❌ 错误: 预生成的回答
grpo_data = [{"prompt": Q, "response": A, "reward": 0.8}]  # 静态的！

# ✅ 正确: 训练时实时采样
for prompt in grpo_prompts:
    responses = model.generate(prompt, num_samples=4)  # 新鲜的！
    rewards = judge.score(responses)  # 实时打分！
    grpo_update(prompt, responses, rewards)
```

模型学的是**改进当前的自己**，而不是背诵旧答案。

### 3. 为什么保持 GRPO prompts 数量恒定？
- prompts 太少 → 训练不稳定
- 新问题注入 → 防止过拟合到旧错题
- 保留旧错题 → 确保难题得到足够练习

## 🛠️ 环境要求

```bash
pip install -r requirements.txt
```

主要依赖:
- `torch>=2.0.0`
- `transformers>=4.40.0`
- `trl>=0.12.0` (DPOTrainer, GRPOTrainer)
- `vllm>=0.6.0` (快速推理)
- `openai>=1.0.0` (GPT Judge)

## 📈 预期效果

| 版本 | 训练方法 | 准确率 |
|------|----------|--------|
| V1 | SFT（冷启动） | ~40% |
| V2 | DPO + GRPO | ~65% |
| V3 | DPO + GRPO | ~80% |
| V4 | DPO + GRPO | ~90%+ |

飞轮效应：每轮迭代都在上一轮基础上提升！

## 📝 许可证

MIT License
