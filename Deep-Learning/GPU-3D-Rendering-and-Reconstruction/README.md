# GPU Architecture Deep Dive: From 3D Rendering Origins to AI Inference Acceleration

> **Author**: Xinyu Wei
>
> **Core thesis**: GPUs were born for 3D rendering. AI inference is an "accidental beneficiary." **Understanding rendering's design philosophy reveals why GPUs are naturally suited for AI — and how to better exploit them.**
>
> **Unique perspective**: This guide validates the deep connections between rendering techniques and AI inference optimizations using the author's real benchmark data — not speculation, but engineering evidence.

---

## Executive Summary

Every AI inference engineer uses GPUs, but few ask: **Why are GPUs designed the way they are?** The answer lies in GPU's birth certificate — 3D rendering.

| Rendering Design Decision | Corresponding AI Optimization | Author's Evidence |
|:---|:---|:---|
| Tiled Rendering | FlashAttention tiling | FlashInfer 9-15% faster at 32K ([FlashInfer-vs-FA](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/FlashInfer-vs-FlashAttention-Benchmark)) |
| Z-Buffer per-pixel memory | PagedAttention block KV Cache | KV Cache six-level guide ([KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive)) |
| Mipmap multi-res LOD | Speculative Decoding draft-verify | EAGLE3 2.67x speedup ([EAGLE3](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Speculative-Decoding-EAGLE3)) |
| Z-fighting 16-bit flicker | BF16 precision accumulation | fuse_lora SSIM gap 2-18% ([LoRA-Merge](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)) |
| Frame buffer reuse | KV Cache caching K/V | GQA/MLA 4-arch comparison ([KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive)) |
| Path Tracing Monte Carlo + denoise | Diffusion DDPM + denoise | Distillation 40→8 steps ([Diffusion-Distillation](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Diffusion-Distillation)) |

---

## 1. The Rendering Problem: Why 3D Must Become 2D

**Because your monitor is 2D.** A 3D scene must be "compressed" into a 2D pixel matrix.

| Method | Approach | GPU Hardware |
|:---|:---|:---|
| **Rasterization** | Each triangle asks: "Which pixels do I cover?" | CUDA Core + Fixed-function Rasterizer |
| **Ray Tracing** | Each pixel asks: "What object do I see?" | RT Core (BVH traversal + Ray-Triangle intersection) |

**Why triangles?** Any 3 points are coplanar (uniquely define a plane); 4 points may not be. Triangles are the simplest guaranteed-planar primitive.

---

## 2. Graphics Pipeline — 5 Steps

The core of 3D→2D is **5 matrix multiplications** (4×4 each):

```
Model coords → [Model Transform] → World coords → [Camera Transform] → Camera coords
→ [Projection] → NDC → [Clipping] → [Viewport] → Screen pixels
```

| Step | What | Why |
|:---|:---|:---|
| **Model Transform** | Place object (rotate+translate+scale) | 4×4 unifies all transforms (3×3 can't translate) |
| **Camera Transform** | Move camera to origin | LookAt matrix, cross products build orthonormal basis |
| **Projection** | Near big, far small | Perspective: divide by z depth, frustum → NDC |
| **Clipping** | Discard invisible parts | Clipping in NDC cube is simpler than in frustum |
| **Viewport** | NDC → pixels | [-1,1] → [0,Width]×[0,Height] |

**Key insight**: All 5 steps are matrix multiplications — they can be pre-multiplied into one matrix. **This is why GPUs exist: massively parallel matrix operations.**

---

## 3. Rasterization vs Ray Tracing

| Effect | Rasterization | Ray Tracing |
|:---|:---|:---|
| Reflections | Cube Map approximation | Recursive reflection rays (physically correct) |
| Shadows | Shadow Map approximation | Shadow ray occlusion test |
| Refraction | Screen-space distortion | Snell's Law + refraction rays |
| Global illumination | Pre-baked Light Probes | Path Tracing Monte Carlo |
| Speed | Fast (60-240fps real-time) | 1-2 orders of magnitude slower |

### Rendering Results

**E1 Software Rasterizer** (14-triangle cube, Edge Function + Z-Buffer + Lambert shading):

![E1 Rasterization](images/e1_final_render.png)

**E2 Software Ray Tracer** (reflective spheres + shadows + multi-light, recursive depth 3):

![E2 Ray Tracing Showcase](images/e2_showcase_render.png)

**E3 Pixel-level Comparison** (Left: rasterization | Middle: ray tracing | Right: difference heatmap, blue=similar, red=different):

![E3 Comparison](images/e3_comparison.png)

> Differences concentrate in **shadow regions** (38% of pixels show large differences) — this is exactly where ray tracing's physical realism shines.

**E4 Blender EEVEE (Rasterization)**:

![E4 EEVEE](images/e4_eevee_640.png)

Experiment scripts and full data available in [scripts/](scripts/) directory.

Sources: [Scratchapixel](https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/overview-rasterization-algorithm.html) (CC BY-NC-ND 4.0), Wikipedia [Ray Tracing](https://en.wikipedia.org/wiki/Ray_tracing_(graphics))

---

## 4. GPU Architecture Evolution

```
1990s   Fixed pipeline — hardware could only do predefined rendering steps
2001    Programmable Shader (GeForce 3)
2006    Unified Shader (GeForce 8) — CUDA born → GPGPU → AI begins
2017    Tensor Core (Volta V100) — matrix multiply hardware acceleration
2018    RT Core (Turing RTX 20) — real-time ray tracing
2020    3rd gen Tensor Core (A100) — TF32/BF16/INT8, structured sparsity
2022    4th gen Tensor Core (H100) — FP8, Transformer Engine
2024    5th gen Tensor Core (B200) — FP4
```

**Design pattern**: When an operation becomes a bottleneck with a fixed pattern → **make it dedicated hardware**.

| General → Programmable → Specialized | Rendering | AI |
|:---|:---|:---|
| CPU general | CPU rendering | CPU ML |
| GPU parallel | CUDA Core Shaders | CUDA Core kernels |
| Dedicated ASIC | RT Core (BVH) | Tensor Core (GEMM) |

---

## 5. Three Types of GPU Cores

| | CUDA Core | RT Core | Tensor Core |
|:---|:---|:---|:---|
| **Function** | General parallel compute | BVH + Ray-Triangle intersection | Matrix multiply (GEMM) |
| **Programmable** | ✅ | ❌ Fixed-function | ❌ Fixed-function |
| **Rendering** | Shaders | Ray tracing acceleration | DLSS |
| **AI** | General CUDA | — | Training & inference |

### Data Center vs Gaming GPUs

| GPU | CUDA Cores | Tensor Cores | RT Cores | Purpose |
|:---|:---:|:---:|:---:|:---|
| **H100** SXM | 16,896 | 528 (4th gen) | ❌ | AI training/inference |
| **A100** | 6,912 | 432 (3rd gen) | ❌ | AI training/inference |
| **A10** | 9,216 | 288 (3rd gen) | ✅ 72 (2nd gen) | Inference + graphics |
| **RTX 4090** | 16,384 | 512 (4th gen) | ✅ 128 (3rd gen) | Gaming + AI |

> **Insight**: Data center GPUs (H100/A100) have **no RT Cores** — purely optimized for AI. A10 has all three core types, used in Azure NV-series for mixed graphics+inference workloads.

Source: NVIDIA official specifications

---

## 6. DLSS: Where Rendering Meets AI

| Version | Year | Core Technology |
|:---:|:---:|:---|
| 1.0 | 2019 | Per-game trained CNN |
| 2.0 | 2020 | Universal temporal feedback network + motion vectors |
| 3.0 | 2022 | + Frame Generation (AI generates intermediate frames) |
| 4.0 | 2025 | Multi Frame Generation (up to 3 frames at once) |
| 4.5 | 2025 | Dynamic Multi Frame Generation |

Sources: [NVIDIA DLSS](https://www.nvidia.com/en-us/geforce/technologies/dlss/), [DLSS 4.5 Blog](https://developer.nvidia.com/blog/nvidia-dlss-4-5-delivers-super-resolution-upgrades-and-new-dynamic-multi-frame-generation/)

---

## 7. ★ Core Chapter: Rendering × AI Inference — Validated with Engineering Data

> Every analogy below is backed by the author's **real benchmark data**.

### 7.1 Tiled Rendering ↔ FlashAttention

**Rendering**: Tiled Rendering splits the screen into 16×16 blocks, processing each independently to avoid global memory bottleneck.

**AI**: FlashAttention tiles Q/K/V matrices, computing Softmax in SRAM to avoid HBM round-trips.

**Evidence**: FlashInfer is 9-15% faster than FlashAttention at 32K sequence length on A100. Source: [FlashInfer-vs-FlashAttention-Benchmark](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/FlashInfer-vs-FlashAttention-Benchmark)

**Shared principle**: IO-aware tiling — move compute to data, not data to compute.

### 7.2 Z-Buffer ↔ PagedAttention

**Rendering**: Z-Buffer writes depth per-pixel on demand, no pre-allocation.

**AI**: PagedAttention allocates KV Cache in pages, no pre-allocation for max sequence length.

**Evidence**: KV Cache size varies >10x across GQA/MLA/Hybrid Attention/Hybrid Mamba architectures. Source: [KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive)

**Shared principle**: Memory is scarce; on-demand allocation beats pre-allocation.

### 7.3 Mipmap/LOD ↔ Speculative Decoding

**Rendering**: Far objects use low-res textures (fast, saves bandwidth); near objects use high-res.

**AI**: Small draft model generates candidate tokens quickly; large model verifies in one pass.

**Evidence**: EAGLE3 achieves 2.67x speedup. Source: [Speculative-Decoding-EAGLE3](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Speculative-Decoding-EAGLE3)

**Shared principle**: Cheap approximation first, expensive verification second.

### 7.4 Z-fighting ↔ BF16 Precision Issues

**Rendering**: Z-Buffer's 16-bit precision causes flickering when two surfaces are nearly coplanar.

**AI**: BF16's 7-bit mantissa causes accumulated rounding errors in Diffusion's multi-step ODE solving.

**Evidence**: At 8-step distillation, fuse_lora SSIM=1.0 vs set_adapters SSIM=0.88-0.91. Source: [LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)

**Shared principle**: Finite precision amplifies errors in accumulated computation; fewer steps = more sensitive.

### 7.5 Frame Buffer ↔ KV Cache

**Rendering**: DLSS uses previous frame + motion vectors to generate high-res output.

**AI**: KV Cache stores computed Keys/Values; generating next token only computes new Q.

**Evidence**: FP8 KV Cache quantization reduces ~50% VRAM. Source: [Qwen3.5-122B-Azure-vs-AWS-Benchmark](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Qwen3.5-122B-Azure-vs-AWS-Benchmark)

**Shared principle**: Cache intermediate results; trade space for time.

### 7.6 Path Tracing Monte Carlo ↔ Diffusion Denoising

**Rendering**: Path Tracing randomly samples light paths → denoise.

**AI**: Diffusion starts from pure noise → iteratively denoise to reconstruct image.

**Evidence**: Distillation compresses 40 steps → 8 steps (ODE trajectory distillation). Source: [Diffusion-Distillation](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Diffusion-Distillation)

**Shared principle**: Iterative process from random to ordered; steps vs quality trade-off.

---

## 8. 2D→3D Reconstruction (Brief)

| Method | Input | Key Idea |
|:---|:---|:---|
| **NeRF** (2020) | N photos | MLP fitting 5D radiance field |
| **3D Gaussian Splatting** (2023) | N photos | 100x faster than NeRF, real-time |
| **Monocular Depth** | 1 photo | Learn visual priors at scale |

Sources: Wikipedia [NeRF](https://en.wikipedia.org/wiki/Neural_radiance_field) + [3DGS](https://en.wikipedia.org/wiki/Gaussian_splatting)

---

## Running on Azure

This is a principles + cross-project reference guide. Chapter 7 evidence comes from:

| Project | GPU | Link |
|:---|:---|:---|
| FlashInfer-vs-FA | A100 80GB | [Link](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/FlashInfer-vs-FlashAttention-Benchmark) |
| KV-Cache-Deep-Dive | Analysis | [Link](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive) |
| EAGLE3 | H100 | [Link](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Speculative-Decoding-EAGLE3) |
| LoRA-Merge-Quality | H100 | [Link](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact) |
| Diffusion-Distillation | H100 | [Link](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Diffusion-Distillation) |
| Qwen3.5-122B | H100 | [Link](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Qwen3.5-122B-Azure-vs-AWS-Benchmark) |

---

## Sources

| Content | Source |
|:---|:---|
| Graphics Pipeline | Wikipedia [Graphics Pipeline](https://en.wikipedia.org/wiki/Graphics_pipeline) |
| Rasterization | [Scratchapixel](https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/overview-rasterization-algorithm.html) (CC BY-NC-ND 4.0) |
| Ray Tracing | Wikipedia [Ray Tracing](https://en.wikipedia.org/wiki/Ray_tracing_(graphics)) |
| DLSS | [NVIDIA DLSS](https://www.nvidia.com/en-us/geforce/technologies/dlss/) |
| RT Core | [NVIDIA Turing In-Depth](https://developer.nvidia.com/blog/nvidia-turing-architecture-in-depth/) |
| GPU specs | NVIDIA official specifications |
| Rendering × AI connections | Author's benchmark data (Chapter 7 source links) |
