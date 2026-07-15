# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + model-specific fused-MoE tuning, shown alongside Xiaomi's H200 reference data.

This customer-facing repo contains the headline comparison, the complete Microsoft-run scalability extension, one supported reproduction bundle, and compact runtime metadata. For PD-separated decode, the container must expose RDMA devices (`--privileged`, `/dev/mem`, and `CAP_SYS_ADMIN`); otherwise Mooncake falls back to TCP and high-concurrency throughput results are invalid.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)
>
> Last tested: 2026-07-14

English | [中文版](README-CN.md)

---

## Architecture

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## Headline Results — Microsoft-Tested MI300X vs Xiaomi H200

The tables below contain the final customer-comparison point set. Detailed scalability results are provided in the next section.

### 1P1D Prefill

| Context | Concurrency | Microsoft-tested MI300X input tok/s | Xiaomi H200 reference | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 8K | 4 | **20,305.98** | 31,950 | 63.6% |
| 64K | 4 | **18,983.91** | 27,400 | 69.3% |
| 256K | 4 | **12,864.96** | 17,400 | 73.9% |

### 1P1D Decode — 8K Input / 1K Output

| Concurrency | Microsoft-tested MI300X output tok/s | Xiaomi H200 reference | MI300X / H200 |
|---:|---:|---:|---:|
| 16 | **1,331.98** | 1,381 | 96.5% |
| 32 | **1,936.24** | 2,549 | 76.0% |
| 64 | **2,465.01** | 4,483 | 55.0% |
| 128 | **2,486.89** | 7,013 | 35.5% |

### Two-Node DP=2 Prefill — Peak Aggregate Throughput

| Context | Concurrency | Aggregate input tok/s |
|---:|---:|---:|
| 8K | 16 | **46,747.01** |
| 64K | 2 | **38,984.45** |

The nominal-length 256K DP=2 observation is retained in the detailed scalability matrix, but it is not an exact-token headline result.

### Result Scope

- The headline 1P1D 256K result sends exactly 262,144 token IDs per request with `--tokenize-prompt`.
- DP=2 values are aggregate Prefill-only capacity across two MI300X nodes; they do not include P→D KV-cache transfer.
- H200 figures are Xiaomi-provided directional references. MI300X uses real expert routing, while the H200 reference uses idealized balanced routing.
- Machine-readable headline results: [`data/final-results.tsv`](data/final-results.tsv).

---

## Microsoft Scalability Extension

AMD provided the base launch method: the container image, tuned AITER path, 1P1D/DP=2 topology, and benchmark entry points. Microsoft first reproduced that path, then independently extended the context and concurrency coverage and added fail-closed correctness gates. **Every performance value below is Microsoft-measured; no AMD performance values are included.**

### Test Matrix

| Surface | Workload | Concurrency sweep | Requests per point |
|---|---|---|---:|
| 1P1D Decode | 8K input / 1K output | 8, 16, 32, 64, 96, 128, 192 | 256 |
| 1P1D Prefill | 8K, 64K, nominal 256K / 1 output | 1, 2, 4, 8 | 16 |
| Two-node DP=2 Prefill | 8K, 64K, nominal 256K / 1 output | 8K/64K: 1, 2, 4, 8, 16; nominal 256K: 1, 2, 4, 8 | 32 |

The tables below present the measured scalability results. The core Decode production points were separately repeated on fresh services.

### Decode Scalability — 8K Input / 1K Output

| Concurrency | Output tok/s | Mean TPOT (ms) | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8 | 930.00 | 7.65 | 863.69 |
| 16 | 1,303.44 | 10.72 | 1,398.73 |
| 32 | 1,930.10 | 13.68 | 2,296.89 |
| 64 | 2,462.83 | 17.08 | 7,406.18 |
| 96 | 2,497.69 | 15.89 | 18,273.38 |
| 128 | 2,468.95 | 16.45 | 27,128.38 |
| 192 | 2,500.54 | 15.98 | 40,956.57 |

Observed behavior:

- Throughput increased from 930.00 tok/s at concurrency 8 to 2,462.83 tok/s at concurrency 64, then plateaued around 2.47–2.50K tok/s through concurrency 192.
- TTFT increased sharply after concurrency 64 even while throughput stayed flat. The plateau is therefore a capacity result, not a latency improvement.

### Core Decode Fresh-Service Repeatability

| Concurrency | Fresh run 1 tok/s | Fresh run 2 tok/s | Throughput delta | TPOT run 1 / run 2 (ms) |
|---:|---:|---:|---:|---:|
| 16 | 1,331.98 | 1,303.44 | -2.14% | 10.83 / 10.72 |
| 32 | 1,936.24 | 1,930.10 | -0.32% | 13.65 / 13.68 |
| 64 | 2,457.73 | 2,462.83 | +0.21% | 17.00 / 17.08 |
| 128 | 2,486.89 | 2,468.95 | -0.72% | 16.56 / 16.45 |

The maximum absolute two-run throughput delta was **2.14%** across the four repeated points.

### 1P1D Prefill Scalability

| Input | Concurrency | Input tok/s | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8K | 1 | 16,835.22 | 485.70 |
| 8K | 2 | 19,618.25 | 829.40 |
| 8K | 4 | 18,161.81 | 1,612.03 |
| 8K | 8 | 21,004.97 | 2,817.91 |
| 64K | 1 | 18,057.01 | 3,628.49 |
| 64K | 2 | 19,860.45 | 6,481.41 |
| 64K | 4 | 18,763.17 | 12,970.83 |
| 64K | 8 | 18,765.43 | 22,530.68 |
| Nominal 256K | 1 | 12,381.87 | 21,170.66 |
| Nominal 256K | 2 | 12,378.06 | 41,208.61 |
| Nominal 256K | 4 | 12,389.64 | 77,254.06 |
| Nominal 256K | 8 | 12,402.23 | 133,251.83 |

Observed behavior:

- 8K Prefill reached 21,004.97 input tok/s at concurrency 8 in the complete matrix.
- 64K Prefill peaked at concurrency 2 and then stayed around 18.76K tok/s as concurrency increased.
- The nominal 256K rows used random-text prompt construction (`tokenize_prompt=false`). They describe scaling behavior only. The headline exact-token result is the separate targeted concurrency-4 run: **12,864.96 input tok/s**.

### Two-Node DP=2 Prefill Scalability

| Input | Concurrency | Aggregate input tok/s | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8K | 1 | 20,751.73 | 393.90 |
| 8K | 2 | 41,201.86 | 394.17 |
| 8K | 4 | 43,401.70 | 723.96 |
| 8K | 8 | 46,113.92 | 1,296.43 |
| 8K | 16 | 46,747.01 | 2,276.28 |
| 64K | 1 | 19,695.02 | 3,326.53 |
| 64K | 2 | 38,984.45 | 3,348.49 |
| 64K | 4 | 38,382.03 | 6,615.25 |
| 64K | 8 | 38,204.80 | 12,418.82 |
| 64K | 16 | 38,155.28 | 21,164.99 |
| Nominal 256K | 1 | 12,783.28 | 20,505.88 |
| Nominal 256K | 2 | 25,063.73 | 20,823.01 |
| Nominal 256K | 4 | 24,923.63 | 40,785.01 |
| Nominal 256K | 8 | 24,765.29 | 76,468.09 |

Observed behavior:

- DP=2 nearly doubled 8K and 64K aggregate Prefill throughput from concurrency 1 to 2, then reached a plateau.
- The DP=2 measurements used both workers behind the two-node router.
- No exact-token DP=2 256K rerun was completed. Those rows remain visible as nominal-length scalability observations and are excluded from the headline comparison.
- DP=2 is Prefill-only capacity; it is not 2P1D end-to-end throughput and does not measure P→D KV-cache transfer.

### 256K Methodology

| Evidence set | Client framing | Delivery use |
|---|---|---|
| Complete expanded matrix | Random-text construction, `tokenize_prompt=false` | Scaling and boundary observations; nominal 256K rows are not exact-token headline evidence |
| Targeted 1P1D 256K rerun | Exactly 262,144 token IDs, `--tokenize-prompt` | Headline result: 12,864.96 input tok/s |
| Current `scripts/amd-latest/` | Exact token IDs for every 256K benchmark | Required reproduction path for future 256K results |

### Machine-Readable Evidence

- Headline point set: [`data/final-results.tsv`](data/final-results.tsv)
- Detailed scalability results: [`data/scalability-results.tsv`](data/scalability-results.tsv)
- Core Decode repeatability: [`data/decode-repeatability.tsv`](data/decode-repeatability.tsv)
- Exact-token and runtime validation metadata: [`data/validation/`](data/validation/)
- Supported reproduction bundle: [`scripts/amd-latest/`](scripts/amd-latest/)

---

## Hardware & Software Stack

### Compute — Two-Node Azure MI300X Cluster

| Property | Value |
|----------|-------|
| Azure SKU | `Standard_ND96isr_MI300X_v5` (8× MI300X per node) |
| GPU | AMD Instinct MI300X, `gfx942` (CDNA 3), **192 GB HBM3e**, 5.3 TB/s |
| Nodes | 2 (VMSS, same placement group — IB guaranteed) |
| Total GPU Memory | **16× 192 GB = 3,072 GB** |
| InfiniBand | 8× CX7 400G NDR per node, measured **368 Gbps** per port |

### Software Stack

| Component | Version | Notes |
|-----------|---------|-------|
| Docker image | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | AMD 0510 build, SHA `bb9d2e5ab1a6` |
| SGLang | Package `0.0.0.dev14147+g2f9b9aedf.d20260706`, source HEAD `2f9b9aedf` | Final tested runtime |
| AITER | Source HEAD `00e94abf`; tuned CSV SHA-256 `2c87ff1...80ea7` | Final tested runtime |
| ROCm | 7.2.0 | |
| GEMM path | **CK A8W8 blockwise bpreshuffle** | `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1` |
| Mooncake | `0.3.7.post2` | KV cache transfer for PD disaggregation |
| PyTorch | 2.9.1+rocm7.2.0 | ROCm backend |

### Model

| Property | Value | Source |
|----------|-------|--------|
| Model | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| Total parameters | 1.02 T | HF Model Card |
| Active parameters | 42 B per token | HF Model Card |
| Routed experts | 384, 8 active per token | HF Model Card |
| Attention | Hybrid: 10 Global + 60 SWA (window=128) | HF Model Card |
| MTP | 3-layer multi-layer EAGLE | HF Model Card |
| Quantization | FP8 E4M3 | HF Model Card |
| Checkpoint size | 963 GB (34 safetensors) | Measured |

---

## Reproduce Final Results

Use only [`scripts/amd-latest/`](scripts/amd-latest/). It contains the final 1P1D and DP=2 launch scripts, customer-facing benchmark points, and fail-closed validators.

### Prerequisites

- 2× Azure `Standard_ND96isr_MI300X_v5` nodes (VMSS, same placement group for IB)
- Docker image: `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` (SHA: `bb9d2e5ab1a6`)
- Model: [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) downloaded to `/data/models/MiMo-V2.5-Pro`
- Final runtime identifiers from [`data/validation/runtime-version.txt`](data/validation/runtime-version.txt)
- The PD-separated Decode container must expose RDMA devices, `/dev/mem`, and `CAP_SYS_ADMIN`

### 1P1D

```bash
# Copy scripts/amd-latest/ to /data/mimo-amd-latest/ in both containers.
cd /data/mimo-amd-latest
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json
export PREFILL_IB_IP=<prefill-node-ib-ip>
export DECODE_IB_IP=<decode-node-ib-ip>

# Separate terminals:
bash launch_pd_prefill.sh
bash launch_pd_decode.sh
bash launch_pd_router.sh

# After direct worker capacity validation:
bash benchmark_1p_prefill.sh
bash benchmark_decode.sh
```

### DP=2 Two-Node Prefill

```bash
cd /data/mimo-amd-latest
bash launch_dp2_node0.sh
bash launch_dp2_node1.sh
Node0_IP=<node0-ib-ip> Node1_IP=<node1-ib-ip> bash launch_dp2_router.sh
bash benchmark_dp2_prefill.sh
```

See the bundle README for direct worker capacity and service-log validation commands.

---

## Required Runtime Settings

| Setting | Requirement |
|---|---|
| Decode CUDA Graph | Keep enabled. Prefill disables CUDA Graph. |
| 256K request framing | Use context length 262151 and `--tokenize-prompt`; require `max_req_input_len>=262145`. |
| Router health | Use the non-generative `/server_info` endpoint with a 30-second timeout. |

---

## References

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` branch](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo model-specific fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)
