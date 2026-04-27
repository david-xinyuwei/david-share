# MI300X vs H200: LLM Inference Benchmark for Dense and MoE Models

> **Author**: Xinyu Wei (魏新宇)  
> **Date**: 2026-04-27  
> **Purpose**: An objective, data-driven comparison of AMD Instinct MI300X and NVIDIA H200 for LLM inference, with focus on large MoE models and long-context workloads.

[中文版](README-CN.md)

---

## TL;DR

- **For dense models (Llama 8B–405B)**, H200 wins across the board: **+31% to +64%** throughput over MI300X.
- **For large MoE models (DeepSeek-R1 671B)**, MI300X can match or slightly beat H200 on online throughput (+10%), thanks to its **192GB HBM3** (vs H200's 141GB).
- **MI300X's sweet spot**: trillion-parameter MoE models with long context, where memory capacity is the binding constraint.
- **H200's advantage**: superior CUDA ecosystem, TensorRT-LLM optimization, NVLink bandwidth, and FP8 GEMM efficiency.
- **Bottom line**: GPU selection should be workload-driven, not brand-driven. This repo provides the data to make that decision.

---

## Hardware Specifications

| Spec | AMD MI300X | NVIDIA H200 SXM | NVIDIA H100 SXM | MI300X Advantage |
|:---|:---:|:---:|:---:|:---|
| **HBM Capacity** | **192 GB** | 141 GB | 80 GB | **+36% vs H200, +140% vs H100** |
| **HBM Bandwidth** | **5.3 TB/s** | 4.8 TB/s | 3.35 TB/s | +10% vs H200, +58% vs H100 |
| **FP16/BF16 TFLOPS** | 1,307 | 989 | 989 | +32% (theoretical) |
| **FP8 TFLOPS** | 2,610 | 1,979 | 1,979 | +32% (theoretical) |
| **Interconnect** | xGMI 896 GB/s | NVLink 900 GB/s | NVLink 900 GB/s | Comparable |
| **TDP (per GPU)** | 750W | 700W | 700W | +7% power |
| **Node Total Memory (8×)** | **1,536 GB** | 1,128 GB | 640 GB | **+36% vs H200** |

*Sources: AMD MI300X datasheet, NVIDIA H200/H100 datasheets*

**Key insight**: MI300X has **more of everything** on paper — more HBM, more bandwidth, more theoretical FLOPS. But real-world performance depends on software optimization, kernel efficiency, and workload characteristics.

---

## Benchmark 1: Dense Models (Llama) — H200 Wins

*Source: [Azure AI Benchmarking Guide](https://github.com/Azure/AI-benchmarking-guide) (Microsoft official)*

### Setup
- **Engine**: vLLM with FP8 quantization, 1000 requests
- **MI300X**: ND MI300X v5 (ROCm 6.8.5)
- **H200**: ND H200 v5 (CUDA 12.8)
- **H100**: ND H100 v5 (CUDA 12.6)

### Llama 3.1 8B (TP=1)

| ISL/OSL | MI300X | H100 | H200 | MI300X vs H200 | MI300X vs H100 |
|:---|:---:|:---:|:---:|:---|:---|
| 128/128 | 18,149 | 15,163 | **25,302** | -28% | +20% |
| 128/2048 | 16,394 | 15,014 | **25,366** | -35% | +9% |
| 1024/1024 | 10,995 | **11,724** | **16,828** | -35% | -6% |
| 2048/2048 | 7,356 | 8,026 | **11,642** | -37% | -8% |

### Llama 3 70B (TP=8)

| ISL/OSL | MI300X | H100 | H200 | MI300X vs H200 | MI300X vs H100 |
|:---|:---:|:---:|:---:|:---|:---|
| 128/128 | 9,026 | 10,032 | **12,306** | -27% | -10% |
| 128/2048 | 12,204 | 12,910 | **18,573** | -34% | -5% |
| 1024/1024 | 8,256 | 9,125 | **11,389** | -28% | -10% |
| 2048/2048 | 7,421 | 7,908 | **10,495** | -29% | -6% |

### Llama 3 405B (TP=8)

| ISL/OSL | MI300X | H100 | H200 | MI300X vs H200 | MI300X vs H100 |
|:---|:---:|:---:|:---:|:---|:---|
| 128/128 | 2,484 | 2,515 | **3,262** | -24% | -1% |
| 128/2048 | 3,902 | 3,434 | **5,179** | -25% | +14% |
| 1024/1024 | 2,363 | 2,422 | **3,121** | -24% | -2% |
| 2048/2048 | 1,840 | 1,973 | **3,014** | -39% | -7% |

### Analysis

**H200 dominates dense models by +24% to +39%** despite MI300X having higher theoretical specs. Why?

1. **NCCL vs RCCL**: H200 AllReduce at 8GB reaches **481 GB/s** vs MI300X's 317 GB/s — a **52% gap** in multi-GPU communication. TP=8 amplifies this.
2. **FP8 GEMM efficiency**: CuBLAS FP8 GEMM (4096×4096) delivers 1,249 TFLOPS on H200 vs 1,085 TFLOPS on MI300X — H200 converts more theoretical FLOPS into real throughput.
3. **Software maturity**: CUDA + cuBLAS + FlashAttention optimizations have years of head start over ROCm + hipBLAS.

**Exception**: MI300X beats H100 (not H200) on 405B with long output (128/2048: +14%), because the 405B model at FP8 nearly fills H100's 80GB but sits comfortably in MI300X's 192GB.

---

## Benchmark 2: MoE Model (DeepSeek-R1 671B) — MI300X Competitive

*Source: [dstack benchmark](https://dstack.ai/blog/h200-mi300x-deepskeek-benchmark/) (independent third-party)*

### Setup
- **Model**: DeepSeek-R1 671B FP8 (MoE, 256 experts)
- **Engines**: SGLang, vLLM, TensorRT-LLM
- **Input**: 3,200 tokens, Output: 800 tokens
- **Hardware**: 8×MI300X (Vultr) vs 8×H200 (Lambda)

### Peak Throughput

| Scenario | MI300X Best | H200 Best | Winner |
|:---|:---|:---|:---|
| **Online (serving)** | **4,574 tok/s** (vLLM) | 4,176 tok/s (TRT-LLM) | **MI300X +10%** |
| **Offline (max throughput)** | — | **6,311 tok/s** (SGLang) | **H200** |

### Latency Breakdown

| Metric | MI300X Behavior | H200 Behavior | Winner |
|:---|:---|:---|:---|
| **TTFT (low concurrency)** | Higher | **Lower** | H200 — compute-bound prefill favors H200 GEMM |
| **TTFT (128 concurrency)** | **Lower** | Higher | MI300X — 192GB survives KV cache pressure |
| **TPOT** | Theoretically better | Similar in practice | Tie — ROCm gap offsets HBM advantage |
| **TTFT vs output length** | **Stable** | vLLM/TRT-LLM spike | MI300X — more headroom for KV cache |

### Why MI300X Competes on MoE

DeepSeek-R1 671B is **the perfect workload for MI300X**:

1. **Memory capacity is the bottleneck**: 671B parameters in FP8 = ~640GB. 8×MI300X = 1,536GB total vs 8×H200 = 1,128GB. The extra 400GB allows larger batches and more KV cache.
2. **256 expert weights**: MoE models load different expert weights per token per layer. More HBM = less weight swapping.
3. **Long chain-of-thought**: Reasoning models generate thousands of thinking tokens. More HBM bandwidth = faster decode.
4. **Diminished NVLink advantage**: MoE expert routing is less AllReduce-heavy than dense TP — MI300X's xGMI gap matters less.

---

## Benchmark 3: Micro-level Comparison

*Source: [Azure AI Benchmarking Guide](https://github.com/Azure/AI-benchmarking-guide)*

| Metric | MI300X | H100 | H200 | Analysis |
|:---|:---:|:---:|:---:|:---|
| **HBM Copy** | **4.15 TB/s** | 2.90 TB/s | 4.01 TB/s | MI300X leads — explains decode advantage |
| **FP8 GEMM 4K** | 1,085 TF | 1,217 TF | **1,249 TF** | H200 leads — explains prefill advantage |
| **FP8 GEMM 8K** | 1,223 TF | **1,290 TF** | 1,269 TF | H100 actually highest at large sizes |
| **Flash Attn 2.0** | 328.6 TF | 327.9 TF | 329.3 TF | All comparable |
| **AllReduce 8GB** | 316.8 GB/s | 478.9 GB/s | **480.9 GB/s** | H200/H100 NVLink **+52%** over xGMI |

**The physics of GPU inference**:
- **Prefill** (TTFT) is compute-bound → GEMM efficiency matters → **H200 wins**
- **Decode** (TPOT) is memory-bandwidth-bound → HBM bandwidth matters → **MI300X wins**
- **Multi-GPU** communication → AllReduce bandwidth matters → **H200 wins**
- **Memory capacity** → KV cache size limit → **MI300X wins**

---

## AMD's Own Data: MI300X vs H100

*Source: AMD Instinct MI300X GBB Training Materials (October 2024), publicly referenced data points*

AMD's internal benchmarks (using vLLM for MI300X, TRT-LLM for H100) on Llama 3.1:

| Model | Metric | MI300X vs H100 |
|:---|:---|:---|
| **Llama 3.1 70B** | E2E Latency | **1.44× faster** |
| | TPOT (decode) | **1.52× faster** |
| | TTFT (prefill) | 0.81× (slower) |
| **Llama 3.1 405B** | E2E Latency | **1.45× faster** |
| | TPOT (decode) | **1.62× faster** |
| | TTFT (prefill) | 0.76× (slower) |

**Key observations**:
- MI300X's **1.5-1.6× TPOT advantage** (decode phase) comes directly from HBM bandwidth superiority
- MI300X's **0.76-0.81× TTFT disadvantage** (prefill phase) comes from lower effective GEMM throughput
- **E2E MI300X wins** because most real-world inference is decode-dominant (output tokens >> input tokens)

> **⚠️ Fairness note**: AMD used vLLM for MI300X but TRT-LLM for H100. TRT-LLM is generally faster than vLLM on NVIDIA hardware. If H100 also used vLLM, the MI300X advantage would likely be larger. If MI300X had a TRT-LLM equivalent, results might differ.

**Additional benchmarks from AMD**:
- Mixtral (MoE): MI300X **1.41×** throughput vs H100
- Mistral 7B: MI300X **1.27×** throughput vs H100
- SDXL (diffusion): MI300X **1.00×** (parity) vs H100

---

## Real-World Production Evidence

| Organization | Hardware | Workload | Key Quote |
|:---|:---|:---|:---|
| **Meta** | MI300X | Llama 405B live traffic | "All Meta (Llama 405B) live traffic has been served using MI300X exclusively due to its large memory capacity and TCO advantage" — Kevin Salvadore, VP Infrastructure |
| **Databricks** | MI300X | Model training & inference | "ROCm capabilities have expanded significantly... Many of our models and workflows can run seamlessly on AMD HW with no modification" — Naveen Rao, VP of AI |
| **Essential AI** | MI300X | Large-scale training | "We are seeing per device best-in-class performance, the linear scaling characteristics are extremely exciting" — Ashish Vaswani, Co-Founder & CEO |
| **Microsoft** | MI300X | M365 Copilot | "These VMs are part of the leading AI infrastructure platform that runs GPT-4 Turbo and underpins critical M365 Copilot scenarios" — Jason Henderson, CVP M365 Core |

---

## Decision Framework: When to Choose MI300X vs H200

| Workload Characteristic | Choose MI300X | Choose H200 |
|:---|:---:|:---:|
| **Dense model ≤ 70B** | | ✅ |
| **Dense model 405B** | Tie | ✅ |
| **MoE model 200B+** | ✅ | Tie |
| **MoE model 600B+ (e.g., DeepSeek-R1)** | ✅ | |
| **Trillion-parameter MoE** | ✅✅ | |
| **Long context (32K+ tokens)** | ✅ | |
| **Short context, high throughput** | | ✅ |
| **Batch inference (offline)** | | ✅ |
| **Real-time serving (online)** | Depends on model | Depends on model |
| **Multi-node training** | | ✅ |
| **Single-node inference** | ✅ (if memory-bound) | ✅ (if compute-bound) |
| **Prefix caching needed** | ⚠️ (ROCm WiP) | ✅ |
| **TensorRT-LLM ecosystem** | ❌ | ✅ |
| **PyTorch/Triton ecosystem** | ✅ | ✅ |
| **Budget-sensitive** | ✅ (typically lower $/GPU) | |

### The Memory Capacity Rule

For any model where **total weights + KV cache** approaches or exceeds the GPU memory:

```
MI300X: 8 × 192GB = 1,536 GB available
H200:   8 × 141GB = 1,128 GB available
H100:   8 × 80GB  =   640 GB available
```

A trillion-parameter MoE model in FP8 requires ~1TB for weights alone. Add KV cache for long context (32K+ tokens) at high concurrency, and **H200's 1,128GB can become the bottleneck while MI300X's 1,536GB still has headroom**.

This is exactly the scenario for:
- DeepSeek-R1/V3 (671B, 256 experts)
- Trillion-parameter MoE models with long context reasoning

---

## Software Ecosystem Comparison

| Aspect | MI300X (ROCm) | H200 (CUDA) | Gap |
|:---|:---|:---|:---|
| **PyTorch** | Fully upstreamed | Native | Parity |
| **Triton kernels** | ROCm backend | CUDA backend | Parity |
| **vLLM** | Supported | Supported | H200 ~30% faster (kernel optimization) |
| **SGLang** | Supported | Supported | Comparable |
| **TensorRT-LLM** | ❌ Not available | ✅ Best performance | H200 exclusive |
| **FlashAttention** | FA 2.0 via CK | FA 2/3 native | H200 ahead (FA3) |
| **NCCL/RCCL** | RCCL | NCCL | NCCL more mature, +52% AllReduce |
| **Prefix caching** | ⚠️ WiP on ROCm | ✅ Full support | H200 ahead |
| **FP8 quantization** | Block-wise FP8 | Block-wise FP8 | Parity |
| **Custom CUDA kernels** | Need HIPIFY porting | Native | H200 easier |
| **Model coverage** | 700K+ models run on ROCm | All models | MI300X catching up |

**Bottom line**: CUDA ecosystem has a **significant lead** in optimization depth, but ROCm has closed the gap substantially — PyTorch and Triton workloads run with no code changes. The remaining gap is in **proprietary optimizations** (TRT-LLM, FlashAttention 3, NCCL tuning).

---

## Pricing Context (Azure, as of 2026)

| VM Size | GPUs | Price/hr (Pay-as-you-go) | Price/GPU/hr |
|:---|:---:|:---:|:---:|
| **ND MI300X v5** | 8× MI300X | ~$27/hr | ~$3.38 |
| **ND H200 v5** | 8× H200 | ~$36/hr | ~$4.50 |
| **ND H100 v5** | 8× H100 | ~$32/hr | ~$4.00 |

> ⚠️ Pricing varies by region and commitment. Check [Azure pricing](https://azure.microsoft.com/pricing/) for current rates.

**Cost-performance for DeepSeek-R1 671B online inference**:
- MI300X: 4,574 tok/s ÷ $27/hr = **169 tok/s/$**
- H200: 4,176 tok/s ÷ $36/hr = **116 tok/s/$**
- **MI300X delivers 46% better cost-performance** on this specific MoE workload

---

## Conclusion

1. **No single GPU wins everything.** H200 dominates dense models; MI300X has an edge on memory-hungry MoE models. The right choice depends on your workload.

2. **MI300X's 192GB HBM is a genuine differentiator** for trillion-parameter MoE models with long context. This advantage grows as models get larger and context windows expand.

3. **H200's software ecosystem advantage is real but narrowing.** TRT-LLM and FlashAttention 3 are H200-exclusive. But PyTorch, Triton, vLLM, and SGLang all work on both platforms.

4. **For MoE models at scale** (DeepSeek-R1, trillion-parameter models), MI300X offers **competitive performance at lower cost per token** — the most important metric for production inference.

5. **The future favors MI300X's memory-first approach**: as models trend toward larger MoE architectures with longer contexts, memory capacity becomes increasingly critical.

---

## Sources

| # | Source | URL | Type |
|:---:|:---|:---|:---|
| 1 | Azure AI Benchmarking Guide | https://github.com/Azure/AI-benchmarking-guide | Microsoft official |
| 2 | dstack DeepSeek-R1 Benchmark | https://dstack.ai/blog/h200-mi300x-deepskeek-benchmark/ | Independent third-party |
| 3 | AMD ROCm Blog — DeepSeek-R1 on MI300X | https://rocm.blogs.amd.com/artificial-intelligence/DeepSeekR1_Perf/README.html | AMD official |
| 4 | AMD Instinct MI300X Value Proposition | AMD GBB Training Materials, Oct 2024 | AMD published |
| 5 | SGLang H200 Benchmarking | https://github.com/sgl-project/sglang/issues/2450 | Community |
| 6 | Verda/DataCrunch DeepSeek-R1 on H200 | https://verda.com/blog/deploy-deepseek-r1-on-8x-nvidia-h200 | Cloud provider |

---

*Running on Azure. Author: Xinyu Wei (魏新宇), Microsoft AI GBB.*
