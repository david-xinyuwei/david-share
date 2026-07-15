# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

在 Azure **AMD Instinct MI300X** 上运行 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）**，使用 SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + 模型专用 fused-MoE tuning，并与小米 H200 参考数据并列展示。

本客户版 repo 只包含最终验证性能、唯一一套 AMD 最新复现代码和紧凑验证元数据。PD-separated decode 必须把 RDMA 设备暴露给容器（`--privileged`、`/dev/mem`、`CAP_SYS_ADMIN`），否则 Mooncake 会 fallback 到 TCP，高并发吞吐结果无效。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

[English](README.md) | 中文

---

## 架构

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## 最终验证性能

以下展示最终通过验收的 MI300X 结果。

### 1P1D Prefill

| Context | Concurrency | 微软实测 MI300X input tok/s | 小米 H200 参考 | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 8K | 4 | **20,305.98** | 31,950 | 63.6% |
| 64K | 4 | **18,983.91** | 27,400 | 69.3% |
| 256K | 4 | **12,864.96** | 17,400 | 73.9% |

### 1P1D Decode — 8K Input / 1K Output

| Concurrency | 微软实测 MI300X output tok/s | 小米 H200 参考 | MI300X / H200 |
|---:|---:|---:|---:|
| 16 | **1,331.98** | 1,381 | 96.5% |
| 32 | **1,936.24** | 2,549 | 76.0% |
| 64 | **2,465.01** | 4,483 | 55.0% |
| 128 | **2,486.89** | 7,013 | 35.5% |

### 双节点 DP=2 Prefill — 有效峰值聚合吞吐

| Context | Concurrency | Aggregate input tok/s | 完成请求数 |
|---:|---:|---:|---:|
| 8K | 16 | **46,747.01** | 32/32 |
| 64K | 2 | **38,984.45** | 32/32 |
| 256K | 2 | **25,063.73** | 32/32 |

### 结果口径

- 所有最终 MI300X 行均通过 request count、output count、worker capacity 和 service-log 验收。
- 256K 使用 `--tokenize-prompt`，每条 request 精确发送 262,144 个 token IDs，16/16 全部完成。
- DP=2 为两台 MI300X 节点的 Prefill-only 聚合容量，不包含 P→D KV-cache transfer。
- H200 数值是小米提供的方向性参考。MI300X 使用真实 expert routing，H200 参考使用理想均衡 routing。
- 机器可读结果：[`data/final-results.tsv`](data/final-results.tsv)。唯一支持的复现代码：[`scripts/amd-latest/`](scripts/amd-latest/)。

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
| Docker 镜像 | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | AMD 0510 build, SHA `bb9d2e5ab1a6` |
| SGLang | Package `0.0.0.dev14147+g2f9b9aedf.d20260706`、source HEAD `2f9b9aedf` | 最终验证 runtime |
| AITER | Source HEAD `00e94abf`；tuned CSV SHA-256 `2c87ff1...80ea7` | 最终验证 runtime |
| ROCm | 7.2.0 | |
| GEMM 路径 | **CK A8W8 blockwise bpreshuffle** | `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1` |
| Mooncake | `0.3.7.post2` | PD 分离 KV cache 传输 |
| PyTorch | 2.9.1+rocm7.2.0 | ROCm backend |

### 模型

| 属性 | 值 | 来源 |
|------|---|------|
| 模型 | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| 总参数 | 1.02 T | HF Model Card |
| 活跃参数 | 42 B / token | HF Model Card |
| Routed experts | 384，每 token 8 个活跃 | HF Model Card |
| Attention | 混合：10 Global + 60 SWA (window=128) | HF Model Card |
| MTP | 3 层 multi-layer EAGLE | HF Model Card |
| 量化 | FP8 E4M3 | HF Model Card |
| Checkpoint 大小 | 963 GB (34 safetensors) | 实测 |

---

## 复现最终结果

只使用 [`scripts/amd-latest/`](scripts/amd-latest/)。该目录包含最终 1P1D、DP=2 启动脚本、客户结果对应的 benchmark 点和 fail-closed validators。

### 前置条件

- 2× Azure `Standard_ND96isr_MI300X_v5` 节点
- Docker image：`rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510`
- 模型：`/data/models/MiMo-V2.5-Pro`
- Runtime identifiers：[`data/validation/runtime-version.txt`](data/validation/runtime-version.txt)
- PD-separated Decode 容器必须暴露 RDMA devices、`/dev/mem` 和 `CAP_SYS_ADMIN`

### 1P1D

```bash
# 将 scripts/amd-latest/ 复制到两个容器的 /data/mimo-amd-latest/。
cd /data/mimo-amd-latest

# 分别在 Prefill、Decode、Router 终端执行：
bash launch_pd_prefill.sh
bash launch_pd_decode.sh
PREFILL_IB_IP=<prefill-node-ib-ip> DECODE_IB_IP=<decode-node-ib-ip> bash launch_pd_router.sh

# Direct worker capacity validation 通过后执行：
DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json bash benchmark_1p_prefill.sh
DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json bash benchmark_decode.sh
```

### DP=2 双节点 Prefill

```bash
cd /data/mimo-amd-latest
bash launch_dp2_node0.sh
bash launch_dp2_node1.sh
Node0_IP=<node0-ib-ip> Node1_IP=<node1-ib-ip> bash launch_dp2_router.sh
DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json bash benchmark_dp2_prefill.sh
```

Direct worker capacity、service logs 和 DP=2 worker distribution 的验收命令见 bundle README。

---

## 必要运行设置

| 设置 | 要求 |
|---|---|
| Decode CUDA Graph | 保持启用；Prefill 禁用 CUDA Graph。 |
| 256K request framing | 使用 context length 262151 和 `--tokenize-prompt`；要求 `max_req_input_len>=262145`。 |
| Router health | 使用非生成型 `/server_info` endpoint，timeout 30 秒。 |

---

## 参考资料

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` 分支](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo 模型专用 fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)
