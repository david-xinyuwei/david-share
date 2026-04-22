# GPU 3D Rendering and Reconstruction — An AI Inference Engineer's Guide

> **Author**: Xinyu Wei
>
> **Core Perspective**: GPUs were born for 3D rendering. AI inference is an "accidental beneficiary." Understanding rendering's design philosophy reveals why GPUs are naturally suited for AI.

## Executive Summary

This guide examines GPU's 3D→2D rendering pipeline, the design philosophy behind three types of GPU Cores (CUDA Core / RT Core / Tensor Core), and the deep connections between rendering techniques and AI inference optimization — all from an AI inference engineer's perspective.

**Key Findings**:

| Finding | Data |
|---------|------|
| Rasterization vs Ray Tracing speed gap | Same scene: rasterization 1.3s vs ray tracing 169s (**130x**) |
| Lighting quality difference | SSIM = -0.07, 38% of pixels have large differences (shadow regions) |
| Blender EEVEE vs Cycles | Rasterization 2.37s vs Path Tracing 7.24s (**3x**) |
| Azure vGPU limitation | A10-24Q vGPU not recognized by Blender Cycles CUDA backend |

---

## 1. First Principles: Why Does 3D Need to Become 2D?

**Because your monitor is 2D.** A screen is a flat pixel matrix (e.g., 3840×2160 pixels). No matter how 3D the game world is, it must be "compressed" into a 2D image for display.

**Two rendering approaches**:

| Approach | Method | Analogy |
|----------|--------|---------|
| **Object-centric** | Rasterization | "Each triangle asks: which pixels do I cover?" |
| **Pixel-centric** | Ray Tracing | "Each pixel asks: what object do I see?" |

---

## 2. Graphics Pipeline — 5 Steps in Detail

The core of 3D→2D rendering is **5 coordinate transformations**, each a 4×4 matrix multiplication:

```
Model coords → [Model Transform] → World coords → [Camera Transform] → Camera coords
→ [Projection] → NDC → [Clipping] → [Viewport Transform] → Screen pixels
```

### 2.1 Model Transform — 4×4 Homogeneous Matrix

Places objects at the correct position, orientation, and scale in the world.

**Why 4×4 instead of 3×3?** Because 3×3 matrices can only do rotation and scaling — **not translation**. Adding a 4th dimension (homogeneous coordinates) turns translation into matrix multiplication, unifying all transforms.

**Experiment (E1)**: Y-axis rotation 35° + X-axis rotation 20°, took **37.61 ms**.

### 2.2 Camera/View Transform — LookAt Matrix

Transforms the entire world so the camera sits at the origin, looking along -Z.

**Experiment (E1)**: eye=[0, 1, 3.5], target=[0, 0, 0], took **0.16 ms**.

### 2.3 Perspective Projection — "Near big, far small"

The mathematical essence: dividing by the w component (i.e., z depth). The view frustum is mapped to NDC [-1, 1]³.

**Experiment (E1)**: FOV=60°, aspect=1.33, near=0.1, far=100.0, took **12.55 ms**.

### 2.4 Clipping

Discard triangles outside the NDC cube. Clip partially-visible triangles.

### 2.5 Viewport Transform

NDC [-1, 1] → Screen pixels [0, Width] × [0, Height].

**Experiment (E1)**: 640×480 viewport, took **0.03 ms**.

---

## 3. Two Rendering Routes

### 3.1 Rasterization

**Principle**: Per-triangle projection → Edge Function pixel coverage test → Z-Buffer occlusion.

**Experiment (E1) Results**:

![E1 Rasterization Result](images/e1_final_render.png)

| Step | Time |
|------|------|
| Model Transform | 37.61 ms |
| Camera Transform | 0.16 ms |
| Projection | 12.55 ms |
| Viewport | 0.03 ms |
| **Rasterization** | **1296.47 ms** |
| **Total** | **1346.81 ms** |

> **Finding**: Rasterization itself (Edge Function + Z-Buffer + Lambert) accounts for **96%** of total time. This is why GPUs implement rasterization as fixed-function hardware.

### 3.2 Ray Tracing

**Principle**: Per-pixel ray casting → Find nearest intersection → Compute lighting + shadow rays + reflection rays (recursive).

**Experiment (E2) Showcase Results**:

![E2 Ray Tracing Showcase](images/e2_showcase_render.png)

| Parameter | Value |
|-----------|-------|
| Resolution | 320×240 |
| Primary rays | 76,800 |
| Max reflections | 3 bounces |
| Render time | **4.68 seconds** |
| Per pixel | 60.9 µs |

---

## 4. E3: Rasterization vs Ray Tracing — Pixel-Level Comparison

Same scene (colored cube + ground), 640×480:

| Metric | Value | Meaning |
|--------|-------|---------|
| MSE | 3577.58 | Significant difference |
| SSIM | -0.07 | Visually distinct results |
| Identical pixels | 0.1% | Background only |
| Moderate difference | 60.1% | Same geometry, different lighting |
| Large difference | 38.2% | Shadow regions |

![E3 Comparison](images/e3_comparison.png)

*Left: E1 Rasterization | Middle: E2 Ray Tracing | Right: Difference heatmap (blue=similar, red=different)*

**Speed Comparison**:

| Method | 640×480 Time | Ratio |
|--------|:-----------:|:-----:|
| Rasterization (E1) | 1.3s | 1x |
| Ray Tracing (E2) | 169s | **130x slower** |

> **Core conclusion**: Ray tracing's physical realism (shadows, multi-light illumination) comes at a **130x performance cost**. This is why RT Core hardware acceleration + DLSS frame generation exist.

---

## 5. E4: Blender EEVEE vs Cycles

| Engine | Type | Samples | Time | Device |
|--------|------|:-------:|:----:|:------:|
| **EEVEE** | Rasterization | 32 | **2.37s** | GPU OpenGL |
| **Cycles** | Path Tracing | 64 | **7.24s** | CPU fallback |

**Key finding**: A10-24Q (vGPU) is not recognized by Blender Cycles CUDA backend — GPU utilization stayed at 0%, falling back to CPU rendering.

---

## 6. Three Types of GPU Cores

| | CUDA Core | RT Core | Tensor Core |
|---|---|---|---|
| **Function** | General parallel compute | BVH traversal + Ray-Triangle intersection | Matrix multiplication (GEMM) |
| **Programmable** | ✅ Fully | ❌ Fixed-function ASIC | ❌ Fixed-function (specific matrix sizes) |
| **Rendering** | Vertex/Fragment Shader | Ray tracing acceleration | DLSS AI super-resolution |
| **AI** | General CUDA compute | — | LLM/Diffusion inference & training |
| **Introduced** | 2006 (G80) | 2018 (Turing) | 2017 (Volta) |

---

## 7. DLSS: Where Rendering Meets AI

DLSS uses Tensor Core to run a temporal feedback neural network that upscales low-resolution frames to high resolution and generates intermediate frames — the same Tensor Core hardware used for LLM and Diffusion inference.

Source: https://www.nvidia.com/en-us/geforce/technologies/dlss/

---

## 8. Unique Insight: Rendering × AI Inference — Deep Analogies

> ⚠️ The following analogies are the author's reasoning (marked "speculative"). Not from official documentation.

| Rendering | AI Inference | Shared Design Idea |
|-----------|-------------|-------------------|
| Tiled Rendering | FlashAttention | Block processing to reduce global memory access (speculative) |
| Z-Buffer | PagedAttention | On-demand memory management (speculative) |
| Mipmap / LOD | Speculative Decoding | Low-precision fast approximation + high-precision verification (speculative) |
| Frame Buffer | KV Cache | Cache intermediate results to avoid recomputation (speculative) |
| Z-fighting | BF16 precision issues | Finite precision errors in accumulated computation (speculative) |
| Path Tracing Monte Carlo | Diffusion DDPM | Random sampling + denoising (speculative) |

**Deepest analogy — Fixed-function → Programmable → Specialized acceleration**:

```
Rendering: Fixed pipeline(1990s) → Programmable Shader(2001) → RT Core(2018)
AI:        CPU general(2010s)    → CUDA parallel(2012)       → Tensor Core(2017)
```

Same design philosophy: when an operation becomes a bottleneck with a fixed pattern → make it dedicated hardware.

---

## 9. 2D→3D Reconstruction (Brief)

The inverse problem of rendering: reconstructing 3D structure from 2D images.

| Method | Input | Output | Key Idea |
|--------|-------|--------|----------|
| **NeRF** (2020) | N photos | Radiance field | MLP fitting 5D function |
| **3D Gaussian Splatting** (2023) | N photos | 3D Gaussian ellipsoids | 100x faster than NeRF, real-time |
| **Monocular Depth** | 1 photo | Depth map | Learn visual priors at scale |
| **Generative 3D** | Text/image | 3D model | Diffusion + multi-view reconstruction |

---

## Running on Azure

| Item | Value |
|------|-------|
| VM | Azure 1a10vm (Standard_NV6ads_A10_v5) |
| GPU | NVIDIA A10-24Q (vGPU, Ampere, Compute 8.6) |
| Driver | 550.144.06 |
| OS | Ubuntu 22.04.5 LTS |
| Location | Canada Central |

**Reproduce**:

```bash
pip install numpy Pillow scikit-image

# E1: Software rasterizer
python3 scripts/e1_software_rasterizer.py --width 640 --height 480

# E2: Ray tracer (showcase)
python3 scripts/e2_ray_tracer.py --width 320 --height 240 --scene showcase --max-depth 3

# E3: Pixel-level comparison
python3 scripts/e3_compare_results.py \
  --img1 results/e1_rasterizer/e1_final_render.png \
  --img2 results/e2_raytracer/e2_match_e1_render.png
```

---

## Sources

| Content | Source |
|---------|--------|
| Graphics Pipeline | Wikipedia [Graphics Pipeline](https://en.wikipedia.org/wiki/Graphics_pipeline) |
| Rasterization Algorithm | [Scratchapixel](https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/overview-rasterization-algorithm.html) (CC BY-NC-ND 4.0) |
| Ray Tracing | Wikipedia [Ray Tracing](https://en.wikipedia.org/wiki/Ray_tracing_(graphics)) |
| DLSS | [NVIDIA DLSS](https://www.nvidia.com/en-us/geforce/technologies/dlss/) |
| RT Core | [NVIDIA Turing In-Depth](https://developer.nvidia.com/blog/nvidia-turing-architecture-in-depth/) |
| Rendering × AI analogies | Author's reasoning (marked "speculative") |
