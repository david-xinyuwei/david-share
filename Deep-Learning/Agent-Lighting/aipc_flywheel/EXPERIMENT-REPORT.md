# AIPC Training Flywheel 实验报告

> **实验日期**: 2026年1月3日-4日
> **实验环境**: Azure A100 80GB VM (YOUR-VM.region.cloudapp.azure.com)
> **基座模型**: Phi-3.5-mini-instruct (3.8B)
> **评估标准**: GPT-5.2 五维度评分 (准确性/完整性/专业性/实用性/代码质量)

## 📊 实验结果汇总

| 模型版本 | 训练方法 | 数据量 | Pass Rate | Avg Score | 备注 |
|----------|----------|--------|-----------|-----------|------|
| V1.3 | DPO | 50 | **0/10 (0%)** | ~6.7/20 | 基线 |
| V1.4 | DPO + Code | 50 | **0/10 (0%)** | ~6.2/20 | 加入代码数据 |
| Distill V1 | SFT (知识蒸馏) | 50 | **0/10 (0%)** | ~8.2/20 | GPT-5.2 生成答案 |
| **GRPO V1** | GRPO + GPT-5.2 Reward | 50 | **2/10 (20%)** | 6.4/20 | ✅ 首次突破 0% |
| GRPO V2 | GRPO + GPT-5.2 Reward | 115 | **1/10 (10%)** | 5.0/20 | 数据扩充后反而下降 |

## 🔍 关键发现

### 1. 原始 GRPO 奖励函数的问题

原始的 `reward_functions.py` 中的奖励函数只检查**关键词和结构**，不评估**答案准确性**：

```python
# 原始奖励函数 (有问题)
def aipc_reward(response):
    score = 0
    # 只检查关键词存在性
    keywords = ["NPU", "AI PC", "OpenVINO", "推理", "优化"]
    for kw in keywords:
        if kw in response:
            score += 0.1
    # 检查结构
    if "```" in response:  # 有代码块
        score += 0.2
    return score
```

**问题**: 模型学会了"堆砌关键词"但答案不准确。

### 2. GPT-5.2 作为奖励模型

使用 GPT-5.2 直接评估答案质量作为 GRPO 奖励：

```python
# 改进的奖励函数
def gpt52_reward(prompts, completions, **kwargs):
    rewards = []
    for prompt, completion in zip(prompts, completions):
        eval_prompt = f"评估这个AI PC技术回答的质量(1-10分):\n问题:{prompt}\n回答:{completion}"
        resp = client.chat.completions.create(model="gpt-5.2", ...)
        score = extract_score(resp)
        rewards.append((score - 5) / 5)  # Normalize to [-1, 1]
    return rewards
```

**结果**: 首次突破 0% 瓶颈，达到 2/10 (20%) 通过率。

### 3. 数据扩充的悖论

| 数据量 | Pass Rate | 分析 |
|--------|-----------|------|
| 50 条 | 2/10 (20%) | ✅ |
| 115 条 | 1/10 (10%) | ❌ 下降 |

**原因分析**:
- 训练时 reward mean = -0.54（负值）
- GPT-5.2 对大部分回答评分较低
- 更多数据 + 负奖励 → 模型"学坏了"

## 🧪 测试问题集 (10 题)

```
1. 解释什么是AI PC，它与传统PC有什么区别？
2. NPU在AI PC中的作用是什么？请详细说明
3. 如何在AI PC上优化大语言模型的推理性能？
4. Intel Core Ultra处理器的AI加速功能有哪些？
5. 请解释AI PC中的混合架构（P-core和E-core）如何协同工作
6. 开发AI PC应用时，如何选择合适的AI框架？
7. AI PC上的本地AI推理相比云端推理有什么优势？
8. 如何评估一款AI PC的AI性能？有哪些关键指标？
9. 请说明OpenVINO在AI PC开发中的应用场景
10. AI PC如何实现隐私保护的本地AI处理？
```

## 📈 评估标准

**五维度评分** (每维度 1-4 分):
1. **准确性**: 技术信息是否正确
2. **完整性**: 是否全面回答了问题
3. **专业性**: 是否使用了正确的技术术语
4. **实用性**: 对用户是否有实际帮助
5. **代码质量** (如适用): 代码是否可运行、有注释

**通过标准**: 总分 ≥ 60% (有代码问题 12/20, 无代码问题 10/16)

## 🎯 结论与建议

### 结论

1. **Phi-3.5-mini (3.8B) 的能力上限**: 即使用 GPT-5.2 作为奖励模型，最高也只能达到 20% 通过率
2. **GRPO + LLM-as-Judge 有效**: 比纯 DPO 和 SFT 效果更好
3. **数据质量 > 数据数量**: 盲目扩充数据可能导致负面效果

### 建议

| 方向 | 预期收益 | 成本 |
|------|----------|------|
| 换更大基座模型 (7B+) | 高 | 高 (显存/算力) |
| 优化奖励函数 (多维度加权) | 中 | 低 |
| 人工标注高质量数据 | 高 | 高 (人力) |
| 课程学习 (由易到难) | 中 | 中 |

## 📁 实验产物

### Checkpoints (在 A100 VM 上)

```
/root/agent-lightning/checkpoints/
├── aipc_dpo_v1.3/          # DPO 基线
├── aipc_dpo_v1.4/          # DPO + Code
├── aipc_grpo_gpt52_v1/     # ✅ 最佳模型 (2/10)
│   └── checkpoint-36/
└── aipc_grpo_v2/           # 数据扩充版本 (1/10)
```

### 数据文件

```
/root/agent-lightning/
├── aipc_questions_200.json     # 198 个 AIPC 问题
├── aipc_qa_120.json            # 115 个 QA 对 (GPT-5.2 生成)
├── test_v1.3_expanded_results.json
├── test_v1.4_expanded_results.json
└── test_distill_v1_results.json
```

## 🔧 复现步骤

### 1. 生成训练数据

```bash
# 生成问题
python generate_aipc_data_agl.py --num_questions 200 --output aipc_questions.json

# 用 GPT-5.2 生成答案
python -c "
from openai import AzureOpenAI
import json

client = AzureOpenAI(
    azure_endpoint='YOUR_ENDPOINT',
    api_key='YOUR_KEY',
    api_version='2025-04-01-preview'
)

questions = json.load(open('aipc_questions.json'))
qa_pairs = []
for q in questions:
    resp = client.chat.completions.create(
        model='gpt-5.2',
        messages=[{'role': 'user', 'content': q}],
        max_completion_tokens=500
    )
    qa_pairs.append({'question': q, 'answer': resp.choices[0].message.content})
json.dump(qa_pairs, open('aipc_qa.json', 'w'), ensure_ascii=False)
"
```

### 2. GRPO 训练 (使用 GPT-5.2 奖励)

```python
from trl import GRPOConfig, GRPOTrainer

def gpt52_reward(prompts, completions, **kwargs):
    # ... GPT-5.2 评分逻辑
    pass

config = GRPOConfig(
    output_dir="checkpoints/aipc_grpo",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=1e-6,
    max_completion_length=512,
    num_generations=4,
    bf16=True,
)

trainer = GRPOTrainer(
    model=model,
    reward_funcs=gpt52_reward,
    args=config,
    train_dataset=dataset,
    processing_class=tokenizer,
)
trainer.train()
```

### 3. 评估

```bash
python evaluate_agl.py \
    --model_path checkpoints/aipc_grpo \
    --eval_model gpt-5.2 \
    --test_questions test_questions.json
```

---

**作者**: 魏新宇 (Xinyu Wei)  
**日期**: 2026-01-04
