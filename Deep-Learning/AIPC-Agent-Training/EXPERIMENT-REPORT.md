# Experiment Report: GRPO Reward Function Design for Small Language Models

> **Date**: 2026-03-13
> **Environment**: Azure A100 80GB VM (`Standard_NC24ads_A100_v4`)
> **Base Model**: `meta-llama/Llama-3.2-3B-Instruct` (3.2B parameters)
> **Evaluator**: GPT-5.2 via Azure OpenAI (APIM proxy)
> **Author**: Xinyu Wei (Microsoft AI and Apps GBB Architect)

---

## Executive Summary

We conducted 3 rounds of experiments to find the optimal GRPO reward function design for fine-tuning a 3B parameter model on customer support tasks. **The key finding is that pure LLM-as-Judge reward fails on small models, and a hybrid reward (rule-based + LLM judge) is required.**

| Round | Reward Design | GPT-5.2 Score (V1.4) | Improvement vs Base |
|:-----:|---------------|:---------------------:|:-------------------:|
| 1 | Rule-based only | N/A (GRPO failed) | N/A |
| 2 | GPT-5.2 only | 2.8/10 | **-12.5%** (degraded) |
| 3 | **Hybrid (Rule + GPT)** | **5.0/10** | **+25%** ✅ |

---

## Training Pipeline

```
LLaMA 3.2 3B-Instruct (Base)
    │
    ▼  SFT (850 samples, 3 epochs)
V1.1: SFT Model (Loss: 2.22 → 0.05)
    │
    ▼  GRPO (200 prompts, 2 epochs, hybrid reward)
V1.1+: GRPO Model (Reward: 0.23 → 0.27)
    │
    ▼  DPO Style (33 pairs, 3 epochs)
V1.2: Style Model (Loss: 0.693 → 0.634)
    │
    ▼  DPO Feedback (33 pairs, 3 epochs)
V1.3: Feedback Model (Loss: 0.693 → 0.644)
    │
    ▼  DPO Code (34 pairs, 3 epochs)
V1.4: Code Model (Loss: 0.693 → 0.668)
```

---

## Round 1: Rule-Based Reward Only

**Hypothesis**: A keyword/structure/length-based reward function is sufficient for GRPO.

**Reward Function**:
- Keyword match: +0.3 (NPU, AI PC, support, etc.)
- Length 100-500 chars: +0.2
- Has structure (numbered list): +0.2
- No hallucination: +0.3

**Result**: ❌ Failed

| Metric | Value | Problem |
|--------|:-----:|---------|
| Reward mean | 0.50-0.55 | Saturated (ceiling too low) |
| Reward std | 0.08-0.12 | Low variance |
| GRPO Loss | ~0 | Zero gradients (nothing to learn) |
| frac_reward_zero_std | 0-5% | Better than 3-sample but still poor |

**Root Cause**: Rule-based rewards hit a ceiling quickly. Once the model learns basic formatting (keywords + structure), all candidates score similarly. GRPO needs reward *variance* to differentiate candidates.

---

## Round 2: Pure GPT-5.2 as Judge

**Hypothesis**: GPT-5.2 can evaluate answer quality more accurately than rules.

**Reward Function**:
```python
score = GPT-5.2("Rate 1-10: Q={prompt} A={completion}")
reward = (score - 5) / 5  # Normalize to [-1, +1]
```

**Result**: ❌ Model degraded (-12.5%)

| Metric | Value | Problem |
|--------|:-----:|---------|
| Reward mean | **-0.50** | All negative! |
| Reward std | 0.25-0.37 | Good variance, but... |
| GPT scores for 3B | 2-3/10 | GPT judges small model too harshly |
| Final V1.4 score | 2.8/10 | **Worse than base** (3.2/10) |

**Root Cause**: GPT-5.2 evaluates on an absolute scale. A 3B model's answers are inherently lower quality than what GPT considers "good" (5/10). After normalization, all rewards are negative (-0.5 average). GRPO receives the signal "everything you do is bad" — the model has no direction to improve and learns to produce worse outputs.

This matches the finding from our prior Agent-Lighting experiment:
> "Training with reward mean = -0.54 → model 'learned to be worse' → Pass Rate dropped from 20% to 10%"

---

## Round 3: Hybrid Reward (Rule-Based + GPT Judge)

**Hypothesis**: Combine rule-based positive baseline with GPT quality adjustment.

**Reward Function Design**:
```python
def hybrid_reward(completion, prompt):
    # Rule-based: 0 ~ 0.5 (always positive baseline)
    rule_score = keyword_match(0~0.15) + length(0~0.1) + structure(0~0.1)
                 + no_refusal(0~0.1) + line_breaks(0~0.05)
    
    # GPT-5.2: -0.3 ~ +0.5 (quality adjustment)
    gpt_score = GPT_judge(prompt, completion)  # 1-10
    gpt_adjustment = (gpt_score - 3) / 14  # score 3 → 0, score 7 → +0.29
    
    return rule_score + gpt_adjustment  # Total: -0.3 ~ +1.0
```

**Key Design Decisions**:
1. **Normalization anchor at 3, not 5**: A 3B model scoring 3/10 maps to reward=0 (neutral), not -0.4 (punish)
2. **Rule-based floor**: Even if GPT gives 1/10, the rule component ensures reward ≥ -0.15 (not deeply negative)
3. **GPT as differentiator**: GPT doesn't set the baseline — it *adjusts* between candidates that rules score similarly

**Result**: ✅ +25% improvement

| Metric | Value | vs Round 2 |
|--------|:-----:|:----------:|
| Reward mean | **+0.22** | Was -0.50 |
| Reward std | 0.08-0.14 | Similar |
| frac_reward_zero_std | **0%** | Was 20-40% |
| GRPO trend | 0.23 → **0.27** ↑ | Was flat/declining |
| Final V1.4 score | **5.0/10** | Was 2.8 |
| Improvement vs Base | **+25%** | Was **-12.5%** |

**GRPO Reward Trajectory**:
```
Step  5: reward = 0.230  (start)
Step 25: reward = 0.239  ↑
Step 50: reward = 0.219  (epoch 1 done)
Step 65: reward = 0.254  ↑ peak
Step 100: reward = 0.266  ↑ new high (epoch 2 done)
```

---

## GPT-5.2 Evaluation: Base vs V1.4

| Question | Base | V1.4 | Delta |
|----------|:----:|:----:|:-----:|
| AI PC vs regular laptop | 3 | **6** | +3 |
| Deploy 7B model locally | 4 | 1 | -3 |
| VPN troubleshooting | 7 | 6 | -1 |
| NPU vs GPU benefits | 4 | **5** | +1 |
| Check NPU utilization | 2 | 2 | 0 |
| Windows update install | 4 | **6** | +2 |
| Reset AD password | 4 | **7** | +3 |
| CPU usage diagnosis | 4 | **7** | +3 |
| **Average** | **4.0** | **5.0** | **+1.0 (+25%)** |

**Analysis**: V1.4 shows clear improvement on IT support tasks (password reset +3, CPU diagnosis +3, AI PC +3) but degradation on some domain-specific questions (Deploy 7B model -3). This is expected: the training data (bitext customer support) is heavy on general IT tasks but light on AI PC-specific content.

---

## Key Takeaways

### For Practitioners

1. **Don't use pure LLM-as-Judge for GRPO on small models** — All-negative rewards cause model degradation
2. **Hybrid reward is essential for <8B models** — Rule-based baseline + LLM quality adjustment
3. **Normalize GPT scores relative to model capability** — Anchor at the model's typical score (3/10 for 3B), not the absolute midpoint (5/10)
4. **Data quality > Data quantity** — 850 SFT samples + 100 DPO pairs are sufficient for demonstrable improvement

### For the INA Customer (LLaMA 3.3 8B)

The customer's 8B model should perform significantly better than our 3B baseline:
- Larger model = higher GPT scores → Pure GPT-as-Judge might work (no hybrid needed)
- But we recommend starting with hybrid reward and validating before switching to pure GPT
- Their 100K support tickets provide far more training data than our 850 samples

---

## Reproducibility

### Environment
```
GPU:           NVIDIA A100 80GB PCIe
Python:        3.11
PyTorch:       2.10.0
Transformers:  4.57.6
TRL:           0.26.1
```

### Timing (A100 80GB)
| Stage | Duration |
|-------|:--------:|
| SFT (850 samples, 3 epochs) | 15 min |
| GRPO (200 prompts, 2 epochs, hybrid) | 55 min |
| DPO Style (33 pairs, 3 epochs) | 2 min |
| DPO Feedback (33 pairs, 3 epochs) | 2 min |
| DPO Code (34 pairs, 3 epochs) | 2 min |
| Evaluation (8 questions × 2 models) | 5 min |
| **Total** | **~80 min** |

### Quick Start
```bash
# 1. Prepare data (no API key needed)
python download_and_prepare_data.py

# 2. SFT
python train_sft_aipc.py --model_name_or_path meta-llama/Llama-3.2-3B-Instruct \
    --train_file data/aipc_sft_train.jsonl --val_file data/aipc_sft_val.jsonl \
    --output_dir checkpoints/aipc_sft_v1 --report_to none

# 3. Full pipeline (GRPO hybrid + DPO + eval) — requires Azure OpenAI for GPT judge
python l5_hybrid_pipeline.py
```

---

## All Experiment Logs

| Log File | Content | Key Metrics |
|----------|---------|-------------|
| `logs/sft_train.log` | SFT training | Loss: 2.22 → 0.05 |
| `logs/grpo_train.log` | GRPO Round 1 (rule-based) | Reward: 0.50 (saturated) |
| `logs/l5_pipeline.log` | GRPO Round 2 (pure GPT judge) | Score: 2.8/10 (-12.5%) |
| `logs/l5_hybrid.log` | GRPO Round 3 (hybrid reward) | Score: 5.0/10 (+25%) |
| `logs/full_pipeline.log` | Full pipeline (rule-based + DPO) | DPO convergence data |

---

*Author: Xinyu Wei (Microsoft AI and Apps GBB Architect) | Date: 2026-03-13*
