# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告

[![MI300X](https://img.shields.io/badge/GPU-AMD%20MI300X-ed1c24)](https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html)
[![MiMo](https://img.shields.io/badge/Model-MiMo--V2.5--Pro-blue)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
[![SGLang](https://img.shields.io/badge/Engine-SGLang-green)](https://github.com/sgl-project/sglang)
[![ROCm](https://img.shields.io/badge/ROCm-7.2.0-orange)](https://rocm.docs.amd.com/)

本报告记录 **小米 MiMo-V2.5-Pro（1.02T MoE / 42B 活跃参数 / FP8）** 在 Azure **AMD Instinct MI300X** 上的性能测试结果。推理引擎采用 SGLang，关键优化包括 AMD CK A8W8 blockwise GEMM、AITER、MTP/EAGLE，以及针对该模型的 fused-MoE tuning；小米 H200 数据作为独立参考列示。

本仓库面向客户，包含核心对比结果、微软补充的扩展性测试、唯一受支持的复现代码和必要的运行环境元数据。本文保留 Prefill（预填充阶段）、Decode（解码阶段）、TTFT（首 Token 时延）、TPOT（单 Token 生成时延）等常用工程术语，首次出现时给出中文解释，后文沿用英文名称。采用 PD 分离时，Decode 容器必须能够访问 RDMA 设备（`--privileged`、`/dev/mem`、`CAP_SYS_ADMIN`）；否则 Mooncake 会回退到 TCP，高并发吞吐数据无效。

> 作者：魏新宇（Xinyu Wei）— Microsoft AI and Apps Global Black Belt（GBB）
>
> 最后验证时间：2026-07-21

[English](README.md) | 中文 | [验证证据](data/validation/)

## 执行摘要

> **Prefill（预填充阶段）：** 在 64K 输入、客户端并发 4 的条件下，MI300X 达到 **18,983.91 input tok/s**。客户提供的 H200 饱和吞吐参考为 **27,400 input tok/s**，但对应的 H200 工作簿未记录客户端并发，因此这里只能作为方向性参考。
>
> **Decode（解码阶段）：** 在 AMD 7/13 环境的最终 AITER/CK 路径下，**单节点非 PD、精确 64K 输入、固定 BS16**的 fixed acceptance（固定接受率）性能测试达到 **933.75 scheduler gen tok/s**。该值取自两次 fresh-service run（每次重启服务后的独立测试）：**931.58 / 935.92 tok/s**，两次结果相差 **0.47%**；折算得到的 TPOT（单 Token 生成时延）为 **17.14 ms**。
>
> **结论边界：** 与 H200 工作簿的 64K BS16 行相比，该结果的相对值为 **70.0%**；与同一镜像下精确长度的 no-CK 基线相比，吞吐提高 **25.7%**。该测量不属于 1P1D PD c16 测试，不验证自然 MTP 接受率，也不验证输出质量。该工作簿没有逐行记录输出长度，J 列的部署范围定义也不明确；双方的部署拓扑、专家路由、接受率方法和指标口径均不相同。BS32–96 仍需 EP 或多节点 Decode 部署，当前不计算硬件比率。

> **ISL=8K 覆盖范围：** 下方独立章节包含 Prefill c1/2/4/8、PD Decode c8/16/32/64/96/128/192，以及 Decode c16/c32/c64/c128 的 N=2 Fresh-Service 复测。
>
> **ISL=64K 覆盖范围：** 下方独立章节包含 Prefill c1/2/4/8、PD Decode c16/32/64/96（实测 Decode batch 4–5），以及 N=2 的单节点固定 BS16 固定接受率记录。
>
> **ISL=128K 覆盖范围：** 下方独立章节包含 Prefill c1/2/4/8、PD Decode c4/8/16/32，以及 Decode c4 的 N=2 Fresh-Service 复测。所有矩阵测点均通过请求数、Token 账目和 fatal log 验收门。
>
> **ISL=192K 覆盖范围：** 下方独立章节包含 Prefill c1/2/4/8、PD Decode c2/4/8/16，以及 Decode c4 的 N=2 Fresh-Service 复测。所有矩阵测点均通过请求数、Token 账目和 fatal log 验收门。
>
> **ISL=256K 覆盖范围：** 下方独立章节将精确输入 Prefill c1/c2 列为有效测点，c4 列为 `REJECTED_BOUNDARY`；255K 输入/1K 输出的 PD Decode 矩阵覆盖 c1/c2/c4，并对 c1 进行了 N=2 Fresh-Service 复测。根据本轮指令，DP=2 不在测量范围内。

### 核心指标对比

| ISL | Prefill 完整矩阵（峰值） | Prefill vs H200（选定记录） | PD Decode 完整矩阵（E2E；实测 batch） | Decode vs H200 | Fresh-Service N=2 差异 |
|---|---:|---:|---|---|---:|
| 8K | 21,004.97 tok/s（c8） | 20,305.98 vs 31,950 = 63.6% | 930.00–2,500.54 tok/s；已审计 batch 15–55 | PD c16 已审计：1,319.78 vs 1,381 = 95.6%；TPOT 10.83 vs 11.59 ms（低 6.6%） | 最大 2.14%（c16–c128） |
| 64K | 19,860.45 tok/s（c2） | 18,983.91 vs 27,400 = 69.3% | 265.17–288.66 tok/s；实测 batch 4–5 | PD c16 为 20.1%（batch 未对齐）；单节点非 PD BS16 引擎潜力 933.75 vs 1,333.89 = 70.0%（非生产部署），TPOT 17.14 vs 11.99 ms（高 42.9%） | 0.27%（单节点 BS16） |
| 128K | 16,711.96 tok/s（c2） | —（无 H200 参考） | 112.79–122.32 tok/s；batch 1 / 1 | —（无 H200 参考） | 0.24%（c4） |
| 192K | 14,402.00 tok/s（c4） | —（无 H200 参考） | 63.30–71.34 tok/s；batch 1 / 1 | —（无 H200 参考） | 0.47%（c4） |
| 256K | 12,725.25 tok/s（c2 精确；c4 `REJECTED_BOUNDARY`） | 12,864.96 vs 17,400 = 73.9%（独立 N=1） | 36.04–162.63 tok/s（255K/1K）；batch 1 / 1 | —（无 H200 参考） | 0.03%（c1） |

吞吐单元格单位为 tok/s（越高越好），TPOT 单位为 ms（越低越好）。“—”表示客户工作簿在该 ISL 没有对应行。所有 H200 百分比仍是工作簿对应行的方向性比值；下方每个 ISL 章节都自带完整矩阵和专门的 vs H200 小节。

**结论：** 已实测的 Prefill 吞吐均未超过 H200 参考值，两个 Decode 吞吐测点亦未超过。仅 MI300X 的 **8K Decode TPOT** 较低，差异为 **6.6%**。64K Decode 验证了精确输入长度和固定接受率下的 scheduler 容量；与同一镜像下的 MI300X 基线相比，吞吐提高 **25.7%**，但仍未达到 H200 工作簿对应行，也不验证输出质量。

这里必须强调“方向性”：H200 工作簿未记录 input concurrency（输入并发）；Decode 各行未注明 output length（输出长度），J 列的部署范围定义也不明确；双方的 topology（部署拓扑）、expert routing（专家路由）、acceptance method（接受率方法）和 metric scope（指标口径）均不一致。因此，所有相对 H200 的百分比只表示工作簿对应行的算术相对值，不能作为严格的硬件排名。

**客户数据分享边界：** 本仓库不分发客户提供的原始工作簿。仓库只摘录部分数值用于方向性比较，但没有记录这些摘录已获准对外分享的证据。再次对外分发前，仓库维护者必须确认相应授权。

**TPOT 指标口径：** 8K 数据取自 1P1D c16 测试的客户端平均 TPOT；64K 数据根据单节点固定 BS 的 scheduler 吞吐，按 `1000 / (mean gen tok/s ÷ BS16)` 计算得到。两项指标回答的问题不同，不能据此绘制受控的 8K→64K TPOT 曲线。受控的长度变化应以下方明确标注的输出 8K 诊断为准，其中两点采用相同方法。

**实测长度变化锚点（仅限同方法可比的变化）：**

- 同一完整矩阵，Prefill c4，输入从 8K 增至 64K：18,161.81 → 18,763.17 tok/s（**提升 3.3%**）。**受控矩阵中，Prefill 吞吐到 64K 仍基本持平。** 这是目前有数据支撑的长度扩展结论。
- 同一完整矩阵，Prefill c4，输入从 64K 增至名义 256K：18,763.17 → 12,389.64 tok/s（**下降 34.0%**）。**接近 256K 时，长输入带来的性能损失开始明显。** 该测点采用随机文本构造，长度按名义值统计。
- 独立的精确 256K Prefill 确认：12,864.96 tok/s，16/16 条请求，**测量次数 N=1**。**已确认精确 262,144 个 Token 的 Prefill 能力**，但该记录不属于受控长度曲线。
- Decode 诊断：采用相同的固定 BS16、输出 8K 方法，context 从 8K 增至 64K：1,031.26 → 718.12 gen tok/s（**下降 30.4%**），15.52 → 22.28 ms（**增加 43.6%**）。**Decode 对长 context 比 Prefill 更敏感。** 这组输出 8K 数据只用于长度扩展诊断，不用于 H200 核心对比。
- 精确 64K/1K Decode，no-CK → AMD 7/13 最终路径：743.12 → 933.75 gen tok/s（**提升 25.7%**），21.53 → 17.14 ms（**降低 20.4%**）。

No-CK 与优化路径 A/B 测试的原始样本分别记录在 [`data/validation/decode-fixed-batch-audit.json`](data/validation/decode-fixed-batch-audit.json) 的 `headline_exact.same_image_exact_no_ck` 和 `headline_exact.points` 字段中；脱敏采样窗口公开在 [`data/evidence/exact64-fixed-acceptance/`](data/evidence/exact64-fixed-acceptance/)，运行 `python3 scripts/analyze_exact64_evidence.py` 可校验 manifest（哈希清单）并重算两组汇总值和提升幅度，但不能单独证明私有完整日志的来源与完整性。

**证据范围：** 所有通过验收的测点均通过请求数、Token 账目和 fatal log 验收门。N=2 Fresh-Service 复测覆盖 8K c16/c32/c64/c128、64K 单节点固定 BS16 记录、128K c4、192K c4 和 256K c1；其余矩阵测点均为 N=1，256K Prefill c4 保留为 `REJECTED_BOUNDARY`。当前证据支持**“长 ISL 性能测量结果可信”**，但不能据此宣称**“达到 H200 同等性能”**、**“输出质量已经验证”**或自然 MTP 接受率已经验证。

---

## 架构

![双节点 MI300X 1P1D Prefill-Decode 架构](images/pd_architecture.png)

*图 1：最终双节点 MI300X 1P1D 拓扑、Mooncake KV transfer 路径与已验证运行时栈。*

---

## 扩展性与长上下文测试

AMD 提供基础启动方案（容器镜像、AITER 调优路径、1P1D/DP=2 拓扑和 benchmark 入口），微软完成复现后联合扩展上下文长度与并发覆盖，并加入 fail-closed 正确性校验。**以下 MI300X 数据取自该联合运行环境；H200 数据为客户提供的参考值（`h200-reference.json`）。**

### 测试矩阵

| 测试类型 | 工作负载 | 并发设置 | 每个测点的请求数 |
|---|---|---|---:|
| 1P1D Decode | 8K 输入 / 1K 输出 | 8, 16, 32, 64, 96, 128, 192 | 256 |
| 1P1D 长上下文 Decode | 请求 64K 输入 / 1K 输出；请求 255K 输入 / 1K 输出（总序列 256K） | 64K：16, 32, 64, 96；255K：1 | 32, 64, 128, 192；1 |
| 单节点精确固定 batch Decode | 精确 64K 输入 / 1K 输出、固定 batch 16；最终 AITER/CK 路径 | 两次全新服务复测 | 每轮 16 |
| 单节点受控 ISL=128K Decode | 128K 输入 / 1K 输出、实际 batch 4；最终 AITER/CK 路径 | 一次通过验收的测量 | 4 |
| 单节点受控 ISL=192K Decode | 192K 输入 / 1K 输出、实际 batch 4；最终 AITER/CK 路径 | 一次通过验收的测量 | 4 |
| 单节点诊断性固定 batch Decode | 64K 或 8K 输入 / 8K 输出；只用于内部长度变化诊断 | 单次服务启动，固定 batch 4/8/16 | 不用于 H200 核心对比 |
| 1P1D Prefill | 8K、64K、名义 256K / 输出 1 | 1, 2, 4, 8 | 16 |
| 1P1D ISL=128K Prefill 选定测点 | 128K 输入 / 输出 1 | 客户端并发 4；一次通过验收的测量 | 16 |
| 1P1D ISL=192K Prefill 选定测点 | 192K 输入 / 输出 1 | 客户端并发 4；一次通过验收的测量 | 16 |
| 1P1D ISL=64K 汇总矩阵 | 64K 输入 / 输出 1；64K 输入 / 1K 输出 | Prefill：1, 2, 4, 8；Decode：16, 32, 64, 96 | Prefill：16；Decode：并发 × 2；Fresh 固定 BS16 单节点：N=2 |
| 1P1D ISL=128K 完整矩阵 | 128K 输入 / 输出 1；128K 输入 / 1K 输出 | Prefill：1, 2, 4, 8；Decode：4, 8, 16, 32 | Prefill：16；Decode：并发 × 2；Fresh Decode c4：N=2 |
| 1P1D ISL=192K 完整矩阵 | 192K 输入 / 输出 1；192K 输入 / 1K 输出 | Prefill：1, 2, 4, 8；Decode：2, 4, 8, 16 | Prefill：16；Decode：并发 × 2；Fresh Decode c4：N=2 |
| 1P1D ISL=256K 完整矩阵 | 精确 256K 输入 / 输出 1；255K 输入 / 1K 输出 | Prefill：1, 2, 4；Decode：1, 2, 4 | Prefill：16；Decode：并发 × 2；Fresh Decode c1：N=2 |
| 双节点 DP=2 Prefill | 8K、64K、名义 256K / 输出 1 | 8K/64K：1, 2, 4, 8, 16；名义 256K：1, 2, 4, 8 | 32 |

以下表格展示实测扩展性结果。Decode 核心生产并发测点还单独做了两次全新服务复测。

### ISL=8K

<details open>
<summary><b>ISL=8K —— 完整矩阵（Prefill / Decode / Fresh-Service）</b></summary>

#### 1P1D Prefill 扩展性：8K 输入 / 输出 1

| 输入长度 | 客户端并发 | 状态 | Input tok/s | 平均 TTFT (ms) | P95 TTFT (ms) |
|---:|---:|---|---:|---:|---:|
| 8K | 1 | VALIDATED | 16,835.22 | 485.70 | — |
| 8K | 2 | VALIDATED | 19,618.25 | 829.40 | — |
| 8K | 4 | VALIDATED | 18,161.81 | 1,612.03 | — |
| 8K | 8 | VALIDATED | 21,004.97 | 2,817.91 | — |

实测现象：

- Input 吞吐在客户端并发 8 时达到峰值 **21,004.97 tok/s**。
- 平均 TTFT 从客户端并发 1 时的 **485.70 ms** 增至并发 8 时的 **2,817.91 ms**。

#### 1P1D Decode 扩展性：8K 输入 / 1K 输出

| 客户端并发 | 实测 Decode batch | Scheduler gen tok/s | E2E Output tok/s | 平均 TPOT (ms) | 平均 TTFT (ms) | H200 参考 |
|---:|---:|---:|---:|---:|---:|---:|
| 8 | — | — | 930.00 | 7.65 | 863.69 | — |
| 16 | — | — | 1,303.44 | 10.72 | 1,398.73 | 1,381 tok/s / 11.59 ms |
| 32 | — | — | 1,930.10 | 13.68 | 2,296.89 | 2,549 tok/s / 12.56 ms |
| 64 | — | — | 2,462.83 | 17.08 | 7,406.18 | 4,483 tok/s / 14.28 ms |
| 96 | — | — | 2,497.69 | 15.89 | 18,273.38 | — |
| 128 | — | — | 2,468.95 | 16.45 | 27,128.38 | 7,013 tok/s / 18.25 ms |
| 192 | — | — | 2,500.54 | 15.98 | 40,956.57 | — |

实测现象：

- 客户端并发从 8 增至 64 时，吞吐由 930.00 tok/s 提高到 2,462.83 tok/s；此后直到并发 192，吞吐均维持在约 2.47–2.50K tok/s。
- 上表 E2E 行没有与同一次运行匹配的 scheduler window，因此实际 batch 与 scheduler gen 单元格保留为 `—`。另外完成审计的 c16/c32/c64/c128 headline 记录中，实测 Decode batch 分别为 15/16、31/32、53/55 和 51/54；本文不会把这些数值回填到不同运行的结果行。
- 并发超过 64 后，吞吐基本不再增长，但 TTFT 明显上升。这是容量平台，不表示延迟得到改善。

#### 8K Decode Fresh-Service（全新服务）复测

| 客户端并发 | 实测 Decode batch | 第 1 轮 Output tok/s | 第 2 轮 Output tok/s | 吞吐差异 | TPOT 第 1 轮 / 第 2 轮 (ms) |
|---:|---:|---:|---:|---:|---:|
| 16 | — | 1,331.98 | 1,303.44 | -2.14% | 10.83 / 10.72 |
| 32 | — | 1,936.24 | 1,930.10 | -0.32% | 13.65 / 13.68 |
| 64 | — | 2,457.73 | 2,462.83 | +0.21% | 17.00 / 17.08 |
| 128 | — | 2,486.89 | 2,468.95 | -0.72% | 16.56 / 16.45 |

四个复测点在两次全新服务运行之间的最大吞吐绝对差异为 **2.14%**。实际 batch 保留为 `—`，因为所有行都没有同时覆盖两轮 Fresh-Service 的配对 scheduler 审计。

机器可读证据：[Prefill 与 Decode](data/scalability-results.tsv)、[Fresh-Service](data/decode-repeatability.tsv)和[scheduler 审计](data/validation/decode-service-log-audit-8k.json)。

#### 8K vs H200 参考

选定 Prefill 记录（与上方完整矩阵分属不同运行，独立 N=1）：

| 上下文 | 客户端并发 | MI300X 实测 input tok/s | 小米 H200 TP8/EP16/DP2 单节点参考 | MI300X / H200 单节点 |
|---:|---:|---:|---:|---:|
| 8K | 4 | **20,305.98** | 31,950 | 63.6% |

已审计的 Decode headline 记录与客户工作簿对比：

| 客户端并发 | 实测 Decode batch | MI300X gen tok/s | MI300X TPOT (ms) | H200 参考 | MI300X / H200 |
|---:|---:|---:|---:|---:|---:|
| 16 | 15 / 16 | **1,319.78** | **10.83** | 1,381 tok/s / 11.59 ms | **95.6%** 吞吐；TPOT **低 6.6%** |
| 32 | 31 / 32 | 1,861.52 | 13.65 | 2,549 tok/s / 12.56 ms | 73.0% |
| 64 | 53 / 55 | 2,324.57 | 16.88 | 4,483 tok/s / 14.28 ms（H200 BS64） | 51.9% — MI300X 实测 BS53 vs H200 BS64 |
| 128 | 51 / 54 | 2,333.44 | 16.56 | 7,013 tok/s / 18.25 ms（H200 BS128） | 33.3% — MI300X 实测 BS51 vs H200 BS128 |

`15 / 16` 表示稳态 15、峰值 16。c64/c128 时 MI300X Decode 节点因 KV 容量饱和在 batch ~50–55，无法与 H200 BS64/BS128 配对；只有 **c16 行**（batch 15–16 vs H200 BS16）是近似对齐的对比——**1,319.78 tok/s**，相当于 H200 BS16 工作簿行的 **95.6%**，同时 MI300X TPOT **低 6.6%**（10.83 vs 11.59 ms）。这些已审计记录来自独立的 headline 运行，不回填到上方 E2E 矩阵。batch 审计：[`data/validation/decode-service-log-audit-8k.json`](data/validation/decode-service-log-audit-8k.json)。

</details>

### ISL=64K

<details open>
<summary><b>ISL=64K —— 完整矩阵（Prefill / Decode / Fresh-Service）</b></summary>

#### 1P1D Prefill 扩展性：64K 输入 / 输出 1

| 输入长度 | 客户端并发 | 状态 | Input tok/s | 平均 TTFT (ms) | P95 TTFT (ms) |
|---:|---:|---|---:|---:|---:|
| 64K | 1 | VALIDATED | 18,057.01 | 3,628.49 | — |
| 64K | 2 | VALIDATED | 19,860.45 | 6,481.41 | — |
| 64K | 4 | VALIDATED | 18,763.17 | 12,970.83 | — |
| 64K | 8 | VALIDATED | 18,765.43 | 22,530.68 | — |

实测现象：

- Input 吞吐在客户端并发 2 时达到峰值 **19,860.45 tok/s**；并发 4–8 时保持在 **18,763.17**–**18,765.43 tok/s** 之间。
- 平均 TTFT 从并发 1 时的 **3,628.49 ms** 增至并发 8 时的 **22,530.68 ms**。

#### 1P1D Decode 扩展性：64K 输入 / 1K 输出

| 客户端并发 | 实测 Decode batch | Scheduler gen tok/s | E2E Output tok/s | 平均 TPOT (ms) | 平均 TTFT (ms) | H200 参考 |
|---:|---:|---:|---:|---:|---:|---:|
| 16 | 4 / 5 | 267.97 | 265.17 | 11.94 | 37,571.24 | 1,333.89 tok/s / 11.99 ms (BS16) = 20.1%，batch 未对齐 |
| 32 | 4 / 4 | 276.74 | 276.59 | 11.76 | 80,228.37 | 2,235.53 tok/s / 14.31 ms (BS32) = 12.4%，batch 未对齐 |
| 64 | 4 / 5 | 282.81 | 284.00 | 11.75 | 165,190.68 | 3,919.78 tok/s / 16.33 ms (BS64) = 7.2%，batch 未对齐 |
| 96 | 4 / 5 | 287.77 | 288.66 | 11.55 | 248,339.44 | 4,891.59 tok/s / 19.63 ms (BS96) = 5.9%，batch 未对齐 |

实测现象：

- 64K 上下文的 KV 占用把实测 Decode batch 限制在 4–5，客户端并发 16–96 无法提高活跃 batch。
- 客户端并发从 16 增至 96 时，E2E Output 吞吐仅提高 **8.9%**，平均 TTFT 则从 **37,571.24 ms** 增至 **248,339.44 ms**。
- 上表 H200 参考行对应 BS16–96，而 MI300X 实测 batch 只有 4–5，因此这些比值并非 batch 对齐比较；batch 对齐的 BS16 视角见下方固定 batch 记录。

#### 64K Decode Fresh-Service（全新服务）复测

| 客户端并发 | 实测 Decode batch | 第 1 轮 Output tok/s | 第 2 轮 Output tok/s | 吞吐差异 | TPOT 第 1 轮 / 第 2 轮 (ms) |
|---:|---:|---:|---:|---:|---:|
| 16 | 16 / 16 | 224.26 | 223.66 | -0.27% | 42.63 / 42.67 |

两轮全新服务测试的客户端 E2E Output 吞吐相差 **0.27%**。该 N=2 记录来自单节点、非 PD、精确 64K、固定 BS16、固定接受率测试，不是 PD 部署测点；其稳态 scheduler 生成吞吐为 931.58 / 935.92 tok/s，按 BS16 折算 TPOT 为 17.14 ms。上方 PD 模式的 64K 矩阵测点均只有一次通过验收的测量。

机器可读证据：[Prefill](data/scalability-results.tsv)、[Decode](data/decode-long-context-results.tsv)、[Fresh-Service](data/decode-fixed-batch-results.tsv)和[scheduler 审计](data/validation/decode-service-log-audit.json)。

#### 64K vs H200 参考

选定 Prefill 记录（独立 N=1 运行）：

| 上下文 | 客户端并发 | MI300X 实测 input tok/s | 小米 H200 TP8/EP16/DP2 单节点参考 | MI300X / H200 单节点 |
|---:|---:|---:|---:|---:|
| 64K | 4 | **18,983.91** | 27,400 | 69.3% |

Decode：上方 PD 矩阵的实测 batch 为 4–5，而 H200 工作簿行为 BS16–96，因此 PD 比值（c16 的 20.1% 降至 c96 的 5.9%）并非 batch 对齐；详见下方“64K Decode — PD 模式（实测 BS4–5）”。batch 对齐的视角是单节点固定 BS16 引擎潜力记录：**933.75 vs 1,333.89 gen tok/s = 70.0%（非生产部署）**，折算 TPOT **17.14 vs 11.99 ms（高 42.9%）**；详见下方“64K Decode 引擎潜力验证”。

</details>

### ISL=128K

<details open>
<summary><b>ISL=128K —— 完整矩阵（Prefill / Decode / Fresh-Service）</b></summary>

#### 1P1D Prefill 扩展性：128K 输入 / 输出 1

| 输入长度 | 客户端并发 | 状态 | Input tok/s | 平均 TTFT (ms) | P95 TTFT (ms) |
|---:|---:|---|---:|---:|---:|
| 128K | 1 | VALIDATED | 16,389.66 | 7,995.96 | 8,387.76 |
| 128K | 2 | VALIDATED | 16,711.96 | 15,280.91 | 16,227.41 |
| 128K | 4 | VALIDATED | 16,667.06 | 28,777.69 | 31,952.15 |
| 128K | 8 | VALIDATED | 16,641.77 | 49,817.65 | 63,576.07 |

实测现象：

- 客户端并发从 1 增至 8 时，Input 吞吐的波动范围不超过 **2.0%**；峰值为并发 2 时的 **16,711.96 tok/s**。
- 平均 TTFT 从并发 1 时的 **7,995.96 ms** 增至并发 8 时的 **49,817.65 ms**。提高客户端并发只增加等待时间，没有提高 Prefill 吞吐。
- 所有观测样本中的 Prefill scheduler 均只接收一条新序列；本文不会把客户端并发写成 Prefill 实际 batch。

#### 1P1D Decode 扩展性：128K 输入 / 1K 输出

| 客户端并发 | 实测 Decode batch | Scheduler gen tok/s | E2E Output tok/s | 平均 TPOT (ms) | 平均 TTFT (ms) | H200 参考 |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 1 / 1 | 140.72 | 112.79 | 5.76 | 24,639.84 | — |
| 8 | 1 / 1 | 137.62 | 117.32 | 5.76 | 49,712.45 | — |
| 16 | 1 / 1 | 138.85 | 121.64 | 5.81 | 98,633.02 | — |
| 32 | 1 / 1 | 138.20 | 122.32 | 5.80 | 198,594.63 | — |

实测现象：

- 所有测点的 Decode 实际 batch 常见值均为 1、峰值均为 1。128K 矩阵中，Decode scheduler 从未达到客户端设置的并发值。
- 客户端并发从 4 增至 32 时，E2E Output 吞吐仅提高 **8.4%**，平均 TTFT 则从 **24,639.84 ms** 增至 **198,594.63 ms**。
- 在实测 batch 下，scheduler 生成吞吐稳定在约 **138–141 tok/s**。继续提高客户端并发主要增加 Decode 前的等待，不会形成更大的实际 Decode batch。

#### 128K Decode Fresh-Service（全新服务）复测

| 客户端并发 | 实测 Decode batch | 第 1 轮 Output tok/s | 第 2 轮 Output tok/s | 吞吐差异 | TPOT 第 1 轮 / 第 2 轮 (ms) |
|---:|---:|---:|---:|---:|---:|
| 4 | 1 / 1 | 113.64 | 113.37 | -0.24% | 5.84 / 5.86 |

两轮全新服务测试的 E2E Output 吞吐相差 **0.24%**。该复测只覆盖客户端并发 4；128K 矩阵中的其他测点均只有一次通过验收的测量。

机器可读证据：[Prefill](data/long-isl/128k/prefill-results.tsv)、[Decode](data/long-isl/128k/decode-results.tsv)和[Fresh-Service](data/long-isl/128k/decode-repeatability.tsv)。

#### 128K vs H200 参考

客户 H200 工作簿没有 128K 行，该 ISL 不存在 H200 参考。上方 128K Prefill 与 Decode 矩阵作为 MI300X 独立证据单独成立；所有通过验收的测点实测 Decode batch 均保持 1 / 1。

</details>

### ISL=192K

<details open>
<summary><b>ISL=192K —— 完整矩阵（Prefill / Decode / Fresh-Service）</b></summary>

#### 1P1D Prefill 扩展性：192K 输入 / 输出 1

| 输入长度 | 客户端并发 | 状态 | Input tok/s | 平均 TTFT (ms) | P95 TTFT (ms) |
|---:|---:|---|---:|---:|---:|
| 192K | 1 | VALIDATED | 13,827.37 | 14,217.14 | 14,906.98 |
| 192K | 2 | VALIDATED | 14,401.79 | 26,537.49 | 27,911.73 |
| 192K | 4 | VALIDATED | 14,402.00 | 49,755.39 | 55,124.70 |
| 192K | 8 | VALIDATED | 14,395.10 | 85,961.99 | 109,824.77 |

实测现象：

- 客户端并发从 1 增至 8 时，Input 吞吐的波动范围不超过 **4.2%**；峰值为并发 4 时的 **14,402.00 tok/s**。
- 平均 TTFT 从并发 1 时的 **14,217.14 ms** 增至并发 8 时的 **85,961.99 ms**。提高客户端并发没有提高持续 Prefill 吞吐。
- 所有观测样本中的 Prefill scheduler 均只接收一条新序列；本文不会把客户端并发写成 Prefill 实际 batch。

#### 1P1D Decode 扩展性：192K 输入 / 1K 输出

| 客户端并发 | 实测 Decode batch | Scheduler gen tok/s | E2E Output tok/s | 平均 TPOT (ms) | 平均 TTFT (ms) | H200 参考 |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 1 / 1 | 129.42 | 63.30 | 6.34 | 22,617.83 | — |
| 4 | 1 / 1 | 126.99 | 68.15 | 6.46 | 43,550.54 | — |
| 8 | 1 / 1 | 126.14 | 70.12 | 6.48 | 86,300.12 | — |
| 16 | 1 / 1 | 125.04 | 71.34 | 6.19 | 171,203.13 | — |

实测现象：

- 所有测点的 Decode 实际 batch 常见值均为 1、峰值均为 1。192K 矩阵中，Decode scheduler 从未达到客户端设置的并发值。
- 客户端并发从 2 增至 16 时，E2E Output 吞吐提高 **12.7%**，平均 TTFT 则从 **22,617.83 ms** 增至 **171,203.13 ms**。
- 在实测 batch 下，scheduler 生成吞吐稳定在约 **125–129 tok/s**。E2E 聚合吞吐的提高来自完整 PD 路径上的请求重叠，不代表实际 Decode batch 增大。

#### 192K Decode Fresh-Service（全新服务）复测

| 客户端并发 | 实测 Decode batch | 第 1 轮 Output tok/s | 第 2 轮 Output tok/s | 吞吐差异 | TPOT 第 1 轮 / 第 2 轮 (ms) |
|---:|---:|---:|---:|---:|---:|
| 4 | 1 / 1 | 67.88 | 68.20 | +0.47% | 6.89 / 6.62 |

两轮全新服务测试的 E2E Output 吞吐相差 **0.47%**。该复测只覆盖客户端并发 4；192K 矩阵中的其他测点均只有一次通过验收的测量。

机器可读证据：[Prefill](data/long-isl/192k/prefill-results.tsv)、[Decode](data/long-isl/192k/decode-results.tsv)和[Fresh-Service](data/long-isl/192k/decode-repeatability.tsv)。

#### 192K vs H200 参考

客户 H200 工作簿没有 192K 行，该 ISL 不存在 H200 参考。上方 192K Prefill 与 Decode 矩阵作为 MI300X 独立证据单独成立；所有通过验收的测点实测 Decode batch 均保持 1 / 1。

</details>

### ISL=256K

<details open>
<summary><b>ISL=256K —— 完整矩阵（Prefill / Decode / Fresh-Service）</b></summary>

#### 1P1D Prefill 扩展性：精确 256K 输入 / 输出 1

| 输入长度 | 客户端并发 | 状态 | Input tok/s | 平均 TTFT (ms) | P95 TTFT (ms) |
|---:|---:|---|---:|---:|---:|
| 精确 256K | 1 | VALIDATED | 12,631.60 | 20,751.02 | 21,048.17 |
| 精确 256K | 2 | VALIDATED | 12,725.25 | 40,002.62 | 41,913.75 |
| 精确 256K | 4 | `REJECTED_BOUNDARY` | — | — | — |

实测现象：

- 两个通过验收的测点都为每条请求精确发送 262,144 个 input token IDs。客户端并发 1 与 2 的 Input 吞吐相差 **0.7%**，平均 TTFT 则接近翻倍。
- 客户端并发 4 已执行多次，但每次都只有部分请求完成。两个独立服务生命周期均记录到 AMDGPU page fault 和 worker 异常退出，随后 Router 才出现错误。该测点保留为 `REJECTED_BOUNDARY`，不把部分完成的吞吐写成有效结果。
- 早期独立完成的精确 256K c4 headline 仍作为另一条 N=1 记录保留，但不能用于回填本次被拒绝的完整矩阵行，也不能证明当前 c4 具有重复性。
- 客户端并发 2 的 canonical client 结果通过了请求数和精确 Token 验收门；补充 scheduler trace 只用于诊断，不作为性能结果。

#### 1P1D Decode 扩展性：255K 输入 / 1K 输出

| 客户端并发 | 实测 Decode batch | Scheduler gen tok/s | E2E Output tok/s | 平均 TPOT (ms) | 平均 TTFT (ms) | H200 参考 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 / 1 | 131.15 | 36.04 | 7.16 | 21,076.57 | — |
| 2 | 1 / 1 | 127.64 | 82.19 | 3.61 | 16,441.84 | — |
| 4 | 1 / 1 | 127.84 | 162.63 | 2.65 | 8,351.65 | — |

实测现象：

- 所有测点的 Decode 实际 batch 常见值均为 1、峰值均为 1。Decode scheduler 从未达到客户端设置的并发 2 或 4。
- 在实测 batch 下，scheduler 生成吞吐稳定在约 **128–131 tok/s**。客户端并发提高后的 E2E 聚合吞吐来自完整 PD 路径上的请求重叠，不代表实际 Decode batch 增大。
- 每条请求发送 261,120 个 input tokens，并请求生成 1,024 个 output tokens，总序列长度为 262,144 个 Token。这是 256K 总序列测试，不是 256K 输入的 Decode 测试。

#### 256K Decode Fresh-Service（全新服务）复测

| 客户端并发 | 实测 Decode batch | 第 1 轮 Output tok/s | 第 2 轮 Output tok/s | 吞吐差异 | TPOT 第 1 轮 / 第 2 轮 (ms) |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 / 1 | 35.97 | 35.96 | -0.03% | 7.15 / 7.21 |

两轮全新服务测试的 E2E Output 吞吐相差 **0.03%**。该复测只覆盖客户端并发 1；客户端并发 2 和 4 的 Decode 测点均只有一次通过验收的测量。

机器可读证据：[Prefill](data/long-isl/256k/prefill-results.tsv)、[Decode](data/long-isl/256k/decode-results.tsv)和[Fresh-Service](data/long-isl/256k/decode-repeatability.tsv)。

#### 256K vs H200 参考

选定 exact-token Prefill 记录（独立 N=1 运行；上方 c1/c2 矩阵行是本轮矩阵证据）：

| 上下文 | 客户端并发 | MI300X 实测 input tok/s | 小米 H200 TP8/EP16/DP2 单节点参考 | MI300X / H200 单节点 |
|---:|---:|---:|---:|---:|
| 256K | 4 | **12,864.96** | 17,400 | 73.9% |

Decode：工作簿没有 255K 输入/1K 输出行，该 ISL 不存在 H200 Decode 参考。

</details>

### 指标口径

Input（输入侧）与 Output（输出侧）指标回答的问题不同，不能互相相除或直接比较。

| 侧别 | 指标 | 准确定义 |
|---|---|---|
| Input | Input tok/s | 每秒处理的聚合 input tokens；越高越好 |
| Input | Input/client concurrency | benchmark client（压测客户端）允许的最大并发请求数；不一定等于 Decode 实际 batch |
| Output | E2E output tok/s | 请求的 output tokens 除以完整测试时长，其中包含 Prefill 和 TTFT |
| Output | Decode-node gen tok/s | 该测点期间 Decode scheduler 日志中 `gen throughput` 样本的算术平均值 |
| Output | TTFT | 从请求开始到首个 output token 的时间；越低越好 |
| Output | TPOT | 首个 Token 之后每个 output token 的时间；越低越好 |

`TPUT` 只是 throughput 的缩写，通常以 tokens/s 表示，不是另一种独立指标。

### 64K Prefill

| 字段 | 微软实测 MI300X | 客户 H200 参考 | 对齐状态 |
|---|---:|---:|---|
| 工作负载 | 64K 输入 / 输出 1 | 64K 输入 / 输出 1 | 已对齐 |
| 输入/客户端并发 | 4 | 源工作簿未记录 | 未完全对齐 |
| 报告口径 | 单个 MI300X Prefill 节点 | 单节点饱和吞吐参考 | 方向性 |
| Input tok/s | 18,983.91 | 27,400 | MI300X 为 H200 参考的 69.3% |

这不是严格的硬件对比，因为 H200 未记录 input concurrency，而且 routing 方式不同。MI300X 使用真实 expert routing；H200 参考使用 balanced `fake_topk_ids`、TP8/EP16/DP2，并关闭 radix cache。

### 64K Decode — PD 模式（实测 BS4–5）

| 客户端并发 | MI300X 实测 Decode BS | MI300X gen tok/s | MI300X TPOT (ms) | H200 参考（per-DP BS） | MI300X / H200 |
|---:|---:|---:|---:|---:|---:|
| 16 | **4–5** | 267.97 | 11.94 | 1,333.89 tok/s（H200 BS16） | 20.1% — MI300X BS4 vs H200 BS16 |
| 32 | **4** | 276.74 | 11.76 | 2,235.53 tok/s（H200 BS32） | 12.4% — MI300X BS4 vs H200 BS32 |
| 64 | **4–5** | 282.81 | 11.75 | 3,919.78 tok/s（H200 BS64） | 7.2% — MI300X BS4 vs H200 BS64 |
| 96 | **4–5** | 287.77 | 11.55 | 4,891.59 tok/s（H200 BS96） | 5.9% — MI300X BS4 vs H200 BS96 |

**比率极低的原因：** 64K 的 KV 占用使 MI300X 实测 Decode batch 只有 4–5，而 H200 各行是 BS16–96。这些数字**不是硬件对比**，只说明需要对齐 batch 才有意义。下方精确固定 batch 测试（双方都是 BS16）给出对齐后的 70.0% 方向性结果。

机器可读审计：[`data/validation/decode-service-log-audit.json`](data/validation/decode-service-log-audit.json)。

### 64K Decode 引擎潜力验证 — 单节点固定 BS16（非生产部署）

> **定位：** 这是 Decode 引擎能力测试，不是生产 PD 部署结果。MI300X 使用 1 节点 / 8 卡（TP8）；H200 参考使用 4 节点 / 32 卡（TP8/EP32/DP4）。上方 PD 模式的实测结果（BS4–5）才是客户生产环境的真实参考。

该测试在单个 MI300X 节点上运行（TP8，不采用 PD 分离），工作负载为精确 64K 输入 / 服务端计数的 1K 输出，使用基于 AMD 7/13 tuned-MoE 环境生成的不可变镜像 `20260713-final`。这是 fixed-acceptance performance benchmark（固定接受率性能测试）：`SGLANG_SIMULATE_ACC_LEN=3` 与 `match-expected` 将 speculative acceptance length（投机接受长度）固定下来，以便比较性能；该方法不验证自然 MTP 接受率或输出质量。将 `--mem-fraction-static` 提高到 0.95 后，full-attention KV pool（全注意力 KV 池）从 554,880 扩大到 1,442,464 个 Token，使 16 条 64K context 请求能够同时进入 Decode。最终路径显式启用 `SGLANG_AITER_UNIFIED_VERIFY=1` 和 `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1`；两轮服务日志均包含 `module_gemm_a8w8_blockscale_bpreshuffle` marker（标记）。

| 精确工作负载 | 固定 BS | 两轮服务重启后的 gen tok/s | 平均 gen tok/s | 两轮差异 | 折算 TPOT | H200 工作簿行 | 方向性比率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 64K input / 1K server-accounted output | 16 | 931.58 / 935.92 | **933.75** | **0.47%** | **17.14 ms** | 1,333.89 tok/s，11.99 ms | **70.0% 对应行相对值** |

每轮均完成 16 条请求，并精确记录 1,048,576 total input tokens（总输入 Token）、16,384 server-accounted generated tokens（服务端计数的生成 Token），以及 4,112 retokenized generated-text tokens（重新分词后的生成文本 Token）。Retokenized（重新分词）指 `tokenizer.encode(generated_text)` 返回的长度，不是 accepted draft-token count（被接受的草稿 Token 数）。这是明确的方法边界，本性能测试不验证输出质量。预先设定的 transition guard（过渡样本门）只排除首个 full-batch 样本，因为该样本低于后续样本中位数的 50%；每个保留窗口包含 7 个 batch-16 样本，simulated accept length 为 3.00，scheduler-reported rate 为 0.67，queued requests（排队请求数）为 0。

**优化路径实测效果。** 在同一主机、同一运行中容器、同一不可变镜像、模型、TP8 拓扑、KV pool 设置、benchmark 命令，以及每轮重启服务的协议下，连续执行受控 A/B 测试。no-CK 两轮基线的平均吞吐为 743.12 tok/s；最终 AITER verification 与 CK blockscale-bpreshuffle 组合的平均吞吐为 **933.75 tok/s**，提升 **25.7%**。A/B 之间只改变两个组合环境变量。因此，该测试能够证明组合方案的整体收益，但不能把收益单独归因于其中某一个环境变量，也不能据此判断剩余差距来自某个特定的软件或硬件上限。

**参考边界。** 客户工作簿记录了 64K context、BS16、1,333.89 tok/s 和 11.994992 ms，但没有输出长度列。J 列标为单机吞吐，数值却等于本地 `BS × TPS`，没有乘 DP4。因此，70.0% 只表示工作簿对应行的相对值，不能作为严格对等部署或精确工作负载下的硬件排名。MI300X 使用真实 expert routing（专家路由）和固定 simulated acceptance（模拟接受率）；H200 使用 balanced `fake_topk_ids`、TP8/EP32/DP4，报告的接受率为 0.75，但没有公开可直接对齐的 acceptance method（接受率方法）。

早期 output8K fixed-batch sweep（固定批次扫描）以 `diagnostic_output8k` 保留在机器可读文件中。由于输出长度、重复次数和优化路径验证方式不同，该结果不用于 H200 核心对比。64K BS32 已超出实测单节点 KV pool；如需对齐 BS32–96，还要采用 EP 或多节点 Decode 部署。

机器可读结果：[`data/decode-fixed-batch-results.tsv`](data/decode-fixed-batch-results.tsv)；方法、运行环境身份和源文件哈希：[`data/validation/decode-fixed-batch-audit.json`](data/validation/decode-fixed-batch-audit.json)；脱敏后的原始采样窗口：[`data/evidence/exact64-fixed-acceptance/`](data/evidence/exact64-fixed-acceptance/)；公开分析脚本：[`scripts/analyze_exact64_evidence.py`](scripts/analyze_exact64_evidence.py)；复现脚本：[`scripts/amd-latest/launch_single_node_decode.sh`](scripts/amd-latest/launch_single_node_decode.sh) + [`scripts/amd-latest/benchmark_decode_fixed_batch.sh`](scripts/amd-latest/benchmark_decode_fixed_batch.sh)。

### 客户问题评估

| 客户问题 | 当前证据 | 是否适合 MI300X/H200 排名？ |
|---|---|---|
| 64K 输入容量 | MI300X 18,983.91 input tok/s；H200 27,400 input tok/s | 只能作方向性比较；H200 未记录客户端并发 |
| 64K 输出吞吐 | 精确 64K/1K、BS16、N=2：MI300X 933.75 tok/s；H200 工作簿行 1,333.89 tok/s | context 和 BS 对齐后的方向性比率为 70.0%；H200 未明确输出长度和 J 列的部署范围 |
| 输出 TTFT | MI300X 已测 | 不适合排名；H200 未提供 TTFT |
| Decode TPOT | 两份来源均提供 scheduler-derived TPOT（由 scheduler 吞吐推算的 TPOT） | BS16：17.14 vs 11.99 ms；输出长度、拓扑、路由和接受率方法仍不同 |
| Near-limit context（接近上限的上下文） | MI300X 完成请求的 255K 输入 + 1K 输出 | 只证明能力；没有匹配的 H200 工作负载 |

### 255K 能力测点

| 工作负载 | 客户端并发 | 实测 Decode batch | E2E output tok/s | Decode 节点平均 gen tok/s | 平均 TTFT (s) | 平均 TPOT (ms) |
|---|---:|---:|---:|---:|---:|---:|
| 请求 255K 输入 / 1K 输出 | 1 | 1 | 31.93 | 80.64 | 20.93 | 10.88 |

该请求实际发送 261,120 input tokens，并生成 1,024 output tokens，总序列长度为 262,144 tokens。这个测点只证明能力，不代表 256K 输入，也不表示达到 H200 同等性能。

机器可读结果：[`data/decode-long-context-results.tsv`](data/decode-long-context-results.tsv)。运行环境身份、测试方法和源文件哈希：[`data/validation/decode-long-context-evidence.json`](data/validation/decode-long-context-evidence.json)。

### 1P1D Prefill 扩展性

| 输入长度 | 客户端并发 | Input tok/s | 平均 TTFT (ms) |
|---:|---:|---:|---:|
| 8K | 1 | 16,835.22 | 485.70 |
| 8K | 2 | 19,618.25 | 829.40 |
| 8K | 4 | 18,161.81 | 1,612.03 |
| 8K | 8 | 21,004.97 | 2,817.91 |
| 64K | 1 | 18,057.01 | 3,628.49 |
| 64K | 2 | 19,860.45 | 6,481.41 |
| 64K | 4 | 18,763.17 | 12,970.83 |
| 64K | 8 | 18,765.43 | 22,530.68 |
| 名义 256K | 1 | 12,381.87 | 21,170.66 |
| 名义 256K | 2 | 12,378.06 | 41,208.61 |
| 名义 256K | 4 | 12,389.64 | 77,254.06 |
| 名义 256K | 8 | 12,402.23 | 133,251.83 |

实测现象：

- 完整矩阵中的 8K Prefill 在客户端并发 8 时达到 21,004.97 input tok/s。
- 64K Prefill 在客户端并发 2 时达到峰值，此后并发继续增加，吞吐仍保持在约 18.76K tok/s。
- 名义 256K 行采用 random-text prompt construction（随机文本 Prompt 构造，`tokenize_prompt=false`），只反映扩展趋势。核心 exact-token 结果来自独立的客户端并发 4 定向复测：**12,864.96 input tok/s**。

### 双节点 DP=2 Prefill 扩展性

峰值聚合核心记录：

| 上下文 | 客户端并发 | 聚合 input tok/s |
|---:|---:|---:|
| 8K | 16 | **46,747.01** |
| 64K | 2 | **38,984.45** |

DP=2 的 nominal-length（名义长度）256K 结果仍保留在下方完整矩阵中，但不作为 exact-token（精确 Token）核心结果。

完整矩阵：

| 输入长度 | 客户端并发 | 聚合 input tok/s | 平均 TTFT (ms) |
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
| 名义 256K | 1 | 12,783.28 | 20,505.88 |
| 名义 256K | 2 | 25,063.73 | 20,823.01 |
| 名义 256K | 4 | 24,923.63 | 40,785.01 |
| 名义 256K | 8 | 24,765.29 | 76,468.09 |

实测现象：

- DP=2 的 8K 和 64K 聚合 Prefill 吞吐在客户端并发从 1 增至 2 时接近翻倍，随后进入平台区间。
- DP=2 测量由双节点 router（路由器）分发到两个 worker（工作进程）。
- 尚未完成 DP=2 256K exact-token 复测。这些行只作为名义长度的扩展性观察，不进入核心验证表。
- DP=2 只测量 Prefill 容量，不代表 2P1D 端到端吞吐，也不测量 P→D KV-cache transfer。

### 256K 测试口径

| 证据集 | 客户端构造方式 | 用途 |
|---|---|---|
| 完整扩展矩阵 | Random-text construction（随机文本构造），`tokenize_prompt=false` | 用于扩展性和边界观察；名义 256K 不属于 exact-token 核心证据 |
| 定向 1P1D 256K 复测 | 精确 262,144 token IDs，`--tokenize-prompt` | 核心结果：12,864.96 input tok/s |
| 当前 `scripts/amd-latest/` | 所有 256K 输入的 Prefill benchmark 均使用 exact token IDs | 后续 256K 输入 Prefill 结果的强制复现路径 |
| 最终固化镜像的长上下文 Decode | Random-text framing（随机文本构造）；请求 64K 输入，以及请求 255K 输入 + 1K 输出 | 只作为 MI300X 能力和扩展性结果；不代表 256K 输入或达到 H200 同等性能 |

### 结果口径

- 核心数值并非来自一轮统一矩阵，也不是跨轮平均值，而是从多次复现中按最终配置和有效性筛选的测点。机器可读数据通过 `headline_source` 标记来源；详细扩展性表展示完整矩阵，重复性表展示轮次间波动。
- 核心结果中的 1P1D 256K 使用 `--tokenize-prompt`，每条请求精确发送 262,144 个 token IDs。
- DP=2 表示两台 MI300X 节点的 Prefill-only capacity（仅 Prefill 聚合容量），不包含 P→D KV-cache transfer（KV 缓存传输）。
- H200 工作簿将 J 列标注为单机 Decode 吞吐，但每个值都等于本地 per-DP `BS × TPS`，没有乘 DP4。因此，本文将其作为工作簿内的 per-DP 口径参考，不认定为已确认的单机或 DP4 聚合指标。
- H200 工作簿没有输出长度列。因此，机器可读的 H200 参考点使用 `output_tokens=null`；另一份 16K 社区镜像说明虽然提到 1K 输出，但不能证明 8K/64K 工作簿各行的输出长度。
- 本文不会把 Client concurrency 直接当成实测 Decode batch；8K 与 64K 的 scheduler-log 审计都记录了稳态值与峰值。
- H200 数值只作为方向性参考，不构成严格同条件的硬件 benchmark：MI300X 使用真实 expert routing，H200 参考使用理想均衡 routing。
- 机器可读的核心结果：[`data/final-results.tsv`](data/final-results.tsv)；scheduler-log 审计：[`data/validation/decode-service-log-audit-8k.json`](data/validation/decode-service-log-audit-8k.json)。

### H200 参考数据来源

| 字段 | 公开记录 |
|---|---|
| 来源 | 小米提供的 MiMo-V2.5-Pro 性能报告；私有归档，不公开转载 |
| 审阅日期 | 2026-05-18 |
| Prefill 参考 | TP8/EP16/DP2、balanced `fake_topk_ids`、关闭 radix cache、单机/单节点吞吐 |
| Decode 参考 | 8K 和 64K 上下文行；TP8/EP32/DP4、balanced `fake_topk_ids`、MTP 3 层、报告接受率 0.75；工作簿没有输出长度列 |
| Decode TPOT 来源 | 客户工作簿；根据 per-DP Decode 日志输出速率和本地 BS，按 `1000 / (tok/s ÷ BS)` 反推 |
| Decode 吞吐口径 | J 列标为单机吞吐，但数值等于本地 `BS × TPS`，且未乘 DP4；本文按工作簿内的 per-DP 口径参考处理 |
| Decode 输出长度证据 | 工作簿逐行未明确；相邻 Word 说明只在另一项 16K 社区镜像测试中提到 1K 输出 |
| 交付用途 | 只作为方向性的 per-node/per-DP 参考 |

机器可读的来源信息和全部参考值见 [`data/validation/h200-reference.json`](data/validation/h200-reference.json)。

### 机器可读证据

- 核心结果点：[`data/final-results.tsv`](data/final-results.tsv)
- 详细扩展性结果：[`data/scalability-results.tsv`](data/scalability-results.tsv)
- Decode 核心点复测：[`data/decode-repeatability.tsv`](data/decode-repeatability.tsv)
- 长上下文 Decode 结果：[`data/decode-long-context-results.tsv`](data/decode-long-context-results.tsv)
- 固定 batch 稳态 Decode 结果：[`data/decode-fixed-batch-results.tsv`](data/decode-fixed-batch-results.tsv)
- 历史受控 ISL 结果包：[`data/controlled-isl-results.tsv`](data/controlled-isl-results.tsv)
- 历史受控 ISL 方法与源文件哈希：[`data/validation/controlled-isl-evidence.json`](data/validation/controlled-isl-evidence.json)
- 固定 batch 方法与源哈希：[`data/validation/decode-fixed-batch-audit.json`](data/validation/decode-fixed-batch-audit.json)
- 长上下文运行环境与源文件证据：[`data/validation/decode-long-context-evidence.json`](data/validation/decode-long-context-evidence.json)
- Exact-token 与运行环境验证元数据：[`data/validation/`](data/validation/)
- 唯一支持的复现代码：[`scripts/amd-latest/`](scripts/amd-latest/)
- 仓库质量门：`python3 scripts/validate_repo.py`（预期最后一行：`REPO_VALIDATION=PASS`）

**仓库 CI 边界：** 已审查 commit 的 CodeQL 已通过。GitHub Pages 在进入 Jekyll 前仍失败，原因是上层 monorepo（单仓库）中已有 gitlink `Deep-Learning/Foundry-Managed-Compute-Open-Models` 缺少对应的 `.gitmodules` URL。该 checkout 故障早于本次 MI300X Fix Pass，不影响 GitHub README、全新克隆验证或本基准测试子目录；修复工作应由上层仓库维护者完成。

---

## 为什么 PD 分离后 Prefill 与 Decode 可以拥有独立 BS 和超参

**核心结论：Batch Size（批大小）不是贯穿整个系统的一个全局值。** 请求的 input length（输入长度，ISL）和 requested output length（请求输出长度，OSL）本身不会因阶段变化，但会先后进入两套独立的 scheduler（调度器）。Prefill scheduler 将 new sequences（新序列）和 input-token chunks（输入 Token 分块）组织成批；Decode scheduler 则对 running requests（正在生成 Token 的请求）动态组批。PD 分离后，两套 scheduler、实例规模和执行参数都可以分别调优。

![PD分离后的请求生命周期与独立batch](images/request_batching_lifecycle.png)

*图 2：Prefill 阶段的请求批、Token 批与 Decode 阶段的运行请求批彼此独立。底部还区分了 1P1D PD c16 记录与非 PD exact64 BS16 容量实验。*

### 如何解读小米社区版协议：Prefill 动态组批，Decode 按目标工况验收

![小米社区版协议中的两套独立 Batch 口径](images/xiaomi_protocol_batch_planes.png)

*图 2a：Prefill 侧由协议固定的是 client load（客户端负载）和 Token chunk 上限，实际 request batch（请求批）与 token batch（Token 批）由 scheduler 动态形成。Decode 侧规定 per-DP BS64 和 BS96 两个目标工况，是否达到目标必须由 `#running-req` 验证。二者之间不存在固定的一一对应关系。*

| 层次 | 协议设定 | 运行日志证据 | 解读 |
|---|---|---|---|
| Client（客户端） | Prefill 压测设置 `max-concurrency=32`；每条请求有自己的 ISL/OSL | 实际 in-flight requests（在途请求数） | c32 表示客户端施加的并发压力，不是 Prefill BS |
| Prefill | `chunked-prefill-size=32768` | `#new-seq` 和 `#new-token` 的分布 | 32K 是单条请求一次允许提交的 Token chunk 上限，不代表 32 条请求 |
| KV handoff（KV 交接） | 每条完成 Prefill 的请求都会生成可交接的 KV | 完成 Prefill 并进入 Decode 的请求速率 | P 侧必须持续供给，但 batch 无须与 D 侧取相同数值 |
| Decode | 16K/1K workload（工作负载）下，per-DP 目标为 BS64 或 BS96 | `#running-req` 的 modal/peak（稳态值/峰值）、queue（排队请求）和 KV usage（KV 占用） | 64/96 是预设目标工况；actual Decode batch 仍由 scheduler 动态形成 |

对客户说明时，可以按四点来讲：

1. `max-concurrency=32` 只表示 Prefill 压测客户端最多同时挂起 32 条请求，不表示 P 节点一次处理 32 条请求。
2. `chunked-prefill-size=32768` 只限制单条请求一次最多提交 32K input tokens，不表示 Prefill request BS 为 32。
3. P 节点在每个 scheduler step 中接纳多少条请求、处理多少 new tokens，应以 `#new-seq` 和 `#new-token` 为准；请求完成 Prefill 后，其 KV 才能交给 Decode。
4. D 节点单独验收 per-DP BS64 和 BS96。二者是预先定义的目标工况；是否真正达到并保持目标，必须查看 `#running-req`，不能用 client concurrency、CUDA Graph BS 或 `--max-running-requests` 代替证明。

因此，不存在 `Prefill BS32 -> Decode BS64/96` 这种固定映射。Prefill 与 Decode 应分别测量：P 侧证明各 ISL 下有足够的输入吞吐，D 侧证明 16K/1K 工作负载下的 actual batch 达到对应 per-DP 目标。没有必要对所有 Prefill 与 Decode 测点做完整笛卡尔积。该图只解释客户协议的 batch 口径，不表示当前 MI300X 路径已经达到 per-DP BS96。

### 一个请求涉及的三类 Batch 概念

| 层次 | 符号 / 指标 | 定义 | 不等同于 |
|---|---|---|---|
| Workload（工作负载） | `ISL`、`OSL` | **每条请求**的 input tokens 和 requested output tokens | Batch Size |
| Client（客户端） | `N_prompts`、`C_client` | 提交请求总数，以及客户端允许的最大 in-flight 请求数 | 服务端实测 batch |
| Prefill request batch | $B_P^{req}(t)$ | 一个 Prefill scheduler batch 接纳的 new sequences 数量 | Client concurrency 或 Decode batch |
| Prefill token batch | $T_P(t)$ | 该 Prefill batch 中全部 input-token chunks 之和 | 整轮测试的全部 prompt tokens |
| Decode batch | $B_D(t)$ | 某个 Decode scheduler step 中 running requests 的数量（`#running-req`） | `--max-running-requests` |
| Admission ceiling（接纳上限） | `--max-running-requests` | 服务端允许同时处于 running 状态的最大请求数 | 实测 Decode batch 必然达到该值的承诺 |

对于规格相同的请求，提交的总输入 Token 数为：

$$
T_{input}=N_{prompts}\times ISL.
$$

在 Prefill scheduler 的第 $t$ 个 step 中，请求 $i$ 只贡献当前 chunk $c_i(t)$：

$$
B_P^{req}(t)=|\mathcal{P}(t)|,\qquad
T_P(t)=\sum_{i\in\mathcal{P}(t)}c_i(t).
$$

三个 Prefill 控制参数的单位不同，不能统一简称为“Prefill BS”：

$$
c_i(t)\le\texttt{chunked-prefill-size},\qquad
T_P(t)\le\texttt{max-prefill-tokens},\qquad
B_P^{req}(t)\le\texttt{prefill-max-requests}
$$

在设置了相应的 limit（上限）时，上述约束适用。在固定的 SGLang 源码中，`--chunked-prefill-size` 限制单个 chunk，`--max-prefill-tokens` 限制一个 Prefill batch 中的全部 new tokens，`--prefill-max-requests` 限制该 batch 的请求数。后两项未在本仓库支持的 launch script（启动脚本）中显式配置，因此本文不推测其实际生效值。

Decode 维护的是另一组动态请求集合：

$$
B_D(t)=|\mathcal{D}(t)|\le\texttt{max-running-requests}.
$$

不同请求完成 Prefill 和 Decode 的时间不同，因此 $C_{client}$、$B_P^{req}(t)$ 和 $B_D(t)$ 无须相等。也正因如此，只写“BS16”无法说明口径；本文会明确指出它表示 client concurrency、Prefill request batch、Prefill token batch，还是 actual Decode batch。

### PD 可以分别调优什么，哪些契约必须保持一致

| 控制项 | 本次支持的 1P1D Prefill 实例 | 本次支持的 1P1D Decode 实例 | 关系 |
|---|---|---|---|
| Scheduler batch | 独立形成 request batch 和 token batch | 独立形成 dynamic running-request batch（动态运行请求批） | **彼此独立，可以不同** |
| Scale-out | Prefill instance pool（实例池） | Decode instance pool（实例池） | 可分别针对 TTFT 与 TPOT/吞吐压力扩缩 |
| `--chunked-prefill-size` | `32768` | `16384` | 分别配置；主 P-stage chunking path（分块路径）由 Prefill 侧数值控制 |
| `--max-prefill-tokens` | 未显式设置 | 未显式设置 | Prefill token-batch 上限；不推测实际生效值 |
| `--prefill-max-requests` | 未显式设置 | 未显式设置 | Prefill request-count 上限；不推测实际生效值 |
| `--max-running-requests` | `128` | `128` | 配置的是 admission ceiling，**不是实测 Decode BS** |
| `--mem-fraction-static` | `0.85` | `0.85` | 本次取值相同，但由两个 process 分别管理，可按 role 调优 |
| CUDA graph | 关闭 | Launch script 未关闭 | role-specific execution tuning（按角色调优）的直接示例 |
| MTP/EAGLE controls | 固定接受长度 `3`、`match-expected` | 固定接受长度 `3`、`match-expected` | 为固定接受率性能测试保持一致；不代表自然接受率 |

两侧可以独立调优，但相关契约仍必须保持兼容。本次 validated path（已验证路径）在两侧使用相同的 model/checkpoint（模型与权重）、TP8 model partition（模型分片）、`context-length=262151`、`kv-cache-dtype=fp8_e4m3`、`page-size=32`、Mooncake transfer backend（传输后端），以及相互兼容的 KV layout（KV 布局）。这些配置共同构成 model/KV-transfer contract（模型与 KV 传输契约）。Batch formation（组批方式）、scheduler policy（调度策略）、process memory budget（进程内存预算）、execution graph policy（执行图策略）和 instance count（实例数量）可以按角色分别调优；序列化后的 KV 表示和 sequence semantics（序列语义）则必须兼容。

### ISL 如何约束实际 Decode Batch

![长ISL Decode的KV容量关系](images/kv_capacity_relationship.png)

*图 3：非 PD exact64 计算示例说明 sequence length（序列长度）与 KV 容量如何限制实际 Decode concurrency。历史 128K actual-BS4 测点和历史 192K actual-BS4 测点分别完成了实测。64K 同方法锚点、255K actual-BS4 测点和 equal-KV-load（等 KV 负载）组合尚未实测，仅用于规划。此前单独实测的 255K PD-serving c1 能力点仍然有效。*

对于正在执行 Decode 的请求，可以采用以下容量模型：

$$
\sum_{i\in\mathcal{D}(t)}\left(ISL_i+generated_i+reserved_i\right)\le K_{pool}.
$$

忽略内存分配粒度和运行时预留后，可得到同规格请求的理论上界：

$$
B_{raw}=\left\lfloor\frac{K_{pool}}{ISL+OSL}\right\rfloor.
$$

Allocation pages（分配页）、fragmentation（内存碎片）、MTP state（MTP 状态）和 safety reserve（安全预留）都会降低可用上限。因此，当 KV 容量已经成为瓶颈时，单纯提高 `--max-running-requests` 无法继续增大实际 Decode batch。

两条 64K/1K 实测记录回答的是不同问题：

| 记录 | Client load（客户端负载） | 实测 Decode batch | 解读 |
|---|---|---|---|
| 双节点 1P1D PD、c16 | Client concurrency 16 | 稳态 `4`、峰值 `5` | PD scheduler/capacity（调度与容量）记录；不是“Decode BS16”，也不是“Prefill BS16” |
| 单节点 exact64 fixed batch | 16 条 prompt、client concurrency 16 | 实际 Decode batch `16`、queue `0` | 核心 Fixed-BS16 结果采用的**非 PD 容量实验** |

单节点记录的 full-attention KV pool（全注意力 KV 池）实测为 $K_{pool}=1{,}442{,}464$ tokens。Raw sequence positions（原始序列位置数）为：

$$
16\times(65{,}536+1{,}024)=1{,}064{,}960,
\qquad
\frac{1{,}064{,}960}{1{,}442{,}464}=73.8\%.
$$

Scheduler 报告的 `full token usage` 为 `0.73–0.74`，与上述计算一致。这说明为什么把单节点 `mem-fraction-static` 提高到 `0.95` 后，exact64 仍能保持实际 Decode BS16；但这**不表示**某个 Prefill kernel 曾同时处理十六条完整的 64K prompt。

### 基于7/13环境的历史受控 ISL=128K 记录

这条历史记录采用的方法不同于上方的 1P1D 完整矩阵，不能替代完整矩阵结果。Prefill 采用双节点 1P1D 部署的 aggregate input tok/s（聚合输入吞吐）；Decode 采用单节点非 PD 服务中经 transition guard（过渡样本门）筛选后的 steady full-BS4 scheduler gen tok/s（稳态满批调度器生成吞吐）。两类指标不能相除，也不能视为同一种吞吐。

#### 历史 128K Prefill 测点

| 拓扑 | 客户端并发 | 请求数 | Input tok/s | 平均 TTFT | 测量次数 |
|---|---:|---:|---:|---:|---:|
| 1P1D PD | 4 | 16 | **15,943.02** | 30.17 s | **N=1** |

#### 历史 128K Decode 固定 BS4 测点

| 拓扑 | 实际 Decode batch | 请求数 | 稳态 scheduler gen tok/s | 客户端 output tok/s | 平均 TTFT | 平均 TPOT | Full-token usage（完整 Token 占用率） | 测量次数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 单节点 TP8、非 PD | **4** | 4 | **380.56** | 94.59 | 20.31 s | 22.46 ms | 0.36–0.37 | **N=1** |

Prefill 测点来自指标解析器恢复后的一次有效服务启动；Decode 测点随后在单节点服务上运行。两项均为 N=1，不能证明同一服务内或 Fresh-Service 的重复性。

Decode 测点使用 `SGLANG_SIMULATE_ACC_LEN=3` 和 `match-expected`；scheduler 报告的 accept length（接受长度）为 `3.00`，rate（接受率）为 `0.67`。该测点用于评估固定接受率下的 scheduler 容量，不验证自然 MTP 接受率或输出质量。六月进行的 BS1 边界诊断未纳入该记录。

历史机器可读证据：[`data/controlled-isl-results.tsv`](data/controlled-isl-results.tsv)；方法与运行环境审计：[`data/validation/controlled-isl-evidence.json`](data/validation/controlled-isl-evidence.json)；脱敏后的重算证据：[`data/evidence/controlled-isl-128k-192k/`](data/evidence/controlled-isl-128k-192k/)。

### 基于7/13环境的历史受控 ISL=192K 记录

这条历史记录同样采用不同于上方 1P1D 完整矩阵的方法。Prefill 与 Decode 仍是两类独立指标，不进行合并。

#### 历史 192K Prefill 测点

| 拓扑 | 客户端并发 | 请求数 | Input tok/s | 平均 TTFT | 测量次数 |
|---|---:|---:|---:|---:|---:|
| 1P1D PD | 4 | 16 | **13,855.30** | 51.89 s | **N=1** |

#### 历史 192K Decode 固定 BS4 测点

| 拓扑 | 实际 Decode batch | 请求数 | 稳态 scheduler gen tok/s | 客户端 output tok/s | 平均 TTFT | 平均 TPOT | Full-token usage（完整 Token 占用率） | 测量次数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 单节点 TP8、非 PD | **4** | 4 | **319.71** | 58.90 | 35.73 s | 33.03 ms | 0.55 | **N=1** |

Prefill 测点来自通过相同不可变运行环境和配置验收门的一次有效服务启动。Decode 测点随后在历史 128K Decode 测点所用的同一单节点服务上运行。这条 192K 记录仍为 N=1，不能证明同一服务内或 Fresh-Service 的重复性。

Decode 测点使用 `SGLANG_SIMULATE_ACC_LEN=3` 和 `match-expected`；scheduler 报告的 accept length（接受长度）为 `3.00`，rate（接受率）为 `0.67`。该测点用于评估固定接受率下的 scheduler 容量，不验证自然 MTP 接受率或输出质量。六月进行的 BS1 边界诊断未纳入该记录。

历史机器可读证据：[`data/controlled-isl-results.tsv`](data/controlled-isl-results.tsv)；方法与运行环境审计：[`data/validation/controlled-isl-evidence.json`](data/validation/controlled-isl-evidence.json)；脱敏后的重算证据：[`data/evidence/controlled-isl-128k-192k/`](data/evidence/controlled-isl-128k-192k/)。运行 `python3 scripts/analyze_controlled_isl_evidence.py` 可以重建历史测点及已披露的跨长度变化率。

### 后续如何只改变输入长度而不混入其他变量

| 研究目标 | 控制变量 | 建议测点 | 证据状态 |
|---|---|---|---|
| 历史受控 128K 锚点 | OSL 固定为 1K，**实际 Decode batch 固定为 4** | 128K 输入 | **已实测；N=1**。 |
| 历史受控 192K 锚点 | OSL 固定为 1K，**实际 Decode batch 固定为 4** | 192K 输入 | **已实测；N=1**。尚未形成完整的 64K→192K 同方法曲线。 |
| 等 KV 负载规划：64K | Raw token positions（原始 Token 位置数）保持在 exact64 负载附近 | 64K×16 | 规划估算；尚未实测 |
| 等 KV 负载规划：128K | Raw token positions（原始 Token 位置数）保持在 exact64 负载附近 | 128K×8 | 规划估算；尚未实测 |
| 等 KV 负载规划：192K | Raw token positions（原始 Token 位置数）保持在 exact64 负载附近 | 192K×5 | 规划估算；尚未实测 |
| 等 KV 负载规划：255K | Raw token positions（原始 Token 位置数）保持在 exact64 负载附近 | 255K×4 | 规划估算；尚未实测 |

允许的最大输入测点是 **255K input + 1K output**：$261{,}120+1{,}024=262{,}144\le262{,}151$。**256K input + 1K output** 需要 $263{,}168$ 个 Token 位置，超过 `context-length=262151` 的限制。后续报告必须保留实际观测到的 Decode batch，不能再把 client concurrency 记成 BS。

两张图均可通过 `python3 scripts/generate_batching_diagrams.py` 复现；运行前请先根据 `requirements-diagrams.txt` 安装固定版本的文档依赖。

---

## 硬件与软件栈

### 计算：双节点 Azure MI300X 集群

| 属性 | 值 |
|------|---|
| Azure SKU | `Standard_ND96isr_MI300X_v5`（每节点 8× MI300X） |
| GPU | AMD Instinct MI300X，`gfx942`（CDNA 3），**192 GB HBM3**，最大理论峰值 5.3 TB/s |
| 节点数 | 2（VMSS，位于同一 placement group，保证 IB 互联） |
| 总 GPU 内存 | **16× 192 GB = 3,072 GB** |
| InfiniBand | 每节点 8× CX7 400G NDR，每端口实测 **368 Gbps** |

### 软件栈

| 组件 | 版本 | 说明 |
|------|------|------|
| 已验证运行环境镜像 | `AMD_20260713_derived_final_image@sha256:08deabd2...5910` | 私有镜像地址不公开；不可变 digest、image ID（镜像 ID）、运行环境 commit 和 clean-pull（全新拉取）证据记录在 `data/validation/` |
| 基础镜像来源 | `rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510` | Base image ID（基础镜像 ID）`sha256:bb9d2e5ab1a6...` |
| SGLang | Package `0.0.0.dev14147+g2f9b9aedf.d20260706`、source HEAD `2f9b9aedf` | 最终测试运行环境 |
| AITER | Source HEAD `00e94abf`；tuned CSV SHA-256 `2c87ff1...80ea7` | 最终测试运行环境 |
| ROCm | 7.2.0 | |
| GEMM 路径 | **CK A8W8 blockwise bpreshuffle** | `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1` |
| Mooncake | `0.3.7.post2` | PD 分离中的 KV cache（KV 缓存）传输 |
| PyTorch | 2.9.1+rocm7.2.0 | ROCm 后端 |

### 模型

| 属性 | 值 | 来源 |
|------|---|------|
| 模型 | [XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro) | HuggingFace |
| 总参数 | 1.02 T | HF Model Card |
| 活跃参数 | 每个 Token 42 B | HF Model Card |
| Routed experts（路由专家） | 384，每个 Token 激活 8 个 | HF Model Card |
| Attention（注意力） | 混合结构：10 Global + 60 SWA（window=128） | HF Model Card |
| MTP | 3 层 multi-layer EAGLE | HF Model Card |
| 量化 | FP8 E4M3 | HF Model Card |
| Checkpoint（检查点）大小 | 963 GB（34 个 safetensors） | 实测 |

---

## 在 Azure 上运行并复现结果

请使用下方的 immutable baked runtime（不可变固化运行环境），其中已包含经过验证的 SGLang/AITER 软件栈。控制脚本必须使用本仓库固定 commit 中的 [`scripts/amd-latest/`](scripts/amd-latest/)；镜像内置副本只是历史版本，可能不包含后续的安全修复和验证修复。

### 前置条件

- 2× Azure `Standard_ND96isr_MI300X_v5` 节点；节点来自同一 VMSS，并位于同一 placement group，以保证 IB 互联
- 已获授权访问私有运行环境镜像；本仓库不公开 registry（镜像仓库）地址和拉取凭据
- 模型：[XiaomiMiMo/MiMo-V2.5-Pro](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)，下载到 `/data/models/MiMo-V2.5-Pro`
- Benchmark dataset（基准测试数据集）位于 `/data`；镜像不包含模型权重和数据集
- PD-separated Decode container（PD 分离的 Decode 容器）必须暴露 RDMA 设备、`/dev/mem` 和 `CAP_SYS_ADMIN`
- 两个节点的 `/data/david-share` 目录下都必须准备本仓库的 pinned checkout（固定版本检出）

启动容器前创建 shared checkout（共享代码检出目录），并把实际 commit SHA 写入本次运行证据：

```bash
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git /data/david-share
git -C /data/david-share sparse-checkout set Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark
git -C /data/david-share rev-parse HEAD
```

### 在两个节点拉取并启动 Runtime

容器需要较高的主机权限来完成 RDMA memory registration（RDMA 内存注册），因此只能部署在专用、可信的 benchmark node（基准测试节点）上。

```bash
read -rp 'Private registry login server: ' ACR_LOGIN_SERVER
read -rp 'Authorized immutable image reference: ' IMAGE_REF

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
'
```

image identity（镜像身份）和 clean-pull 证据见 [`data/validation/container-image.json`](data/validation/container-image.json)。

还需要在两个容器内分别验证当前 source bundle（源码包）：

```bash
export BUNDLE_DIR=/data/david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
cd "$BUNDLE_DIR"
sha256sum -c SHA256SUMS.txt
```

### 1P1D

```bash
# 在每个节点进入容器，然后使用固定 commit 中的仓库脚本包。
docker exec -it mimo-mi300x bash
cd /data/david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/datasets/ShareGPT_V3_unfiltered_cleaned_split.json
read -rp 'Prefill node IB IP: ' PREFILL_IB_IP
read -rp 'Decode node IB IP: ' DECODE_IB_IP
export PREFILL_IB_IP DECODE_IB_IP

# 先在对应节点的独立终端启动两个 worker：
SERVER_HOST="$PREFILL_IB_IP" bash launch_pd_prefill.sh
SERVER_HOST="$DECODE_IB_IP" bash launch_pd_decode.sh

# Prefill 节点容量校验：
python3 validate_server_info.py "http://${PREFILL_IB_IP}:30000/server_info" \
	--output /data/mimo-amd-latest/onep/evidence/prefill-server-info.json

# Decode 节点容量校验：
python3 validate_server_info.py "http://${DECODE_IB_IP}:30001/server_info" \
	--output /data/mimo-amd-latest/onep/evidence/decode-server-info.json

# 两项容量校验都通过后，在 Prefill 节点启动 Router：
export ROUTER_BIND_HOST="$PREFILL_IB_IP"
bash launch_pd_router.sh

# Router 就绪校验：
curl -fsS --max-time 30 "http://${ROUTER_BIND_HOST}:40000/v1/models" >/dev/null

# 三项校验都通过后，在 Router 节点执行：
export ROUTER_HOST="$ROUTER_BIND_HOST"
bash benchmark_1p_prefill.sh
bash benchmark_decode.sh
```

Immutable image（不可变镜像）内置的是生成原始核心结果的脚本包；长上下文 Decode 脚本是在镜像发布后加入本仓库的扩展。该脚本不修改镜像，仍使用同一套 immutable runtime（不可变运行环境）。将当前仓库克隆或复制到 `/data` 下，然后执行：

```bash
cd /data/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
export MODEL=/data/models/MiMo-V2.5-Pro
export DATASET_PATH=/data/datasets/ShareGPT_V3_unfiltered_cleaned_split.json
export PYTHONPATH="/sgl-workspace/sglang_0625/python${PYTHONPATH:+:$PYTHONPATH}"
bash benchmark_decode_long_context.sh
```

完成后，把 Decode 节点证据复制到 Router 节点，使三份 service log（服务日志）和两份 `server-info.json` 位于同一目录，并保留下列 basename（基本文件名）。然后执行：

```bash
cd /data/david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
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

### 双节点 Prefill（DP=2）

```bash
cd /data/david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
read -rp 'Node0 IB IP: ' Node0_IP
read -rp 'Node1 IB IP: ' Node1_IP
export Node0_IP Node1_IP

# 分别在对应节点的独立终端启动 worker：
SERVER_HOST="$Node0_IP" bash launch_dp2_node0.sh
SERVER_HOST="$Node1_IP" bash launch_dp2_node1.sh

# 启动 Router 前，分别直连验证 node0 和 node1：
python3 validate_server_info.py "http://${Node0_IP}:30000/server_info" \
	--output /data/mimo-amd-latest/dp2/evidence/node0-server-info.json
python3 validate_server_info.py "http://${Node1_IP}:30001/server_info" \
	--output /data/mimo-amd-latest/dp2/evidence/node1-server-info.json

export ROUTER_BIND_HOST="$Node0_IP"
bash launch_dp2_router.sh
curl -fsS --max-time 30 "http://${ROUTER_BIND_HOST}:40000/v1/models" >/dev/null
export ROUTER_HOST="$ROUTER_BIND_HOST"
bash benchmark_dp2_prefill.sh
```

上面的 convenience script（便捷脚本）会连续执行三个测点。要生成可用于报告的 per-point distribution evidence（逐点请求分布证据），需要启动全新的 DP=2 服务，在每次 `run_point` 前后分别统计两个 worker log 中的 `grep -c 'POST /generate'`，再校验记录下来的四个整数。8K、64K、256K 都要分别执行：

```bash
cd /opt/mimo-mi300x/scripts/amd-latest
export LOG_DIR=/data/mimo-amd-latest/dp2
source ./benchmark_common.sh

# 记录两个执行前计数后，在 node0 每次只运行一个测点：
run_point 8192 1 16 32 1 900 'Input token throughput'
# run_point 65536 1 2 32 1 900 'Input token throughput'
# run_point 262144 1 2 32 1 1200 'Input token throughput' token_ids

# 分别在 node0 和 node1 记录执行前后的计数：
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

汇总三份 DP=2 服务日志后执行：

```bash
cd /data/david-share/Deep-Learning/MiMo-V2.5-Pro-on-MI300X-Benchmark/scripts/amd-latest
EVIDENCE=/data/mimo-amd-latest/dp2/evidence
python3 validate_service_logs.py \
	"$EVIDENCE/node0_outer.log" \
	"$EVIDENCE/node1_outer.log" \
	"$EVIDENCE/router_outer.log" \
	--profile dp2 \
	--output "$EVIDENCE/service-validation.json"
```

只有 client gate（客户端校验门）通过、两个 worker delta（请求数增量）都为正且总和为 33（32 measured + 1 warmup），并且 service-log gate（服务日志校验门）通过时，该 DP=2 测点才可写入报告。

### 清理

```bash
docker rm -f mimo-mi300x
```

---

## 必要的运行设置

| 设置 | 要求 |
|---|---|
| Decode CUDA Graph | 保持启用；Prefill 禁用 CUDA Graph。 |
| 256K request framing（请求构造） | 使用 context length（上下文长度）262151 和 `--tokenize-prompt`；要求 `max_req_input_len>=262145`。 |
| Router health（健康检查） | 使用非生成型 `/server_info` endpoint（端点），timeout（超时）为 30 秒。 |

---

## 参考资料

- [Azure ND-MI300X-v5 规格系列](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ndmi300xv5-series)
- [AMD Instinct MI300X datasheet（数据手册）](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/data-sheets/amd-instinct-mi300x-data-sheet.pdf)
- [MiMo-V2.5-Pro Model Card（模型卡）](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro)
- [AMD SGLang Fork（分支）— `mimo_aiter_attn`](https://github.com/sammysun0711/sglang/tree/mimo_aiter_attn)
- [AMD aiter (ROCm)](https://github.com/ROCm/aiter)
- [MiMo 模型专用 fused-MoE tuning — `aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- [SGLang PD Disaggregation Docs（文档）](https://docs.sglang.io/docs/advanced_features/pd_disaggregation.md)
