# Qwen-Image-Edit-2511 虚拟试穿 Inference Benchmark（推理基准测试）

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch 2.5+](https://img.shields.io/badge/pytorch-2.5+-red.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

在 NVIDIA H100 GPU 上对 **Qwen-Image-Edit-2511** 虚拟试穿模型进行的推理引擎对比基准测试，实现最高 **6.8 倍加速**，附质量分析。


## 在 Azure 上运行

本项目的所有实验均在 **Azure GPU 虚拟机**上完成。

| 项目 | 详情 |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **框架** | vLLM, SGLang, TensorRT-LLM, torch.compile, Diffusers |


## 核心结果

| 引擎 | 耗时 | vs 基线 | 加速比 | 质量 | 状态 |
|------|------|---------|--------|------|------|
| diffusers 基线 (无 CFG) | **70.31s** | - | 1.0x | ✅ 参考 | 基线 |
| diffusers 基线 (有 CFG=4.0) | 142.47s | +102.6% | 0.49x | ✅ 参考 | CFG 启用 |
| diffusers + torch.compile | 73.74s | -16.8% | **1.2x** | ✅ 一致 | ✅ 稳定 |
| SGLang | 67.81s | -23.5% | **1.3x** | ✅ 良好 | ✅ 稳定 |
| **vLLM-Omni** | **28.96s** | **-67.3%** | **3.1x** | **✅ 更好** | **✅ 推荐** |
| vLLM-Omni (有 CFG=4.0) | 58.90s | -16.2% | **1.2x** | ✅ 更好 | ✅ CFG 启用 |
| **vLLM-Omni TP=2** | **17.85s** | **-74.6%** | **3.9x** | **✅ 更好** | **✅ 多 GPU** |
| **vLLM-Omni TP=2 + CFG** | **35.59s** | **-49.4%** | **2.0x** | **✅ 更好** | **✅ 多 GPU + CFG** |
| vLLM-Omni + Cache-DiT | 12.99s | -85.3% | **6.8x** | ⚠️ 有损 | ⚠️ 质量折中 |
| ComfyUI-GGUF (Q4) | 115.11s | +29.8% | 0.8x | ✅ 良好 | ⚠️ 缓慢 (仅限边缘端) |

> **核心发现**: vLLM-Omni 实现 **3.1 倍加速**，同时保持或提升输出质量。Cache-DiT 可实现 **6.8 倍加速**，但有可见的质量下降。

## 目录

- [技术背景](#技术背景)
- [可视化对比](#可视化对比)
- [FlashAttention-3 基准测试](#flashattention-3-fa3-attention-backend-基准测试)
- [三层优化框架](#三层优化框架)
- [为什么 vLLM-Omni 能快 3.1 倍](#为什么-vllm-omni-能快-31-倍)
- [关键发现](#关键发现)
- [我们尝试过的方案（及失败原因）](#我们尝试过的方案及失败原因)
- [快速开始](#快速开始)
- [运行日志示例](#运行日志示例)
- [基准测试方法论](#基准测试方法论)


## 技术背景

> 本节为刚接触扩散模型和推理优化的读者解释核心概念。

### 什么是 Diffusers？

**Diffusers** 是 HuggingFace 的开源扩散模型库——Stable Diffusion、DALL-E、Midjourney 等 AI 图像生成技术的基础框架。

```mermaid
flowchart LR
    subgraph Diffusers["🤗 Diffusers 库"]
        A[文本提示词] --> B[文本编码器]
        B --> C[U-Net / DiT]
        C --> D[VAE 解码器]
        D --> E[生成图像]
        
        N[噪声] --> C
        S[调度器] --> C
    end
    
    style Diffusers fill:#fff3e0
```

| 组件 | 作用 | 示例 |
|------|------|------|
| **Pipeline** | 端到端封装 | `QwenImageEditPlusPipeline` |
| **Scheduler (调度器)** | 控制去噪步骤 | DDPM (Denoising Diffusion Probabilistic Models，去噪扩散概率模型)、Euler、DPM++ |
| **U-Net / DiT (Diffusion Transformer，扩散 Transformer)** | 核心神经网络 | Qwen-Image-Edit 使用 DiT |
| **VAE (Variational Autoencoder，变分自编码器)** | 压缩/解压图像 | 潜空间 ↔ 像素空间 |

**为什么 Diffusers 重要**：它是行业标准框架。当我们说"基线"时，指的是直接通过 diffusers 运行模型，不加额外优化。


### ViT vs DiT：理解 vs 生成

在深入优化技术之前，先理解 Qwen-Image-Edit 中两个核心 Transformer 架构：

| | **ViT** | **DiT** |
|---|---------|---------|
| **全称** | Vision Transformer（视觉 Transformer） | Diffusion Transformer（扩散 Transformer） |
| **用途** | 👀 **理解**图像 | 🎨 **生成**图像 |
| **任务方向** | 图像 → 语义 | 语义 → 图像 |
| **在 Qwen-Image-Edit 中的角色** | Qwen2.5-VL（语义编码器） | MMDiT（生成骨干网络） |

**记忆口诀**：
- **V**iT = **V**iew（看）= 理解
- **D**iT = **D**raw（画）= 生成

```mermaid
flowchart TB
    subgraph INPUT["输入处理 ViT 风格"]
        I1["模特图"] --> VL["Qwen2.5-VL"]
        I2["衣服图"] --> VL
        I3["文字提示"] --> VL
        I1 --> VAE["VAE 编码器"]
        I2 --> VAE
    end

    subgraph CORE["MMDiT 核心 DiT 风格"]
        VL --> |"语义特征"| DIT["DiT Transformer 20B"]
        VAE --> |"潜空间 Tokens"| DIT
    end

    subgraph OUTPUT["输出生成"]
        DIT --> |"40步去噪"| DECODE["VAE 解码器"]
        DECODE --> RESULT["换装结果"]
    end

    style INPUT fill:#e3f2fd
    style CORE fill:#fff3e0
    style OUTPUT fill:#c8e6c9
```

**Qwen-Image-Edit 的双编码架构**：

| 组件 | 架构类型 | 功能 |
|------|----------|------|
| **Qwen2.5-VL** | ViT 风格 | 理解"模特长什么样"和"衣服是什么款式" |
| **VAE Encoder** | CNN | 将图像压缩到潜空间 |
| **MMDiT** | DiT（200亿参数） | 通过 Denoising（去噪）生成换装结果 |
| **VAE Decoder** | CNN | 从潜空间重建最终图像 |

**为什么需要 ViT 和 DiT 结合？**

| 只用 ViT | 只用 DiT | **ViT + DiT** |
|----------|----------|---------------|
| 能理解，不能生成 | 能生成，理解能力弱 | ✅ 既能理解又能生成 |
| 无法创建新内容 | 条件控制不够精准 | ✅ 精准的语义控制 |

> **核心洞察**：本 Benchmark 中的优化技术（vLLM-Omni、Cache-DiT、torch.compile）主要针对 **DiT 组件**，因为它占据了约 90% 的推理计算量。


### 什么是 vLLM-Omni？

**vLLM**（Very Large Language Model）是一个高性能推理引擎，最初为大语言模型设计。**vLLM-Omni** 扩展了它以支持**扩散模型**（图像生成）。

```mermaid
flowchart TB
    subgraph VLLM["vLLM-Omni"]
        direction TB
        R[请求队列] --> S[异步调度器]
        S --> P[PagedAttention]
        P --> C[编译后模型]
        C --> G[CUDA Graphs]
        G --> O[输出]
    end
    
    subgraph Benefits["核心优势"]
        B1[3倍+ 加速]
        B2[生产就绪]
        B3[支持批处理]
    end
    
    VLLM --> Benefits
    
    style VLLM fill:#e3f2fd
    style Benefits fill:#c8e6c9
```

| 特性 | 作用 | 加速贡献 |
|------|------|----------|
| **PagedAttention (分页注意力)** | 高效的 KV (Key-Value，键值对) 缓存内存管理 | ~10% |
| **CUDA Graphs (CUDA 图捕获)** | 捕获整个 GPU 计算，即时重放 | ~25% |
| **异步调度** | CPU/GPU 工作重叠 | ~15% |
| **内置 torch.compile** | 自动内核优化 | ~17% |

**类比**：如果 diffusers 像是从头做每道菜，vLLM-Omni 就像专业厨房——有备菜台、并行烹饪和优化的工作流程。

### 什么是 CFG (Classifier-Free Guidance，无分类器引导)？

**CFG** 控制模型多严格地遵循你的文本提示词，还是自由发挥创意。

```
CFG = 1.0  → 模型忽略提示词，最大创意（通常很随机）
CFG = 4.0  → 平衡（换装推荐值）
CFG = 7.0  → 严格遵循提示词
CFG = 15+ → 过度饱和，出现伪影
```

```mermaid
flowchart LR
    subgraph CFG["CFG 缩放效果"]
        L[低 CFG 1-2] --> |"有创意但随机"| R1[🎨]
        M[中 CFG 3-5] --> |"平衡"| R2[✅]
        H[高 CFG 7+] --> |"严格遵循提示词"| R3[📝]
        VH[超高 15+] --> |"过度饱和"| R4[⚠️]
    end
```

| CFG 值 | 效果 | 使用场景 |
|--------|------|----------|
| 1.0 | 纯模型创意 | 艺术探索 |
| **4.0** | **平衡** | **虚拟换装（推荐）** |
| 7.0 | 强提示词遵循 | 文生图 |
| 15.0+ | 过度处理 | 很少有用 |

**代码示例**：
```python
# 对于 Qwen-Image-Edit，使用 true_cfg_scale（而非 guidance_scale）
pipe(..., true_cfg_scale=4.0)
```

### 什么是 Inference Steps（推理步数）？

**Steps** = 去噪迭代次数。步数越多 = 图像越清晰，但速度越慢。

```mermaid
flowchart LR
    N[纯噪声] --> S1[第 1 步]
    S1 --> S2[第 10 步]
    S2 --> S3[第 20 步]
    S3 --> S4[第 40 步]
    S4 --> I[最终图像]
    
    style N fill:#ffcdd2
    style I fill:#c8e6c9
```

| 步数 | 质量 | 速度 | 建议 |
|------|------|------|------|
| 10 | ❌ 模糊、有伪影 | ⚡ 非常快 | 不推荐 |
| 20 | ⚠️ 可接受 | ⚡ 快 | 快速预览 |
| **40** | **✅ 质量好** | **标准** | **生产使用** |
| 50 | ✅ 略好一点 | 较慢 | 收益递减 |
| 100 | ✅ 边际改善 | ❌ 非常慢 | 过度 |

**关键洞察**：质量提升在约 40 步后递减。从 40→100 步时间翻倍，但质量几乎没有提升。

**代码示例**：
```python
pipe(..., num_inference_steps=40)
```

### 什么是 Cache-DiT？

**Cache-DiT** 是一种优化技术，通过缓存中间结果来**跳过扩散 Transformer 中的冗余计算**。

```mermaid
flowchart TB
    subgraph Normal["普通 DiT（40 步）"]
        N1[第 1 步：完整计算] --> N2[第 2 步：完整计算]
        N2 --> N3[第 3 步：完整计算]
        N3 --> N4[...]
        N4 --> N40[第 40 步：完整计算]
    end
    
    subgraph Cached["Cache-DiT（40 步）"]
        C1[第 1-4 步：完整计算] --> C2[第 5+ 步：复用缓存]
        C2 --> C3[跳过相似块]
        C3 --> C40[快得多！]
    end
    
    Normal --> |"88秒"| R1[结果]
    Cached --> |"13秒 ⚡"| R2[结果]
    
    style Cached fill:#c8e6c9
    style Normal fill:#fff3e0
```

| 方面 | 无 Cache-DiT | 有 Cache-DiT |
|------|--------------|--------------|
| 速度 | 28.96秒 | **12.99秒**（快 2.2 倍）|
| 质量 | ✅ 完整质量 | ⚠️ 轻微下降 |
| 细节 | ✅ 清晰 | ⚠️ 可能较柔和 |

**权衡**：Cache-DiT 提供 **6.8 倍总加速**（相对基线），但有可见的质量损失。当速度比完美更重要时使用。

**参数配置**：
```python
# Cache-DiT 配置
cache_config = {
    "max_warmup_steps": 4,           # 前 N 步完整计算
    "residual_diff_threshold": 0.24  # 变化 < 阈值时跳过块
}
```

### 什么是 torch.compile？

**torch.compile** 是 PyTorch 2.0+ 内置的优化功能，可自动加速模型。

```mermaid
flowchart TB
    subgraph Compile["torch.compile 层次"]
        L1["第 1 层：TorchDynamo<br/>捕获 Python → 计算图"]
        L2["第 2 层：TorchInductor<br/>优化操作"]
        L3["第 3 层：CUDA Graphs<br/>批量 GPU 调用"]
        
        L1 --> L2 --> L3
    end
    
    E[Eager 模式<br/>88.67秒] --> Compile
    Compile --> F[编译后<br/>73.74秒]
    
    style Compile fill:#e3f2fd
```

| 模式 | 加速 | 稳定性 | 说明 |
|------|------|--------|------|
| `default` | 1.2x | ✅ 稳定 | **推荐** |
| `reduce-overhead` | 1.3x | ⚠️ 可能 OOM (Out of Memory，内存不足) | 需要更多 VRAM (Video RAM，显存) |
| `max-autotune` | 1.3x | ⚠️ 首次慢 | 编译时间长 |

**代码示例**：
```python
pipe.transformer = torch.compile(pipe.transformer, mode="default")
```

### 综合运用

以下是所有组件如何协同工作：

```mermaid
flowchart TB
    subgraph Input["📥 输入"]
        I1[模特图像]
        I2[服装图像]
        I3[文本提示词]
    end
    
    subgraph Engine["🔧 推理引擎"]
        E1[diffusers<br/>基线]
        E2[torch.compile<br/>快 1.2 倍]
        E3[vLLM-Omni<br/>快 3.1 倍]
    end
    
    subgraph Params["⚙️ 参数"]
        P1["步数：40"]
        P2["CFG：4.0"]
        P3["种子：42"]
    end
    
    subgraph Optimization["🚀 可选优化"]
        O1[Cache-DiT<br/>+2.2倍但质量↓]
    end
    
    Input --> Engine
    Params --> Engine
    Engine --> O1
    O1 --> Output["📤 输出图像"]
    Engine --> Output
    
    style Engine fill:#e3f2fd
    style Optimization fill:#fff3e0
```

| 你的优先级 | 推荐配置 | 预期速度 |
|------------|----------|----------|
| **质量优先** | diffusers + torch.compile | 73秒（1.2x）|
| **均衡** | vLLM-Omni | 29秒（3.1x）⭐ |
| **速度优先** | vLLM-Omni + Cache-DiT | 13秒（6.8x）|

## 可视化对比	

### 输入图像

<table>
  <tr>
    <td align="center"><b>模特图像</b></td>
    <td align="center"><b>服装图像</b></td>
  </tr>
  <tr>
    <td><img src="images/model_input.jpg" width="300"/></td>
    <td><img src="images/00736_00.jpg" width="300"/></td>
  </tr>
</table>



### 输出对比

<table>
  <tr>
    <td align="center"><b>diffusers 基线</b><br/>(88.67s)</td>
    <td align="center"><b>torch.compile</b><br/>(73.74s, 快 17%)</td>
    <td align="center"><b>vLLM-Omni</b><br/>(28.96s, 快 3.1 倍)</td>
  </tr>
  <tr>
    <td><img src="images/output_baseline.png" width="250"/></td>
    <td><img src="images/output_compile.png" width="250"/></td>
    <td><img src="images/output_compile.png" width="250"/></td>
  </tr>
</table>


<table>
  <tr>
    <td align="center"><b>SGLang</b><br/>(67.81s)</td>
    <td align="center"><b>vLLM-Omni + Cache-DiT</b><br/>(12.99s, 快 6.8 倍) ⚠️ 质量损失</td>
  </tr>
  <tr>
    <td><img src="images/output_sglang.png" width="250"/></td>
    <td><img src="images/output_vllm_cache_dit.png" width="250"/></td>
  </tr>
</table>


### CFG 模式对比

> CFG (Classifier-Free Guidance，无分类器引导) 会使计算量翻倍，但可以提升输出质量。
>
> **Attention Backend 对比**：FlashInfer 0.5.3 与 FlashAttention 2.8.3 性能**完全一致**（差异 <0.5%）。**新增**：FA3 相比 SDPA 提供 **27% 加速**。详见 [FA3 基准测试](#flashattention-3-fa3-attention-backend-基准测试)。




### FlashAttention-3 (FA3) Attention Backend Benchmark（基准测试）

> **新发现 (2026-02-03)**：在 H100 上使用 FA3 注意力后端相比 PyTorch SDPA 提供 **27% 的加速**。

| Backend | 时间 | vs FA3 | 说明 |
|---------|------|--------|------|
| **FA3** | **29.68s** | - | ✅ 默认，推荐 |
| TORCH_SDPA | 37.65s | 慢 27% | PyTorch 原生 SDPA |

**图像质量**：PSNR **45.38 dB**（视觉上完全相同）。

<table>
  <tr>
    <td align="center"><b>FA3</b><br/>(平均 29.68s)</td>
    <td align="center"><b>TORCH_SDPA</b><br/>(平均 37.65s，慢 27%)</td>
  </tr>
  <tr>
    <td><img src="images/output_fa3.png" width="300"/></td>
    <td><img src="images/output_sdpa.png" width="300"/></td>
  </tr>
</table>

### 张量并行 (TP=2) 性能

> 使用 2× H100 NVL GPU 进行张量并行，进一步加速。


| 配置 | 耗时 | vs TP=1 | vs diffusers | 说明 |
|------|------|---------|--------------|------|
| vLLM TP=1 无 CFG | 28.98s | - | 2.43x | 单 GPU 基线 |
| **vLLM TP=2 无 CFG** | **17.85s** | **1.62x** | **3.94x** | 2× H100 NVL |
| vLLM TP=1 有 CFG | 58.90s | - | 2.42x | 单 GPU 启用 CFG |
| **vLLM TP=2 有 CFG** | **35.59s** | **1.65x** | **4.00x** | 2× H100 NVL 启用 CFG |

**关键发现**：张量并行相比单 GPU vLLM-Omni 提供约 **1.6 倍额外加速**，相比 diffusers 基线实现近 **4 倍加速**。

## 三层优化框架

现代推理引擎在三个不同层级进行优化：

```mermaid
flowchart TB
    subgraph L3["第三层: CUDA Graphs"]
        G1[记录 Kernel 序列]
        G2[单次启动执行所有]
        G3[消除启动开销]
    end
    
    subgraph L2["第二层: TorchInductor"]
        I1[Kernel 融合]
        I2[内存布局优化]
        I3[Triton 代码生成]
    end
    
    subgraph L1["第一层: TorchDynamo"]
        D1[Python 字节码拦截]
        D2[计算图提取]
        D3[消除解释器开销]
    end
    
    subgraph BASE["基线: Eager 模式"]
        E1[Python 解释器]
        E2[单独 Kernel 启动]
        E3[无优化]
    end
    
    BASE --> L1 --> L2 --> L3
    
    style L3 fill:#4caf50,color:#fff
    style L2 fill:#2196f3,color:#fff
    style L1 fill:#ff9800,color:#fff
    style BASE fill:#9e9e9e,color:#fff
```

### 逐层加速分析

| 层级 | 技术 | 优化目标 | 加速比 | 累计耗时 |
|------|------|----------|--------|----------|
| 基线 | Eager 模式 | - | 1.0x | 88.67s |
| 第一层 | TorchDynamo | Python 解释器 | 1.05x | 84.4s |
| 第二层 | TorchInductor | 内存带宽 | 1.12x | 75.4s |
| 第三层 | CUDA Graphs | Kernel 启动 | 1.30x | 58.0s |
| + vLLM | Async + PagedAttn | 调度 | 2.0x | 29.0s |

## 为什么 vLLM-Omni 能快 3.1 倍

vLLM-Omni 通过编译器优化（torch.compile）、CUDA Graphs 执行、PagedAttention 显存管理和异步调度的组合实现 3.1 倍加速。多种优化技术共同贡献了整体加速效果。结果因模型和硬件配置而异。

> **说明 (2026-02-03)**：vLLM V1 **默认启用 `torch.compile`**（`optimization_level=O2`）。无需手动配置。

## 关键发现

### ⚠️ 发现 0：CFG 在低步数下 ROI 极差

> **🆕 Stage-12 实验验证（2026-03-01）：H100 上 4/8/20/40 步 × CFG=1/4 完整矩阵测试**

使用 LoRA 融合模型（40 步 + CFG=4 输出作为参考基准，SSIM=1.0）：

| 步数 | CFG=1 SSIM | CFG=4 SSIM | CFG 增益 | CFG=1 耗时 | CFG=4 耗时 | 时间倍数 |
|:----:|:----------:|:----------:|:--------:|:----------:|:----------:|:--------:|
| 4 | 0.662 | 0.670 | **+0.008** | 4.28s | 8.08s | 1.89× |
| 8 | 0.788 | 0.804 | **+0.016** | 7.97s | 15.44s | 1.94× |
| 20 | 0.859 | 0.913 | **+0.054** | 19.01s | 37.58s | 1.98× |
| 40 | 0.902 | 1.000 | **+0.098** | 37.46s | 74.47s | 1.99× |

**核心结论**：
- **CFG 恒定增加 ~2× 时间**（conditional + unconditional 双前向传播）
- **低步数（4/8 步）CFG 增益可忽略**：8 步仅 +0.016 SSIM
- **同等时间预算下，加步数远优于加 CFG**：4→8 步 SSIM +0.126 vs 4 步开 CFG 仅 +0.008，**步数增益是 CFG 增益的 15.75 倍**
- **物理原因**：低步数时每步幅度大，引导信号累积不足；CFG 效果在 20 步以上才显现

![CFG 与步数对比网格](images/cfg_batch_comparison_grid.png)

#### diffusers Batch 吞吐量完全扁平

| Batch Size | 总时间 | 吞吐量 (img/s) | vs B=1 |
|:----------:|:------:|:--------------:|:------:|
| 1 | 7.97s | 0.1254 | 1.00× |
| 2 | 15.93s | 0.1256 | 1.00× |
| 4 | 31.90s | 0.1254 | 1.00× |

diffusers 管线级 batch 为纯串行循环，batch=4 时间 = batch=1 × 4。提升吞吐需引擎级优化（如 continuous batching）。

### ⚠️ 发现 0b：CFG 参数陷阱 - `guidance_scale` 被忽略！

**这是使用 Qwen-Image-Edit-2511 时最常见的坑！**

| 参数 | 效果 | 时间影响 |
|------|------|----------|
| `guidance_scale=4.0` | ❌ **被忽略** - 不起作用！ | 无 |
| 只设 `true_cfg_scale=4.0` | ❌ 仍无效（会显示警告） | 无 |
| `negative_prompt=" "` + `true_cfg_scale=4.0` | ✅ **CFG 生效** | **慢 2 倍** |

**根本原因**：Qwen-Image-Edit-2511 **不是 guidance-distilled 模型**。`guidance_scale` 参数被 pipeline 静默忽略。

**实测验证 (H100, 40 步, 1340×1785 分辨率)**：

| 模式 | 配置 | 耗时 | 说明 |
|------|------|------|------|
| **无 CFG** | 不设 `negative_prompt`，不设 `true_cfg_scale` | **70.31s** | 单次前向传播 |
| **有 CFG** | `negative_prompt=" "` + `true_cfg_scale=4.0` | **142.47s** | 2 倍时间（符合预期）|

**代码示例**：
```python
# ❌ 错误 - guidance_scale 不起作用：
result = pipe(prompt=prompt, image=images, guidance_scale=4.0)  # 被忽略！

# ✅ 正确 - 无 CFG（最快）：
result = pipe(prompt=prompt, image=images, num_inference_steps=40)

# ✅ 正确 - 有 CFG（慢 2 倍，但可能提升质量）：
result = pipe(
    prompt=prompt,
    image=images, 
    num_inference_steps=40,
    negative_prompt=" ",       # 必须！触发 CFG 模式
    true_cfg_scale=4.0         # 现在 CFG 才真正生效
)
```

> **血泪教训**：如果你的 Benchmark 显示 CFG=4.0 和 CFG=1.0 耗时一样，**说明你的 CFG 根本没生效**！

### ⚠️ 发现 1: torch.compile dynamic=True 的 NaN Bug

使用 `torch.compile(mode="reduce-overhead", dynamic=True)` 时，输出图像会被 NaN 值损坏。

| 配置 | 结果 | 状态 |
|------|------|------|
| `dynamic=True` | NaN 损坏 | ❌ **禁止使用** |
| `dynamic=None` | 正常工作 | ✅ 推荐 |

**根因**: TorchInductor 在动态形状下处理 complex64 数据类型的 bug。

### ⚠️ 发现 2: Cache-DiT 质量下降

Cache-DiT 实现 6.8 倍加速，但有**可见的质量损失**：

| 方面 | 无 Cache-DiT | 有 Cache-DiT |
|------|--------------|--------------|
| 细节 | ✅ 清晰 | ⚠️ 略微模糊 |
| 颜色准确度 | ✅ 准确 | ⚠️ 轻微偏移 |
| 边缘质量 | ✅ 干净 | ⚠️ 有伪影 |

**建议**: 仅在速度至关重要且可接受一定质量损失时使用 Cache-DiT。

### ⚠️ 发现 3: diffusers 版本很重要

| 版本 | 性能 | 脸部质量 | 状态 |
|------|------|----------|------|
| 0.35.2 | ❌ 报错 | N/A | Token 不匹配 |
| 0.36.0 | ✅ 快 | ❌ 美颜滤镜 bug | 不推荐 |
| 0.37.0.dev0 (原版) | ❌ 慢 55% | ✅ 正常 | 性能回退 |
| **PR #12987** | ✅ 快 | ✅ 正常 | **推荐** |

**根因**：注意力 mask 处理的回退导致某些 diffusers 版本出现性能下降。

### ⚠️ 发现 4: 提示词工程保持细节一致性

vLLM-Omni 的加速可能导致**脚部位置和鞋子**等细节发生意外变化。通过精心设计的提示词可以缓解此问题。

| 提示词类型 | 耗时 | 脚/鞋 |
|------------|------|-------|
| 简单提示词 | 28.34s | ❌ 位置改变 |
| **优化提示词** | **28.22s** | **✅ 保持一致** |

**优化提示词模板:**

```
Replace the clothing on the model in image 1 with the garment shown in image 2.
Requirements: Keep model pose, feet position, shoes exactly same. Maintain lighting, shadows, fine details.
Avoid: Changed feet position, swapped legs, different shoes, blurry output.
```

**关键洞察**: 在正向提示词中明确包含 "Avoid" 语句（而不是使用 negative_prompt 参数），可以有效引导模型保持细节，同时保持 3.1 倍加速。

![完整对比](images/full_comparison.png)

### ⚠️ 发现 5: 服装细节保留（肩带、蝴蝶结、纽扣）

扩散模型可能无法保留服装上的小而重要的细节，如**肩带装饰（蝴蝶结、金属扣、纽扣）**。这是所有推理引擎面临的共同挑战。

**✅ 关键成果**: 通过提示词工程，我们**在保持 vLLM-Omni 3.1 倍加速的同时保留了服装细节**。无需在质量和速度之间妥协！

| 细节类型 | 默认行为 | 优化提示词后 |
|----------|----------|--------------|
| 肩带蝴蝶结 | ❌ 经常丢失 | ✅ 保留 |
| 金属扣 | ❌ 可能消失 | ✅ 保留 |
| 纽扣数量 | ❌ 可能改变 | ✅ 精确数量 |
| 肩带图案 | ❌ 被简化 | ✅ 保持原样 |

**效果展示 - vLLM-Omni 保留蝴蝶结 (28.96秒):**

<img src="images/bow_preserved_vllm_omni.png" width="800"/>

*左: 模特输入 | 中: 带肩带蝴蝶结的服装 | 右: vLLM-Omni 输出，蝴蝶结完整保留 ✅*

**服装细节优化提示词模板:**

```
Replace clothing on the model with the garment shown.
CRITICAL - Preserve garment details exactly:
- The garment has a BOW/RIBBON on the shoulder strap - KEEP IT exactly as shown
- Shoulder strap is PLAIN BLACK with NO additional decorations - DO NOT add beads or pearls
- Count and preserve ALL buttons exactly as shown in garment image
Requirements: Maintain exact garment details, preserve model pose and face.
```

**关键技巧:**

| 技巧 | 用途 | 示例 |
|------|------|------|
| **明确提及** | 告诉模型什么存在 | "has a BOW on shoulder strap" |
| **负向引导** | 告诉模型不要添加什么 | "DO NOT add beads or pearls" |
| **计数** | 确保数量准确 | "preserve ALL 8 buttons" |

**根因**：去噪过程中小细节可能丢失。明确的提示词有助于保留它们。

![images](./images/vllm_omni_comparison.png)

## 我们尝试过的方案（及失败原因）

### ❌ FP8 量化

| 方案 | 结果 | 原因 |
|------|------|------|
| torchao float8_weight_only | 慢 69% | 量化开销 > 计算节省 |
| torchao float8_dynamic | 慢 7% | 动态 scale 计算开销 |
| transformer_engine fp8_autocast | 无效果 | 仅对 TE 原生层有效 |

**结论**: FP8 不适用于 diffusers + Qwen-Image-Edit 组合。

### ❌ torch.compile reduce-overhead 模式

| 问题 | 影响 |
|------|------|
| 20B 模型 OOM | CUDA Graphs 需要额外显存捕获计算图 |
| @lru_cache 不兼容 | MSRoPE (Multi-Scale Rotary Position Embedding，多尺度旋转位置编码) 位置编码破坏了图捕获 |

### ❌ GGUF 量化 (ComfyUI)

| 引擎 | 格式 | 耗时 | vs vLLM | 显存 |
|------|------|------|---------|------|
| vLLM-Omni | BF16 | **28.96s** | 基准 | ~32GB |
| ComfyUI-GGUF | Q4_K_M | 115.11s | **慢 4 倍** | ~12GB |

**根因**：在 H100 等高带宽 GPU 上，反量化开销超过了内存节省，使 GGUF 比原生 BF16 更慢。

**NVFP4 硬件支持缺口**

我们调研了 NVIDIA Blackwell 的 **NVFP4** 能否解决这个问题：

| 格式 | 支持情况 | 硬件加速 |
|------|----------|----------|
| MXFP4 (Block Scaling) | ✅ llama.cpp 支持 | ❌ 纯软件实现 |
| **NVFP4** | ❌ llama.cpp 不支持 | ✅ 需要 TensorRT-LLM/vLLM |

**部署场景推荐**

| 场景 | 推荐方案 | 原因 |
|------|----------|------|
| **数据中心 (H100/A100)** | vLLM/SGLang (BF16/FP8) | 最大化算力；显存不是约束 |
| **消费级 GPU (4090/3090)** | AutoGPTQ/AWQ | 平衡显存与速度 |
| **边缘端 (MacBook/低显存)** | GGUF | 唯一能塞下模型的方案；速度是次要的 |

**结论**：GGUF 非常适合显存受限的边缘设备，但在高端数据中心 GPU 上会引入巨大的性能开销。

### ❌ SGLang 默认配置

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 比基线慢 14.8% | 默认启用 CPU offload | 在 H100 上禁用 offload |

## 快速开始

### 前置要求

- NVIDIA H100/A100 GPU，80GB+ 显存
- CUDA 12.4+
- Python 3.10+

### 安装

```bash
# 克隆仓库
git clone https://github.com/xinyuwei-david/Qwen-Virtual-TryOn-Inference-Benchmark.git
cd Qwen-Virtual-TryOn-Inference-Benchmark

# 创建环境
conda create -n tryon-bench python=3.10 -y
conda activate tryon-bench

# 安装依赖（使用 PR #12987 获得最佳性能）
pip install git+https://github.com/kashif/diffusers.git@fix-reg
pip install torch>=2.5.0 transformers accelerate Pillow
```

### 运行基准测试

```bash
cd benchmarks
bash run_all.sh
```

## 运行日志示例

### diffusers 基线

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
  - max_warmup_steps: 4
  - residual_diff_threshold: 0.24
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


### vLLM-Omni TP=2 (张量并行)

```
============================================================
vLLM-Omni TP=2 Benchmark - NO CFG
============================================================
vllm-omni: 0.14.0rc1
GPU 0: NVIDIA H100 NVL
GPU 1: NVIDIA H100 NVL
Model: Qwen/Qwen-Image-Edit-2511
Steps: 40, Seed: 1, TP: 2, CFG: DISABLED
------------------------------------------------------------
Garment: (1340, 1785), Model: (1340, 1785)

Loading vLLM-Omni with TP=2...
Loaded in 45.2s

Warmup: 2 runs
  Warmup 1: 18.12s
  Warmup 2: 17.89s

Benchmark: 5 runs
  Run 1: 17.63s
  Run 2: 17.74s
  Run 3: 17.82s
  Run 4: 17.98s
  Run 5: 18.11s

Saved: output_vllm_tp2_nocfg.png (896x1184)

============================================================
All runs: [17.63, 17.74, 17.82, 17.98, 18.11]
Trimmed (drop min/max): [17.74, 17.82, 17.98]
RESULT (TP=2, NO CFG): 17.85s ± 0.100s
Speedup vs TP=1 (28.98s): 1.62x
Speedup vs diffusers (70.31s): 3.94x 🚀
============================================================
```

## 基准测试方法论

### 测试参数（7 维对齐）

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | Qwen/Qwen-Image-Edit-2511 | 所有测试使用相同模型 |
| 步数 | 40 | 去噪步数 |
| CFG Scale | 4.0 | true_cfg_scale（非 guidance_scale） |
| Seed | 42 | 保证可复现 |
| 分辨率 | 576×1024 | 竖版模式 |
| dtype | bfloat16 | H100 优化 |
| 硬件 | H100 NVL 96GB | 所有测试使用相同 GPU |

### 测量协议

1. **预热**: 5 次运行（不计入计时）
2. **计时运行**: 5 次
3. **报告**: 均值 ± 标准差
4. **质量验证**: 所有输出的视觉检查

### 硬件环境

| 组件 | 规格 |
|------|------|
| GPU | NVIDIA H100 NVL 96GB |
| CPU | Intel Xeon Platinum |
| 内存 | 256GB DDR5 |
| 存储 | NVMe SSD |
| CUDA | 12.4 |
| 驱动 | 560.x |

## 仓库结构

```
Qwen-Virtual-TryOn-Inference-Benchmark/
├── README.md                 # 英文文档
├── README-CN.md              # 中文文档（本文件）
├── requirements.txt          # 依赖
├── LICENSE                   # MIT 许可证
├── benchmarks/               # 示例代码（精简版）
│   ├── diffusers_baseline.py # diffusers 基线示例
│   ├── diffusers_compile.py  # torch.compile 示例
│   ├── vllm_omni_baseline.py # vLLM-Omni 示例
│   └── sglang_test.py        # SGLang 示例
└── images/
    ├── model_input.jpg       # 测试模特图 (576x1024)
    ├── garment.jpg           # 测试服装图 (1340x1785)
    └── output_*.png          # 基准测试输出
```

## 相关工作

- [torch-compile-tryon](https://github.com/xinyuwei-david/Deep-Learning/tree/main/torch-compile-tryon) - 我们的 torch.compile 优化研究
- [vLLM-Omni](https://github.com/vllm-project/vllm) - 统一推理引擎
- [SGLang](https://github.com/sgl-project/sglang) - 快速 LLM 服务框架
- [diffusers PR #12987](https://github.com/huggingface/diffusers/pull/12987) - Qwen-Image-Edit 性能修复

## 作者

**魏新宇 (Xinyu Wei)**

- GitHub: [@xinyuwei-david](https://github.com/xinyuwei-david)
- 职位: Microsoft AI and Apps Global Black Belt (GBB) Senior System Engineer

## 许可证

MIT License - 详见 [LICENSE](LICENSE)。
