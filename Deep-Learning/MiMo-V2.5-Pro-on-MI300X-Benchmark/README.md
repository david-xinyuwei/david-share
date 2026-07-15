# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + model-specific fused-MoE tuning, shown alongside Xiaomi's H200 reference data.

This customer-facing repo contains the final validated performance tables, one supported AMD reproduction bundle, and compact validation metadata. For PD-separated decode, the container must expose RDMA devices (`--privileged`, `/dev/mem`, and `CAP_SYS_ADMIN`); otherwise Mooncake falls back to TCP and high-concurrency throughput results are invalid.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

English | [中文版](README-CN.md)

---

## Architecture

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## Final Validated Performance

The tables below contain the final validated MI300X results.

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

### Two-Node DP=2 Prefill — Peak Valid Aggregate Throughput

| Context | Concurrency | Aggregate input tok/s | Completed requests |
|---:|---:|---:|---:|
| 8K | 16 | **46,747.01** | 32/32 |
| 64K | 2 | **38,984.45** | 32/32 |
| 256K | 2 | **25,063.73** | 32/32 |

### Result Scope

- All final MI300X rows passed request-count, output-count, worker-capacity, and service-log validation.
- The 256K result sends exactly 262,144 token IDs per request with `--tokenize-prompt`; all 16/16 requests completed.
- DP=2 values are aggregate Prefill-only capacity across two MI300X nodes; they do not include P→D KV-cache transfer.
- H200 figures are Xiaomi-provided directional references. MI300X uses real expert routing, while the H200 reference uses idealized balanced routing.
- Machine-readable results: [`data/final-results.tsv`](data/final-results.tsv). The only supported reproduction bundle is [`scripts/amd-latest/`](scripts/amd-latest/).

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
| SGLang | Package `0.0.0.dev14147+g2f9b9aedf.d20260706`, source HEAD `2f9b9aedf` | Final validated runtime |
| AITER | Source HEAD `00e94abf`; tuned CSV SHA-256 `2c87ff1...80ea7` | Final validated runtime |
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
