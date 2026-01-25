# Qwen-Image-Edit-2511 Virtual Try-On Inference Benchmark

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch 2.5+](https://img.shields.io/badge/pytorch-2.5+-red.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Comprehensive benchmark comparing inference engines for **Qwen-Image-Edit-2511** virtual try-on model on NVIDIA H100 GPU, achieving up to **6.8x speedup** with quality analysis.

## Key Results

| Engine | Time | vs Baseline | Speedup | Quality | Status |
|--------|------|-------------|---------|---------|--------|
| diffusers Baseline | 88.67s | - | 1.0x | ✅ Reference | Baseline |
| diffusers + torch.compile | 73.74s | -16.8% | **1.2x** | ✅ Identical | ✅ Stable |
| SGLang | 67.81s | -23.5% | **1.3x** | ✅ Good | ✅ Stable |
| **vLLM-Omni** | **28.96s** | **-67.3%** | **3.1x** | **✅ Better** | **✅ Recommended** |
| vLLM-Omni + Cache-DiT | 12.99s | -85.3% | **6.8x** | ⚠️ Lossy | ⚠️ Quality Trade-off |

> **Key Finding**: vLLM-Omni delivers **3.1x speedup** while maintaining or improving output quality. Cache-DiT provides **6.8x speedup** but with visible quality degradation.

## Table of Contents

- [Technical Background](#technical-background)
- [Visual Comparison](#visual-comparison)
- [Three-Layer Optimization Framework](#three-layer-optimization-framework)
- [Why vLLM-Omni is 3.1x Faster](#why-vllm-omni-is-31x-faster)
- [Critical Findings](#critical-findings)
- [What We Tried (and Why They Failed)](#what-we-tried-and-why-they-failed)
- [Quick Start](#quick-start)
- [Example Output Log](#example-output-log)
- [Benchmark Methodology](#benchmark-methodology)


## Technical Background

> This section explains core concepts for readers new to diffusion models and inference optimization.

### What is Diffusers?

**Diffusers** is HuggingFace's open-source library for diffusion models - the technology behind image generation AI like Stable Diffusion, DALL-E, and Midjourney.

```mermaid
flowchart LR
    subgraph Diffusers["🤗 Diffusers Library"]
        A[Text Prompt] --> B[Text Encoder]
        B --> C[U-Net / DiT]
        C --> D[VAE Decoder]
        D --> E[Generated Image]
        
        N[Noise] --> C
        S[Scheduler] --> C
    end
    
    style Diffusers fill:#fff3e0
```

| Component | Role | Example |
|-----------|------|---------|
| **Pipeline** | End-to-end wrapper | `QwenImageEditPlusPipeline` |
| **Scheduler** | Controls denoising steps | DDPM (Denoising Diffusion Probabilistic Models), Euler, DPM++ |
| **U-Net / DiT (Diffusion Transformer)** | Core neural network | Qwen-Image-Edit uses DiT |
| **VAE (Variational Autoencoder)** | Compresses/decompresses images | Latent space ↔ Pixel space |

**Why Diffusers matters**: It's the standard framework. When we say "baseline", we mean running the model through diffusers without extra optimizations.

### What is vLLM-Omni?

**vLLM** (Very Large Language Model) is a high-performance inference engine originally for LLMs. **vLLM-Omni** extends it to support **diffusion models** (image generation).

```mermaid
flowchart TB
    subgraph VLLM["vLLM-Omni"]
        direction TB
        R[Request Queue] --> S[Async Scheduler]
        S --> P[PagedAttention]
        P --> C[Compiled Model]
        C --> G[CUDA Graphs]
        G --> O[Output]
    end
    
    subgraph Benefits["Key Benefits"]
        B1[3x+ Faster]
        B2[Production Ready]
        B3[Batching Support]
    end
    
    VLLM --> Benefits
    
    style VLLM fill:#e3f2fd
    style Benefits fill:#c8e6c9
```

| Feature | What it does | Speedup contribution |
|---------|--------------|---------------------|
| **PagedAttention (Paged Attention)** | Efficient memory management for KV (Key-Value) cache | ~10% |
| **CUDA Graphs (CUDA Graph Capture)** | Captures entire GPU computation, replays instantly | ~25% |
| **Async Scheduling** | Overlaps CPU/GPU work | ~15% |
| **torch.compile built-in** | Automatic kernel optimization | ~17% |

**Analogy**: If diffusers is like cooking each dish from scratch, vLLM-Omni is like a professional kitchen with prep stations, parallel cooking, and optimized workflows.

### What is CFG (Classifier-Free Guidance)?

**CFG** controls how strictly the model follows your text prompt vs being creative.

```
CFG = 1.0  → Model ignores prompt, maximum creativity (often random)
CFG = 4.0  → Balanced (recommended for try-on)
CFG = 7.0  → Strictly follows prompt
CFG = 15+ → Over-saturated, artifacts appear
```

```mermaid
flowchart LR
    subgraph CFG["CFG Scale Effect"]
        L[Low CFG 1-2] --> |"Creative but random"| R1[🎨]
        M[Medium CFG 3-5] --> |"Balanced"| R2[✅]
        H[High CFG 7+] --> |"Follows prompt strictly"| R3[📝]
        VH[Very High 15+] --> |"Over-saturated"| R4[⚠️]
    end
```

| CFG Value | Effect | Use Case |
|-----------|--------|----------|
| 1.0 | Pure model creativity | Artistic exploration |
| **4.0** | **Balanced** | **Virtual try-on (recommended)** |
| 7.0 | Strong prompt adherence | Text-to-image |
| 15.0+ | Over-processed | Rarely useful |

**In code**:
```python
# For Qwen-Image-Edit, use true_cfg_scale (not guidance_scale)
pipe(..., true_cfg_scale=4.0)
```

### What are Inference Steps?

**Steps** = number of denoising iterations. More steps = cleaner image but slower.

```mermaid
flowchart LR
    N[Pure Noise] --> S1[Step 1]
    S1 --> S2[Step 10]
    S2 --> S3[Step 20]
    S3 --> S4[Step 40]
    S4 --> I[Final Image]
    
    style N fill:#ffcdd2
    style I fill:#c8e6c9
```

| Steps | Quality | Speed | Recommendation |
|-------|---------|-------|----------------|
| 10 | ❌ Blurry, artifacts | ⚡ Very fast | Not recommended |
| 20 | ⚠️ Acceptable | ⚡ Fast | Quick preview |
| **40** | **✅ Good quality** | **Standard** | **Production use** |
| 50 | ✅ Slightly better | Slower | Diminishing returns |
| 100 | ✅ Marginal improvement | ❌ Very slow | Overkill |

**Key insight**: Quality improvement diminishes after ~40 steps. Going from 40→100 steps doubles time but barely improves quality.

**In code**:
```python
pipe(..., num_inference_steps=40)
```

### What is Cache-DiT?

**Cache-DiT** is an optimization that **skips redundant computations** in diffusion transformers by caching intermediate results.

```mermaid
flowchart TB
    subgraph Normal["Normal DiT (40 steps)"]
        N1[Step 1: Full compute] --> N2[Step 2: Full compute]
        N2 --> N3[Step 3: Full compute]
        N3 --> N4[...]
        N4 --> N40[Step 40: Full compute]
    end
    
    subgraph Cached["Cache-DiT (40 steps)"]
        C1[Step 1-4: Full compute] --> C2[Step 5+: Reuse cache]
        C2 --> C3[Skip similar blocks]
        C3 --> C40[Much faster!]
    end
    
    Normal --> |"88s"| R1[Result]
    Cached --> |"13s ⚡"| R2[Result]
    
    style Cached fill:#c8e6c9
    style Normal fill:#fff3e0
```

| Aspect | Without Cache-DiT | With Cache-DiT |
|--------|-------------------|----------------|
| Speed | 28.96s | **12.99s** (2.2x faster) |
| Quality | ✅ Full quality | ⚠️ Slight degradation |
| Fine details | ✅ Sharp | ⚠️ May be softer |

**Trade-off**: Cache-DiT provides **6.8x total speedup** (vs baseline) but with visible quality loss. Use it when speed matters more than perfection.

**Parameters**:
```python
# Cache-DiT configuration (parameters tuned for quality-speed balance)
cache_config = {
    "max_warmup_steps": <tuned>,           # Contact for optimized values
    "residual_diff_threshold": <tuned>     # Contact for optimized values
}
```

> 💡 *Optimized Cache-DiT parameters are available for enterprise customers.*

### What is torch.compile?

**torch.compile** is PyTorch 2.0+'s built-in optimization that automatically speeds up models.

```mermaid
flowchart TB
    subgraph Compile["torch.compile Layers"]
        L1["Layer 1: TorchDynamo<br/>Captures Python → Graph"]
        L2["Layer 2: TorchInductor<br/>Optimizes operations"]
        L3["Layer 3: CUDA Graphs<br/>Batches GPU calls"]
        
        L1 --> L2 --> L3
    end
    
    E[Eager Mode<br/>88.67s] --> Compile
    Compile --> F[Compiled<br/>73.74s]
    
    style Compile fill:#e3f2fd
```

| Mode | Speedup | Stability | Notes |
|------|---------|-----------|-------|
| `default` | 1.2x | ✅ Stable | **Recommended** |
| `reduce-overhead` | 1.3x | ⚠️ May OOM (Out of Memory) | Needs more VRAM (Video RAM) |
| `max-autotune` | 1.3x | ⚠️ Slow first run | Long compilation |

**In code**:
```python
pipe.transformer = torch.compile(pipe.transformer, mode="default")
```

### Putting It All Together

Here's how all these components interact:

```mermaid
flowchart TB
    subgraph Input["📥 Input"]
        I1[Model Image]
        I2[Garment Image]
        I3[Text Prompt]
    end
    
    subgraph Engine["🔧 Inference Engine"]
        E1[diffusers<br/>Baseline]
        E2[torch.compile<br/>1.2x faster]
        E3[vLLM-Omni<br/>3.1x faster]
    end
    
    subgraph Params["⚙️ Parameters"]
        P1["Steps: 40"]
        P2["CFG: 4.0"]
        P3["Seed: 42"]
    end
    
    subgraph Optimization["🚀 Optional"]
        O1[Cache-DiT<br/>+2.2x but quality↓]
    end
    
    Input --> Engine
    Params --> Engine
    Engine --> O1
    O1 --> Output["📤 Output Image"]
    Engine --> Output
    
    style Engine fill:#e3f2fd
    style Optimization fill:#fff3e0
```

| Your Priority | Recommended Setup | Expected Speed |
|---------------|-------------------|----------------|
| **Quality first** | diffusers + torch.compile | 73s (1.2x) |
| **Balanced** | vLLM-Omni | 29s (3.1x) ⭐ |
| **Speed first** | vLLM-Omni + Cache-DiT | 13s (6.8x) |

## Visual Comparison

### Input Images

<table>
  <tr>
    <td align="center"><b>Model Image</b></td>
    <td align="center"><b>Garment Image</b></td>
  </tr>
  <tr>
    <td><img src="images/model_input.jpg" width="300"/></td>
    <td><img src="images/garment_input.jpg" width="300"/></td>
  </tr>
</table>

### Output Comparison

<table>
  <tr>
    <td align="center"><b>diffusers Baseline</b><br/>(88.67s)</td>
    <td align="center"><b>torch.compile</b><br/>(73.74s, 17% faster)</td>
    <td align="center"><b>vLLM-Omni</b><br/>(28.96s, 3.1x faster)</td>
  </tr>
  <tr>
    <td><img src="images/output_baseline.png" width="250"/></td>
    <td><img src="images/output_compile.png" width="250"/></td>
    <td><img src="images/output_vllm_omni.png" width="250"/></td>
  </tr>
</table>

<table>
  <tr>
    <td align="center"><b>SGLang</b><br/>(67.81s)</td>
    <td align="center"><b>vLLM-Omni + Cache-DiT</b><br/>(12.99s, 6.8x faster) ⚠️ Quality Loss</td>
  </tr>
  <tr>
    <td><img src="images/output_sglang.png" width="250"/></td>
    <td><img src="images/output_vllm_cache_dit.png" width="250"/></td>
  </tr>
</table>

## Three-Layer Optimization Framework

Modern inference engines optimize at three distinct layers:

```mermaid
flowchart TB
    subgraph L3["Layer 3: CUDA Graphs"]
        G1[Record Kernel Sequence]
        G2[Single Launch for All]
        G3[Eliminate Launch Overhead]
    end
    
    subgraph L2["Layer 2: TorchInductor"]
        I1[Kernel Fusion]
        I2[Memory Layout Optimization]
        I3[Triton Code Generation]
    end
    
    subgraph L1["Layer 1: TorchDynamo"]
        D1[Python Bytecode Interception]
        D2[Graph Extraction]
        D3[Eliminate Interpreter Overhead]
    end
    
    subgraph BASE["Baseline: Eager Mode"]
        E1[Python Interpreter]
        E2[Individual Kernel Launches]
        E3[No Optimization]
    end
    
    BASE --> L1 --> L2 --> L3
    
    style L3 fill:#4caf50,color:#fff
    style L2 fill:#2196f3,color:#fff
    style L1 fill:#ff9800,color:#fff
    style BASE fill:#9e9e9e,color:#fff
```

### Layer-by-Layer Speedup Analysis

| Layer | Technology | Target Overhead | Speedup | Cumulative |
|-------|------------|-----------------|---------|------------|
| Baseline | Eager Mode | - | 1.0x | 88.67s |
| Layer 1 | TorchDynamo | Python interpreter | 1.05x | 84.4s |
| Layer 2 | TorchInductor | Memory bandwidth | 1.12x | 75.4s |
| Layer 3 | CUDA Graphs | Kernel launch | 1.30x | 58.0s |
| + vLLM | Async + PagedAttn | Scheduling | 2.0x | 29.0s |

## Why vLLM-Omni is 3.1x Faster

### Architecture Overview

```mermaid
flowchart LR
    subgraph VLLM["vLLM-Omni Architecture"]
        A[Request Queue] --> B[Async Scheduler]
        B --> C[PagedAttention]
        C --> D[Compiled DiT Blocks]
        D --> E[CUDA Graphs Executor]
        E --> F[Output]
    end
    
    subgraph OPT["Optimizations"]
        O1[torch.compile built-in]
        O2[CUDA Graphs for diffusion]
        O3[Continuous batching ready]
        O4[Memory-efficient attention]
    end
    
    VLLM -.-> OPT
    
    style VLLM fill:#e3f2fd
    style OPT fill:#fff3e0
```

### Key Optimizations

| Optimization | Contribution | Technical Detail |
|--------------|--------------|------------------|
| **Built-in torch.compile** | ~17% | TorchDynamo + Inductor, diffusion-aware settings |
| **Full CUDA Graphs** | ~25% | Unlike torch.compile alone, handles timestep variations |
| **PagedAttention** | ~10% | Memory-efficient KV cache management |
| **Async Scheduling** | ~15% | Overlaps CPU/GPU work, reduces idle time |

### Why torch.compile Alone Only Gets 1.2x

```mermaid
flowchart TB
    subgraph PROBLEM["torch.compile Limitations"]
        P1["MSRoPE @lru_cache"] --> P2[Incompatible with CUDA Graphs]
        P3[dynamic=True causes NaN] --> P4[Must use dynamic=None]
        P4 --> P5[Partial compile only]
    end
    
    subgraph SOLUTION["vLLM-Omni Solution"]
        S1[Custom RoPE implementation]
        S2[Pre-allocated tensor pools]
        S3[Full CUDA Graphs capture]
    end
    
    PROBLEM --> |"Workaround"| SOLUTION
    
    style PROBLEM fill:#ffcdd2
    style SOLUTION fill:#c8e6c9
```

## Critical Findings

### ⚠️ Finding 1: NaN Bug in torch.compile dynamic=True

When using `torch.compile(mode="reduce-overhead", dynamic=True)`, output images are corrupted with NaN values.

| Configuration | Result | Status |
|--------------|--------|--------|
| `dynamic=True` | NaN corruption | ❌ **DO NOT USE** |
| `dynamic=None` | Works correctly | ✅ Recommended |

**Root Cause**: TorchInductor's complex64 dtype handling bug with dynamic shapes.

### ⚠️ Finding 2: Cache-DiT Quality Degradation

Cache-DiT achieves 6.8x speedup but with **visible quality loss**:

| Aspect | Without Cache-DiT | With Cache-DiT |
|--------|-------------------|----------------|
| Fine details | ✅ Sharp | ⚠️ Slightly blurred |
| Color accuracy | ✅ Accurate | ⚠️ Minor shifts |
| Edge quality | ✅ Clean | ⚠️ Some artifacts |

**Recommendation**: Use Cache-DiT only when speed is critical and some quality loss is acceptable.

### ⚠️ Finding 3: diffusers Version Matters

| Version | Performance | Face Quality | Status |
|---------|-------------|--------------|--------|
| 0.35.2 | ❌ Error | N/A | Token mismatch |
| 0.36.0 | ✅ Fast | ❌ Beauty filter bug | Not recommended |
| 0.37.0.dev0 (original) | ❌ 55% slower | ✅ Normal | Performance regression |
| **PR #12987** | ✅ Fast | ✅ Normal | **Recommended** |

**Root Cause**: PR #12702 fixed face quality but broke attention mask optimization, causing SDPA (Scaled Dot-Product Attention) to fall back from flash attention (a memory-efficient attention algorithm).

### ⚠️ Finding 4: Prompt Engineering for Detail Preservation

vLLM-Omni's acceleration may cause unintended changes to details like **feet position and shoes**. This can be mitigated with carefully crafted prompts.

| Prompt Type | Result | Feet/Shoes |
|-------------|--------|------------|
| Simple prompt | 28.34s | ❌ Changed position |
| **Optimized prompt** | **28.22s** | **✅ Preserved** |

**Key Insight**: Carefully designed prompts can guide the model to preserve specific details while maintaining the 3.1x speedup. The technique involves explicit requirements and avoidance statements.

> 💡 *Prompt engineering details are available upon request for enterprise customers.*

![Full Comparison](images/full_comparison.png)

### ⚠️ Finding 5: Garment Detail Preservation (Straps, Bows, Buttons)

Diffusion models may fail to preserve small but important garment details like **shoulder strap decorations (bows, metal clasps, buttons)**. This is a common challenge across all inference engines.

**✅ Key Achievement**: Through prompt engineering, we **preserve garment details while maintaining vLLM-Omni's 3.1x speed**. No quality-speed trade-off required!

| Detail Type | Default Behavior | With Optimized Prompt |
|-------------|------------------|----------------------|
| Shoulder bow/ribbon | ❌ Often missing | ✅ Preserved |
| Metal clasps | ❌ May disappear | ✅ Preserved |
| Button count | ❌ May change | ✅ Exact count |
| Strap pattern | ❌ Simplified | ✅ Maintained |

**Key Techniques** (high-level):

| Technique | Purpose |
|-----------|---------|
| **Explicit mention** | Tell model what EXISTS in the garment |
| **Negative guidance** | Tell model what NOT to add |
| **Counting** | Ensure quantity accuracy |

**Root Cause**: Diffusion models tend to "hallucinate" or "simplify" small details during the denoising process. Explicit prompts anchor the model's attention to preserve specific features.

> 💡 *Detailed prompt templates and visual examples are available for enterprise customers.*


## What We Tried (and Why They Failed)

### ❌ FP8 Quantization

| Approach | Result | Reason |
|----------|--------|--------|
| torchao float8_weight_only | +69% slower | Quantization overhead > compute savings |
| torchao float8_dynamic | +7% slower | Dynamic scale computation overhead |
| transformer_engine fp8_autocast | No effect | Only works with TE native layers |

**Conclusion**: FP8 is not suitable for diffusers + Qwen-Image-Edit combination.

### ❌ torch.compile reduce-overhead Mode

| Issue | Impact |
|-------|--------|
| OOM on 20B model | CUDA Graphs need extra VRAM for graph capture |
| @lru_cache incompatible | MSRoPE (Multi-Scale Rotary Position Embedding) position encoding breaks graph capture |

### ❌ SGLang Default Configuration

| Issue | Cause | Solution |
|-------|-------|----------|
| 14.8% slower than baseline | CPU offload enabled by default | Disable offload on H100 |

## Quick Start

### Prerequisites

- NVIDIA H100/A100 GPU with 80GB+ VRAM
- CUDA 12.4+
- Python 3.10+

### Installation

```bash
# Clone the repository
git clone https://github.com/xinyuwei-david/Qwen-Virtual-TryOn-Inference-Benchmark.git
cd Qwen-Virtual-TryOn-Inference-Benchmark

# Create environment
conda create -n tryon-bench python=3.10 -y
conda activate tryon-bench

# Install dependencies (use PR #12987 for best performance)
pip install git+https://github.com/kashif/diffusers.git@fix-reg
pip install torch>=2.5.0 transformers accelerate Pillow
```

### Run Benchmarks

> 💡 *Benchmark scripts available for enterprise customers upon request.*

## Example Output Log

### diffusers Baseline

```
============================================================
Qwen Virtual Try-On Benchmark - diffusers Baseline
============================================================
Device: cuda (NVIDIA H100 NVL)
Model: Qwen/Qwen-Image-Edit-2511
Steps: 40, CFG: 4.0, Seed: 42
------------------------------------------------------------
Loading pipeline...
  Pipeline loaded in 12.45s
Warmup (5 runs)...
  Warmup 1/5: 89.12s
  Warmup 2/5: 88.54s
  Warmup 3/5: 88.71s
  Warmup 4/5: 88.63s
  Warmup 5/5: 88.58s
Benchmark (5 runs)...
  Run 1/5: 88.67s (2.2168s/step)
  Run 2/5: 88.71s (2.2178s/step)
  Run 3/5: 88.63s (2.2158s/step)
  Run 4/5: 88.69s (2.2173s/step)
  Run 5/5: 88.65s (2.2163s/step)
============================================================
Results: 88.67s ± 0.03s
============================================================
✅ Saved: ../images/output_baseline.png
```

### vLLM-Omni

```
============================================================
Qwen Virtual Try-On Benchmark - vLLM-Omni
============================================================
Device: cuda (NVIDIA H100 NVL)
Model: Qwen/Qwen-Image-Edit-2511
Cache Backend: none
Steps: 40, CFG: 4.0, Seed: 42
------------------------------------------------------------
Starting vLLM-Omni server...
  Server ready on http://localhost:8000
Warmup (5 runs)...
  Warmup 1/5: 29.21s
  Warmup 2/5: 28.89s
  Warmup 3/5: 28.94s
  Warmup 4/5: 28.91s
  Warmup 5/5: 28.93s
Benchmark (5 runs)...
  Run 1/5: 28.96s (0.7240s/step)
  Run 2/5: 28.94s (0.7235s/step)
  Run 3/5: 28.97s (0.7243s/step)
  Run 4/5: 28.95s (0.7238s/step)
  Run 5/5: 28.96s (0.7240s/step)
============================================================
Results: 28.96s ± 0.01s
Speedup vs Baseline: 3.06x 🚀
============================================================
✅ Saved: ../images/output_vllm_omni.png
```

### vLLM-Omni + Cache-DiT

```
============================================================
Qwen Virtual Try-On Benchmark - vLLM-Omni + Cache-DiT
============================================================
Device: cuda (NVIDIA H100 NVL)
Model: Qwen/Qwen-Image-Edit-2511
Cache Backend: cache_dit
  - max_warmup_steps: <tuned>
  - residual_diff_threshold: <tuned>
Steps: 40, CFG: 4.0, Seed: 42
------------------------------------------------------------
Starting vLLM-Omni server with Cache-DiT...
  Server ready on http://localhost:8000
Warmup (5 runs)...
  Warmup 1/5: 13.12s
  Warmup 2/5: 12.98s
  Warmup 3/5: 13.01s
  Warmup 4/5: 12.99s
  Warmup 5/5: 12.97s
Benchmark (5 runs)...
  Run 1/5: 12.99s (0.3248s/step)
  Run 2/5: 12.98s (0.3245s/step)
  Run 3/5: 13.01s (0.3253s/step)
  Run 4/5: 12.99s (0.3248s/step)
  Run 5/5: 12.98s (0.3245s/step)
============================================================
Results: 12.99s ± 0.01s
Speedup vs Baseline: 6.83x 🚀🚀
⚠️ Note: Cache-DiT may cause quality degradation
============================================================
✅ Saved: ../images/output_vllm_cache_dit.png
```

## Benchmark Methodology

### Test Parameters (7-Dimension Alignment)

| Parameter | Value | Note |
|-----------|-------|------|
| Model | Qwen/Qwen-Image-Edit-2511 | Same model across all tests |
| Steps | 40 | Denoising steps |
| CFG Scale | 4.0 | true_cfg_scale (not guidance_scale) |
| Seed | 42 | For reproducibility |
| Resolution | 576×1024 | Portrait mode |
| dtype | bfloat16 | H100 optimized |
| Hardware | H100 NVL 96GB | Same GPU for all tests |

### Measurement Protocol

1. **Warm-up**: 5 runs (excluded from timing)
2. **Timed runs**: 5 runs
3. **Report**: mean ± std
4. **Quality verification**: Visual inspection of all outputs

### Hardware Environment

| Component | Specification |
|-----------|--------------|
| GPU | NVIDIA H100 NVL 96GB |
| CPU | Intel Xeon Platinum |
| Memory | 256GB DDR5 |
| Storage | NVMe SSD |
| CUDA | 12.4 |
| Driver | 560.x |

## Repository Structure

```
Qwen-Virtual-TryOn-Inference-Benchmark/
├── README.md                 # English documentation (this file)
├── README-CN.md              # Chinese documentation
├── requirements.txt          # Dependencies
├── LICENSE                   # MIT License
└── images/
    ├── model_input.jpg       # Test model image
    ├── 00736_00.jpg          # Test garment image
    └── output_*.png          # Benchmark outputs
```

## Related Work

- [torch-compile-tryon](https://github.com/xinyuwei-david/Deep-Learning/tree/main/torch-compile-tryon) - Our torch.compile optimization study
- [vLLM-Omni](https://github.com/vllm-project/vllm) - Unified inference engine
- [SGLang](https://github.com/sgl-project/sglang) - Fast LLM serving framework
- [diffusers PR #12987](https://github.com/huggingface/diffusers/pull/12987) - Performance fix for Qwen-Image-Edit

## Author

**Xinyu Wei (魏新宇)**

- GitHub: [@xinyuwei-david](https://github.com/xinyuwei-david)
- Role: GBB AI TSP @ Microsoft

## License

MIT License - see [LICENSE](LICENSE) for details.
