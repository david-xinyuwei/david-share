# MI300X vs H200: LLM Inference Benchmark for Dense and MoE Models

> **Author**: Xinyu Wei (魏新宇)  
> **Date**: 2026-04-27  
> **Purpose**: An objective, data-driven comparison of AMD Instinct MI300X and NVIDIA H200 for LLM inference, with focus on large MoE models and long-context workloads.

[中文版](README-CN.md)

---

## TL;DR

- **Dense models (Llama 8B–405B)**: H200 outperforms MI300X by **+24% to +39%** in throughput (Azure vLLM FP8 benchmark). The gap comes primarily from software maturity (CUDA ecosystem) and collective communication efficiency (NCCL), not from hardware limitations.
- **Large MoE models (DeepSeek-R1 671B)**: MI300X achieves **+10% higher online throughput** than H200 in a third-party benchmark (dstack, vLLM vs TRT-LLM). MI300X's 192GB HBM3 provides critical headroom for 671B-class models.
- **Hardware vs software gap**: MI300X leads on HBM capacity (+36%), HBM bandwidth (+10%), and theoretical FLOPS (+32%). The performance gap on dense models is largely attributable to software optimization differences (ROCm vs CUDA), which are narrowing over time.
- **Workload determines the right choice**: memory-bound workloads (large MoE, long context) favor MI300X; compute-bound workloads (dense models, short context) favor H200.

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

H200 outperforms MI300X on dense models by **+24% to +39%** across all configurations tested, despite MI300X having higher theoretical specs. The gap has both hardware and software components:

**Hardware factors** (inherent to the platform):
1. **Collective communication**: NCCL AllReduce at 8GB reaches **481 GB/s** on H200 vs RCCL's 317 GB/s on MI300X — a **52% gap**. With TP=8, every forward pass requires AllReduce across 8 GPUs, making this a significant throughput bottleneck for MI300X.
2. **FP8 GEMM realized efficiency**: CuBLAS FP8 GEMM (4096×4096) delivers 1,249 TFLOPS on H200 vs hipBLAS's 1,085 TFLOPS on MI300X. MI300X has higher peak FP8 TFLOPS (2,610 vs 1,979), but achieves lower utilization — 47.8% vs 63.1% of theoretical peak at this size.

**Software factors** (subject to improvement over time):
3. **Kernel optimization maturity**: CUDA + cuBLAS + FlashAttention have years of optimization for NVIDIA hardware. ROCm + hipBLAS + Composable Kernel are improving rapidly — AMD demonstrated a **4× improvement** in DeepSeek-R1 throughput within just two weeks of optimization on SGLang (Source: AMD ROCm Blog).
4. **Software version gap in Azure data**: The MI300X results were last updated ~1 year ago (ROCm 6.8.5), while H200 results were updated ~5 months ago. This version gap likely accounts for a portion of the measured difference.

> **Important context**: The performance gap on dense models is a combination of hardware architecture differences and software maturity differences. The software component is narrowing as ROCm matures. Teams evaluating MI300X should benchmark with the latest ROCm and vLLM/SGLang versions, as results may differ significantly from older published data.

**Notable exception**: MI300X outperforms H100 (not H200) on 405B with long output (128/2048: +14%), because the 405B model at FP8 approaches H100's 80GB capacity limit while MI300X's 192GB provides ample headroom.

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

### Why Dense Models and MoE Models Have Different Bottlenecks

The reason MI300X loses on dense models but competes on MoE models comes down to **which hardware resource is the bottleneck**:

**Dense model inference (e.g., Llama 70B)**:
```
Every token → passes through ALL 70B parameters → AllReduce sync across 8 GPUs
```
- High compute per token → **GEMM efficiency is the bottleneck** → H200's cuBLAS wins (63% utilization vs MI300X's 48%)
- 8-GPU synchronization on every layer → **AllReduce bandwidth is the bottleneck** → H200's NCCL wins (481 vs 317 GB/s)
- Model fits comfortably in memory (70B FP8 = 35GB per card) → **memory capacity is NOT a factor**

**MoE model inference (e.g., DeepSeek-R1 671B, 256 experts)**:
```
Every token → Router selects 8 out of 256 experts → only ~37B parameters activated per token
```
- Actual compute per token is only ~37B (not 671B) → **GEMM efficiency matters less**
- But all 256 experts' weights must **reside in GPU memory** (~640GB FP8) → **memory capacity is the binding constraint**
- Each layer loads different expert weights per token → **random-access HBM bandwidth is the bottleneck**
- Communication pattern is All-to-All (route tokens to experts), not AllReduce → **NVLink advantage is diminished**

| Bottleneck | Dense Model Needs | MoE Model Needs | MI300X | H200 | MoE Winner |
|:---|:---|:---|:---:|:---:|:---|
| **Memory capacity** | Low (70B=35GB/card) | **Critical** (671B=640GB total) | **1,536GB** | 1,128GB | **MI300X** |
| **HBM bandwidth** | Important (decode) | **Most important** (expert loading) | **5.3 TB/s** | 4.8 TB/s | **MI300X** |
| **GEMM compute** | **Most important** (all params) | Less important (only 37B active) | Weaker | Stronger | Gap shrinks |
| **Multi-GPU comm** | AllReduce (TP sync) | All-to-All (token routing) | Weaker | Stronger | Gap shrinks |

This is why MI300X loses by 24-39% on dense models but competes on MoE: **MoE shifts the bottleneck from compute and communication (where H200 leads) to memory capacity and bandwidth (where MI300X leads).**

### Why MI300X Is Competitive on MoE

DeepSeek-R1 671B has characteristics that align with MI300X's hardware strengths:

1. **Memory capacity as the binding constraint**: 671B parameters in FP8 require ~640GB for weights alone. 8×MI300X provides 1,536GB total vs 8×H200's 1,128GB. The additional 408GB enables larger batch sizes and more KV cache entries before memory pressure forces eviction or reduces concurrency.
2. **Expert weight access pattern**: MoE models activate different expert subsets per token per layer, creating a memory-bandwidth-intensive access pattern. MI300X's 5.3 TB/s HBM bandwidth provides a 10% advantage over H200's 4.8 TB/s for these random-access weight loads.
3. **Long output generation**: Reasoning models produce extended chain-of-thought sequences (often 2,000+ tokens). The decode phase is memory-bandwidth-bound, where MI300X's HBM advantage directly translates to lower per-token latency.
4. **Reduced collective communication dependency**: MoE expert routing uses All-to-All communication patterns rather than AllReduce. The 52% NCCL vs RCCL gap measured on AllReduce has a smaller impact on MoE workloads.

> **Caveat**: The dstack benchmark compared MI300X (vLLM) against H200 (TRT-LLM). TRT-LLM is not available on MI300X. If both platforms used the same engine, the comparison would be more controlled. The +10% throughput advantage should be interpreted with this asymmetry in mind.

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
- MI300X shows a **1.5-1.6× TPOT advantage** (decode phase), consistent with its HBM bandwidth lead
- MI300X shows a **0.76-0.81× TTFT disadvantage** (prefill phase), consistent with lower realized GEMM throughput
- **E2E latency favors MI300X** in AMD's tests, because these configurations use input/output ratios where decode time dominates total latency. For workloads with very long inputs and short outputs (e.g., summarization), the TTFT disadvantage would weigh more heavily.

> **⚠️ Fairness note**: These are AMD-published numbers using vLLM for MI300X vs TRT-LLM for H100. TRT-LLM is typically faster than vLLM on NVIDIA hardware, so H100's comparison baseline is actually *stronger* than if both used vLLM. However, the comparison is still asymmetric — MI300X does not have a TRT-LLM equivalent. Readers should treat these as directional indicators rather than exact ratios.

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

1. **Performance is workload-dependent, not GPU-dependent.** H200 outperforms MI300X on dense models (+24-39%); MI300X is competitive on large MoE models (+10% on DeepSeek-R1 671B online serving). The right choice requires profiling your specific model, input/output distribution, and concurrency requirements.

2. **MI300X's 192GB HBM addresses a real constraint** for 600B+ parameter MoE models with long context. When total weights + KV cache approach the memory limit, the additional 36% capacity directly enables higher concurrency and larger batches.

3. **The measured performance gap on dense models has both hardware and software components.** Hardware factors (NCCL bandwidth, GEMM utilization) are inherent; software factors (ROCm optimization maturity) are improving. Teams should benchmark with the latest software stack rather than relying on published numbers that may be 6-12 months old.

4. **Cost-performance analysis is model-specific.** On DeepSeek-R1 671B, MI300X shows 46% better tok/s/\$ at Azure list prices. On Llama 70B, H200 would show better cost-performance despite higher per-GPU cost. There is no universal cost-performance winner.

5. **Both platforms carry risks.** MI300X risks: ROCm ecosystem gaps (no TRT-LLM, prefix caching WiP, smaller community). H200 risks: memory capacity ceiling for next-generation trillion-parameter models, higher unit cost. A thorough POC on the target workload is the only reliable way to make the decision.

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

## Related Repos (Our Hands-on Tests on MI300X)

| Repo | Description |
|:---|:---|
| [Azure-AMD-MI300X-Guide](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Azure-AMD-MI300X-Guide) | Deployment, benchmarking, and fine-tuning guide for Azure ND MI300X v5. Covers DeepSeek-R1 671B (SGLang), Qwen3-235B-A22B (vLLM), Qwen 2.5 72B, Qwen 2.5 VL 7B, Llama 4, with real benchmark data on MI300X. |
| [AMD-GPU-SFT-Inference](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/AMD-GPU-SFT-Inference) | SFT training and inference on AMD Instinct GPUs. (Merged into unified project) |

---

*Running on Azure. Author: Xinyu Wei (魏新宇), Microsoft AI GBB.*



## Reproducing the Results

### Prerequisites

- Python 3.10+
- CUDA-compatible GPU (recommended)

### Setup

```bash
git clone <this-repo-url>
cd <repo-name>
```
