# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD fork MTP/EAGLE, benchmarked against Xiaomi's H200 reference data.

This repo provides full reproduction scripts, launch commands, benchmark results, and server logs. With 2× Azure ND96isr_MI300X_v5 nodes and the specified Docker image, the steps below rebuild a clean-room MI300X environment and run the same AMD benchmark scripts. For PD-separated decode, the container must expose RDMA devices (`--privileged`, `/dev/mem`, and `CAP_SYS_ADMIN`); otherwise Mooncake may fall back to TCP and invalidate high-concurrency throughput results.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

English | [中文版](README-CN.md)

---

## Architecture

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## Executive Summary

- **Latest AMD CK reproduction (2026-07-07):** AMD's CK A8W8 blockwise GEMM path was reproduced from the original AMD scripts with `decode_full.rc=0` and `prefill_full.rc=0`. Decode mean TPOT matches AMD's CK row within 1.2%; prefill input throughput matches the observed CK 32K-chunk column within 1.2%.
- **CK concurrency extension (2026-07-08):** decode 8K/1K completed through concurrency 256 and plateaued around 2,200 output tok/s from concurrency 64 onward. Prefill 8K/64K completed through concurrency 8; 256K completed at concurrency 1/2 and failed at concurrency 4/8 during warmup with no healthy prefill workers.
- **Prefill:** MI300X/H200 throughput is 51.1% at 8K, 54.9% at 64K, and 214.1% at the validated 256K long-context point.
- **Decode:** with aligned MTP acceptance (`SIMULATE_ACC_LEN=3` on both sides), MI300X is close on TPOT latency; output tok/s is also shown with the same visible-BS-row methodology.
- **Key discovery:** H200's constant `accept_rate=0.75` is simulated via `SGLANG_SIMULATE_ACC_LEN=3`, so H200 TPOT reflects ideal MTP acceptance rather than real draft-model accuracy.

**Prefill throughput (output=1; higher is better)**

| Context | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|
| 8K | 16,323 | 31,950 | 51.1% |
| 64K | 15,047 | 27,400 | 54.9% |
| 256K | 37,252 | 17,400 | **214.1%** |

Prefill does not report TPOT because this benchmark uses `output=1`: there is no steady decode-token phase after the first generated token. Prefill is compared by input-token throughput (`tok/s`); TPOT is reported in the Decode table below.

**Decode 8K/1K, same methodology (`SIMULATE_ACC_LEN=3` on both sides)**

| BS | MI300X Median TPOT | MI300X P99 | H200 TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 14.75 ms | 15.32 ms | 11.59 ms | 1.27x | 973 | 1,381 | 70.5% |
| 32 | 17.82 ms | 18.39 ms | 12.56 ms | 1.42x | 1,518 | 2,549 | 59.6% |
| 64 | 20.42 ms | 20.62 ms | 14.28 ms | 1.43x | 1,852 | 4,483 | 41.3% |
| 128 | 20.31 ms | 20.52 ms | 18.25 ms | **1.11x** | 1,852 | 7,013 | 26.4% |

TPOT: lower is better. Output tok/s: higher is better.

### Methodology Note

The H200 reference data uses two conditions that inflate its numbers beyond real-world behavior:

1. **`fake_topk_ids`** — forces perfectly balanced expert routing (zero straggler overhead)
2. **`SGLANG_SIMULATE_ACC_LEN=3`** — fixes MTP accept_length at 3.0, bypassing real draft model verification

Therefore, the decode comparison in this report only uses the aligned methodology where both sides use `SIMULATE_ACC_LEN=3`. Earlier MI300X runs without this setting are not used in the H200 comparison tables because they mix real draft-model verification with H200's simulated accept-length baseline.

All MI300X numbers use **real expert routing** (not `fake_topk_ids`), adding 5-15% overhead vs the H200 ideal baseline.

---

## 2026-07-07 AMD CK A8W8 GEMM Strict Reproduction

AMD's 2026-07-07 update replaced the triton A8W8 blockwise GEMM path with **CK A8W8 blockwise GEMM bpreshuffle** and added AITER INT8 quick-reduce support. This run follows AMD's original reproduction steps without editing the launch or benchmark scripts; the only execution-carrier adaptation was to keep the foreground prefill, decode, router, and benchmark commands in separate sessions.

- Raw evidence: [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/)
- Result summary: [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md)
- Script snapshot: [`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/)

### Decode 8K/1K — Strict AMD Script Reproduction

N = 256 requests per BS point; target concurrency = 16/32/64/128; `decode_full.rc=0`; no benchmark `ClientPayloadError`, `Traceback`, `Exception`, `ERROR`, `No available`, `unhealthy`, or `TimedOut` markers.

| BS | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | AMD CK mean TPOT ms | Delta vs AMD CK |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,299.18 | 10.64 | 10.83 | 11.57 | 10.59 | +0.5% |
| 32 | 256 | 1,910.75 | 13.50 | 13.73 | 14.25 | 13.43 | +0.5% |
| 64 | 256 | 2,188.05 | 15.10 | 15.53 | 16.58 | 14.92 | +1.2% |
| 128 | 256 | 2,209.43 | 14.52 | 14.83 | 15.82 | 14.55 | -0.2% |

**Interpretation:** the strict reproduction matches AMD's 2026-07-07 CK decode table within about 1.2% on mean TPOT and within about 0.4% on output throughput. This is the strongest evidence that the CK GEMM path materially improves MI300X decode TPOT versus the 6/26 triton-GEMM stack.

### Prefill — Strict AMD Script Reproduction

N = 16 requests per input length; target concurrency = 4; `prefill_full.rc=0`; no benchmark error markers. The observed prefill launch uses `--chunked-prefill-size 32768`, even though the log filename says `chunk_128k`, so the cleanest table comparison is against AMD's CK 32K-chunk column.

| ISL/OSL | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms | AMD CK 32K input tok/s | Delta vs AMD CK |
|---:|---:|---:|---:|---:|---:|---:|
| 8K/1 | 16 | 16,715.80 | 1,849.62 | 2,709.97 | 16,924.08 | -1.2% |
| 64K/1 | 16 | 17,254.14 | 14,107.62 | 16,674.08 | 17,223.51 | +0.2% |
| 256K/1 | 16 | 37,492.80 | 19,278.17 | 86,264.51 | 37,241.84 | +0.7% |

**Caveat:** the router emitted transient `/health` timeout warnings during the long 64K prefill phase, while `/generate` requests continued returning HTTP 200 and both benchmark scripts completed successfully.

---

## 2026-07-08 CK A8W8 Concurrency Extension

This run keeps the 2026-07-07 AMD CK strict reproduction artifacts unchanged and adds a wider concurrency sweep to identify saturation and availability boundaries.

- Raw evidence: [`data/raw-logs/20260708-ck-a8w8-concurrency-extension/`](data/raw-logs/20260708-ck-a8w8-concurrency-extension/)
- Result summary: [`reports/20260708-ck-a8w8-concurrency-extension.md`](reports/20260708-ck-a8w8-concurrency-extension.md)
- Script snapshot: [`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/)

### Decode 8K/1K — High-Concurrency Sweep

N = 256 requests per concurrency point; output length = 1024; warmup requests = 32; `decode_full.rc=0`.

| Concurrency | Successful requests | Output tok/s | Mean TPOT ms | P99 TPOT ms | Mean TTFT ms |
|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,321.50 | 10.79 | 11.65 | 1,191.13 |
| 32 | 256 | 1,914.27 | 13.37 | 14.26 | 2,847.33 |
| 64 | 256 | 2,198.77 | 15.49 | 17.08 | 11,853.11 |
| 96 | 256 | 2,200.63 | 15.06 | 16.31 | 23,666.92 |
| 128 | 256 | 2,203.65 | 14.83 | 16.22 | 33,429.51 |
| 192 | 256 | 2,202.57 | 14.72 | 16.28 | 47,910.53 |
| 256 | 256 | 2,207.97 | 14.60 | 16.36 | 55,466.82 |

**Interpretation:** decode throughput saturates around concurrency 64 and remains stable through concurrency 256. Higher concurrency mainly increases queueing/TTFT rather than output-token throughput.

### Prefill — Concurrency Sweep

N = 16 requests per point; output length = 1; warmup requests = 1. The full prefill matrix exits with `prefill_full.rc=1` because the 256K/con4 and 256K/con8 points fail during warmup.

| Input tokens | Concurrency | rc | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms |
|---:|---:|---:|---:|---:|---:|---:|
| 8192 | 1 | 0 | 16 | 14,811.18 | 552.33 | 589.05 |
| 8192 | 2 | 0 | 16 | 16,982.94 | 958.32 | 1,368.64 |
| 8192 | 4 | 0 | 16 | 16,783.88 | 1,840.95 | 2,680.40 |
| 8192 | 8 | 0 | 16 | 18,617.41 | 3,210.75 | 4,690.96 |
| 65536 | 1 | 0 | 16 | 16,602.69 | 3,946.37 | 4,869.77 |
| 65536 | 2 | 0 | 16 | 18,077.28 | 7,122.69 | 9,003.76 |
| 65536 | 4 | 0 | 16 | 16,904.74 | 14,231.93 | 16,774.44 |
| 65536 | 8 | 0 | 16 | 17,252.39 | 24,482.37 | 31,726.89 |
| 262144 | 1 | 0 | 16 | 35,452.56 | 6,995.06 | 22,647.57 |
| 262144 | 2 | 0 | 16 | 37,429.63 | 12,417.08 | 47,335.03 |
| 262144 | 4 | 1 | NA | NA | NA | NA |
| 262144 | 8 | 1 | NA | NA | NA | NA |

**Failure boundary:** 256K/con4 and 256K/con8 both fail before measurement during warmup with `No available prefill workers (all circuits open or unhealthy)`. This is an availability/circuit-health boundary for very long-context prefill concurrency, not a measured throughput regression.

---

## 2026-06-26 AMD aiter+MTP3 Stack and Aligned Result

AMD provided an updated 1P1D MI300X test stack on 2026-06-26:

| Component | 2026-06-26 stack |
|-----------|------------------|
| SGLang | `sammysun0711/sglang` branch `mimo_aiter_attn`, local package `0.0.0.dev14146+gdb840d935.d20260626` |
| aiter | `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` |
| Runtime | 1P1D PD router, prefill and decode both using `aiter backend + MTP=3` |

> **Raw benchmark logs** for reproducibility verification are archived under [`data/raw-logs/`](data/raw-logs/). The latest AMD CK strict reproduction is under [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/). H200 decode comparisons use the aligned `SIMULATE_ACC_LEN=3` logs under [`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/).

> **Decode metric provenance**: MI300X TPOT and output tok/s are measured directly from SGLang `bench_serving` logs. H200 TPOT and output tok/s are taken from Xiaomi's H200 reference sheet. The H200 output tok/s column equals `BS × 1000 / TPOT` and is shown as the sheet's visible-BS-row throughput.

### Prefill Throughput — 2026-06-26

| Input | MI300X aiter+MTP3 tok/s | H200 EP16/DP2 tok/s | MI300X/H200 EP16/DP2 | H200 EP32/DP4 tok/s | MI300X/H200 EP32/DP4 |
|---:|---:|---:|---:|---:|---:|
| 8K | 16,323.45 | 31,950 | 51.1% | 27,500 | 59.4% |
| 64K | 15,047.08 | 27,400 | 54.9% | 23,000 | 65.4% |
| 256K | 37,251.55 | 17,400 | 214.1% | 13,425 | 277.5% |

This prefill section reports throughput only. Since the run generates one token (`output=1`), TPOT is not a meaningful steady-state metric here.

### Critical Discovery: H200 accept_rate = 0.75 Is Simulated, Not Real

The Xiaomi H200 reference sheet uses `SGLANG_SIMULATE_ACC_LEN=3` with `SGLANG_SIMULATE_ACC_METHOD=match-expected` to **fix MTP accept_length at 3.0** across all scenarios. This was confirmed during AMD/SGLang technical review and is also visible in the SGLang source code (`sglang/srt/speculative/eagle_utils.py` L519-530): when `SIMULATE_ACC_LEN > 0`, the real verification result is **completely replaced** with a simulated accept_index — `predict.fill_(100)` and `num_correct_drafts.fill_(simulate_acc_len - 1)`. The H200 sheet's constant 0.75 accept_rate across all BS/context combinations (zero variance) is consistent with this simulated behavior.

This means the H200 TPOT numbers reflect **pure kernel latency with ideal MTP acceleration**, not real draft model prediction accuracy. The correct same-methodology comparison requires running MI300X with the same `SIMULATE_ACC_LEN=3` setting.

### Decode 8K/1K — Same Methodology (both sides SIMULATE_ACC_LEN=3)

Raw logs: [`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/)  
N = 256 requests per BS point; input=8192, output=1024, seed=12345, warmup=32.

| BS | MI300X Median TPOT (ms) | MI300X P99 (ms) | H200 TPOT (ms) | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 14.75 | 15.32 | 11.59 | 1.27x | 973.06 | 1,380.71 | 70.5% |
| 32 | 17.82 | 18.39 | 12.56 | 1.42x | 1,518.15 | 2,548.66 | 59.6% |
| 64 | 20.42 | 20.62 | 14.28 | 1.43x | 1,852.16 | 4,482.93 | 41.3% |
| 128 | 20.31 | 20.52 | 18.25 | **1.11x** | 1,851.63 | 7,013.05 | 26.4% |

**Key takeaway**: with the same simulated accept_length=3 (matching the H200 test methodology), MI300X decode Median TPOT is **1.11-1.43x** of H200. At BS=128, MI300X is within 11% of H200 per-path decode latency (N=256, P99 spread <1ms). The output tok/s ratio is lower because it reflects serving topology and scheduling in addition to per-token latency.

### Real Benchmark Output Sample

Below is a representative raw output from the same-methodology decode benchmark (BS=128, `SIMULATE_ACC_LEN=3`), showing exactly what the benchmark tool reports:

```
============ Serving Benchmark Result ============
Traffic request rate:                    inf
Max request concurrency:                 128
Successful requests:                     256
Benchmark duration (s):                  141.68
Total input tokens:                      2,097,152
Total generated tokens:                  262,144
Request throughput (req/s):              1.81
Input token throughput (tok/s):          14,803.47
Output token throughput (tok/s):         1,851.63
Peak concurrent requests:                133
Total token throughput (tok/s):          16,655.10
Concurrency:                             104.85
Median E2E Latency (ms):                 62,099.76
---------------Time to First Token----------------
Median TTFT (ms):                        41,716.67
-----Time per Output Token (excl. 1st token)------
Mean TPOT (ms):                          19.71
Median TPOT (ms):                        20.31
P90 TPOT (ms):                           20.45
P95 TPOT (ms):                           20.49
P99 TPOT (ms):                           20.52
```

> Source: [`data/raw-logs/20260626-simulate-acc3/decode_8k1k_bs128.txt`](data/raw-logs/20260626-simulate-acc3/decode_8k1k_bs128.txt). The H200 reference reports Median TPOT = 18.25 ms at the same BS=128, giving a ratio of 20.31/18.25 = **1.11×**.

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
| SGLang | `0.0.0.dev14146+gdb840d935.d20260626` | AMD fork: [sammysun0711/sglang](https://github.com/sammysun0711/sglang) branch `mimo_aiter_attn`, commit `db840d935` |
| ROCm | 7.2.0 | |
| aiter | `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` | [ROCm/aiter](https://github.com/ROCm/aiter), commit `7a8ff7dd4`. MoE/GEMM/FP8/LayerNorm/Attention all enabled. sglang-kernel 0.4.3 |
| Mooncake | `0.3.7.post2` | KV cache transfer for PD disaggregation |
| PyTorch | 2.9.1+rocm7.2.0 | ROCm backend |
| triton | 3.6.0+git42270451 | Custom ROCm build |

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

## Reproducing 2026-06-26 Results

All scripts, environment info, and raw logs needed to reproduce the 6/26 benchmark are archived in this repo under [`scripts/20260626-amd-stack/`](scripts/20260626-amd-stack/).

### Prerequisites

- 2× Azure `Standard_ND96isr_MI300X_v5` nodes (VMSS, same placement group for IB)
- Docker image: `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` (SHA: `bb9d2e5ab1a6`)
- Model: [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) downloaded to `/data/models/MiMo-V2.5-Pro`
- SGLang: `sammysun0711/sglang` branch `mimo_aiter_attn`, commit `db840d935` — source at `/sgl-workspace/sglang_0625`
- aiter: `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4`, commit `7a8ff7dd4` — source at `/sgl-workspace/aiter_0625`

### Container Runtime Requirements

The AMD reference path depends on container-level RDMA access. These requirements are part of the reproduction recipe, not optional tuning:

| Requirement | Why it matters | Verification |
|---|---|---|
| `--privileged`, `/dev/mem`, `CAP_SYS_ADMIN` | Allows Mooncake to discover and use RDMA HCAs for KV-cache transfer | `ls /dev/infiniband/uverbs0 && ls /dev/mem` inside the container |
| No stale same-name source tree, especially `/sgl-workspace/aiter` | Prevents Python import shadowing of `/sgl-workspace/aiter_0625` | `test ! -d /sgl-workspace/aiter` |
| Explicit benchmark source tree | Prevents namespace-package drift in benchmark client imports | `PYTHONPATH=/sgl-workspace/sglang_0625/python` and import-check `sglang.benchmark.datasets` |

The original AMD BS16/32/64/128 fixed-acceptance matrix is already archived in this repo. The section below documents how to rebuild a new environment so the same AMD benchmark scripts can be run on fresh MI300X VMs.

### Clean-Room Run Gates

These gates are required. They are the failure points that caused earlier false starts: stale `sglang.launch_server` processes, router circuit-breaker state, health checks without worker registration, and overwritten benchmark logs.

### Step-by-Step

```bash
# 1. Start a fresh container on both nodes.
#    Use a new container name for each clean-room reproduction run.
CONTAINER=sglang
docker run -d --name $CONTAINER \
  --privileged \
  --ipc=host --network=host --shm-size=256g \
  --device=/dev/kfd --device=/dev/dri --device=/dev/mem \
  --group-add video \
  --cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined --security-opt label=disable \
  -v /data:/data rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510 sleep infinity

# 1a. RDMA gate (both nodes, before installing anything)
#    This must pass. If it fails, Mooncake will fall back to TCP and BS64 throughput drops by about 3x.
docker exec $CONTAINER bash -c "ls /dev/infiniband/uverbs0 && ls /dev/mem && echo RDMA_DEVICE_OK"

# 2. Clone SGLang + aiter source inside container (both nodes)
docker exec -it $CONTAINER bash
mkdir -p /sgl-workspace && cd /sgl-workspace
git clone https://github.com/sammysun0711/sglang.git sglang_0625
cd sglang_0625 && git checkout db840d935
cd /sgl-workspace
git clone https://github.com/ROCm/aiter.git aiter_0625
cd aiter_0625 && git checkout 7a8ff7dd4

# 3. Install PD infrastructure if not pre-installed (both nodes)
#    The rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510 image already includes etcd/UCX/OpenMPI.
#    If using a different base image, run setup_amd_pd_infra.sh first:
#    bash /data/xisun/setup_amd_pd_infra.sh

# 4. Install SGLang + aiter + Mooncake (both nodes)
#    IMPORTANT: use --no-deps for SGLang to preserve the base image's ROCm torch/sglang-kernel stack.
#    Without --no-deps, pip will pull CUDA versions of torch, sglang-kernel, and
#    torch_c_dlpack_ext, which breaks the ROCm environment.
#    AITER 0625 expects flydsl >=0.1.8; the AMD original container used flydsl 0.2.0.
#    Install flydsl first, then use --no-deps for aiter to avoid changing unrelated packages.
cd /sgl-workspace/sglang_0625 && pip install -e "python[all_hip]" --no-deps
pip install flydsl==0.2.0 --no-deps
cd /sgl-workspace/aiter_0625 && pip install -e . --no-deps
pip install mooncake-transfer-engine==0.3.7.post2 --no-deps

# 4a. Kernel parity gate (node-specific)
# AMD original runtime used different effective sglang-kernel import precedence:
# - Prefill/router node: sglang-kernel 0.4.3
# - Decode node: sglang-kernel 0.4.2.post1 first in sys.path
# Therefore, do NOT blindly run setup_rocm.py on both nodes if the goal is performance parity.
# On the prefill/router node only:
cd /sgl-workspace/sglang_0625/sgl-kernel && python3 setup_rocm.py install
# On the decode node, first verify the import path before changing anything:
python3 - <<'PY'
import sgl_kernel
print(sgl_kernel.__file__)
PY

# 4b. Benchmark-client import gate
# The benchmark must resolve sglang.benchmark.datasets from the intended source tree.
export PYTHONPATH=/sgl-workspace/sglang_0625/python:${PYTHONPATH:-}
python3 - <<'PY'
import sglang.benchmark.datasets as datasets
print(datasets.__file__)
PY

# 4c. Source-tree shadowing gate
# A stale /sgl-workspace/aiter directory can shadow /sgl-workspace/aiter_0625.
# AMD original did not have this stale directory.
test ! -d /sgl-workspace/aiter || { echo "ERROR: stale /sgl-workspace/aiter shadows aiter_0625"; exit 1; }

# 5. Download model (both nodes, or shared storage)
huggingface-cli download XiaomiMiMo/MiMo-V2.5-Pro --local-dir /data/models/MiMo-V2.5-Pro

# 6. Deploy benchmark scripts from this repo to working directory
#    Exit container first (Ctrl-D), then run on the HOST:
docker exec $CONTAINER mkdir -p /data/xisun
git clone https://github.com/david-xinyuwei/david-share.git
DIR=david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/20260626-amd-stack
docker cp $DIR/launch_tp8_noep_prefill_aiter_mtp.sh $CONTAINER:/data/xisun/
docker cp $DIR/launch_tp8_noep_decode_aiter_mtp.sh $CONTAINER:/data/xisun/
docker cp $DIR/launch_router.sh $CONTAINER:/data/xisun/
docker cp $DIR/run_benchmark_mimo_pro_decode.sh $CONTAINER:/data/xisun/
docker cp $DIR/run_benchmark_mimo_pro_prefill.sh $CONTAINER:/data/xisun/
docker cp $DIR/setup_amd_pd_infra.sh $CONTAINER:/data/xisun/

# 7. Verify environment (both nodes, inside container)
#    Run these checks before launching servers:
docker exec $CONTAINER bash -c "ibdev2netdev | grep mlx5"          # should show mlx5_ib0..7 Up
docker exec $CONTAINER bash -c "pip show sglang amd-aiter mooncake-transfer-engine | grep -E 'Name:|Version:'"
#    Expected: sglang 0.0.0.dev14146+..., amd-aiter 0.1.14rc1.dev213+..., mooncake 0.3.7.post2

# 8. Find IB IPs for your two nodes
#    Run on each node (HOST shell):
docker exec $CONTAINER ibdev2netdev | head -1   # e.g. mlx5_ib0 port 1 ==> ib0 (Up)
docker exec $CONTAINER bash -c "ip addr show ib0 | grep inet"  # get the 172.16.x.x IP
export PREFILL_IB_IP=<your-prefill-node-ib-ip>   # e.g. 172.16.1.26
export DECODE_IB_IP=<your-decode-node-ib-ip>      # e.g. 172.16.1.122

# 9. Clean process and port gate before launching servers (both nodes)
#    Do this before every clean-room run. Router / worker state from a previous run can make /health misleading.
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|sglang_router.launch_router|bench_serving' || true"
docker exec $CONTAINER bash -c "ss -ltnp | grep -E ':(30000|30001|40000)' || true"
docker exec $CONTAINER bash -c "ps -eo pid,stat,cmd | grep defunct | grep -v grep || true"

# 10. Launch servers (each in a SEPARATE terminal/tmux pane — they run in foreground)
# Terminal A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/xisun && LOG_DIR=/data/xisun/cleanroom_logs bash launch_tp8_noep_prefill_aiter_mtp.sh"
# Terminal B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/xisun && LOG_DIR=/data/xisun/cleanroom_logs bash launch_tp8_noep_decode_aiter_mtp.sh"
# Terminal C — Node 1 (router, AFTER both servers print 'ready'):
docker exec $CONTAINER bash -c "cd /data/xisun && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP LOG_DIR=/data/xisun/cleanroom_logs bash launch_router.sh"
# Wait for router to print 'Uvicorn running' before proceeding.

# 11. Health and router registry gate
# Run on the prefill node after prefill/decode/router are up.
curl -fsS http://127.0.0.1:30000/health   # prefill node
ssh <decode-node> "curl -fsS http://127.0.0.1:30001/health"   # decode node
curl -fsS http://127.0.0.1:40000/health   # router on prefill node

# A tiny request must pass before full benchmark. /health alone is not enough.
docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 12. Run benchmarks (Node 1, through router port 40000)
# Use a unique evidence directory for every clean-room attempt to avoid overwriting old logs.
RUN_DIR=/data/xisun/verify-cleanroom-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/bench_decode && cd /data/xisun && LOG_DIR=$RUN_DIR/bench_decode bash run_benchmark_mimo_pro_decode.sh > $RUN_DIR/decode_full.out 2>&1; echo \$? > $RUN_DIR/decode_full.rc"
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/bench_prefill && cd /data/xisun && LOG_DIR=$RUN_DIR/bench_prefill bash run_benchmark_mimo_pro_prefill.sh > $RUN_DIR/prefill_full.out 2>&1; echo \$? > $RUN_DIR/prefill_full.rc"

# Required pass criteria:
docker exec $CONTAINER bash -c "cat $RUN_DIR/decode_full.rc $RUN_DIR/prefill_full.rc"
docker exec $CONTAINER bash -c "grep -c 'Successful requests' $RUN_DIR/decode_full.out"    # expected: 4
docker exec $CONTAINER bash -c "grep -c 'Successful requests' $RUN_DIR/prefill_full.out"   # expected: 3
docker exec $CONTAINER bash -c "grep -c ClientPayloadError $RUN_DIR/decode_full.out $RUN_DIR/prefill_full.out || true"  # expected: 0 each

# 13. Same-methodology decode for H200 comparison (simulated accept_length=3)
#     This reproduces the "Same Methodology" table in the README.
#     Stop the decode server (Ctrl-C in Terminal B), then restart with:
docker exec $CONTAINER bash -c "cd /data/xisun && SGLANG_SIMULATE_ACC_LEN=3 SGLANG_SIMULATE_ACC_METHOD=match-expected LOG_DIR=/data/xisun/cleanroom_logs bash launch_tp8_noep_decode_aiter_mtp.sh"
#     After decode server prints 'ready', re-run decode benchmark:
docker exec -it $CONTAINER bash -c "cd /data/xisun && bash run_benchmark_mimo_pro_decode.sh"
```

> **Note on `--dataset-path`**: The benchmark scripts reference `/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json`. With `--dataset-name random`, the actual prompts are randomly generated and the dataset file is only used for tokenizer vocabulary. You can download it from [HuggingFace](https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/tree/main) or simply remove the `--dataset-path` line if using SGLang ≥ 0.5.x which has a built-in random generator.

### Archived Evidence

| Path | Content |
|------|---------|
| [`scripts/20260626-amd-stack/`](scripts/20260626-amd-stack/) | All launch + benchmark scripts + environment snapshot |
| [`scripts/20260626-amd-stack/environment_snapshot.txt`](scripts/20260626-amd-stack/environment_snapshot.txt) | Full pip list, git commits, docker image SHA, VM IPs |
| [`scripts/20260626-amd-stack/Dockerfile.sglang`](scripts/20260626-amd-stack/Dockerfile.sglang) | SGLang upstream CUDA Dockerfile (reference only — not used to build the MI300X image) |
| [`scripts/20260626-amd-stack/Dockerfile.mooncake`](scripts/20260626-amd-stack/Dockerfile.mooncake) | Mooncake upstream Dockerfile (reference only) |
| [`scripts/20260626-amd-stack/setup_amd_pd_infra.sh`](scripts/20260626-amd-stack/setup_amd_pd_infra.sh) | AMD PD infrastructure setup (etcd, UCX, OpenMPI) |
| [`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/) | Raw benchmark logs (simulated accept_length=3) |

### Environment Snapshot (2026-06-26)

```
Docker: rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510
SGLang: 0.0.0.dev14146+gdb840d935.d20260626 (sammysun0711/sglang@mimo_aiter_attn)
aiter:  amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4
torch:  2.9.1+rocm7.2.0.lw.git7e1940d4
triton: 3.6.0+git42270451
sglang-kernel: prefill/router node 0.4.3; decode node 0.4.2.post1 in the AMD original runtime
mooncake: 0.3.7.post2
```

---

---

## Known Issues (Current 6/26 Stack)

| Issue | Status | Impact |
|-------|--------|--------|
| **CUDA Graph on decode** | ⚠️ Critical config | Decode server must NOT use `--disable-cuda-graph`. Disabling causes 5× TPOT regression. Prefill server should disable it. |
| **256K repeated prefill** | ⚠️ Stability | Single 256K requests work (37,252 tok/s); concurrent/repeated may stall via PD router drain. |


## Scripts and Files Inventory

### 2026-06-26 AMD Stack

| Script | Purpose | Run on |
|--------|---------|--------|
| [`scripts/20260626-amd-stack/launch_tp8_noep_prefill_aiter_mtp.sh`](scripts/20260626-amd-stack/launch_tp8_noep_prefill_aiter_mtp.sh) | Start prefill server (aiter+MTP3, port 30000) | Node 1 |
| [`scripts/20260626-amd-stack/launch_tp8_noep_decode_aiter_mtp.sh`](scripts/20260626-amd-stack/launch_tp8_noep_decode_aiter_mtp.sh) | Start decode server (aiter+MTP3, port 30001) | Node 2 |
| [`scripts/20260626-amd-stack/launch_router.sh`](scripts/20260626-amd-stack/launch_router.sh) | Start PD router (port 40000) | Node 1 |
| [`scripts/20260626-amd-stack/run_benchmark_mimo_pro_decode.sh`](scripts/20260626-amd-stack/run_benchmark_mimo_pro_decode.sh) | Decode benchmark: 8K/1K, BS=16/32/64/128 | Node 1 |
| [`scripts/20260626-amd-stack/run_benchmark_mimo_pro_prefill.sh`](scripts/20260626-amd-stack/run_benchmark_mimo_pro_prefill.sh) | Prefill benchmark: 8K/64K/256K, BS=4 | Node 1 |
| [`scripts/20260626-amd-stack/setup_amd_pd_infra.sh`](scripts/20260626-amd-stack/setup_amd_pd_infra.sh) | Install etcd + UCX + OpenMPI (AMD PD infra) | Both |
| [`scripts/20260626-amd-stack/Dockerfile.sglang`](scripts/20260626-amd-stack/Dockerfile.sglang) | SGLang upstream CUDA Dockerfile (reference only) | — |
| [`scripts/20260626-amd-stack/Dockerfile.mooncake`](scripts/20260626-amd-stack/Dockerfile.mooncake) | Mooncake upstream Dockerfile (reference only) | — |
| [`scripts/20260626-amd-stack/environment_snapshot.txt`](scripts/20260626-amd-stack/environment_snapshot.txt) | Full pip list + git commits + docker SHA + VM IPs | — |

### 2026-07-07 AMD CK A8W8 Script Snapshot

| Script | Purpose | Run on |
|--------|---------|--------|
| [`scripts/20260707-amd-ck-a8w8/launch_tp8_noep_prefill_aiter_mtp.sh`](scripts/20260707-amd-ck-a8w8/launch_tp8_noep_prefill_aiter_mtp.sh) | Start prefill server with AITER CK blockscale bpreshuffle enabled | Node 1 |
| [`scripts/20260707-amd-ck-a8w8/launch_tp8_noep_decode_aiter_mtp.sh`](scripts/20260707-amd-ck-a8w8/launch_tp8_noep_decode_aiter_mtp.sh) | Start decode server | Node 2 |
| [`scripts/20260707-amd-ck-a8w8/launch_router.sh`](scripts/20260707-amd-ck-a8w8/launch_router.sh) | Start PD router | Node 1 |
| [`scripts/20260707-amd-ck-a8w8/run_benchmark_mimo_pro_decode.sh`](scripts/20260707-amd-ck-a8w8/run_benchmark_mimo_pro_decode.sh) | Decode benchmark: 8K/1K, BS=16/32/64/128 | Node 1 |
| [`scripts/20260707-amd-ck-a8w8/run_benchmark_mimo_pro_prefill.sh`](scripts/20260707-amd-ck-a8w8/run_benchmark_mimo_pro_prefill.sh) | Prefill benchmark: 8K/64K/256K, BS=4 | Node 1 |

### Data and Logs

| Path | Content |
|------|------|
| `data/raw-logs/20260707-ck-a8w8-gemm/` | Strict AMD-step CK A8W8 benchmark logs, env gates, script SHA256, and status files |
| `data/raw-logs/20260626-simulate-acc3/` | 4 decode logs (simulated accept_length=3) |

### Historical Scripts (6/18 baseline)

| Script | Purpose |
|--------|------|
| `scripts/bench_micro_matrix_2x.sh` | Two-round EP8/DP1 matrix |
| `scripts/bench_256k_prefill_minimal.sh` | 256K isolated diagnostic |
| `scripts/launch_prefill.sh` | PD prefill (6/18 triton) |
| `scripts/launch_decode.sh` | PD decode (6/18 triton) |
| `scripts/launch_router.sh` | PD router (6/18) |
| `scripts/launch_single_node_mtp.sh` | Single-node MTP server |
| `scripts/launch_tp16_dp2_node0.sh` | TP16/DP2 topology probe Node 0 |
| `scripts/launch_tp16_dp2_node1.sh` | TP16/DP2 topology probe Node 1 |

---

## References

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` branch (6/26 latest)](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [AMD SGLang Fork — `Mimo_mtp_enable` branch (6/18 historical)](https://github.com/TianHao65/sglang/tree/Mimo_mtp_enable)
- [AMD MI308X PD Disaggregation Guide](https://github.com/TianHao65/sglang/blob/Mimo_Swa_Eable/MiMo-V2-Flash-MI308X_1P1D_Disaggregated_Inference_Guide.md)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*Last updated: 2026-07-07*
