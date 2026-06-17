# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD fork MTP/EAGLE, benchmarked against Xiaomi's H200 reference data.

This repo provides full reproduction scripts, launch commands, benchmark results, and server logs — so anyone with access to the same hardware can reproduce every number.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

---

## Latest H200-Aligned Result (2026-06-17)

The latest valid run uses the PD router path, fixed random input lengths, `chunked-prefill-size=16384`, and MTP/EAGLE layer=3. The current MI300X topology is `TP=8, EP=8`; Xiaomi's H200 reference uses stronger EP/DP settings (`EP=16/DP=2` for prefill and `EP=32/DP=4` for decode), so this is an aligned workload comparison rather than an identical-topology comparison.

Full initial report: [`reports/initial_h200_aligned_report_20260617.md`](reports/initial_h200_aligned_report_20260617.md)  
Raw parsed summary: [`data/initial_router_valid_summary_20260617.tsv`](data/initial_router_valid_summary_20260617.tsv)  
Two-round recovery script now running: [`scripts/bench_micro_matrix_2x.sh`](scripts/bench_micro_matrix_2x.sh)

### Current Summary

#### H200 Alignment Matrix — 6 Scenarios

**Prefill Throughput** (input=context_len, output=1, BS=4, MTP=3)

| Context | MI300X EP8 (tok/s) | H200 EP16/DP2 (tok/s) | H200 EP32/DP4 (tok/s) | MI300X / H200 EP16 | Status |
|---:|---:|---:|---:|---:|:---:|
| **8K** | 14,436 | 31,950 | 27,500 | **45.2%** | ✅ |
| **64K** | 11,445 | 27,400 | 23,000 | **41.8%** | ✅ |
| **256K** | ~7,315 (single-req) | 17,400 | 13,425 | ~42% single / ❌ concurrent | ⚠️ |

> 256K concurrent prefill unstable (PD router drain issue); single-request diagnostic confirms ~7,315 tok/s.

**Decode TPOT** (input=context_len, output=1024, MTP=3)

| Context | BS | MI300X TPOT (ms) | H200 EP32/DP4 TPOT (ms) | Ratio | Status |
|---:|---:|---:|---:|---:|:---:|
| **8K** | 16 | 14.74 | 11.59 | 1.27× | ✅ |
| | 32 | 19.07 | 12.56 | 1.52× | ✅ |
| | 64 | 22.57 | 14.28 | 1.58× | ✅ |
| | 128 | 22.62 | 18.25 | 1.24× | ✅ |
| | 192 | 22.79 | 23.29 | **0.98×** ✅ | ✅ |
| | 256 | 22.78 | 27.38 | **0.83×** ✅ | ✅ |
| **64K** | 16 | 23.65 | 11.99 | 1.97× | ✅ |
| | 32 | 23.61 | 14.31 | 1.65× | ✅ |
| | 64 | 23.77 | 16.33 | 1.46× | ✅ |
| | 96 | 23.60 | 19.63 | 1.20× | ✅ |
| **256K** | 16 | 59.40 | 13.93 | 4.26× | ❌ unstable |
| | 32 | — | 16.94 | — | ❌ stuck |

### Key Findings

1. **Decode 8K (BS≥192): MI300X matches or beats H200.** MI300X TPOT plateaus at ~22ms from BS64+, while H200 degrades linearly. Crossover at BS192.
2. **Decode 64K: 1.2-2.0× slower.** Flat ~23.6ms regardless of BS — memory-bandwidth bound on long-context KV access.
3. **Prefill: ~45% of H200 EP16.** Biggest gap. Root cause: **attention backend stuck on triton** — aiter CK attention kernel does not support MiMo's hybrid SWA+GQA yet ([ROCm/aiter#1542](https://github.com/ROCm/aiter/issues/1542)). AMD acknowledged this in the 2026-05-09 sync meeting.
4. **256K: PD router response-drain issue.** Not a compute or OOM problem — single-request works fine. Concurrent 256K requests trigger router-level failures.
5. **Topology disadvantage**: MI300X uses EP=8/DP=1 (model constraint: kv_heads=8=tp_size). H200 uses EP16-32/DP2-4. This alone accounts for a significant portion of the prefill gap.

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
| `--tp-size` | 8 | Matches H200 `attn_tp=8` |
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
| 16 | 7,170.84 | 14.74 | 11.59 | 1.27× slower | ✅ |
| 32 | 10,763.28 | 19.07 | 12.56 | 1.52× slower | ✅ |
| 64 | 12,776.32 | 22.57 | 14.28 | 1.58× slower | ✅ |
| 128 | 12,875.40 | 22.62 | 18.25 | 1.24× slower | ✅ |
| 192 | 13,248.56 | 22.79 | 23.29 | **0.98× (parity)** | ✅ |
| 256 | 13,025.30 | 22.78 | 27.38 | **0.83× (faster)** | ✅ |

> MI300X TPOT is flat ~22ms across BS128-256 (likely hitting EAGLE draft batch ceiling), while H200 TPOT degrades linearly. At BS≥192 MI300X matches or beats H200.

### Results — PD Disaggregated Decode (H200 Customer Alignment: context 64K)

| BS (total) | Output Throughput (tok/s) | Median TPOT (ms) | H200 TPOT (ms) | Ratio | Status |
|---:|---:|---:|---:|---:|:---:|
| 16 | 11,494.38 | 23.65 | 11.99 | 1.97× slower | ✅ |
| 32 | 11,477.83 | 23.61 | 14.31 | 1.65× slower | ✅ |
| 64 | 11,508.16 | 23.77 | 16.33 | 1.46× slower | ✅ |
| 96 | 11,454.83 | 23.60 | 19.63 | 1.20× slower | ✅ |

> 64K context decode TPOT is flat ~23.6ms regardless of BS, suggesting memory-bandwidth saturation on long-context KV access.

### Results — Prefill Throughput (output=1)

| Context | MI300X (tok/s) | H200 EP16/DP2 (tok/s) | H200 EP32/DP4 (tok/s) | vs EP16 | vs EP32 | Status |
|---:|---:|---:|---:|---:|---:|:---:|
| 8K | 14,435.91 | 31,950 | 27,500 | 45.2% | 52.5% | ✅ |
| 64K | 11,445.42 | 27,400 | 23,000 | 41.8% | 49.8% | ✅ |
| 256K | 217.38 | 17,400 | 13,425 | 1.2% | 1.6% | ❌ unstable |

> 256K prefill is not stable — only 6/20 requests succeeded (PD router response-drain issue). Single-request diagnostic confirms 256K works (~7,315 tok/s for 1 request), but concurrent load triggers failures.

---

## Comparison vs H200 — Important Context

### What Cannot Be Directly Compared

The Xiaomi H200 reference data uses a different parallelism topology:

| | H200 (Customer) | MI300X (This Work) |
|---|---|---|
| TP | 8 | 8 |
| EP | **32** | **None** (V2.5-Pro constraint) |
| DP | **4** | **1** (V2.5-Pro kv_heads=8=tp_size) |
| Nodes | Multiple (implied by EP=32) | 2 (1P+1D) |
| GPU Memory | 141 GB HBM3e × 8 = 1,128 GB | **192 GB HBM3e × 8 = 1,536 GB** |

The H200 report's `bs (per DP)` column means **per data-parallel rank**. With DP=4, total actual concurrency = bs × 4. MI300X uses DP=1, so our BS = total concurrency.

### Why DP Attention Is Not Available on MI300X

MiMo-V2.5-Pro has `num_kv_heads=8 = tp_size=8`. DP attention requires `num_kv_heads > tp_size` to split KV heads across DP ranks. This is a model architecture constraint, not a hardware limitation.

---

## Known Issues & Blocked Paths

| Issue | Status | Impact | Reference |
|-------|--------|--------|-----------|
| **aiter attention backend** | **❌ Blocked** | Attention (prefill+decode) stuck on triton; hybrid SWA+GQA K/V layout not supported by CK kernel. **This is the #1 perf bottleneck.** AMD acknowledged 2026-05-09. | [ROCm/aiter#1542](https://github.com/ROCm/aiter/issues/1542) |
| Cross-node MORI-EP=16 | ❌ Blocked | RCCL deadlock with Mooncake when using 16-GPU EP across 2 nodes. Limits us to EP=8 per node. | [ROCm/mori#168](https://github.com/ROCm/mori/issues/168) |
| MTP/EAGLE + BS > cuda-graph-max-bs | ❌ Crash | EAGLE eager path SWA buffer fault at high BS | This repo |
| DP attention on V2.5-Pro | ❌ N/A | kv_heads=8=tp_size, cannot split KV heads across DP ranks | Model architecture |
| 256K PD router drain | ⚠️ Investigating | Concurrent 256K requests trigger `Error consuming prefill response` in router | This repo |

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
│   └── bench_h200_alignment.sh   ← H200-aligned benchmark
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

*Last updated: 2026-06-16*
