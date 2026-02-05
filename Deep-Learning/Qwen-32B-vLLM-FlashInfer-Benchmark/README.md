# vLLM Attention Backend Benchmark: Qwen3-32B-FP8 on H100 NVL

> **Author**: Xinyu Wei (魏新宇)  
> **Date**: 2026-02-05 (Updated)  
> **Model**: Qwen3-32B-FP8 (32GB, FP8 Quantization)  
> **GPU**: NVIDIA H100 NVL 94GB  
> **Benchmark Scenario**: (1024 input, 1024 output), Streaming mode

---

## 📊 Executive Summary

This benchmark compares **FlashAttention 2 (FA2)** vs **FlashInfer** attention backends for vLLM inference on H100 NVL GPU.

### ⚠️ Critical Update (2026-02-05)

**Previous benchmark had methodology flaws** - comparing different vLLM versions (0.11.2 vs 0.15.0) led to incorrect conclusions. This update provides **fair comparison using the same vLLM version**.

### Key Findings (Fair Comparison on vLLM 0.11.2)

| Metric | FlashAttention 2 | FlashInfer | Difference |
|--------|------------------|------------|------------|
| **Peak Throughput (512 concurrent)** | **4,022.6 t/s** | 3,741.4 t/s | **FA2 +7.5%** |
| **TTFT @ 512 concurrent** | **1,116 ms** | 1,866 ms | **FA2 -40%** |
| **Low Concurrency (1-128)** | ~ | +1~3% | FlashInfer slightly faster |
| **High Concurrency (256-512)** | **+5~7%** | ~ | **FA2 significantly faster** |

🏆 **Conclusion**: On vLLM 0.11.2 + H100 + FP8 models, **FlashAttention 2 outperforms FlashInfer at high concurrency** (+7.5% peak throughput, -40% TTFT).

---

## 🔬 Why Previous Benchmark Was Wrong

### The Unfair Comparison Problem

| Config | vLLM Version | Attention Backend | Peak Throughput |
|--------|--------------|-------------------|-----------------|
| **Previous "Baseline"** | 0.11.2 | FlashAttention 2 | 3,907.8 t/s |
| **Previous "Optimized"** | 0.15.0 | FlashInfer | 4,531.3 t/s |
| **Claimed Improvement** | - | - | +16% |

**Problem**: The 16% improvement came from **vLLM version upgrade (0.11.2 → 0.15.0)**, NOT from the attention backend difference!

### Fair Comparison (Same vLLM 0.11.2)

| Config | vLLM Version | Attention Backend | Peak Throughput |
|--------|--------------|-------------------|-----------------|
| **FA2** | 0.11.2 | FLASH_ATTN | **4,022.6 t/s** |
| **FlashInfer** | 0.11.2 | FLASHINFER | 3,741.4 t/s |
| **Actual Difference** | - | - | **FA2 +7.5%** |

**Lesson Learned**: When comparing attention backends, **always use the same vLLM version**!

---

## 🧪 Test Environment

### Hardware Configuration

| Component | Specification |
|-----------|---------------|
| **GPU** | NVIDIA H100 NVL 94GB HBM3 (Single Card) |
| **vCPU** | 40 cores |
| **RAM** | 320 GB |
| **Storage** | 3.5 TB NVMe SSD |

### Software Configuration (Fair Test)

| Component | Version |
|-----------|---------|
| **vLLM** | 0.11.2 (Docker: vllm/vllm-openai:v0.11.2) |
| **CUDA** | 12.8 |
| **PyTorch** | 2.9.0+cu128 |
| **FlashAttention** | 2.8.3 (bundled in Docker) |
| **FlashInfer** | 0.5.2 (bundled in Docker) |

### Model Configuration

| Parameter | Value |
|-----------|-------|
| **Model** | Qwen/Qwen3-32B-FP8 |
| **Precision** | FP8 (E4M3) |
| **Model Size** | 32 GB |
| **max_model_len** | 4096 |
| **tensor_parallel_size** | 1 |
| **gpu_memory_utilization** | 0.95 |

---

## 🐳 Why Docker Instead of pip install?

### The Dependency Conflict Problem

When trying to install vLLM 0.11.2 via pip, we encountered **dependency conflicts**:

\`\`\`bash
# ❌ pip install failed
pip install vllm==0.11.2

# Error: huggingface_hub 0.32.0 requires transformers>=4.45.0,
# but vllm 0.11.2 requires transformers==4.51.3
\`\`\`

**Root Cause**: vLLM 0.11.2 was released in late 2025, and the Python ecosystem has evolved. Newer \`huggingface_hub\` versions are incompatible with the older \`transformers\` version that vLLM 0.11.2 requires.

### Solution: Use Official Docker Image

The official Docker image \`vllm/vllm-openai:v0.11.2\` has **all dependencies pre-locked and tested**:

| Component | Version (Locked in Docker) |
|-----------|---------------------------|
| vLLM | 0.11.2 |
| PyTorch | 2.9.0+cu128 |
| transformers | 4.51.3 |
| huggingface_hub | (compatible version) |
| FlashAttention | 2.8.3 |
| FlashInfer | 0.5.2 |

### Lesson Learned

> **When testing older vLLM versions, always use Docker images to avoid dependency conflicts.**
> pip install may work on a fresh environment, but will fail if you have newer packages installed.

---

## 📈 Benchmark Results (vLLM 0.11.2 Fair Comparison)

### FlashAttention 2 Results

| Concurrency | QPS | TTFT (ms) | Throughput (t/s) |
|-------------|-----|-----------|------------------|
| 1 | 0.08 | 26 | 55.7 |
| 4 | 0.27 | 37 | 195.2 |
| 8 | 0.45 | 41 | 344.4 |
| 16 | 0.80 | 46 | 600.7 |
| 32 | 1.51 | 52 | 1,096.6 |
| 64 | 2.70 | 63 | 1,889.7 |
| 128 | 4.21 | 102 | 2,759.9 |
| 256 | 5.45 | 145 | 3,607.2 |
| **512** | **6.22** | **1,116** | **4,022.6** |

### FlashInfer Results

| Concurrency | QPS | TTFT (ms) | Throughput (t/s) |
|-------------|-----|-----------|------------------|
| 1 | 0.08 | 31 | 55.4 |
| 4 | 0.27 | 38 | 200.6 |
| 8 | 0.45 | 44 | 354.9 |
| 16 | 0.89 | 53 | 613.2 |
| 32 | 1.58 | 60 | 1,110.2 |
| 64 | 2.72 | 79 | 1,923.6 |
| 128 | 3.84 | 129 | 2,788.7 |
| 256 | 4.88 | 205 | 3,444.6 |
| **512** | **5.35** | **1,866** | **3,741.4** |

### Side-by-Side Comparison

| Concurrency | FA2 Throughput | FI Throughput | Difference |
|-------------|----------------|---------------|------------|
| 1 | 55.7 | 55.4 | -0.5% |
| 4 | 195.2 | 200.6 | +2.8% |
| 8 | 344.4 | 354.9 | +3.0% |
| 16 | 600.7 | 613.2 | +2.1% |
| 32 | 1,096.6 | 1,110.2 | +1.2% |
| 64 | 1,889.7 | 1,923.6 | +1.8% |
| 128 | 2,759.9 | 2,788.7 | +1.0% |
| 256 | 3,607.2 | 3,444.6 | **-4.5%** |
| **512** | **4,022.6** | **3,741.4** | **-7.0%** |

---

## 🚀 Quick Start

### Prerequisites

- Docker installed
- NVIDIA GPU with CUDA 12.x
- Model downloaded to local path

### Running the Benchmark

\`\`\`bash
# Start vLLM server with FlashAttention 2 (default)
docker run -d --gpus all \\
  -v <your-model-path>:/models/Qwen3-32B-FP8 \\
  -p 8088:8000 \\
  --name vllm-fa2 \\
  vllm/vllm-openai:v0.11.2 \\
  --model /models/Qwen3-32B-FP8 \\
  --max-model-len 4096 \\
  --gpu-memory-utilization 0.95

# Start vLLM server with FlashInfer
docker run -d --gpus all \\
  -e VLLM_ATTENTION_BACKEND=FLASHINFER \\
  -v <your-model-path>:/models/Qwen3-32B-FP8 \\
  -p 8088:8000 \\
  --name vllm-fi \\
  vllm/vllm-openai:v0.11.2 \\
  --model /models/Qwen3-32B-FP8 \\
  --max-model-len 4096 \\
  --gpu-memory-utilization 0.95

# Run benchmark
python scripts/bench_0112.py
\`\`\`

---

## 🎯 Conclusions

### For vLLM 0.11.2 Users

1. **Use default FlashAttention 2** - vLLM's default choice is optimal for H100 + FP8
2. **Don't force FlashInfer** - Setting \`VLLM_ATTENTION_BACKEND=FLASHINFER\` will reduce performance by 7%
3. **Focus on other optimizations** - Chunked prefill, CUDA graph, etc.

### Performance Summary

| Scenario | Recommended Backend | Reason |
|----------|---------------------|--------|
| **Low Concurrency (1-128)** | Either | <3% difference, negligible |
| **High Concurrency (256-512)** | **FlashAttention 2** | 5-7% faster, 40% lower TTFT |

### Why FA2 is Faster on H100 + FP8?

1. **FP8 Tensor Core Optimization** - FA2 has better FP8 kernel implementations for H100
2. **Known FlashInfer Issue** - FlashInfer's \`use_tensor_cores\` heuristic doesn't work well with FP8 (GitHub Issue #9471)
3. **vLLM's Default Selection** - vLLM chooses FA2 as default on H100 precisely because it's faster

---

## 📚 References

- [vLLM Documentation](https://docs.vllm.ai/)
- [FlashInfer GitHub Issue #9471](https://github.com/vllm-project/vllm/issues/9471) - FP8 tensor cores heuristic
- [FlashAttention 2 Paper](https://arxiv.org/abs/2307.08691)
- [vLLM Docker Hub](https://hub.docker.com/r/vllm/vllm-openai)

---

## 📄 License

MIT License
