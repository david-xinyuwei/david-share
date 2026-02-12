# LLM Training Parallelism Explained: DP, TP, PP, and ZeRO

> **A comprehensive visual guide to distributed parallelism strategies for Large Language Model training and inference.**

This guide provides clear, diagram-driven explanations of the four major parallelism strategies used in LLM training and inference. It answers one of the most frequently confused questions: *What exactly do TP, PP, and ZeRO each split, and how are they different?*

## Table of Contents

- [The Big Picture](#the-big-picture)
- [Data Parallelism (DP)](#data-parallelism-dp)
- [Tensor Parallelism (TP)](#tensor-parallelism-tp)
- [Pipeline Parallelism (PP)](#pipeline-parallelism-pp)
- [ZeRO (Zero Redundancy Optimizer)](#zero-zero-redundancy-optimizer)
  - [ZeRO Stage 1: Optimizer State Partitioning](#zero-stage-1-optimizer-state-partitioning)
  - [ZeRO Stage 2: + Gradient Partitioning](#zero-stage-2--gradient-partitioning)
  - [ZeRO Stage 3: + Parameter Partitioning](#zero-stage-3--parameter-partitioning)
- [The Critical Difference: TP vs ZeRO](#the-critical-difference-tp-vs-zero)
- [3D Parallelism: TP × PP × DP](#3d-parallelism-tp--pp--dp)
- [Communication Patterns Comparison](#communication-patterns-comparison)
- [Training vs Inference: Different Priorities](#training-vs-inference-different-priorities)
- [Decision Guide: When to Use What](#decision-guide-when-to-use-what)
- [Real-World Example: Training Llama-3 405B](#real-world-example-training-llama-3-405b)
- [References](#references)

---

## The Big Picture

All parallelism strategies solve the same fundamental problem: **a single GPU doesn't have enough memory or compute power to handle a large model**. But they approach it from different angles:

![Parallelism Overview](images/parallelism_overview.png)

| Strategy | What It Splits | Each GPU Processes | Communication |
|----------|---------------|-------------------|---------------|
| **DP** (Data Parallelism) | **Data batches** | Different data, full model | AllReduce gradients |
| **TP** (Tensor Parallelism) | **Weight matrices** within each layer | Same data, partial weights | AllReduce per layer |
| **PP** (Pipeline Parallelism) | **Layer groups** across stages | Same data, full layers (subset) | P2P activations at boundaries |
| **ZeRO** | **Model states** (W/G/OS) for storage | Different data, reconstructed full weights | AllGather before compute |

**Key Insight**: TP and PP split **how the model computes** (model parallelism). ZeRO splits **how the model is stored** (memory optimization on top of data parallelism).

---

## Data Parallelism (DP)

**Core Idea**: Replicate the entire model on every GPU. Each GPU processes a different slice of the training data.

### How It Works

```
Global Batch = [B0, B1, B2, B3]   (e.g., 1024 samples)

GPU 0: Full Model Copy → processes B0 (256 samples) → local gradients G0
GPU 1: Full Model Copy → processes B1 (256 samples) → local gradients G1
GPU 2: Full Model Copy → processes B2 (256 samples) → local gradients G2
GPU 3: Full Model Copy → processes B3 (256 samples) → local gradients G3

                    ↓ AllReduce ↓
           G_avg = (G0 + G1 + G2 + G3) / 4
                    ↓
           All GPUs update parameters with G_avg
```

### Communication Pattern

- **When**: Once after backward pass (per training step)
- **What**: AllReduce on gradients
- **Volume**: 2M per step (M = model size, ring AllReduce)
- **Bandwidth need**: Medium

### Pros and Cons

| Pros | Cons |
|------|------|
| Simple to implement | Each GPU must hold full model copy |
| No model modification needed | Memory inefficient (N copies of model) |
| Linear speedup with more GPUs | Limited by single-GPU memory |
| Works well with any model | Gradient sync can be bottleneck |

### Variants

- **DP** (PyTorch DataParallel): Uses python threads, GPU0 as master → load imbalance
- **DDP** (DistributedDataParallel): Multi-process, each GPU independent → preferred
- **FSDP** (Fully Sharded Data Parallel): PyTorch's ZeRO implementation

---

## Tensor Parallelism (TP)

**Core Idea**: Split each layer's weight matrix across GPUs. Each GPU computes a **partial result** and they synchronize to get the full output.

### How It Works — MLP Layer Example

For a linear layer `Y = XW + b` with weight matrix `W ∈ R^{d_in × d_out}`:

```
Column-parallel split (TP=2):

W = [W_left | W_right]     (split along output dimension)

GPU 0: Y_left  = X × W_left     → partial output
GPU 1: Y_right = X × W_right    → partial output

         ↓ AllReduce ↓
    Y_full = concat or reduce(Y_left, Y_right)
```

For multi-head attention, it's even more natural since heads are already independent:

```
Attention with 32 heads, TP=2:

GPU 0: Heads 0-15  → partial attention output
GPU 1: Heads 16-31 → partial attention output

         ↓ AllReduce ↓
       Full attention output
```

### Communication Pattern

- **When**: Every layer (both forward and backward)
- **What**: AllReduce on activations (per-layer intermediate results)
- **Volume**: Very high (communication at every layer)
- **Bandwidth need**: Very high → **requires NVLink** (300-900 GB/s)

### Why TP Needs NVLink

A typical Transformer layer requires **2 AllReduce operations** (one for MLP, one for attention). For a 94-layer model, that's **188 AllReduce operations per forward pass**, and the same for backward. If using Ethernet (~25 Gbps), the communication overhead would dominate compute time.

**Rule of thumb**: TP should only be used **within a single node** connected by NVLink.

### Pros and Cons

| Pros | Cons |
|------|------|
| Reduces per-GPU memory proportionally | Requires very high bandwidth (NVLink) |
| Each GPU computes partial work → faster | Communication at every layer |
| Natural fit for attention heads | Must modify model architecture |
| Reduces activation memory | TP degree limited by number of attention heads |

---

## Pipeline Parallelism (PP)

**Core Idea**: Assign different **groups of complete layers** to different GPUs. Data flows through the pipeline from first stage to last stage.

### How It Works

```
94-layer model with PP=2:

GPU 0 (Stage 0): Layer 0 ~ Layer 46    ← complete weights for these layers
GPU 1 (Stage 1): Layer 47 ~ Layer 93   ← complete weights for these layers

Forward: Input → GPU0 computes layers 0-46 → send activations → GPU1 computes layers 47-93 → Output
Backward: Same path in reverse, send gradients of activations
```

### The Pipeline Bubble Problem

With naive PP, only one GPU is active at a time (huge waste):

```
Naive PP (no micro-batching):

GPU0: [F0 ][    idle    ][B0 ]
GPU1: [idle][F1 ][B1 ][idle]
              ↑ bubble ↑
```

**Micro-batching** (GPipe/1F1B schedule) alleviates this by splitting the batch into smaller chunks:

```
1F1B Schedule (4 micro-batches):

GPU0: [F0][F1][F2][F3][B0][B1][B2][B3]
GPU1:     [F0][F1][F2][F3][B0][B1][B2][B3]
              ↑ smaller bubble ↑
```

### Communication Pattern

- **When**: Only at stage boundaries (between layer groups)
- **What**: Point-to-point (P2P) send/recv of activations
- **Volume**: Low (only activations at boundary layers)
- **Bandwidth need**: Low → **Ethernet is sufficient**

### Pros and Cons

| Pros | Cons |
|------|------|
| Low communication overhead | Pipeline bubble (idle time) |
| Works over low-bandwidth links (Ethernet) | Increased latency for single requests |
| Each GPU holds complete layers | Load balancing across stages |
| No model architecture changes | Micro-batching adds complexity |

### PP for Training vs Inference

| Aspect | Training | Inference |
|--------|----------|-----------|
| **Micro-batch benefit** | Fills bubble (independent samples) | Only helps throughput (tokens are sequential) |
| **Bubble impact** | Reduced by 1F1B schedule | Unavoidable for single-request latency |
| **When to use** | When nodes can't hold full model | When single GPU can't hold model |

---

## ZeRO (Zero Redundancy Optimizer)

**Core Idea**: In standard DP, every GPU redundantly stores a full copy of model parameters (W), gradients (G), and optimizer states (OS). ZeRO **partitions** these across GPUs to save memory, while **reconstructing** them on-the-fly when needed for computation.

> **ZeRO is NOT model parallelism. It's memory-optimized data parallelism.** Each GPU still processes different data batches and computes with full model weights — it just doesn't *store* everything all the time.

![ZeRO Stages](images/zero_stages.png)

### Memory Breakdown (FP16 model with Adam optimizer)

For a model with M parameters:

| Component | Per-Parameter Memory | Total for M params |
|-----------|---------------------|-------------------|
| Parameters (W) in FP16 | 2 bytes | 2M |
| Gradients (G) in FP16 | 2 bytes | 2M |
| Adam Optimizer States | 12 bytes (FP32 W copy + momentum + variance) | 12M |
| **Total** | **16 bytes** | **16M** |

With standard DP on N GPUs: **each GPU stores 16M** → total memory = 16M × N (massive waste!)

### ZeRO Stage 1: Optimizer State Partitioning

**What's partitioned**: Only optimizer states (OS)

```
4 GPUs, Model M:

GPU 0: W (full 2M) + G (full 2M) + OS_0 (3M)     = 7M bytes
GPU 1: W (full 2M) + G (full 2M) + OS_1 (3M)     = 7M bytes
GPU 2: W (full 2M) + G (full 2M) + OS_2 (3M)     = 7M bytes
GPU 3: W (full 2M) + G (full 2M) + OS_3 (3M)     = 7M bytes

vs. Standard DP: 16M per GPU → Stage 1 saves ~56% memory
```

**Communication**: Same as DDP (AllReduce gradients) + AllGather for updated parameters

### ZeRO Stage 2: + Gradient Partitioning

**What's partitioned**: Optimizer states + Gradients

```
4 GPUs, Model M:

GPU 0: W (full 2M) + G_0 (0.5M) + OS_0 (3M)      = 5.5M bytes
GPU 1: W (full 2M) + G_1 (0.5M) + OS_1 (3M)      = 5.5M bytes

vs. Standard DP: 16M per GPU → Stage 2 saves ~66% memory
```

**Communication**: Replaces AllReduce with Reduce-Scatter (each GPU gets its gradient shard)

### ZeRO Stage 3: + Parameter Partitioning

**What's partitioned**: Optimizer states + Gradients + Parameters (everything!)

```
4 GPUs, Model M:

GPU 0: W_0 (0.5M) + G_0 (0.5M) + OS_0 (3M)       = 4M bytes
GPU 1: W_1 (0.5M) + G_1 (0.5M) + OS_1 (3M)       = 4M bytes

vs. Standard DP: 16M per GPU → Stage 3 saves ~75% memory
```

**Communication**: All-Gather (collect full W before each layer's forward/backward) + Reduce-Scatter (distribute gradients)

**How ZeRO-3 handles forward pass**:
```
For each layer L:
  1. All-Gather: Reconstruct full W of layer L from all GPU shards
  2. Compute: Y = f(X, W_full)     ← same math as single GPU!
  3. Discard: Drop the gathered W (only keep own shard)
  4. Move to next layer
```

---

## The Critical Difference: TP vs ZeRO

This is the most commonly confused point. Both TP and ZeRO-3 split weights across GPUs. But the computation model is fundamentally different:

![TP vs ZeRO](images/tp_vs_zero.png)

| Aspect | Tensor Parallelism (TP) | ZeRO Stage 3 |
|--------|------------------------|---------------|
| **Splits** | Weight matrix within each layer | Weight shards for storage |
| **During compute** | Each GPU uses **partial weights** | Each GPU reconstructs and uses **full weights** |
| **Data processed** | **Same data** across TP group | **Different data** per GPU (data parallelism) |
| **Communication type** | AllReduce (per layer, merge partial results) | All-Gather (per layer, reconstruct weights) |
| **Model modification** | Required (split Linear, Attention) | Not required |
| **Nature** | **Model parallelism** | **Memory-optimized data parallelism** |
| **Analogy** | Workers each build **part** of a car, then assemble | Workers each **borrow the full toolkit**, build their own car, return tools |

### Why This Matters

1. **TP reduces compute per GPU** (each does partial matrix multiply) → good for latency
2. **ZeRO doesn't reduce compute** (each does full matrix multiply) → same latency as single GPU
3. **TP requires high bandwidth** (sync at every layer) → needs NVLink
4. **ZeRO's All-Gather can be prefetched** (overlap with compute) → more flexible

---

## 3D Parallelism: TP × PP × DP

For training the largest models (100B+), a single parallelism strategy isn't enough. **3D Parallelism** combines all three:

![3D Parallelism](images/3d_parallelism.png)

### How They Combine

```
Total GPUs = TP_size × PP_size × DP_size

Example: 8 GPUs, TP=2, PP=2, DP=2

                    DP Rank 0                    DP Rank 1
              ┌────────────────────┐      ┌────────────────────┐
PP Stage 0    │ GPU0(TP0) GPU1(TP1)│      │ GPU4(TP0) GPU5(TP1)│
(Layer 0-46)  │  ←── NVLink ──→   │      │  ←── NVLink ──→   │
              ├────────────────────┤      ├────────────────────┤
PP Stage 1    │ GPU2(TP0) GPU3(TP1)│      │ GPU6(TP0) GPU7(TP1)│
(Layer 47-93) │  ←── NVLink ──→   │      │  ←── NVLink ──→   │
              └────────────────────┘      └────────────────────┘
                         ↕ AllReduce gradients (DP) ↕
```

### Communication Hierarchies

| Dimension | Bandwidth Need | Typical Interconnect | Communication |
|-----------|---------------|---------------------|---------------|
| **TP** (within node) | Highest | NVLink (600-900 GB/s) | AllReduce every layer |
| **PP** (across nodes) | Low | Ethernet (10-100 Gbps) | P2P at stage boundaries |
| **DP** (across replicas) | Medium | Ethernet/InfiniBand | AllReduce gradients once per step |

### ZeRO + 3D Parallelism

When combining ZeRO with PP+TP:
- **ZeRO-1** (optimizer sharding) works well with PP+TP
- **ZeRO-2** (+ gradient sharding) has performance issues with PP due to extra Reduce-Scatter per micro-batch
- **ZeRO-3** (+ parameter sharding) typically not combined with PP/TP (redundant and adds communication)

---

## Communication Patterns Comparison

| Parallelism | Collective Op | When | Volume per Step | Can Overlap with Compute? |
|-------------|--------------|------|-----------------|--------------------------|
| **DP/DDP** | AllReduce | After backward | 2M (ring) | Yes (gradient bucketing) |
| **TP** | AllReduce | Every layer (fwd+bwd) | 2 × L × activation_size | No (on critical path) |
| **PP** | P2P Send/Recv | Stage boundaries | activation_size_per_boundary | Partially (1F1B) |
| **ZeRO-1** | AllGather + ReduceScatter | Optimizer step | M | Yes |
| **ZeRO-2** | ReduceScatter | After backward | M | Yes |
| **ZeRO-3** | AllGather + ReduceScatter | Every layer (fwd+bwd) | 3M total (fwd AG + bwd AG + bwd RS) | Yes (prefetch) |

Where: M = model size, L = number of layers.

---

## Training vs Inference: Different Priorities

| Aspect | Training | Inference |
|--------|----------|-----------|
| **Primary goal** | Maximize throughput (samples/sec) | Minimize latency (ms/token) |
| **Parallelism priority** | DP > TP > PP | TP > PP > DP |
| **Why DP is preferred in training** | Lowest communication, linear scaling | Not applicable (single input) |
| **Why TP is preferred in inference** | — | Reduces per-GPU compute, lowers latency |
| **ZeRO relevance** | Very useful (saves memory for larger batches) | ZeRO-Inference exists but less common |
| **PP trade-off** | Acceptable bubble, micro-batch helps | Adds latency (pipeline bubble per token) |

### Why Training Prefers DP

- Each GPU processes independent data → minimal communication (just gradients at end)
- Communication a can overlap with backward computation (gradient bucketing)
- Linear throughput scaling: 2× GPUs ≈ 2× throughput

### Why Inference Prefers TP

- Single request → can't split data (no DP benefit)
- TP reduces per-GPU computation → lower latency
- NVLink bandwidth handles per-layer AllReduce efficiently

---

## Decision Guide: When to Use What

### Model fits on single GPU
```
→ Just use DDP (Data Parallel) for training
→ Single GPU for inference
```

### Model doesn't fit on single GPU

**Single node (NVLink available)**:
```
→ Training: TP first, add ZeRO-1/2 if needed
→ Inference: TP (degree = number of GPUs)
```

**Multi-node (Ethernet between nodes)**:
```
→ Training: TP within node + PP across nodes + DP for scaling
→ Inference: TP within node + PP across nodes
```

**Memory still insufficient**:
```
→ Add ZeRO-3 (caution: high communication for Stage 3)
→ Consider ZeRO-Offload (offload to CPU/NVMe)
```

### Quick Decision Table

| Scenario | Recommended Strategy |
|----------|---------------------|
| 7B model, 1 node 8×H100 | DDP (training) / TP=1 (inference) |
| 70B model, 1 node 8×H100 | TP=8 (inference) / TP=8 + ZeRO-1 (training) |
| 70B model, 2 nodes 4×H100 | TP=4 + PP=2 |
| 405B model, 8 nodes 8×H100 | TP=8 + PP=4 + DP=2 |
| 405B model, 192 nodes 8×H100 | TP=8 + PP=4 + DP=48 (Llama-3 actual config) |

---

## Real-World Example: Training Llama-3 405B

Meta's Llama-3 405B was trained on **16,384 H100 GPUs** using 3D parallelism:

| Dimension | Value | Details |
|-----------|-------|---------|
| **TP** | 8 | Within each node (8×H100 NVSwitch, 900 GB/s) |
| **PP** | 4 (16 for context extension) | Across 4 nodes per pipeline |
| **DP** | 512 (128 for context extension) | 16384 / (8 × 4) = 512 DP replicas |

### Per-GPU View

```
Total parameters: 405B
Per TP group (8 GPUs): 405B (shared, each holds 1/8 of each layer's weights)
Per PP stage (TP group handles some layers):
  - Pipeline has 4 stages → each stage ≈ 126B / 4 = ~31.5B parameters
  - With TP=8: each GPU holds ~31.5B / 8 = ~3.9B parameters
  - In FP16: ~3.9B × 2 bytes = ~7.8 GB for weights alone

Memory breakdown per GPU:
  Parameters (FP16):     ~7.8 GB
  Gradients (FP16):      ~7.8 GB
  Optimizer (FP32):      ~23.4 GB (Adam: 3× param FP32)
  Activations & KV:      ~30-40 GB
  ──────────────────────────────
  Total:                 ~70-80 GB / 80 GB H100
```

## Related Resources

Other repositories in this series cover specific aspects in greater depth:

| Repository | Focus |
|-----------|-------|
| [Deep-Speed-ZeRO-Policy](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Deep-Speed-ZeRO-Policy) | ZeRO stages deep dive with DeepSpeed |
| [NVIDIA-GPU-Distributed-Training](https://github.com/xinyuwei-david/david-share/tree/master/GPUs/NVIDIA-GPU-Distributed-Training) | NCCL communication internals (Ring, Tree, CollNet) |
| [Memory-consumption-in-Training-and-Inference](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference) | GPU memory breakdown for training and inference |
| [How-to-Run-Training-Faster](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/How-to-Run-Training-Faster) | Training speed optimization techniques |
| [Megatron+Deepspeed-Pretrain-GPT2](https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Megatron+Deepspeed-Pretrain-GPT2) | Hands-on 3D parallelism with Megatron-DeepSpeed |

## References

- [ZeRO: Memory Optimizations Toward Training Trillion Parameter Models](https://arxiv.org/abs/1910.02054) (Rajbhandari et al., 2019)
- [Megatron-LM: Training Multi-Billion Parameter Language Models Using Model Parallelism](https://arxiv.org/abs/1909.08053) (Shoeybi et al., 2019)
- [GPipe: Efficient Training of Giant Neural Networks using Pipeline Parallelism](https://arxiv.org/abs/1811.06965) (Huang et al., 2018)
- [Efficient Large-Scale Language Model Training on GPU Clusters Using Megatron-LM](https://arxiv.org/abs/2104.04473) (Narayanan et al., 2021)
- [DeepSpeed ZeRO++: A leap in speed for LLM and chat model training](https://www.microsoft.com/en-us/research/blog/deepspeed-zero-a-leap-in-speed-for-llm-and-chat-model-training-with-4x-less-communication/) (Microsoft Research, 2023)
- [HuggingFace: Efficient Training on Multiple GPUs](https://huggingface.co/docs/transformers/perf_train_gpu_many)
- [The Llama 3 Herd of Models](https://arxiv.org/abs/2407.21783) (Meta, 2024)
