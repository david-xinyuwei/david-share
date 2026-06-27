# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD fork MTP/EAGLE, benchmarked against Xiaomi's H200 reference data.

This repo provides full reproduction scripts, launch commands, benchmark results, and server logs — so anyone with access to the same hardware can reproduce every number.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

English | [中文版](README-CN.md)

---

## Latest 2026-06-26 AMD aiter+MTP3 Result

AMD provided an updated 1P1D MI300X test stack on 2026-06-26:

| Component | 2026-06-26 stack |
|-----------|------------------|
| SGLang | `sammysun0711/sglang` branch `mimo_aiter_attn`, local package `0.0.0.dev14146+gdb840d935.d20260626` |
| aiter | `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` |
| Runtime | 1P1D PD router, prefill and decode both using `aiter backend + MTP=3` |

Evidence and parsed alignment files:

- 2026-06-26 alignment report: [`reports/amd_aiter_mtp_20260626_h200_alignment.md`](reports/amd_aiter_mtp_20260626_h200_alignment.md)
- Parsed TSV: [`data/amd_aiter_mtp_20260626_h200_alignment.tsv`](data/amd_aiter_mtp_20260626_h200_alignment.tsv)
- Raw logs: [`data/raw-logs/20260626-amd-aiter-mtp/`](data/raw-logs/20260626-amd-aiter-mtp/)

### Short Answer: Matched 2026-06-26 Ratio

| Track | Matched point | MI300X / H200 | Readout |
|-------|---------------|---------------|---------|
| Prefill vs H200 EP16/DP2 | 8K and 64K, BS=4 | 0.51-0.55x | H200 is about **1.8-2.0x faster** |
| Prefill vs H200 EP16/DP2 | 256K, BS=4 | 2.14x | MI300X is **2.14x faster** in this specific 6/26 long-context run; keep this as a validated 6/26 point, not a general 256K stability claim |
| Decode 8K/1K (real accept) | Same visible BS rows, MI300X real accept 0.38-0.46 vs H200 simulated 0.75 | 0.50x → 0.20x throughput | H200 is **2.0x faster at BS16**, **5.0x faster at BS128** — but this comparison is **not same-methodology** (see below) |
| **Decode 8K/1K (same methodology)** | Both sides use `SGLANG_SIMULATE_ACC_LEN=3` to fix accept_length=3 | **Median TPOT gap = 1.11-1.43x only** | **BS≥128: MI300X within 11% of H200 per-path TPOT** |

The key cleanup is the H200 decode denominator. The H200 sheet labels `bs (per DP)` with `dp size=4`, but its throughput column equals `BS * 1000 / TPOT`, not `BS * DP * 1000 / TPOT`. Therefore the main decode comparison below uses the sheet-provided throughput column as a **visible-BS-row comparison**. Multiplying the H200 sheet again by DP=4 would change the definition of the published H200 number.

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

The Xiaomi H200 reference sheet uses `SGLANG_SIMULATE_ACC_LEN=3` with `SGLANG_SIMULATE_ACC_METHOD=match-expected` to **fix MTP accept_length at 3.0** across all scenarios. This was confirmed by AMD's SGLang team (source: AMD engineer 孙霞克, 2026-06-26 WeChat). The SGLang source code (`sglang/srt/speculative/eagle_utils.py` L519-530) shows that when `SIMULATE_ACC_LEN > 0`, the real verification result is **completely replaced** with a simulated accept_index — `predict.fill_(100)` and `num_correct_drafts.fill_(simulate_acc_len - 1)`. The H200 sheet's constant 0.75 accept_rate across all BS/context combinations (zero variance) is consistent with this simulated behavior.

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

### Remaining Decode Throughput Gap Explained

Even with same-methodology TPOT, MI300X throughput plateaus at ~1,852 tok/s at BS≥64 while H200 reports 4,483-7,013 tok/s. This is because:

1. **DP=1 vs DP=4**: MI300X has a single decode server; H200's throughput is per-DP-rank but with 4x more parallelism available
2. **H200 throughput is formula-computed** (`BS × 1000 / TPOT`), while MI300X throughput is end-to-end measured (includes PD router overhead, KV transfer latency, scheduler gaps)
3. **MI300X scheduler saturation**: output throughput stops growing at BS≥64, indicating the single decode server hits a scheduling ceiling

---

## Previous H200-Aligned Baseline (2026-06-18)

The latest valid run uses the PD router path, fixed random input lengths, `chunked-prefill-size=16384`, and MTP/EAGLE layer=3. The completed MI300X baseline is `TP=8, local EP=8, DP=1`; Xiaomi's H200 reference uses stronger global EP/DP settings (`attn TP=8, DP=2, global EP=16` for prefill and `attn TP=8, DP=4, global EP=32` for decode), so the completed numbers below are an aligned workload comparison rather than an identical-topology comparison.

There is now a separate topology probe for the H200 prefill shape: `--tp-size 16 --dp-size 2 --enable-dp-attention`. In the current SGLang AMD fork, this gives `effective_attn_tp = tp_size / dp_size = 8`, matching MiMo-V2.5-Pro's fused-QKV requirement (`num_key_value_heads=8`). The probe passed the model/config validation path but failed before server readiness with MORI dispatch heap pressure, so it has **no performance numbers yet**.

Full two-round report: [`reports/micro_matrix_2x_report_20260618.md`](reports/micro_matrix_2x_report_20260618.md)  
Raw two-round summary: [`data/micro_matrix_2x_summary_20260618.tsv`](data/micro_matrix_2x_summary_20260618.tsv)  
256K diagnostic report: [`reports/diagnostic_256k_minimal_20260618.md`](reports/diagnostic_256k_minimal_20260618.md)  
Raw 256K diagnostic summary: [`data/diagnostic_256k_minimal_20260618.tsv`](data/diagnostic_256k_minimal_20260618.tsv)  
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
| TP16/DP2 probe | `TP=16, DP=2, enable-dp-attention`, 2-node single server | Startup probe failed before ready: MORI heap OOM plus HIP invalid argument in dispatch/combine | The corrected H200 topology expression passes the MiMo-V2.5-Pro effective-attention-TP validation, but current MORI/runtime sizing cannot yet sustain the server |

### Current Summary

#### H200 Alignment Matrix — 6 Scenarios

**Prefill Throughput** (input=context_len, output=1, BS=4, MTP=3)

| Context | MI300X EP8 (tok/s) | H200 EP16/DP2 (tok/s) | H200 EP32/DP4 (tok/s) | MI300X / H200 EP16 | Status |
|---:|---:|---:|---:|---:|:---:|
| **8K** | 13,531 | 31,950 | 27,500 | **42.4%** | ✅ |
| **64K** | 11,500 | 27,400 | 23,000 | **42.0%** | ✅ |
| **256K** | 7,239 (isolated single-req avg) | 17,400 | 13,425 | **41.6% single / ❌ concurrent** | ⚠️ |

> 256K repeated/concurrent prefill remains unstable. The isolated single-request diagnostic confirms the compute path is viable at ~7.2K tok/s, but sequential `n=4` stalls after partial progress.

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
| **256K** | 16 | — | 13.93 | — | ❌ stuck |
| | 32 | — | 16.94 | — | ❌ stuck |

### Key Findings

1. **Decode 8K (BS≥192): MI300X matches or beats H200 with triton+MTP.** MI300X TPOT plateaus at ~22ms from BS64+, while H200 degrades linearly. Crossover at BS192.
2. **Decode 64K: 1.23-1.95× slower (triton+MTP) / 1.4-1.7× slower (aiter no-MTP).** Flat TPOT regardless of BS — memory-bandwidth bound on long-context KV access. aiter is slightly better for 64K decode.
3. **Prefill: ~42% of H200 (triton) → ~50-66% of H200 (aiter).** aiter attention kernel unlocks +12%~56% prefill improvement. Biggest gain at 256K context (triton=7.3K → aiter=11.4K tok/s).
4. **aiter + MTP improved on 2026-06-26, but still trails H200 decode.** The 6/19 aiter+MTP run had acceptance rate ~0.2 / accept length ~1.6; the 6/26 stack improves to accept length 2.15-2.38 and accept rate 0.38-0.46 on 8K/1K decode. H200's sheet still reports 0.75 accept rate, and H200 remains 2.0-5.0× faster by the sheet's output-throughput column across BS16-128.
5. **CUDA Graph critical for decode (discovered 2026-06-19)**: Decode server `--disable-cuda-graph` causes 5× TPOT regression (23ms → 120ms). Only prefill should disable CUDA graph.
6. **256K: compute path works, repeated/concurrent PD-router path stalls.** Five isolated 256K prefill requests succeeded at 7,239 tok/s (triton) / 11,410 tok/s (aiter), while sequential `n=4` stalls.
7. **Topology gap remains open.** H200's EP16/DP2 vs MI300X's EP8/DP1 is still a structural difference that contributes to the gap.

### aiter Coverage (Updated 2026-06-19)

| Component | aiter Enabled | Backend | Notes |
|-----------|:---:|:---:|------|
| MoE expert dispatch (fused_moe) | ✅ | CK kernel | 384-expert routing |
| MoE topk routing | ✅ | aiter topk | Expert selection |
| MORI-EP token dispatcher | ✅ | aiter FP8 quant | Cross-GPU communication |
| FP8 quantization | ✅ | aiter per-token FP8 | Weight/activation quantization |
| LayerNorm | ✅ | aiter fused | Fused normalization |
| **Attention (prefill + decode)** | **✅** | **aiter `mha_batch_prefill`** | **Enabled since 2026-06-18 commit `f5fe8e944`** |

> **2026-06-26 Update**: AMD's newer `mimo_aiter_attn` stack with `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` improves aiter+MTP acceptance length from ~1.6 to 2.15-2.38 on 8K/1K decode. It is a real improvement, but not enough to close the H200 decode gap on the published H200 sheet rows. See the latest section above for the matched 6/26 ratios.

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
| SGLang | `0.5.12.post2.dev4` | AMD fork: [TianHao65/sglang](https://github.com/TianHao65/sglang) branch `Mimo_mtp_enable`, commit `f5fe8e944` ("aiter_backend enable") |
| ROCm | 7.2.0 | |
| aiter | `0.1.12.post2.dev150` | MoE/GEMM/FP8/LayerNorm/Attention all enabled. sgl-kernel 0.4.2.post1. |
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

# 2. Install SGLang + aiter inside container (both nodes)
docker exec -it sglang bash
cd /sgl-workspace/sglang_0625/python && pip install -e ".[all_hip]"
cd /sgl-workspace/aiter_0625 && pip install -e .
pip install mooncake-transfer-engine

# 3. Launch Prefill server (Node 1 / VM8)
cd /data/xisun && bash launch_tp8_noep_prefill_aiter_mtp.sh
# See: scripts/20260626-amd-stack/launch_tp8_noep_prefill_aiter_mtp.sh

# 4. Launch Decode server (Node 2 / VM10)
cd /data/xisun && bash launch_tp8_noep_decode_aiter_mtp.sh
# See: scripts/20260626-amd-stack/launch_tp8_noep_decode_aiter_mtp.sh

# 5. Launch PD Router (Node 1, after both servers are healthy)
cd /data/xisun && bash launch_router.sh
# See: scripts/20260626-amd-stack/launch_router.sh

# 6. Run benchmarks (Node 1, through router port 40000)
cd /data/xisun && bash run_benchmark_mimo_pro_decode.sh    # Decode: 8K/1K, BS=16/32/64/128
cd /data/xisun && bash run_benchmark_mimo_pro_prefill.sh   # Prefill: 8K/64K/256K, BS=4

# 7. (Optional) Same-methodology decode with simulated accept_length=3
export SGLANG_SIMULATE_ACC_LEN=3
export SGLANG_SIMULATE_ACC_METHOD=match-expected
# Restart decode server with these env vars, then re-run decode benchmark
```

### Archived Evidence

| Path | Content |
|------|---------|
| [`scripts/20260626-amd-stack/`](scripts/20260626-amd-stack/) | All launch + benchmark scripts + environment snapshot |
| [`scripts/20260626-amd-stack/environment_snapshot.txt`](scripts/20260626-amd-stack/environment_snapshot.txt) | Full pip list, git commits, docker image SHA, VM IPs |
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
- **Prefill**: `--disable-cuda-graph` (prefill does not benefit from cuda graph; long sequences need dynamic memory allocation)
- **Decode**: cuda graph **ON** (no `--disable-cuda-graph` flag — this is critical! Disabling it causes 5× TPOT regression)

> **⚠️ Critical Configuration Note (discovered 2026-06-19)**: The decode server must NOT have `--disable-cuda-graph`. In earlier testing, `--disable-cuda-graph` was mistakenly applied to both P and D servers, causing decode TPOT to degrade from 23ms to 120ms. After removing the flag from decode only, TPOT returned to normal. This applies to both triton and aiter attention backends.

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

## Scenario 3 — aiter Backend, No MTP (2026-06-19)

### Background

AMD's `Mimo_mtp_enable` branch commit `f5fe8e944` enables `--attention-backend aiter` for MiMo-V2.5-Pro. This replaces the triton attention kernel with AMD's optimized CK-based `mha_batch_prefill` (prefill) and fused decode attention. The original 2026-06-19 test showed poor aiter+MTP acceptance, so this historical scenario ran without speculative decoding. AMD's 2026-06-26 stack improves aiter+MTP acceptance; those newer numbers are reported in the latest section at the top of this README.

### Configuration

```
Prefill (VM8):  --attention-backend aiter --kv-cache-dtype fp8_e4m3 --page-size 32 --disable-cuda-graph --mem-fraction-static 0.9
Decode  (VM10): --attention-backend aiter --kv-cache-dtype fp8_e4m3 --page-size 32 --mem-fraction-static 0.9
                (NO --disable-cuda-graph on decode!)
Router:         python3 -m sglang_router.launch_router --pd-disaggregation --prefill ... --decode ...
```

### Results — Prefill Throughput (aiter no-MTP vs triton+MTP)

| Context | aiter no-MTP (tok/s) | triton+MTP (tok/s) | Improvement | H200 (tok/s) |
|:-------:|:---:|:---:|:---:|:---:|
| **8K** | **15,133** | 13,531 | **+12%** | 31,950 |
| **64K** | **16,125** | 11,500 | **+40%** | 27,400 |
| **256K** | **11,410** | 7,294 | **+56%** | 17,400 |

> aiter attention kernel acceleration matches AMD's reported kernel-level speedup (triton 1678μs → aiter 298μs = 5.6×). End-to-end improvement is 12-56% because attention is only part of the pipeline; longer sequences have larger attention fraction → bigger improvement.

### Results — Decode TPOT (aiter no-MTP, CUDA Graph ON)

**8K Context:**

| BS | aiter no-MTP TPOT (ms) | triton+MTP TPOT (ms) | H200 (ms) | aiter/H200 |
|:--:|:---:|:---:|:---:|:---:|
| 16 | 23.23 | 13.71 | 11.59 | 2.0× |
| 32 | 27.29 | 16.53 | 12.56 | 2.2× |
| 64 | 34.62 | 19.70 | 14.28 | 2.4× |
| 128 | 35.96 | 22.16 | 18.25 | 2.0× |
| 192 | 41.79 | 22.56 | 23.29 | 1.8× |
| 256 | 43.64 | 22.86 | 27.38 | 1.6× |

**64K Context:**

| BS | aiter no-MTP TPOT (ms) | triton+MTP TPOT (ms) | H200 (ms) | aiter/H200 |
|:--:|:---:|:---:|:---:|:---:|
| 16 | 20.25 | 23.36 | 11.99 | 1.7× |
| 32 | 20.58 | 23.37 | 14.31 | 1.4× |
| 64 | 22.27 | 24.39 | 16.33 | 1.4× |
| 96 | OOM | 24.18 | 19.63 | — |

### aiter + MTP Compatibility Status

| Metric | triton + MTP=3 | aiter + MTP=3 (2026-06-19) | aiter + MTP=3 (2026-06-26) | aiter no-MTP |
|--------|:---:|:---:|:---:|:---:|
| MTP acceptance_rate | **0.666** | 0.2 | 0.38-0.46 on BS16-128 | N/A |
| MTP accept_length | **3.2** | 1.6 | 2.15-2.38 on BS16-128 | N/A |
| Decode 8K BS16 TPOT | **13.71ms** | 22.78ms | 21.61ms | 23.23ms |
| Decode 8K BS16 output tok/s | — | — | 689.22 | — |

> **Status**: the 6/26 stack shows the aiter+MTP path is no longer the 6/19 failure mode, but it is still below both the prior triton+MTP decode latency and H200's 0.75 accept rate. The remaining gap is visible in output throughput: H200 is 2.0× faster at BS16 and 5.0× faster at BS128 on the 6/26 H200 sheet rows.

### Key Insight — Three Configuration Trade-off

| Config | Prefill tok/s (64K) | Decode 8K TPOT (ms) | Best for |
|--------|:---:|:---:|------|
| ① triton + MTP=3 | 11,500 | **13.71** | Decode-heavy workloads |
| ② aiter + MTP=3 (2026-06-26) | 15,047 | 21.61 | Improved, but still slower than triton+MTP and H200 decode |
| ③ aiter + no-MTP | **16,125** | 23.23 | Prefill-heavy / long-context workloads |

**Conclusion**: aiter+MTP improved on 2026-06-26, but the optimal choice still depends on workload:
- **Short-context, high-BS decode** → Use triton + MTP=3 (config ①)
- **Long-context prefill-heavy** → Use the latest aiter path, while treating the 256K 6/26 result as a point that still needs repeated-run stability validation

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
| **Attention backend** | CUDA kernels (FlashAttention / vendor-optimized) | aiter CK (enabled since 2026-06-18) or triton fallback | With aiter enabled, prefill gap narrows from 42% to 50-66% of H200. The remaining gap is primarily topology (EP8/DP1 vs EP16/DP2). |

> **Key caveat for readers**: The H200 reference data was generated with `fake_topk_ids` which forces all 384 experts to receive exactly equal token counts, eliminating MoE load imbalance. Our MI300X benchmark uses real model routing where expert load follows natural distribution. This means a portion of the observed gap is methodology-driven, not hardware-driven.

### DP Attention Status

DP attention is not available in the completed EP8/DP1 baseline because the baseline uses raw `--tp-size 8`, and MiMo-V2.5-Pro expects effective attention TP=8. Under DP attention, current SGLang divides raw `tp_size` by `dp_size`, so a two-node topology must raise raw `--tp-size` to 16 to keep effective attention TP at 8. That TP16/DP2 path now passes the model/config validation path but fails later in MORI dispatch heap allocation before the server becomes ready.

---

## Known Issues & Blocked Paths

| Issue | Status | Impact | Reference |
|-------|--------|--------|-----------|
| ~~aiter attention backend~~ | **✅ Resolved** | Fixed in commit `f5fe8e944` (2026-06-18). `--attention-backend aiter` now works for MiMo-V2.5-Pro. Prefill +12%~56%. | [TianHao65/sglang@f5fe8e94](https://github.com/TianHao65/sglang/commit/f5fe8e944) |
| **aiter + MTP acceptance gap** | **⚠️ Improved, still open** | 2026-06-19: acceptance rate ~0.2 / accept length ~1.6. 2026-06-26: accept length improves to 2.15-2.38 and accept rate 0.38-0.46 on 8K/1K, but H200 still reports 0.75 accept rate and 2.0-5.0× higher output throughput on the same visible BS rows. | This repo, latest 2026-06-26 section |
| **CUDA Graph on decode** | **⚠️ Critical config** | Decode server **must NOT** use `--disable-cuda-graph`. Disabling it causes 5× TPOT regression (23ms → 120ms). Prefill server should keep `--disable-cuda-graph` (long sequences need dynamic memory). | This repo, verified 2026-06-19 |
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

*Last updated: 2026-06-26*
