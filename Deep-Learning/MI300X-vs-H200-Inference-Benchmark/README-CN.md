# MI300X vs H200：LLM 推理性能对比 — MI300X 什么时候赢？

> **作者**：魏新宇 (Xinyu Wei)  
> **日期**：2026-04-27  
> **定位**：基于公开数据的客观对比，聚焦大规模 MoE 模型和长上下文推理场景。

[English Version](README.md)

---

## 一句话结论

- **Dense 模型（Llama 8B-405B）**：H200 全面领先，吞吐量高 **31%-64%**。
- **大规模 MoE 模型（DeepSeek-R1 671B）**：MI300X 在线推理吞吐量反超 H200 **+10%**，得益于 **192GB HBM3** 显存优势。
- **MI300X 的最佳战场**：万亿参数 MoE 模型 + 长上下文推理，显存容量是决定性约束。
- **H200 的核心优势**：CUDA 生态成熟度、TensorRT-LLM 优化、NVLink 带宽、FP8 GEMM 效率。
- **结论**：GPU 选型应该由工作负载驱动，而非品牌驱动。本 Repo 提供数据支撑决策。

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

尽管 MI300X 理论规格全面领先，**H200 在 dense 模型上仍以 +24% 到 +39% 的优势碾压**。原因：

1. **NCCL vs RCCL**：8GB AllReduce 带宽 H200 **481 GB/s** vs MI300X 317 GB/s — **差距 52%**，TP=8 下多卡通信被放大。
2. **FP8 GEMM 实际效率**：CuBLAS FP8 GEMM (4096×4096) H200 达 1,249 TFLOPS vs MI300X 1,085 TFLOPS — 理论 FLOPS 高不等于实际 GEMM 快。
3. **软件成熟度**：CUDA + cuBLAS + FlashAttention 多年积累的优化深度远超 ROCm。

**例外**：MI300X 在 405B 长输出（128/2048）场景下**反超 H100 14%** — 因为 405B FP8 接近 H100 80GB 显存上限，而 MI300X 192GB 游刃有余。

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

DeepSeek-R1 671B 是 MI300X 最有利的战场：

1. **显存容量是瓶颈**：671B FP8 ≈ 640GB 权重。8×MI300X = 1,536GB vs 8×H200 = 1,128GB，多出 400GB 可用于更大 batch 和更多 KV cache。
2. **256 个 expert 权重**：MoE 每层每 token 加载不同 expert 权重。更多 HBM = 更少权重换入换出。
3. **长链式推理**：Reasoning 模型生成数千 thinking tokens。更高 HBM 带宽 = 更快 decode。
4. **NVLink 优势减弱**：MoE expert routing 不像 dense TP 那么依赖 AllReduce，MI300X 的 xGMI 差距影响更小。

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

> ⚠️ 公平性说明：AMD 用 vLLM（MI300X）vs TRT-LLM（H100），TRT-LLM 通常比 vLLM 在 NVIDIA 硬件上更快。如果 H100 也用 vLLM，MI300X 优势可能更大。

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

1. **没有一款 GPU 通吃所有场景。** H200 碾压 dense 模型；MI300X 在显存密集型 MoE 模型上有优势。
2. **MI300X 的 192GB HBM 是万亿参数 MoE 长上下文推理的真正差异化优势**。
3. **H200 的软件生态优势真实存在但在缩小。** TRT-LLM 和 FA3 是 H200 独占。但 PyTorch/Triton/vLLM/SGLang 两边都能跑。
4. **对于大规模 MoE 推理**，MI300X 提供**有竞争力的性能和更低的单 token 成本** — 生产推理最重要的指标。
5. **未来趋势有利于 MI300X 的 memory-first 路线**：模型越来越大、MoE 架构越来越主流、上下文窗口越来越长 — 显存容量的重要性持续上升。

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
