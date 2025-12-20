# FP8 Validation On 3 GPUs

> 跨 GPU 架构的 FP8 推理性能验证：H100、A100 和 RTX PRO 6000

## 🎯 概述

本测试对比 **H100 原生 FP8 Tensor Core** 与 **A100 Marlin 内核 (weight-only FP8)** 在不同负载模式下的表现。核心发现：**H100 FP8 在 compute-bound 场景下实现 41% 加速，优于 A100 的 29%**。

### 核心结果

| 场景 | H100 FP8 加速 | A100 FP8 加速 | 胜出 |
|------|---------------|---------------|------|
| Memory-bound (单请求 Prefill) | +30% | +54% | A100 |
| **Compute-bound (50 并发)** | **+41%** | +29% | **H100** |
| **H100 强制 Marlin** | **-44%** | N/A | ❌ 比 BF16 更慢 |

---

## 🧠 技术架构

### FP8 实现差异

```
┌──────────────────────────────────────────────────────────────┐
│  H100: 原生 FP8 Tensor Core (W8A8)                           │
│  ┌─────────┐    ┌──────────────┐    ┌─────────┐             │
│  │ 权重    │ -> │ FP8 Tensor   │ -> │ 输出    │             │
│  │ (FP8)   │    │ Core GEMM    │    │ (BF16)  │             │
│  └─────────┘    └──────────────┘    └─────────┘             │
│  ✓ 真正的低精度计算 (W8A8)                                    │
│  ✓ 算力翻倍: FP8 TFLOPS > BF16 TFLOPS                        │
├──────────────────────────────────────────────────────────────┤
│  A100: Marlin 内核 (Weight-Only FP8 动态反量化)               │
│  ┌─────────┐    ┌──────────────┐    ┌─────────┐             │
│  │ 权重    │ -> │ 动态反量化 + │ -> │ 输出    │             │
│  │ (FP8)   │    │ BF16 GEMM    │    │ (BF16)  │             │
│  └─────────┘    └──────────────┘    └─────────┘             │
│  ✓ 仅节省显存带宽，计算仍是 BF16                              │
│  ✗ A100 没有 FP8 Tensor Core 硬件                            │
└──────────────────────────────────────────────────────────────┘
```

### 关键概念: 动态反量化 (Dynamic Dequantization)

**Marlin** 是 IST-DASLab 开发的高性能 CUDA kernel，核心做的是**动态反量化**：

```
存储阶段: FP8 权重 (压缩态，节省显存带宽)
    ↓
运行时: 动态反量化 → BF16 (on-the-fly)
    ↓
计算阶段: BF16 GEMM (不是 FP8 计算!)
```

| 术语 | 含义 | Marlin 的角色 |
|------|------|---------------|
| 动态量化 | 推理时把激活值 高精度→低精度 | ❌ 不是这个 |
| **动态反量化** | 推理时把权重 低精度→高精度 | ✅ 正是这个 |
| Weight-only | 只压缩权重，激活保持高精度 | ✅ 也是这个 |

### 为什么结果不同？

| 瓶颈类型 | H100 优势 | A100 优势 |
|----------|-----------|-----------|
| Memory-bound | - | Marlin 节省 50% 带宽 |
| Compute-bound | 原生 FP8 算力翻倍 | - |

---
## 🔧 FP8 推理深度解析：两类 Backend

### FP8 推理包含三个独立可控组件

```
┌─────────────────────────────────────────────────────────────────┐
│                        FP8 推理流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   Weight    │    │  Activation │    │      KV Cache       │ │
│  │  (模型权重)  │    │ (运行时激活) │    │    (键值缓存)       │ │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘ │
│         │                  │                      │             │
│         ▼                  ▼                      ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ 预量化模型   │    │--quantization│   │ --kv-cache-dtype    │ │
│  │ 或 --dtype  │    │    fp8      │    │    fp8_e5m2         │ │
│  │             │    │  (不推荐!)   │    │   (推荐)            │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

| 组件 | 含义 | 何时确定 | 控制方式 |
|------|------|----------|----------|
| **Weight** | 模型权重精度 | 模型文件 (预量化) | 使用 HuggingFace 上的 FP8 模型 |
| **Activation** | 运行时激活值精度 | 运行时 | `--quantization fp8` (⚠️ 会 OOM!) |
| **KV Cache** | 注意力缓存精度 | 运行时 | `--kv-cache-dtype fp8_e5m2` ✅ |

> ⚠️ **关键教训**：Runtime quantization (`--quantization fp8`) 会导致 OOM 和高错误率。务必使用**预量化 FP8 模型**！

### 两类 Backend：Attention vs GEMM

```
┌────────────────────────────────────────────────────────────────┐
│                    Transformer 层计算流程                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Input ──► [Linear Q/K/V] ──► [Attention] ──► [Linear O] ──► Out
│                 │                  │                │          │
│                 ▼                  ▼                ▼          │
│           ┌─────────┐        ┌─────────┐      ┌─────────┐     │
│           │  GEMM   │        │Attention│      │  GEMM   │     │
│           │ Backend │        │ Backend │      │ Backend │     │
│           └─────────┘        └─────────┘      └─────────┘     │
│                                                                │
│  Weight × Activation       Q × K^T + softmax     Weight × Act │
│  (矩阵乘法)                    + V 检索          (矩阵乘法)    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

| Backend 类型 | 计算内容 | 精度敏感度 | 代表实现 |
|--------------|----------|------------|----------|
| **GEMM Backend** | Weight × Activation | 中 | cuBLAS, CUTLASS |
| **Attention Backend** | Q×K^T, softmax, ×V | 高 | FlashInfer, FlashAttention, Triton |

### SGLang vs vLLM 参数对照表（源码验证）

**SGLang 参数：**

| 组件 | 参数 | 可选值 | 源码位置 |
|------|------|--------|----------|
| Weight | `--dtype` | `auto`, `float16`, `bfloat16`, `float8_e4m3fn` | server_args.py |
| KV Cache | `--kv-cache-dtype` | `auto`, `fp8_e5m2`, `fp8_e4m3` | server_args.py |
| Attention | `--attention-backend` | `flashinfer`, `triton`, `torch_native`, `fa3` | server_args.py |
| GEMM | `--fp8-gemm-backend` | `cutlass`, `cublas` | server_args.py |

**vLLM 参数：**

| 组件 | 参数 | 可选值 | 源码位置 |
|------|------|--------|----------|
| Weight | `--dtype` | `auto`, `float16`, `bfloat16`, `float8_e4m3fn` | engine_args.py |
| KV Cache | `--kv-cache-dtype` | `auto`, `fp8`, `fp8_e5m2`, `fp8_e4m3` | engine_args.py |
| Attention | `VLLM_ATTENTION_BACKEND` (环境变量) | `FLASH_ATTN`, `FLASHINFER`, `XFORMERS`, `TRITON_ATTN` | selector.py |
| 执行模式 | `--enforce-eager` | `True`/`False` | engine_args.py |

### Triton 澄清：OpenAI Triton ≠ NVIDIA Triton！

| 项目 | OpenAI Triton | NVIDIA Triton |
|------|---------------|---------------|
| **类型** | GPU 编程语言 | 推理服务器 |
| **用途** | 写自定义 CUDA kernel | 模型部署和服务 |
| **代码** | `@triton.jit` 装饰器 | Docker 容器 |
| **SGLang 用的是** | ✅ 用于 attention kernel | ❌ |

### 中间计算精度

> **关键发现**：即使输入是 FP8/FP16，**所有 backend 的中间计算都用 FP32**！

源码证据 (from SGLang's `triton_flashinfer_cudnn.py`):
```python
attn_logits = torch.empty(
    (batch_size, head_num_q, num_kv_splits, head_dim + 1),
    dtype=torch.float32,  # ← 强制 FP32 保证数值稳定性
    device="cuda",
)
```

---


## 🚀 快速开始

### 环境要求

| 依赖 | 版本 |
|------|------|
| vLLM | ≥ 0.12.0 |
| CUDA | ≥ 12.0 |
| GPU | H100 或 A100 |

### 运行测试

```bash
# 克隆仓库
git clone https://github.com/xinyuwei/H100-A100-FP8-Benchmark.git
cd H100-A100-FP8-Benchmark

# 启动 vLLM 服务 (BF16 基准)
vllm serve Qwen/Qwen2.5-14B-Instruct --port 8080 --max-model-len 4096

# 运行测试
python benchmark.py --mode prefill   # 单请求 prefill
python benchmark.py --mode decode    # 50 并发 decode

# 重启为 FP8 模式
pkill -f vllm
vllm serve Qwen/Qwen2.5-14B-Instruct --port 8080 --max-model-len 4096 --quantization fp8

# 再次运行测试
python benchmark.py --mode prefill
python benchmark.py --mode decode
```

---

## 📊 详细结果

### 测试环境

| 配置 | H100 | A100 |
|------|------|------|
| GPU 型号 | NVIDIA H100 NVL 96GB | NVIDIA A100 80GB |
| 驱动版本 | 570.195.03 | 535.x |
| vLLM 版本 | 0.1.dev (源码编译) | 0.12.0 |
| 测试模型 | Qwen/Qwen2.5-14B-Instruct | 相同 |

### 场景1: Memory-Bound (~4K Token Prefill)

| GPU | BF16 | FP8 | 加速比 |
|-----|------|-----|--------|
| H100 (原生 FP8) | 14,157 tok/s | 18,392 tok/s | 1.30x |
| H100 (强制 Marlin) | 14,157 tok/s | 7,936 tok/s | **0.56x** |
| A100 | 2,759 tok/s | 4,253 tok/s | 1.54x |

### 场景2: Compute-Bound (50 并发 Decode) ⭐

| GPU | BF16 | FP8 | 加速比 |
|-----|------|-----|--------|
| **H100** | 2,901 tok/s | **4,094 tok/s** | **1.41x** |
| A100 | 1,683 tok/s | 2,169 tok/s | 1.29x |

### 绝对性能对比

| 指标 | H100 FP8 | A100 FP8 | H100/A100 |
|------|----------|----------|-----------|
| Prefill | 18,392 tok/s | 4,253 tok/s | **4.3x** |
| Decode | 4,094 tok/s | 2,169 tok/s | **1.9x** |

---

## 🔬 NVIDIA 官方量化推荐

### 按 GPU 架构的官方推荐

| GPU 架构 | 推荐量化方式 | 说明 |
|----------|-------------|------|
| **Blackwell (B100/B200)** | NVFP4 | 最新 4-bit 浮点格式 |
| **Hopper (H100/H200)** | **FP8 (W8A8)** | 原生 FP8 Tensor Core |
| **Ampere (A100/A10)** | INT8 SmoothQuant | A100 没有 FP8 硬件! |
| 通用/旧卡 | INT4 Weight-Only | 节省显存 |

> ⚠️ **重要**: NVIDIA 官方 TensorRT-LLM 文档明确标注 "FP8 (Hopper)"，A100 上的 FP8 不是官方推荐方案。

### A100 的官方量化选项

| 方案 | 精度 | 计算方式 | 官方支持 |
|------|------|----------|----------|
| INT8 SmoothQuant | W8A8 | INT8 Tensor Core | ✅ 推荐 |
| INT8 Weight-Only | W8A16 | BF16 GEMM | ✅ 支持 |
| INT4 Weight-Only | W4A16 | BF16 GEMM | ✅ 支持 |
| GPTQ/AWQ | W4A16 | BF16 GEMM | ✅ 支持 |
| **FP8** | W8A8 | - | ❌ **仅 Hopper+** |

### vLLM 的 A100 FP8 实现 (非官方)

```
vLLM A100 + --quantization fp8 = Marlin kernel 实现的 FP8 动态反量化

这是社区方案，不是 NVIDIA 官方推荐:
- 用 Marlin 做 FP8 → BF16 反量化
- 计算还是 BF16 GEMM
- 在 memory-bound 场景有效
```

### 动态反量化 vs 静态量化

| 类型 | 代表 | 权重来源 | 量化时机 | 特点 |
|------|------|----------|----------|------|
| **动态反量化** | Marlin FP8 | 原始 BF16 模型 | 推理时动态转换 | 无需预处理，开箱即用 |
| **静态量化** | GPTQ, AWQ | 预量化模型 | 离线校准后固定 | 需下载专门的量化版模型 |

### 类似 Marlin 的动态反量化技术

| 技术 | 来源 | 支持精度 | 特点 |
|------|------|----------|------|
| **Marlin** | IST-DASLab | FP8, INT4 | 最快之一，vLLM 默认 |
| ExLlamaV2 | turboderp | INT4 (GPTQ) | 消费级 GPU 优化 |
| bitsandbytes | Tim Dettmers | INT8, INT4 | 简单易用 |
| TensorRT-LLM | NVIDIA | FP8, INT8, INT4 | 官方极致优化 |

---

## ⚠️ 踩坑记录

### 问题1: H100 强制 Marlin 比 BF16 慢 44%
- **原因**: Marlin 需要 dequant 开销，且无法使用原生 FP8 Tensor Core
- **解决**: 不要在 H100 上强制 Marlin，让 vLLM 自动选择原生 FP8
- **如何强制 (仅测试)**: `export VLLM_TEST_FORCE_FP8_MARLIN=1`

### 问题2: 预量化 FP8 模型显示 A100 加速比更高
- **原因**: 预量化 FP8 (compressed-tensors) 使用 weight-only 压缩，H100 不走原生 FP8 Tensor Core
- **解决**: 使用 `--quantization fp8` 动态量化触发原生 FP8

### 问题3: Prefix cache 导致结果不准
- **原因**: vLLM 默认开启 prefix caching，重复 prompt 命中缓存
- **解决**: 每个请求使用随机前缀

### 问题4: H100 FP8 加速比低于 A100
- **原因**: 测试的是 memory-bound 场景，Marlin 的带宽节省更有效
- **解决**: 测试 compute-bound 场景（高并发、长 context）

---

## 💡 选型建议

| 使用场景 | 推荐方案 | 理由 |
|----------|----------|------|
| 高并发服务 (>50 QPS) | H100 + FP8 | Compute-bound，原生 FP8 优势明显 |
| 长 context (32K+) | H100 + FP8 | Attention O(n²)，compute-bound |
| 低并发场景 | 两者均可 + FP8 | 都能从 FP8 受益 |
| 成本敏感 | A100 + FP8 | 性价比高 |

---

## �� RTX PRO 6000 (Blackwell) SGLang 测试

> 测试日期: 2025-12-19 | 框架: SGLang 0.5.6 + FlashInfer 0.5.3

### 测试环境

| 配置 | 值 |
|------|-----|
| GPU | NVIDIA RTX PRO 6000 48GB vGPU (Blackwell) |
| VM SKU | Azure NC RTX PRO 6000 |
| 驱动 | 580.105.08 (vGPU R580) |
| CUDA | 13.0 |
| 框架 | SGLang 0.5.6.post2 |
| FlashInfer | 0.5.3 |

### 测试模型

| 模型 | 精度 | 大小 |
|------|------|------|
| Qwen/Qwen2.5-14B-Instruct | BF16 | ~28GB |
| RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic | FP8 | ~15GB |

### 测试命令

```bash
# 启动 SGLang 服务 (最优配置)
python -m sglang.launch_server \
    --model-path RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic \
    --attention-backend triton \
    --kv-cache-dtype fp8_e5m2 \
    --tp 1 --port 30000

# 运行测试
python -m sglang.bench_serving --backend sglang \
    --num-prompts 200 --random-input-len 512 --random-output-len 128 \
    --random-range-ratio 0.0 --host 127.0.0.1 --port 30000
```

### 配置矩阵测试结果

| # | 模型 | Attention Backend | KV Cache | Output tok/s | 相对基准 |
|---|------|-------------------|----------|-------------:|:--------:|
| 1 | BF16 | FlashInfer | auto | 1,579.49 | baseline |
| 2 | BF16 | Triton | auto | 1,584.47 | +0.3% |
| 3 | BF16 | FlashInfer | fp8_e5m2 | 1,622.54 | +2.7% |
| 4 | BF16 | Triton | fp8_e5m2 | 1,618.93 | +2.5% |
| 5 | FP8 | FlashInfer | auto | 2,257.79 | +42.9% |
| 6 | FP8 | Triton | auto | 2,262.62 | +43.3% |
| 7 | FP8 | FlashInfer | fp8_e5m2 | 2,337.92 | +48.0% |
| 8 | **FP8** | **Triton** | **fp8_e5m2** | **2,352.61** | **+49.0%** 🏆 |

### 核心发现

| 因素 | 性能影响 |
|------|----------|
| **FP8 预量化模型** | **+43%** (最显著!) |
| KV Cache FP8 | +2-4% |
| FlashInfer vs Triton | <1% (Blackwell 上几乎无差异) |

### RTX PRO 6000 vs H100 vs A100 汇总

| GPU | 架构 | FP8 支持 | 框架 | BF16 tok/s | FP8 tok/s | 加速比 |
|-----|------|----------|------|------------|-----------|--------|
| **H100** | Hopper | ✅ 原生 | vLLM | 2,901 | 4,094 | **+41%** |
| **RTX PRO 6000** | Blackwell | ✅ 原生 | SGLang | 1,579 | 2,353 | **+49%** |
| A100 | Ampere | ❌ Marlin | vLLM | 1,683 | 2,169 | +29% |

> ⚠️ 注意: H100/A100 使用 vLLM 测试，RTX PRO 6000 使用 SGLang 测试。直接对比需考虑框架差异。

### RTX PRO 6000 最佳实践

```bash
# 🏆 RTX PRO 6000 最优配置 (2,353 tok/s)
python -m sglang.launch_server \
    --model-path RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic \
    --attention-backend triton \
    --kv-cache-dtype fp8_e5m2 \
    --tp 1
```

---

## 📚 参考资料

### 官方文档
- [NVIDIA TensorRT-LLM 量化指南](https://nvidia.github.io/TensorRT-LLM/reference/precision.html) - 官方量化推荐
- [NVIDIA Transformer Engine FP8 指南](https://docs.nvidia.com/deeplearning/transformer-engine/user-guide/examples/fp8_primer.html)
- [vLLM FP8 量化文档](https://docs.vllm.ai/en/latest/quantization/fp8.html)

### 硬件架构
- [NVIDIA H100 Tensor Core GPU](https://www.nvidia.com/en-us/data-center/h100/)
- [NVIDIA A100 Tensor Core GPU](https://www.nvidia.com/en-us/data-center/a100/)

### 量化技术
- [Marlin: 混合精度 LLM 内核](https://github.com/IST-DASLab/marlin) - 动态反量化 kernel
- [SmoothQuant 论文](https://arxiv.org/abs/2211.10438) - INT8 W8A8 量化
- [GPTQ 论文](https://arxiv.org/abs/2210.17323) - INT4 权重量化
- [AWQ 论文](https://arxiv.org/abs/2306.00978) - 激活感知量化

---

*作者: 魏新宇 (Microsoft AI and Apps GBB Architect) | 验证日期: 2025-12-19*
