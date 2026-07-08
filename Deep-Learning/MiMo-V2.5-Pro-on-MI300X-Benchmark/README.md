# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE, benchmarked against Xiaomi's H200 reference data.

This repo provides full reproduction scripts, launch commands, benchmark results, and server logs. With 2× Azure ND96isr_MI300X_v5 nodes and the specified Docker image, the steps below rebuild a clean-room MI300X environment and run the AMD benchmark scripts. For PD-separated decode, the container must expose RDMA devices (`--privileged`, `/dev/mem`, and `CAP_SYS_ADMIN`); otherwise Mooncake falls back to TCP and high-concurrency throughput results are invalid.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

English | [中文版](README-CN.md)

---

## Architecture

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## Executive Summary

**Prefill throughput (CK A8W8, output=1; higher is better)**

| Context | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|
| 8K | 16,716 | 31,950 | 52.3% |
| 64K | 17,254 | 27,400 | 63.0% |
| 256K | 37,493 | 17,400 | **215.5%** |

**Decode 8K/1K (CK A8W8, `SIMULATE_ACC_LEN=3` on both sides; TPOT: lower is better)**

| BS | MI300X Median TPOT | MI300X P99 | H200 TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 10.83 ms | 11.57 ms | 11.59 ms | **0.93x** | 1,299 | 1,381 | 94.1% |
| 32 | 13.73 ms | 14.25 ms | 12.56 ms | 1.09x | 1,911 | 2,549 | 74.9% |
| 64 | 15.53 ms | 16.58 ms | 14.28 ms | 1.09x | 2,188 | 4,483 | 48.8% |
| 128 | 14.83 ms | 15.82 ms | 18.25 ms | **0.81x** | 2,209 | 7,013 | 31.5% |

### Key Findings

- **Decode TPOT at BS=16 and BS=128: MI300X surpasses H200.** At BS=16 the per-token latency is 0.93× of H200; at BS=128 it is 0.81×. At BS=32/64 the gap is only 9%.
- **Prefill 256K long-context: MI300X is 2.15× of H200** throughput. At 8K/64K MI300X reaches 52–63% of H200.
- **Output tok/s gap is wider than TPOT gap** because output tok/s also reflects serving topology and scheduling differences (single TP=8 decode path vs H200 multi-DP/EP). The TPOT comparison isolates kernel-level performance.
- **Decode throughput plateaus at concurrency 64** (~2,200 output tok/s) and stays flat through concurrency 256.

### Methodology Note

Both MI300X and H200 use `SGLANG_SIMULATE_ACC_LEN=3` (fixing MTP accept_length at 3.0). All MI300X numbers use **real expert routing** (not `fake_topk_ids`), adding 5–15% overhead vs the H200 ideal-routing baseline. The H200 output tok/s column equals `BS × 1000 / TPOT` from Xiaomi's reference sheet.

---

## Decode — Detailed Results

### Decode 8K/1K — AMD CK Reference Alignment (Low Concurrency)

This section reproduces AMD's 2026-07-07 CK A8W8 benchmark using their original scripts without modification. The "AMD CK" column is AMD's own published result; our reproduction matches within ~1.2%.

N = 256 requests per BS point; target concurrency = 16/32/64/128; `decode_full.rc=0`; no benchmark error markers.

| BS | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | AMD CK mean TPOT ms | Delta vs AMD CK |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,299.18 | 10.64 | 10.83 | 11.57 | 10.59 | +0.5% |
| 32 | 256 | 1,910.75 | 13.50 | 13.73 | 14.25 | 13.43 | +0.5% |
| 64 | 256 | 2,188.05 | 15.10 | 15.53 | 16.58 | 14.92 | +1.2% |
| 128 | 256 | 2,209.43 | 14.52 | 14.83 | 15.82 | 14.55 | -0.2% |

- Raw evidence: [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/)
- Result summary: [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md)
- Script snapshot: [`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/)

### Decode 8K/1K — High-Concurrency Extension (Beyond AMD's Test Range)

AMD's benchmark covers concurrency up to 128. We extended the sweep to concurrency 256 to identify the saturation point.

N = 256 requests per concurrency point; output length = 1024; warmup = 32; `decode_full.rc=0`.

| Concurrency | Output tok/s | Mean TPOT ms | P99 TPOT ms | Mean TTFT ms |
|---:|---:|---:|---:|---:|
| 16 | 1,321.50 | 10.79 | 11.65 | 1,191 |
| 32 | 1,914.27 | 13.37 | 14.26 | 2,847 |
| 64 | 2,198.77 | 15.49 | 17.08 | 11,853 |
| 96 | 2,200.63 | 15.06 | 16.31 | 23,667 |
| 128 | 2,203.65 | 14.83 | 16.22 | 33,430 |
| 192 | 2,202.57 | 14.72 | 16.28 | 47,911 |
| 256 | 2,207.97 | 14.60 | 16.36 | 55,467 |

**Interpretation:** throughput saturates around concurrency 64 (~2,200 output tok/s) and remains stable through concurrency 256. Higher concurrency mainly increases queueing/TTFT without improving output throughput.

- Raw evidence: [`data/raw-logs/20260708-ck-a8w8-concurrency-extension/`](data/raw-logs/20260708-ck-a8w8-concurrency-extension/)
- Result summary: [`reports/20260708-ck-a8w8-concurrency-extension.md`](reports/20260708-ck-a8w8-concurrency-extension.md)
- Script snapshot: [`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/)

---

## Prefill — Detailed Results

### Prefill — AMD CK Reference Alignment

N = 16 requests per input length; target concurrency = 4; `prefill_full.rc=0`; no benchmark error markers.

| ISL/OSL | Successful requests | Input tok/s | Mean TTFT ms | P99 TTFT ms | AMD CK 32K input tok/s | Delta vs AMD CK |
|---:|---:|---:|---:|---:|---:|---:|
| 8K/1 | 16 | 16,715.80 | 1,849.62 | 2,709.97 | 16,924.08 | -1.2% |
| 64K/1 | 16 | 17,254.14 | 14,107.62 | 16,674.08 | 17,223.51 | +0.2% |
| 256K/1 | 16 | 37,492.80 | 19,278.17 | 86,264.51 | 37,241.84 | +0.7% |

### Prefill — Multi-Concurrency Extension (Beyond AMD's Test Range)

AMD's prefill benchmark uses concurrency 4. We extended the sweep to concurrency 1/2/4/8 across 8K/64K/256K to map the concurrency scaling behavior.

N = 16 requests per point; output = 1; warmup = 1.

| Input tokens | Concurrency | Input tok/s | Mean TTFT ms | P99 TTFT ms |
|---:|---:|---:|---:|---:|
| 8192 | 1 | 14,811.18 | 552 | 589 |
| 8192 | 2 | 16,982.94 | 958 | 1,369 |
| 8192 | 4 | 16,783.88 | 1,841 | 2,680 |
| 8192 | 8 | 18,617.41 | 3,211 | 4,691 |
| 65536 | 1 | 16,602.69 | 3,946 | 4,870 |
| 65536 | 2 | 18,077.28 | 7,123 | 9,004 |
| 65536 | 4 | 16,904.74 | 14,232 | 16,774 |
| 65536 | 8 | 17,252.39 | 24,482 | 31,727 |
| 262144 | 1 | 35,452.56 | 6,995 | 22,648 |
| 262144 | 2 | 37,429.63 | 12,417 | 47,335 |
| 262144 | 4 | — (warmup failure) | — | — |
| 262144 | 8 | — (warmup failure) | — | — |

256K/con4 and 256K/con8 fail during warmup with `No available prefill workers (all circuits open or unhealthy)`. This is a high-concurrency availability boundary, not a measured throughput regression.

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
| SGLang | AMD fork: [sammysun0711/sglang](https://github.com/sammysun0711/sglang) branch `mimo_aiter_attn`, commit `db840d935` | CK A8W8 blockwise GEMM bpreshuffle + AITER INT8 quick-reduce |
| ROCm | 7.2.0 | |
| aiter | `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4` | [ROCm/aiter](https://github.com/ROCm/aiter). MoE/GEMM/FP8/LayerNorm/Attention all enabled |
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

## Reproducing Results

All scripts and raw logs are archived under [`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/) and [`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/).

### Prerequisites

- 2× Azure `Standard_ND96isr_MI300X_v5` nodes (VMSS, same placement group for IB)
- Docker image: `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` (SHA: `bb9d2e5ab1a6`)
- Model: [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) downloaded to `/data/models/MiMo-V2.5-Pro`
- SGLang: `sammysun0711/sglang` branch `mimo_aiter_attn`, commit `db840d935`
- aiter: `amd-aiter 0.1.14rc1.dev213+g7a8ff7dd4`, commit `7a8ff7dd4`

### Container Runtime Requirements

| Requirement | Why it matters | Verification |
|---|---|---|
| `--privileged`, `/dev/mem`, `CAP_SYS_ADMIN` | Allows Mooncake to discover and use RDMA HCAs for KV-cache transfer | `ls /dev/infiniband/uverbs0 && ls /dev/mem` inside the container |
| No stale `/sgl-workspace/aiter` | Prevents Python import shadowing of `/sgl-workspace/aiter_0625` | `test ! -d /sgl-workspace/aiter` |
| Explicit benchmark source tree | Prevents namespace-package drift in benchmark client imports | `PYTHONPATH=/sgl-workspace/sglang_0625/python` |

### Step-by-Step

```bash
# 1. Start a fresh container on both nodes
CONTAINER=sglang
docker run -d --name $CONTAINER \
  --privileged \
  --ipc=host --network=host --shm-size=256g \
  --device=/dev/kfd --device=/dev/dri --device=/dev/mem \
  --group-add video \
  --cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE \
  --security-opt seccomp=unconfined --security-opt label=disable \
  -v /data:/data rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510 sleep infinity

# 1a. RDMA gate (both nodes — must pass before proceeding)
docker exec $CONTAINER bash -c "ls /dev/infiniband/uverbs0 && ls /dev/mem && echo RDMA_DEVICE_OK"

# 2. Clone SGLang + aiter source inside container (both nodes)
docker exec -it $CONTAINER bash
mkdir -p /sgl-workspace && cd /sgl-workspace
git clone https://github.com/sammysun0711/sglang.git sglang_0625
cd sglang_0625 && git checkout db840d935
cd /sgl-workspace
git clone https://github.com/ROCm/aiter.git aiter_0625
cd aiter_0625 && git checkout 7a8ff7dd4

# 3. Install (both nodes — use --no-deps to preserve ROCm torch stack)
cd /sgl-workspace/sglang_0625 && pip install -e "python[all_hip]" --no-deps
pip install flydsl==0.2.0 --no-deps
cd /sgl-workspace/aiter_0625 && pip install -e . --no-deps
pip install mooncake-transfer-engine==0.3.7.post2 --no-deps

# 3a. Build sglang-kernel on prefill/router node only
cd /sgl-workspace/sglang_0625/sgl-kernel && python3 setup_rocm.py install

# 3b. Verify imports
export PYTHONPATH=/sgl-workspace/sglang_0625/python:${PYTHONPATH:-}
python3 -c "import torch, sglang, sgl_kernel, aiter; print('IMPORT_OK')"
test ! -d /sgl-workspace/aiter || { echo "ERROR: stale aiter shadows aiter_0625"; exit 1; }

# 4. Download model (both nodes or shared storage)
huggingface-cli download XiaomiMiMo/MiMo-V2.5-Pro --local-dir /data/models/MiMo-V2.5-Pro

# 5. Deploy benchmark scripts from scripts/20260707-amd-ck-a8w8/ into /data/xisun/

# 6. Find IB IPs for your two nodes
docker exec $CONTAINER bash -c "ibdev2netdev | head -1"
docker exec $CONTAINER bash -c "ip addr show ib0 | grep inet"
export PREFILL_IB_IP=<prefill-node-ib-ip>
export DECODE_IB_IP=<decode-node-ib-ip>

# 7. Clean old processes (both nodes)
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|sglang_router|bench_serving' || true"

# 8. Launch servers (each in a separate terminal — foreground processes)
# Terminal A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/xisun && bash launch_tp8_noep_prefill_aiter_mtp.sh"
# Terminal B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/xisun && bash launch_tp8_noep_decode_aiter_mtp.sh"
# Terminal C — Node 1 (router, after both servers print 'ready'):
docker exec $CONTAINER bash -c "cd /data/xisun && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP bash launch_router.sh"

# 9. Health + smoke test
curl -fsS http://127.0.0.1:40000/health
docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 10. Run benchmarks
RUN_DIR=/data/xisun/benchmark-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR && cd /data/xisun && bash run_benchmark_mimo_pro_decode.sh > $RUN_DIR/decode_full.out 2>&1; echo \$? > $RUN_DIR/decode_full.rc"
docker exec $CONTAINER bash -c "cd /data/xisun && bash run_benchmark_mimo_pro_prefill.sh > $RUN_DIR/prefill_full.out 2>&1; echo \$? > $RUN_DIR/prefill_full.rc"
```

### Archived Evidence

| Path | Content |
|------|---------|
| [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/) | CK A8W8 strict reproduction: benchmark logs, env gates, script SHA256 |
| [`data/raw-logs/20260708-ck-a8w8-concurrency-extension/`](data/raw-logs/20260708-ck-a8w8-concurrency-extension/) | High-concurrency extension: decode + prefill sweep logs |
| [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md) | CK strict reproduction result summary |
| [`reports/20260708-ck-a8w8-concurrency-extension.md`](reports/20260708-ck-a8w8-concurrency-extension.md) | Concurrency extension result summary |
| [`scripts/20260707-amd-ck-a8w8/`](scripts/20260707-amd-ck-a8w8/) | CK launch + benchmark scripts |
| [`scripts/20260708-ck-a8w8-concurrency-sweep/`](scripts/20260708-ck-a8w8-concurrency-sweep/) | Concurrency sweep scripts |

---

## Known Issues

| Issue | Status | Impact |
|-------|--------|--------|
| **Decode CUDA Graph** | ⚠️ Critical config | Decode server must NOT use `--disable-cuda-graph`. Disabling causes 5× TPOT regression. Prefill server should disable it. |
| **256K high-concurrency prefill** | ⚠️ Boundary | 256K prefill at concurrency ≥4 fails during warmup with no healthy prefill workers. Concurrency 1–2 works. |

---

## References

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` branch](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*Last updated: 2026-07-08*
