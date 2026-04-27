# MI300X vs H200：Dense 模型与 MoE 模型推理性能对比

> **作者**：魏新宇 (Xinyu Wei)  
> **日期**：2026-04-27  
> **定位**：基于公开数据的客观对比，聚焦大规模 MoE 模型和长上下文推理场景。

[English Version](README.md)

---

## 一句话结论

- **Dense 模型（Llama 8B-405B）**：H200 吐量领先 MI300X **+24% 到 +39%**（Azure vLLM FP8 测试）。差距主要来自软件成熟度（CUDA 生态）和集合通信效率（NCCL），而非硬件局限。
- **大规模 MoE 模型（DeepSeek-R1 671B）**：MI300X 在线推理吞吐量 **高出 H200 10%**（dstack 第三方测试，vLLM vs TRT-LLM）。MI300X 的 192GB HBM3 为 671B 级别模型提供了关键的显存余量。
- **硬件 vs 软件差距**：MI300X 在 HBM 容量（+36%）、HBM 带宽（+10%）、理论 FLOPS（+32%）上均领先。Dense 模型上的性能差距主要归因于软件优化差异（ROCm vs CUDA），该差距正在缩小。
- **工作负载决定正确选择**：显存密集型工作负载（大 MoE、长上下文）适合 MI300X；计算密集型工作负载（Dense 模型、短上下文）适合 H200。

---

## 硬件规格

| 规格 | AMD MI300X | NVIDIA H200 SXM | NVIDIA H100 SXM | MI300X 优势 |
|:---|:---:|:---:|:---:|:---|
| **HBM 容量** | **192 GB** | 141 GB | 80 GB | **比 H200 多 36%，比 H100 多 140%** |
| **HBM 带宽** | **5.3 TB/s** | 4.8 TB/s | 3.35 TB/s | 比 H200 多 10%，比 H100 多 58% |
| **FP16/BF16 TFLOPS** | 1,307 | 989 | 989 | 理论值高 32% |
| **FP8 TFLOPS** | 2,610 | 1,979 | 1,979 | 理论值高 32% |
| **互联带宽** | xGMI 896 GB/s | NVLink 900 GB/s | NVLink 900 GB/s | 基本持平 |
| **TDP（单卡）** | 750W | 700W | 700W | 功耗多 7% |
| **单节点总显存（8 卡）** | **1,536 GB** | 1,128 GB | 640 GB | **比 H200 多 36%** |

**关键洞察**：MI300X 纸面规格**全面领先** — 更多显存、更高带宽、更高理论 TFLOPS。但实际性能取决于软件优化、kernel 效率和工作负载特性。

---

## Benchmark 1：Dense 模型（Llama）— H200 赢

*来源：[Azure AI Benchmarking Guide](https://github.com/Azure/AI-benchmarking-guide)（微软官方）*

### Llama 3.1 8B（TP=1，FP8，vLLM，1000 requests）

| ISL/OSL | MI300X | H100 | H200 | MI300X vs H200 | MI300X vs H100 |
|:---|:---:|:---:|:---:|:---|:---|
| 128/128 | 18,149 | 15,163 | **25,302** | -28% | +20% |
| 128/2048 | 16,394 | 15,014 | **25,366** | -35% | +9% |
| 1024/1024 | 10,995 | **11,724** | **16,828** | -35% | -6% |
| 2048/2048 | 7,356 | 8,026 | **11,642** | -37% | -8% |

### Llama 3 70B（TP=8）

| ISL/OSL | MI300X | H100 | H200 | MI300X vs H200 | MI300X vs H100 |
|:---|:---:|:---:|:---:|:---|:---|
| 128/128 | 9,026 | 10,032 | **12,306** | -27% | -10% |
| 128/2048 | 12,204 | 12,910 | **18,573** | -34% | -5% |
| 1024/1024 | 8,256 | 9,125 | **11,389** | -28% | -10% |
| 2048/2048 | 7,421 | 7,908 | **10,495** | -29% | -6% |

### Llama 3 405B（TP=8）

| ISL/OSL | MI300X | H100 | H200 | MI300X vs H200 | MI300X vs H100 |
|:---|:---:|:---:|:---:|:---|:---|
| 128/128 | 2,484 | 2,515 | **3,262** | -24% | -1% |
| 128/2048 | 3,902 | 3,434 | **5,179** | -25% | +14% |
| 1024/1024 | 2,363 | 2,422 | **3,121** | -24% | -2% |
| 2048/2048 | 1,840 | 1,973 | **3,014** | -39% | -7% |

### 分析

尽管 MI300X 理论规格全面领先，**H200 在 dense 模型上仍以 +24% 到 +39% 的优势领先**。该差距同时包含硬件和软件因素：

**硬件因素**（平台固有）：
1. **集合通信**：8GB AllReduce 带宽 H200 **481 GB/s** vs MI300X 317 GB/s — **差距 52%**。TP=8 时每次前向传播都需要 AllReduce，这是 MI300X 的显著吞吐量瓶颈。
2. **FP8 GEMM 实际效率**：CuBLAS FP8 GEMM (4096×4096) H200 达 1,249 TFLOPS vs hipBLAS MI300X 1,085 TFLOPS。MI300X 理论 FP8 更高（2,610 vs 1,979 TFLOPS），但利用率更低 — 47.8% vs 63.1%。

**软件因素**（可随时间改善）：
3. **Kernel 优化成熟度**：CUDA + cuBLAS + FlashAttention 对 NVIDIA 硬件有多年优化积累。ROCm + hipBLAS + Composable Kernel 正在快速进步 — AMD 在 SGLang 上仅用两周就实现了 DeepSeek-R1 **4× 性能提升**（来源：AMD ROCm Blog）。
4. **Azure 数据的软件版本差异**：MI300X 结果更新于约 1 年前（ROCm 6.8.5），H200 结果更新于约 5 个月前。这个版本差距可能占实测差异的一部分。

> **重要背景**：Dense 模型上的性能差距是硬件架构差异和软件成熟度差异的综合结果。软件部分正在随 ROCm 成熟而缩小。评估 MI300X 的团队应使用最新的 ROCm 和 vLLM/SGLang 版本进行实测，因为结果可能与较早发布的数据有显著差异。

**例外**：MI300X 在 405B 长输出场景（128/2048）下超越 H100（非 H200）**14%** — 因为 405B FP8 接近 H100 80GB 显存上限，而 MI300X 192GB 游刃有余。

---

## Benchmark 2：MoE 模型（DeepSeek-R1 671B）— MI300X 有竞争力

*来源：[dstack benchmark](https://dstack.ai/blog/h200-mi300x-deepskeek-benchmark/)（独立第三方）*

### 配置
- **模型**：DeepSeek-R1 671B FP8（MoE，256 experts）
- **引擎**：SGLang / vLLM / TensorRT-LLM
- **输入**：3,200 tokens，输出：800 tokens
- **硬件**：8×MI300X (Vultr) vs 8×H200 (Lambda)

### 峰值吞吐量

| 场景 | MI300X 最佳 | H200 最佳 | 赢家 |
|:---|:---|:---|:---|
| **在线推理（serving）** | **4,574 tok/s** (vLLM) | 4,176 tok/s (TRT-LLM) | **MI300X +10%** |
| **离线推理（max throughput）** | — | **6,311 tok/s** (SGLang) | **H200** |

### 延迟分析

| 指标 | MI300X | H200 | 赢家 | 原因 |
|:---|:---|:---|:---|:---|
| **TTFT（低并发）** | 较高 | **较低** | H200 | Prefill 是计算密集型，H200 GEMM 更强 |
| **TTFT（128 并发）** | **较低** | 较高 | MI300X | 192GB 显存扛住 KV cache 压力 |
| **TPOT** | 理论更优 | 实际差距不大 | 持平 | ROCm 优化差距抵消 HBM 优势 |
| **TTFT vs 输出长度** | **稳定** | vLLM/TRT-LLM 飙升 | MI300X | 显存更大，KV cache 不溢出 |

### MI300X 在 MoE 上有竞争力的原因

DeepSeek-R1 671B 的工作负载特征与 MI300X 的硬件优势高度匹配：

1. **显存容量是约束条件**：671B FP8 仅权重就需 ~640GB。8×MI300X 提供 1,536GB vs 8×H200 1,128GB，多出的 408GB 可用于更大 batch 和更多 KV cache 条目。
2. **Expert 权重访问模式**：MoE 每层每 token 激活不同的 expert 子集，产生显存带宽密集型的随机访问。MI300X 5.3 TB/s HBM 带宽比 H200 4.8 TB/s 高 10%。
3. **长输出生成**：Reasoning 模型生成较长的链式推理序列（常超 2000 tokens）。Decode 阶段受显存带宽约束，MI300X 的 HBM 优势直接降低每 token 延迟。
4. **集合通信依赖减少**：MoE expert routing 使用 All-to-All 通信模式而非 AllReduce。AllReduce 上测量的 NCCL vs RCCL 52% 差距对 MoE 工作负载影响较小。

> **注意**：dstack benchmark 对比的是 MI300X（vLLM）vs H200（TRT-LLM）。TRT-LLM 在 MI300X 上不可用。如果两个平台使用相同引擎，对比会更可控。+10% 的吞吐量优势应在考虑这个不对称性的前提下理解。

---

## Benchmark 3：微观性能对比

*来源：[Azure AI Benchmarking Guide](https://github.com/Azure/AI-benchmarking-guide)*

| 指标 | MI300X | H100 | H200 | 分析 |
|:---|:---:|:---:|:---:|:---|
| **HBM 拷贝** | **4.15 TB/s** | 2.90 TB/s | 4.01 TB/s | MI300X 领先 — 解释 decode 优势 |
| **FP8 GEMM 4K** | 1,085 TF | 1,217 TF | **1,249 TF** | H200 领先 — 解释 prefill 优势 |
| **Flash Attn 2.0** | 328.6 TF | 327.9 TF | 329.3 TF | 三者持平 |
| **AllReduce 8GB** | 316.8 GB/s | 478.9 GB/s | **480.9 GB/s** | H200/H100 NVLink **领先 52%** |

**GPU 推理的物理本质**：
- **Prefill**（TTFT）= 计算密集型 → GEMM 效率决定 → **H200 赢**
- **Decode**（TPOT）= 显存带宽密集型 → HBM 带宽决定 → **MI300X 赢**
- **多卡通信** → AllReduce 带宽决定 → **H200 赢**
- **显存容量** → KV cache 上限决定 → **MI300X 赢**

---

## AMD 官方数据：MI300X vs H100

*来源：AMD Instinct MI300X GBB Training Materials (2024-10)*

AMD 内部测试（MI300X 用 vLLM，H100 用 TRT-LLM）Llama 3.1 结果：

| 模型 | 指标 | MI300X vs H100 |
|:---|:---|:---|
| **Llama 3.1 70B** | E2E 延迟 | **快 1.44×** |
| | TPOT（decode） | **快 1.52×** |
| | TTFT（prefill） | 慢 0.81× |
| **Llama 3.1 405B** | E2E 延迟 | **快 1.45×** |
| | TPOT（decode） | **快 1.62×** |
| | TTFT（prefill） | 慢 0.76× |

**其他模型**：Mixtral（MoE）MI300X **1.41×**、Mistral 7B **1.27×**、SDXL（diffusion）**持平**。

**关键观察**：
- MI300X **TPOT 优势 1.5-1.6×**（decode 阶段），与其 HBM 带宽领先一致
- MI300X **TTFT 劣势 0.76-0.81×**（prefill 阶段），与其较低的实际 GEMM 吞吐量一致
- **E2E 延迟在 AMD 测试中对 MI300X 有利**，因为这些配置的输入/输出比例中 decode 时间占总延迟的主要部分。对于输入很长但输出很短的工作负载（如摘要），TTFT 劣势会占更大比重。

> ⚠️ **公平性说明**：这些是 AMD 发布的数据，使用 vLLM（MI300X）vs TRT-LLM（H100）。TRT-LLM 在 NVIDIA 硬件上通常比 vLLM 更快，所以 H100 的对比基线实际上是*更强的*。但对比仍然是不对称的 — MI300X 没有 TRT-LLM 等价物。读者应将这些数据视为方向性指标而非精确比例。

---

## 生产环境验证

| 组织 | 硬件 | 工作负载 | 关键引用 |
|:---|:---|:---|:---|
| **Meta** | MI300X | Llama 405B 线上流量 | "所有 Meta Llama 405B 线上流量均由 MI300X 独占服务，因其大显存和 TCO 优势" |
| **Databricks** | MI300X | 模型训练 & 推理 | "ROCm 能力大幅提升...很多模型无需修改即可在 AMD 硬件上运行" |
| **Microsoft** | MI300X | M365 Copilot | "这些 VM 是运行 GPT-4 Turbo 和 M365 Copilot 关键场景的 AI 基础设施" |

---

## 选型决策框架

| 工作负载特征 | 选 MI300X | 选 H200 |
|:---|:---:|:---:|
| **Dense 模型 ≤ 70B** | | ✅ |
| **Dense 模型 405B** | 持平 | ✅ |
| **MoE 模型 200B+** | ✅ | 持平 |
| **MoE 模型 600B+（如 DeepSeek-R1）** | ✅ | |
| **万亿参数 MoE** | ✅✅ | |
| **长上下文（32K+ tokens）** | ✅ | |
| **短上下文高吞吐** | | ✅ |
| **离线批量推理** | | ✅ |
| **多节点训练** | | ✅ |
| **Prefix Caching** | ⚠️（ROCm 开发中） | ✅ |
| **预算敏感** | ✅（通常更低 $/GPU） | |

### 显存容量法则

```
MI300X: 8 × 192GB = 1,536 GB
H200:   8 × 141GB = 1,128 GB
H100:   8 × 80GB  =   640 GB
```

万亿参数 MoE 模型 FP8 仅权重就需要约 1TB。加上高并发长上下文的 KV cache，**H200 的 1,128GB 可能成为瓶颈，而 MI300X 的 1,536GB 仍有余量**。

---

## 性价比参考（Azure）

| VM | GPU | 参考价 | 每 GPU 每小时 |
|:---|:---:|:---:|:---:|
| **ND MI300X v5** | 8× MI300X | ~$27/hr | ~$3.38 |
| **ND H200 v5** | 8× H200 | ~$36/hr | ~$4.50 |

**DeepSeek-R1 671B 在线推理性价比**：
- MI300X：4,574 tok/s ÷ $27/hr = **169 tok/s/$**
- H200：4,176 tok/s ÷ $36/hr = **116 tok/s/$**
- **MI300X 性价比高 46%**（该 MoE 工作负载下）

---

## 软件生态对比

| 维度 | MI300X (ROCm) | H200 (CUDA) | 差距 |
|:---|:---|:---|:---|
| **PyTorch** | 完全上游合并 | 原生支持 | 持平 |
| **Triton kernels** | ROCm backend | CUDA backend | 持平 |
| **vLLM** | 支持 | 支持 | H200 快约 30%（kernel 优化） |
| **SGLang** | 支持 | 支持 | 基本持平 |
| **TensorRT-LLM** | ❌ 不可用 | ✅ 最强性能 | H200 独占 |
| **FlashAttention** | FA 2.0 (CK) | FA 2/3 原生 | H200 领先（FA3） |
| **NCCL/RCCL** | RCCL | NCCL | NCCL 更成熟，AllReduce +52% |
| **Prefix Caching** | ⚠️ 开发中 | ✅ 完整支持 | H200 领先 |
| **FP8 量化** | Block-wise FP8 | Block-wise FP8 | 持平 |
| **自定义 CUDA kernel** | 需 HIPIFY 移植 | 原生 | H200 更方便 |
| **模型覆盖** | 70 万+ 模型可运行 | 所有模型 | MI300X 在追赶 |

**总结**：CUDA 生态在优化深度上**显著领先**，但 ROCm 已大幅缩小差距 — PyTorch 和 Triton 工作负载无需改代码即可运行。剩余差距主要在**专有优化**（TRT-LLM、FA3、NCCL 调优）。

---

## 结论

1. **性能取决于工作负载，而非 GPU 本身。** H200 在 dense 模型上领先（+24-39%）；MI300X 在大 MoE 模型上有竞争力（DeepSeek-R1 671B 在线推理 +10%）。正确选择需要针对具体模型、输入/输出分布和并发需求进行实测。

2. **MI300X 的 192GB HBM 解决的是真实的显存约束问题。** 当 600B+ 参数 MoE 模型的权重 + KV cache 接近显存上限时，额外 36% 的容量直接支持更高并发和更大 batch。

3. **Dense 模型上的性能差距同时包含硬件和软件因素。** 硬件因素（NCCL 带宽、GEMM 利用率）是固有的；软件因素（ROCm 优化成熟度）正在改善。团队应使用最新软件栈实测，而非依赖 6-12 个月前的发布数据。

4. **性价比分析是模型特定的。** DeepSeek-R1 671B 上 MI300X 性价比高 46%；Llama 70B 上 H200 性价比会更高。没有普遍的性价比赢家。

5. **两个平台都有风险。** MI300X 风险：ROCm 生态差距（无 TRT-LLM、prefix caching 开发中、社区较小）。H200 风险：显存容量上限可能不够下一代万亿参数模型、单卡成本更高。**基于目标工作负载的充分 POC 是做出可靠决策的唯一方式。**

---

## 数据来源

| # | 来源 | URL | 类型 |
|:---:|:---|:---|:---|
| 1 | Azure AI Benchmarking Guide | https://github.com/Azure/AI-benchmarking-guide | 微软官方 |
| 2 | dstack DeepSeek-R1 Benchmark | https://dstack.ai/blog/h200-mi300x-deepskeek-benchmark/ | 独立第三方 |
| 3 | AMD ROCm Blog — DeepSeek-R1 | https://rocm.blogs.amd.com/artificial-intelligence/DeepSeekR1_Perf/README.html | AMD 官方 |
| 4 | AMD Instinct MI300X 价值主张 | AMD GBB Training Materials, 2024-10 | AMD 公开 |
| 5 | SGLang H200 Benchmarking | https://github.com/sgl-project/sglang/issues/2450 | 社区 |
| 6 | Verda/DataCrunch DeepSeek-R1 | https://verda.com/blog/deploy-deepseek-r1-on-8x-nvidia-h200 | 云供应商 |

---

*Running on Azure. 作者：魏新宇 (Xinyu Wei)，Microsoft AI GBB.*
