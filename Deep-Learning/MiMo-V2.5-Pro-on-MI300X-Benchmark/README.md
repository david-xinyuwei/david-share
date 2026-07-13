# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

Running **Xiaomi MiMo-V2.5-Pro (1.02T MoE / 42B active / FP8)** on Azure **AMD Instinct MI300X** with SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + the model-specific fused-MoE tuning from [`aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9), benchmarked against Xiaomi's H200 reference data.

This repo provides full reproduction scripts, launch commands, benchmark results, and server logs. With 2× Azure ND96isr_MI300X_v5 nodes and the specified Docker image, the steps below rebuild a clean-room MI300X environment and run the AMD benchmark scripts. For PD-separated decode, the container must expose RDMA devices (`--privileged`, `/dev/mem`, and `CAP_SYS_ADMIN`); otherwise Mooncake falls back to TCP and high-concurrency throughput results are invalid.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)

English | [中文版](README-CN.md)

---

## Architecture

<div align="center"><img src="images/pd_architecture.png" width="960"></div>

---

## Executive Summary

**Prefill throughput (2026-07-13 tuned fused-MoE retest, 1P1D prefill stage, output=1; higher is better)**

| Context | Concurrency | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 8K | 4 | 20,780.79 | 31,950 | 65.0% |
| 64K | 4 | 19,022.57 | 27,400 | 69.4% |
| 256K | 4 | Excluded | 17,400 | Under corrected rerun |

The 8K and 64K points completed 16/16 requests with zero client or server error markers. The original 256K client summary is excluded because both 1P1D server logs contain context-overflow responses. For the independently retested DP=2 results, see [Prefill Scaling — AMD 2-Node DP=2/TP=8](#prefill-scaling--amd-2-node-dp2tp8).

**Decode 8K/1K (2026-07-13 tuned fused-MoE retest, `SIMULATE_ACC_LEN=3`; TPOT: lower is better)**

| BS | Concurrency | MI300X Median TPOT | H200 Median TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 16 | 10.97 ms | 11.59 ms | **0.95x** | 1,331.98 | 1,381 | 96.5% |
| 32 | 32 | 13.93 ms | 12.56 ms | 1.11x | 1,936.24 | 2,549 | 76.0% |
| 64 | 64 | 17.60 ms | 14.28 ms | 1.23x | 2,457.73 | 4,483 | 54.8% |
| 128 | 128 | 17.30 ms | 18.25 ms | **0.95x** | 2,486.89 | 7,013 | 35.5% |

In the decode table, `BS` equals target concurrency, matching the H200 reference load shape.

### Key Findings

- **Validated 1P1D prefill improves at 8K and 64K:** +24.32% and +10.25% versus our 2026-07-07 strict CK baseline. The original 256K point is excluded pending the corrected rerun.
- **High-concurrency decode is a throughput/latency trade-off:** output throughput improves by +12.33% at BS=64 and +12.56% at BS=128, while mean TPOT increases by +12.58% and +14.05% respectively.
- **Decode median TPOT remains below the H200 reference at BS=16 and BS=128** (0.95x in both cases). Output throughput is reported separately because the serving topologies are not normalized.
- **DP=2 prefill completed all six points independently:** aggregate throughput reaches 45,992.94 tok/s at 8K and 78,613.96 tok/s at 256K. The H200 comparison uses MI300X per-node throughput, not the 2-node aggregate.
- **Accepted matrices passed:** 4 decode points at 256/256 requests, 2 valid 1P1D prefill points at 16/16, and 6 DP=2 points at 32/32. Client-only success is not sufficient for the excluded 1P1D 256K point.

### Methodology Note

The public aiter commit adds model-specific fused-MoE tuning CSV files; it does not change kernel source. `--speculative-num-draft-tokens=4` means three proposed draft tokens plus one bonus target token. `accept length=3` includes that bonus token, so two draft tokens are accepted and the reported draft accept rate is `2/3=0.67`. MI300X uses real expert routing; the H200 reference uses idealized balanced routing. The AMD-reported 37.6% single-kernel latency reduction is excluded from our measured conclusions because no standalone microbenchmark log was supplied.

---

## Decode — Detailed Results

### Decode 8K/1K — Tuned Fused-MoE Independent Retest

N = 256 requests per point; input length = 8,192; output length = 1,024; warmup = 32; target concurrency = 16/32/64/128; `full.rc=0`.

| Concurrency | Successful requests | Output tok/s | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | Output vs strict baseline | Mean TPOT vs strict baseline |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 256 | 1,331.98 | 10.83 | 10.97 | 11.35 | +2.52% | +1.79% |
| 32 | 256 | 1,936.24 | 13.65 | 13.93 | 14.35 | +1.33% | +1.11% |
| 64 | 256 | 2,457.73 | 17.00 | 17.60 | 18.44 | +12.33% | +12.58% |
| 128 | 256 | 2,486.89 | 16.56 | 17.30 | 17.92 | +12.56% | +14.05% |

**Interpretation:** the material throughput gain appears at BS=64/128, but it comes with higher TPOT. Keep throughput and per-token latency as separate decision metrics.

- Raw evidence: [`data/raw-logs/20260713-amd-tuned-moe-retest/decode/`](data/raw-logs/20260713-amd-tuned-moe-retest/decode/)
- Detailed report: [`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md)
- Reproduction bundle: [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/)

---

## Prefill — Detailed Results

### Prefill — Tuned Fused-MoE Independent Retest

N = 16 requests per input length; output length = 1; target concurrency = 4; `full.rc=0`.

| ISL/OSL | Concurrency | Successful requests | Input tok/s | vs strict baseline | MI300X / H200 |
|---:|---:|---:|---:|---:|---:|
| 8K/1 | 4 | 16 | 20,780.79 | +24.32% | 65.0% |
| 64K/1 | 4 | 16 | 19,022.57 | +10.25% | 69.4% |
| 256K/1 | 4 | Client reported 16 | Excluded | Excluded | Excluded |

**Interpretation:** the tuned fused-MoE configuration improves the validated 8K and 64K points. The 256K client reported 16 successes, but node 0 and node 1 each logged 11 `262148 > 262144` context-overflow responses. That point is not a valid throughput measurement and is being rerun with a 262,149-token server allowance.

- Raw evidence: [`data/raw-logs/20260713-amd-tuned-moe-retest/prefill/`](data/raw-logs/20260713-amd-tuned-moe-retest/prefill/)

---

## Prefill Scaling — AMD 2-Node DP=2/TP=8

We independently retested the 2-node DP=2/TP=8 prefill-only server path with the same Docker image and tuned fused-MoE configuration. This test does **not** include P→D KV-cache transfer overhead; a 2P1D end-to-end run would require 3 nodes.

### Test Method

```bash
# Run DP=2, TP=8 2-node prefill benchmark.
./launch_dp2_node0.sh       # node 0, port 30000
./launch_dp2_node1.sh       # node 1, port 30001
./launch_dp2_router.sh      # node 0
./benchmark_dp2_prefill.sh  # node 0
```

### Results

| ISL/OSL | Concurrency | Aggregate input tok/s | Per-node input tok/s | Per-node / H200 |
|---:|---:|---:|---:|---:|
| 8K/1 | 4 | 43,221.12 | 21,610.56 | 67.6% |
| 8K/1 | 8 | 45,992.94 | 22,996.47 | 72.0% |
| 64K/1 | 4 | 38,374.65 | 19,187.33 | 70.0% |
| 64K/1 | 8 | 38,255.28 | 19,127.64 | 69.8% |
| 256K/1 | 4 | 74,611.25 | 37,305.62 | 214.4% |
| 256K/1 | 8 | 78,613.96 | 39,306.98 | 225.9% |

All six points completed 32/32 requests. Per-node throughput is used for the H200 comparison; the 2-node aggregate is not compared directly with one H200 node.

### 256K Correctness Guard

With `random_input_len=262144`, the standard DP=2 server path observed 262,148 tokens after request construction. A server allowance of 262,144 therefore returned HTTP 200 error payloads that a client-only success counter could misclassify. The invalid attempt is excluded. The accepted run changes only the server allowance to `--context-length 262149`; both node logs contain zero context-overflow entries.

- Raw evidence: [`data/raw-logs/20260713-amd-tuned-moe-retest/dp2/`](data/raw-logs/20260713-amd-tuned-moe-retest/dp2/)
- Validation record: [`data/raw-logs/20260713-amd-tuned-moe-retest/checks/validation.txt`](data/raw-logs/20260713-amd-tuned-moe-retest/checks/validation.txt)

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
| aiter | [sammysun0711/aiter](https://github.com/sammysun0711/aiter) commit [`d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9) | Model-specific MiMo fused-MoE tuning CSV; runtime-local equivalent commit `00e94abf1` |
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

The accepted launch, benchmark, configuration, and parser bundle is archived under [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/). Client logs and deterministic summaries are under [`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/).

### Prerequisites

- 2× Azure `Standard_ND96isr_MI300X_v5` nodes (VMSS, same placement group for IB)
- Docker image: `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` (SHA: `bb9d2e5ab1a6`)
- Model: [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) downloaded to `/data/models/MiMo-V2.5-Pro`
- SGLang: `sammysun0711/sglang` branch `mimo_aiter_attn`, commit `db840d935`
- aiter: `sammysun0711/aiter`, commit `d725746a0f8c233d8e46e2771a7c8dbcd06e40d9`

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
git clone https://github.com/sammysun0711/aiter.git aiter_0625
cd aiter_0625 && git checkout d725746a0f8c233d8e46e2771a7c8dbcd06e40d9

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

# 5. Copy scripts/20260713-amd-tuned-moe-retest/ to /data/xisun/20260713-amd-tuned-moe-retest/

# 6. Find IB IPs for your two nodes
docker exec $CONTAINER bash -c "ibdev2netdev | head -1"
docker exec $CONTAINER bash -c "ip addr show ib0 | grep inet"
export PREFILL_IB_IP=<prefill-node-ib-ip>
export DECODE_IB_IP=<decode-node-ib-ip>

# 7. Clean old processes (both nodes)
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|bench_serving' || true; pkill -f '[s]glang::router|sglang_router' || true"

# 8. Launch servers (each in a separate terminal — foreground processes)
# Terminal A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest && bash launch_pd_prefill.sh"
# Terminal B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest && bash launch_pd_decode.sh"
# Terminal C — Node 1 (router, after both servers print 'ready'):
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP bash launch_pd_router.sh"

# 9. Health + smoke test
curl -fsS http://127.0.0.1:40000/health
docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 10. Run benchmarks
RUN_DIR=/data/xisun/benchmark-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/decode $RUN_DIR/prefill; cd /data/xisun/20260713-amd-tuned-moe-retest; LOG_DIR=$RUN_DIR/decode bash benchmark_decode.sh > $RUN_DIR/decode/full.out 2>&1; echo \$? > $RUN_DIR/decode/full.rc"
docker exec $CONTAINER bash -c "cd /data/xisun/20260713-amd-tuned-moe-retest; LOG_DIR=$RUN_DIR/prefill bash benchmark_1p_prefill.sh > $RUN_DIR/prefill/full.out 2>&1; echo \$? > $RUN_DIR/prefill/full.rc"
```

### AMD DP=2/TP=8 Two-Node Prefill Method

The accepted DP=2 reproduction uses the same Docker image and a 262,149-token server allowance for 262,144-token requests. This is a prefill-only server-mode benchmark; it does not include P→D KV-cache transfer.

```bash
./launch_dp2_node0.sh       # node 0
./launch_dp2_node1.sh       # node 1
Node0_IP=<node0-ib-ip> Node1_IP=<node1-ib-ip> ./launch_dp2_router.sh
LOG_DIR=/data/xisun/dp2 ./benchmark_dp2_prefill.sh
```

### Archived Evidence

| Path | Content |
|------|---------|
| [`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/) | Accepted 4/3/6 matrices: client logs, exit codes, summaries, JSON, SHA-256 manifest, context guard |
| [`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md) | Independent tuned fused-MoE retest report and evidence map |
| [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/) | Accepted launch, benchmark, tuning CSV, and deterministic parser bundle |
| [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/) | CK A8W8 strict reproduction: benchmark logs, env gates, script SHA256 |
| [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md) | CK strict reproduction result summary |

---

## Known Issues

| Issue | Status | Impact |
|-------|--------|--------|
| **Decode CUDA Graph** | ⚠️ Critical config | Decode server must NOT use `--disable-cuda-graph`. Disabling causes 5× TPOT regression. Prefill server should disable it. |
| **DP=2 256K request framing** | ✅ Guarded | `random_input_len=262144` becomes 262,148 server-side tokens. Use `--context-length 262149` and validate service-log overflow count, not client success alone. |
| **Run-to-run variance** | ⚠️ Not characterized | Each published matrix point is one run. Request counts are reported, but no multi-run standard deviation is claimed. |

---

## References

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` branch](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo model-specific fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*Last updated: 2026-07-13*
