# Multi-Expert On-Policy Distillation: How DeepSeek-V4 Merges 10+ Domain Experts into One Model

*Author: Xinyu Wei (魏新宇)*

> A deep dive into On-Policy Distillation (OPD) — the post-training method DeepSeek-V4 uses to consolidate 10+ domain-specialist models into a single unified model, replacing the traditional mixed-RL stage entirely.

[中文版](README-CN.md) | [Companion: Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) | [Related: LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)

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
  <img src="images/opd_vs_offline.png" width="720" alt="Offline vs On-Policy Distillation comparison">
  <p><em>Offline distillation: student fits to teacher's trajectories. OPD: student fits to teacher's scoring of student's own trajectories.</em></p>
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

## The Math: Why Reverse KL?

The OPD objective from the V4 paper (Equation 29):

$$L_{OPD}(\theta) = \sum_{i=1}^{N} w_i \cdot D_{KL}(\pi_\theta \,\|\, \pi_{E_i})$$

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

### 2. The expectation is over student trajectories

The KL is computed at every token in a student-sampled trajectory. This is the "on-policy" part:

$$D_{KL}(\pi_\theta \,\|\, \pi_{E_i}) = \mathbb{E}_{y \sim \pi_\theta}\left[\sum_{t} \sum_v \pi_\theta(v|y_{<t}) \log \frac{\pi_\theta(v|y_{<t})}{\pi_{E_i}(v|y_{<t})}\right]$$

If we sampled from the teacher instead, this would degenerate into offline distillation.

### 3. The weights `w_i` route by domain implicitly

The paper explains:
> *"the unified policy π_θ selectively learns from the specialized expert relevant to the current task context (e.g., aligning with the mathematics expert for math reasoning tasks and the coding expert for programming tasks)."*

This works because each teacher's distribution is sharp on its own domain and flat on others. When the trajectory is a math problem, only the math expert produces low-loss gradients; other teachers contribute roughly uniform-distribution noise that cancels out.

So even though all teachers are summed, each task naturally aligns with its corresponding expert. This is much simpler than explicit task routing.

---

## Multi-Expert OPD at Scale

<div align="center">
  <img src="images/multi_teacher_opd.png" width="600" alt="Multi-Expert OPD Pipeline">
  <p><em>Multi-Expert OPD: student samples → all teachers score → weighted KL gradient updates student.</em></p>
</div>

DeepSeek-V4 distills from **10+ teachers** simultaneously. The naive implementation has two showstopper problems:

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

Problems:
- Reward functions don't compose. A math reward might prefer 500-token solutions; a chat reward might prefer 80-token responses. Optimizing both simultaneously produces incoherent length policies.
- The model has no way to know which domain it's serving, so it learns averaged behavior rather than domain-conditional behavior.
- Reward hacking is amplified — exploitable rewards in one domain pollute the gradient for all others.

OPD doesn't have this problem because:
- Each teacher's distribution is implicitly domain-specialized (the teacher itself was trained per-domain)
- The KL signal is dense (every token, every vocab position) vs. sparse RL reward (one scalar per trajectory)
- No reward function design needed — the teacher distribution IS the implicit reward

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

## Implementing OPD: Skeleton Code

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

## OPD vs MoE: Two Different "Experts"

V4 is **both a MoE architecture and a recipient of OPD post-training**. These are completely separate concepts that happen to share the word "expert" — a frequent source of confusion. Disambiguating:

| Concept | What it is | Lifetime | Quantity in V4-Pro |
|---------|------------|----------|:------------------:|
| **MoE expert** (architectural) | A single FFN sub-network within one Transformer block, selected by a router per-token | **Permanent** — part of the model architecture | ~256 fine-grained experts × ~60 layers = ~15K experts total |
| **OPD "specialist expert"** (training-only) | A complete standalone model trained on one domain (math, code, writing, etc.) via full-parameter RL | **Training-only** — disappears after OPD distillation | 10+ during training, 0 after |

Visualizing the architectural MoE inside V4's Transformer — to make clear where the fine-grained FFN experts live relative to Attention, KV Cache, and other components — see the full MoE Transformer pipeline diagram in [KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive#moe-variant-when-step-5-becomes-a-mixture-of-experts). Key takeaway: each MoE "expert" is a small FFN (e.g., 4096→1408→4096), selected per-token by a router. An OPD specialist is an entire multi-hundred-billion-parameter model. They are fundamentally different things.

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

## Where OPD Fits in the V4 Series

DeepSeek-V4 is a coordinated set of innovations. OPD plays a specific role:

| Innovation | Purpose | Covered In |
|-----------|---------|------------|
| Long-context efficient attention (CSA + HCA) | Make 1M-token context computationally feasible | [Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) |
| Manifold-Constrained Hyper-Connections (mHC) | Strengthen residual connections in deep models | V4 Tech Report Section 2.2 |
| Muon Optimizer | Faster convergence and training stability | V4 Tech Report Section 2.4 |
| FP4 Quantization-Aware Training | Reduce memory traffic for both training and inference | V4 Tech Report Section 3.4 |
| **On-Policy Distillation (this article)** | **Merge 10+ specialists into a single production model** | V4 Tech Report Section 5.1 |
| Quick Instruction (auxiliary tasks via KV cache reuse) | Reduce TTFT for chatbot scenarios | V4 Tech Report Section 5.1.1 |

OPD is the **post-training capstone** — the method that takes all the domain experts trained on the new architecture and consolidates them into the final shipped model.

---

## What This Repo Doesn't Have (Yet)

This is a **theoretical deep-dive** based on the DeepSeek-V4 Technical Report. We have not yet:

- Reproduced OPD experiments on real hardware
- Compared OPD vs Weight Merging vs Task Arithmetic with controlled benchmarks
- Verified the claimed quality preservation at small scale

These are planned for a follow-up phase. When the experimental data is in, this README will be updated with:

- H100 benchmark setup (Qwen 2.5 family teachers + Qwen3 student, single GPU)
- GSM8K / HumanEval / MMLU evaluation comparing OPD vs baselines
- Training stability curves and hyperparameter ablations

---

## References

- DeepSeek-AI. (2026). *DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence*. Technical Report. [PDF](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf) — Section 5.1 (Post-Training Pipeline) and Section 5.2 (RL and OPD Infrastructures)
- Hinton, G., Vinyals, O., & Dean, J. (2015). *Distilling the Knowledge in a Neural Network*. arXiv:1503.02531
- Agarwal, R. et al. (2023). *GKD: Generalized Knowledge Distillation for Auto-regressive Sequence Models*. arXiv:2306.13649 (formalized on-policy distillation for LLMs)
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
| Status | **Theoretical deep-dive** — experiments planned for follow-up |
| Source | DeepSeek-V4 Technical Report (Section 5.1, 5.2) |
| Companion | [Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) (V4 Series) |

*This article is part of the [DL-Algorithm-Insights](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights) series — explaining deep learning algorithms with paper-grounded analysis and (where applicable) real GPU experiments.*
