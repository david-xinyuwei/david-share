# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

在 Azure **AMD Instinct MI300X** 上运行 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）**，使用 SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + 模型专用 fused-MoE tuning，并与小米 H200 参考数据并列展示。

本客户版 repo 包含核心对比结果、完整的微软扩展性测试矩阵、唯一一套支持的复现代码和紧凑验证元数据。PD-separated decode 必须把 RDMA 设备暴露给容器（`--privileged`、`/dev/mem`、`CAP_SYS_ADMIN`），否则 Mooncake 会 fallback 到 TCP，高并发吞吐结果无效。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)
>
> 最后验证：2026-07-14

[English](README.md) | 中文

---

## 架构

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## 核心结果 — 微软实测 MI300X vs 小米 H200

以下展示最终用于客户对比的结果点。下一节完整披露通过验收的扩展性矩阵。

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

### 双节点 DP=2 Prefill — 已验证峰值聚合吞吐

| Context | Concurrency | Aggregate input tok/s | 完成请求数 |
|---:|---:|---:|---:|
| 8K | 16 | **46,747.01** | 32/32 |
| 64K | 2 | **38,984.45** | 32/32 |

DP=2 的 nominal-length 256K 结果保留在后面的扩展性矩阵中，但不作为 exact-token 核心结果。

### 结果口径

- 所有标记为 `VALIDATED` 的核心结果均通过 request count、output count、worker capacity 和 service-log 验收。
- 核心结果中的 1P1D 256K 使用 `--tokenize-prompt`，每条 request 精确发送 262,144 个 token IDs，16/16 全部完成。
- DP=2 为两台 MI300X 节点的 Prefill-only 聚合容量，不包含 P→D KV-cache transfer。
- H200 数值是小米提供的方向性参考。MI300X 使用真实 expert routing，H200 参考使用理想均衡 routing。
- 核心结果来自最终 accepted evidence set。[`data/final-results.tsv`](data/final-results.tsv) 的 `evidence_scope` 字段区分 targeted rerun、fresh-service measurement 和 full-matrix peak。

---

## 微软扩展性测试

AMD 提供了基础启动方法：container image、tuned AITER path、1P1D/DP=2 topology 和 benchmark 入口。微软先严格复现该路径，再独立扩展 context/concurrency 覆盖范围，并加入 fail-closed correctness gates。**以下所有性能数据均为微软实测，不包含 AMD 性能数值。**

### 测试矩阵

| 测试面 | 工作负载 | Concurrency sweep | 每点请求数 | 结果 |
|---|---|---|---:|---|
| 1P1D Decode | 8K input / 1K output | 8, 16, 32, 64, 96, 128, 192 | 256 | 7 accepted |
| 1P1D Prefill | 8K、64K、nominal 256K / 1 output | 1, 2, 4, 8 | 16 | 12 个点通过运行门；nominal 256K 仅用于扩展性观察 |
| 双节点 DP=2 Prefill | 8K、64K、nominal 256K / 1 output | 8K/64K：1, 2, 4, 8, 16；nominal 256K：1, 2, 4, 8 | 32 | 14 accepted |
| **公开合计** |  |  |  | **33 个通过验收的扩展性测试点** |

仅发布通过验收的测量结果。这是一轮完整 accepted scalability matrix，不声称每个点都执行了三次。Decode 核心生产并发点另外做了两次 fresh-service 复测。

### Decode 扩展性 — 8K Input / 1K Output

| Concurrency | 成功请求数 | Output tok/s | Mean TPOT (ms) | Mean TTFT (ms) | 处理方式 |
|---:|---:|---:|---:|---:|---|
| 8 | 256/256 | 930.00 | 7.65 | 863.69 | Accepted |
| 16 | 256/256 | 1,303.44 | 10.72 | 1,398.73 | Accepted |
| 32 | 256/256 | 1,930.10 | 13.68 | 2,296.89 | Accepted |
| 64 | 256/256 | 2,462.83 | 17.08 | 7,406.18 | Accepted |
| 96 | 256/256 | 2,497.69 | 15.89 | 18,273.38 | Accepted |
| 128 | 256/256 | 2,468.95 | 16.45 | 27,128.38 | Accepted |
| 192 | 256/256 | 2,500.54 | 15.98 | 40,956.57 | Accepted |

实测现象：

- 吞吐从 concurrency 8 的 930.00 tok/s 增长到 concurrency 64 的 2,462.83 tok/s，此后到 concurrency 192 维持在约 2.47–2.50K tok/s 的平台区间。
- concurrency 64 以后吞吐基本不再增长，但 TTFT 显著上升。因此这是容量平台，不是延迟改善。

### Decode 核心点 Fresh-Service 复测

| Concurrency | Fresh run 1 tok/s | Fresh run 2 tok/s | 吞吐差异 | TPOT run 1 / run 2 (ms) |
|---:|---:|---:|---:|---:|
| 16 | 1,331.98 | 1,303.44 | -2.14% | 10.83 / 10.72 |
| 32 | 1,936.24 | 1,930.10 | -0.32% | 13.65 / 13.68 |
| 64 | 2,457.73 | 2,462.83 | +0.21% | 17.00 / 17.08 |
| 128 | 2,486.89 | 2,468.95 | -0.72% | 16.56 / 16.45 |

四个复测点的两次 fresh-service 吞吐最大绝对差异为 **2.14%**。

### 1P1D Prefill 扩展性

| Input | Concurrency | 成功请求数 | Input tok/s | Mean TTFT (ms) | 处理方式 |
|---:|---:|---:|---:|---:|---|
| 8K | 1 | 16/16 | 16,835.22 | 485.70 | Accepted |
| 8K | 2 | 16/16 | 19,618.25 | 829.40 | Accepted |
| 8K | 4 | 16/16 | 18,161.81 | 1,612.03 | Accepted |
| 8K | 8 | 16/16 | 21,004.97 | 2,817.91 | Accepted |
| 64K | 1 | 16/16 | 18,057.01 | 3,628.49 | Accepted |
| 64K | 2 | 16/16 | 19,860.45 | 6,481.41 | Accepted |
| 64K | 4 | 16/16 | 18,763.17 | 12,970.83 | Accepted |
| 64K | 8 | 16/16 | 18,765.43 | 22,530.68 | Accepted |
| Nominal 256K | 1 | 16/16 | 12,381.87 | 21,170.66 | 仅用于扩展性观察 |
| Nominal 256K | 2 | 16/16 | 12,378.06 | 41,208.61 | 仅用于扩展性观察 |
| Nominal 256K | 4 | 16/16 | 12,389.64 | 77,254.06 | 仅用于扩展性观察 |
| Nominal 256K | 8 | 16/16 | 12,402.23 | 133,251.83 | 仅用于扩展性观察 |

实测现象：

- 完整矩阵中的 8K Prefill 在 concurrency 8 达到 21,004.97 input tok/s。
- 64K Prefill 在 concurrency 2 达到峰值，此后随着并发增加保持在约 18.76K tok/s。
- nominal 256K 行使用 random-text prompt construction（`tokenize_prompt=false`），只描述扩展趋势。核心 exact-token 结果来自独立 targeted concurrency-4 复测：**12,864.96 input tok/s**，16/16 请求成功、16/16 retokenized outputs。

### 双节点 DP=2 Prefill 扩展性

| Input | Concurrency | 成功请求数 | Aggregate input tok/s | Mean TTFT (ms) | Worker request delta | 处理方式 |
|---:|---:|---:|---:|---:|---:|---|
| 8K | 1 | 32/32 | 20,751.73 | 393.90 | 17/16 | Accepted |
| 8K | 2 | 32/32 | 41,201.86 | 394.17 | 16/17 | Accepted |
| 8K | 4 | 32/32 | 43,401.70 | 723.96 | 17/16 | Accepted |
| 8K | 8 | 32/32 | 46,113.92 | 1,296.43 | 16/17 | Accepted |
| 8K | 16 | 32/32 | 46,747.01 | 2,276.28 | 17/16 | Accepted |
| 64K | 1 | 32/32 | 19,695.02 | 3,326.53 | 16/17 | Accepted |
| 64K | 2 | 32/32 | 38,984.45 | 3,348.49 | 17/16 | Accepted |
| 64K | 4 | 32/32 | 38,382.03 | 6,615.25 | 16/17 | Accepted |
| 64K | 8 | 32/32 | 38,204.80 | 12,418.82 | 17/16 | Accepted |
| 64K | 16 | 32/32 | 38,155.28 | 21,164.99 | 16/17 | Accepted |
| Nominal 256K | 1 | 32/32 | 12,783.28 | 20,505.88 | 17/16 | 仅用于扩展性观察 |
| Nominal 256K | 2 | 32/32 | 25,063.73 | 20,823.01 | 17/16 | 仅用于扩展性观察 |
| Nominal 256K | 4 | 32/32 | 24,923.63 | 40,785.01 | 16/17 | 仅用于扩展性观察 |
| Nominal 256K | 8 | 32/32 | 24,765.29 | 76,468.09 | 17/16 | 仅用于扩展性观察 |

实测现象：

- DP=2 的 8K 和 64K aggregate Prefill throughput 从 concurrency 1 到 2 接近翻倍，随后进入平台区间。
- 每个 accepted DP=2 点在两个 worker 上都有正 request delta，证明 router 实际将流量分配到了两个节点。
- 尚未完成 DP=2 256K exact-token rerun。这些行保留为 nominal-length 扩展性观察，不进入核心验证表。
- DP=2 是 Prefill-only capacity，不是 2P1D end-to-end throughput，也不测量 P→D KV-cache transfer。

### 256K Correctness 口径

| 证据集 | Client framing | 交付用途 |
|---|---|---|
| 完整扩展矩阵 | Random-text construction，`tokenize_prompt=false` | 用于 scaling 和 boundary 观察；nominal 256K 不是 exact-token 核心证据 |
| Targeted 1P1D 256K 复测 | 精确 262,144 token IDs，`--tokenize-prompt` | 核心验证结果：12,864.96 input tok/s，16/16 请求 |
| 当前 `scripts/amd-latest/` | 所有 256K benchmark 均使用 exact token IDs | 后续 256K 结果的强制复现路径 |

### 机器可读证据

- 核心结果点：[`data/final-results.tsv`](data/final-results.tsv)
- 通过验收的 33 点扩展性矩阵：[`data/scalability-results.tsv`](data/scalability-results.tsv)
- Decode 核心点复测：[`data/decode-repeatability.tsv`](data/decode-repeatability.tsv)
- Exact-token 与 runtime 验证元数据：[`data/validation/`](data/validation/)
- 唯一支持的复现代码：[`scripts/amd-latest/`](scripts/amd-latest/)

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
