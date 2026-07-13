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

**Prefill throughput (2026-07-13 corrected single-full run, 1P1D prefill stage, output=1; higher is better)**

| Context | Concurrency | MI300X tok/s | H200 tok/s | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 8K | 4 | 18,161.81 | 31,950 | 56.8% |
| 64K | 4 | 18,763.17 | 27,400 | 68.5% |
| 256K | 4 | 12,389.64 | 17,400 | 71.2% |

All twelve 1P1D Prefill points completed 16/16 requests with `rc=0`, context length 262151, and zero fatal markers in the Prefill, Decode, and router logs. The table above shows concurrency 4 for comparison with the H200 reference; the full concurrency 1/2/4/8 matrix is below.

**Decode 8K/1K (2026-07-13 tuned fused-MoE retest, `SIMULATE_ACC_LEN=3`; TPOT: lower is better)**

| BS | Concurrency | MI300X Median TPOT | H200 Median TPOT | MI300X/H200 TPOT | MI300X output tok/s | H200 output tok/s | MI300X/H200 tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 16 | 10.79 ms | 11.59 ms | **0.93x** | 1,303.44 | 1,381 | 94.3% |
| 32 | 32 | 13.91 ms | 12.56 ms | 1.11x | 1,930.10 | 2,549 | 75.7% |
| 64 | 64 | 17.82 ms | 14.28 ms | 1.25x | 2,462.83 | 4,483 | 54.9% |
| 128 | 128 | 16.93 ms | 18.25 ms | **0.93x** | 2,468.95 | 7,013 | 35.2% |

In the decode table, `BS` equals target concurrency, matching the H200 reference load shape.

### Key Findings

- **The corrected 1P1D Prefill matrix covers all 12 points:** 8K/64K/256K at concurrency 1/2/4/8, each with 16/16 requests. The 256K path is now valid at context length 262151 and stays near 12.4K tok/s across the concurrency sweep.
- **Core Decode is reproducible across fresh services:** concurrency 16/32/64/128 differs by no more than 2.14% in output throughput and 1.02% in mean TPOT across two runs.
- **Decode median TPOT remains below the H200 reference at BS=16 and BS=128** (0.93x in both cases). The expanded sweep accepts concurrency 8–192 and rejects 256 because of a prefill watchdog dump.
- **Corrected DP=2 Prefill accepts 14/15 points:** 8K/64K concurrency 1/2/4/8/16 and 256K concurrency 1/2/4/8 complete 32/32 requests with valid two-worker distributions. The 256K/concurrency-16 point is rejected after a node-1 GPU memory-aperture fault.
- **Expanded single-full verdict:** 35 points measured, 33 accepted, and 2 rejected boundaries: Decode concurrency 256 and DP=2 256K/concurrency 16. A separate fresh-service DP=2 256K/concurrency-2 attempt also hit a two-node GPU memory-aperture fault; its archived evidence remains part of the robustness verdict even though the targeted retry succeeded.

### Methodology Note

The public aiter commit adds model-specific fused-MoE tuning CSV files; it does not change kernel source. `--speculative-num-draft-tokens=4` means three proposed draft tokens plus one bonus target token. `accept length=3` includes that bonus token, so two draft tokens are accepted and the reported draft accept rate is `2/3=0.67`. MI300X uses real expert routing; the H200 reference uses idealized balanced routing. The AMD-reported 37.6% single-kernel latency reduction is excluded from our measured conclusions because no standalone microbenchmark log was supplied.

---

## Decode — Detailed Results

### Decode 8K/1K — Expanded Concurrency

Requests per point = 256; input length = 8,192; output length = 1,024; warmup = 32; target concurrency = 8/16/32/64/96/128/192/256. All clients exited `0` with 256/256 responses. Server evidence rejects concurrency 256 because the prefill service emitted watchdog thread dumps.

| Concurrency | Successful requests | Output tok/s | Mean TTFT ms | P99 TTFT ms | Mean TPOT ms | Median TPOT ms | P99 TPOT ms | Status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 8 | 256 | 930.00 | 863.69 | 3,041.31 | 7.65 | 7.61 | 8.11 | Accepted |
| 16 | 256 | 1,303.44 | 1,398.73 | 5,864.28 | 10.72 | 10.79 | 11.55 | Accepted |
| 32 | 256 | 1,930.10 | 2,296.89 | 11,931.01 | 13.68 | 13.91 | 14.36 | Accepted |
| 64 | 256 | 2,462.83 | 7,406.18 | 23,962.77 | 17.08 | 17.82 | 18.49 | Accepted |
| 96 | 256 | 2,497.69 | 18,273.38 | 35,014.59 | 15.89 | 16.25 | 17.96 | Accepted |
| 128 | 256 | 2,468.95 | 27,128.38 | 47,023.69 | 16.45 | 16.93 | 18.09 | Accepted |
| 192 | 256 | 2,500.54 | 40,956.57 | 70,422.68 | 15.98 | 16.78 | 17.75 | Accepted |
| 256 | 256 | 729.98 | 29,013.34 | 196,140.78 | 108.58 | 16.79 | 350.94 | Rejected: prefill watchdog |

**Interpretation:** throughput plateaus around 2.47–2.50K tok/s at concurrency 64–192 while TTFT rises with queue depth. Concurrency 256 is outside the accepted operating envelope in this run; client exit code alone would have hidden the service failure.

#### Core Decode Fresh-Service Repeatability

The AMD headline concurrencies were measured in two separate fresh-service runs. Throughput differs by no more than 2.14%, and mean TPOT differs by no more than 1.02%.

| Concurrency | Fresh run 1 tok/s | Fresh run 2 tok/s | Throughput delta | Mean TPOT delta |
|---:|---:|---:|---:|---:|
| 16 | 1,331.98 | 1,303.44 | -2.14% | -1.02% |
| 32 | 1,936.24 | 1,930.10 | -0.32% | +0.22% |
| 64 | 2,457.73 | 2,462.83 | +0.21% | +0.47% |
| 128 | 2,486.89 | 2,468.95 | -0.72% | -0.66% |

- Raw evidence: [`data/raw-logs/20260713-amd-tuned-moe-retest/decode/`](data/raw-logs/20260713-amd-tuned-moe-retest/decode/)
- Detailed report: [`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md)
- Reproduction bundle: [`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/)

---

## Prefill — Detailed Results

### Prefill — Expanded Concurrency, Corrected Context

Requests per point = 16; output length = 1; target concurrency = 1/2/4/8; context length = 262151.

| Input | Concurrency | Successful requests | Input tok/s | Mean TTFT ms | Status |
|---:|---:|---:|---:|---:|---|
| 8K | 1 | 16 | 16,835.22 | 485.70 | Accepted |
| 8K | 2 | 16 | 19,618.25 | 829.40 | Accepted |
| 8K | 4 | 16 | 18,161.81 | 1,612.03 | Accepted |
| 8K | 8 | 16 | 21,004.97 | 2,817.91 | Accepted |
| 64K | 1 | 16 | 18,057.01 | 3,628.49 | Accepted |
| 64K | 2 | 16 | 19,860.45 | 6,481.41 | Accepted |
| 64K | 4 | 16 | 18,763.17 | 12,970.83 | Accepted |
| 64K | 8 | 16 | 18,765.43 | 22,530.68 | Accepted |
| 256K | 1 | 16 | 12,381.87 | 21,170.66 | Accepted |
| 256K | 2 | 16 | 12,378.06 | 41,208.61 | Accepted |
| 256K | 4 | 16 | 12,389.64 | 77,254.06 | Accepted |
| 256K | 8 | 16 | 12,402.23 | 133,251.83 | Accepted |

**Interpretation:** 8K peaks at concurrency 8, while 64K is broadly flat from concurrency 2–8. The corrected 256K path stays near 12.4K tok/s; higher concurrency mainly increases TTFT. Because output length is 1, sustained GPU pressure is concentrated on Prefill while Decode performs only the transferred-KV handoff and one-token generation.

- Reproduction bundle: [`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/)

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

| ISL/OSL | Concurrency | Successful requests | Aggregate input tok/s | Worker request deltas | Status |
|---:|---:|---:|---:|---:|---|
| 8K/1 | 1 | 32 | 20,751.73 | 17/16 | Accepted |
| 8K/1 | 2 | 32 | 41,201.86 | 16/17 | Accepted |
| 8K/1 | 4 | 32 | 43,401.70 | 17/16 | Accepted |
| 8K/1 | 8 | 32 | 46,113.92 | 16/17 | Accepted |
| 8K/1 | 16 | 32 | 46,747.01 | 17/16 | Accepted |
| 64K/1 | 1 | 32 | 19,695.02 | 16/17 | Accepted |
| 64K/1 | 2 | 32 | 38,984.45 | 17/16 | Accepted |
| 64K/1 | 4 | 32 | 38,382.03 | 16/17 | Accepted |
| 64K/1 | 8 | 32 | 38,204.80 | 17/16 | Accepted |
| 64K/1 | 16 | 32 | 38,155.28 | 16/17 | Accepted |
| 256K/1 | 1 | 32 | 12,783.28 | 17/16 | Accepted |
| 256K/1 | 2 | 32 | 25,063.73 | 17/16 | Accepted after targeted retry |
| 256K/1 | 4 | 32 | 24,923.63 | 16/17 | Accepted |
| 256K/1 | 8 | 32 | 24,765.29 | 17/16 | Accepted |
| 256K/1 | 16 | 24 | 18,742.17 | Not produced | Rejected: GPU memory-aperture fault |

All accepted points passed exact request-count, context, client, two-worker distribution, and service-evidence gates. The rejected concurrency-16 client exited `0`, demonstrating again that client exit status is not sufficient. These are aggregate two-node capacity values; they must not be compared directly with one H200 node.

### 256K Correctness Guard

With `random_input_len=262144`, HTTP 200 error payloads can be misclassified by a client-only success counter. The later 262149 retry is also withdrawn because this runtime exposes only `max_req_input_len=262143`. The corrected entry point uses `--context-length 262151`, captures `/server_info` from both workers, and requires `max_req_input_len>=262145` before measurement. A valid context gate does not guarantee runtime stability: the clean session failed at 256K/concurrency 2 on both nodes, and a targeted fresh-service retry later failed at concurrency 16 on node 1. Both incidents are disclosed.

- Current sanitized evidence: [`data/raw-logs/20260713-amd-tuned-moe-expanded-concurrency/`](data/raw-logs/20260713-amd-tuned-moe-expanded-concurrency/)
- Current report: [`reports/20260713-amd-tuned-moe-expanded-concurrency.md`](reports/20260713-amd-tuned-moe-expanded-concurrency.md)
- Historical withdrawn evidence: [`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/)

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

The current corrected launch, expanded concurrency, validation, and parser bundle is under [`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/). The earlier [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/) bundle and its raw logs are retained as historical evidence; do not use its 262149 launch settings for current 256K reproduction.

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

# 5. Copy the current corrected bundle into the container
# scripts/20260713-amd-tuned-moe-expanded-concurrency/ -> /data/mimo-tuned-expanded/

# 6. Find IB IPs for your two nodes
docker exec $CONTAINER bash -c "ibdev2netdev | head -1"
docker exec $CONTAINER bash -c "ip addr show ib0 | grep inet"
export PREFILL_IB_IP=<prefill-node-ib-ip>
export DECODE_IB_IP=<decode-node-ib-ip>

# 7. Clean old processes (both nodes)
docker exec $CONTAINER bash -c "pkill -f 'sglang.launch_server|bench_serving' || true; pkill -f '[s]glang::router|sglang_router' || true"

# 8. Launch servers (each in a separate terminal — foreground processes)
# Terminal A — Node 1 (prefill):
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded && bash launch_pd_prefill.sh"
# Terminal B — Node 2 (decode):
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded && bash launch_pd_decode.sh"
# Terminal C — Node 1 (router, after both servers print 'ready'):
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded && PREFILL_IB_IP=$PREFILL_IB_IP DECODE_IB_IP=$DECODE_IB_IP bash launch_pd_router.sh"

# 9. Health + smoke test
curl -fsS http://127.0.0.1:40000/health
docker exec $CONTAINER bash -c "python3 -m sglang.bench_serving \
  --backend sglang --model /data/models/MiMo-V2.5-Pro --host 0.0.0.0 --port 40000 \
  --dataset-name random --random-input-len 128 --random-output-len 16 \
  --num-prompts 2 --warmup-requests 1 --max-concurrency 1 --pd-separated"

# 10. Run benchmarks
RUN_DIR=/data/mimo-tuned-expanded/run-$(date +%Y%m%d-%H%M%S)
docker exec $CONTAINER bash -c "mkdir -p $RUN_DIR/decode $RUN_DIR/prefill; cd /data/mimo-tuned-expanded; LOG_DIR=$RUN_DIR/decode bash benchmark_decode.sh > $RUN_DIR/decode/full.out 2>&1; echo \$? > $RUN_DIR/decode/full.rc"
docker exec $CONTAINER bash -c "cd /data/mimo-tuned-expanded; LOG_DIR=$RUN_DIR/prefill bash benchmark_1p_prefill.sh > $RUN_DIR/prefill/full.out 2>&1; echo \$? > $RUN_DIR/prefill/full.rc"
```

### AMD DP=2/TP=8 Two-Node Prefill Method

The corrected DP=2 reproduction uses the same Docker image and `--context-length 262151` for 262,144-token requests. It validates both workers through `/server_info` and uses explicit round-robin routing. This is a prefill-only server-mode benchmark; it does not include P→D KV-cache transfer.

```bash
cd /data/mimo-tuned-expanded
./launch_dp2_node0.sh       # node 0
./launch_dp2_node1.sh       # node 1
Node0_IP=<node0-ib-ip> Node1_IP=<node1-ib-ip> ./launch_dp2_router.sh
LOG_DIR=/data/mimo-tuned-expanded/rep-1/dp2 ./benchmark_dp2_prefill.sh
```

The sweep command is client-only convenience. Accepted DP=2 evidence must run each point with `benchmark_dp2_point.sh` and save the two worker request deltas as described in the current bundle README.

### Archived Evidence

| Path | Content |
|------|---------|
| [`data/raw-logs/20260713-amd-tuned-moe-retest/`](data/raw-logs/20260713-amd-tuned-moe-retest/) | Historical evidence; valid Decode and 8K/64K Prefill rows plus withdrawn 256K client summaries |
| [`reports/20260713-amd-tuned-moe-retest.md`](reports/20260713-amd-tuned-moe-retest.md) | Independent tuned fused-MoE retest report and evidence map |
| [`scripts/20260713-amd-tuned-moe-expanded-concurrency/`](scripts/20260713-amd-tuned-moe-expanded-concurrency/) | Current corrected launch, expanded concurrency, validation, and parser bundle |
| [`scripts/20260713-amd-tuned-moe-retest/`](scripts/20260713-amd-tuned-moe-retest/) | Superseded historical bundle; do not use for current 256K reproduction |
| [`data/raw-logs/20260707-ck-a8w8-gemm/`](data/raw-logs/20260707-ck-a8w8-gemm/) | CK A8W8 strict reproduction: benchmark logs, env gates, script SHA256 |
| [`reports/20260707-ck-a8w8-gemm-strict-repro.md`](reports/20260707-ck-a8w8-gemm-strict-repro.md) | CK strict reproduction result summary |

---

## Known Issues

| Issue | Status | Impact |
|-------|--------|--------|
| **Decode CUDA Graph** | ⚠️ Critical config | Decode server must NOT use `--disable-cuda-graph`. Disabling causes 5× TPOT regression. Prefill server should disable it. |
| **DP=2 256K request framing** | ✅ Corrected | Use `--context-length 262151`; require direct worker `/server_info` with `max_req_input_len>=262145`, clean service logs, and two-worker distribution evidence. |
| **Router health endpoint** | ✅ Corrected | SGLang `/health` performs synthetic generation and can fail under long Prefill load. Use the bundle's non-generative `/server_info` endpoint with a 30-second timeout and validate worker/router logs. |
| **Run-to-run variance** | ⚠️ Partially characterized | The expanded matrix is one run per point. Decode concurrency 16/32/64/128 has a separate second fresh-service run; no full-matrix standard deviation is claimed. |

---

## References

- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` branch](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo model-specific fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)

---

*Last updated: 2026-07-13*
