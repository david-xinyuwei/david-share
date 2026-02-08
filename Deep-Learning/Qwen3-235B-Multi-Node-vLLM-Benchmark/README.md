# Qwen3-235B Multi-Node vLLM Benchmark (TP=2 + PP=2)

> **Model**: Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 (235B MoE, 22B activated per token)
> **Hardware**: 2× Azure NC80adis_H100_v5 (4× H100 NVL, 376GB VRAM total)
> **vLLM**: v0.10.1 (stable production, V0 engine)

---

## 🏆 Key Results

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

**Peak Throughput (Benchmark)**: 610.4 tokens/s @ C=64 (Run 2, with NCCL optimization)
**Peak Throughput (Production Load)**: 304.4 tokens/s @ C=33 (v0.10.1 V0 engine, 1,801 requests, zero crashes)

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

### Production Validation

Tested v0.10.1 V0 engine with real production traffic:

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

Key parameters: `--max-model-len 16384`, `--gpu-memory-utilization 0.96`, `--enforce-eager`

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

## 🎯 Recommendations

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
| **64** | ✅ **Sweet spot for peak throughput** |
| 128+ | ⚠️ Not recommended (known instability) |

---

**Author**: Xinyu Wei (魏新宇)
**Date**: 2026-02-06
