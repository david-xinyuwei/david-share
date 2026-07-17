# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

在 Azure **AMD Instinct MI300X** 上运行 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）**，使用 SGLang + AMD CK A8W8 blockwise GEMM + AITER + MTP/EAGLE + 模型专用 fused-MoE tuning，并与小米 H200 参考数据并列展示。

本客户版 repo 包含核心对比结果、完整的微软扩展性测试矩阵、唯一一套支持的复现代码和紧凑运行时元数据。PD-separated decode 必须把 RDMA 设备暴露给容器（`--privileged`、`/dev/mem`、`CAP_SYS_ADMIN`），否则 Mooncake 会 fallback 到 TCP，高并发吞吐结果无效。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB)
>
> 最后测试：2026-07-17

[English](README.md) | 中文 | [验证证据](data/validation/)

> **64K Decode 核心亮点（每点 1 次 measurement run）：**在最终双节点 1P1D MI300X runtime 上，从 concurrency 16 到 96，mean TPOT 稳定在 11.55–11.94 ms。与客户提供的 H200 per-DP TPOT 在相同 local batch 下对比，MI300X 在 16 基本持平，在 32–96 的 TPOT **低 17.8–41.1%**。这是方向性的 Decode-only 观察，不声明 Prefill 或 E2E 领先：MI300X 达到客户 H200 64K 单节点 Prefill 参考的 69.3%，而客户数据没有匹配的 64K E2E 结果。

---

## 架构

![双节点 MI300X 1P1D Prefill-Decode 架构](images/pd_architecture.png)

*图 1：最终双节点 MI300X 1P1D 拓扑、Mooncake KV transfer 路径与已验证运行时栈。*

---

## 核心结果 — 微软实测 MI300X vs 小米 H200

以下展示从 accepted runs 中选出的已验证客户对比点。每一行的 MI300X 指标都来自同一条测量记录；下一节单独展示一轮完整扩展性矩阵。

### 1P1D Prefill

| Context | Concurrency | 微软实测 MI300X input tok/s | 小米 H200 TP8/EP16/DP2 单节点参考 | MI300X / H200 单节点 |
|---:|---:|---:|---:|---:|
| 8K | 4 | **20,305.98** | 31,950 | 63.6% |
| 64K | 4 | **18,983.91** | 27,400 | 69.3% |
| 256K | 4 | **12,864.96** | 17,400 | 73.9% |

### 1P1D Decode — 8K Input / 1K Output

| MI300X concurrency | H200 per-DP BS | 微软实测 MI300X output tok/s | 小米 H200 报告的 per-DP/单节点 tok/s | MI300X / H200 单节点 |
|---:|---:|---:|---:|---:|
| 16 | 16 | **1,331.98** | 1,381 | 96.5% |
| 32 | 32 | **1,936.24** | 2,549 | 76.0% |
| 64 | 64 | **2,465.01** | 4,483 | 55.0% |
| 128 | 128 | **2,486.89** | 7,013 | 35.5% |

#### Decode TPOT — 越低越好

| MI300X concurrency | H200 per-DP BS | 微软实测 MI300X mean TPOT (ms) | 小米 H200 TPOT 参考 (ms) | MI300X / H200 |
|---:|---:|---:|---:|---:|
| 16 | 16 | **10.83** | 11.59 | 0.93× |
| 32 | 32 | **13.65** | 12.56 | 1.09× |
| 64 | 64 | **16.88** | 14.28 | 1.18× |
| 128 | 128 | **16.56** | 18.25 | 0.91× |

比值低于 1.00× 表示 MI300X 的 TPOT 更低。这里比较的是一个 MI300X Decode 节点与一个 H200 DP replica/节点在相同 local batch 下的结果。H200 报告使用 DP=4，因此这不是整套部署的 aggregate 对比。每个 MI300X TPOT 都与上方 throughput 使用同一条测量记录。

### 双节点 DP=2 Prefill — 峰值聚合吞吐

| Context | Concurrency | Aggregate input tok/s |
|---:|---:|---:|
| 8K | 16 | **46,747.01** |
| 64K | 2 | **38,984.45** |

DP=2 的 nominal-length 256K 结果保留在后面的扩展性矩阵中，但不作为 exact-token 核心结果。

### 结果口径

- Headline 数值来自按最终配置和有效性选定的多次 accepted reproduction runs，不是一轮统一矩阵，也不是跨 run 聚合值。机器可读数据中的 `headline_source` 记录来源 run；详细扩展性表是一轮完整矩阵，repeatability 表展示跨 run 波动。
- 核心结果中的 1P1D 256K 使用 `--tokenize-prompt`，每条 request 精确发送 262,144 个 token IDs。
- DP=2 为两台 MI300X 节点的 Prefill-only 聚合容量，不包含 P→D KV-cache transfer。
- H200 Decode `tok/s` 是报告中的 per-DP/单节点口径（`BS × TPS`），不作为 DP=4 aggregate throughput 展示。
- H200 数值仍是方向性参考，不是严格 apples-to-apples 硬件 benchmark：MI300X 使用真实 expert routing，H200 参考使用理想均衡 routing。
- 机器可读核心结果：[`data/final-results.tsv`](data/final-results.tsv)。

### H200 参考数据来源

| 字段 | 公开记录 |
|---|---|
| 来源 | 小米提供的 MiMo-V2.5-Pro 性能报告；私有归档，不公开转载 |
| 审阅日期 | 2026-05-18 |
| Prefill 参考 | TP8/EP16/DP2、balanced `fake_topk_ids`、关闭 radix cache、单机/单节点吞吐 |
| Decode 参考 | 8K 和 64K input / 1K output；TP8/EP32/DP4、balanced `fake_topk_ids`、MTP layer 3、报告 accept rate 0.75 |
| Decode TPOT 来源 | 客户工作簿；根据 per-DP Decode 日志输出速率与 local BS 按 `1000 / (tok/s ÷ BS)` 反推 |
| Decode 吞吐口径 | 报告中的 per-DP/单节点 `BS × TPS`；未确认是 DP=4 aggregate throughput |
| 交付用途 | 仅作方向性 per-node/per-DP 参考 |

机器可读 provenance 和全部参考值见 [`data/validation/h200-reference.json`](data/validation/h200-reference.json)。

---

## 微软扩展性测试

AMD 提供了基础启动方法：container image、tuned AITER path、1P1D/DP=2 topology 和 benchmark 入口。微软先严格复现该路径，再独立扩展 context/concurrency 覆盖范围，并加入 fail-closed correctness gates。**以下所有 MI300X 性能数据均为微软实测；H200 TPOT 是记录在 `h200-reference.json` 中的客户提供参考值。不包含 AMD 性能数值。**

### 测试矩阵

| 测试面 | 工作负载 | Concurrency sweep | 每点请求数 |
|---|---|---|---:|
| 1P1D Decode | 8K input / 1K output | 8, 16, 32, 64, 96, 128, 192 | 256 |
| 1P1D 长上下文 Decode | Requested 64K input / 1K output；requested 255K input / 1K output（256K total sequence） | 64K：16, 32, 64, 96；255K：1 | 32, 64, 128, 192；1 |
| 1P1D Prefill | 8K、64K、nominal 256K / 1 output | 1, 2, 4, 8 | 16 |
| 双节点 DP=2 Prefill | 8K、64K、nominal 256K / 1 output | 8K/64K：1, 2, 4, 8, 16；nominal 256K：1, 2, 4, 8 | 32 |

以下表格展示实测扩展性结果。Decode 核心生产并发点另外做了两次 fresh-service 复测。

### Decode 扩展性 — 8K Input / 1K Output

| Concurrency | Output tok/s | Mean TPOT (ms) | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8 | 930.00 | 7.65 | 863.69 |
| 16 | 1,303.44 | 10.72 | 1,398.73 |
| 32 | 1,930.10 | 13.68 | 2,296.89 |
| 64 | 2,462.83 | 17.08 | 7,406.18 |
| 96 | 2,497.69 | 15.89 | 18,273.38 |
| 128 | 2,468.95 | 16.45 | 27,128.38 |
| 192 | 2,500.54 | 15.98 | 40,956.57 |

实测现象：

- 吞吐从 concurrency 8 的 930.00 tok/s 增长到 concurrency 64 的 2,462.83 tok/s，此后到 concurrency 192 维持在约 2.47–2.50K tok/s 的平台区间。
- concurrency 64 以后吞吐基本不再增长，但 TTFT 显著上升。因此这是容量平台，不是延迟改善。

### Decode 核心点 Fresh-Service 复测

| Concurrency | Fresh run 1 tok/s | Fresh run 2 tok/s | 吞吐差异 | TPOT run 1 / run 2 (ms) |
|---:|---:|---:|---:|---:|
| 16 | 1,331.98 | 1,303.44 | -2.14% | 10.83 / 10.72 |
| 32 | 1,936.24 | 1,930.10 | -0.32% | 13.65 / 13.68 |
| 64 | 2,457.73 | 2,462.83 | +0.21% | 17.00 / 17.08 |
| 128 | 2,486.89 | 2,468.95 | -0.72% | 16.56 / 16.45 |

四个复测点的两次 fresh-service 吞吐最大绝对差异为 **2.14%**。

### 长上下文 Decode — 最终 Baked Image

以下点于 2026-07-17 使用 Software Stack 章节中的 immutable image 直接拉取并运行得到。每一行是 1 次 measurement run；同一行中的多个 requests 不是独立重复实验。

长 ISL 首先考验 **Prefill**。判断长输入摄入能力与在线响应，应看 Input tok/s 和 TTFT；判断首 token 之后的 Decode，应在固定 local batch 下看 TPOT/ITL。Throughput 的单位通常是 tokens/s；`TPUT` 只是 throughput 的缩写，不是另一种独立指标。

| 指标 | 主导阶段 | 含义 |
|---|---|---|
| Input tok/s | Prefill | 长 ISL 容量主指标；越高越好 |
| TTFT | Prefill + queueing + KV transfer | 首 token 等待时间；越低越好 |
| TPOT / ITL | Decode | 首 token 之后每个输出 token 的延迟；越低越好 |
| Decode server output tok/s | Decode | 固定 workload 下的 Decode 侧容量；越高越好 |
| SGLang E2E Output token throughput | 完整请求 | 包含 Prefill/TTFT；不能当作纯 Decode capacity |

#### Decode 侧优势 — 64K Input / 1K Output

| Local concurrency / per-DP BS | MI300X mean TPOT (ms) | 小米 H200 mean TPOT (ms) | MI300X / H200 |
|---:|---:|---:|---:|
| 16 | 11.94 | 11.99 | 1.00× |
| 32 | 11.76 | 14.31 | 0.82× |
| 64 | 11.75 | 16.33 | 0.72× |
| 96 | 11.55 | 19.63 | 0.59× |

在相同 local batch 下，MI300X 在 16 基本持平，在 32–96 的 TPOT **低 17.8–41.1%**。TPOT 越低，表示首 token 之后单条请求的 token 生成越快。

H200 TPOT 本身是客户工作簿根据 per-DP Decode 日志吞吐反推的数值。这是同 workload、相同 local batch 的方向性 Decode 对比，不是整套部署对比：MI300X 使用真实 expert routing；H200 参考使用 balanced `fake_topk_ids`、TP8/EP32/DP4、MTP3 和报告 accept rate 0.75。

H200 来源：客户提供报告于 2026-05-18 完成审阅，并于 2026-07-17 对原始工作簿重新核验；见 [`data/validation/h200-reference.json`](data/validation/h200-reference.json)。私有工作簿不在本 Repo 中再分发。

#### 与 H200 的可比和不可比边界

| 测试面 | 微软实测 MI300X | 客户提供 H200 | 判定 |
|---|---:|---:|---|
| 64K Prefill | 18,983.91 input tok/s | 27,400 input tok/s | 方向性单节点对比：MI300X 为 H200 的 69.3%，MI300X 不领先 |
| 64K Decode | 11.55–11.94 ms TPOT | 相同 BS 下 11.99–19.63 ms TPOT | 方向性相同 local batch 对比：MI300X 在 BS32–96 领先 |
| 64K/1K E2E | 已测 SGLang E2E output tok/s 与 TTFT | 客户无匹配 E2E 结果 | 不计算 H200 比率，不声明 parity |
| Requested 255K + 1K | 1 个成功能力点 | 客户无完全相同 workload | 只证明能力，不做 H200 对比 |

#### 端到端 1P1D 诊断 — 包含 Prefill

SGLang 的 `Output token throughput` 是**端到端（E2E）**指标：请求的总输出 token 数除以完整 benchmark 时长，其中包含 Prefill/TTFT；它不是纯 Decode server capacity。对于本次固定 64K/1K workload，按定义有 `Output token throughput = Input token throughput ÷ 64`。

| Requested ISL | OSL | Concurrency | Requests | SGLang E2E output tok/s（包含 Prefill） | Input tok/s | Mean TPOT (ms) | Mean TTFT (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| Requested 64K | 1K | 16 | 32 | 265.17 | 16,970.68 | 11.94 | 37,571.24 |
| Requested 64K | 1K | 32 | 64 | 276.59 | 17,701.98 | 11.76 | 80,228.37 |
| Requested 64K | 1K | 64 | 128 | 284.00 | 18,175.89 | 11.75 | 165,190.68 |
| Requested 64K | 1K | 96 | 192 | 288.66 | 18,474.01 | 11.55 | 248,339.44 |
| Requested 255K (256K total) | 1K | 1 | 1 | 31.93 | 8,142.75 | 10.88 | 20,931.86 |

实测现象：

- Requested 64K ISL 下，E2E output throughput 只从 265.17 增长到 288.66 tok/s，Input throughput 在 16.97–18.47K tok/s 进入平台；Mean TPOT 稳定在 11.55–11.94 ms，但 Mean TTFT 从 37.57 秒增长到 248.34 秒。因此 E2E 结果受 Prefill 限制，不能把 265–289 tok/s 解读成纯 Decode capacity。
- 最后一行实际发送 261,120 input tokens，并生成 1,024 output tokens，总序列为 262,144 tokens。这是 requested-255K 能力点，不是 256K-input 声明。
- 客户报告中存在匹配的 64K TPOT 参考，但没有匹配的 255K 参考。

机器可读结果：[`data/decode-long-context-results.tsv`](data/decode-long-context-results.tsv)。Runtime identity、测试方法与 source-artifact hashes：[`data/validation/decode-long-context-evidence.json`](data/validation/decode-long-context-evidence.json)。

### 1P1D Prefill 扩展性

| Input | Concurrency | Input tok/s | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8K | 1 | 16,835.22 | 485.70 |
| 8K | 2 | 19,618.25 | 829.40 |
| 8K | 4 | 18,161.81 | 1,612.03 |
| 8K | 8 | 21,004.97 | 2,817.91 |
| 64K | 1 | 18,057.01 | 3,628.49 |
| 64K | 2 | 19,860.45 | 6,481.41 |
| 64K | 4 | 18,763.17 | 12,970.83 |
| 64K | 8 | 18,765.43 | 22,530.68 |
| Nominal 256K | 1 | 12,381.87 | 21,170.66 |
| Nominal 256K | 2 | 12,378.06 | 41,208.61 |
| Nominal 256K | 4 | 12,389.64 | 77,254.06 |
| Nominal 256K | 8 | 12,402.23 | 133,251.83 |

实测现象：

- 完整矩阵中的 8K Prefill 在 concurrency 8 达到 21,004.97 input tok/s。
- 64K Prefill 在 concurrency 2 达到峰值，此后随着并发增加保持在约 18.76K tok/s。
- nominal 256K 行使用 random-text prompt construction（`tokenize_prompt=false`），只描述扩展趋势。核心 exact-token 结果来自独立 targeted concurrency-4 复测：**12,864.96 input tok/s**。

### 双节点 DP=2 Prefill 扩展性

| Input | Concurrency | Aggregate input tok/s | Mean TTFT (ms) |
|---:|---:|---:|---:|
| 8K | 1 | 20,751.73 | 393.90 |
| 8K | 2 | 41,201.86 | 394.17 |
| 8K | 4 | 43,401.70 | 723.96 |
| 8K | 8 | 46,113.92 | 1,296.43 |
| 8K | 16 | 46,747.01 | 2,276.28 |
| 64K | 1 | 19,695.02 | 3,326.53 |
| 64K | 2 | 38,984.45 | 3,348.49 |
| 64K | 4 | 38,382.03 | 6,615.25 |
| 64K | 8 | 38,204.80 | 12,418.82 |
| 64K | 16 | 38,155.28 | 21,164.99 |
| Nominal 256K | 1 | 12,783.28 | 20,505.88 |
| Nominal 256K | 2 | 25,063.73 | 20,823.01 |
| Nominal 256K | 4 | 24,923.63 | 40,785.01 |
| Nominal 256K | 8 | 24,765.29 | 76,468.09 |

实测现象：

- DP=2 的 8K 和 64K aggregate Prefill throughput 从 concurrency 1 到 2 接近翻倍，随后进入平台区间。
- DP=2 测量通过双节点 router 使用两个 worker。
- 尚未完成 DP=2 256K exact-token rerun。这些行保留为 nominal-length 扩展性观察，不进入核心验证表。
- DP=2 是 Prefill-only capacity，不是 2P1D end-to-end throughput，也不测量 P→D KV-cache transfer。

### 256K 方法口径

| 证据集 | Client framing | 交付用途 |
|---|---|---|
| 完整扩展矩阵 | Random-text construction，`tokenize_prompt=false` | 用于 scaling 和 boundary 观察；nominal 256K 不是 exact-token 核心证据 |
| Targeted 1P1D 256K 复测 | 精确 262,144 token IDs，`--tokenize-prompt` | 核心结果：12,864.96 input tok/s |
| 当前 `scripts/amd-latest/` | 所有 256K-input Prefill benchmark 均使用 exact token IDs | 后续 256K-input Prefill 结果的强制复现路径 |
| 最终 baked image 长上下文 Decode | Random-text framing；requested 64K input 和 requested 255K input + 1K output | 仅作为 MI300X 能力/扩展性结果；不是 256K-input 或 H200 parity 声明 |

### 机器可读证据

- 核心结果点：[`data/final-results.tsv`](data/final-results.tsv)
- 详细扩展性结果：[`data/scalability-results.tsv`](data/scalability-results.tsv)
- Decode 核心点复测：[`data/decode-repeatability.tsv`](data/decode-repeatability.tsv)
- 长上下文 Decode 结果：[`data/decode-long-context-results.tsv`](data/decode-long-context-results.tsv)
- 长上下文 runtime 与 source-artifact evidence：[`data/validation/decode-long-context-evidence.json`](data/validation/decode-long-context-evidence.json)
- Exact-token 与 runtime 验证元数据：[`data/validation/`](data/validation/)
- 唯一支持的复现代码：[`scripts/amd-latest/`](scripts/amd-latest/)
- Repo 质量门：`python3 scripts/validate_repo.py`（预期最后一行：`REPO_VALIDATION=PASS`）

---

## 硬件与软件栈

### 计算 — 双节点 Azure MI300X 集群

| 属性 | 值 |
|------|---|
| Azure SKU | `Standard_ND96isr_MI300X_v5`（每节点 8× MI300X） |
| GPU | AMD Instinct MI300X, `gfx942` (CDNA 3), **192 GB HBM3**，5.3 TB/s max peak theoretical |
| 节点数 | 2（VMSS，相同 placement group — IB 保证） |
| 总 GPU 内存 | **16× 192 GB = 3,072 GB** |
| InfiniBand | 8× CX7 400G NDR/节点，实测 **368 Gbps**/端口 |

### 软件栈

| 组件 | 版本 | 说明 |
|------|------|------|
| 已验证 runtime 镜像 | `mimomi300xacr.azurecr.io/mimo-v2.5-pro-mi300x@sha256:08deabd2f3a4e98e183944048730f560056b0e4dd724c06f74c368645a655910` | 私有 ACR；37 layers；clean Docker pull 已验证 |
| 基础镜像来源 | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | Base image ID `sha256:bb9d2e5ab1a6...` |
| SGLang | Package `0.0.0.dev14147+g2f9b9aedf.d20260706`、source HEAD `2f9b9aedf` | 最终测试 runtime |
| AITER | Source HEAD `00e94abf`；tuned CSV SHA-256 `2c87ff1...80ea7` | 最终测试 runtime |
| ROCm | 7.2.0 | |
| GEMM 路径 | **CK A8W8 blockwise bpreshuffle** | `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1` |
| Mooncake | `0.3.7.post2` | PD 分离 KV cache 传输 |
| PyTorch | 2.9.1+rocm7.2.0 | ROCm backend |

### 模型

| 属性 | 值 | 来源 |
|------|---|------|
| 模型 | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| 总参数 | 1.02 T | HF Model Card |
| 活跃参数 | 42 B / token | HF Model Card |
| Routed experts | 384，每 token 8 个活跃 | HF Model Card |
| Attention | 混合：10 Global + 60 SWA (window=128) | HF Model Card |
| MTP | 3 层 multi-layer EAGLE | HF Model Card |
| 量化 | FP8 E4M3 | HF Model Card |
| Checkpoint 大小 | 963 GB (34 safetensors) | 实测 |

---

## 在 Azure 上运行并复现最终结果

使用下面的 immutable baked runtime。它内置已测试的 SGLang/AITER source trees、Python/runtime deltas、tuned fused-MoE 配置、RDMA userspace stack，以及位于 `/opt/mimo-mi300x/scripts/amd-latest` 的 [`scripts/amd-latest/`](scripts/amd-latest/)。

### 前置条件

- 2× Azure `Standard_ND96isr_MI300X_v5` 节点
- 通过私有渠道提供的 repository-scoped ACR pull username 和 password
- 模型：`/data/models/MiMo-V2.5-Pro`
- Benchmark dataset 位于 `/data`；镜像不包含模型权重和 dataset
- PD-separated Decode 容器必须暴露 RDMA devices、`/dev/mem` 和 `CAP_SYS_ADMIN`

### 拉取并启动 Runtime — 两个节点都执行

容器需要较高的 host 权限来完成 RDMA memory registration，只能在专用、可信的 benchmark 节点上运行。

```bash
export ACR_LOGIN_SERVER=mimomi300xacr.azurecr.io
export IMAGE_REF='mimomi300xacr.azurecr.io/mimo-v2.5-pro-mi300x@sha256:08deabd2f3a4e98e183944048730f560056b0e4dd724c06f74c368645a655910'

read -rp 'ACR pull username: ' ACR_USERNAME
read -rsp 'ACR pull password: ' ACR_PASSWORD && printf '\n'
printf '%s' "$ACR_PASSWORD" | docker login "$ACR_LOGIN_SERVER" \
	--username "$ACR_USERNAME" --password-stdin
docker pull "$IMAGE_REF"
docker logout "$ACR_LOGIN_SERVER"
unset ACR_USERNAME ACR_PASSWORD

docker run -d --name mimo-mi300x \
	--privileged --network=host --ipc=host --shm-size=256g \
	--device=/dev/kfd --device=/dev/dri --device=/dev/mem \
	--cap-add=CAP_SYS_ADMIN --cap-add=SYS_PTRACE \
	--security-opt seccomp=unconfined --security-opt label=disable \
	--group-add video -v /data:/data \
	--entrypoint /bin/bash "$IMAGE_REF" -lc 'sleep infinity'

docker exec mimo-mi300x bash -lc '
	set -euo pipefail
	test "$(git -C /sgl-workspace/sglang_0625 rev-parse HEAD)" = 2f9b9aedf32977bc5d088a86ec0a73bcf432a4d0
	test "$(git -C /sgl-workspace/aiter_0625 rev-parse HEAD)" = 00e94abf15e1e09ab7cf481e989bca5d19a99b82
	test "$(sha256sum /sgl-workspace/aiter_0625/aiter/configs/model_configs/mimo_v2_5_pro_b16_tuned_fmoe.csv | cut -d" " -f1)" = 2c87ff1fa062c73e1941962f8630a335ea1e39d2dbb5b0c2d4971bcd55880ea7
	test -e /dev/infiniband/uverbs0
	test -e /dev/mem
	cd /opt/mimo-mi300x/scripts/amd-latest
	sha256sum -c SHA256SUMS.txt
'
```

镜像 identity 与 clean-pull 证据见 [`data/validation/container-image.json`](data/validation/container-image.json)。

### 1P1D

```bash
# 在每个节点进入容器，然后使用内置 bundle。
docker exec -it mimo-mi300x bash
cd /opt/mimo-mi300x/scripts/amd-latest
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json
read -rp 'Prefill node IB IP: ' PREFILL_IB_IP
read -rp 'Decode node IB IP: ' DECODE_IB_IP
export PREFILL_IB_IP DECODE_IB_IP

# 先在对应节点的独立终端启动两个 worker：
bash launch_pd_prefill.sh
bash launch_pd_decode.sh

# Prefill 节点 capacity gate：
python3 validate_server_info.py http://127.0.0.1:30000/server_info \
	--output /data/mimo-amd-latest/onep/evidence/prefill-server-info.json

# Decode 节点 capacity gate：
python3 validate_server_info.py http://127.0.0.1:30001/server_info \
	--output /data/mimo-amd-latest/onep/evidence/decode-server-info.json

# 两个 capacity gate 都通过后，在 Prefill 节点启动 Router：
bash launch_pd_router.sh

# Router readiness gate：
curl -fsS --max-time 30 http://127.0.0.1:40000/v1/models >/dev/null

# 三个 gate 通过后，在 Router 节点执行：
bash benchmark_1p_prefill.sh
bash benchmark_decode.sh
```

Immutable image 内置的是原 headline bundle；长上下文 Decode 脚本是在该镜像发布后新增到本 Repo 的扩展。它在不修改镜像的前提下使用相同 immutable runtime 执行。将当前 Repo clone 或复制到 `/data` 下，然后运行：

```bash
cd /data/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/xisun/ShareGPT_V3_unfiltered_cleaned_split.json
export PYTHONPATH="/sgl-workspace/sglang_0625/python${PYTHONPATH:+:$PYTHONPATH}"
bash benchmark_decode_long_context.sh
```

完成后，把 Decode 节点证据复制到 Router 节点，使 3 份 service logs 和 2 份 `server-info.json` 位于同一目录，并保留下列 basename。然后执行：

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
EVIDENCE=/data/mimo-amd-latest/onep/evidence

python3 validate_service_logs.py \
	"$EVIDENCE/prefill_outer.log" \
	"$EVIDENCE/decode_outer.log" \
	"$EVIDENCE/router_outer.log" \
	--profile onep \
	--output "$EVIDENCE/service-validation.json"

python3 validate_exact_256k.py \
	/data/mimo-amd-latest/onep/prefill/benchmark_262144_out1_con4.log \
	--prefill-info "$EVIDENCE/prefill-server-info.json" \
	--decode-info "$EVIDENCE/decode-server-info.json" \
	--service-logs \
		"$EVIDENCE/prefill_outer.log" \
		"$EVIDENCE/decode_outer.log" \
		"$EVIDENCE/router_outer.log" \
	--output "$EVIDENCE/exact-token-256k.json"
```

### DP=2 双节点 Prefill

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
bash launch_dp2_node0.sh
bash launch_dp2_node1.sh

# 启动 Router 前分别直连验证 node0 和 node1：
python3 validate_server_info.py http://127.0.0.1:30000/server_info \
	--output /data/mimo-amd-latest/dp2/evidence/node0-server-info.json
python3 validate_server_info.py http://127.0.0.1:30001/server_info \
	--output /data/mimo-amd-latest/dp2/evidence/node1-server-info.json

read -rp 'Node0 IB IP: ' Node0_IP
read -rp 'Node1 IB IP: ' Node1_IP
export Node0_IP Node1_IP
bash launch_dp2_router.sh
curl -fsS --max-time 30 http://127.0.0.1:40000/v1/models >/dev/null
bash benchmark_dp2_prefill.sh
```

上面的 convenience script 会连续执行三个点。要生成可报告的逐点 distribution 证据，需要启动 fresh DP=2 services，在单个 `run_point` 前后分别统计两个 worker log 中的 `grep -c 'POST /generate'`，再验证记录下来的四个整数。8K、64K、256K 都要分别执行：

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
export LOG_DIR=/data/mimo-amd-latest/dp2
source ./benchmark_common.sh

# 记录两个 before-count 后，在 node0 每次只执行一个点：
run_point 8192 1 16 32 1 900 'Input token throughput'
# run_point 65536 1 2 32 1 900 'Input token throughput'
# run_point 262144 1 2 32 1 1200 'Input token throughput' token_ids

# 分别在 node0 和 node1 记录 before/after count：
grep -c 'POST /generate' /data/mimo-amd-latest/dp2/service/node0_outer.log || true
grep -c 'POST /generate' /data/mimo-amd-latest/dp2/service/node1_outer.log || true

read -rp 'Node0 before count: ' NODE0_BEFORE
read -rp 'Node0 after count: ' NODE0_AFTER
read -rp 'Node1 before count: ' NODE1_BEFORE
read -rp 'Node1 after count: ' NODE1_AFTER
python3 write_distribution.py \
	--node0-before "$NODE0_BEFORE" --node0-after "$NODE0_AFTER" \
	--node1-before "$NODE1_BEFORE" --node1-after "$NODE1_AFTER" \
	--expected-total 33 \
	--output /data/mimo-amd-latest/dp2/benchmark_8192_out1_con16.distribution.tsv
```

汇总 3 份 DP=2 service logs 后执行：

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
EVIDENCE=/data/mimo-amd-latest/dp2/evidence
python3 validate_service_logs.py \
	"$EVIDENCE/node0_outer.log" \
	"$EVIDENCE/node1_outer.log" \
	"$EVIDENCE/router_outer.log" \
	--profile dp2 \
	--output "$EVIDENCE/service-validation.json"
```

只有 client gate 通过、两个 worker delta 都为正且总和为 33（32 measured + 1 warmup）、service-log gate 通过时，该 DP=2 点才可报告。

### 清理

```bash
docker rm -f mimo-mi300x
```

---

## 必要运行设置

| 设置 | 要求 |
|---|---|
| Decode CUDA Graph | 保持启用；Prefill 禁用 CUDA Graph。 |
| 256K request framing | 使用 context length 262151 和 `--tokenize-prompt`；要求 `max_req_input_len>=262145`。 |
| Router health | 使用非生成型 `/server_info` endpoint，timeout 30 秒。 |

---

## 参考资料

- [Azure ND-MI300X-v5 规格系列](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ndmi300xv5-series)
- [AMD Instinct MI300X datasheet](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/data-sheets/amd-instinct-mi300x-data-sheet.pdf)
- [MiMo-V2.5-Pro Model Card](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork — `mimo_aiter_attn` 分支](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo 模型专用 fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)
