# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

在 Azure **AMD Instinct MI300X** 上运行 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）**，使用 SGLang + AMD fork MTP/EAGLE，与小米 H200 参考数据对齐 benchmark。

本 repo 提供完整的复现脚本、启动命令、benchmark 结果和 server 日志——任何有相同硬件的人都可以复现每一个数字。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

[English](README.md) | 中文

---

## 核心发现（2026-06-19 更新）

### 三种配置的 Trade-off

| 配置 | Prefill tok/s (64K) | Decode 8K TPOT (ms) | 适用场景 |
|------|:---:|:---:|------|
| ① triton + MTP=3 | 11,500 | **13.71** | Decode 密集型 |
| ② aiter + MTP=3 | ~16,000 | 22.78 | ❌ 最差组合（MTP 失效） |
| ③ aiter + no-MTP | **16,125** | 23.23 | Prefill 密集型 / 长上下文 |

### aiter 后端效果

AMD 新 commit（`f5fe8e944`）启用 aiter 注意力后端：

- **Prefill 提升**：+12%（8K）、+40%（64K）、+56%（256K）
- **Decode**：aiter + MTP 不兼容（acceptance rate 0.666 → 0.2），MTP 失效
- **结论**：Prefill 赢，Decode 输（因为丢了 MTP 加速）

### 关键配置发现：CUDA Graph

> **⚠️ 2026-06-19 发现**：Decode server **禁止**使用 `--disable-cuda-graph`。禁用后 TPOT 退化 5 倍（23ms → 120ms）。仅 Prefill server 应禁用 CUDA Graph（长序列需要动态内存分配）。

---

## H200 对齐矩阵 — 完整结果

### Decode 8K TPOT (ms) — 三版本对比

| BS | ① triton+MTP=3 | ② aiter+MTP=3 | ③ aiter no-MTP | H200 |
|:--:|:---:|:---:|:---:|:---:|
| 16 | **13.71** | 22.78 | 23.23 | 11.59 |
| 32 | **16.53** | 29.14 | 27.29 | 12.56 |
| 64 | **19.70** | 35.29 | 34.62 | 14.28 |
| 128 | **22.16** | 40.45 | 35.96 | 18.25 |
| 192 | **22.56** | 44.36 | 41.79 | 23.29 |
| 256 | **22.86** | 47.23 | 43.64 | 27.38 |

### Decode 64K TPOT (ms)

| BS | ③ aiter no-MTP | ① triton+MTP=3 | H200 | aiter/H200 |
|:--:|:---:|:---:|:---:|:---:|
| 16 | 20.25 | 23.36 | 11.99 | 1.7× |
| 32 | 20.58 | 23.37 | 14.31 | 1.4× |
| 64 | 22.27 | 24.39 | 16.33 | 1.4× |
| 96 | OOM | 24.18 | 19.63 | — |

### Prefill 吞吐 (tok/s)

| 上下文长度 | aiter no-MTP | triton+MTP | 提升 | H200 | aiter/H200 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **8K** | **15,133** | 13,531 | +12% | 31,950 | 47% |
| **64K** | **16,125** | 11,500 | +40% | 27,400 | 59% |
| **256K** | **11,410** | 7,294 | +56% | 17,400 | 66% |

### aiter + MTP 不兼容性

| 指标 | triton + MTP=3 | aiter + MTP=3 |
|------|:---:|:---:|
| acceptance_rate | **0.666** | 0.2 |
| accept_length | **3.2** | 1.6 |
| 实际加速 | ~3× | ~1.05×（基本无效） |

> **根因**：aiter 注意力产生与 triton 数值不同的输出。MTP draft model 是基于 triton 注意力输出训练/校准的，切到 aiter 后 draft 预测变得不准确，~80% 被拒绝。

---

## aiter 覆盖情况（2026-06-19 更新）

| 组件 | aiter 启用 | 后端 | 说明 |
|------|:---:|:---:|------|
| MoE expert dispatch (fused_moe) | ✅ | CK kernel | 384 expert routing |
| MoE topk routing | ✅ | aiter topk | Expert 选择 |
| MORI-EP token dispatcher | ✅ | aiter FP8 quant | 跨 GPU 通信 |
| FP8 quantization | ✅ | aiter per-token FP8 | 权重/激活量化 |
| LayerNorm | ✅ | aiter fused | Fused normalization |
| **Attention (prefill + decode)** | **✅** | **aiter `mha_batch_prefill`** | **2026-06-18 commit `f5fe8e944` 启用** |

---

## 硬件与软件栈

### 计算 — 双节点 Azure MI300X 集群

| 属性 | 值 |
|------|---|
| Azure SKU | `Standard_ND96isr_MI300X_v5`（每节点 8× MI300X） |
| GPU | AMD Instinct MI300X, `gfx942` (CDNA 3), **192 GB HBM3e**, 5.3 TB/s |
| 节点数 | 2（VMSS，相同 placement group — IB 保证） |
| 总 GPU 内存 | **16× 192 GB = 3,072 GB** |
| InfiniBand | 8× CX7 400G NDR/节点，实测 **368 Gbps**/端口 |

### 软件栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker 镜像 | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | AMD 0510 build |
| SGLang | `0.5.12.post2.dev4` | AMD fork: [TianHao65/sglang](https://github.com/TianHao65/sglang) branch `Mimo_mtp_enable`, commit `f5fe8e944` |
| ROCm | 7.2.0 | |
| aiter | `0.1.12.post2.dev150` | MoE/GEMM/FP8/LayerNorm/Attention 全部启用。sgl-kernel 0.4.2.post1 |
| Mooncake | `0.3.11.post1` | PD 分离 KV cache 传输 |
| PyTorch | 2.9.1 | ROCm backend |

### 模型

| 属性 | 值 | 来源 |
|------|---|------|
| 模型 | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| 总参数 | 1.02 T | HF Model Card |
| 活跃参数 | 42 B / token | HF Model Card |
| Routed experts | 384, 每 token 8 个活跃 | HF Model Card |
| Attention | 混合：10 Global + 60 SWA (window=128) | HF Model Card |
| MTP | 3 层 multi-layer EAGLE | HF Model Card |
| 量化 | FP8 E4M3 | HF Model Card |
| Checkpoint 大小 | 963 GB (34 safetensors) | 实测 |

---

## 架构 — PD 分离部署

```
Node 1 (8× MI300X)               Node 2 (8× MI300X)
┌────────────────────┐            ┌────────────────────┐
│  Prefill Server     │  ──IB──▶  │  Decode Server      │
│  TP=8, port 30000   │  Mooncake │  TP=8, port 30001   │
│  --disagg prefill   │  KV xfer  │  --disagg decode     │
│  cuda_graph OFF     │  8×CX7    │  cuda_graph ON ⚠️    │
│  aiter attention    │  400G     │  aiter attention     │
└────────────────────┘            └────────────────────┘
         │
    sglang_router (port 40000)
    --pd-disaggregation
```

> ⚠️ Decode server **必须保持 CUDA Graph 启用**（不加 `--disable-cuda-graph`），否则 TPOT 退化 5×。

---

## 已知问题

| 问题 | 状态 | 影响 |
|------|------|------|
| ~~aiter attention 后端~~ | **✅ 已修复** | commit `f5fe8e944` 已修复 |
| **aiter + MTP 不兼容** | **❌ 新问题** | MTP acceptance rate 降到 0.2，阻碍最佳 decode 性能 |
| **Decode CUDA Graph** | **⚠️ 关键配置** | Decode 禁用 CUDA Graph 导致 5× TPOT 退化 |
| TP16/DP2 DP-attention | ❌ 阻塞 | MORI dispatch heap OOM |
| 跨节点 MORI-EP=16 | ❌ 阻塞 | RCCL 不稳定 |
| 256K PD router drain | ⚠️ 调查中 | 并发 256K 请求触发 router 错误 |

---

## 结论

1. **aiter 后端是 Prefill 优化**：注意力算子加速 5.6×，端到端 Prefill 提升 12-56%
2. **aiter + MTP 不兼容是当前最大阻碍**：修复后可同时获得 Prefill 加速 + MTP decode 加速
3. **MI300X 在高并发 decode 场景有优势**：BS≥192 时（triton+MTP）TPOT 与 H200 持平甚至更快
4. **CUDA Graph 对 decode 性能至关重要**：decode server 禁用 = 5× 性能退化

---

## 参考资料

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork (Mimo_mtp_enable)](https://github.com/TianHao65/sglang/tree/Mimo_mtp_enable)
- [AMD MI308X PD Disaggregation Guide](https://github.com/TianHao65/sglang/blob/Mimo_Swa_Eable/MiMo-V2-Flash-MI308X_1P1D_Disaggregated_Inference_Guide.md)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*最后更新: 2026-06-22*
