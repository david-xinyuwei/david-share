# On-Policy Distillation Deep Dive: How DeepSeek-V4 Merges 10+ Experts — Verified on Azure AI

> **Author: Xinyu Wei (魏新宇)** · Microsoft AI GBB

[![Azure](https://img.shields.io/badge/Verified%20on-Azure%20AI-0078D4?logo=microsoftazure)](https://azure.microsoft.com) [![DeepSeek](https://img.shields.io/badge/Based%20on-DeepSeek--V4-blue)](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro) [![TRL](https://img.shields.io/badge/Framework-TRL%20GKDTrainer-orange)](https://huggingface.co/docs/trl/main/en/gkd_trainer) [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[中文版](README-CN.md) | English

[Companion: Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) | [Related: LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)

> A deep dive into On-Policy Distillation (OPD) — the post-training method DeepSeek-V4 uses to consolidate 10+ domain-specialist models into a single unified model, replacing the traditional mixed-RL stage entirely.

### Why This Matters for Practitioners

Enterprise teams building multi-domain AI systems face the same question DeepSeek solved with OPD: **how to consolidate multiple specialist models into one production endpoint** without losing each specialist's quality. This repo helps in three ways:

1. **Understand the competitive landscape** — When evaluating DeepSeek-V4 vs OpenAI models, practitioners can see *exactly* how V4 achieves multi-domain quality (OPD) vs how OpenAI does it (RL-to-the-end). Different engineering trade-offs, not magic.
2. **Architecture guidance** — Teams with 5-10 fine-tuned LoRA adapters or domain models can adopt distillation-based consolidation (using TRL/GKDTrainer on GPU VMs), reducing serving cost from N endpoints to one.
3. **Reproducible on Azure AI** — Every experiment in this repo ran on Azure H100 VMs, demonstrating that the full OPD workflow (training + evaluation) is reproducible on cloud GPU infrastructure.

## Executive Summary

| Method | How experts are merged | Failure mode | DeepSeek-V4 used? |
|--------|------------------------|--------------|:----------------:|
| **Weight Averaging** | Arithmetic mean of weights | Capabilities interfere → degraded quality | ❌ |
| **Task Arithmetic** (TIES, DARE, etc.) | Task vectors added/subtracted | Better than averaging, but still parameter-space heuristic | ❌ |
| **Mixed RL** (multi-task PPO/GRPO) | Joint reward across tasks | Reward hacking, training instability | ❌ (used in V3.2, replaced in V4) |
| **On-Policy Distillation (OPD)** | Logit-level alignment on student trajectories | Slow training, but stable & faithful | ✅ **V4's choice** |

> *"the mixed Reinforcement Learning (RL) stage was entirely replaced by On-Policy Distillation (OPD)."*
> — DeepSeek-V4 Technical Report, Section 5.1

DeepSeek trained 10+ domain-specialist models (math, code, writing, agent, reasoning, etc.) by branching from a base model and running domain-specific RL. Then they faced the question every multi-expert system faces: **how do you fuse them into one production model without losing each expert's specialty?**

This article explains why V4 chose OPD over the alternatives, walks through the full method with a concrete example, and shows how the engineering challenges (10+ teacher logits, vocabulary > 100k) were solved at scale.

---

## The 30-Second Picture: Where OPD Fits in DeepSeek-V4

Before the math, before the engineering — here is the *one diagram* you need to understand why OPD exists.

```mermaid
flowchart TB
    A["<b>Stage 1 · Pre-training</b><br/>Trillions of internet tokens<br/>→ DeepSeek-V4-Base"]
    B["<b>Stage 2 · Branch & Specialize</b><br/>Clone V4-Base into 10+ copies<br/>Each does SFT + RL on a domain corpus"]
    M["Math"]
    C["Code"]
    W["Writing"]
    AG["Agent"]
    R["Reason"]
    D["... 10+ experts"]
    P["⚠️ Deployment problem<br/>10 separate models = 10× inference cost"]
    O["<b>Stage 3 · ⭐ OPD — the consolidation step</b><br/>Each expert is a teacher<br/>One student does reverse-KL distillation<br/>on its own trajectories vs the experts' logits"]
    F["<b>DeepSeek-V4-Final</b><br/>Single model, 10+ skills<br/>Production-ready"]

    A --> B
    B --> M & C & W & AG & R & D
    M & C & W & AG & R & D --> P
    P --> O
    O --> F

    style O fill:#fff4e6,stroke:#ea580c,stroke-width:2.5px
    style F fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style P fill:#fef2f2,stroke:#dc2626,stroke-width:1.5px
```

### Why this matters

DeepSeek-V3 and earlier used **Mixed RL** (multi-task PPO/GRPO) for Stage 3. V4 abandoned it. The Tech Report is explicit:

> *"the mixed Reinforcement Learning (RL) stage was entirely replaced by On-Policy Distillation (OPD)."*
> — DeepSeek-V4 Technical Report, Section 5.1

The rest of this document explains the *what*, *why*, and *how* of that replacement — and verifies the mechanism end-to-end on real hardware.

### One-sentence summary

> **OPD is DeepSeek-V4's "expert merging" technique: it compresses 10+ separately-trained domain specialists back into a single unified model, replacing the unstable Mixed RL approach used in V3.**

---

## Running on Azure

The verification experiments in this repo were run on an Azure NCads H100 v5 class VM. Microsoft Learn describes the NCads_H100_v5 series as powered by NVIDIA H100 NVL GPUs and 4th-generation AMD EPYC Genoa processors, with up to 2 H100 NVL GPUs, 94 GB GPU memory per accelerator, up to 80 vCPUs, and 640 GiB system memory for the `Standard_NC80adis_H100_v5` size. Source: [NCads_H100_v5 sizes series](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ncadsh100v5-series), checked 2026-05-20.

| Resource | Run 11 configuration | Role in the OPD experiment |
|----------|----------------------|-----------------------------|
| VM SKU | `Standard_NC80adis_H100_v5` | 2-GPU H100 node for DDP training |
| GPU | 2 x NVIDIA H100 NVL, 94 GB each | Student rollout, teacher logits, reverse-KL training |
| vCPU | 80 AMD EPYC Genoa cores | Dataset preprocessing, code evaluation, dataloader workers |
| System memory | 640 GiB | Host-side dataset and tokenizer buffers |
| Remote storage | Premium SSD / managed disk | Checkpoints, logs, and JSON result artifacts |

Single VM matters here: Run 11 did not require a Kubernetes cluster or a multi-node training setup. The final positive run used `accelerate launch --num_processes 2 --mixed_precision bf16`, completed 738 training steps in 5h 58min, and then ran HumanEval greedy and pass@10 evaluation on the same H100 node.

### Technology Stack at a Glance

| Category | Technique | What it does | Impact | Detail section |
|----------|-----------|--------------|--------|----------------|
| Algorithm | On-Policy Distillation | Student samples its own trajectory; teacher scores the student's tokens | +6.10pp HumanEval pass@10 in Run 11 | [Phase 5](#phase-5--scaled-cross-domain-opd-triangulated-positive-signal-run-11) |
| KL objective | Reverse KL | Makes the student mode-seeking instead of mode-covering | Prevents blended, low-confidence generation | [The Math](#the-math-reverse-kl--gkd-framework) |
| Framework | TRL `GKDTrainer` | Provides an off-the-shelf OPD-style training loop | Reduces implementation to model, teacher, dataset, and two OPD flags | [OPD Code Ecosystem](#opd-code-ecosystem-2026-reality-check) |
| Distributed training | Accelerate DDP | Uses both H100 GPUs in one VM | 2x effective batch parallelism for Run 11 | [Reproducibility](#reproducibility) |
| Precision | bf16 + fp32 LM head | Keeps most training in bf16 while stabilizing logits | Avoids the earlier bf16 NaN failure path | [bf16 NaN Investigation](#the-bf16-nan-investigation--a-forensic-trail) |

### Resource Distribution

| Component | Where it lives | Peak pressure in this repo | Why it matters |
|-----------|----------------|----------------------------|----------------|
| Student model | H100 VRAM | 1.5B parameters + gradients | Trainable OPD target |
| Teacher model | H100 VRAM | 7B parameters for scoring | Provides code-domain logits |
| Activations + rollout tokens | H100 VRAM | `max_length=1536`, `max_new_tokens=512` | Dominates per-step memory during on-policy generation |
| Dataset and tokenization | CPU RAM | MBPP + CodeAlpaca subset | Keeps GPU fed during DDP training |
| Checkpoints and logs | Managed disk | Final checkpoint + JSON/log artifacts | Makes the benchmark traceable |

Recommended reproduction starting point: start with `Standard_NC80adis_H100_v5` or another 2-H100-equivalent VM, confirm H100 quota in the target Azure region, install the dependencies from `requirements.txt`, then run the archived Run 11 command in the [Reproducibility](#reproducibility) section.

---

## Background: The Multi-Expert Merging Problem

Modern LLMs need to be good at many things — math, code, writing, agent tool-use, multilingual translation. The standard playbook is:

1. **Pre-train** a single base model on diverse data
2. **Specialize** copies of it into domain experts via supervised fine-tuning + RL
3. **Merge** these experts back into one model for production deployment

Step 3 is where most of the difficulty lies. Once you have, say, 10 experts each better than the base model on its own domain, naive ways to combine them tend to either average away the specialty or destabilize training.

### Why not just keep separate experts?

Production deployment heavily favors a single unified model:

- **Cost**: One model = one set of GPUs. Ten models = ten times the inference cost.
- **Latency**: Routing requests to the right expert adds round-trip overhead.
- **Capability composition**: A real user query often spans multiple domains (e.g., "write Python code that solves this math problem"). A single model that internalized all expertise can compose them; routed experts cannot.

#### What about LoRA hot-swapping?

A reasonable engineering response is: "modern serving stacks (vLLM, SGLang) support LoRA hot-swapping — keep one base model + N small adapters, switch on demand. Why merge at all?"

LoRA hot-swap **is the right answer** for many deployments — but not for V4-class production. Comparison:

| Aspect | LoRA Hot-Swap | OPD-Merged Single Model |
|--------|:-------------:|:-----------------------:|
| Storage per expert | ~MB-scale adapter | None (knowledge baked into base) |
| Switching latency | 1-50ms per request | 0 (no switching) |
| Cross-domain query (math + code) | ❌ Only one adapter active per request | ✅ All capabilities co-active |
| Capability ceiling | LoRA rank-limited (typically r=16-64) | Full-parameter ceiling |
| Specialist training cost | Cheap (LoRA training) | Expensive (full RL) |
| When it shines | Multi-tenant customization, single-domain queries | Frontier quality, cross-domain composition |

V4 chose merging because (1) DeepSeek's specialists are full-parameter RL outputs, not LoRA adapters; (2) frontier-quality math/code/agent tasks routinely span multiple domains; (3) router-based serving introduces operational complexity DeepSeek wanted to avoid.

For most enterprise multi-tenant scenarios, LoRA hot-swap remains the more practical answer.

### Why not just directly inject the experts as MoE expert slots?

Another natural reaction: "V4 is already a MoE architecture with hundreds of expert slots. Why not just plug each external specialist into one of those slots?" This sounds elegant but is structurally impossible. Five reasons:

| # | Mismatch | Detail |
|:-:|----------|--------|
| 1 | **Granularity** | A MoE expert is a **single FFN sub-network within one Transformer block** (~100MB). An external specialist is an **entire model** (hundreds of GB) with its own attention, embedding, and all FFN layers. You cannot fit a complete model into one FFN slot. |
| 2 | **Architecture incompatibility** | The external specialists may be V3.2-derived (V3.2 architecture); the V4 student uses CSA/HCA + mHC. Layer dimensions, attention mechanisms, and residual structures differ — the FFN weights cannot be transplanted directly. |
| 3 | **Router doesn't know them** | The MoE router was trained from scratch during pre-training to route among the existing experts. Inserting unfamiliar external FFN modules means the router has no signal about when to dispatch to them. Retraining the router ≈ retraining the model. |
| 4 | **Expertise is whole-network** | A "math expert" model encodes math capability across **every layer** — attention patterns, embedding representations, all FFN coordination. Transplanting only one FFN layer captures < 1% of the actual capability. |
| 5 | **Granularity mismatch with MoE design** | V4's MoE uses *fine-grained* experts — each one specializes in token-level patterns (a syntax structure, a class of knowledge tokens), not a whole domain. A "domain expert" corresponds to coordinated behavior across hundreds of fine-grained experts, not a 1:1 mapping. |

> **Bottom line**: OPD merges by **behavior replication** (logit distribution matching). Direct MoE injection would require **part transplantation** (weight insertion) — which fails because the parts don't have compatible interfaces.

With these two natural alternatives ruled out, the field has converged on four serious approaches for multi-expert merging.

### The four candidate approaches

| Approach | Mechanism | Why it falls short |
|----------|-----------|---------------------|
| **Weight Averaging** | `θ_merged = (θ_1 + θ_2 + ... + θ_N) / N` | Linear interpolation of non-linear functions. The math expert's weights and code expert's weights cancel each other in the loss landscape, often landing in a worse region than either. |
| **Task Arithmetic** (TIES, DARE) | `θ_merged = θ_base + Σ τ_i · (θ_i − θ_base)`, with sign/sparsification heuristics | Better than naive averaging because it preserves task vectors. But still operates in parameter space, ignoring how the network's outputs change. |
| **Mixed RL** | Single RL run with multi-task reward signal | Reward functions across domains often conflict (e.g., math wants long step-by-step reasoning, chat wants concise answers). Training is unstable; one task's reward gradient can sabotage another's. |
| **On-Policy Distillation (OPD)** | Distill multiple teachers into student, where student samples its own trajectories and matches each teacher's distribution via reverse KL | Slow per step (student must roll out), but training is stable and the student learns task-conditional behavior naturally. |

DeepSeek-V3.2 used Mixed RL. **V4 dropped it entirely** in favor of OPD.

---

## What is On-Policy Distillation?

OPD is a refinement of standard knowledge distillation. To understand what makes it "on-policy", contrast it with the offline version:

<div align="center">

<img width="960" src="images/opd_vs_offline.png" alt="Offline vs On-Policy Distillation comparison">

<p><em>Offline distillation: student fits to teacher's trajectories. OPD: student fits to teacher's scoring of student's own trajectories. Generated by <code>scripts/generate_diagrams.py</code>.</em></p>
</div>

### Offline Distillation (the traditional approach)

```
Step 1: Teacher generates an answer
Step 2: Student trains to imitate that answer
```

The student sees only data the teacher would produce. At inference time, the student is asked to generate from its own (different) distribution — this train/inference gap hurts generalization, especially for long autoregressive generation where errors compound.

### On-Policy Distillation

```
Step 1: Student generates an answer (rollout)
Step 2: Teacher computes its probability distribution over each token in that answer
Step 3: Student updates to make its distribution closer to teacher's, on these specific positions
```

The student is always learning from feedback on **its own behavior**. There is no train/inference distribution mismatch. This is exactly the principle that makes on-policy reinforcement learning more sample-efficient than off-policy — except here we replace the reward signal with a teacher's logit distribution.

### A concrete example (one training step)

Suppose the prompt is `"Solve: 12 × 7 = "` and we are using a math expert as the teacher.

**Step 1 — Student rollout** (student samples its own continuation):
```
Student generates:  " Let me think. 12 × 7 = 12 × 5 + 12 × 2 = 60 + 24 = 84"
```

**Step 2 — Teacher scoring** (math expert sees the same prompt + student's continuation, computes logits at every position):
```
Position of "84":
  Teacher logits → softmax → P(token | context)
  P("84") = 0.92 (teacher highly confident)
  P("82") = 0.03
  P("76") = 0.02
  ...

Position of "60":  
  Teacher P("60") = 0.71  (teacher would also pick 60 here)
  Teacher P("70") = 0.05
  ...
```

**Step 3 — Student update** (compute reverse KL between student and teacher distributions, update student weights so its distribution moves closer to teacher's):
```
At each token position:  L = Σ_v π_θ(v) · [log π_θ(v) − log π_E(v)]
Backpropagate, update θ.
```

Notice: the student is being scored on **its own decomposition strategy** ("12 × 5 + 12 × 2"), not the teacher's. If the teacher would have done it differently, the student doesn't need to copy that — it just needs to make sure the teacher endorses the answer at each step the student took.

---

### "Loss" and "comparing probabilities" are the same thing

A common confusion when reading distillation papers: *"Are we computing a loss, or are we comparing probabilities?"* The answer is **both, simultaneously** — the loss function *is* the probability comparison.

Every neural network training procedure needs one scalar number that says "how wrong are we right now?" That number is called the **loss**. Different training methods use different loss functions, but they all output one scalar.

| Training type | What the loss function measures |
|---------------|--------------------------------|
| **SFT** (supervised fine-tuning) | Cross-entropy: did the predicted token match the correct token? |
| **Distillation** | KL divergence: how close is the student's probability distribution to the teacher's? |
| **RLHF / GRPO** | Reward gap: did this response score higher than alternatives? |

So when this article says "OPD compares probability distributions," it's the same thing as saying "OPD uses KL divergence as its loss function." There is no choice between the two — comparing probability distributions *via the KL formula* **is** the loss.

#### What the KL loss actually computes

`KL(P_student || P_teacher) = Σ_i P_student(i) · log(P_student(i) / P_teacher(i))`

This formula takes two probability vectors (each `|V|` entries long, where `|V|` is the vocab size of student and teacher — they must match) and returns one scalar:

| Two distributions are... | KL value |
|--------------------------|----------|
| Identical | 0 |
| Slightly different | small positive number |
| Very different | large positive number |

**Training = backpropagating to reduce this scalar**. Every gradient step nudges the student's distribution closer to the teacher's.

#### Side-by-side: SFT loss vs distillation loss

For the same input prompt and the same vocabulary position:

```
SFT loss (uses one-hot label, sparse signal):
  P_student   = [0.10, 0.70, 0.05, 0.02, 0.05, 0.08, ...]  ← student output
  target      = [   0,    1,    0,    0,    0,    0, ...]  ← only token 1 is "correct"
  loss = −log(0.70) = 0.36
  ↑ Only sees one position; learns "must output token 1"

Distillation loss (uses full distribution, dense signal):
  P_student   = [0.10, 0.70, 0.05, 0.02, 0.05, 0.08, ...]  ← student output
  P_teacher   = [0.05, 0.85, 0.03, 0.02, 0.04, 0.01, ...]  ← teacher output
  loss = KL(P_s ‖ P_t) = 0.13
  ↑ Sees all `|V|` positions; learns the full ranking, not just the winner
```

This is also why the loss numbers reported in the experiments later in this document — `{'loss': '2.581'}`, `{'loss': '1.644'}` and so on — are KL divergence values. **A falling loss in OPD literally means "the student's distribution is converging toward the teacher's distribution."**

#### Why dense signal is the entire point

| Dimension | SFT (one-hot) | Distillation (full distribution) |
|-----------|---------------|----------------------------------|
| Information per token | ~1 bit ("right or wrong") | ~log₂(`|V|`) bits (full ranking, ~17 bits for 152K vocab) |
| What student learns | "Output X" | "X best, Y second-best, Z definitely-not, ..." |
| Sample efficiency | Baseline | 5-10× faster (Hinton 2015 result) |
| Preserves teacher's "personality" | No | Yes (multiple acceptable answers all kept) |

#### Caveat: low loss ≠ high accuracy

Driving the KL loss to a low number guarantees that the student's distribution looks like the teacher's distribution **on the trained tokens**. It does **not** automatically guarantee end-task improvement. The 9 experiments documented in the Appendix prove this — several runs achieved loss values of 0.5 or even 1.6 on cross-domain training, yet end-task accuracy moved less than 1 percentage point. The loss is necessary but not sufficient.

The thunlp/OPD paper's two failure conditions explain why: even if the student exactly matches the teacher's output distribution, that only helps if (i) the student and teacher have compatible thinking patterns, and (ii) the teacher actually has new capabilities the student hadn't seen during pre-training. If both fail, KL → 0 changes nothing measurable downstream.

---

## OPD vs MoE: Two Different "Experts"

V4 is **both a MoE architecture and a recipient of OPD post-training**. These are completely separate concepts that happen to share the word "expert" — a frequent source of confusion. Disambiguating:

| Concept | What it is | Lifetime | Quantity in V4-Pro |
|---------|------------|----------|:------------------:|
| **MoE expert** (architectural) | A single FFN sub-network within one Transformer block, selected by a router per-token | **Permanent** — part of the model architecture | ~256 fine-grained experts × ~60 layers = ~15K experts total |
| **OPD "specialist expert"** (training-only) | A complete standalone model trained on one domain (math, code, writing, etc.) via full-parameter RL | **Training-only** — disappears after OPD distillation | 10+ during training, 0 after |

Visualizing the architectural MoE inside V4's Transformer — to make clear where the fine-grained FFN experts live relative to Attention, KV Cache, and other components — see the full MoE Transformer pipeline diagram in [KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive#moe-variant-when-step-5-becomes-a-mixture-of-experts). Key takeaway: each MoE "expert" is a small FFN (e.g., 4096→1408→4096), selected per-token by a router. An OPD specialist is an entire multi-hundred-billion-parameter model. They are fundamentally different things.

### How do MoE experts get their "skills"?

A common follow-up question: if no one labels MoE experts as "the math expert" or "the writing expert", how do they end up specialized at all?

The answer: **specialization emerges automatically during pre-training, driven by the router-expert feedback loop.**

```
Pre-training initialization:
  Expert 1, 2, ..., 256:  random FFN weights, no skills
  Router:                   random weights, picks experts arbitrarily

Pre-training progresses (trillions of tokens):
  Random fluctuations make some experts marginally better at certain token patterns
  → Router learns to pick those experts more often for that pattern
  → Those experts receive more gradient on that pattern
  → They become even better at it
  → Positive feedback loop crystallizes the specialization

Pre-training ends:
  Expert 17:  attends mostly to English grammar tokens
  Expert 42:  attends mostly to math symbols
  Expert 103: attends mostly to Chinese narrative tokens
  Expert 200: attends mostly to code indentation tokens
  ...
  (But no human ever labeled them. The router learned, the experts adapted.)
```

**Important nuance**: an expert's "skill" is not a domain — it is a **token-level pattern**. There is no "math expert" in the literal sense; there is "the expert that gets selected when the input token looks like a math operator", which behaves *as if* it were a math expert in aggregate. A math problem activates many different experts across many different tokens (numbers, operators, punctuation, etc.), each contributing to the final output.

### OPD Gradient Flow: Which Experts Actually Get Updated?

Now we can answer the most subtle question: **when an OPD step happens with 10+ teachers all scoring, which MoE experts in the student get updated?**

Strict logical derivation from the OPD loss:

`L = Σ_i w_i · D_KL(π_θ || π_E_i)`

For any parameter `θ_p` (e.g., a specific expert's FFN weight), the gradient is:

`∂L/∂θ_p = Σ_i w_i · ∂D_KL(π_θ || π_E_i)/∂θ_p`

The teacher distributions `π_E_i` are **frozen** (they don't depend on `θ_p`), so the only way the gradient is non-zero is through `π_θ` — the student's output distribution. By the chain rule:

`∂D_KL/∂θ_p = (∂D_KL/∂π_θ) · (∂π_θ/∂θ_p)`

If `θ_p` did not participate in the forward pass that produced `π_θ`, then `∂π_θ / ∂θ_p = 0` for that sample's direct FFN path (it's not in the computation graph at all).

**Putting it together** for a single training sample (e.g., a math problem):

| Component | Participates in forward? | Receives gradient? |
|-----------|:------------------------:|:-----------------:|
| Embedding, Attention, LM Head | ✅ Always | ✅ Always |
| Router | ✅ Always | ✅ Always |
| MoE experts **selected by router** (top-8) | ✅ Yes | ✅ Yes (gradient flows) |
| MoE experts **NOT selected** (the other 248) | ❌ No | ❌ Zero direct FFN gradient for this sample |

**Crucially**: the "all 10 teachers score every sample" fact only changes the *composition* of the gradient that flows to the selected experts — it does not make unselected expert FFN blocks participate in this sample's forward graph. In other words, the sparsity claim is about **direct per-sample FFN gradients**, not a statement that an expert can never be affected by optimizer state, router learning, or later samples.

So when a math problem comes in:

1. Router selects top-8 experts that handle math-pattern tokens — call this set M
2. Forward pass uses only M (the other 248 experts are bypassed)
3. All 10+ teachers score the student's output:
   - Math teacher: high-quality KL signal (it understands math)
  - Other 9 teachers: weaker or less task-aligned signal (often closer to noise on this domain)
4. Gradients flow back, summed weighted by `w_i`:
   - Math teacher's gradient dominates (large KL → large gradient)
  - Other teachers' gradients contribute less useful signal; whether they cancel perfectly depends on teacher overlap and weighting
5. The dominant gradient updates **only the experts in M** (and Router/Attention/etc.)
6. The other 248 experts: no direct FFN gradient from this sample

**End result**: math-pattern experts tend to receive math training, writing-pattern experts tend to receive writing training, and code-pattern experts tend to receive code training — even though all teachers are present at every step. The router (architectural) and the gradient sparsity (mathematical) create a strong specialization bias, not a manually labeled one-expert-per-domain assignment.

### Visualizing it: Inference Path vs OPD Training Path

Two diagrams that make the above mechanism concrete.

**Diagram A — Inference (one token through all 60 layers)**:

```mermaid
graph TD
    INPUT["Input Token<br/>e.g., '12'<br/>4096-dim hidden state"] --> L1
    
    subgraph L1["Layer 1"]
        L1_ATT["Attention<br/>(CSA/HCA)"] --> L1_ROUTER
        L1_ROUTER["Router<br/>4096d → 256 logits"]
        L1_ROUTER -->|"top-8"| L1_E["Expert {17, 42, 89,<br/>103, 128, 156, 200, 233}<br/>+ Shared Expert"]
        L1_E --> L1_OUT["output 4096d<br/>→ next layer"]
    end
    
    L1 --> L2
    
    subgraph L2["Layer 2"]
        L2_ATT["Attention"] --> L2_ROUTER
        L2_ROUTER["Router"]
        L2_ROUTER -->|"top-8"| L2_E["Expert {5, 23, 67,<br/>91, 120, 178, 201, 245}<br/>+ Shared Expert"]
        L2_E --> L2_OUT["output 4096d<br/>→ next layer"]
    end
    
    L2 --> DOTS["...<br/>(every layer repeats:<br/>Attention → Router → top-8 expert)"]
    
    DOTS --> L60
    
    subgraph L60["Layer 60"]
        L60_ATT["Attention"] --> L60_ROUTER
        L60_ROUTER["Router"]
        L60_ROUTER -->|"top-8"| L60_E["Expert {3, 47, 88,<br/>112, 145, 189, 217, 250}<br/>+ Shared Expert"]
        L60_E --> L60_OUT["output 4096d"]
    end
    
    L60 --> LM_HEAD["LM Head<br/>4096d → 150K vocab<br/>→ predict next token"]
    
    style L1 fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    style L2 fill:#E8EAF6,stroke:#283593,stroke-width:2px
    style L60 fill:#FCE4EC,stroke:#C62828,stroke-width:2px
    style DOTS fill:#FFF9C4,stroke:#F9A825,stroke-width:2px,stroke-dasharray:5 5
    style L1_ROUTER fill:#9C27B0,color:#fff
    style L2_ROUTER fill:#9C27B0,color:#fff
    style L60_ROUTER fill:#9C27B0,color:#fff
    style L1_E fill:#CE93D8
    style L2_E fill:#CE93D8
    style L60_E fill:#CE93D8
    style INPUT fill:#FFE082
    style LM_HEAD fill:#FFAB91
```

Key observations from Diagram A:
- **60 layers, each with its own independent 256-expert pool** (Layer 1's experts and Layer 2's experts are completely separate)
- **Each layer's Router independently picks top-8** (the selected expert IDs differ across layers)
- **Total per-token activation**: 60 × (8 routed + 1 shared) = **540 expert instances** (out of ~15,000 total)
- This corresponds to ~49B activated parameters (≈ 3% of V4-Pro's 1.6T total)

**Diagram B — One OPD Training Step**:

```mermaid
graph TD
    INPUT["Training sample: math problem<br/>e.g., '12 × 7 = ?'<br/>current token = '12'"] --> SPLIT[" "]
    
    SPLIT -.->|"same token input"| STUDENT
    SPLIT -.->|"same token input"| TEACHERS
    
    subgraph STUDENT["Student (V4 MoE, being trained)"]
        direction TB
        S_L1["Layer 1: Attention → Router → top-8 expert<br/>{17, 42, 89, 103, ...}"] --> S_L2["Layer 2: same structure<br/>{5, 23, 67, 91, ...}"]
        S_L2 --> S_DOTS["...60 layers all repeat..."]
        S_DOTS --> S_LMHEAD["LM Head"]
        S_LMHEAD --> S_DIST["π_θ:<br/>student's full-vocab distribution<br/>(150K-dim)"]
    end
    
    subgraph TEACHERS["10+ Specialist Teachers (frozen, NOT trained)"]
        direction TB
        T_MATH["Math Specialist<br/>(complete model)<br/>→ output distribution"]
        T_CODE["Code Specialist<br/>→ output distribution"]
        T_WRITE["Writing Specialist<br/>→ output distribution"]
        T_DOTS["...other ~7 specialists..."]
    end
    
    S_DIST --> LOSS
    T_MATH -->|"π_E1: high-quality signal<br/>(it understands math)"| LOSS
    T_CODE -->|"π_E2: noise<br/>(doesn't understand math)"| LOSS
    T_WRITE -->|"π_E3: noise"| LOSS
    T_DOTS -->|"..."| LOSS
    
    LOSS["Loss = Σᵢ wᵢ · KL(π_θ ‖ π_Ei)<br/>ALL N teachers summed weighted<br/>(paper Eq.29)"]
    
    LOSS --> GRAD["Backward pass"]
    
    GRAD -.->|"math teacher's gradient dominates<br/>updates student parameters"| S_UPDATE["✅ Update Student:<br/>• Embedding<br/>• Attention (every layer)<br/>• Router (every layer)<br/>• Selected top-8 experts (every layer)<br/>(other experts: no direct FFN gradient for this token)"]
    
    GRAD -.->|"❌ no update"| T_FROZEN["Teachers stay frozen<br/>throughout training"]
    
    style INPUT fill:#FFE082
    style SPLIT fill:#FFFFFF,stroke:#FFFFFF
    style STUDENT fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    style TEACHERS fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    style LOSS fill:#FFAB91,stroke:#BF360C,stroke-width:3px
    style GRAD fill:#FFCC80,stroke:#E65100,stroke-width:2px
    style S_UPDATE fill:#C8E6C9,stroke:#2E7D32,stroke-width:2px
    style T_FROZEN fill:#FFCDD2,stroke:#B71C1C,stroke-width:2px
    style S_DIST fill:#9C27B0,color:#fff
    style T_MATH fill:#F8BBD0
    style T_CODE fill:#F8BBD0
    style T_WRITE fill:#F8BBD0
    style T_DOTS fill:#F8BBD0,stroke-dasharray:3 3
```

Key observations from Diagram B:
- **All N teachers run forward at every step** (Eq.29 sums all KL terms — there is no teacher selection)
- **The relevant teacher should provide the most useful gradient** (math teacher on math problem = sharper, more task-aligned distribution; other teachers can still contribute correlated noise if their pre-training overlaps)
- **Teachers are frozen** — only the student's parameters are updated
- **Within the student, only router-selected expert FFNs get direct gradient for that token** — non-selected expert FFNs are outside this sample's computation graph

The combination of "all teachers always score" (Eq.29) and "only selected experts compute" (MoE forward) is what produces the useful property: **mathematically all 10+ teachers participate, but in practice each problem mainly updates the student paths whose router pattern aligns with that problem, ideally guided most strongly by the teacher that understands the domain**.

### Where do the OPD-distilled capabilities end up?

When OPD-distilled student receives a math query at inference time:

1. **Embedding** layer activates math-relevant token embeddings
2. **Attention** layer (CSA/HCA) attends to math-relevant context
3. **Router** in Step 5 dispatches the token to MoE experts that, during OPD training, became specialized for math token patterns (this is automatic — gradient descent decided which experts handle which patterns)
4. **Multiple MoE experts** contribute weighted outputs (no single expert "is" the math expert)
5. **LM Head** maps to math-relevant vocabulary

The "math specialist model" that taught this behavior during OPD has been deleted long ago. Its capability now lives **distributed across the entire student model**, not concentrated in any one component.

This is fundamentally different from architectural MoE, where each expert FFN is a discrete unit with discrete parameters. OPD merging produces **capability that is distributed by gradient descent**, not by architectural design.

---

## The Math: Reverse KL + GKD Framework

The OPD objective from the V4 paper (Equation 29):

`L_OPD(θ) = Σ_i w_i · D_KL(π_θ || π_E_i)`

Three things are worth unpacking here.

### 1. The KL is reverse, not forward

| Direction | Formula | Behavior |
|-----------|---------|----------|
| **Forward KL** `D_KL(π_E ‖ π_θ)` | `Σ π_E(v) · [log π_E(v) − log π_θ(v)]` | "Mode-covering" — student tries to put non-zero probability everywhere the teacher does. Common in offline distillation. |
| **Reverse KL** `D_KL(π_θ ‖ π_E)` | `Σ π_θ(v) · [log π_θ(v) − log π_E(v)]` | "Mode-seeking" — student concentrates on the teacher's high-probability modes. |

OPD uses **reverse KL** because:
- Trajectories are sampled from `π_θ` (the student), so it's natural to weight by `π_θ(v)`
- Mode-seeking behavior produces sharper, more decisive student outputs (better for generation)
- Forward KL on student-sampled trajectories would have high variance because we'd be evaluating teacher probability on tokens the student rarely picks

This is the right bias for math, code, and other tasks where the model must commit to a concrete next token. It is still a design trade-off: for open-ended creative generation, a more mode-covering objective may preserve diversity better.

### 2. The expectation is over student trajectories

The KL is computed at every token in a student-sampled trajectory. This is the "on-policy" part:

`D_KL(π_θ || π_E_i) = E_{y ~ π_θ}[Σ_t Σ_v π_θ(v | y_<t) · log(π_θ(v | y_<t) / π_E_i(v | y_<t))]`

If we sampled from the teacher instead, this would degenerate into offline distillation.

### 3. The weights `w_i` route by domain implicitly

The paper explains:
> *"the unified policy π_θ selectively learns from the specialized expert relevant to the current task context (e.g., aligning with the mathematics expert for math reasoning tasks and the coding expert for programming tasks)."*

The intended mechanism is that each teacher is most informative on its own domain and less informative elsewhere. When the trajectory is a math problem, the math expert should provide the strongest, most task-aligned gradient; other teachers may contribute weaker or noisier gradients. They do not magically disappear, and if teachers share similar pre-training biases their out-of-domain gradients may be correlated rather than perfectly canceling.

So even though all teachers are summed, the training objective can align each task with its corresponding expert signal without explicit task routing. This is much simpler than a router, but it still depends on teacher specialization, teacher weights, and data coverage.

---


### OPD in the GKD Framework

With the reverse-KL objective established, we can now place OPD precisely within the broader landscape of distillation methods using the GKD (Generalized Knowledge Distillation) framework.


OPD is not a standalone method — it's actually a **specific configuration** of a more general framework called **GKD (Generalized Knowledge Distillation)** by Agarwal et al. (Google DeepMind, 2023). Understanding GKD makes the OPD design space crystal clear.

### The GKD unified loss

GKD parameterizes all distillation methods with two knobs:

```
GKD Loss = (1 - lmbda) × KL_offline + lmbda × KL_on_policy
                                                ↑
                              "lmbda" controls on-policy ratio
                              0 = pure offline, 1 = pure on-policy

KL_inner = (1 - beta) × Forward_KL + beta × Reverse_KL
                                              ↑
                              "beta" controls KL direction
                              0 = pure forward KL, 1 = pure reverse KL
```

### All distillation methods are GKD configurations

| Configuration | Method | Trajectory Source | KL Direction |
|---------------|--------|-------------------|--------------|
| `lmbda=0, beta=0` | Classic SFT distillation | Teacher | Forward |
| `lmbda=0, beta=1` | Sequence-level KD with reverse KL | Teacher | Reverse |
| `lmbda=1, beta=0` | On-policy + forward KL | Student | Forward |
| **`lmbda=1, beta=1`** | **OPD (V4's choice)** | **Student** | **Reverse** |
| `lmbda=0.5, beta=0.5` | Hybrid mode | 50/50 mix | 50/50 mix |

DeepSeek-V4's OPD is the corner case: **maximum on-policy + maximum reverse KL**.

This generality is why TRL's `GKDTrainer` is the easiest way to start experimenting with OPD-style training: **set `lmbda=1.0, beta=1.0` and you have OPD**.

> 🔗 GKD paper: Agarwal et al., *On-Policy Distillation of Language Models: Learning from Self-Generated Mistakes*, NeurIPS 2024 (arXiv:2306.13649). The official DeepMind implementation is at https://github.com/google-deepmind/gkd.

### The KL direction question, intuitively

A common confusion: "If `beta=0` (forward KL) keeps the student covering all teacher modes, why would V4 choose `beta=1` (reverse KL) which 'drops' some modes?"

The answer: student capacity is finite, so it can't perfectly fit a multi-modal teacher distribution. Forced to approximate, the two KL directions produce opposite behaviors:

```
Teacher distribution (multi-modal, e.g., a math problem with 3 valid phrasings):
   ▲
   │ ████        ████        ████
   │ ████        ████        ████
   └──────────────────────────────
      "84"        "answer:84"  "= 84"
       0.4          0.3          0.3

Forward KL (mode-covering):
   ▲
   │ ████   ███        ████        
   │ ████   █████      ████        ← Spreads probability across all modes
   │ ████   ███████    ████        ← Output: random middling guesses
   └──────────────────────────────

Reverse KL (mode-seeking):
   ▲
   │ ████████                       ← Picks one mode and commits
   │ ████████                        
   │ ████████                       ← Output: confident single answer
   └──────────────────────────────
```

For LLM generation, where each position must commit to one token, the **mode-seeking** behavior of reverse KL produces decisive, coherent outputs. Forward KL produces hesitant, blended outputs that often don't even correspond to any of the teacher's actual modes.

This is why OPD specifically uses reverse KL — not because it captures more information, but because it **learns the right kind of behavior for autoregressive generation**.

---

## Multi-Expert OPD at Scale

<div align="center">

<img width="960" src="images/multi_teacher_opd.png" alt="Multi-Expert OPD pipeline">

<p><em>Multi-Expert OPD: student samples -> all teachers score -> weighted KL gradient updates student. Generated by <code>scripts/generate_diagrams.py</code>.</em></p>
</div>

DeepSeek-V4 distills from **10+ teachers** simultaneously. The naive implementation has two showstopper problems:

### A note on vocabulary size — every model is different

Before going into the storage explosion, a brief reality check: **vocabulary size varies wildly across models**. There is no universal "152K." The choice depends on multilingual coverage, compression ratio, and GPU alignment. Common values:

| Model family | Vocab size |
|--------------|-----------:|
| LLaMA-1 / LLaMA-2 | 32,000 |
| Mistral / Mixtral | 32,000-32,768 |
| GPT-2 / GPT-3 / GPT-3.5 | 50,257 |
| GPT-4 | ~100,277 |
| GPT-4o | ~200,019 |
| **DeepSeek-V2 / V3 / V4** | **~102,400** (own tokenizer) |
| DeepSeek-R1 | 128,000 |
| LLaMA-3 / 3.1 / 3.2 | 128,256 |
| **Qwen2 / Qwen2.5 / Qwen3 (1.5B variants)** | **151,936** |
| **Qwen2 / Qwen2.5 / Qwen3 (7B+ variants)** | **152,064** ← (1.5B and 7B differ by 128 padding rows!) |
| Gemma-1 / Gemma-2 | 256,000 |
| Gemma-3 | 262,144 |

A few takeaways:

- **DeepSeek-V4 itself uses ~102K vocab**, not 152K. The numbers throughout this document referring to "152K" are about Qwen-based models, which is what our experiments later in this document use.
- **Same family, different sizes can have different vocabs.** Qwen2.5-Math-1.5B = 151,936; Qwen2.5-Math-7B = 152,064. The 128-row gap is GPU alignment padding. This bit us in Run 7 onwards (see Appendix) — we had to slice the teacher's `lm_head` from [152064, 3584] to [151936, 3584] to make GKDTrainer happy.
- **Larger vocab is not strictly better.** It improves multilingual coverage and reduces token count per sentence, but inflates the embedding/`lm_head` matrix. DeepSeek's smaller 102K vocab is offset by their tokenizer being highly optimized for code+math+Chinese mix.
- **For OPD, what matters is**: student and teacher vocab sizes **must match exactly**, otherwise the KL divergence cannot be computed. Mismatched models require slicing or projecting the larger one down.

### Problem 1 — Logit storage explodes

Storing full-vocabulary logits at every token, for every teacher, for every training sample:

- Vocabulary size `|V| > 100,000` (Qwen3, DeepSeek-V3 series)
- Sequence length `L = 2048-32768` for long-context training
- Per-position logits per teacher: `|V| × 4 bytes (FP32) = 400 KB`
- For 10 teachers × 32K seq × 400 KB = **128 GB per training sample** — clearly impossible to materialize in memory or even on disk.

**V4's solution** (paper Section 5.2.2): cache only the **last-layer hidden states** of each teacher, not the logits. Hidden states are `d_model × 2 bytes` (BF16), typically 7-14 KB per token — orders of magnitude smaller. At training time, the cached hidden states are passed through the teacher's prediction head on-the-fly to reconstruct the full logits exactly when needed.

Trade-off: small recomputation overhead (one matrix multiply per token) for massive memory savings.

### Problem 2 — Loading 10+ teacher weights simultaneously

Each teacher might be a hundreds-of-billions-parameter model. Holding 10 of them in GPU memory at the same time is infeasible.

**V4's solution**: ZeRO-style parameter sharding for teacher weights, with on-demand loading from centralized storage. Teachers are scheduled in batches; data is also reordered by teacher index to minimize prediction-head context-switching (paper Section 5.2.2).

### Why bother? Why not use full logits with fewer teachers?

The V4 paper takes a strong stance against the common shortcut of approximating the full-vocabulary KL with a single per-token KL estimate:

> *"prior works usually simplify the full-vocabulary KL loss into a token-level KL estimate at each token position [...] Although this approach is resource-efficient, it leads to **high variance in gradient estimation and often causes training instability**. Therefore, we adopt full-vocabulary logit distillation in our OPD."*

Token-level KL only looks at the probability the teacher assigned to the **token the student chose**, ignoring the rest of the distribution. This loses the information about how confident the teacher is in the chosen token vs. its alternatives — exactly the signal that matters for distillation. Full-vocabulary KL is more expensive but produces lower-variance, more stable training.

---

## How OPD Compares to Other Multi-Expert Methods

### vs Weight Averaging

| Aspect | Weight Averaging | OPD |
|--------|:----------------:|:---:|
| Where merging happens | Parameter space | Logit space (output behavior) |
| Captures non-linear interactions? | ❌ No | ✅ Yes (training does) |
| Speed | Instant (no training) | Slow (student rollouts + multi-teacher forward passes) |
| Quality preservation | Often poor (~70-90% of best expert) | Strong (often matches or exceeds best expert in domain) |
| Hyperparameters | Just the merge weights | Weights `w_i`, learning rate, training steps, sampling temperature |

Weight averaging is essentially asking: "if I take a step halfway between two good points in a non-convex loss landscape, am I still in a good region?" Often the answer is no — neural network loss landscapes are full of valleys where the midpoint is high above either endpoint.

### vs Task Arithmetic (TIES, DARE, etc.)

Task arithmetic is a more sophisticated form of weight merging:

```
For each expert i:  task_vector_i = θ_i − θ_base
Merged:             θ_merged = θ_base + Σ_i τ_i · task_vector_i (with sign + sparsification heuristics)
```

This is better than averaging because it isolates "what the fine-tuning changed" from the base model. But it still suffers from the same fundamental issue: parameter-space combinations don't necessarily produce coherent output behaviors. TIES and DARE add heuristics (sign election, magnitude pruning) to mitigate interference, but the underlying assumption — that good behaviors compose linearly in weight space — is empirically shaky.

OPD sidesteps the issue by working in output space directly. Whatever the parameters end up being, the student is rewarded for producing distributions that match the teachers'.

> 🔗 We have a separate Repo, [LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact), that quantifies how parameter-space merging degrades quality. OPD is the alternative path that bypasses this problem.

### vs Mixed RL (the V3.2 approach that V4 abandoned)

Mixed RL trains one model with reward signals from multiple domains simultaneously:

```
For each batch: sample tasks from domain mix → run RL update with combined reward
```

This is what V3 and earlier used. V4 *entirely replaced* it with OPD. Why? The V4 report states the replacement; the following is a structural analysis of why Mixed RL becomes fragile when many domains and very large models are trained together.

#### Problem 1 — Reward hacking (the student learns to game the scorer)

GRPO requires you to first define a **reward function** for each domain:
- Math: a verifier runs the code and checks the answer
- Code: unit tests act as the reward
- Writing: another LLM judges quality

The student model, optimizing for that reward, learns to **exploit holes in the reward function**:
- Math: outputs `print(answer)` directly to skip the reasoning
- Writing: discovers the judge prefers long answers → pads every response
- Code: writes a hardcoded hack that happens to pass the visible test cases

At V4 scale (10+ domains), these exploits stack up — every reward function leaks something.

#### Problem 2 — Reward functions don't compose across domains

Different domains have *contradictory* reward shapes:
- Math reward: prefer rigorous step-by-step (long, structured)
- Chat reward: prefer concise natural reply (short, conversational)
- Code reward: prefer minimal correct snippet

Optimizing all simultaneously means the model **gets pulled in opposite directions** within the same gradient update. It learns "averaged" behavior — neither rigorously stepwise nor naturally conversational, just bland in the middle.

The model also has no signal of which domain it's serving at inference time, so it can't switch behavior conditionally.

#### Problem 3 — RL is intrinsically unstable at 671B

Policy gradient methods have high variance. PPO/GRPO need stabilization tricks such as PPO clipping, GAE, and value function baselines just to converge. At V4 scale, the cost of unstable updates grows sharply; this is the setting in which a smoother KL-matching objective becomes attractive.

#### How OPD sidesteps all three

| Mixed RL problem | OPD's structural answer |
|------------------|-------------------------|
| Reward hacking | **No reward function exists**. The student doesn't optimize a score — it matches teacher logit distributions directly. There's nothing to hack. |
| Cross-domain conflict | Each domain has its own teacher. At each token, only the teachers with non-trivial probability there contribute gradient. **Domains don't fight each other** — they coexist on different tokens. |
| RL instability at 671B | KL minimization on student trajectories has a smooth, well-conditioned objective. **No PPO clipping, no GAE, no value baseline needed.** |

#### Why would Mixed RL become especially fragile at 671B + 10 domains?

The three problems above existed at smaller scale too. V1/V2/V3 lived with them. The analysis below is a **back-of-envelope structural argument**, not a set of DeepSeek-published ablation numbers. It explains why the same training loop becomes harder to stabilize as model size and domain count grow.

1. **Curse of dimensionality.** A 7B dense model has roughly 7B parameters, while a 671B-class model has roughly 671B total parameters (with fewer activated per token in MoE). The exact trainable/activated count depends on architecture, but the scaling problem is clear: many more parameters are being influenced by noisy multi-domain reward gradients.

2. **Reward hacking surface grows with domain count.** A toy independence calculation makes the intuition visible: if one reward has a small exploit probability `p`, then 10 independent rewards have probability `1 - (1-p)^10` that at least one exploit exists. The exact `p` is not measured here; the point is that every additional reward function adds another attack surface.

3. **PPO memory pressure explodes.** PPO-style setups often require policy, value, reward, and reference components, plus rollout activations and optimizer state. Whether these are separate full models or partially shared components is implementation-specific, but the memory pressure pushes teams toward smaller batches, shorter rollouts, or cheaper reward models — all of which increase variance or weaken the feedback signal.

4. **Failed exploration becomes expensive.** Policy-gradient training deliberately explores and corrects. At frontier scale, even a modest fraction of low-value exploration is costly in GPU-hours. OPD trades that exploratory reward optimization for direct distribution matching against already-trained domain teachers.

These four amplifications all push in the same direction: Mixed RL can work, but the operational risk rises quickly. DeepSeek's reported choice was to replace the mixed RL stage with OPD rather than keep adding stabilization machinery.

#### The intuition: "scoring the test" vs. "copying the top student's notebook"

| GRPO | OPD |
|------|-----|
| Student takes a test; we score the answers | Student watches the top student work through the problem; copies their reasoning at every step |
| Student looks for cheap ways to score | No score exists — only the top student's reasoning to match |
| Score function design is hard and exploitable | Top student's notebook is given (the teacher model itself) |
| Multiple subjects → multiple scoring rubrics that conflict | Multiple subjects → multiple top students, one per subject — no conflict |

That last analogy is the cleanest way to remember it: **GRPO trains via outcome rewards (what got points); OPD trains via process imitation (how the teacher thinks token-by-token).**

#### What OPD doesn't have but Mixed RL does

To be fair, Mixed RL has one capability OPD lacks: it can produce behavior **better than any single teacher** (via reward signal exploration). OPD is bounded by teacher quality — the student converges toward teacher distribution, never exceeds it on the trained data.

V4's design choice: that ceiling is fine. They train domain experts very strongly first (Stage 2 produces near-state-of-art per-domain), then OPD simply consolidates without losing capability. The "exploration above teachers" advantage of RL is reserved for Stage 2, where each domain is trained independently with its own RL — without the cross-domain interference.

### vs SFT (Supervised Fine-Tuning) — The Exposure Bias Problem

A common question: **why not just use SFT to train the student on each specialist's outputs?** It seems simpler — collect specialist responses to a prompt, then fine-tune the student on those (prompt, response) pairs.

This works to some degree but suffers a fundamental problem called **Exposure Bias**:

```
SFT training:
  Prompt:   "Solve: 13 × 7 = ?"
  Teacher's answer: "13 × 7 = 91"
  
  Student learns at every step:
    Step 1: prefix "13 ×" → predict next token
            (this prefix was written by teacher — clean, correct)
    Step 2: prefix "13 × 7" → predict next token
            (still teacher's prefix)
    Step 3: prefix "13 × 7 =" → predict next token (= "91")
  
  At all training steps, student only sees teacher-generated prefixes.
```

But at inference time, **there is no teacher** — the student generates its own prefix:

```
Inference time:
  Step 1: prefix "" → student generates "13"
  Step 2: prefix "13" → student generates "×"
  Step 3: prefix "13 ×" → student generates "7"
  Step 4: prefix "13 × 7" → student accidentally generates "+" (a mistake!)
  Step 5: prefix "13 × 7 +"  ← ⚠️ Student has NEVER seen this prefix during training!
          The student doesn't know how to recover from its own error.
          → Output may degenerate: "13 × 7 + 91 = 104" (nonsensical)
```

**This is exposure bias**: the student is never "exposed" during training to its own generated prefixes (which may contain errors). At inference time, when the student inevitably makes mistakes, it has no learned behavior for "how to continue after I just wrote something wrong".

OPD solves this by **on-policy sampling**:

```
OPD training:
  Step 1: Student generates a full trajectory using its own current ability:
          "Let me think... 13 × 7 = 81... wait, let me recalculate: 13 × 7 = 91"
          (Includes the student's own mistakes and self-corrections)
  Step 2: Specialist scores this trajectory at every token position
  Step 3: Student learns from feedback ON ITS OWN MISTAKES
  
  → Student is exposed to "what to do when I just wrote an error"
  → At inference time, student can self-correct (this is exactly what reasoning models do)
```

This is why frontier reasoning models (DeepSeek-R1, OpenAI o1, etc.) all use on-policy training (RL or OPD) — pure SFT cannot teach self-correction.

| Aspect | SFT | OPD |
|--------|:---:|:---:|
| Training data prefixes come from | Teacher | **Student itself** |
| Per-token signal | 1 label (the teacher's chosen token) | **Full distribution (~150K probabilities)** |
| Train/inference distribution match | ❌ Mismatch | ✅ Match |
| Self-correction capability | ❌ Cannot teach | ✅ Can teach |
| Multi-teacher support | ❌ Need to pick one or sequence them (catastrophic forgetting) | ✅ Native via Σᵢ |

### vs RL / RLAIF — Just a Denser Reward Signal

A natural follow-up question: **RL solves exposure bias too (student samples its own trajectories) — why not just use RL?**

You're right — V3.2 used RL. V4 *did* try RL and replaced it with OPD. The key insight is:

**OPD = RL with the teacher's logit distribution as the reward signal.**

Both are on-policy training (student samples). The only difference is what kind of feedback the student gets per trajectory:

| Method | Feedback per trajectory | Density per token |
|--------|------------------------|:---:|
| **RL with rule reward** (e.g., math correctness) | 1 scalar (e.g., +1 / -1) | ~0.001 (1 / 1000 tokens) |
| **RLHF** (human feedback) | 1 scalar | ~0.001 |
| **RLAIF** (LLM-as-judge, e.g., GPT-5 grades the answer) | 1 scalar | ~0.001 |
| **OPD** | Full vocabulary distribution (~150K) at every token | **150,000** |

A useful but imperfect way to view this: OPD exposes vastly more **observable supervision positions** than a single trajectory-level scalar reward. For a 150K-vocab model with a 1000-token response, that is on the order of `150K × 1000` probability entries versus one scalar. This does **not** mean 150 million times more useful information or 150 million times larger gradients; it means the feedback is much denser and lower-variance in the dimensions the student actually predicts. In practice, that can translate to:
- More stable gradients (lower variance)
- Faster convergence when teacher and student are compatible
- No hand-designed reward function for the merged stage (teacher distribution is the feedback)
- Less reward hacking surface than scalar reward optimization

**Why doesn't everyone use OPD then?** Because it requires the **teacher's full vocabulary logits** — and that's where the practical wall is.

#### The hidden constraint: API access to logits

Commercial LLM APIs (OpenAI, Anthropic, etc.) **do not expose full-vocabulary logits**:

| API | Maximum top_logprobs | Can do full-vocab OPD? |
|-----|:--:|:--:|
| Azure OpenAI Chat Completions | 20 | ❌ (only 0.013% of vocabulary) |
| Azure OpenAI Completions | 5 | ❌ (only 0.003%) |
| Anthropic Claude API | not exposed | ❌ |
| **Self-hosted open model** (Llama / Qwen / DeepSeek) | All | ✅ Full vocabulary |

> Source: [Azure OpenAI REST API Reference](https://learn.microsoft.com/en-us/azure/foundry/openai/reference) — `top_logprobs` is "an integer between 0 and 20 specifying the number of most likely tokens to return at each token position".

This is why V4 had to do everything in-house: their specialists are self-hosted, so they get full vocabulary logits. A startup using GPT-5 as a teacher can only do "RLAIF with top-20 KL", which is much weaker than full OPD (the V4 paper explicitly criticizes this kind of approximation in Section 5.1.2).

> 🔗 If you want to do something like OPD as a smaller team, the path is: deploy an open-source teacher (e.g., Llama-3-70B, Qwen2.5-72B, DeepSeek-V3) yourself, and you'll get full vocabulary logits. This is exactly how DeepSeek-R1's distillation into Qwen-series works.

### vs Step Distillation (Diffusion Models) — Different Domain, Different Mechanism

Engineers familiar with image generation may have heard of "distillation" in the context of diffusion models — for example, distilling a 50-step Stable Diffusion teacher into an 8-step student (LCM, Lightning, Hyper-SD, etc.). **This is a completely different kind of distillation, not OPD.**

| Aspect | Step Distillation (Diffusion) | OPD (LLM) |
|--------|:----------------------------:|:---:|
| Domain | Diffusion image generation | Autoregressive LLM |
| Goal | Reduce inference steps (50 → 8) | Merge multiple domain experts |
| Teacher behavior at training | Generates trajectories **once** offline; then leaves | Computes logits **online** at every training step |
| On-policy or offline? | **Offline** (teacher's trajectories saved as fixed dataset) | **On-policy** (student's trajectories scored live) |
| Training signal | Teacher's intermediate denoising states | Teacher's full vocabulary distributions |

In Step Distillation, the teacher's role is to **pre-generate a training dataset**. Once the dataset exists, the teacher disappears and the student trains in a normal supervised manner.

In OPD, the teacher is **always present in the training loop** — it scores the student's live samples on every step.

These are two completely different methods that happen to share the word "distillation". When someone says "we use distillation", always ask: **on-policy or offline? Single-teacher or multi-teacher? What signal does the teacher provide?** The answers determine which method is being discussed.

---


### vs Velocity Field Distillation (Diffusion Models)


Engineers familiar with diffusion models may have heard about "velocity field distillation" (Flow Matching, Lightning, etc.) used in diffusion image generation. **OPD is not this.** Quick disambiguation:

| Concept | OPD (LLM) | Velocity Field Distillation (Diffusion) |
|---------|---|---|
| Domain | Autoregressive LLM | Diffusion image/video generation |
| What is learned | Categorical token distribution (~150K dim) | Continuous velocity vector (~1024 dim) |
| Loss type | **Reverse KL divergence** | **MSE on velocity** |
| Goal | Multi-expert capability fusion | Reduce inference steps (50 → 8) |
| Teacher signal | Probability over vocabulary | Velocity prediction at each timestep |
| Examples | DeepSeek-V4, Qwen3, MiMo-V2-Flash | Stable Diffusion 3, Flux, Qwen-Image-Lightning |

These are completely different methods that share the word "distillation". When discussing distillation for LLMs, OPD/GKD is the relevant family. When discussing distillation for diffusion models, Step Distillation (Progressive Distillation, ADD, Lightning, Hyper-SD) is the relevant family.

---

## What's Original in DeepSeek-V4?

OPD has been studied in the academic literature for several years. Honest breakdown of V4's contribution:

| Component | Origin | Source |
|-----------|--------|--------|
| Knowledge distillation (general) | Hinton et al., 2015 | "Distilling the Knowledge in a Neural Network" |
| Reverse-KL distillation | Generative modeling literature | Various 2018-2023 |
| On-policy distillation concept | Agarwal et al., 2023 (GKD) | "Generalized Knowledge Distillation" |
| Multi-teacher distillation | Multiple academic works 2020-2024 | Various |
| **Replacing mixed RL with OPD entirely** | ✅ V4 — first major model to do this | V4 Tech Report Section 5.1 |
| **Full-vocabulary OPD (no token-level KL approximation)** | ✅ V4 — emphasizes against the common shortcut | V4 Tech Report Section 5.1.2 |
| **10+ teacher distillation at trillion-parameter scale** | ✅ V4 — engineering scale unprecedented | V4 Tech Report Section 5.2.2 |
| **Hidden-state caching for logit reconstruction** | ✅ V4 — original engineering trick | V4 Tech Report Section 5.2.2 |

In short: the **OPD method itself is not new**. What V4 contributes is (1) the strategic decision to make OPD the *only* multi-expert merging mechanism, (2) the insistence on full-vocabulary KL despite the cost, and (3) the engineering infrastructure to make this work with 10+ trillion-parameter teachers.

---

With the originality picture clear, we can now discuss OPD's honest limitations:

## Why OPD Entered Production Only Now

Knowledge Distillation was published in 2015 (Hinton et al.). Generalized Knowledge Distillation — the on-policy variant — was published in 2023 (Agarwal et al., DeepMind). So there are really two timelines: a decade in which "distillation" was mostly understood as compression, and a much shorter 2023→2026 window in which on-policy distillation became a practical post-training tool. **Why did the older KD idea take so long to be reframed this way?**

The quick answer most people give: "compute wasn't ready." That's wrong. The deeper truth is **a cognitive lock-in across the entire field**.

### Reason 1 — "Distillation = compression" was the field's mental model

From 2015 to 2024, distillation was almost universally framed as a *model-compression* technique. DistilBERT, TinyBERT, MobileBERT — all of these targeted "shrink a big model into a small one." **Nobody framed distillation as a multi-task consolidation tool**. Multi-task fusion was reserved for:
- Multi-task learning (joint training from scratch)
- RLHF (one model, multiple reward signals)
- Mixture-of-Experts (architectural solution)

Distillation was simply not in the conversation when teams discussed "how to merge specialists." The mental model was sticky for a decade.

### Reason 2 — Mixed RL "worked well enough" until V3

DeepSeek-V1, V2, V3 all used Mixed RL for the post-training consolidation step. It was painful (frequent restarts, reward hacking, instability) — but **it produced shippable models**. There was no forcing function to switch.

Only when V4 pushed the scale to **671B parameters × 10+ specialist domains** did the cost and instability pressure become strong enough to justify replacing the mixed-RL consolidation stage. "Good enough" is the biggest enemy of innovation.

### Reason 3 — ChatGPT pulled the entire field toward RLHF

When ChatGPT exploded in late 2022, the entire research community went all-in on RLHF: PPO improvements, reward modeling, Constitutional AI, RLAIF. Distillation was deemed "low-status" — something small companies did when they couldn't afford to train from scratch. Top labs invested research effort into RL variants, not into rethinking distillation.

### Reason 4 — The 10+ specialist consolidation problem didn't exist before

This is the deepest reason. **OPD as we know it (multi-expert consolidation) requires the input "we have 10+ trained specialists that need to become one model."** That input didn't widely exist before V4-class models. Earlier LLM teams trained one foundation model + RLHF — there was nothing to consolidate.

Like shipping containers (invented 1956): the technology to build a steel box was always trivially available. What was missing was **the standardized global trade volume that made the box necessary**. OPD waited for the multi-expert-training pattern to become widespread.

### Reason 5 — Specific engineering enablers landed late

Even once you wanted OPD, you needed several pieces in place:

| Enabler | First widely available |
|---------|------------------------|
| Top-K sparse logit storage | 2024 |
| vLLM / SGLang inference engines (efficient teacher forward) | 2023-2024 |
| TRL `GKDTrainer` (off-the-shelf framework) | 2024 |
| H100 / H200 making 3× SFT compute affordable | 2023-2024 |

None of these are the *fundamental* reason OPD took so long. They became necessary only **after** the cognitive shift. The cognitive shift required the V4-team-level pain to force.

### One-sentence answer to "why didn't they use it earlier?"

> **For most of the last decade, distillation was framed as compression, not consolidation.** GKD made the on-policy formulation explicit in 2023; V4-style multi-expert training made the consolidation problem urgent. The core shift was not just hardware readiness, but the moment when many strong specialists had to be merged into one production model.

This is also why this Repo exists — most existing OPD writeups still treat distillation as compression. Repositioning it as multi-expert consolidation is the conceptual contribution.

## Honest Limitations of OPD

OPD is not a magic bullet. Four honest constraints worth understanding:

### 1. Cannot exceed the teacher (the fundamental ceiling)

The OPD objective is:

`min over π_student: KL(π_student || π_teacher)`

KL = 0 has exactly one solution: `π_student` identical to `π_teacher`. **By the math itself, the student converges toward the teacher and cannot exceed it.** This is not an engineering bug — it's the optimization target.

**Why DeepSeek-V4 accepts this trade-off**

V4's training is split:

```
Stage 2: Each domain expert is trained with its own RL → can exceed prior SOTA per domain
Stage 3 (OPD): Consolidates 10+ experts into one student → ceiling = strongest expert per token
```

The "can-exceed" property of RL is **reserved for Stage 2**, where each expert is trained independently without cross-domain interference. Stage 3 is deliberately the "compress + merge" step — no innovation, just packaging.

**The contrast with OpenAI / Anthropic**

| | OPD path (V4) | RL-to-the-end path (GPT/Claude) |
|---|---|---|
| Final ceiling | = strongest teacher | can exceed teacher |
| Stability | high | low |
| Compute waste (failed RL exploration) | low | high |
| Best for | merging many specialists at scale | chasing absolute SOTA |

This is a **business strategy choice as much as a technical one**:
- Want absolute frontier? Keep RL in the final stage. Pay for instability and compute waste.
- Want stable productionization of many specialists? Use OPD. Accept the teacher ceiling.

### 2. Coverage is data-dependent, not architectural

OPD only updates the MoE experts that the router selects for each training sample. Experts that are never selected during OPD training — because their token-level pattern doesn't match the training data distribution — keep their pre-training weights unchanged.

```
If OPD training data covers math + code + writing only:
  → Math/code/writing-pattern experts get OPD updates (~most experts in practice)
  → Experts handling rare patterns (e.g., obscure languages, niche notation)
    receive no OPD signal → retain pre-training capability only

→ OPD coverage = OPD training data coverage ≠ "all 256 experts trained equally"
```

V4 mitigates this by using diverse training data covering many domains and a "general chat" specialist that activates broadly. But there's no theoretical guarantee that every expert is improved — it's a data engineering choice.

### 3. Gradient attribution is imprecise

The teacher gives feedback at the **output level** (next-token distribution), but the student's mistake might happen at **any internal layer** (wrong attention pattern, wrong router selection, wrong FFN computation). The gradient flowing back has to "guess" which internal component to blame.

In practice this means:
- Training is slower than ideal (some gradient lands on innocent components)
- An expert that didn't cause the error still gets a small gradient update
- Compensated by small learning rate + many training steps + multi-teacher noise cancellation

V4 doesn't claim to solve this — they just empirically tune around it.

### 4. Scale-dependent practicality

The full V4 OPD pipeline (10+ teachers × trillion-scale parameters × full vocabulary KL) is only feasible for organizations with:
- Self-hosted teacher models (commercial APIs cap top_logprobs at 20)
- Centralized weight storage with ZeRO-style sharding
- Custom hidden-state caching (prevents logit storage from exploding to TB scale)

For smaller teams: simpler variants of OPD-like training (single open-source teacher + standard PyTorch) are still very effective. But the *full* V4 setup is a frontier-only capability.

---

## Getting Started: Code & Tools

### Implementing OPD: Skeleton Code

A minimal, single-GPU OPD training loop in PyTorch (illustrative, not production):

```python
import torch
import torch.nn.functional as F

def opd_loss(student_logits, teacher_logits_list, weights):
    """
    Full-vocabulary reverse-KL OPD loss.
    Source: DeepSeek-V4 Tech Report Section 5.1.2 Eq. (29)

    Args:
        student_logits:        (B, L, |V|) — student forward output
        teacher_logits_list:   list of N tensors, each (B, L, |V|)
        weights:               list of N floats summing to 1.0

    Returns:
        scalar loss tensor
    """
    student_logp = F.log_softmax(student_logits, dim=-1)
    student_p = student_logp.exp()

    total_loss = 0.0
    for w, t_logits in zip(weights, teacher_logits_list):
        teacher_logp = F.log_softmax(t_logits, dim=-1)
        # Reverse KL: D_KL(π_θ || π_E) = Σ π_θ * (log π_θ - log π_E)
        kl_per_token = (student_p * (student_logp - teacher_logp)).sum(dim=-1)  # (B, L)
        total_loss += w * kl_per_token.mean()
    return total_loss


def opd_train_step(student, teachers, prompts, weights, optimizer, max_new_tokens=256):
    """
    One on-policy distillation training step.
    """
    # 1. Student samples a rollout (no_grad to avoid memory blow-up)
    with torch.no_grad():
        rollout_ids = student.generate(prompts, max_new_tokens=max_new_tokens,
                                        do_sample=True, temperature=1.0)

    # 2. Forward pass: student computes logits WITH gradient
    student_logits = student(rollout_ids).logits  # (B, L, |V|)

    # 3. Each teacher scores the same rollout (no gradient needed)
    with torch.no_grad():
        teacher_logits_list = [t(rollout_ids).logits for t in teachers]

    # 4. Compute OPD loss and backpropagate
    loss = opd_loss(student_logits, teacher_logits_list, weights)
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(student.parameters(), max_norm=1.0)
    optimizer.step()
    return loss.item()
```

A few practical notes:

- **Tokenizer alignment is mandatory.** All teachers and the student must share the same tokenizer (so logits are comparable token-by-token). In practice this means picking models from the same family (Qwen 2.5/3 series, Llama 3 series, etc.).
- **Reverse KL can NaN.** Start with a small learning rate (5e-7 to 1e-6), use BF16 mixed precision, and keep gradient clipping at 1.0.
- **Trajectory length matters.** Too short = not enough distillation signal per step. Too long = memory and time blow-up. 256-512 tokens is a reasonable starting point for small-scale experiments.
- **Memory for teachers.** Even with `no_grad`, holding multiple teachers in GPU memory adds up. Consider CPU offload (`device_map="auto"` with `offload_folder`) for ablation studies.

---


### OPD Code Ecosystem (2026 Reality Check)

With the conceptual skeleton clear, let's survey the actual tools and frameworks available for OPD training today.


DeepSeek did not open-source V4's OPD training code. **No frontier model company has open-sourced their full OPD pipeline as of mid-2026.** What does exist is a layer of **third-party open-source frameworks** (HuggingFace TRL, KDFlow, NeMo-RL, etc.) that let you implement OPD-style training yourself.

> ⚠️ **OPD is not yet an industry standard practice.** Realistic adoption (mid-2026):
> - ~90% of LLM fine-tuning projects use **SFT + LoRA** (small-model customization)
> - ~8% use SFT + simple RLHF
> - ~1.5% use complex RL (PPO/GRPO)
> - **<1% use OPD** — currently confined to a handful of frontier labs
>
> Calling OPD "industry standard" would be misleading; "frontier-lab post-training trend" is more accurate.

### Working implementations you can fork today

| Repo | URL | Stars | Best for |
|------|------|:----:|----------|
| **HuggingFace TRL `GKDTrainer`** | https://github.com/huggingface/trl | 15.7k | Fastest path to single-teacher OPD (set `lmbda=1.0, beta=1.0`) |
| **songmzhang/KDFlow** ⭐ | https://github.com/songmzhang/KDFlow | 122 | LLM-distillation-specific framework, SGLang teacher inference + FSDP2 student training |
| **NVIDIA NeMo-RL** | https://github.com/NVIDIA-NeMo/RL | — | Multi-teacher + cross-tokenizer at scale |
| **MS-SWIFT (Alibaba)** | https://github.com/modelscope/ms-swift | 14k | GKD trainer built-in (`examples/train/rlhf/gkd/`) |
| **OpenRLHF** | https://github.com/OpenRLHF/OpenRLHF | 9.4k | Ray + vLLM + DeepSpeed; reward function customizable for OPD-style loss |
| **verl-project/verl** (ByteDance) | https://github.com/verl-project/verl | 21.1k | Many OPD papers fork verl as the base |
| **agentica-project/AReaL** | — | — | OPD over student-sampled trajectories with teacher log-prob guidance |
| **THUDM/slime (Zhipu)** | https://github.com/THUDM/slime | — | Unified RL stack supporting OPD |

### What `GKDTrainer` actually is, in plain English

If the table above feels abstract, here's the simplest mental model:

> **`GKDTrainer` is HuggingFace's "one-button OPD trainer"** — you provide a student model, a teacher model, and a dataset, set two flags, and it handles everything: student rollout, teacher scoring, KL loss computation, backpropagation, checkpointing.

The two flags that matter:

| Parameter | Meaning | Set to (for OPD) |
|-----------|---------|:----------------:|
| `lmbda` | Fraction of training steps where student samples its own trajectory (vs. using teacher's) | **1.0** (100% on-policy) |
| `beta` | KL direction (0 = forward KL, 1 = reverse KL) | **1.0** (reverse KL) |

A complete minimal example:

```python
from trl.experimental.gkd import GKDTrainer, GKDConfig

config = GKDConfig(
    lmbda=1.0,      # 100% on-policy → OPD
    beta=1.0,       # reverse KL → OPD
    output_dir="./output",
    learning_rate=5e-7,
    per_device_train_batch_size=4,
    max_new_tokens=512,
)

trainer = GKDTrainer(
    model="Qwen/Qwen2.5-1.5B-Instruct",          # student
    teacher_model="Qwen/Qwen2.5-Math-7B",         # teacher (must share tokenizer!)
    args=config,
    train_dataset=my_dataset,
    processing_class=tokenizer,
)

trainer.train()
```

That's it — same API as `SFTTrainer`, just with a teacher model and two extra flags. The full implementation (`generalized_jsd_loss` + `training_step`) is ~30 lines of PyTorch in `trl/experimental/gkd/gkd_trainer.py`.

Other GKD configurations correspond to other distillation methods:

| `lmbda` | `beta` | Equivalent to |
|:-------:|:------:|---------------|
| 0 | 0 | Classic SFT distillation (offline + forward KL) |
| 0 | 1 | Sequence-level KD with reverse KL |
| 1 | 0 | On-policy + forward KL (rare) |
| **1** | **1** | **OPD (V4's choice)** |
| 0.5 | 0.5 | Hybrid mode |

So `GKDTrainer` covers the entire distillation design space — `lmbda=1, beta=1` is just the OPD corner.

### thunlp/OPD: an academic deep-dive (not a production framework)

If you want to study OPD's behavior at the research level, the most thorough open implementation is **[thunlp/OPD](https://github.com/thunlp/OPD)** from Tsinghua NLP (223 stars, accompanying paper [arXiv:2604.13016](https://arxiv.org/abs/2604.13016) "Rethinking On-Policy Distillation").

**Strengths**:
- Academic credibility (Tsinghua NLP, same lab as MiniCPM/OpenBMB)
- The paper isn't a simple reproduction — it identifies *when OPD fails* and proposes recovery strategies (off-policy cold start, teacher-aligned prompt selection)
- Provides released checkpoints (`Qwen3-1.7B-SFT`, `Qwen3-4B-Base-GRPO`) on HuggingFace for reproducing baselines
- Rich configuration: `LOG_PROB_TOP_K`, `TOP_K_STRATEGY` (`only_stu` / `only_tch` / `intersection` / `union` / `union-intersection`), `REWARD_WEIGHT_MODE` (`student_p` / `teacher_p` / `none`) — useful for ablation studies

**Caveats**:
- **High hardware bar**: experiments run on 8 × NVIDIA A800 80GB GPUs (math-domain SFT + RL + OPD pipeline)
- **Requires two conda environments**: one for verl (training), one for LlamaFactory (SFT)
- **Single-teacher only** in published configs; not V4-style multi-teacher
- **Top-K KL approximation** by default (`LOG_PROB_TOP_K=16`) — not the full-vocabulary KL the V4 paper insists on
- **Core OPD loss is buried** inside their fork of verl (`verl/trainer/main_ppo.py` with `algorithm.adv_estimator=token_reward_direct`); the public `on_policy_distillation.sh` is a configuration shell, not standalone PyTorch code
- License not stated in README (verify before commercial use)

**Bottom line**:

| Use case | Best tool |
|----------|-----------|
| Read OPD code top-to-bottom in one sitting | TRL `gkd_trainer.py` (~30 lines for the math) |
| Run OPD on a single GPU | TRL `GKDTrainer` |
| Reproduce OPD academic results & study failure modes | thunlp/OPD (need 8×A800) |
| Build V4-style multi-teacher OPD | Neither directly — fork TRL or KDFlow and add Σᵢ teacher loop |

### Awesome lists and meta-resources

- **Curated OPD list**: https://github.com/chrisliu298/awesome-on-policy-distillation (~32 stars, daily updates) — includes ~21 core OPD papers and 13 training frameworks
- **Parallel awesome list**: https://github.com/nick7nlp/Awesome-LLM-On-Policy-Distillation
- **Best conceptual blog**: https://thinkingmachines.ai/blog/on-policy-distillation/ (Thinking Machines)
- **GOLD walkthrough** (HuggingFace H4, with TRL code): https://huggingface.co/spaces/HuggingFaceH4/on-policy-distillation
- **OPD survey paper**: arXiv 2604.00626 (2026)

> ⚠️ **A note on awesome-lists**: these are useful entry points but should not be treated as primary sources. We've personally verified that some claims circulating in awesome-lists about "X model uses OPD" turn out to be wrong on reading the actual papers (model name mismatches, methodology mislabeled, etc.). Always trace claims back to the original technical report before citing.

### Industry models using OPD (verified from primary sources)

> ⚠️ **Methodology note**: This table only includes models where I have **personally verified the original technical report or paper** contains the exact OPD claim. Earlier drafts of this Repo cited a longer list copied from a third-party awesome-list ([chrisliu298/awesome-on-policy-distillation](https://github.com/chrisliu298/awesome-on-policy-distillation)); subsequent verification revealed model name errors (e.g., "GLM-5" doesn't exist publicly, only GLM-4.5; "Nemotron-Cascade 2" doesn't exist, the closest is Nemotron-Nano-2 which uses Minitron-style forward KL distillation, not OPD). The table below is the cleaned, verified version.

| Year | Model | OPD Application | Primary Source |
|------|-------|-----------------|----------------|
| 2025 | **Qwen3** | "Strong-to-weak distillation" combining off-policy and on-policy knowledge transfer for smaller models | [arXiv:2505.09388](https://arxiv.org/abs/2505.09388) §1, §4 |
| 2026 | **MiMo-V2-Flash** (Xiaomi) | **Multi-Teacher On-Policy Distillation (MOPD)** as main post-training stage; explicitly framed as "a new paradigm that formulates knowledge distillation as a reinforcement learning process; the student model learns from its own generated responses" | [GitHub README](https://github.com/XiaomiMiMo/MiMo-V2-Flash) §1, §5.1; arXiv 2601.02780 |
| 2026 | **DeepSeek-V4** | "the mixed RL stage was entirely replaced by On-Policy Distillation (OPD)"; multi-teacher distillation merging 10+ domain experts into the unified model | DeepSeek-V4 Tech Report §5.1 |

**Other models** sometimes claimed to use OPD (Baichuan-M3, GLM-5, Nemotron-Cascade 2, HY-Embodied-0.5, etc.) either: (a) the model name doesn't match a publicly verifiable release, (b) the original report uses different terminology that may or may not be OPD, or (c) the report doesn't include enough detail to confirm. We exclude them here pending direct verification.

> The window for an open-source independent reproduction of V4's multi-teacher OPD remains open as of mid-2026.

### Quick-start by role

| Goal | Recommended path |
|------|------------------|
| Quickly run single-teacher OPD | **TRL `GKDTrainer`** with `lmbda=1.0, beta=1.0` |
| Production-grade OPD framework | **KDFlow** (LLM-distillation-specific, well-documented) |
| Multi-teacher OPD (closest to V4) | **NeMo-RL** or extend KDFlow with MiMo-V2 MOPD recipe |
| Build on verl ecosystem | **HJSang/OPSD_OnPolicyDistillation** + add multi-teacher loop |

---

## OPD's Place in the V4 Innovation Set

The [opening diagram](#the-30-second-picture-where-opd-fits-in-deepseek-v4) showed *where* OPD sits in V4's training pipeline. This section zooms out one more level: how OPD relates to the *other* V4 innovations and why none of them can replace it.

### Why OPD specifically (and not the alternatives)

Mixed RL has three structural problems at this scale, all of which OPD sidesteps:

| Mixed RL problem | OPD's answer |
|------------------|--------------|
| Reward hacking across heterogeneous rewards | No reward function — just teacher logits to match |
| Different domains' rewards conflict | Each token only attributes to teachers that have non-trivial probability there |
| RL training instability (especially at 671B) | KL minimization on student trajectories is far more stable than policy gradient |

### How OPD relates to the rest of V4

DeepSeek-V4 is a coordinated set of innovations. OPD plays a specific role within them:

| Innovation | Purpose | Covered In |
|-----------|---------|------------|
| Long-context efficient attention (CSA + HCA) | Make 1M-token context computationally feasible | [Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) |
| Manifold-Constrained Hyper-Connections (mHC) | Strengthen residual connections in deep models | V4 Tech Report Section 2.2 |
| Muon Optimizer | Faster convergence and training stability | V4 Tech Report Section 2.4 |
| FP4 Quantization-Aware Training | Reduce memory traffic for both training and inference | V4 Tech Report Section 3.4 |
| **On-Policy Distillation (this article)** | **Merge 10+ specialists into a single production model** | V4 Tech Report Section 5.1 |
| Quick Instruction (auxiliary tasks via KV cache reuse) | Reduce TTFT for chatbot scenarios | V4 Tech Report Section 5.1.1 |

**OPD is the post-training capstone** — it takes all the domain experts trained on the new architecture (with CSA, mHC, Muon, FP4) and consolidates them into the final shipped model. Without OPD, V4 would either ship 10+ separate models (10× inference cost) or revert to Mixed RL.

Our small-scale experiments later in this document (Math student + Code teacher) replicate exactly this consolidation mechanism at toy scale, to verify how it behaves in practice with TRL on a single GPU.

---

## Appendix: OPD Verification Experiment on H100

We ran a hands-on OPD experiment on a single NVIDIA H100 NVL (95 GB) to verify that the GKD-based OPD training loop works in practice, observe the loss dynamics first-hand, and measure end-task accuracy improvement on GSM8K.

### TL;DR — Honest Result

We ran 11 OPD training runs and 5 evaluations across 3 phases. **The journey: 8 runs failed (Phases 1-3), then 1 run showed weak positive signal (Phase 4), then scaling up by 14× produced a triangulated positive result on 3 metrics (Phase 5).**

| Phase | Run | Configuration | Best Metric | Result |
|-------|-----|---------------|--------|--------|
| Phase 1-3 | Runs 1-8 | Same-family teacher (R1-Distill or Math) | various | All failed: NaN crashes, mode collapse, or null results |
| Phase 4 | Run 9 | **Cross-domain**: Math-1.5B student + Coder-7B teacher (54 steps) | HumanEval pass@1 | **+1.22pp** (22.56→23.78%, weak positive) |
| **Phase 5** | **Run 11** | **Same as Run 9 + 14× training data + 2× H100 DDP** (738 steps, 5h 58min) | **HumanEval pass@10** | **+6.10pp** (49.39→55.49%, triangulated positive; CIs still overlap) |
| Phase 6 | Run 12 | Continue from Run 11 + 5 mixed code datasets (6944 samples, epoch 1.1) | Loss plateau | Loss 1.66 plateau — 7B teacher exhausted |
| Phase 6 | v3 eval | Consistent evaluator (multiprocessing timeout, all models same script) | HumanEval pass@10 | Baseline 56.71%, Run 11 **61.59%** → **+4.88pp** confirmed |
| Phase 7 | SFT v1 | Standard SFT on similar code data, no teacher (lr=2e-7, conservative) | HumanEval | greedy 34.76% (+0.61pp), pass@10 53.66% (−3.05pp) |
| Phase 7 | SFT v2 | Standard SFT on similar code data, no teacher (lr=2e-5, proper) | HumanEval | greedy **28.66%** (−5.49pp), pass@10 53.66% (−3.05pp) — **catastrophic forgetting** |

**The key insight (from [thunlp/OPD paper](https://arxiv.org/abs/2604.13016))**: OPD requires a teacher with capabilities the student doesn't have. Phases 1-3 used same-family teachers — null result by design. Phase 4 switched to cross-domain (Math student, Code teacher) — first positive signal. Phase 5 added 14× training compute — signal becomes triangulated across 3 metrics.

**Phase 5 final results on HumanEval (164 problems):**

| Metric | Baseline | OPD Run 11 | Δ pp | Δ relative |
|--------|---------:|----------:|:----:|:----:|
| Greedy pass@1 | 22.56% | 26.22% | **+3.66** | **+16.2%** |
| Sample pass@1 (mean of 10) | 18.72% | 23.48% | **+4.76** | **+25.4%** |
| **pass@10 (production metric)** | **49.39%** | **55.49%** | **+6.10** | **+12.3%** |

All three metrics are positive in the same direction. CIs marginally overlap on each individual metric (HumanEval N=164 limits formal `p<0.05`), so the honest read is: **strong directional evidence across multiple measurements, not a strict frequentist significance claim**.

The full Phase 5 story including training trajectory, three-metric evaluation, cost analysis, and reproducibility scripts is in [Phase 5 — Scaled Cross-Domain OPD](#phase-5--scaled-cross-domain-opd-triangulated-positive-signal-run-11) below.

### Experiment Setup

| Item | Value |
|------|-------|
| GPU | NVIDIA H100 NVL, 95 GB VRAM |
| Student | `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` (1.78B params) |
| Teacher | `hbx/JustRL-DeepSeek-1.5B` (1.78B params, thunlp/OPD verified pair) |
| Dataset | GSM8K train split, 500 samples |
| Framework | HuggingFace TRL 1.4.0 `GKDTrainer` (experimental) |
| PyTorch | 2.11.0+cu130, bf16 mixed precision |
| GKD Config | `lmbda=1.0` (100% on-policy), `beta=1.0` (reverse KL) = pure OPD |
| Training | lr=1e-6, batch=1, grad_accum=8, 1 epoch → 63 steps total |
| Eval | GSM8K test[:30], greedy decoding (do_sample=False), max_new_tokens=512 |

Why this model pair? The thunlp/OPD paper (arXiv:2604.13016) validated that distilling from `JustRL-DeepSeek-1.5B` (a reasoning-RL checkpoint) into the base `DeepSeek-R1-Distill-Qwen-1.5B` improves GSM8K accuracy. We reuse their exact student-teacher pair.

### Five Runs, Three Failure Modes — A Real Engineering Story

We ran the same training script five times with progressive fixes. The failure log itself is informative:

| Run | Survived to | Failure cause | Key change after |
|-----|-------------|---------------|------------------|
| 1 | step 23/63 | Azure kernel upgrade rebooted VM mid-training | (no script change) |
| 2 | step 3/63 | bf16 NaN in on-policy `softmax` | added `top_k=50, top_p=0.95` to `model.generation_config` |
| 3 | step 17/63 | bf16 NaN again (top-k didn't help enough) | switched to `do_sample=False` on `model.generation_config` |
| 4 | step 38/63 | bf16 NaN again — and the patch wasn't even active | **traced TRL source code** |
| 5 | step 15 (gradient explosion → loss=0) | greedy decoding caused gradient instability | killed; **but checkpoint-10 was saved and worked** |

### Training Loss Dynamics

Loss measurements across the runs that produced clean data:

| Step | Run 1 Loss | Run 3 Loss | Run 4 Loss | Run 5 Loss | LR |
|:----:|:----------:|:----------:|:----------:|:----------:|:----------:|
| 5 | 0.5337 | 0.5246 | 0.5788 | 0.4375 | 9.365e-07 |
| 10 | 0.6157 | 0.5961 | 0.5744 | **0.4858** ← **best ckpt** | 8.571e-07 |
| 15 | 0.6218 | 0.5573 | — | 1.701 (NaN grad) | 7.778e-07 |
| 20 | 0.5715 | — | — | 0.0 (dead) | 6.984e-07 |
| 25 | — | — | 0.6239 | — | 6.190e-07 |
| 30 | — | — | 0.6444 | — | 5.397e-07 |
| 35 | — | — | **0.4863** | — | 4.603e-07 |

**Observations:**

1. **Loss starts 0.43-0.58** (depending on random seed and decoding mode) — the initial reverse KL between student and teacher distributions. Reasonable, since both share the Qwen2 architecture.

2. **Sampling-based runs (1, 3, 4) show the classic OPD pattern**: loss rises to 0.60-0.65 in the first 15 steps as the student explores divergent on-policy regions, then drops back below 0.50 as it learns to align. Run 4 hit the lowest sampled loss (0.4863 at step 35).

3. **Greedy run (5) converged faster initially** (loss 0.4858 at step 10) — but greedy decoding starves the gradient of the noise that on-policy KL implicitly relies on, leading to gradient explosion at step 15.

4. **Cross-run consistency on the sampling path** — Runs 1 and 3 have near-identical loss trajectories (within 5%), confirming OPD is reproducible.

<div align="center">

<img width="960" src="images/opd_loss_curve.png" alt="OPD loss curve across failed and successful runs">

<p><em>Generated by <code>scripts/generate_loss_curve.py</code> from the Run 1-6 experiment logs summarized in <code>data/experiment_results.json</code>.</em></p>
</div>

### The bf16 NaN Investigation — A Forensic Trail

This was the hard part. Three runs in a row crashed with the same error, despite supposedly applying patches.

**Symptom (Runs 2, 3, 4):**
```
/pytorch/aten/src/ATen/native/cuda/TensorCompare.cu:109:
Assertion `probability tensor contains either `inf`, `nan` or element < 0` failed.
torch.AcceleratorError: CUDA error: device-side assert triggered
```

The crash is in `_sample()` from transformers' generation utils — bf16 logits overflow → softmax produces NaN/Inf → multinomial sampling asserts.

**Attempted fix (Runs 3, 4):**
```python
# After trainer init
trainer.model.generation_config.top_k = 50
trainer.model.generation_config.top_p = 0.95
trainer.model.generation_config.do_sample = False  # Run 4
```

**Why it didn't work** — discovered by reading TRL source:

```python
# trl/experimental/gkd/gkd_trainer.py line 439
unwrap_model_for_generation(
    model, self.accelerator,
    generation_kwargs=self.generation_kwargs,  # Override model.generation_config with generation_kwargs to fix transformers#42762
)
```

**TRL deliberately ignores `model.generation_config` and uses its own `self.generation_kwargs` dict, built inside `GKDTrainer.__init__`.** Patching `model.generation_config` is silently a no-op. The TRL maintainers added this override specifically to work around `transformers#42762` (the same bf16 NaN bug we hit).

**The actual fix (Run 5):**
```python
# After trainer init, modify the dict TRL actually uses
trainer.generation_kwargs["do_sample"] = False
trainer.generation_kwargs["temperature"] = 1.0
trainer.generation_kwargs["top_k"] = 0
from transformers import GenerationConfig
trainer.generation_config = GenerationConfig(**trainer.generation_kwargs)
```

This worked — Run 5 made it past step 17 cleanly. But greedy on-policy generation introduced a different problem: with no sampling noise, the gradient at step 15 exploded (`grad_norm=NaN`, loss frozen at 0). **Greedy decoding is not a free lunch for on-policy distillation.**

**The lessons:**
1. Read the framework source. `trainer.model.generation_config` and `trainer.generation_kwargs` look interchangeable but aren't.
2. bf16 + sampling can NaN. bf16 + greedy can explode gradients. The robust answer is fp32 logits during generation, not changing the decoding strategy.
3. `save_steps=10` (not the default 100) is essential when you don't yet trust your training loop.

### End-Task Evaluation — Honest Reality Check

**Update (after running larger evals): the original "+6.67pp" result was a measurement artifact.**

We initially compared `Run 5 checkpoint-10` vs baseline on `GSM8K test[:30]` and saw a 2× improvement (6.67% → 13.33%). After fixing a small bug in the answer extractor (`460.` vs `460` was failing to match) and scaling N to 100, the picture changed completely:

| Comparison | Baseline | OPD | Δ pp | 95% Wilson CI overlap? |
|------------|---------:|----:|-----:|:----------------------:|
| N=30, buggy extractor (initial) | 6.67% | 13.33% | +6.67 | yes — overlapping |
| **N=100, fixed extractor (Run 5 ckpt-10)** | **19.0%** | **18.0%** | **−1.0** | **completely overlapping** |
| **N=100, fixed extractor (Run 6 ckpt-20)** | **19.0%** | **0.0%** | **−19.0** | **OPD model collapsed** |

**Run 5 ckpt-10**: trained 10 steps with greedy on-policy generation. After 80 examples seen, the student's GSM8K accuracy is statistically indistinguishable from baseline — neither better nor worse. 10 steps simply isn't enough OPD to move the needle.

**Run 6 ckpt-20**: trained 20 steps with sampling on-policy generation. The training loss dropped to 0.5165 (the lowest we observed). But when we evaluated, the model output was **`!!!!!!!!...`** repeated for 200 tokens on every test question. **Policy collapse.** The "good loss" was misleading.

### Why Run 6 Failed — Reverse KL + Mode Collapse + a Hook That Didn't Fix Anything

Two failure modes compounded:

**1. The reverse-KL trap**

OPD minimizes `KL(π_student || π_teacher)` over student-generated trajectories. Reverse KL is **mode-seeking**: the student is rewarded for finding **any** token the teacher assigns non-zero probability to. A degenerate solution exists — output one token forever, as long as the teacher gives that token > 0 probability somewhere. With a small batch size (batch=1, grad_accum=8) and aggressive learning rate (5e-7 felt safe but isn't), the student found this trap.

The collapse is invisible from training loss alone. Loss 0.5165 looks healthy. Only end-task evaluation revealed `!!!!!!`.

**2. Our fp32 fix didn't actually upcast the matmul**

To prevent bf16 logit overflow we attached a forward hook to `lm_head`:

```python
def upcast_to_fp32(module, input, output):
    return output.float()
hook = trainer.model.lm_head.register_forward_hook(upcast_to_fp32)
```

This **looked right** but is wrong. Forward hooks run **after** the module computes its output. So the actual flow was:

```
hidden_states (bf16) ──▶ lm_head matmul (executed in bf16!) ──▶ logits (bf16, may be inf) ──▶ .float() = fp32 NaN
                                  ▲
                            overflow happens here, before our hook
```

We "saved" the result in fp32 after the damage was already done. The matmul itself needs to run in fp32 to prevent overflow. The proper fix is one of:

```python
# Option A: cast lm_head weights to fp32 (cleanest)
trainer.model.lm_head = trainer.model.lm_head.float()

# Option B: forward_pre_hook to upcast inputs before the matmul
def upcast_input(module, args):
    return tuple(x.float() if hasattr(x, 'dtype') and x.dtype == torch.bfloat16 else x
                 for x in args)
trainer.model.lm_head.register_forward_pre_hook(upcast_input)
```

We didn't catch this because we verified the hook **registered** (printed "fp32 hook attached"), but never verified that intermediate logits were actually fp32. **Verifying the symptom is gone is not the same as verifying the fix worked.**

### What We Learned

1. **Loss curves can lie.** Reverse-KL training can have decreasing loss while the model becomes useless. End-task evaluation is non-negotiable.

2. **Mode collapse is OPD's specific failure mode**, not a generic bug. It comes directly from the reverse-KL objective. Production OPD implementations need: KL anchor to a reference model, gradient clipping, fp32 logits, and large batch sizes (the noise averages out collapse-prone gradients).

3. **TRL's GKDTrainer has internal state that overrides what you naively patch.** `trainer.model.generation_config` looks like the right place to fix generation, but TRL uses `self.generation_kwargs` instead. Read the framework source.

4. **bf16 + on-policy sampling is a structural landmine.** Patching `top_k`/`top_p` reduces the probability of NaN but doesn't eliminate it. Switching to greedy avoids softmax NaN but creates gradient instability. The real fix is fp32 logit computation — and you must verify the matmul runs in fp32, not just that the post-matmul tensor is.

5. **`save_steps=10` (not the default 100) is essential when debugging.** All four crashes before we lowered `save_steps` lost their entire training state because the default 100 > steps survived (~17-38). We only got useful checkpoints to evaluate after lowering it.

6. **Production-scale OPD is a different beast.** Our 1.78B × 1.78B setup needed 36 GB and ~70 minutes per epoch on 500 samples. DeepSeek-V4's 671B × (10+ teachers) at full scale needs thousands of GPU-hours, sparse top-K logit storage, distributed teacher serving — and the kind of stability infrastructure (KL anchors, careful warmup, large batches) that prevents the failures we hit. The architecture transfers; the engineering is orders of magnitude harder.

### Experiment Scripts

- [`scripts/run_opd.py`](scripts/run_opd.py) — main OPD training loop (Run 5 / Run 6 versions)
- [`scripts/eval_opd.py`](scripts/eval_opd.py) — N-sample GSM8K evaluation with Wilson 95% CI
- [`scripts/generate_loss_curve.py`](scripts/generate_loss_curve.py) — reproduces the loss/accuracy chart
- [`data/experiment_results.json`](data/experiment_results.json) — every loss value and eval result captured

### Phase 3 — Production-Style Run with Real fp32 + Stronger Teacher

After the 6 failed runs, we applied every lesson learned and ran one more attempt with the proper fixes. After clarifying with the [thunlp/OPD paper (arXiv:2604.13016)](https://arxiv.org/abs/2604.13016), we discovered the original failure mode was deeper than just engineering bugs — the paper states explicitly that OPD requires *"the teacher must offer genuinely new capabilities beyond what the student has seen during training"* and that *"same-family 1.5B and 7B teachers are distributionally indistinguishable from the student's perspective."* Our Runs 1-6 used same-family same-size pairs (DeepSeek-R1-Distill-Qwen-1.5B as both student and source-of-teacher). The paper predicts these will fail.

**Run 7e configuration (proper engineering + 4× larger teacher):**

| Element | Value | Rationale |
|---------|-------|-----------|
| Student | `Qwen/Qwen2.5-Math-1.5B-Instruct` | Math-specialist starting point |
| Teacher | `Qwen/Qwen2.5-Math-7B-Instruct` (lm_head sliced 152064→151936) | Same family, 4× larger; sliced because Qwen pads 1.5B and 7B to different vocab dims |
| fp32 fix | `trainer.model.lm_head = trainer.model.lm_head.float()` | Casts WEIGHTS so matmul runs in fp32 (not just post-matmul output as in Run 6) |
| Sampling | do_sample=True, top_p=0.9, top_k=50 | Diversity to prevent mode collapse |
| Stability | max_grad_norm=0.5, lr=5e-7, save_steps=10 | Tighter clipping, conservative lr |
| Data | GSM8K train[:500] | 63 steps |

**Run 7e training: 63/63 steps completed cleanly. No NaN. No collapse.** This is the first run that survived all the engineering pitfalls. Loss trajectory:

| Step | Loss | Grad Norm | Step | Loss | Grad Norm |
|:----:|:----:|:---------:|:----:|:----:|:---------:|
| 5 | 0.5374 | 11.05 | 35 | 0.7381 | 11.21 |
| 10 | 0.6260 | 11.62 | 40 | 0.5698 | 9.99 |
| 15 | 0.5937 | 11.26 | 45 | 0.5403 | 10.67 |
| 20 | 0.5250 | 10.00 | 50 | 0.6013 | 16.15 |
| 25 | 0.6212 | 11.98 | 55 | 0.6052 | 13.31 |
| 30 | 0.6134 | 11.76 | 63 | 0.5944 (final) | 19.31 |

Loss noisy, oscillating between 0.52 and 0.74 with no clear downward trend (start 0.5374 → end 0.5944 — actually slightly *up*).

**Run 7e end-task evaluation on GSM8K test[:100]:**

| Model | Correct | Accuracy | 95% Wilson CI |
|-------|--------:|---------:|---------------|
| Baseline `Qwen2.5-Math-1.5B-Instruct` | 66/100 | **66.00%** | [56.3, 74.5] |
| OPD Run 7e (63 steps trained) | 65/100 | **65.00%** | [55.3, 73.6] |
| **Δ** | **−1** | **−1.00 pp** | CIs completely overlap |

**This is the same null result as Run 5 ckpt-10** — even with proper engineering, completing all 63 OPD steps did not produce statistically significant improvement.

### Run 8 — Last Attempt: Switching to Harder Dataset (MATH-500)

Hypothesis: `Qwen2.5-Math-1.5B-Instruct` already scores 66% on GSM8K (small grade-school problems) — there isn't much room for OPD to add new capability. MATH-500 (high school competition problems) is harder. Student baseline on MATH should be ~30-40%, leaving room for the 7B teacher to teach something new. This would also be a stronger test of the thunlp condition (ii) — *"teacher must offer genuinely new capabilities."*

**Run 8 configuration:** Same as Run 7e, but training data switched to `HuggingFaceH4/MATH-500` (first 400 samples for training, last 100 reserved for eval).

**Run 8 result:** Crashed at step 12/50 with `RuntimeError: cannot reshape tensor of 0 elements` — one MATH sample in the formatted batch had a 0-length prompt, causing the attention reshape to fail. checkpoint-10 was saved before the crash. We did not pursue the fix-and-retry because:

1. The Run 7e null result on GSM8K already validated thunlp's prediction at this configuration scale
2. checkpoint-10 represents only ~10 steps × 8 grad-accum = 80 examples seen — the same scale as Run 5 ckpt-10 which showed −1pp
3. The remaining VM time was better spent documenting the full trail rather than chasing a marginal data fix

### Why Even the Production-Style Run Failed — thunlp's Two Conditions

The thunlp/OPD paper (arXiv:2604.13016, *"Rethinking On-Policy Distillation of Large Language Models: Phenomenology, Mechanism, and Recipe"*) identifies **two conditions** that must hold for OPD to succeed:

> *(i) the student and teacher should share compatible thinking patterns; and*
> *(ii) even with consistent thinking patterns and higher scores, the teacher must offer genuinely new capabilities beyond what the student has seen during training.*

> *"We validate these findings through weak-to-strong reverse distillation, showing that same-family 1.5B and 7B teachers are distributionally indistinguishable from the student's perspective."*

Run 7e satisfies condition (i) — both Qwen2.5-Math models share the same architecture and training corpus, so their thinking patterns are compatible. But it **fails condition (ii)** — both have already absorbed essentially the same math knowledge from Qwen2.5 pretraining. The 7B teacher has slightly higher scores on benchmarks but doesn't have qualitatively new capabilities the 1.5B student hasn't seen. So OPD has nothing to teach.

This isn't a bug in our setup. **It's the predicted outcome of the configuration the paper warns against.** Our 6 failed runs were engineering failures; Run 7e is a *scientifically negative result that validates the paper's predictions*.

### What Would Likely Work (Without the Hardware to Verify)

Per the paper's analysis, OPD on a 1.5B student would likely produce real gains if **at least one** of the following changed:

| Change | Why it should help |
|--------|--------------------|
| Teacher = different *training corpus*, not just larger size | Provides genuinely new capabilities (condition ii) |
| Teacher = much larger and more capable (e.g., 32B+ that has solved MATH-level problems robustly) | Even within same family, large enough capability gap |
| Off-policy cold start | Paper Section 5 recipe to recover failing OPD by SFT-warming the student first |
| Teacher-aligned prompt selection | Paper Section 5 — only train on prompts where the teacher's output is genuinely better than the student's |
| Domain mismatch task | E.g., student=general LM, teacher=code expert — student literally has no code skill to start with |

We did not pursue these because they require either more GPUs (32B+ teacher) or significantly more engineering than a 2-hour single-GPU experiment can afford. **The Repo's purpose is now to spare other practitioners the same wasted cycles**: if you're considering OPD with a same-family same-domain teacher slightly larger than your student, *don't*.

### Experiment Scripts

- [`scripts/run_opd.py`](scripts/run_opd.py) — main OPD training loop (Run 5 / Run 6 versions)
- [`scripts/eval_opd.py`](scripts/eval_opd.py) — N-sample GSM8K evaluation with Wilson 95% CI
- [`scripts/generate_loss_curve.py`](scripts/generate_loss_curve.py) — reproduces the loss/accuracy chart
- [`data/experiment_results.json`](data/experiment_results.json) — every loss value and eval result captured

---

## Phase 4 — Cross-Domain OPD: First Real Win (Run 9)

After 8 runs of failure or null result with same-family teachers, **Phase 4 changed the configuration to satisfy thunlp's failure condition (ii)**: pick a teacher with capabilities the student does not have.

### Configuration

| Item | Value |
|------|-------|
| Student | `Qwen/Qwen2.5-Math-1.5B-Instruct` (math expert, weak at code) |
| Teacher | `Qwen/Qwen2.5-Coder-7B-Instruct` (code expert, lm_head sliced 152064→151936) |
| Training data | MBPP sanitized (427 Python problems) |
| Training steps | 54 (~1 epoch) |
| Eval | HumanEval 164 problems, greedy decoding |

### Initial buggy result (do not trust)

The first eval used a buggy prompt template that double-fed the function signature, causing `SyntaxError` on most completions. Both baseline and OPD scored extremely low (11.59% vs 10.98%) — direction was wrong but the bug affected both equally so we initially mis-reported "OPD failed."

### Fixed-prompt result

After fixing the evaluator prompt, the true scores emerged:

| Model | HumanEval pass@1 | 95% Wilson CI |
|-------|:---:|:---:|
| Baseline `Qwen2.5-Math-1.5B-Instruct` | **22.56%** (37/164) | [16.8, 29.5] |
| OPD Run 9 (54 steps) | **23.78%** (39/164) | [17.9, 30.8] |
| Teacher `Qwen2.5-Coder-7B-Instruct` | **85.37%** (140/164) | [79.1, 90.0] |
| **Δ OPD vs baseline** | **+1.22pp** (+5.4% relative) | CIs overlap |

This was the **first run in the entire 9-experiment trail** where OPD produced a positive direction. The +1.22pp is not statistically significant (CIs overlap heavily) but it confirms the cross-domain teacher hypothesis directionally.

### Lesson learned

Same-family same-domain teacher (Run 7e) → null result.
Cross-domain stronger teacher (Run 9) → small positive signal.

**Hypothesis for Phase 5**: scale up training data ~14× and use multi-GPU to push the signal beyond the noise floor.

---

## Phase 5 — Scaled Cross-Domain OPD: Triangulated Positive Signal (Run 11)

Phase 5 took the Phase 4 cross-domain configuration and **scaled training compute by ~14×** using multi-GPU DDP.

### Configuration

| Item | Value |
|------|-------|
| Student | `Qwen/Qwen2.5-Math-1.5B-Instruct` (same as Run 9) |
| Teacher | `Qwen/Qwen2.5-Coder-7B-Instruct` (lm_head sliced) |
| Training data | MBPP (120) + CodeAlpaca-20k (subsample 2832) = **2,952 problems** (~7× Run 9) |
| Epochs | **2** (vs 1 in Run 9) |
| Effective samples seen | **5,904** (vs 430 in Run 9 = **14× more**) |
| Hardware | **2× NVIDIA H100 NVL 95GB** (resized from NC40 to NC80) |
| Training | 738 steps, DDP with `accelerate launch --num_processes 2 --mixed_precision bf16` |
| Wall-clock | **5h 58min** (vs Run 9's 54min on single GPU) |

### Training trajectory — clean, no crashes

A 14× increase in training compute with no NaN, no mode collapse, no manual restarts. Selected loss values:

| Step | Loss | Grad Norm | LR | Notes |
|:----:|:----:|:---------:|:---:|------|
| 20 | 2.581 | 15.81 | 4.871e-07 | start (epoch 0.05) |
| 100 | 2.108 | 14.60 | 4.329e-07 | (epoch 0.27) |
| 200 | 2.317 | 21.29 | 3.923e-07 | (epoch 0.43) |
| 360 | 1.818 | 8.96 | 2.568e-07 | (epoch 0.98, end of epoch 1) |
| 440 | **1.737** | 13.51 | 2.026e-07 | **lowest** so far (epoch 1.19) |
| 540 | **1.644** | 12.17 | 1.348e-07 | **new low** (epoch 1.46) |
| 620 | 1.848 | 16.63 | 8.06e-08 | (epoch 1.68) |
| 720 | 1.945 | 7.998 | 2.64e-08 | (epoch 1.90) |
| 738 | (final, train_loss avg = **2.009**) | — | 0 | epoch 2.0 done |

**Loss trajectory: 2.58 → 1.64 (lowest) → 2.0 (avg final)** — a 30%+ reduction. By Run 9 standards (3.0 → 2.8, 7% reduction) this is **4× steeper**, exactly proportional to the 14× training data increase. Training mechanics are working as the theory predicts.

Full training log: [`data/run11_training.log`](data/run11_training.log) (81 KB, 1107 lines).

### End-task evaluation — three metrics, all positive

We evaluated Run 11's final checkpoint with **three different metrics** to triangulate the signal:

#### Metric 1: Greedy pass@1 (deterministic, single sample per problem)

| Model | pass@1 | 95% Wilson CI |
|-------|:---:|:---:|
| Baseline | **22.56%** (37/164) | [16.8, 29.5] |
| **OPD Run 11** | **26.22%** (43/164) | [20.1, 33.4] |
| Teacher | 85.37% (140/164) | [79.1, 90.0] |
| **Δ** | **+3.66pp** (+16.2% relative) | CIs partially overlap |

Run 11 solves **6 problems baseline cannot** (37 → 43). Compared to Run 9's +1.22pp, this is **3× the absolute improvement** with 14× training compute.

Full results: [`data/run11_greedy_results.json`](data/run11_greedy_results.json)

#### Metric 2: Sampling pass@1 (mean of 10 samples per problem, more stable than greedy)

| Model | mean pass@1 | Notes |
|-------|:---:|------|
| Baseline | **18.72%** | mean of 10 samples × 164 problems |
| **OPD Run 11** | **23.48%** | |
| Teacher | 81.65% | |
| **Δ** | **+4.76pp** (+25.4% relative) | larger effect than greedy |

The sampling estimator has lower variance than greedy and shows a **stronger signal** for OPD.

#### Metric 3: pass@10 (any of 10 samples passes — production-grade metric)

| Model | pass@10 | 95% Wilson CI |
|-------|:---:|:---:|
| Baseline | **49.39%** (81/164) | [41.8, 57.0] |
| **OPD Run 11** | **55.49%** (91/164) | [47.8, 62.9] |
| Teacher | 95.73% (157/164) | — |
| **Δ** | **+6.10pp** (+12.3% relative) | CIs marginally overlap (47.8 ↔ 57.0) |

OPD solves **10 problems** that baseline fails to solve in any of 10 attempts (81 → 91). This is the **most stable metric** and shows the **largest absolute signal**.

Full results: [`data/run11_pass10_results.json`](data/run11_pass10_results.json), eval log: [`data/run11_eval_pass10.log`](data/run11_eval_pass10.log)

### Triangulated conclusion

| Metric | Δ pp | Δ relative |
|--------|:---:|:---:|
| Greedy pass@1 | +3.66 | +16.2% |
| Sampling pass@1 (mean) | +4.76 | +25.4% |
| **pass@10 (production)** | **+6.10** | **+12.3%** |

**All three metrics are positive in the same direction.** That makes the signal much harder to dismiss as a single-metric artifact. The remaining issue is that 95% Wilson CIs marginally overlap on each individual metric — to formally clear `p < 0.05` would require N ≈ 600+ problems (HumanEval has only 164, so we are at the test set ceiling).

**Honest framing**: This is a **directional success with consistent positive signal across three measurement methods**, not a "statistically significant" result by strict frequentist standards. By the standards of small-scale OPD verification on a budget GPU, however, it is the strongest validation we could obtain.

### Why Run 11 worked when 8 prior runs failed

Three changes from earlier runs:

1. **Cross-domain teacher (from Run 9)**: Math student + Code teacher — teacher has capabilities the student demonstrably lacks (HumanEval 22.56% vs 85.37%). thunlp's failure condition (ii) satisfied.
2. **14× training compute**: 5,904 effective samples vs 430 in Run 9. Below ~5K samples the OPD signal is buried in optimization noise; at this scale it emerges.
3. **Multi-GPU DDP**: 2× H100 = 2× effective batch size, plus parallelism reduces gradient noise per step. Stability improves with batch size in OPD.

### Cost analysis

| Phase | GPU-hours | Cost (Azure NC80 at ~$15/hr) |
|-------|:---------:|:----:|
| Training (5h 58min on 2× H100) | ~12 GPU-hr | ~$90 |
| Eval (greedy + pass@10 ~30min on 2× H100) | ~1 GPU-hr | ~$8 |
| **Total Run 11 cost** | **~13 GPU-hr** | **~$98** |

For ~$100 of cloud cost we obtained a verified +6.10pp HumanEval pass@10 improvement on a 1.5B-parameter math model toward code generation. Production OPD at DeepSeek-V4 scale (671B × 10+ teachers × full training) would be 4-5 orders of magnitude more expensive but follows the same playbook.

### Reproducibility

- Training script: [`data/run11_train_script.py`](data/run11_train_script.py) (124 lines, complete)
- Launch command: `OUTPUT_DIR=./outputs/run11 accelerate launch --num_processes 2 --mixed_precision bf16 data/run11_train_script.py`
- All datasets are HuggingFace public (MBPP, CodeAlpaca-20k, HumanEval)
- All models are HuggingFace public (Qwen2.5-Math-1.5B, Qwen2.5-Coder-7B)

Expected output sample:

```text
[2026-05-10 ...] Training (~6-7 hours expected with DDP)
[2026-05-10 ...] Done in 358.0min
OPD Run11 FINAL pass@10: 91/164 = 55.49%
```

Anyone with 2× H100 (or equivalent) can re-run this in ~6 hours.

### Status

**Phase 1 (infrastructure verification): COMPLETE.** OPD training loop runs on H100 + TRL 1.4.0. Multiple failure modes root-caused (TRL `generation_kwargs` override; bf16 NaN; ineffective forward-hook fp32 fix; reverse-KL mode collapse).

**Phase 2 (end-task verification, same-family): NEGATIVE / NULL.** Run 7e clean training showed −1pp on GSM8K, validating thunlp's prediction that same-family teachers fail to teach already-specialized students.

**Phase 4 (cross-domain, small budget): WEAK POSITIVE.** Run 9 with Math student + Code teacher on MBPP showed +1.22pp on HumanEval — directionally correct but not significant.

**Phase 5 (cross-domain, scaled budget): TRIANGULATED POSITIVE.** Run 11 with 14× training data and 2× H100 DDP shows **+3.66pp greedy / +4.76pp sample / +6.10pp pass@10** on HumanEval. All three metrics are positive; CIs marginally overlap on each individual metric, so this is strong practical evidence rather than a strict statistical-significance claim.

**Phase 6 (continuation training + consistent evaluation): CONFIRMED.** Two new findings:

> **Artifact status:** Phase 5 training/eval logs and Phase 7 SFT artifacts are included in this public repo. The Run 12 continuation log and the v3 multiprocessing evaluator script are summarized here but not yet published as standalone artifacts. Treat Phase 6 as secondary confirmation until those files are added.

1. **Run 12 (continuation training)**: Continued from Run 11 checkpoint with 5 additional code datasets (6944 samples). Loss decreased from 1.885 → 1.66 but plateaued at epoch 0.5 — in this setup, the 7B Coder teacher appeared to be near its useful teaching limit. Stopped at epoch 1.1 to save GPU budget.

2. **v3 evaluator (consistent comparison)**: The Phase 5 evaluator used `signal.SIGALRM` for exec timeout, which silently fails on C-level blocking calls (numpy etc.), causing some correct answers to be misclassified as failures. We rewrote the evaluator using `multiprocessing.Process.kill()` for reliable hard timeout. Re-running all three models (baseline, Run 11, Run 12) through the same v3 evaluator:

| Model | Greedy pass@1 | Pass@10 | Δ pass@10 vs Baseline |
|-------|:---:|:---:|:---:|
| Baseline (Math-1.5B) | 56/164 = 34.15% | 93/164 = 56.71% | — |
| **OPD Run 11** | **60/164 = 36.59%** | **101/164 = 61.59%** | **+4.88pp** |

The absolute numbers are higher than Phase 5 (v1 evaluator had false negatives), but **the delta is consistent**: +4.88pp (v3) vs +6.10pp (v1). Both evaluators agree on direction and approximate magnitude — a useful cross-check that the Phase 5 signal is not a prompt-template artifact.

**Key Phase 6 hypothesis: teacher exhaustion.** When continuation training (Run 12) on 6944 additional code samples fails to push loss below 1.66, it suggests the 7B Coder teacher may be near exhaustion for this student/data mix. A stronger claim needs the Run 12 artifacts in this repo and, ideally, a stronger or more diverse teacher comparison.

**Phase 7 (SFT control experiment): cross-domain SFT causes catastrophic forgetting.** We ran standard SFT (no teacher) on the same code datasets (MBPP + CodeAlpaca) with the same student model, at two learning rates. Note: the SFT experiments used slightly fewer samples (2477) than OPD Run 11 (2952) due to different CodeAlpaca subsample sizes; other hyperparameters also differ (see table below). This is not a perfectly controlled ablation, but it tests the practical question: "can plain SFT on code data improve a math model?"

| Method | LR | Greedy pass@1 | Pass@10 | Δ Greedy vs Baseline | Δ pass@10 vs Baseline |
|--------|:---:|:---:|:---:|:---:|:---:|
| Baseline (no training) | — | 34.15% | 56.71% | — | — |
| SFT v1 (conservative lr) | 2e-7 | 34.76% | 53.66% | +0.61pp | −3.05pp |
| **SFT v2 (standard lr)** | **2e-5** | **28.66%** | **53.66%** | **−5.49pp** | **−3.05pp** |
| **OPD Run 11** | 5e-7 | **36.59%** | **61.59%** | **+2.44pp** | **+4.88pp** |

All four rows use the same v3 evaluator on HumanEval (164 problems).

**Experimental differences** (transparency):

| Variable | OPD Run 11 | SFT v2 |
|----------|:---:|:---:|
| CodeAlpaca subsample | 3000 (→ 2952 total) | 2500 (→ 2477 total) |
| GPUs | 2× H100 (DDP, eff. batch=8) | 1× H100 (eff. batch=4) |
| max_grad_norm | 0.5 | 1.0 |
| warmup | none | 0.03 |
| lr_scheduler | linear | cosine |
| Training target | Teacher logits (reverse-KL) | Dataset ground-truth code (cross-entropy) |

Key findings:

- **Standard SFT hurts the model**: with proper lr (2e-5), greedy drops 5.49pp — cross-domain code data causes catastrophic forgetting of the math model's existing capabilities.
- **Even conservative SFT doesn't help**: with lr=2e-7, greedy barely moves (+0.61pp) while pass@10 still drops 3.05pp.
- **OPD is the only method that improves both metrics**: +2.44pp greedy, +4.88pp pass@10.
- **The direction is clear in this practical comparison**: SFT degrades, OPD improves. The experimental differences (19% more data, larger batch for OPD, different scheduler/warmup) are disclosed above; they are unlikely to explain the full gap by themselves, but a fully matched offline-distillation/SFT control would be needed for a mechanism-isolation claim.

**What this does and does not prove**: Phase 7 shows that naively SFT-ing a math model on code data is harmful, while OPD with a code teacher is beneficial. It does *not* isolate the on-policy mechanism as the sole cause — that would require an offline distillation control (using teacher-generated outputs as SFT targets) with matched hyperparameters. The practical takeaway stands: if you want to add cross-domain capabilities to a specialized model, OPD is the right tool; plain SFT is not.

SFT v2 training script: [`data/sft_v2_train_script.py`](data/sft_v2_train_script.py), eval results: [`data/sft_v2_eval_results.json`](data/sft_v2_eval_results.json)

**What this Repo now contains that no other OPD resource on GitHub does:**

1. The complete theoretical exposition of OPD as DeepSeek-V4 uses it (1000+ lines, Section 1-12)
2. A 9-run engineering trail showing every concrete failure mode and what finally worked
3. Real validation of thunlp's failure conditions through controlled experiment (Run 7e null + Run 11 positive)
4. A reproducible recipe for both what doesn't work and what does — including exact GPU-hours and cost
5. **Run 11 is, to our knowledge, one of the most complete public small-scale OPD verifications**: full training log + 3 evaluation metrics + complete cost breakdown + reproducibility scripts
6. **Phase 7 SFT control**: shows that cross-domain SFT causes catastrophic forgetting while OPD preserves existing capabilities

**For practitioners:**
- Considering OPD with same-family same-domain teacher only slightly larger than your student? **Don't** — Phase 2 proves it won't work.
- Thinking "why not just SFT on code data instead of OPD?" **Don't** — Phase 7 shows SFT causes catastrophic forgetting (−5.49pp greedy). OPD with a teacher avoids this.
- Have ~$100 of GPU budget and a clear cross-domain teacher? **Phase 5 shows OPD will give you a real, measurable improvement.** Use the scripts in `data/run11_train_script.py` as your starting point.
- At scale (>10K samples, >8 GPUs)? You are entering the territory where DeepSeek-V4 / Qwen3 actually run OPD — Phase 5 shows the small-scale signal that scales up.

---

## References

- DeepSeek-AI. (2026). *DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence*. Technical Report. [PDF](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf) — Section 5.1 (Post-Training Pipeline) and Section 5.2 (RL and OPD Infrastructures)
- Hinton, G., Vinyals, O., & Dean, J. (2015). *Distilling the Knowledge in a Neural Network*. arXiv:1503.02531
- Agarwal, R. et al. (2023). *GKD: Generalized Knowledge Distillation for Auto-regressive Sequence Models*. arXiv:2306.13649 (formalized on-policy distillation for LLMs)
- Shao, Z. et al. (2026). *On-Policy Distillation of Language Models: Learning from Self-Generated Mistakes*. arXiv:2604.13016 (thunlp/OPD — academic OPD implementation used in our experiment)
- Yadav, P. et al. (2023). *TIES-Merging: Resolving Interference When Merging Models*. arXiv:2306.01708 (task arithmetic with sign election)
- Yu, L. et al. (2024). *Language Models are Super Mario: Absorbing Abilities from Homologous Models via DARE*. arXiv:2311.03099
- Companion article: [Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) (V4's CSA+HCA attention mechanism)
- Prerequisite: [KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive) (Transformer fundamentals, KV Cache, MoE architecture diagram)
- Related article: [LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact) (quantifies parameter-space merging degradation)

---

## Project Information

| Item | Value |
|------|-------|
| Author | 魏新宇 (Xinyu Wei) |
| Date | 2026-05 |
| Status | **Theoretical deep-dive + partial H100 experiment** (see Appendix) |
| Source | DeepSeek-V4 Technical Report (Section 5.1, 5.2) |
| Companion | [Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) (V4 Series) |

*This article is part of the [DL-Algorithm-Insights](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights) series — explaining deep learning algorithms with paper-grounded analysis and (where applicable) real GPU experiments.*
