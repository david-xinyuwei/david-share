# NVIDIA Groq LPU — Architecture Deep Dive: From TSP to Vera Rubin Platform

> **⛔ Last Updated: 2026-03-30 12:00**
> **Project Category**: AI Infrastructure — Chip Architecture Analysis
> **Author**: Xinyu Wei

---

## Executive Summary

| Dimension | Detail |
|-----------|--------|
| **What** | NVIDIA Groq 3 LPU (Language Processing Unit) — an ASIC inference accelerator acquired by NVIDIA for ~$20B in 2025 |
| **Core Innovation** | Tensor Streaming Processor (TSP): functional slicing + deterministic execution + on-chip SRAM as primary weight storage |
| **Key Specs (single chip)** | 500 MB SRAM, 150 TB/s bandwidth, 1.2 PFLOPS (FP8), 98B transistors |
| **Key Specs (LPX rack)** | 256 LPUs, 128 GB SRAM, 315 PFLOPS, 640 TB/s scale-up bandwidth |
| **Positioning** | Decode accelerator paired with Vera Rubin NVL72 GPU rack for disaggregated serving |
| **Performance** | GPU + LPU = 35× throughput for trillion-parameter models (vs Blackwell alone) |
| **How it works** | Compiler pre-computes entire execution graph down to individual clock cycles; SRAM stores weights statically; zero dynamic scheduling at runtime |
| **Trade-offs** | No training capability; limited SRAM capacity; model changes require recompilation; no CUDA ecosystem |

---

## 1. Background: Why NVIDIA Bought Groq

### 1.1 The Inference Bottleneck

LLM inference has two distinct phases with different computational characteristics:

| Phase | What Happens | Bottleneck | GPU Utilization |
|-------|-------------|-----------|:---------------:|
| **Prefill** | Process entire input prompt in parallel | Compute-bound (high FLOPS needed) | High |
| **Decode** | Generate tokens one-by-one, each requiring full weight read | **Memory bandwidth-bound** | Low |

During decode, GPU's massive compute (50 PFLOPS) sits idle while waiting for weights to be read from HBM (22 TB/s). This is the fundamental inefficiency that LPU addresses.

### 1.2 Groq's Solution

Groq, founded in 2016 by former Google TPU engineers, built a chip from scratch optimized for the decode bottleneck:
- **Replace HBM with on-chip SRAM**: 150 TB/s bandwidth (7× GPU's HBM)
- **Replace dynamic scheduling with static scheduling**: Compiler determines everything at compile-time
- **Replace multi-core hub-and-spoke with assembly-line**: Data flows through functional slices like a production line

### 1.3 Acquisition and Integration

- **Acquired**: 2025, ~$20B by NVIDIA
- **GTC 2026 Announcement**: Groq 3 LPU integrated into Vera Rubin platform as one of seven new chips
- **Product**: NVIDIA Groq 3 LPX rack (256 LPUs per rack)
- **Next Generation**: LP40 (Feynman architecture, announced at GTC 2026)

---

## 2. TSP Architecture Deep Dive

### 2.1 Functional Slicing — The Core Innovation

Traditional chips (CPU/GPU) package all functions into each core: instruction control, memory, integer ALU, floating-point ALU, and networking. Multiple identical cores connect via a 2D mesh.

TSP (Tensor Streaming Processor) does the opposite — **slices by function, not by core**:

| Slice | Full Name | Function |
|-------|-----------|----------|
| **ICU** | Instruction Control Unit | Instruction decode and dispatch (shared, <3% chip area) |
| **MEM** | Memory Slice | SRAM read/write, data routing |
| **VXM** | Vector Execution Module | Vector operations (ReLU, LayerNorm, etc.) |
| **MXM** | Matrix Execution Module | Matrix multiplication (the main compute) |
| **SXM** | Switch Execution Module | Inter-chip networking and data routing |

```
Traditional (GPU): Each core has everything → cores fight for shared resources

  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
  │Core 0│ │Core 1│ │Core 2│ │Core 3│  ← each has ALU+cache+control
  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
     └────────┴────────┴────────┘
              Shared Bus / Crossbar         ← contention!

TSP (LPU): Functions separated into slices → data flows through like assembly line

  Instructions flow ↓ (Y-axis)
  ┌─────┬─────┬─────┬─────┬─────┐
  │ ICU │ ICU │ ICU │ ICU │ ICU │  ← instruction control (one copy)
  ├─────┼─────┼─────┼─────┼─────┤
  │ MEM │ MEM │ MEM │ MEM │ MEM │  ← memory (read weights)
  ├─────┼─────┼─────┼─────┼─────┤
  │ VXM │ VXM │ VXM │ VXM │ VXM │  ← vector compute
  ├─────┼─────┼─────┼─────┼─────┤
  │ MXM │ MXM │ MXM │ MXM │ MXM │  ← matrix compute
  ├─────┼─────┼─────┼─────┼─────┤
  │ SXM │ SXM │ SXM │ SXM │ SXM │  ← networking
  └─────┴─────┴─────┴─────┴─────┘
  Data flows → (X-axis)
```

### 2.2 Why This Design Works

| Advantage | Explanation |
|-----------|-------------|
| **ICU shared once** | All tiles of the same function execute the same instruction → decode logic needed only once (<3% area) |
| **Natural pipeline** | Instructions flow vertically, data flows horizontally → instruction and data paths decouple completely |
| **No resource contention** | Each functional slice has dedicated resources → no fighting for shared buses or caches |
| **Memory-compute colocation** | MEM slices feed data directly to VXM/MXM slices → no register file intermediary |

> **Source**: Groq 2020 ISCA paper (TSP); EETOP WeChat article "深度拆解Groq LPU架构" (2026-03-30)

### 2.3 Hardware Details (First Generation → Groq 3)

| Spec | Gen 1 (2020 ISCA) | Groq 3 (2026 GTC) |
|------|:-:|:-:|
| SRAM | 220 MB | **500 MB** |
| Process | 14nm | Not disclosed (likely 4nm) |
| Clock | 900 MHz | Not disclosed |
| Transistors | Not disclosed | **98B** |
| SRAM Bandwidth | 80 TB/s (per Groq official 2025) | **150 TB/s** |
| Compute (FP8) | Not disclosed | **1.2 PFLOPS** |
| Parallel Lanes | 320 (20 tiles × 16 lanes) | Not disclosed |
| Logical Streams | 64 (32 east + 32 west) | Not disclosed |
| Interconnect | Custom C2C | **Custom Chip-to-Chip** |
| HBM | None | **⚠️ Unconfirmed** (see note below) |

> **⚠️ Important Note on HBM4**: The Post Keynote Deck (Page 11) chip comparison photo shows 288 GB HBM4 on the **left side (GPU)**, not the right side (LPU). The LPU side shows only 500 MB SRAM. **Whether Groq 3 LPU has HBM4 is NOT confirmed** — the 288 GB HBM4 specification belongs to the Vera Rubin GPU. Groq's official architecture page (groq.com/lpu-architecture) describes only on-chip SRAM, consistent with the original SRAM-only design philosophy.

> **Source**: Post Keynote GTC 2026 Customer Deck Page 11; Groq official (groq.com/lpu-architecture; groq.com/blog/inside-the-lpu-deconstructing-groq-speed)

---

## 3. How Data is Handled: Weights, Activations, KV Cache

### 3.1 Weights — SRAM as Primary Weight Storage

Groq official statement (☠2 level source):
> **"The LPU integrates hundreds of MB of SRAM as primary weight storage (not cache)"**
> — groq.com/lpu-architecture

How weights are distributed across 256 LPUs:

```
Model: 70B parameters (FP8) = ~70 GB total weights

Step 1 — Compile: Groq compiler slices each weight matrix (illustrative example)
  ⚠️ Note: Exact slicing mechanism not publicly disclosed. Below is a conceptual illustration.
  W (4096 × 4096) → split across 256 LPUs (analogous to tensor parallelism)
  LPU 0:   a slice of W → stored at predetermined SRAM address
  LPU 1:   a different slice of W → stored at predetermined SRAM address
  ...
  LPU 255: the last slice of W → stored at predetermined SRAM address

Step 2 — Load: At service startup, weights loaded into each LPU's SRAM

Step 3 — Run: Each LPU computes its slice, results combined via 640 TB/s interconnect
```

### 3.2 Activations — Static Shape, Dynamic Values

Groq official statement:
> **"FP8 storage for activations in error-tolerant layers"**
> — groq.com/blog/inside-the-lpu-deconstructing-groq-speed

Key insight: Activation **values** are dynamic (different every inference), but activation **shapes** are static (determined by model architecture). The compiler pre-allocates fixed SRAM regions for activations.

### 3.3 KV Cache — Officially Undisclosed

**⚠️ Groq has not publicly disclosed how KV Cache is managed on the LPU.**

Three official sources searched (groq.com/lpu-architecture, inside-the-lpu blog, from-speed-to-scale blog) — none mention KV Cache management mechanisms.

In the NVIDIA Vera Rubin platform context, KV Cache management involves:
- **NVIDIA Dynamo KVBM**: Offloads KV cache across GPU → CPU → SSD → remote storage
- **BlueField-4 STX**: Dedicated KV cache storage rack with DOCA Memos framework
- **NIXL**: Low-latency data transfer protocol between GPU and LPU

> **Source**: Dynamo GitHub README (github.com/ai-dynamo/dynamo); Post Keynote Deck Page 42; NVIDIA Vera Rubin press release

---

## 4. Deterministic Execution — The "No Cache, No Arbitration" Philosophy

### 4.1 What Gets Compiled Down to Clock Cycles

The Groq compiler pre-computes the **entire execution graph** including:

| What is determined at compile-time | GPU equivalent (runtime) |
|-----------------------------------|-------------------------|
| Which SRAM address to read from | Runtime: cache hit or miss? Unknown |
| Which SRAM address to write to | Runtime: memory controller decides |
| Which data stream to use (east #5, west #3) | Runtime: router arbitration |
| Which clock cycle each operation executes | Runtime: thread scheduler assigns |
| Which functional slice does the computation | Runtime: SM availability check |
| When inter-chip communication happens | Runtime: collective operation sync |
| How long the entire inference takes | Runtime: varies every time |

Groq official statement:
> **"Our compiler pre-computes the entire execution graph, including inter-chip communication patterns, down to the individual clock cycles."**
> — groq.com/blog/inside-the-lpu-deconstructing-groq-speed

### 4.2 What Was Removed from Hardware

From the original TSP paper:
> **"We eliminated all reactive hardware, such as arbiters and caches."**

| Removed | Why it existed | Why LPU doesn't need it |
|---------|---------------|------------------------|
| **Cache** | Handles unpredictable data access patterns | All accesses are statically scheduled → no unpredictability |
| **Arbiters** | Resolves resource contention between cores | Functional slicing → no shared resources → no contention |
| **Reorder buffers** | Handles out-of-order execution | Static scheduling → always in-order |
| **Speculative execution** | Guesses branch outcomes | No branches in linear algebra → no speculation needed |
| **Dynamic thread scheduler** | Assigns work to available cores | Compiler assigns work at compile-time |

### 4.3 Comparison: Four Levels of Inference Optimization

```
Layer (top = shallow, bottom = deep):

Application    │  Python code (model.generate())
               │
───────────    │  ① torch.compile ← Optimizes here (Python → static graph)
               │     ~1.5× speedup, near-zero cost
CPU Dispatch   │  CPU sends kernels to GPU one by one
               │
───────────    │  ② CUDA Graph ← Optimizes here (record & replay, skip CPU)
               │     ~1.2× speedup, requires fixed input shapes
GPU Compute    │  GPU runs kernels (MatMul/Attention/LayerNorm)
               │
───────────    │  ③ TensorRT ← Optimizes here (operator fusion + quantization)
               │     ~2-3× speedup, slow compilation, less flexibility
HW Execution   │  Memory access, cache behavior, thread scheduling, bus arbitration
               │
───────────    │  ④ Groq Compiler ← Optimizes here (everything static, zero dynamic)
               │     ~4-7× speedup, requires dedicated LPU hardware
Physical       │  Transistors, electrical signals
```

---

## 5. Vera Rubin Platform Integration: GPU + LPU Jointly Computing

### 5.1 Official Architecture Statement

From NVIDIA official press release (☠1 level — highest authority):
> **"Deployed with Vera Rubin NVL72, Rubin GPUs and LPUs boost decode by jointly computing every layer of the AI model for every output token."**
> — nvidianews.nvidia.com/news/nvidia-vera-rubin-platform

Key phrase: **"jointly computing every layer"** — GPU and LPU are NOT simply splitting prefill/decode. They jointly compute during decode phase.

### 5.2 System Architecture

```
Vera Rubin SuperPOD:

  ┌───────────────────────────────────┐
  │ Vera Rubin NVL72 Rack             │  72 Rubin GPUs + 36 Vera CPUs
  │  • 288 GB HBM4 per GPU            │  NVLink 6 (3600 GB/s)
  │  • 3.6 EFLOPS (NVFP4)             │  Prefill + Joint Decode
  │  • NVLink 6 interconnect           │
  └─────────────┬─────────────────────┘
                │ Activations + KV Cache (via NIXL)
                │
  ┌─────────────┴─────────────────────┐
  │ NVIDIA Groq 3 LPX Rack            │  256 LPUs
  │  • 128 GB SRAM (total)             │  Custom C2C (640 TB/s)
  │  • 315 PFLOPS (FP8)               │  Joint Decode
  │  • 150 TB/s SRAM bandwidth        │
  └─────────────┬─────────────────────┘
                │
  ┌─────────────┴─────────────────────┐
  │ BlueField-4 STX Storage Rack      │  KV Cache storage tier
  │  • DOCA Memos framework            │  5× inference throughput boost
  │  • POD-wide context memory         │
  └───────────────────────────────────┘

  Orchestrator: NVIDIA Dynamo 1.0
    • KV-aware routing
    • KV Block Manager (GPU → CPU → SSD → remote)
    • ModelExpress (weight streaming via NIXL)
    • SLA-based Planner (auto-scaling prefill/decode pools)
    • Grove (K8s topology-aware gang scheduling)
```

### 5.3 LPX Rack Specifications

| Spec | Value | Source |
|------|-------|--------|
| LPUs per rack | 256 | Post Keynote Deck Page 12 |
| AI Inference Compute | 315 PFLOPS | Post Keynote Deck Page 12 |
| SRAM Capacity | 128 GB | Post Keynote Deck Page 12 |
| Memory Bandwidth | 40 PB/s | Post Keynote Deck Page 12 |
| Scale-Up Density | 256 Chips | Post Keynote Deck Page 12 |
| Scale-Up Bandwidth | 640 TB/s | Post Keynote Deck Page 12 |
| Scale-Out Density | 1000+ LPUs | Post Keynote Deck Page 12 |
| Per-node (compute tray) | 8× LPU, 1.2 PB/s SRAM BW | Post Keynote Deck Page 12 |
| Security | BlueField-4 AI Runtime | Post Keynote Deck Page 12 |
| Cooling | 100% Liquid-Cooled | Post Keynote Deck Page 12 |

### 5.4 Combined Performance

| Metric | Blackwell NVL72 alone | VR NVL72 + LPX | Improvement |
|--------|:----:|:----:|:----:|
| Throughput (trillion-param) | Baseline | **35×** | Post Keynote Deck Page 13 |
| Revenue $/sec/MW | $1 (Blackwell), $4 (Rubin) | **$10** | Post Keynote Deck Page 13 |
| TPS/User (1T param, 400K context) | ~30 | **1000+** | Post Keynote Deck Page 13 |
| $/Mtok | $150 (Blackwell), $45 (Rubin) | **$3** | Post Keynote Deck Page 13 |

> **Source**: Post Keynote GTC 2026 Customer Deck Pages 11-14, 42-43

---

## 6. TruePoint Numerics — Precision Without Quality Loss

Groq's proprietary numeric format:

| Feature | Detail |
|---------|--------|
| Intermediate accumulation | **100 bits** — sufficient for lossless accumulation regardless of input bit width |
| Weight storage | Lower precision (FP8, Block Floating Point) |
| Attention logits | **FP32** — where 1-bit errors propagate |
| MoE expert weights | Block Floating Point — robustness studies show no degradation |
| Activations | FP8 in error-tolerant layers |
| Result | 2-4× speedup over BF16 with no accuracy loss on MMLU/HumanEval |

> **Source**: groq.com/blog/inside-the-lpu-deconstructing-groq-speed

---

## 7. Trade-offs and Limitations

| Limitation | Detail | Mitigation |
|-----------|--------|------------|
| **No training** | LPU is inference-only ASIC | Use GPU for training |
| **Small SRAM** | 500 MB per chip, 128 GB per rack | Scale-out to 1000+ LPUs; MoE sparse activation |
| **Model change = recompile** | Static scheduling means new model needs full recompilation | Groq compiler optimized for fast compilation |
| **No CUDA** | Custom compiler, not PyTorch-native | Higher barrier to adoption |
| **SRAM cost** | Estimated ~$100/GB vs HBM ~$15/GB vs GDDR ~$3/GB (industry estimates, not officially confirmed) | Trade-off: bandwidth for capacity |
| **SRAM area** | Estimated ~400 mm²/GB (6 transistors/bit vs 1 for DRAM, industry rule of thumb) | Chip size constrained by lithography limits |
| **KV Cache management** | Officially undisclosed mechanism | NVIDIA mitigates with BlueField-4 STX + Dynamo KVBM |
| **Low utilization at short context** | Pre-allocated max context wastes SRAM when context is short | Multi-level KV offloading |

---

## 8. NVIDIA GPU Roadmap — LPU Evolution

| Generation | GPU | LPU | CPU | Networking | Timeline |
|-----------|-----|-----|-----|-----------|---------|
| Blackwell | Blackwell / Blackwell Ultra (HBM3e) | — | Grace | NVLink 5 (1800 GB/s) | 2024-2026 |
| **Vera Rubin** | **Rubin (HBM4)** | **Groq 3** | **Vera (88 Olympus)** | **NVLink 6 (3600 GB/s)** | **2026-2028** |
| Feynman | Feynman (Die Stacking + Custom HBM) | **LP40** | Rosa | NVLink 8 CPO | 2028+ |

> **Source**: Post Keynote GTC 2026 Customer Deck Page 29; GTC Blog keynote coverage ("LP40, NVIDIA's next-generation LPU")

---

## 9. Key Quotes — Primary Sources

| Quote | Source | Authority |
|-------|--------|:---------:|
| "Rubin GPUs and LPUs boost decode by jointly computing every layer of the AI model for every output token." | nvidianews.nvidia.com | ☠1 |
| "The LPU integrates hundreds of MB of SRAM as primary weight storage (not cache)" | groq.com/lpu-architecture | ☠2 |
| "Our compiler pre-computes the entire execution graph, including inter-chip communication patterns, down to the individual clock cycles." | groq.com/blog/inside-the-lpu | ☠2 |
| "We eliminated all reactive hardware, such as arbiters and caches." | Groq 2020 ISCA paper | ☠2 |
| "A fleet of LPUs function as a giant single processor for fast, deterministic inference acceleration." | nvidianews.nvidia.com | ☠1 |
| "At scale...128GB of on-chip SRAM and 640 TB/s of scale-up bandwidth." | nvidianews.nvidia.com | ☠1 |
| "FP8 storage for activations in error-tolerant layers" | groq.com/blog/inside-the-lpu | ☠2 |
| "Individual Groq LPU chips are designed to interconnect and create one shared resource fabric for models to run on" | groq.com/blog/from-speed-to-scale | ☠2 |

---

## 10. Terminology Quick Reference

| Term | Full Name | What It Is |
|------|-----------|-----------|
| **LPU** | Language Processing Unit | Single ASIC inference chip (500 MB SRAM, 1.2 PFLOPS) |
| **LPX** | (Full name not publicly disclosed) | Rack system: 256 LPUs (128 GB SRAM, 315 PFLOPS) |
| **TSP** | Tensor Streaming Processor | Groq's chip architecture (functional slicing + deterministic execution) |
| **ICU** | Instruction Control Unit | Shared instruction decode (<3% chip area) |
| **MEM** | Memory Slice | SRAM read/write and data routing |
| **VXM** | Vector Execution Module | Vector operations (ReLU, LayerNorm) |
| **MXM** | Matrix Execution Module | Matrix multiplication |
| **SXM** | Switch Execution Module | Inter-chip networking |
| **TruePoint** | TruePoint Numerics | 100-bit intermediate accumulation for lossless precision |
| **RealScale** | RealScale Interconnect | Plesiosynchronous chip-to-chip protocol |
| **NIXL** | NVIDIA Inference Xfer Library | Low-latency data transfer between GPU and LPU |
| **KVBM** | KV Block Manager | Multi-tier KV cache offloading (Dynamo) |
| **STX** | Storage (BlueField-4) | Dedicated KV cache storage rack |
| **NVL72** | NVLink 72 | 72-GPU rack with NVLink 6 interconnect |
| **Dynamo** | NVIDIA Dynamo 1.0 | Open-source datacenter-scale inference orchestrator |

---

## Source Materials

| # | Source | Type | Authority |
|---|--------|------|:---------:|
| 1 | Post Keynote GTC 2026 Customer Deck — Accelerated Computing (44 pages) | PDF | ☠2 |
| 2 | nvidianews.nvidia.com/news/nvidia-vera-rubin-platform | Press Release | ☠1 |
| 3 | blogs.nvidia.com/blog/gtc-2026-news (Keynote live blog) | Blog | ☠2 |
| 4 | groq.com/lpu-architecture | Official Product Page | ☠2 |
| 5 | groq.com/blog/inside-the-lpu-deconstructing-groq-speed | Technical Blog | ☠2 |
| 6 | groq.com/blog/from-speed-to-scale-how-groq-is-optimized-for-moe-other-large-models | Technical Blog | ☠2 |
| 7 | groq.com/blog/the-groq-lpu-explained (LPU 4 Design Principles) | Technical Blog | ☠2 |
| 8 | Groq TSP ISCA 2020 Paper | Academic Paper | ☠2 |
| 9 | EETOP WeChat: "深度拆解Groq LPU架构" (2026-03-30) | Analysis Article | ☠4 |
| 10 | github.com/ai-dynamo/dynamo (NVIDIA Dynamo 1.0) | Open Source Repo | ☠2 |

---
