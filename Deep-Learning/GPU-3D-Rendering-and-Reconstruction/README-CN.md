# GPU 架构深潜：从 3D 渲染起源到 AI 推理加速

> **作者**: 魏新宇 (Xinyu Wei)
>
> **核心命题**: GPU 为 3D 渲染而生，AI 推理是"意外的受益者"。**理解渲染的设计哲学，就理解了 GPU 为什么天生适合 AI — 以及如何更好地利用它。**
>
> **独到视角**: 本文用作者在 LLM/Diffusion 推理优化领域的实测数据，验证渲染技术与 AI 推理优化之间的深层关联 — 不是推测，是工程证据。

---

## Executive Summary

每个 AI 推理工程师都在用 GPU，但很少有人思考：**GPU 为什么被设计成现在这样？** 答案藏在 GPU 的出生证——3D 渲染中。

| 渲染中的设计决策 | 对应的 AI 推理优化 | 作者实测证据 |
|:---|:---|:---|
| 分块渲染（Tiled Rendering） | FlashAttention 分块计算 | FlashInfer 在 32K 时比 FA 快 9-15%（[FlashInfer-vs-FA-Benchmark](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/FlashInfer-vs-FlashAttention-Benchmark)） |
| Z-Buffer 逐像素内存管理 | PagedAttention 逐块 KV Cache | KV Cache 六级深潜（[KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive)） |
| Mipmap 多精度 LOD | Speculative Decoding 草稿验证 | EAGLE3 加速 2.67x（[EAGLE3](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Speculative-Decoding-EAGLE3)） |
| Z-fighting 16-bit 闪烁 | BF16 精度累积误差 | fuse_lora SSIM 差 2-18%（[LoRA-Merge](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)） |
| 帧缓冲复用上一帧 | KV Cache 缓存 Key/Value | GQA/MLA 四架构对比（[KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive)） |
| 光追 Monte Carlo 降噪 | Diffusion DDPM 去噪 | 蒸馏 40步→8步（[Diffusion-Distillation](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Diffusion-Distillation)） |

---

## 1. 渲染问题：为什么 3D 要变成 2D？

**因为显示器是 2D 的。** 3D 场景必须被"压"成 2D 像素矩阵。

| 方法 | 思路 | GPU 硬件 |
|:---|:---|:---|
| **光栅化** | 每个三角形问："我覆盖了哪些像素？" | CUDA Core + 固定功能 Rasterizer |
| **光线追踪** | 每个像素问："我看到了什么物体？" | RT Core（BVH 遍历 + Ray-Triangle 求交） |

**为什么三角形？** 任意 3 点必然共面，4 点不一定 — 三角形是最简单的保证平面性的图元。

---

## 2. 图形管线 5 步

3D→2D 的核心是 **5 次 4×4 矩阵乘法**：

```
模型坐标 → [Model Transform] → 世界坐标 → [Camera Transform] → 摄像机坐标
→ [Projection] → NDC → [Clipping] → [Viewport] → 屏幕像素
```

| 步骤 | 做什么 | 为什么 |
|:---|:---|:---|
| **Model Transform** | 放置物体（旋转+平移+缩放） | 4×4 矩阵统一所有变换（3×3 不能做平移） |
| **Camera Transform** | 摄像机移到原点 | LookAt 矩阵，叉积构建正交基 |
| **Projection** | 近大远小 | 透视投影：除以 z 深度，视锥体→NDC |
| **Clipping** | 丢弃不可见部分 | NDC 空间裁剪比原始空间简单 |
| **Viewport** | NDC→像素 | [-1,1] → [0,Width]×[0,Height] |

**关键洞察**: 5 步全是矩阵乘法，可预乘为一个矩阵。**这就是 GPU 存在的原因：大规模并行矩阵运算。**

---

## 3. 光栅化 vs 光线追踪

| 效果 | 光栅化 | 光追 |
|:---|:---|:---|
| 反射 | Cube Map 近似 | 递归反射光线（物理正确） |
| 阴影 | Shadow Map 近似 | 阴影光线遮挡测试 |
| 折射 | 屏幕空间扭曲 | Snell's Law + 折射光线 |
| 全局光照 | 预烘焙 Light Probe | Path Tracing Monte Carlo |
| 速度 | 快（实时 60-240fps） | 慢 1-2 个数量级 |

### 渲染效果实测对比

**E1 软件光栅化器**（14 三角形立方体，Edge Function + Z-Buffer + Lambert 着色）：

![E1 光栅化渲染](images/e1_final_render.png)

**E2 软件光线追踪器**（反射球 + 阴影 + 多光源，递归深度 3）：

![E2 光追展示](images/e2_showcase_render.png)

**E3 同一场景像素级对比**（左：光栅化 | 中：光追 | 右：差异热力图，蓝=相似，红=差异大）：

![E3 对比](images/e3_comparison.png)

> 差异集中在**阴影区域**（38% 像素有大差异）— 这正是光追的物理真实性优势所在。

**E4 Blender EEVEE（光栅化）**：

![E4 EEVEE](images/e4_eevee_640.png)

实验脚本和完整数据见 [scripts/](scripts/) 目录。

来源：[Scratchapixel](https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/overview-rasterization-algorithm.html) (CC BY-NC-ND 4.0)、Wikipedia [Ray Tracing](https://en.wikipedia.org/wiki/Ray_tracing_(graphics))

---

## 4. GPU 架构演进

```
1990s   固定管线 — 硬件只能做预定义渲染步骤
2001    可编程 Shader (GeForce 3)
2006    统一着色器 (GeForce 8) — CUDA 诞生 → AI 的起点
2017    Tensor Core (Volta V100) — 矩阵乘法硬件加速
2018    RT Core (Turing RTX 20) — 实时光追
2020    3rd gen Tensor Core (A100) — TF32/BF16/INT8, 结构化稀疏
2022    4th gen Tensor Core (H100) — FP8, Transformer Engine
2024    5th gen Tensor Core (B200) — FP4
```

**设计模式**: 操作成为瓶颈且模式固定 → **做成专用硬件**。

| 通用 → 可编程 → 专用 | 渲染 | AI |
|:---|:---|:---|
| CPU 通用 | CPU 做渲染 | CPU 做 ML |
| GPU 并行 | CUDA Core Shader | CUDA Core kernel |
| 专用 ASIC | RT Core (BVH) | Tensor Core (GEMM) |

---

## 5. GPU 三种核心

| | CUDA Core | RT Core | Tensor Core |
|:---|:---|:---|:---|
| **功能** | 通用并行计算 | BVH + Ray-Triangle 求交 | 矩阵乘法 (GEMM) |
| **可编程** | ✅ | ❌ 固定功能 | ❌ 固定功能 |
| **渲染** | Shader | 光追加速 | DLSS |
| **AI** | 通用 CUDA | — | 训练推理 |

### 数据中心 vs 游戏 GPU

| GPU | CUDA Core | Tensor Core | RT Core | 定位 |
|:---|:---:|:---:|:---:|:---|
| **H100** SXM | 16,896 | 528 (4th) | ❌ | AI 训练推理 |
| **A100** | 6,912 | 432 (3rd) | ❌ | AI 训练推理 |
| **A10** | 9,216 | 288 (3rd) | ✅ 72 (2nd) | 推理 + 图形 |
| **RTX 4090** | 16,384 | 512 (4th) | ✅ 128 (3rd) | 游戏 + AI |

> **洞察**: 数据中心 GPU（H100/A100）**没有 RT Core** — 纯为 AI 优化。A10 同时有三种 Core，用于 Azure NV 系列（图形+推理混合）。

来源：NVIDIA 官方规格

---

## 6. DLSS：渲染 × AI 的融合

| 版本 | 年份 | 核心技术 |
|:---:|:---:|:---|
| 1.0 | 2019 | 每游戏单独训练 CNN |
| 2.0 | 2020 | 通用时序反馈网络 + 运动向量 + 前帧 |
| 3.0 | 2022 | + 帧生成（AI "凭空"生成中间帧） |
| 4.0 | 2025 | Multi Frame Generation（一次最多 3 帧） |
| 4.5 | 2025 | Dynamic Multi Frame Generation |

来源：[NVIDIA DLSS](https://www.nvidia.com/en-us/geforce/technologies/dlss/)、[DLSS 4.5 Blog](https://developer.nvidia.com/blog/nvidia-dlss-4-5-delivers-super-resolution-upgrades-and-new-dynamic-multi-frame-generation/)

---

## 7. ★ 核心章节：渲染设计 × AI 推理 — 用工程数据验证

> 以下每个类比都有作者**实测数据**支撑。

### 7.1 分块渲染 ↔ FlashAttention

**渲染**: Tiled Rendering 将屏幕分 16×16 块，每块独立处理，避免全局内存瓶颈。

**AI**: FlashAttention 将 Q/K/V 分块在 SRAM 中计算 Softmax，避免 HBM 读写。

**证据**: FlashInfer 在 A100/32K 序列时比 FlashAttention 快 9-15%。来源：[FlashInfer-vs-FlashAttention-Benchmark](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/FlashInfer-vs-FlashAttention-Benchmark)

**共同原理**: IO-aware tiling — 把计算搬到数据旁边，而非把数据搬到计算旁边。

### 7.2 Z-Buffer ↔ PagedAttention

**渲染**: Z-Buffer 逐像素按需写入深度，不预分配整个场景内存。

**AI**: PagedAttention 将 KV Cache 按页分配，不预分配最大序列长度。

**证据**: GQA/MLA/Hybrid Attention/Hybrid Mamba 四种架构 KV Cache 大小差异超过 10 倍。来源：[KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive)

**共同原理**: 内存是稀缺资源，按需分配优于预分配。

### 7.3 Mipmap/LOD ↔ Speculative Decoding

**渲染**: 远处物体用低分辨率纹理（快+省带宽），近处用高分辨率。

**AI**: 小模型快速生成候选 token，大模型一次性验证。

**证据**: EAGLE3 加速 2.67x。来源：[Speculative-Decoding-EAGLE3](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Speculative-Decoding-EAGLE3)

**共同原理**: 先用便宜的近似，再用昂贵的精确验证。

### 7.4 Z-fighting ↔ BF16 精度问题

**渲染**: Z-Buffer 16-bit 精度不够 → 两面闪烁（Z-fighting）。

**AI**: BF16 7-bit 尾数 → fuse_lora 和 set_adapters 在 Diffusion 多步推理中累积不同误差。

**证据**: 蒸馏 8 步 fuse_lora SSIM=1.0 vs set_adapters SSIM=0.88-0.91。来源：[LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)

**共同原理**: 有限精度在累积计算中放大误差，步数越少越敏感。

### 7.5 帧缓冲 ↔ KV Cache

**渲染**: DLSS 利用上一帧 + 运动向量生成高分辨率输出。

**AI**: KV Cache 缓存已算的 Key/Value，生成下一 token 只算新 Q。

**证据**: FP8 KV Cache 量化减少约 50% VRAM。来源：[Qwen3.5-122B-Azure-vs-AWS-Benchmark](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Qwen3.5-122B-Azure-vs-AWS-Benchmark)

**共同原理**: 缓存中间结果，用空间换时间。

### 7.6 光追 Monte Carlo ↔ Diffusion 去噪

**渲染**: Path Tracing 随机采样光路 → 降噪。

**AI**: Diffusion 从纯噪声 → 逐步去噪还原图像。

**证据**: 蒸馏 40 步→8 步（ODE 轨迹蒸馏）。来源：[Diffusion-Distillation](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Diffusion-Distillation)

**共同原理**: 从随机到有序的迭代过程，步数和质量的权衡。

---

## 8. 2D→3D 重建（简要）

| 方法 | 输入 | 核心思想 |
|:---|:---|:---|
| **NeRF** (2020) | N 张照片 | MLP 拟合 5D 辐射场 |
| **3D Gaussian Splatting** (2023) | N 张照片 | 比 NeRF 快 100x，可实时 |
| **单图深度估计** | 1 张照片 | 学习视觉先验 |

来源：Wikipedia [NeRF](https://en.wikipedia.org/wiki/Neural_radiance_field) + [3DGS](https://en.wikipedia.org/wiki/Gaussian_splatting)

---

## Running on Azure

本文是原理解析 + 跨项目交叉引用。第 7 章实测数据来自：

| 项目 | GPU | 链接 |
|:---|:---|:---|
| FlashInfer-vs-FA | A100 80GB | [链接](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/FlashInfer-vs-FlashAttention-Benchmark) |
| KV-Cache-Deep-Dive | 原理分析 | [链接](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive) |
| EAGLE3 | H100 | [链接](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Speculative-Decoding-EAGLE3) |
| LoRA-Merge-Quality | H100 | [链接](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact) |
| Diffusion-Distillation | H100 | [链接](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Diffusion-Distillation) |
| Qwen3.5-122B Benchmark | H100 | [链接](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Qwen3.5-122B-Azure-vs-AWS-Benchmark) |

---

## 来源

| 内容 | 来源 |
|:---|:---|
| 图形管线 | Wikipedia [Graphics Pipeline](https://en.wikipedia.org/wiki/Graphics_pipeline) |
| 光栅化 | [Scratchapixel](https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/overview-rasterization-algorithm.html) (CC BY-NC-ND 4.0) |
| 光线追踪 | Wikipedia [Ray Tracing](https://en.wikipedia.org/wiki/Ray_tracing_(graphics)) |
| DLSS | [NVIDIA DLSS](https://www.nvidia.com/en-us/geforce/technologies/dlss/) |
| RT Core | [NVIDIA Turing In-Depth](https://developer.nvidia.com/blog/nvidia-turing-architecture-in-depth/) |
| GPU 规格 | NVIDIA 官方规格 |
| 渲染×AI 关联 | 作者实测数据（第 7 章来源链接） |
