# Qwen3-235B Multi-Node Inference Benchmark (TP=2 + PP=2)

> **Model**: Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 (235B MoE, 22B activated per token)
> **Hardware**: 2× Azure NC80adis_H100_v5 (4× H100 NVL, 376GB VRAM total)
> **Engines Tested**: vLLM v0.11.2/v0.10.1 → **SGLang v0.5.8.post1** (current production)
> **Features**: Function Calling, Reasoning Mode, Chunked Prefill

---

## 🏆 Key Results

### Three-Engine Comparison (Same Hardware, Same Model)

| Metric | SGLang v0.5.8 | vLLM V0 (v0.10.1) | vLLM V1 (v0.11.2) |
|--------|:-------------:|:------------------:|:------------------:|
| **Single-request TPS** | **70-75 t/s** | 6.8 t/s | 17 t/s |
| **Peak Throughput** | **1,320 t/s** @ C=128 | 304 t/s @ C=33 | 610 t/s @ C=64 |
| **TTFT (idle)** | 104-142 ms | 141-146 ms | 81-93 ms |
| **ITL (avg)** | **13.3 ms** | ~158 ms | ~57 ms |
| **PP>1 Stability** | ✅ Zero crashes | ✅ Zero crashes | ❌ Crashes in min~hours |
| **Function Calling** | ✅ 5/5 tests | ✅ Working | ✅ Working |
| **Max Tested Concurrency** | C=128 stable | C=91 stable | C=64 (C=128 crash) |

### SGLang Benchmark (Current Production - 2026-02-11)

| Concurrency | Throughput (t/s) | TTFT (ms) | QPS |
|:-----------:|:----------------:|:---------:|:---:|
| 1 | 70.1 | 140 | 0.07 |
| 2 | 129.9 | 264 | 0.13 |
| 4 | 217.4 | 326 | 0.22 |
| 8 | 376.0 | 378 | 0.37 |
| 16 | 653.3 | 505 | 0.65 |
| 32 | 999.5 | 738 | 1.00 |
| 64 | 1,260.2 | 1,115 | 1.26 |
| **128** | **1,320.4** | 2,189 | **1.32** |

### vLLM V1 Benchmark (v0.11.2 - 2026-02-05, Unstable)

| Concurrency | Run 1 (tokens/s) | Run 2 (tokens/s) | Variance | Status |
|:-----------:|:----------------:|:----------------:|:--------:|:------:|
| 1 | 17.2 | 17.2 | 0% | ✅ |
| 2 | 31.6 | 31.6 | 0% | ✅ |
| 4 | 50.7 | 56.5 | +11% | ✅ |
| 8 | 102.9 | 89.4 | -13% | ✅ |
| 16 | 171.1 | 170.3 | -0.5% | ✅ |
| 32 | 314.5 | 314.7 | +0.1% | ✅ |
| **64** | **553.0** | **610.4** | **+10%** | **🏆 Peak** |
| 128 | Crash | Stall | - | ❌ Known Issue |

**vLLM V0 Peak (Production Load)**: 304.4 tokens/s @ C=33 (v0.10.1, 1,801 requests, zero crashes)

---

## 📐 Architecture

### Multi-Node Parallelism: TP=2 + PP=2

![Architecture](images/architecture.png)



### Why TP=2 + PP=2?

| Parallelism | Communication | Bandwidth | Location |
|-------------|---------------|-----------|----------|
| **Tensor Parallel (TP=2)** | All-reduce every layer | 600 GB/s NVLink | Intra-node |
| **Pipeline Parallel (PP=2)** | Point-to-point between stages | Ethernet | Inter-node |

**Mathematical Rationale**:
- TP requires **all-reduce** after every layer's attention/FFN → high bandwidth critical
- PP only requires **point-to-point** activation transfer between stages → tolerates lower bandwidth
- H100 NVL provides 600 GB/s NVLink within node, but only ~10 Gbps Ethernet between nodes
- **Conclusion**: TP within node (NVLink), PP across nodes (Ethernet) is optimal

---

## 🔌 Software Stack & Communication Architecture

### Component Roles

| Component | Role | Phase | Analogy |
|-----------|------|-------|---------|
| **vLLM** | Inference engine + API server | All phases | The "brain" — decides what to compute |
| **Ray** | Distributed process scheduler | Startup only | "HR department" — places workers on correct machines |
| **NCCL** | GPU-to-GPU communication library | Inference | "Nervous system" — transfers tensors between GPUs |
| **NVLink** | Physical interconnect (intra-node) | Inference | "Highway" — 600 GB/s bandwidth |
| **TCP/eth0** | Physical interconnect (inter-node) | Inference | "Country road" — ~10 Gbps bandwidth |

### What is Ray?

[Ray](https://github.com/ray-project/ray) is a distributed computing framework developed by UC Berkeley RISELab (38k+ GitHub stars). In this setup, **vLLM calls Ray** (not the other way around) via `--distributed-executor-backend ray`.

Ray's job is simple:
1. **Resource discovery**: ray-head starts GCS (Global Control Store), ray-worker registers → Ray knows the cluster has 4 GPUs across 2 nodes
2. **Process scheduling**: vLLM requests 4 GPU workers, Ray places 2 on each node
3. **Done**: After workers are placed, Ray steps back. It does NOT transfer inference data.

### End-to-End Request Flow

```
Client (curl/Python)
  │
  │ HTTP (:8000)
  ▼
vLLM API Server (node0, ray-head container)
  │
  │ Dispatches to GPU workers (managed by Ray at startup)
  ▼
┌─── PP Stage 0 (node0) ───────────────┐
│  GPU0 ◄──NCCL/NVLink──► GPU1         │  TP=2: All-reduce every layer
│  (Layers 0-39)                        │  Bandwidth: 600 GB/s
└──────────────┬────────────────────────┘
               │
               │ NCCL over TCP/eth0 (Pipeline Parallel)
               │ Transfers: intermediate activations (~tens of MB)
               │ Bandwidth: ~10 Gbps
               │
┌──────────────▼────────────────────────┐
│  GPU2 ◄──NCCL/NVLink──► GPU3         │  TP=2: All-reduce every layer
│  (Layers 40-79)                       │  Bandwidth: 600 GB/s
└─── PP Stage 1 (node1) ───────────────┘
               │
               │ NCCL over TCP/eth0 (result back to node0)
               ▼
vLLM API Server → HTTP Response → Client
```

### Protocol Stack (Per Layer)

| What happens | Who does it | Protocol | Physical medium | Bandwidth |
|-------------|-------------|----------|----------------|-----------|
| Client → vLLM | Test script | **HTTP** | Internet/LAN | N/A |
| GPU0 ↔ GPU1 (TP all-reduce) | vLLM via PyTorch | **NCCL** | NVLink | 600 GB/s |
| GPU2 ↔ GPU3 (TP all-reduce) | vLLM via PyTorch | **NCCL** | NVLink | 600 GB/s |
| node0 → node1 (PP activation) | vLLM via PyTorch | **NCCL** | TCP/eth0 | ~10 Gbps |
| node1 → node0 (PP result) | vLLM via PyTorch | **NCCL** | TCP/eth0 | ~10 Gbps |

**Key insight**: NCCL is used for ALL GPU communication (both intra-node and inter-node), but the underlying physical medium differs. The test script only sees HTTP — NCCL is completely transparent to the client.

### Timeline: Who Works When?

```
[Startup Phase]                      [Inference Phase - every request]
                                     
Ray ████████░░░░░░░░░░░░░░░░         Ray ░░░░░░░░░░░░░░░ (idle)
     ↑ discover & schedule                                
                                     NCCL ░░░████████████ (active every token)
NCCL ░░░░░░░░████░░░░░░░░░░░              ↑ TP all-reduce + PP transfer
          ↑ init comm groups
                                     vLLM ████████████████ (orchestrating)
vLLM ████████████░░░░░░░░░░░
     ↑ load model, init engine
```

---

## 🔧 NCCL Optimization (Critical for Azure)

Azure VMs have multiple network interfaces (eth0, docker0, etc.). NCCL may select the wrong interface, causing cross-node communication failures or service hangs.

**Solution**: Set `NCCL_SOCKET_IFNAME=eth0` before starting the inference server to force NCCL to use the correct interface.

**Reference**: [vLLM GitHub Issue #10419](https://github.com/vllm-project/vllm/issues/10419)

| Metric | Before NCCL Fix | After NCCL Fix | Change |
|--------|-----------------|----------------|--------|
| Service Startup | Intermittent hang | ✅ Stable | Fixed |
| C=64 Throughput | 553.0 t/s | 610.4 t/s | **+10%** |
| C=128 Stability | Crash | Still unstable | Known issue |

---

## ⚠️ Known Issues

### V1 Engine + PP Crash (vLLM v0.11.x)

vLLM v0.11.x with V1 engine + Pipeline Parallel (`PP > 1`) crashes due to a Ray compiled DAG bug. This affects ALL multi-node PP deployments on v0.11.x.

**Root Cause**: The V1 engine uses **Ray compiled DAG** for inter-node PP communication. This code path has bugs:
1. **Attribute mismatch**: `_accelerator_group` was renamed to `_accelerator_group_id` but callers were not updated
2. **C++ deserialization crash**: In `experimental_mutable_object_provider.cc` — Raylet core dumps
3. V0 engine was **completely removed** in vLLM v0.11.0 (PR #15256), so `VLLM_USE_V1=0` is a NO-OP on v0.11.x

**Related GitHub Issues (all open as of 2026-02-06)**:
- [vllm #26899](https://github.com/vllm-project/vllm/issues/26899) — PP crashes with compiled DAG
- [vllm #29373](https://github.com/vllm-project/vllm/issues/29373) — Multi-node PP Raylet crash
- [ray #59404](https://github.com/ray-project/ray/issues/59404) — compiled DAG accelerator channel bug

---

## 🔽 v0.10.1 Downgrade Solution (V0 Engine)

### Why v0.10.1?

| Version | V0 Engine | V1 Engine | PP Stability |
|---------|-----------|-----------|-------------|
| v0.10.1 | ✅ Available | ✅ Default | ✅ V0 stable (bypasses compiled DAG) |
| v0.11.0+ | ❌ **Removed** | ✅ Only option | ❌ Crashes (compiled DAG bug) |

**v0.10.1 + `VLLM_USE_V1=0`** → V0 engine → `RayGPUExecutor` (traditional Ray task scheduling) → completely bypasses compiled DAG → stable PP

### V0 vs V1 Architecture for PP

| Component | V1 Engine (v0.11.x) | V0 Engine (v0.10.1) |
|-----------|--------------------|--------------------|  
| PP communication | Ray compiled DAG → TorchTensorAcceleratorChannel | Ray task scheduling → RayGPUExecutor |
| Performance | ~10-20% faster throughput | Baseline |
| PP stability | ❌ Crashes (compiled DAG bug) | ✅ Stable |

### Production Validation (v0.10.1 V0 Engine)

Tested with real production traffic:

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Successful Requests** | **1,801** | All returned 200 OK |
| **Server Errors (5xx)** | **0** | Zero server-side errors |
| **Crashes** | **0** | Zero crashes throughout entire session |
| **Peak Concurrent Requests** | **91** | KV cache usage: 3.9% (abundant headroom) |
| **Peak Generation Throughput** | **304.4 tokens/s** | @ ~30 concurrent |
| **Peak Prompt Throughput** | **18,322 tokens/s** | Prefill phase |
| **TTFT (idle)** | **141-146 ms** | Measured post-test |

### Deployment Summary (v0.10.1)

The deployment uses Docker containers with `vllm/vllm-openai:v0.10.1` image in a Ray cluster setup:

1. **Worker node**: Start Ray worker container, join cluster
2. **Head node**: Start Ray head container, verify cluster with `ray status`
3. **Launch vLLM**: Inside head container, set `VLLM_USE_V1=0` environment variable, then start vLLM with `--tensor-parallel-size 2 --pipeline-parallel-size 2 --distributed-executor-backend ray`

Key parameters: `--max-model-len 16384`, `--gpu-memory-utilization 0.90`, `--enforce-eager`, `--enable-auto-tool-choice --tool-call-parser hermes`

> **Note**: v0.10.1 release notes warn about FP8 kv-cache in V0 engine, but this only affects the `--kv-cache-dtype fp8` flag. Default BF16 KV cache (FP8 for model weights only) is **not affected**.

---

## 📊 Detailed Benchmark Results

### Test Parameters

| Parameter | Scenario 1 | Scenario 2 |
|-----------|------------|------------|
| Input tokens | 1024 | 10240 |
| Output tokens | 1024 | 1024 |
| Concurrency levels | 1, 2, 4, 8, 16, 32, 64, 128 | Same |

### Run 1 Results (Initial Test)

| Concurrency | QPS | TTFT (ms) | Avg Latency (s) | Throughput (t/s) |
|:-----------:|:---:|:---------:|:---------------:|:----------------:|
| 1 | 0.11 | 81 | 8.75 | 17.2 |
| 2 | 0.21 | 108 | 8.66 | 31.6 |
| 4 | 0.37 | 115 | 9.38 | 50.7 |
| 8 | 0.70 | 131 | 8.52 | 102.9 |
| 16 | 1.18 | 147 | 10.11 | 171.1 |
| 32 | 2.16 | 162 | 11.13 | 314.5 |
| 64 | 3.78 | 173 | 12.98 | 553.0 |
| 128 | - | - | Crash | - |

### Run 2 Results (After NCCL Optimization)

| Concurrency | QPS | TTFT (ms) | Avg Latency (s) | Throughput (t/s) |
|:-----------:|:---:|:---------:|:---------------:|:----------------:|
| 1 | 0.11 | 93 | 9.50 | 17.2 |
| 2 | 0.21 | 122 | 9.00 | 31.6 |
| 4 | 0.37 | 131 | 9.61 | 56.5 |
| 8 | 0.64 | 140 | 9.11 | 89.4 |
| 16 | 1.17 | 149 | 10.17 | 170.3 |
| 32 | 2.18 | 163 | 11.07 | 314.7 |
| 64 | 4.22 | N/A* | 69.88 | **610.4** |
| 128 | - | - | Stall | - |

*Note: C=64 in Run 2 used `stream=False`, so TTFT not measured. Reference TTFT from Run 1: 173ms.

### Variance Analysis

| Concurrency | Variance | Assessment |
|:-----------:|:--------:|:-----------|
| 1-2 | 0% | Perfectly stable |
| 4 | +11% | Normal variance |
| 8 | -13% | Normal variance |
| 16-32 | <1% | Very stable |
| **64** | **+10%** | **NCCL fix benefit** |

---

## 🖥️ Hardware Specifications

### Azure NC80adis_H100_v5

| Component | Specification |
|-----------|---------------|
| **GPU** | 2× NVIDIA H100 NVL (PCIe form factor) |
| **GPU Memory** | 94 GB HBM3 per GPU (188 GB total per node) |
| **GPU Interconnect** | NVLink 600 GB/s (between 2 GPUs in same node) |
| **vCPU** | 80 vCPUs (AMD EPYC 4th Gen "Genoa") |
| **RAM** | 640 GiB |
| **Local NVMe** | ~7 TB |

### H100 NVL vs H100 SXM

| Feature | H100 NVL | H100 SXM |
|---------|----------|----------|
| Form Factor | PCIe | SXM5 |
| Memory | 94 GB HBM3 | 80 GB HBM3 |
| NVLink Bandwidth | 600 GB/s (2-GPU bridge) | 900 GB/s (NVSwitch fabric) |
| Target Use Case | **LLM Inference** | Training |
| Multi-GPU Scaling | 2-way optimal | 8-way optimal |

**Why 2 nodes × 2 GPUs works well**:
- H100 NVL is designed for 2-GPU tight coupling (600 GB/s NVLink)
- For >2 GPUs, NVL must use PCIe (~128 GB/s) which becomes bottleneck
- Using PP across nodes avoids this bottleneck

---

## 🔄 SGLang Migration (2026-02-11)

### Why Migrate from vLLM to SGLang?

| Factor | vLLM V0 (v0.10.1) | vLLM V1 (v0.11.2) | SGLang v0.5.8 |
|--------|:------------------:|:------------------:|:-------------:|
| Single TPS | 6.8 t/s | 17 t/s | **70-75 t/s** |
| ITL | ~158 ms | ~57 ms | **13.3 ms** |
| PP>1 Stability | ✅ Stable | ❌ Crashes | ✅ Stable |
| Function Calling | ✅ Hermes | ✅ Hermes | ✅ Qwen parser |
| Status | **Too slow** | **Too unstable** | **✅ Production** |

**Pain Point**: With vLLM V0 in production, an 880-token response took ~140s (ITL=158ms) — unacceptable latency. With SGLang (ITL=13.3ms), the same response takes ~11.8s.

### SGLang Benchmark Details

#### Stability Test (516 requests, zero failures)

| Concurrency | Requests | Completed | Failed | Throughput (t/s) |
|:-----------:|:--------:|:---------:|:------:|:----------------:|
| 1 | 10 | 10 | 0 | 37.2 |
| 4 | 10 | 10 | 0 | 117.6 |
| 8 | 16 | 16 | 0 | 228.5 |
| 16 | 32 | 32 | 0 | 388.6 |
| 32 | 64 | 64 | 0 | 637.2 |
| 64 | 128 | 128 | 0 | 836.7 |
| 128 | 256 | 256 | 0 | 975.4 |
| **Total** | **516** | **516** | **0** | — |

#### Function Calling Test (5/5 passed)

| Test Case | tool_choice | Expected | Result |
|-----------|:-----------:|:--------:|:------:|
| Weather query | auto | Tool call | ✅ `get_weather(city="Beijing")` |
| Weather query | **required** | Tool call | ✅ `get_weather(city="Shanghai")` |
| Math question | auto | No tool | ✅ Direct answer |
| Info search | specific (`search_database`) | Specific tool | ✅ `search_database(query="AI agents")` |
| Weather (streaming) | required | Tool call (stream) | ✅ `get_weather(city="Tokyo")` |

#### ITL Precision Test

| Scenario | TTFT (ms) | ITL avg (ms) | ITL P50 (ms) | ITL P99 (ms) | TPS |
|----------|:---------:|:------------:|:------------:|:------------:|:---:|
| Short CN (128→512) | 110 | 13.2 | 13.2 | 13.5 | 74.8 |
| Medium EN (512→1024) | 141 | 13.3 | 13.3 | 13.8 | 72.9 |
| Long EN (1024→1024) | 131 | 13.3 | 13.3 | 13.7 | 73.6 |
| Long CN (1024→1024) | 142 | 13.2 | 13.2 | 13.6 | 74.1 |

### Technical Root Cause: Why SGLang Is 10× Faster

| Root Cause | vLLM V0 Impact | SGLang Solution |
|------------|:--------------:|:---------------:|
| **Scheduling overhead** | V0's `RayGPUExecutor` uses Ray task scheduling per step — ~4-5ms overhead/token | SGLang uses custom NCCL-based PP, no per-step Ray overhead |
| **PP communication** | NCCL over TCP with Ray intermediary, extra serialization | Direct NCCL P2P with overlap scheduling |
| **Batch scheduling** | V0 lacks continuous batching optimization | RadixAttention + continuous batching |
| **Kernel optimization** | V0 uses older attention kernels | FlashAttention 3 + FlashInfer sampling |
| **Prefill strategy** | No chunked prefill in V0 | Chunked prefill reduces queuing |

**vLLM V0 ITL Breakdown (PP=2)**:
Each decode step is dispatched as a Ray task. For PP=2, each token requires: Ray task dispatch (~1ms) → GPU compute stage 0 (~3ms) → NCCL send to node1 (~2ms) → GPU compute stage 1 (~3ms) → NCCL result back (~2ms) → Ray callback (~1ms) = ~12ms GPU cycle, but with Ray scheduling jitter and GIL contention, actual ITL ≈ 158ms. SGLang eliminates the Ray per-step overhead entirely.

### SGLang Key Configuration Notes (PP>1)

| Parameter | Rationale |
|-----------|-----------|
| `--tool-call-parser qwen` | Qwen3 native format (NOT hermes — hermes works but qwen is more compatible) |
| `--disable-radix-cache` | **Required** for PP>1 — radix cache incompatible with pipeline parallelism |
| `--mem-fraction-static 0.85` | Conservative GPU memory allocation for stability |
| `--chunked-prefill-size 6144` | Balance between TTFT and throughput |
| `NCCL_SOCKET_IFNAME=eth0` | Force correct Azure network interface |
| `NCCL_IB_DISABLE=1` | No InfiniBand on Azure NC series |

### Failed Optimizations (PP>1 Incompatible — Do NOT Use)

| Optimization | Error | Root Cause |
|-------------|-------|------------|
| `--kv-cache-dtype fp8_e4m3` | NCCL error during CUDA graph capture | FP8 KV cache format mismatch during cross-node PP transfer |
| `--enable-mixed-chunk` | `AssertionError: not compatible with PP` | Mixed chunk prefill assumes single-stage scheduling |
| `--num-continuous-decode-steps 2` | Hangs/timeout | Multi-step decode breaks PP synchronization |
| `NCCL_ALGO=Tree` | NCCL error during CUDA graph capture | Tree algorithm conflicts with PP point-to-point pattern |

**Conclusion**: For PP>1 on SGLang, use the vanilla configuration only. All "standard" optimizations are designed for single-node or TP-only setups.

### Performance Impact Summary

| Metric | Before (vLLM V0) | After (SGLang) | Improvement |
|--------|:-----------------:|:--------------:|:-----------:|
| **ITL** | 158 ms | 13.3 ms | **12× faster** |
| **880-token response** | ~140 s | ~11.8 s | **12× faster** |
| **Single-request TPS** | 6.8 t/s | 70-75 t/s | **10× faster** |
| **Peak throughput** | 304 t/s | 1,320 t/s | **4.3× faster** |
| **Crash count** | 0 (V0) | 0 | Both stable |

**Remaining gap vs single-node setup**: Caused by physical cross-node Ethernet PP communication overhead (~2-3ms per token round trip). This is a hardware topology limitation — cannot be fixed in software. To fully eliminate this overhead, use a single-machine 4×H100 SXM (eliminates PP entirely, all communication via NVSwitch at 900 GB/s).

---

## 🎯 Recommendations

### Engine Selection

| Scenario | Recommended Engine |
|----------|-------------------|
| Multi-node PP deployment | **SGLang** (stable + fast) |
| Single-node TP only | vLLM V1 or SGLang |
| vLLM PP (must use vLLM) | v0.10.1 + `VLLM_USE_V1=0` (V0 engine) |
| vLLM v0.11.x + PP | ❌ Not recommended (compiled DAG crash) |

### When to Use Multi-Node PP

| Model Size | GPUs Needed | Recommended Setup |
|------------|-------------|-------------------|
| < 70B | 1-2 | Single node, TP only |
| 70B - 100B | 2-4 | Single node TP=4 or 2-node PP=2 |
| **100B - 250B** | **4** | **2-node TP=2 PP=2** ✅ |
| > 250B | 8+ | 4+ nodes, consider SXM |

### Concurrency Guidelines

| Concurrency | Recommendation |
|-------------|----------------|
| 1-32 | ✅ Stable, use freely |
| **64-128** | ✅ **Sweet spot for peak throughput (SGLang)** |
| 128+ (vLLM) | ⚠️ Not recommended (known instability) |

---

**Author**: Xinyu Wei (魏新宇)
**Date**: 2026-02-06 (initial vLLM), 2026-02-11 (SGLang Migration)
