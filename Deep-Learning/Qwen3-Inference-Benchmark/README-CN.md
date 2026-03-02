# Qwen3 Inference Benchmark（推理基准测试）(Azure H100)

> **作者**: 魏新宇 (Xinyu Wei)  
> **日期**: 2026-02-06 (32B), 2026-02-11 (235B SGLang)  
> **模型**: Qwen3-32B-FP8 (Dense) | Qwen3-235B-A22B-FP8 (MoE)  
> **硬件**: Azure NC40ads H100 v5 (1×H100 NVL) | NC80adis H100 v5 (每节点 2×H100 NVL)

---

## 目录

- [Qwen3 模型家族概览](#qwen3-模型家族概览)
- [Part 1: 单卡 Dense 模型 (32B) — 注意力后端基准测试](#part-1-单卡-dense-模型-32b--注意力后端基准测试)
- [Part 2: 多节点 MoE 模型 (235B) — 推理引擎基准测试](#part-2-多节点-moe-模型-235b--推理引擎基准测试)
- [硬件规格](#硬件规格)
- [决策矩阵](#决策矩阵)
- [参考资料](#参考资料)

---

## Qwen3 模型家族概览

Qwen3 是阿里巴巴第三代开源大语言模型家族，同时覆盖 Dense（稠密）和 MoE（混合专家）两种架构。本节提供截至 2026 年 2 月的 Qwen3 及 Qwen3.5 全部模型清单。

### Qwen3（2025-04 发布，2025-07 更新）

Qwen3 初版涵盖 8 个模型规格，从边缘设备到数据中心级 MoE：

| 模型 | 架构 | 总参数量 | 激活参数量 | 层数 | 专家数 | 上下文 |
|------|:----:|:--------:|:----------:|:----:|:------:|:------:|
| Qwen3-0.6B | Dense | 0.6B | 0.6B | 28 | — | 32K |
| Qwen3-1.7B | Dense | 1.7B | 1.7B | 28 | — | 32K |
| Qwen3-4B | Dense | 4B | 4B | 36 | — | 32K |
| Qwen3-8B | Dense | 8B | 8B | 36 | — | 128K |
| Qwen3-14B | Dense | 14B | 14B | 40 | — | 128K |
| **Qwen3-32B** | **Dense** | **32B** | **32B** | **64** | **—** | **128K** |
| Qwen3-30B-A3B | MoE | 30B | 3B | 48 | 128/8 | 128K |
| **Qwen3-235B-A22B** | **MoE** | **235B** | **22B** | **94** | **128/8** | **128K** |

**粗体** = 本基准测试中已测试的模型。

**每个模型的可用变体**：
- **Base** / **Instruct** — 预训练版 vs 指令微调版
- **2507** — 2025 年 7 月更新版，改进推理和指令遵循能力
- **FP8** — W8A8 量化，高效部署
- **GGUF** / **AWQ** / **GPTQ** — 社区量化格式

### Qwen3.5（2026-02-16 发布）

Qwen3.5 引入重大架构升级 — 最显著的是 **75% Gated Deltanet 线性注意力**（在 75% 的层中替换标准 Softmax 注意力），将这些层的 KV Cache 内存从 O(n) 降至 O(1)。

| 模型 | 架构 | 总参数量 | 激活参数量 | 专家数 | 相比 Qwen3 的关键变化 |
|------|:----:|:--------:|:----------:|:------:|:---------------------|
| Qwen3.5-27B | Dense | 27B | 27B | — | 75% 线性注意力，32B 的继任者 |
| Qwen3.5-35B-A3B | MoE | 35B | 3B | 256/8 | 256 专家（原 128），线性注意力 |
| Qwen3.5-122B-A10B | MoE | 122B | 10B | 256/8 | 新增中杯规格，256 专家 |
| Qwen3.5-397B-A17B | MoE | 397B | 17B | 256/8 | 旗舰，235B 的继任者 |

**架构亮点**：
- **Gated Deltanet**：一种使用 Delta Rule 进行记忆更新的线性注意力变体（替代 Softmax）。75% 的层采用此机制，KV Cache 减少约 75%，质量损失极小。
- **256 专家**：相比 Qwen3 的 128 专家翻倍，每个 token 仍激活 8 个。
- **原生多模态**：Qwen3.5 原生支持文本、图像、视频和音频（本基准测试未涉及）。

### 代际对比

| Qwen3 | → | Qwen3.5 | 变化 |
|-------|---|---------|------|
| 32B Dense | → | 27B Dense | 缩小 16%，线性注意力，质量相当 |
| 235B-A22B MoE | → | 397B-A17B MoE | 总参数 1.7 倍，激活量减少 23% |
| 30B-A3B MoE | → | 35B-A3B MoE | 激活预算相同，256 专家 |
| — | → | 122B-A10B MoE | 新增中杯规格 |

### 本基准测试范围

本基准测试在 Azure H100 基础设施上测试 **Qwen3** 模型：

| 部分 | 模型 | GPU 配置 | 测试重点 |
|------|------|---------|---------|
| **Part 1** | Qwen3-32B-FP8 (Dense) | 单卡 H100 NVL 94GB | 注意力后端：FA2 vs FlashInfer |
| **Part 2** | Qwen3-235B-A22B-FP8 (MoE) | 4×H100 NVL（2 节点） | 推理引擎：vLLM V0/V1 vs SGLang |

> Qwen3.5 基准测试已规划，将作为 Part 3 添加。

---

## Part 1: 单卡 Dense 模型 (32B) — 注意力后端基准测试

> **模型**: Qwen3-32B-FP8 (FP8 E4M3, 32GB)  
> **GPU**: Azure NC40ads H100 v5 (单卡 H100 NVL 94GB)  
> **vLLM**: 0.11.2 | **场景**: (1024 输入, 1024 输出), 流式模式

### 核心结论

![架构图](images/01-architecture.png)

**核心发现**: 在 vLLM 0.11.2 + H100 NVL + FP8 模型配置下，**FlashAttention 2 比 FlashInfer 快 7.5%**（高并发场景）。

> **适用范围**: 此结论仅适用于 **vLLM 0.11.2 + FlashInfer 0.5.2 + FP8 (E4M3) + 短上下文 (4K)** 在 H100 上的场景。根本原因是 [FlashInfer FP8 启发式 Bug](https://github.com/vllm-project/vllm/issues/9471)，可能在新版本中已修复。

| 指标 | FlashAttention 2 | FlashInfer | 差异 |
|------|:----------------:|:----------:|:----:|
| **峰值吞吐 (C=512)** | **4,022.6 t/s** | 3,741.4 t/s | **FA2 +7.5%** |
| **TTFT @ C=512** | **1,116 ms** | 1,866 ms | **FA2 -40%** |
| 低并发 (1-128) | ~ | +1~3% | FlashInfer 略快 |
| 高并发 (256-512) | **+5~7%** | ~ | **FA2 显著更快** |

### 不公平对比问题

先前基准测试对比了**不同 vLLM 版本**，导致结论错误：

| 配置 | vLLM 版本 | 后端 | 峰值吞吐 |
|------|:---------:|:----:|:--------:|
| 先前"基线" | 0.11.2 | FA2 | 3,907.8 t/s |
| 先前"优化版" | **0.15.0** | FlashInfer | 4,531.3 t/s |
| 声称提升 | — | — | +16% |

16% 的提升来自 **vLLM 版本升级**，而非注意力后端差异。修正为相同 vLLM 0.11.2 后：

| 配置 | 后端 | 峰值吞吐 |
|------|:----:|:--------:|
| FA2 | FLASH_ATTN | **4,022.6 t/s** |
| FlashInfer | FLASHINFER | 3,741.4 t/s |
| **实际差异** | — | **FA2 +7.5%** |

### FlashInfer 是什么？

**FlashInfer 不仅仅是"注意力后端"** — 它是一个综合性的 **LLM 推理内核库和内核生成器**（论文：[arXiv:2501.01005](https://arxiv.org/abs/2501.01005)，MLSys 2025）：

| 类别 | 内核 |
|------|------|
| **注意力** | Paged, Ragged, MLA, Cascade, Sparse, POD Attention |
| **GEMM** | FP8/FP4 Grouped GEMM |
| **MoE** | Fused MoE (DeepSeek-V3/Llama-4 路由) |
| **采样** | 免排序 top-k/top-p |
| **通信** | AllReduce, MNNVL, NVSHMEM |
| **归一化** | RMSNorm, LayerNorm, RoPE |

FlashInfer 内部实现了 FlashAttention 算法 + PagedAttention 内存管理，以及 JIT 编译自定义内核。**SGLang 在 Ampere/Ada GPU** (sm80/86/89) 上默认使用 FlashInfer，在 Hopper (sm90) 上默认使用 FA3。

### 根因：FlashInfer FP8 Tensor Core 启发式 Bug

参考：[vLLM GitHub Issue #9471](https://github.com/vllm-project/vllm/issues/9471)

FlashInfer 的 `use_tensor_cores` 启发式在 FP8 下失效：

```
FlashInfer Tensor Core 决策逻辑:
if head_dim >= 128:
    use_tensor_cores = True       # 正确
else:
    # 基于 FP16/BF16 性能分析的启发式
    use_tensor_cores = (batch * heads) > threshold

    问题: FP8 有不同的最优阈值!
    结果: 回退到 CUDA Core 而非 Tensor Core
```

| 后端 | 内核类型 | H100 TFLOPS (FP8) | 利用率 |
|------|:--------:|:------------------:|:------:|
| FA2 | 始终 Tensor Core | 3,958 | ~85% |
| FlashInfer (FP8 Bug) | 混合 CUDA+Tensor | 3,958 | ~70% |

效率损失：`(85% - 70%) / 85% = 17.6%` 理论值 → 实测 7.5%（其他优化补偿）。

### 测试环境 (Part 1)

| 组件 | 规格 |
|------|:----:|
| **GPU** | NVIDIA H100 NVL 94GB HBM3（单卡） |
| **VM SKU** | Azure Standard_NC40ads_H100_v5 |
| **vCPU** | 40 核 |
| **RAM** | 320 GB |

| 软件 | 版本 |
|------|:----:|
| **vLLM** | 0.11.2 (Docker: `vllm/vllm-openai:v0.11.2`) |
| **CUDA** | 12.8 |
| **PyTorch** | 2.9.0+cu128 |
| **FlashAttention** | 2.8.3（内置） |
| **FlashInfer** | 0.5.2（内置） |

| 模型参数 | 值 |
|---------|:--:|
| **模型** | Qwen/Qwen3-32B-FP8 |
| **精度** | FP8 (E4M3) |
| **max_model_len** | 4096 |
| **tensor_parallel_size** | 1 |
| **gpu_memory_utilization** | 0.95 |

### 为什么用 Docker 而非 pip install？

```bash
$ pip install vllm==0.11.2
ERROR: Cannot install vllm==0.11.2 because:
  huggingface_hub 0.32.0 requires transformers>=4.45.0
  but vllm 0.11.2 requires transformers==4.51.3
```

Docker 镜像 `vllm/vllm-openai:v0.11.2` 已锁定所有依赖 — 无冲突。

### 基准测试结果 (Part 1)

**测试方法**: 每种配置 3 轮，取**中位数**。等待 30 秒预热。测试之间清理 GPU 显存。

#### FlashAttention 2

| 并发数 | QPS | TTFT (ms) | 吞吐量 (t/s) |
|:------:|:---:|:---------:|:------------:|
| 1 | 0.08 | 26 | 55.7 |
| 4 | 0.27 | 37 | 195.2 |
| 8 | 0.45 | 41 | 344.4 |
| 16 | 0.80 | 46 | 600.7 |
| 32 | 1.51 | 52 | 1,096.6 |
| 64 | 2.70 | 63 | 1,889.7 |
| 128 | 4.21 | 102 | 2,759.9 |
| 256 | 5.45 | 145 | 3,607.2 |
| **512** | **6.22** | **1,116** | **4,022.6** |

#### FlashInfer

| 并发数 | QPS | TTFT (ms) | 吞吐量 (t/s) |
|:------:|:---:|:---------:|:------------:|
| 1 | 0.08 | 31 | 55.4 |
| 4 | 0.27 | 38 | 200.6 |
| 8 | 0.45 | 44 | 354.9 |
| 16 | 0.89 | 53 | 613.2 |
| 32 | 1.58 | 60 | 1,110.2 |
| 64 | 2.72 | 79 | 1,923.6 |
| 128 | 3.84 | 129 | 2,788.7 |
| 256 | 4.88 | 205 | 3,444.6 |
| **512** | **5.35** | **1,866** | **3,741.4** |

#### 并行对比

| 并发数 | FA2 (t/s) | FlashInfer (t/s) | 差异 |
|:------:|:---------:|:----------------:|:----:|
| 1-128 | ~ | ~ | ±3% |
| 256 | 3,607.2 | 3,444.6 | FA2 +4.7% |
| **512** | **4,022.6** | **3,741.4** | **FA2 +7.5%** |

### 局限性与注意事项 (Part 1)

以上建议**适用范围有限**，请勿随意推广：

| 未测试的变量 | 影响 |
|:------------|:-----|
| **CUDAGraph** | FlashInfer 原生支持 CUDAGraph，启用后结果可能不同 |
| **长上下文 (32K+)** | FlashInfer 的 Ragged Tensor + Cascade Attention 可能优于 FA2 |
| **BF16/FP16 模型** | FP8 启发式 Bug 不影响 BF16/FP16 |
| **更新版本** | FlashInfer 0.6.x / vLLM 0.13+ 可能已修复该问题 |
| **SGLang** | SGLang 在 Ampere/Ada 上默认使用 FlashInfer，不同调度可能产生不同结果 |
| **MLA 模型 (DeepSeek)** | FlashInfer 有 FA2 没有的专用 MLA 内核 |

**关键洞察**: FA2 的 7.5% 优势来自 FlashInfer 0.5.2 中的**特定 FP8 内核选择 Bug**，而非架构层面的根本优势。

---

## Part 2: 多节点 MoE 模型 (235B) — Inference Engine Benchmark（推理引擎基准测试）

> **模型**: Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 (235B MoE, 每 token 激活 22B 参数)  
> **硬件**: 2× Azure NC80adis_H100_v5 (4× H100 NVL, 总计 376GB VRAM)  
> **引擎**: vLLM v0.11.2/v0.10.1 → **SGLang v0.5.8.post1**（当前生产）  
> **功能特性**: Function Calling, 推理模式, Chunked Prefill

### 三引擎对比

| 指标 | SGLang v0.5.8 | vLLM V0 (v0.10.1) | vLLM V1 (v0.11.2) |
|------|:-------------:|:------------------:|:------------------:|
| **单请求 TPS** | **70-75 t/s** | 6.8 t/s | 17 t/s |
| **峰值吞吐量** | **1,320 t/s** @ C=128 | 304 t/s @ C=33 | 610 t/s @ C=64 |
| **TTFT（空闲）** | 104-142 ms | 141-146 ms | 81-93 ms |
| **ITL（平均）** | **13.3 ms** | ~158 ms | ~57 ms |
| **PP>1 稳定性** | ✅ 零崩溃 | ✅ 零崩溃 | ❌ 分钟~小时崩溃 |
| **Function Calling** | ✅ 5/5 测试 | ✅ 正常 | ✅ 正常 |
| **最大测试并发** | C=128 稳定 | C=91 稳定 | C=64 (C=128 崩溃) |

> **数据来源**：SGLang — 标准基准测试（2026-02-11）。vLLM V0 — 客户生产环境验证（2026-02-06，v0.10.1）。vLLM V1 — 标准基准测试（2026-02-05，v0.11.2）。

### 多节点架构：TP=2 + PP=2

![Architecture](images/architecture.png)

| 并行方式 | 通信模式 | 带宽 | 位置 |
|:--------:|:--------:|:----:|:----:|
| **张量并行 (TP=2)** | 每层 All-reduce | 600 GB/s NVLink | 节点内 |
| **流水线并行 (PP=2)** | 阶段间点对点 | ~10 Gbps 以太网 | 节点间 |

**为什么 TP=2 + PP=2？**
- TP 每层都需 **all-reduce** → 需要高带宽（节点内 NVLink）
- PP 只需**点对点**激活值传输 → 可容忍低带宽（节点间以太网）
- H100 NVL：节点内 600 GB/s NVLink，节点间 ~10 Gbps 以太网

### 软件栈与通信架构

| 组件 | 角色 | 阶段 |
|------|:-----|:----:|
| **vLLM/SGLang** | 推理引擎 + API 服务器 | 全程 |
| **Ray** | 分布式进程调度器 | 仅启动时 |
| **NCCL** | GPU-to-GPU 通信库 | 推理时 |
| **NVLink** | 物理互连（节点内） | 推理时 |
| **TCP/eth0** | 物理互连（节点间） | 推理时 |

**关键洞察**: NCCL 处理所有 GPU 通信（节点内和节点间），但底层物理介质不同。Ray 只在启动时分配 worker，不传输推理数据。

### 端到端请求流程

![Request Flow](images/request-flow.png)

### SGLang 基准测试（当前生产 - 2026-02-11）

> **测试配置**：输入 1024 tokens → 输出 1024 tokens，stream=True

| 并发数 | 吞吐量 (t/s) | TTFT (ms) | QPS |
|:------:|:------------:|:---------:|:---:|
| 1 | 70.1 | 140 | 0.07 |
| 2 | 129.9 | 264 | 0.13 |
| 4 | 217.4 | 326 | 0.22 |
| 8 | 376.0 | 378 | 0.37 |
| 16 | 653.3 | 505 | 0.65 |
| 32 | 999.5 | 738 | 1.00 |
| 64 | 1,260.2 | 1,115 | 1.26 |
| **128** | **1,320.4** | 2,189 | **1.32** |

#### 稳定性测试（516 请求，零失败）

> **测试配置**：输入 1024 tokens → 输出 512 tokens，stream=True。因输出长度不同，吐吞量与上方性能基准测试有差异。

| 并发数 | 请求数 | 完成数 | 失败数 | 吞吐量 (t/s) |
|:------:|:------:|:------:|:------:|:------------:|
| 1 | 10 | 10 | 0 | 37.2 |
| 4 | 10 | 10 | 0 | 117.6 |
| 8 | 16 | 16 | 0 | 228.5 |
| 16 | 32 | 32 | 0 | 388.6 |
| 32 | 64 | 64 | 0 | 637.2 |
| 64 | 128 | 128 | 0 | 836.7 |
| 128 | 256 | 256 | 0 | 975.4 |
| **合计** | **516** | **516** | **0** | — |

#### Function Calling 测试（5/5 通过）

| 测试用例 | tool_choice | 期望结果 | 实际结果 |
|---------|:-----------:|:--------:|:--------:|
| 天气查询 | auto | 工具调用 | ✅ `get_weather(city="Beijing")` |
| 天气查询 | **required** | 工具调用 | ✅ `get_weather(city="Shanghai")` |
| 数学问题 | auto | 无工具 | ✅ 直接回答 |
| 信息搜索 | specific | 指定工具 | ✅ `search_database(query="AI agents")` |
| 天气（流式） | required | 工具调用（流）| ✅ `get_weather(city="Tokyo")` |

#### ITL 精度测试

> **测试配置**：每个场景使用不同的输入→输出长度（见括号内标注），单请求，stream=True。

| 场景 | TTFT (ms) | ITL 平均 (ms) | ITL P50 (ms) | ITL P99 (ms) | TPS |
|------|:---------:|:-------------:|:------------:|:------------:|:---:|
| 短中文 (128→512) | 110 | 13.2 | 13.2 | 13.5 | 74.8 |
| 中英文 (512→1024) | 141 | 13.3 | 13.3 | 13.8 | 72.9 |
| 长英文 (1024→1024) | 131 | 13.3 | 13.3 | 13.7 | 73.6 |
| 长中文 (1024→1024) | 142 | 13.2 | 13.2 | 13.6 | 74.1 |

**ITL 是终端用户体验的关键指标**。客户原有投诉（880 token 耗时 140s）源于 vLLM V0 的 ~158ms ITL。SGLang 的 13.3ms ITL 彻底解决：880 × 13.3ms ≈ 11.8s。

#### 客户真实负载测试（SGLang，1,196 请求 — 2026-02-11）

客户工程团队生产级负载测试（11 分 22 秒会话）：

| 指标 | 值 |
|------|:---:|
| **总请求数** | 1,196 |
| **错误率** | **0%**（全部 HTTP 200 OK） |
| **测试时长** | 11 分 22 秒 |
| **并发模式** | 峰值 5-7 请求/秒 |
| **Prompt 长度** | ~1,000 到 6,144 tokens/请求 |

**SGLang 内部指标**：

| 阶段 | 运行请求 | 队列深度 | KV Cache 使用率 | 生成吞吐 (t/s) |
|:-----|:-------:|:-------:|:--------------:|:--------------:|
| 预热 | 1 | 0 | 0% | 0~66 |
| 升温 | 15 | 0 | 27% | 49~358 |
| 高负载 | 20~28 | 25~48 | 90~97% | 61~190 |
| 峰值 | 19~42 | 20~65 | 93~98% | 52~168 |
| 回落 | 1~16 | 0~21 | 3~96% | 45~433 |

**关键发现**：KV Cache 峰值达 98%，最大并发运行 42 请求，队列最深 65 请求，但近饱和状态下依然零错误。

**基于负载测试的并发指南**：

| 场景 | 最大并发 | 预期端到端延迟 | KV Cache |
|------|:-------:|:-----------:|:--------:|
| 低延迟（交互式） | ≤5 | < 5s | < 30% |
| 均衡 | 10~15 | 10~30s | 50~70% |
| 最大吞吐 | 20~30 | 30~120s | 80~95% |
| 过载（测试观察值） | 40+ | 100~140s | 95~98% |

### vLLM V1 基准测试（v0.11.2）

V1 引擎使用 Ray compiled DAG 优化 PP 通信。V0 引擎在 v0.11.0 中已移除（PR #15256），因此 v0.11.2 仅支持 V1。测试日期：2026-02-05。

> **测试配置**：输入 1024 tokens → 输出 1024 tokens，stream=True

#### 第一轮（初始测试）

| 并发数 | QPS | TTFT (ms) | 平均延迟 (s) | 吞吐量 (t/s) |
|:------:|:---:|:---------:|:----------:|:----------:|
| 1 | 0.11 | 81 | 8.75 | 17.2 |
| 2 | 0.21 | 108 | 8.66 | 31.6 |
| 4 | 0.37 | 115 | 9.38 | 50.7 |
| 8 | 0.70 | 131 | 8.52 | 102.9 |
| 16 | 1.18 | 147 | 10.11 | 171.1 |
| 32 | 2.16 | 162 | 11.13 | 314.5 |
| 64 | 3.78 | 173 | 12.98 | 553.0 |
| 128 | — | — | 崩溃 | — |

#### 第二轮（NCCL 优化后）

| 并发数 | QPS | TTFT (ms) | 平均延迟 (s) | 吞吐量 (t/s) |
|:------:|:---:|:---------:|:----------:|:----------:|
| 1 | 0.11 | 93 | 9.50 | 17.2 |
| 2 | 0.21 | 122 | 9.00 | 31.6 |
| 4 | 0.37 | 131 | 9.61 | 56.5 |
| 8 | 0.64 | 140 | 9.11 | 89.4 |
| 16 | 1.17 | 149 | 10.17 | 170.3 |
| 32 | 2.18 | 163 | 11.07 | 314.7 |
| **64** | **4.22** | **N/A*** | **69.88** | **610.4** |
| 128 | — | — | 卡死 | — |

*注：第二轮 C=64 使用 `stream=False`，未测量 TTFT。

#### 方差分析（第一轮 vs 第二轮）

| 并发数 | 波动 | 评估 |
|:------:|:----:|:-----|
| 1-2 | 0% | 完全稳定 |
| 4 | +11% | 正常波动 |
| 8 | -13% | 正常波动 |
| 16-32 | <1% | 非常稳定 |
| **64** | **+10%** | **NCCL 修复收益** |

**关键问题**：V1 在 C≥128 时因 Ray compiled DAG Bug 崩溃或卡死 (PP>1)。该不稳定性导致客户生产环境降级到 v0.10.1 V0 引擎。

### vLLM V0 生产环境（v0.10.1 - 稳定回退方案）

V1 在 PP>1 场景下不稳定（C≥128 崩溃）后，生产服务降级到 v0.10.1 + `VLLM_USE_V1=0`。V0 引擎使用 `RayGPUExecutor`（传统 Ray 任务调度），完全绕过导致 V1 崩溃的 compiled DAG 代码路径。

> **注意**：V0 未进行标准并发基准测试。以下所有 V0 性能数据均来自客户生产环境验证。

#### V0 vs V1 性能对比

| 指标 | V1 引擎 (v0.11.2) | V0 引擎 (v0.10.1) | 差异 |
|------|:-----------------:|:-----------------:|:----:|
| 单请求吞吐 | ~17 t/s | ~6.8 t/s | -60% |
| C=32 吞吐 | 314.7 t/s | ~247 t/s | -22% |
| 峰值吞吐 | 610.4 t/s (C=64) | 304.4 t/s (C=33) | -50% |
| TTFT（空闲） | 81-93 ms | 141-146 ms | +60% |
| 稳定性 (PP>1) | ❌ 分钟~小时内崩溃 | ✅ 1,801 请求零崩溃 | — |
| 最大测试并发 | C=64（C=128 崩溃） | C=91 稳定 | — |

**数据来源**：V1 数据来自标准基准测试（2026-02-05，v0.11.2）。V0 数据来自客户生产环境验证（2026-02-06，v0.10.1）。

**结论**: V0 因 Ray 逐步任务调度开销，单请求吞吐比 V1 低约 60%，但提供了生产 PP>1 部署所需的稳定性。关键权衡是**稳定性优先于原始速度**。

#### 客户真实验证（V0 引擎，1,801 请求）

客户在 v0.10.1 V0 引擎上进行生产流量测试（2026-02-06）：

| 指标 | 值 |
|------|:---:|
| **成功请求总数** | **1,801** |
| **服务端错误 (500/502/503)** | **0** |
| **崩溃次数** | **0** |
| **峰值并发请求** | 91 |
| **峰值生成吞吐** | **304.4 tokens/s** @ ~C=30 |
| **TTFT（空闲，实测）** | 141-146 ms |

**客户负载下的吞吐量扩展**：

| 并发请求数 | 生成吞吐 (t/s) | KV Cache 使用率 |
|:----------:|:--------------:|:--------------:|
| 8 | 30.5 | 1.2% |
| 15 | 100.3 | 2.1% |
| 22 | 153.3 | 1.9% |
| 25 | 197-202 | 2.6% |
| 28 | 199.5 | 2.6% |
| 30 | 257.4 | 3.2% |
| 31 | 229.2 | 3.0% |
| 32 | 247.0 | 3.2% |
| 33 | **291.3** | 3.9% |

### SGLang 为何比 vLLM V0 快 10 倍

| 根因 | vLLM V0 的影响 | SGLang 的方案 |
|:-----|:--------------:|:-------------:|
| 调度开销 | V0 `RayGPUExecutor` 每步使用 Ray 任务（~4-5ms/token） | 自定义基于 NCCL 的 PP，无逐步 Ray 开销 |
| PP 通信 | NCCL over TCP 经 Ray 中介 | 直接 NCCL P2P + 重叠调度 |
| 批处理调度 | 缺乏连续批处理优化 | RadixAttention + 连续批处理 |
| 内核优化 | 旧版注意力内核 | FlashAttention 3 + FlashInfer 采样 |
| 预填充策略 | V0 无 Chunked Prefill | Chunked Prefill 减少排队 |

**vLLM V0 ITL 分解 (PP=2)**：每个解码步骤作为 Ray 任务调度。每 token：Ray 调度 (~1ms) → GPU Stage 0 (~3ms) → NCCL 发送 (~2ms) → GPU Stage 1 (~3ms) → NCCL 返回 (~2ms) → Ray 回调 (~1ms) = ~12ms GPU 周期，但受 Ray 调度抖动影响，实际 ITL ≈ 158ms。SGLang 完全消除了 Ray 逐步开销。

### V1 引擎 + PP 崩溃（vLLM v0.11.x）— 已知问题

vLLM v0.11.x 的 V1 引擎 + 流水线并行因 **Ray compiled DAG Bug** 崩溃：

1. `_accelerator_group` 重命名为 `_accelerator_group_id` 但调用方未更新
2. C++ 反序列化崩溃 `experimental_mutable_object_provider.cc`
3. V0 引擎在 v0.11.0 中**已移除**（PR #15256），`VLLM_USE_V1=0` 无效

**相关 Issue**: [vllm #26899](https://github.com/vllm-project/vllm/issues/26899)、[vllm #29373](https://github.com/vllm-project/vllm/issues/29373)、[ray #59404](https://github.com/ray-project/ray/issues/59404)

**解决方案**: 降级到 v0.10.1 + `VLLM_USE_V1=0` → V0 引擎 → `RayGPUExecutor`（绕过 compiled DAG）→ 稳定 PP。或迁移到 SGLang。

### NCCL 优化（Azure 关键配置）

Azure VM 有多个网卡（eth0、docker0 等），NCCL 可能选错网卡导致跨节点通信失败。

**解决方案**: `NCCL_SOCKET_IFNAME=eth0` + `NCCL_IB_DISABLE=1`

| 指标 | NCCL 修复前 | NCCL 修复后 |
|------|:-----------:|:-----------:|
| 服务启动 | 间歇性挂起 | ✅ 稳定 |
| C=64 吞吐量 | 553.0 t/s | **610.4 t/s (+10%)** |

### SGLang 配置说明 (PP>1)

| 参数 | 原因 |
|------|:-----|
| `--tool-call-parser qwen` | Qwen3 原生格式（比 hermes 更兼容） |
| `--disable-radix-cache` | **PP>1 必需** — radix cache 与流水线并行不兼容 |
| `--mem-fraction-static 0.85` | 保守的 GPU 显存分配，确保稳定 |
| `--chunked-prefill-size 6144` | 平衡 TTFT 和吞吐量 |
| `NCCL_SOCKET_IFNAME=eth0` | 强制使用 Azure 正确网卡 |

**失败的优化尝试（PP>1 不兼容）**：

| 优化项 | 错误 |
|:-------|:-----|
| `--kv-cache-dtype fp8_e4m3` | CUDA graph 捕获时 NCCL 错误 |
| `--enable-mixed-chunk` | `AssertionError: not compatible with PP` |
| `--num-continuous-decode-steps 2` | 挂起/超时 |
| `NCCL_ALGO=Tree` | CUDA graph 捕获时 NCCL 错误 |

**结论**: PP>1 场景下使用 SGLang 原始配置即可。

### 性能提升汇总（vLLM V0 → SGLang）

| 指标 | vLLM V0 | SGLang | 提升 |
|------|:-------:|:------:|:----:|
| **ITL** | 158 ms | 13.3 ms | **12 倍** |
| **880 token 响应** | ~140 s | ~11.8 s | **12 倍** |
| **单请求 TPS** | 6.8 t/s | 70-75 t/s | **10 倍** |
| **峰值吞吐** | 304 t/s | 1,320 t/s | **4.3 倍** |
| **崩溃次数** | 0 | 0 | 均稳定 |

---

## 硬件规格

### Azure NC40ads H100 v5 (Part 1)

| 组件 | 规格 |
|------|:----:|
| **GPU** | 1× NVIDIA H100 NVL 94GB HBM3 |
| **vCPU** | 40（AMD EPYC 第四代 "Genoa"） |
| **RAM** | 320 GiB |
| **本地 NVMe** | ~3.5 TB |

### Azure NC80adis H100 v5 (Part 2)

| 组件 | 规格 |
|------|:----:|
| **GPU** | 2× NVIDIA H100 NVL 94GB HBM3（每节点 188GB） |
| **GPU 互连** | NVLink 600 GB/s（同节点内两卡间） |
| **vCPU** | 80（AMD EPYC 第四代 "Genoa"） |
| **RAM** | 640 GiB |
| **本地 NVMe** | ~7 TB |

### H100 NVL vs H100 SXM

| 特性 | H100 NVL | H100 SXM |
|------|:--------:|:--------:|
| 形态 | PCIe | SXM5 |
| 显存 | 94 GB HBM3 | 80 GB HBM3 |
| NVLink 带宽 | 600 GB/s（2 卡桥接） | 900 GB/s（NVSwitch） |
| 目标场景 | **LLM 推理** | 训练 |
| 多卡扩展 | 2 卡最优 | 8 卡最优 |

### Qwen3-235B VRAM 需求

| 精度 | 模型大小 | 最低 GPU 配置 |
|:----:|:--------:|:------------:|
| BF16 | ~470 GB | 8× H100 80GB (TP=8) |
| **FP8** | **~235 GB** | **4× H100 NVL 94GB (TP=2, PP=2)** |
| INT4 | ~118 GB | 2× H100 NVL 94GB (TP=2) |

---

## 决策矩阵

### Part 1: 注意力后端（32B，单卡）

| 场景 | 推荐 | 原因 |
|------|:----:|:-----|
| 生产聊天机器人 | **FA2** | TTFT 更低 = 更好的用户体验 |
| 批量处理 | **FA2** | 吞吐量更高 |
| 低并发 (<128) | 均可 | <3% 差异 |
| 高并发 (256+) | **FA2** | 快 5-7% |

### Part 2: 推理引擎（235B，多节点）

| 场景 | 推荐 |
|------|:----:|
| 多节点 PP 部署 | **SGLang**（稳定 + 高速） |
| 单节点纯 TP | vLLM V1 或 SGLang |
| 必须用 vLLM + PP | v0.10.1 + V0 引擎 |
| vLLM v0.11.x + PP | ❌ 不推荐 |

### 何时需要多节点 PP

| 模型大小 | 所需 GPU | 推荐配置 |
|:--------:|:--------:|:--------:|
| < 70B | 1-2 | 单节点纯 TP |
| 70B - 100B | 2-4 | 单节点 TP=4 或双节点 PP=2 |
| **100B - 250B** | **4** | **双节点 TP=2 PP=2** ✅ |
| > 250B | 8+ | 4+ 节点 |

---

## 在 Azure 上运行

### Part 1: 单卡基准测试

```bash
# 1. 部署 Azure NC40ads H100 v5
# 2. 拉取 vLLM Docker 镜像
docker pull vllm/vllm-openai:v0.11.2

# 3. 启动 FA2 服务
docker run -d --gpus all \
  -v <your-model-path>:/models/Qwen3-32B-FP8 \
  -p 8088:8000 --name vllm-fa2 \
  vllm/vllm-openai:v0.11.2 \
  --model /models/Qwen3-32B-FP8 \
  --max-model-len 4096 --gpu-memory-utilization 0.95

# 4. 等待就绪
sleep 30 && curl http://localhost:8088/v1/models

# 5. 运行基准测试
python3 scripts/bench_0112.py

# 6. 测试 FlashInfer（添加环境变量）
docker run -d --gpus all \
  -e VLLM_ATTENTION_BACKEND=FLASHINFER \
  -v <your-model-path>:/models/Qwen3-32B-FP8 \
  -p 8088:8000 --name vllm-fi \
  vllm/vllm-openai:v0.11.2 \
  --model /models/Qwen3-32B-FP8 \
  --max-model-len 4096 --gpu-memory-utilization 0.95
```

### Part 2: 多节点基准测试

```bash
# 1. 部署 2× Azure NC80adis H100 v5
# 2. 设置 NCCL 环境
export NCCL_SOCKET_IFNAME=eth0
export NCCL_IB_DISABLE=1

# 3. 启动 Ray 集群（node0 = head, node1 = worker）
# 4. 启动 SGLang (PP=2 TP=2)
python3 -m sglang.launch_server \
  --model Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 \
  --tp 2 --pp 2 \
  --tool-call-parser qwen \
  --disable-radix-cache \
  --mem-fraction-static 0.85 \
  --chunked-prefill-size 6144

# 5. 运行基准测试
python3 scripts/bench_235b.py
```

---

## 参考资料

- [FlashAttention-2 论文](https://arxiv.org/abs/2307.08691) — Dao et al., 2023
- [FlashAttention-3 论文](https://arxiv.org/abs/2407.08691) — Shah et al., 2024（Hopper 优化）
- [FlashInfer 论文](https://arxiv.org/abs/2501.01005) — Ye et al., MLSys 2025（内核库和生成器）
- [FlashInfer GitHub](https://github.com/flashinfer-ai/flashinfer)
- [vLLM GitHub Issue #9471](https://github.com/vllm-project/vllm/issues/9471) — FlashInfer FP8 启发式 Bug
- [vLLM GitHub Issue #26899](https://github.com/vllm-project/vllm/issues/26899) — PP compiled DAG 崩溃
- [SGLang 文档](https://docs.sglang.ai/)
- [SGLang 注意力后端文档](https://docs.sglang.ai/backend/attention_backend.html)
- [Ray GitHub](https://github.com/ray-project/ray)
- [Qwen3 GitHub](https://github.com/QwenLM/Qwen3)
- [Qwen3.5 博客](https://qwen.ai/research) — 2026 年 2 月
- [HuggingFace Qwen3 Collection](https://huggingface.co/collections/Qwen/qwen3-67dd247413f0e2e4f653967f)
- [HuggingFace Qwen3.5 Collection](https://huggingface.co/collections/Qwen/qwen35-67b2bc617a45415a73bbb04e)
- [Azure NC H100 v5 系列](https://learn.microsoft.com/zh-cn/azure/virtual-machines/nc-h100-v5-series)

---

**作者**: 魏新宇 (Xinyu Wei)

## 许可证

MIT License
