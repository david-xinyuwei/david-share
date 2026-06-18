# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD fork MTP/EAGLE, benchmarked against Xiaomi's H200 reference data.

This repo provides full reproduction scripts, launch commands, benchmark results, and server logs — so anyone with access to the same hardware can reproduce every number.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

---

## Latest H200-Aligned Result (2026-06-18)

The latest valid run uses the PD router path, fixed random input lengths, `chunked-prefill-size=16384`, and MTP/EAGLE layer=3. The completed MI300X baseline is `TP=8, local EP=8, DP=1`; Xiaomi's H200 reference uses stronger global EP/DP settings (`attn TP=8, DP=2, global EP=16` for prefill and `attn TP=8, DP=4, global EP=32` for decode), so the completed numbers below are an aligned workload comparison rather than an identical-topology comparison.

There is now a separate topology probe for the H200 prefill shape: `--tp-size 16 --dp-size 2 --enable-dp-attention`. In the current SGLang AMD fork, this gives `effective_attn_tp = tp_size / dp_size = 8`, matching MiMo-V2.5-Pro's fused-QKV requirement (`num_key_value_heads=8`). The probe passed the model/config validation path but failed before server readiness with MORI dispatch heap pressure, so it has **no performance numbers yet**.

Full two-round report: [`reports/micro_matrix_2x_report_20260618.md`](reports/micro_matrix_2x_report_20260618.md)
Raw two-round summary: [`data/micro_matrix_2x_summary_20260618.tsv`](data/micro_matrix_2x_summary_20260618.tsv)
256K diagnostic report: [`reports/diagnostic_256k_minimal_20260618.md`](reports/diagnostic_256k_minimal_20260618.md)
Raw 256K diagnostic summary: [`data/diagnostic_256k_minimal_20260618.tsv`](data/diagnostic_256k_minimal_20260618.tsv)
Long-context prefill sweep: [`reports/prefill_context_sweep_20260618.md`](reports/prefill_context_sweep_20260618.md)
Raw prefill context sweep: [`data/prefill_context_sweep_20260618.tsv`](data/prefill_context_sweep_20260618.tsv)
Streaming decode boundary report: [`reports/decode_context_boundary_20260618.md`](reports/decode_context_boundary_20260618.md)
Raw decode boundary summary: [`data/decode_context_boundary_20260618.tsv`](data/decode_context_boundary_20260618.tsv)
Initial report: [`reports/initial_h200_aligned_report_20260617.md`](reports/initial_h200_aligned_report_20260617.md)
Initial parsed summary: [`data/initial_router_valid_summary_20260617.tsv`](data/initial_router_valid_summary_20260617.tsv)
Topology probe report: [`reports/tp16_dp2_topology_probe_20260617.md`](reports/tp16_dp2_topology_probe_20260617.md)
Topology probe status TSV: [`data/tp16_dp2_probe_status_20260617.tsv`](data/tp16_dp2_probe_status_20260617.tsv)
Two-round matrix script: [`scripts/bench_micro_matrix_2x.sh`](scripts/bench_micro_matrix_2x.sh)
256K diagnostic script: [`scripts/bench_256k_prefill_minimal.sh`](scripts/bench_256k_prefill_minimal.sh)

### Validated vs Investigating

| Track | Topology | Status | What it proves |
|-------|----------|--------|----------------|
| EP8/DP1 baseline | `TP=8, local EP=8, DP=1`, 1P+1D PD router | Two-round data complete for 8K/64K prefill and 8K/64K decode; 256K repeated/concurrent runs are unstable | MI300X can run the H200 workload shape with real routing, MTP=3, and fixed random input lengths |
| 256K isolated diagnostic | `TP=8, local EP=8, DP=1`, single 256K request through PD router | 5/5 isolated 256K prefill requests succeeded, average 7,239 tok/s; sequential `n=4` still stalled after 2/4 | 256K compute path works; instability is in repeated/concurrent PD-router response-drain state |
| Long-context prefill sweep | `TP=8, local EP=8, DP=1`, isolated single requests with router restart | 64K, 128K, 192K, and 256K prefill all completed; latest 256K isolated result is 7,294 tok/s | The isolated prefill compute path is viable through 256K |
| Streaming decode boundary | `TP=8, local EP=8, DP=1`, BS=1, output=1024, streaming | 64K through 255.25K completed; 255.375K, 255.5K, and 256K hit the 300s stale rule with idle GPU | The single-request streaming decode boundary is between 255.25K and 255.375K |
| TP16/DP2 probe | `TP=16, DP=2, enable-dp-attention`, 2-node single server | Startup probe failed before ready: MORI heap OOM plus HIP invalid argument in dispatch/combine | The corrected H200 topology expression passes the MiMo-V2.5-Pro effective-attention-TP validation, but current MORI/runtime sizing cannot yet sustain the server |

### Current Summary

#### H200 Alignment Matrix — 6 Scenarios

**Prefill Throughput** (input=context_len, output=1, BS=4, MTP=3)

| Context | MI300X EP8 (tok/s) | H200 EP16/DP2 (tok/s) | H200 EP32/DP4 (tok/s) | MI300X / H200 EP16 | Status |
|---:|---:|---:|---:|---:|:---:|
| **8K** | 13,531 | 31,950 | 27,500 | **42.4%** | ✅ |
| **64K** | 11,500 | 27,400 | 23,000 | **42.0%** | ✅ |
| **256K** | 7,239 avg / 7,294 latest isolated | 17,400 | 13,425 | **41.6-41.9% single / ❌ concurrent** | ⚠️ |

> 256K repeated/concurrent prefill remains unstable. The isolated single-request diagnostic and context sweep confirm the compute path is viable at ~7.2-7.3K tok/s, but sequential `n=4` stalls after partial progress.

**Decode TPOT** (input=context_len, output=1024, MTP=3)

| Context | BS | MI300X TPOT (ms) | H200 EP32/DP4 TPOT (ms) | Ratio | Status |
|---:|---:|---:|---:|---:|:---:|
| **8K** | 16 | 13.71 | 11.59 | 1.18× | ✅ |
| | 32 | 16.53 | 12.56 | 1.32× | ✅ |
| | 64 | 19.70 | 14.28 | 1.38× | ✅ |
| | 128 | 22.16 | 18.25 | 1.21× | ✅ |
| | 192 | 22.56 | 23.29 | **0.97×** ✅ | ✅ |
| | 256 | 22.86 | 27.38 | **0.83×** ✅ | ✅ |
| **64K** | 16 | 23.36 | 11.99 | 1.95× | ✅ |
| | 32 | 23.37 | 14.31 | 1.63× | ✅ |
| | 64 | 24.39 | 16.33 | 1.49× | ✅ |
| | 96 | 24.18 | 19.63 | 1.23× | ✅ |
| **64K boundary** | 1 | 23.03 | — | — | ✅ |
| **80K boundary** | 1 | 26.07 | — | — | ✅ |
| **96K boundary** | 1 | 29.14 | — | — | ✅ |
| **112K boundary** | 1 | 32.20 | — | — | ✅ |
| **128K boundary** | 1 | 35.27 | — | — | ✅ |
| **192K boundary** | 1 | 47.48 | — | — | ✅ |
| **224K boundary** | 1 | 53.55 | — | — | ✅ |
| **240K boundary** | 1 | 56.57 | — | — | ✅ |
| **248K boundary** | 1 | 58.15 | — | — | ✅ |
| **252K boundary** | 1 | 58.86 | — | — | ✅ |
| **254K boundary** | 1 | 59.29 | — | — | ✅ |
| **255K boundary** | 1 | 59.45 | — | — | ✅ |
| **255.25K boundary** | 1 | 59.49 | — | — | ✅ |
| **255.375K boundary** | 1 | — | — | — | ❌ stale |
| **255.5K boundary** | 1 | — | — | — | ❌ stale |
| **256K boundary** | 1 | — | — | — | ❌ stale |
| **256K** | 16 | — | 13.93 | — | ❌ stuck |
| | 32 | — | 16.94 | — | ❌ stuck |

### Key Findings

1. **Decode 8K (BS≥192): MI300X matches or beats H200.** MI300X TPOT plateaus at ~22ms from BS64+, while H200 degrades linearly. Crossover at BS192.
2. **Decode 64K: 1.23-1.95× slower.** Flat ~23-24ms regardless of BS — memory-bandwidth bound on long-context KV access.
3. **Prefill: ~42% of H200 EP16.** Biggest gap. Root cause: **attention backend stuck on triton** — aiter CK attention kernel does not support MiMo's hybrid SWA+GQA yet ([ROCm/aiter#1542](https://github.com/ROCm/aiter/issues/1542)). AMD acknowledged this in the 2026-05-09 sync meeting.
4. **256K prefill: compute path works, repeated/concurrent PD-router path stalls.** Five isolated 256K prefill requests succeeded at 7,239 tok/s average, and a later isolated context sweep produced 7,294 tok/s. Sequential `n=4` still stalled at 2/4 with GPU idle and healthy router/prefill endpoints.
5. **Decode long-context boundary is now narrowed to 255.25K-255.375K for BS=1 streaming.** Single-request streaming decode works from 64K through 255.25K. The 255.375K, 255.5K, and 256K strict runs hit the 300s stale rule with idle GPU and healthy services, so they are not valid performance numbers.
6. **Topology gap remains open.** The completed MI300X data is EP8/DP1. H200's `ep_size` in the customer sheet is a global topology field (`attn_tp_size * dp_size`), not the same as SGLang's local `--ep-size`. The closest SGLang expression of H200 prefill EP16/DP2 for MiMo-V2.5-Pro is `--tp-size 16 --dp-size 2 --enable-dp-attention`, which is now tracked as a separate probe rather than mixed into the EP8 baseline.

### aiter Coverage (Current State)

| Component | aiter Enabled | Backend | Notes |
|-----------|:---:|:---:|------|
| MoE expert dispatch (fused_moe) | ✅ | CK kernel | 384-expert routing |
| MoE topk routing | ✅ | aiter topk | Expert selection |
| MORI-EP token dispatcher | ✅ | aiter FP8 quant | Cross-GPU communication |
| FP8 quantization | ✅ | aiter per-token FP8 | Weight/activation quantization |
| LayerNorm | ✅ | aiter fused | Fused normalization |
| **Attention (prefill + decode)** | **❌** | **triton** | **Blocked: hybrid SWA+GQA layout** ([ROCm/aiter#1542](https://github.com/ROCm/aiter/issues/1542)) |

> Attention is the single most compute-intensive operation. Prefill throughput is directly bottlenecked by the triton fallback. AMD confirmed this gap in the 2026-05-09 sync and has a CK MHA kernel in development, but it does not yet support hybrid SWA+GQA models.

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
| Docker image | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | AMD 0510 build |
| SGLang | `0.5.12.post2.dev2+gb5e695251` | AMD fork: [TianHao65/sglang](https://github.com/TianHao65/sglang) branch `Mimo_mtp_enable` |
| ROCm | 7.2.0 | |
| aiter | `0.1.12.post2.dev150` | MoE/GEMM/FP8/LayerNorm enabled; **attention still triton** (hybrid SWA+GQA blocked, [ROCm/aiter#1542](https://github.com/ROCm/aiter/issues/1542)) |
| Mooncake | `0.3.11.post1` | KV cache transfer for PD disaggregation |
| PyTorch | 2.9.1 | ROCm backend |

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

## Setup — AMD Fork SGLang Installation

The stock SGLang in the Docker image does NOT support MTP + cuda graph together on MiMo models. You must install the AMD fork:

```bash
# Inside the container
pip uninstall -y sglang
git clone https://github.com/TianHao65/sglang.git sglang-amd
cd sglang-amd
git checkout Mimo_mtp_enable

# Compile sgl-kernel for ROCm
pip install --upgrade pip
cd sgl-kernel
python3 setup_rocm.py install

# Install sglang
cd ..
rm -rf python/pyproject.toml && mv python/pyproject_other.toml python/pyproject.toml
pip install -e "python[all_hip]"

# Install Mooncake for PD disaggregation
pip install mooncake-transfer-engine

# Fix editable install import resolution
echo /path/to/sglang-amd/python > /opt/venv/lib/python3.10/site-packages/sglang_path.pth
```

Verify:
```bash
pip show sglang | grep Version
# Expected: 0.5.12.post2.dev2+gb5e695251

python3 -c "from sglang.benchmark.datasets import get_dataset; print('OK')"
# Expected: OK
```

---

## Scenario 1 — Single-Node MTP/EAGLE (TP=8)

### Configuration

```bash
python3 -m sglang.launch_server \
  --model-path /data/models/MiMo-V2.5-Pro \
  --tp-size 8 --host 0.0.0.0 --port 30000 \
  --trust-remote-code --disable-radix-cache \
  --cuda-graph-max-bs 32 \
  --mem-fraction-static 0.80 \
  --context-length 32768 --max-total-tokens 65536 \
  --max-running-requests 64 \
  --chunked-prefill-size 32768 \
  --attention-backend triton \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --enable-multi-layer-eagle \
  --enable-draft-weights-cpu-backup
```

Environment variables:
```bash
export SGLANG_USE_AITER=1 SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1 SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1 HSA_NO_SCRATCH_RECLAIM=1 NCCL_DMABUF_ENABLE=0
export SGLANG_ENABLE_SPEC_V2=1
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected
```

> Note: the table below is the earlier single-node smoke result. It remains useful as a baseline, but the H200-aligned run uses the PD router path and the newer MTP layer=3 settings shown above.

### Results — Single-Node Decode (16K input / 1K output)

| BS | Output Throughput (tok/s) | Median TPOT (ms) | MTP Accept Rate | MTP Accept Length | Status |
|---:|---:|---:|---:|---:|:---:|
| 4 | 248.49 | 15.01 | 0.88 | 2.00 | ✅ |
| 8 | 367.62 | 20.38 | — | 1.70 | ✅ |
| 16 | 522.85 | 27.23 | — | ~1.7 | ✅ |
| 32 | 639.98 | 40.61 | — | ~1.7 | ✅ |
| 64 | **CRASHED** | — | — | — | ❌ |

### BS=64 Crash — Known Issue

At BS=64 (exceeding `cuda-graph-max-bs=32`), the EAGLE draft model's extend step falls back to the eager attention path, which triggers a GPU memory fault in the SWA attention buffer:

```
RuntimeError: HIP error: an illegal instruction was encountered
  in SGLang triton extend_attention_fwd (SWA branch, eager path)
```

**Root cause**: The AMD fork's triton SWA kernel has an out-of-bounds buffer access when running in eager mode (non-cuda-graph) with EAGLE draft extend at batch sizes exceeding the cuda graph capture range.

**Workaround**: Set `--cuda-graph-max-bs` to cover all expected batch sizes. However, this increases GPU memory usage for cuda graph capture and may cause OOM with very large values.

---

## Scenario 2 — Cross-Node PD Disaggregation + MTP/EAGLE (1P+1D)

### Architecture

```
Node 1 (8× MI300X)               Node 2 (8× MI300X)
┌────────────────────┐            ┌────────────────────┐
│  Prefill Server     │  ──IB──▶  │  Decode Server      │
│  TP=8, port 30000   │  Mooncake │  TP=8, port 30001   │
│  --disagg prefill   │  KV xfer  │  --disagg decode     │
│  cuda_graph OFF     │  8×CX7    │  cuda_graph ON       │
│  MTP/EAGLE ON       │  400G     │  MTP/EAGLE ON        │
└────────────────────┘            └────────────────────┘
         │
    sglang_router (port 40000)
    --pd-disaggregation
```

- **KV Transfer**: Mooncake over InfiniBand (all 8× `mlx5_ib0..7`, 400 Gbps NDR each)
- **MTP/EAGLE**: Enabled on both Prefill and Decode servers
- **Prefill**: `--disable-cuda-graph` (prefill does not benefit from cuda graph)
- **Decode**: `--cuda-graph-max-bs 32` (cuda graph ON for decode acceleration)

### Key Parameters (Aligned to Xiaomi H200 Test Protocol)

| Parameter | Value | Alignment |
|-----------|-------|-----------|
| `--chunked-prefill-size` | **16384** | Matches H200 customer report `chunk_size=16384` |
| `--disable-radix-cache` | Yes | Matches H200 customer report |
| `--context-length` | 262144 | Covers H200 decode matrix (up to 256K context) |
| `--tp-size` | 8 | Completed EP8/DP1 baseline. With DP attention enabled, H200 `attn_tp=8` maps to effective attention TP, not necessarily the raw CLI `--tp-size`. |
| MTP layers | 3 (model built-in) | Matches H200 `mtp_layer_num=3` |
| IB devices | 8× CX7 400G | All NICs used for maximum KV transfer bandwidth |

### Environment Variables

```bash
# AMD ROCm / aiter
export SGLANG_USE_AITER=1 SGLANG_MOE_PADDING=1
export SGLANG_ROCM_FUSED_DECODE_MLA=1 SGLANG_SET_CPU_AFFINITY=1
export SGLANG_USE_ROCM700A=1 HSA_NO_SCRATCH_RECLAIM=1 NCCL_DMABUF_ENABLE=0

# Mooncake PD disaggregation
export TORCH_NCCL_BLOCKING_WAIT=1
export MC_GID_INDEX=3
export MC_TE_METRIC=1
export SGLANG_DISAGGREGATION_THREAD_POOL_SIZE=12
export SGLANG_DISAGGREGATION_BOOTSTRAP_TIMEOUT=5000
export SGLANG_DISAGGREGATION_WAITING_TIMEOUT=5000
```

### Results — PD Disaggregated Decode (16K input / 1K output, MTP ON)

| BS | Output Throughput (tok/s) | Median TPOT (ms) | Median TTFT (ms) | MTP Accept Rate | Status |
|---:|---:|---:|---:|---:|:---:|
| 4 | 247.73 | 14.11 | 295.60 | ~0.76 | ✅ |
| 8 | 398.04 | 17.70 | 344.06 | ~0.75 | ✅ |
| 16 | 576.88 | 22.15 | 613.53 | ~0.75 | ✅ |
| 32 | 820.00 | 30.01 | 1098.04 | ~0.75 | ✅ |
| 48 | 491.24 | 84.25 | 1053.36 | ~0.75 | ✅ ⚠️ |
| 64 | 690.19 | 82.47 | 1285.19 | ~0.75 | ✅ ⚠️ |

> **⚠️ BS=48/64**: TPOT jumps from ~30ms to ~84ms because BS exceeds `cuda-graph-max-bs=32`. The EAGLE draft extend step falls back to the eager triton SWA path, which is significantly slower. Unlike the single-node case (which crashes at BS=64), PD mode completes successfully but with degraded TPOT. Setting `cuda-graph-max-bs=96` could resolve this but requires revalidation.

> MTP accept rate ~0.75 closely matches the Xiaomi H200 report (accept_rate=0.75).

### Results — PD Disaggregated Decode (H200 Customer Alignment: context 8K)

| BS (total) | Output Throughput (tok/s) | Median TPOT (ms) | H200 TPOT (ms) | Ratio | Status |
|---:|---:|---:|---:|---:|:---:|
| 16 | 682.36 | 13.71 | 11.59 | 1.18× slower | ✅ |
| 32 | 961.58 | 16.53 | 12.56 | 1.32× slower | ✅ |
| 64 | 1,244.16 | 19.70 | 14.28 | 1.38× slower | ✅ |
| 128 | 1,513.52 | 22.16 | 18.25 | 1.21× slower | ✅ |
| 192 | 1,609.61 | 22.56 | 23.29 | **0.97× (parity)** | ✅ |
| 256 | 1,694.96 | 22.86 | 27.38 | **0.83× (faster)** | ✅ |

> MI300X TPOT is flat ~22ms across BS128-256 (likely hitting EAGLE draft batch ceiling), while H200 TPOT degrades linearly. At BS≥192 MI300X matches or beats H200.

### Results — PD Disaggregated Decode (H200 Customer Alignment: context 64K)

| BS (total) | Output Throughput (tok/s) | Median TPOT (ms) | H200 TPOT (ms) | Ratio | Status |
|---:|---:|---:|---:|---:|:---:|
| 16 | 143.06 | 23.36 | 11.99 | 1.95× slower | ✅ |
| 32 | 157.64 | 23.37 | 14.31 | 1.63× slower | ✅ |
| 64 | 171.81 | 24.39 | 16.33 | 1.49× slower | ✅ |
| 96 | 176.82 | 24.18 | 19.63 | 1.23× slower | ✅ |

> 64K context decode TPOT is flat ~23.6ms regardless of BS, suggesting memory-bandwidth saturation on long-context KV access.

### Results — Prefill Throughput (output=1)

| Context | MI300X (tok/s) | H200 EP16/DP2 (tok/s) | H200 EP32/DP4 (tok/s) | vs EP16 | vs EP32 | Status |
|---:|---:|---:|---:|---:|---:|:---:|
| 8K | 13,530.83 | 31,950 | 27,500 | 42.4% | 49.2% | ✅ |
| 64K | 11,500.10 | 27,400 | 23,000 | 42.0% | 50.0% | ✅ |
| 256K | 7,239.08 (isolated single request) | 17,400 | 13,425 | 41.6% | 53.9% | ⚠️ isolated only |

> 256K prefill is not stable under repeated/concurrent PD-router traffic. Five isolated single-request runs succeeded at 7,239.08 tok/s average, while sequential `n=4` stalled at 2/4 with GPU idle and healthy router/prefill endpoints.

---

## Comparison vs H200 — Important Context

### What Cannot Be Directly Compared

The Xiaomi H200 reference data uses a different parallelism topology:

| | H200 (Customer) | MI300X (This Work) |
|---|---|---|
| Attention TP | 8 | 8 effective attention TP in the completed EP8/DP1 baseline |
| Global EP | **16 / 32** | **8 local EP** in completed baseline |
| DP | **2 / 4** | **1** in completed baseline |
| Nodes | Multiple (implied by EP=32) | 2 (1P+1D) |
| GPU Memory | 141 GB HBM3e × 8 = 1,128 GB | **192 GB HBM3e × 8 = 1,536 GB** |

The H200 report's `bs (per DP)` column means **per data-parallel rank**. With DP=4, total actual concurrency = bs × 4. MI300X uses DP=1 in the completed baseline, so our BS = total concurrency. H200 system-level decode throughput = reported per-DP TPS × DP.

#### Topology Semantics Correction

The H200 sheet uses:

```text
global ep_size = attn_tp_size * dp_size
```

Examples from the H200 table:

| H200 row | attn TP | DP | global EP |
|----------|--------:|---:|----------:|
| Prefill group 1 | 8 | 2 | 16 |
| Prefill group 2 | 8 | 4 | 32 |
| Decode group | 8 | 4 | 32 |

Current SGLang has a different local CLI constraint for MoE EP. For `MiMoV2ForCausalLM` with `attention_projection_layout=fused_qkv`, the AMD fork computes:

```text
effective_attn_tp_size = tp_size / dp_size / attn_cp_size
expected_effective_attn_tp = num_key_value_heads = 8
```

Therefore:

- `--tp-size 8 --dp-size 2 --enable-dp-attention` would imply effective attention TP=4 for MiMo-V2.5-Pro and should not match the fused-QKV requirement.
- `--tp-size 16 --dp-size 2 --enable-dp-attention` implies effective attention TP=8 and is the current probe for H200 prefill EP16/DP2 shape.
- This probe is reported separately because it did not reach server readiness and has no benchmark numbers yet.

### Benchmark Methodology Differences

| Factor | H200 Reference | MI300X (This Work) | Impact |
|--------|------|------|--------|
| **Expert routing** | `fake_topk_ids` (perfectly balanced) | Real model routing (natural imbalance) | H200 numbers are **best-case** with zero straggler overhead. MI300X includes real routing overhead. The gap may be overstated by ~5-15%. |
| **Chunk size** | `16384 per DP` × DP=2 = 32768 total | `chunked-prefill-size=32768` (DP=1) | Total chunk throughput aligned. But single-rank processing a 32K chunk hits higher attention peak memory than two ranks each processing 16K. |
| **Attention backend** | CUDA kernels (FlashAttention / vendor-optimized) | triton (aiter CK blocked for hybrid SWA+GQA) | This is the #1 bottleneck. Prefill throughput is directly limited by triton fallback. |

> **Key caveat for readers**: The H200 reference data was generated with `fake_topk_ids` which forces all 384 experts to receive exactly equal token counts, eliminating MoE load imbalance. Our MI300X benchmark uses real model routing where expert load follows natural distribution. This means a portion of the observed gap is methodology-driven, not hardware-driven.

### DP Attention Status

DP attention is not available in the completed EP8/DP1 baseline because the baseline uses raw `--tp-size 8`, and MiMo-V2.5-Pro expects effective attention TP=8. Under DP attention, current SGLang divides raw `tp_size` by `dp_size`, so a two-node topology must raise raw `--tp-size` to 16 to keep effective attention TP at 8. That TP16/DP2 path now passes the model/config validation path but fails later in MORI dispatch heap allocation before the server becomes ready.

---

## Known Issues & Blocked Paths

| Issue | Status | Impact | Reference |
|-------|--------|--------|-----------|
| **aiter attention backend** | **❌ Blocked** | Attention (prefill+decode) stuck on triton; hybrid SWA+GQA K/V layout not supported by CK kernel. **This is the #1 perf bottleneck.** AMD acknowledged 2026-05-09. | [ROCm/aiter#1542](https://github.com/ROCm/aiter/issues/1542) |
| TP16/DP2 DP-attention server | ❌ Blocked before ready | Corrected H200 prefill topology probe passes effective-attention-TP validation, then fails with MORI dispatch heap OOM and HIP invalid argument in dispatch/combine. | This repo: [`reports/tp16_dp2_topology_probe_20260617.md`](reports/tp16_dp2_topology_probe_20260617.md) |
| Cross-node MORI-EP=16 | ❌ Blocked | RCCL / MORI instability when using 16-GPU expert-dispatch style layouts across 2 nodes. Limits the completed baseline to EP=8 per node. | [ROCm/mori#168](https://github.com/ROCm/mori/issues/168) |
| MTP/EAGLE + BS > cuda-graph-max-bs | ❌ Crash | EAGLE eager path SWA buffer fault at high BS | This repo |
| 256K PD router drain | ⚠️ Investigating | Concurrent 256K requests trigger `Error consuming prefill response` in router. Likely related to missing etcd/UCX infrastructure (see below). | This repo |

### PD Disaggregation Infrastructure Gap

Our PD setup differs from AMD's reference guide ([TianHao65/sglang MiMo-V2-Flash 1P1D Guide](https://github.com/TianHao65/sglang/blob/Mimo_Swa_Eable/MiMo-V2-Flash-MI308X_1P1D_Disaggregated_Inference_Guide.md)). AMD's standard PD uses additional infrastructure components that we have not yet deployed:

| Component | AMD Standard PD | Our Current Setup | Gap |
|-----------|:---:|:---:|------|
| etcd (cluster metadata) | ✅ `install_etcd.sh` | ❌ | PD coordination / service discovery |
| ROCm-aware UCX | ✅ Source build `--with-rocm` | ❌ | Optimized RDMA transport for GPU memory |
| ROCm-aware OpenMPI | ✅ Source build | ❌ | Cross-node process orchestration |
| RCCL 16-GPU all_reduce test | ✅ via mpirun | ❌ | Cross-node collective verification |
| `--page-size` | 64 | 1 for stable v3 baseline; 64 tested separately | KV cache page granularity |
| `--chunked-prefill-size` | 32768 | 16384 for stable EP8 baseline; 32768 triggered MORI heap pressure | Prefill chunk size |
| SSH between containers | ✅ passwordless | N/A (VM-level SSH) | Process launch mechanism |
| `llm-distributed-inference` helper repo | ✅ [sammysun0711/llm-distributed-inference](https://github.com/sammysun0711/llm-distributed-inference) | ❌ | Setup automation scripts |

> **Impact hypothesis**: The 256K PD router drain issue and the overall PD stability gap may stem from missing etcd/UCX/OpenMPI infrastructure. AMD's guide installs these as prerequisites before launching PD servers. Our setup relies on bare SGLang router + Mooncake without etcd coordination or UCX transport optimization.
>
> **Next step**: Deploy AMD-standard PD infrastructure (etcd + ROCm-aware UCX + OpenMPI) on our MI300X cluster, then re-run the full H200 matrix to see if 256K stabilizes and overall performance improves.

---

## Reproduction

### Step 1 — Pull image and download model

```bash
docker pull rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510

pip install huggingface_hub
huggingface-cli download XiaomiMiMo/MiMo-V2.5-Pro \
  --local-dir /data/models/MiMo-V2.5-Pro
# 963 GB, 49 files
```

### Step 2 — Start container

```bash
docker run -d -it \
    --ipc=host --network=host --privileged \
    --cap-add=CAP_SYS_ADMIN \
    --device=/dev/kfd --device=/dev/dri --device=/dev/mem \
    --group-add video \
    --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
    --shm-size 32G \
    -v /data:/data \
    --entrypoint /bin/bash \
    --name sglang \
    rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510
```

### Step 3 — Install AMD fork SGLang (see Setup section above)

### Step 4 — Launch servers

- **Single node**: `bash scripts/launch_single_node_mtp.sh`
- **PD disaggregated**: Edit IB IPs in scripts, then:
  1. Decode node: `bash scripts/launch_decode.sh`
  2. Prefill node: `bash scripts/launch_prefill.sh`
  3. Prefill node: `bash scripts/launch_router.sh`
- **TP16/DP2 topology probe**: export a `DIST_INIT_ADDR` reachable from both nodes, then run `scripts/launch_tp16_dp2_node0.sh` on node 0 and `scripts/launch_tp16_dp2_node1.sh` on node 1. This is a diagnostic path only until MORI heap sizing is fixed.

### Step 5 — Run benchmarks

```bash
bash scripts/bench_h200_alignment.sh
```

---

## File Structure

```
├── README.md                     ← This file
├── scripts/
│   ├── launch_single_node_mtp.sh ← Single-node MTP server
│   ├── launch_prefill.sh         ← PD prefill server
│   ├── launch_decode.sh          ← PD decode server
│   ├── launch_router.sh          ← PD router
│   ├── bench_h200_alignment.sh   ← H200-aligned benchmark
│   ├── bench_full_h200_matrix_v3.sh ← Full EP8/DP1 matrix, page-size=1 baseline
│   ├── launch_tp16_dp2_node0.sh  ← Node 0 for H200 EP16/DP2 topology probe
│   └── launch_tp16_dp2_node1.sh  ← Node 1 for H200 EP16/DP2 topology probe
├── data/                         ← Raw benchmark JSON results
├── logs/                         ← Server logs (sanitized)
└── images/                       ← Diagrams
```

---

## References

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork (Mimo_mtp_enable)](https://github.com/TianHao65/sglang/tree/Mimo_mtp_enable)
- [AMD MI308X PD Disaggregation Guide](https://github.com/TianHao65/sglang/blob/Mimo_Swa_Eable/MiMo-V2-Flash-MI308X_1P1D_Disaggregated_Inference_Guide.md)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*Last updated: 2026-06-17*
