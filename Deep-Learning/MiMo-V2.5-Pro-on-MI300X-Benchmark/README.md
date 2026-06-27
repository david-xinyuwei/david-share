# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD fork MTP/EAGLE, benchmarked against Xiaomi's H200 reference data.

This repo provides full reproduction scripts, launch commands, benchmark results, and server logs — so anyone with 2× Azure ND96isr_MI300X_v5 nodes and the specified Docker image can reproduce the benchmarks following the step-by-step guide below.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

English | [中文版](README-CN.md)

---

## Architecture

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## Executive Summary

| Dimension | MI300X (6/26 aiter+MTP3) | H200 Reference | Gap | Notes |
|-----------|:---:|:---:|:---:|------|
| **Prefill 8K/64K** | 16,323 / 15,047 tok/s | 31,950 / 27,400 tok/s | H200 1.8-2.0× faster | MI300X EP8/DP1 vs H200 EP16/DP2; both use `fake_topk_ids`=NO on MI300X side |
| **Prefill 256K** | 37,252 tok/s | 17,400 tok/s | MI300X 2.14× faster | Single validated point; requires repeated-run stability confirmation |
| **Decode TPOT (same methodology)** | 14.75-20.31 ms | 11.59-18.25 ms | H200 11-43% faster | Both sides: `SIMULATE_ACC_LEN=3`; BS≥128 gap is only 11% |
| **Key discovery** | H200 accept_rate=0.75 is simulated via `SGLANG_SIMULATE_ACC_LEN=3` | — | — | Confirmed during AMD/SGLang technical review; H200 TPOT reflects ideal MTP, not real draft accuracy |

### Methodology Note

The H200 reference data uses two conditions that inflate its numbers beyond real-world behavior:

1. **`fake_topk_ids`** — forces perfectly balanced expert routing (zero straggler overhead)
2. **`SGLANG_SIMULATE_ACC_LEN=3`** — fixes MTP accept_length at 3.0, bypassing real draft model verification

Therefore, the "same methodology" comparison (both sides use `SIMULATE_ACC_LEN=3`) isolates **pure kernel latency** and is the fairest decode comparison. The "real accept" comparison shows what happens when MI300X uses real MTP verification while H200 uses simulated — it overstates the gap by mixing methodology.

All MI300X numbers use **real expert routing** (not `fake_topk_ids`), adding 5-15% overhead vs the H200 ideal baseline.

---

## Latest 2026-06-26 AMD aiter+MTP3 Result

AMD provided an updated 1P1D MI300X test stack on 2026-06-26:

| Component | 2026-06-26 stack |
|-----------|------------------|
| SGLang | `sammysun0711/sglang` branch `mimo_aiter_attn`, local package `0.0.0.dev14146+gdb840d935.d20260626` |
| aiter | `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` |
| Runtime | 1P1D PD router, prefill and decode both using `aiter backend + MTP=3` |

> **Raw benchmark logs** for reproducibility verification are archived under [`data/raw-logs/`](data/raw-logs/) (12 decode + prefill logs from real-accept and simulated-accept runs).

> **H200 decode throughput note**: The H200 sheet labels `bs (per DP)` with `dp size=4`, but its throughput column equals `BS × 1000 / TPOT`, not `BS × DP × 1000 / TPOT`. All decode comparisons below use the sheet-provided throughput column as-is (visible-BS-row comparison).

### Prefill Throughput — 2026-06-26

| Input | MI300X aiter+MTP3 tok/s | H200 EP16/DP2 tok/s | MI/H200 | H200 faster | H200 EP32/DP4 tok/s | MI/H200 | H200 faster |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 8K | 16,323.45 | 31,950 | 51.1% | 1.96x | 27,500 | 59.4% | 1.68x |
| 64K | 15,047.08 | 27,400 | 54.9% | 1.82x | 23,000 | 65.4% | 1.53x |
| 256K | 37,251.55 | 17,400 | 214.1% | 0.47x | 13,425 | 277.5% | 0.36x |

### Decode 8K/1K — 2026-06-26

| BS row | MI300X TPOT ms | H200 TPOT ms | MI latency slower | MI300X output tok/s | H200 output tok/s | MI/H200 throughput | H200 faster | MI accept len/rate | H200 accept rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 21.61 | 11.59 | 1.86x | 689.22 | 1,380.71 | 49.9% | 2.00x | 2.38/0.46 | 0.75 |
| 32 | 27.94 | 12.56 | 2.22x | 1,017.58 | 2,548.66 | 39.9% | 2.50x | 2.34/0.44 | 0.75 |
| 64 | 34.78 | 14.28 | 2.44x | 1,391.54 | 4,482.93 | 31.0% | 3.22x | 2.25/0.41 | 0.75 |
| 128 | 34.70 | 18.25 | 1.90x | 1,396.29 | 7,013.05 | 19.9% | 5.02x | 2.15/0.38 | 0.75 |

**Interpretation**: the 6/26 stack improves aiter+MTP acceptance versus the 6/19 run (`accept_length` rises from ~1.6 to 2.15-2.38), but it still does not reach H200's 0.75 accept rate and decode throughput remains H200-led on the 8K/1K sheet rows.

### Critical Discovery: H200 accept_rate = 0.75 Is Simulated, Not Real

The Xiaomi H200 reference sheet uses `SGLANG_SIMULATE_ACC_LEN=3` with `SGLANG_SIMULATE_ACC_METHOD=match-expected` to **fix MTP accept_length at 3.0** across all scenarios. This was confirmed during AMD/SGLang technical review and is also visible in the SGLang source code (`sglang/srt/speculative/eagle_utils.py` L519-530): when `SIMULATE_ACC_LEN > 0`, the real verification result is **completely replaced** with a simulated accept_index — `predict.fill_(100)` and `num_correct_drafts.fill_(simulate_acc_len - 1)`. The H200 sheet's constant 0.75 accept_rate across all BS/context combinations (zero variance) is consistent with this simulated behavior.

This means the H200 TPOT numbers reflect **pure kernel latency with ideal MTP acceleration**, not real draft model prediction accuracy. The correct same-methodology comparison requires running MI300X with the same `SIMULATE_ACC_LEN=3` setting.

### Decode 8K/1K — Same Methodology (both sides SIMULATE_ACC_LEN=3)

Raw logs: [`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/)  
N = 256 requests per BS point; input=8192, output=1024, seed=12345, warmup=32.

| BS | MI300X Median TPOT (ms) | MI300X P99 (ms) | H200 TPOT (ms) | MI300X slower | Gap |
|---:|---:|---:|---:|---:|---:|
| 16 | 14.75 | 15.32 | 11.59 | 1.27x | H200 faster by 27% |
| 32 | 17.82 | 18.39 | 12.56 | 1.42x | H200 faster by 42% |
| 64 | 20.42 | 20.62 | 14.28 | 1.43x | H200 faster by 43% |
| 128 | 20.31 | 20.52 | 18.25 | **1.11x** | H200 faster by **11%** |

**Key takeaway**: with the same simulated accept_length=3 (matching the H200 test methodology), the MI300X decode Median TPOT gap shrinks from 1.86-2.44x to **1.11-1.43x**. At BS≥128, MI300X is within 11% of H200 per-path decode latency (N=256, P99 spread <1ms). The remaining gap at lower BS is primarily due to topology differences (MI300X EP8/DP1 vs H200 EP32/DP4) and the aiter vs FA3 kernel efficiency difference.

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

### Remaining Decode Throughput Gap Explained

Even with same-methodology TPOT, MI300X throughput plateaus at ~1,852 tok/s at BS≥64 while H200 reports 4,483-7,013 tok/s. This is because:

1. **DP=1 vs DP=4**: MI300X has a single decode server; H200's throughput is per-DP-rank but with 4x more parallelism available
2. **H200 throughput is formula-computed** (`BS × 1000 / TPOT`), while MI300X throughput is end-to-end measured (includes PD router overhead, KV transfer latency, scheduler gaps)
3. **MI300X scheduler saturation**: output throughput stops growing at BS≥64, indicating the single decode server hits a scheduling ceiling

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

## Reproducing 2026-06-26 Results (Latest)

All scripts, environment info, and raw logs needed to reproduce the 6/26 benchmark are archived in this repo under [`scripts/20260626-amd-stack/`](scripts/20260626-amd-stack/).

### Prerequisites

- 2× Azure `Standard_ND96isr_MI300X_v5` nodes (VMSS, same placement group for IB)
- Docker image: `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` (SHA: `bb9d2e5ab1a6`)
- Model: [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) downloaded to `/data/models/MiMo-V2.5-Pro`
- SGLang: `sammysun0711/sglang` branch `mimo_aiter_attn`, commit `db840d935` — source at `/sgl-workspace/sglang_0625`
- aiter: `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4`, commit `7a8ff7dd4` — source at `/sgl-workspace/aiter_0625`

### Step-by-Step

```bash
# 1. Start container on both nodes
docker run -d --name sglang --ipc=host --network=host --device=/dev/kfd --device=/dev/dri \
  --group-add video --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  -v /data:/data rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510 sleep infinity

# 2. Clone SGLang + aiter source inside container (both nodes)
docker exec -it sglang bash
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
cd /sgl-workspace/sglang_0625/sgl-kernel && python3 setup_rocm.py install
cd /sgl-workspace/sglang_0625 && pip install -e "python[all_hip]"
cd /sgl-workspace/aiter_0625 && pip install -e .
pip install mooncake-transfer-engine==0.3.7.post2

# 5. Download model (both nodes, or shared storage)
huggingface-cli download XiaomiMiMo/MiMo-V2.5-Pro --local-dir /data/models/MiMo-V2.5-Pro

# 6. Deploy benchmark scripts from this repo to working directory
#    Exit container first (Ctrl-D), then run on the HOST:
docker exec sglang mkdir -p /data/xisun
git clone https://github.com/david-xinyuwei/david-share.git
DIR=david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/20260626-amd-stack
docker cp $DIR/launch_tp8_noep_prefill_aiter_mtp.sh sglang:/data/xisun/
docker cp $DIR/launch_tp8_noep_decode_aiter_mtp.sh sglang:/data/xisun/
docker cp $DIR/launch_router.sh sglang:/data/xisun/
docker cp $DIR/run_benchmark_mimo_pro_decode.sh sglang:/data/xisun/
docker cp $DIR/run_benchmark_mimo_pro_prefill.sh sglang:/data/xisun/
docker cp $DIR/setup_amd_pd_infra.sh sglang:/data/xisun/

# 7. Verify environment (both nodes, inside container)
#    Run these checks before launching servers:
docker exec sglang bash -c "ibdev2netdev | grep mlx5"          # should show mlx5_ib0..7 Up
docker exec sglang bash -c "pip show sglang amd-aiter mooncake-transfer-engine | grep -E 'Name:|Version:'"
#    Expected: sglang 0.0.0.dev14146+..., amd-aiter 0.1.14rc1.dev213+..., mooncake 0.3.7.post2

# 8. Find IB IPs for your two nodes
#    Run on each node (HOST shell):
docker exec sglang ibdev2netdev | head -1   # e.g. mlx5_ib0 port 1 ==> ib0 (Up)
docker exec sglang bash -c "ip addr show ib0 | grep inet"  # get the 172.16.x.x IP
export PREFILL_IB_IP=<your-prefill-node-ib-ip>   # e.g. 172.16.1.26
export DECODE_IB_IP=<your-decode-node-ib-ip>      # e.g. 172.16.1.122

# 9. Launch servers (each in a SEPARATE terminal/tmux pane — they run in foreground)
# Terminal A — Node 1 (prefill):
docker exec sglang bash -c "cd /data/xisun && bash launch_tp8_noep_prefill_aiter_mtp.sh"
# Terminal B — Node 2 (decode):
docker exec sglang bash -c "cd /data/xisun && bash launch_tp8_noep_decode_aiter_mtp.sh"
# Terminal C — Node 1 (router, AFTER both servers print 'ready'):
docker exec sglang bash -c "cd /data/xisun && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP bash launch_router.sh"
# Wait for router to print 'Uvicorn running' before proceeding to step 10.

# 10. Run benchmarks (Node 1, through router port 40000)
docker exec -it sglang bash -c "cd /data/xisun && bash run_benchmark_mimo_pro_decode.sh"   # Decode: 8K/1K, BS=16/32/64/128
docker exec -it sglang bash -c "cd /data/xisun && bash run_benchmark_mimo_pro_prefill.sh"  # Prefill: 8K/64K/256K, BS=4

# 11. Same-methodology decode for H200 comparison (simulated accept_length=3)
#     This reproduces the "Same Methodology" table in the README.
#     Stop the decode server (Ctrl-C in Terminal B), then restart with:
docker exec sglang bash -c "cd /data/xisun && SGLANG_SIMULATE_ACC_LEN=3 SGLANG_SIMULATE_ACC_METHOD=match-expected bash launch_tp8_noep_decode_aiter_mtp.sh"
#     After decode server prints 'ready', re-run decode benchmark:
docker exec -it sglang bash -c "cd /data/xisun && bash run_benchmark_mimo_pro_decode.sh"
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
| [`data/raw-logs/20260626-amd-aiter-mtp/`](data/raw-logs/20260626-amd-aiter-mtp/) | Raw benchmark logs (real acceptance) |
| [`data/raw-logs/20260626-simulate-acc3/`](data/raw-logs/20260626-simulate-acc3/) | Raw benchmark logs (simulated accept_length=3) |

### Environment Snapshot (2026-06-26)

```
Docker: rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510
SGLang: 0.0.0.dev14146+gdb840d935.d20260626 (sammysun0711/sglang@mimo_aiter_attn)
aiter:  amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4
torch:  2.9.1+rocm7.2.0.lw.git7e1940d4
triton: 3.6.0+git42270451
sglang-kernel: 0.4.3
mooncake: 0.3.7.post2
```

---

---

## Known Issues (Current 6/26 Stack)

| Issue | Status | Impact |
|-------|--------|--------|
| **aiter + MTP acceptance gap** | ⚠️ Improved, still open | accept_length 2.15-2.38 / accept_rate 0.38-0.46 on MI300X vs H200 simulated 0.75. Gap is software (draft model calibration), not hardware. |
| **CUDA Graph on decode** | ⚠️ Critical config | Decode server must NOT use `--disable-cuda-graph`. Disabling causes 5× TPOT regression. Prefill server should disable it. |
| **DP=1 throughput ceiling** | ⚠️ Topology limitation | Single decode server saturates at ~1,852 tok/s (BS≥64). H200 uses DP=4. AMD working on TP16/DP2 support. |
| **256K repeated prefill** | ⚠️ Stability | Single 256K requests work (37,252 tok/s); concurrent/repeated may stall via PD router drain. |


## Scripts and Files Inventory

### 2026-06-26 AMD Stack (Latest)

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

### Data and Logs

| Path | Content |
|------|------|
| `data/raw-logs/20260626-amd-aiter-mtp/` | 8 benchmark logs (real MTP acceptance) |
| `data/raw-logs/20260626-simulate-acc3/` | 4 decode logs (simulated accept_length=3) |
| `data/amd_aiter_mtp_20260626_h200_alignment.tsv` | Parsed alignment ratios (10 rows) |
| `reports/amd_aiter_mtp_20260626_h200_alignment.md` | Structured alignment analysis |

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

*Last updated: 2026-06-27*
