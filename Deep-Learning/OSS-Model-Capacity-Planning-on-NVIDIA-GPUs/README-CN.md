# Azure ND/NC H100 上的开源与开放权重模型容量规划

[![AIConfigurator](https://img.shields.io/badge/AIConfigurator-0.11.0-76B900)](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0)
[![Evidence](https://img.shields.io/badge/evidence-CPU--offline%20prediction-087A80)](evidence/)
[![GPU scope](https://img.shields.io/badge/GPU%20scope-H100%20SXM%20%7C%20H200%20SXM-76B900)](https://ai-dynamo.org/aiconfigurator/support-matrix/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB)](requirements-repro.txt)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](../../LICENSE)

> 一次可复现的 AIConfigurator 容量评估：先定义模型、工作负载、服务目标、运行时和 NVIDIA 平台，再在 CPU 上运行官方搜索命令，保存排序后的预测结果和完整证据。

> Author: 魏新宇 (Xinyu Wei)

[English](README.md) | [中文](README-CN.md)

[详细步骤](#5-完整复现一次-cpu-离线预测) · [使用的工具](#2-使用的工具与方法) · [规划输入](#3-容量规划的输入) · [示例](#6-完整示例) · [证据](#附录-a-证据与参考资料)

---

## 1. 执行摘要

开源与开放权重模型的容量规划，不是从参数量到 GPU 数量的查表。答案会随模型架构与量化方式、工作负载特征、时延目标、目标 GPU 拓扑、推理后端和服务模式而改变。

本仓库冻结模型、工作负载、平台和 SLO 输入；在 CPU 上以 `SILICON` 模式运行 NVIDIA AIConfigurator 0.11.0；保存完整日志、Top-N CSV、Pareto 数据和生成的候选配置；并校验它们的哈希和算术。这些结果是 AIConfigurator 的容量预测，也正是该工具设计要输出的内容。

第 6 节的 Qwen 案例用于演示方法。它们是示例，不是工具的适用范围。在同一模型、同一 GPU 预算的对比中，工作负载输入会显著改变预测：长上下文 Coding Agent 与短上下文 Chat 两个场景的每卡吞吐相差 4.75 倍。第 4.4 节对照固定版本的源码，说明这些数字究竟由哪些算术得出，并列出限制其使用范围的十项建模局限。

## 2. 使用的工具与方法

### 2.1 已公开运行所使用的软件

| 软件 | 官方来源 | 在本仓库中的角色 | 本次实际用法 |
|---|---|---|---|
| NVIDIA AIConfigurator | [GitHub repository](https://github.com/ai-dynamo/aiconfigurator) · [v0.11.0](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0) · [CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md) | 性能建模、配置搜索、排序和部署配置生成 | 主要的容量评估引擎；版本 `0.11.0`，commit `614b9c8c8725332533616786e2eb049df48935f0` |
| vLLM | [GitHub repository](https://github.com/vllm-project/vllm) | 开源推理后端 | 在一个本地示例中作为性能数据库目标；未启动模型服务 |
| TensorRT-LLM | [GitHub repository](https://github.com/NVIDIA/TensorRT-LLM) | NVIDIA 优化的推理后端 | 在一个本地示例中作为性能数据库目标；未启动模型服务 |

AIConfigurator 是 Apache-2.0 软件。它内置的性能数据以 NVIDIA GPU 平台和特定框架实现为中心，因此软件路径开放并不意味着这个容量模型与硬件厂商无关。

**方法依据：** [AIConfigurator: Lightning-Fast Configuration Optimization for Multi-Framework LLM Serving, arXiv:2601.06288v1](https://arxiv.org/abs/2601.06288v1) 定义了建模方法、准确度评估、搜索效率证据和设计边界。

### 2.2 本仓库实际执行了什么

每个公开结果都经过以下路径：

| 阶段 | 实际动作 | 输出与证据 |
|---|---|---|
| 1. 定义输入 | 记录精确的模型、ISL/OSL、前缀复用、SLO、目标 GPU、后端、版本，以及 GPU 预算或负载目标 | 命令 argv 和实验配置 |
| 2. 检查支持情况 | 在需要预检的场景运行官方 `aiconfigurator cli support` | 完整的支持性检查日志 |
| 3. 评估容量 | 以 `SILICON` 模式运行官方 `default` 或 `recommend` 命令 | 排序后的 Top-N 预测、Pareto 数据和生成的候选配置 |
| 4. 发布证据 | 只复制允许公开的日志和机器可读输出，同时记录源文件和公开文件的 SHA-256 | 带版本的运行证据包和 manifest |
| 5. 校验 | 重算哈希、结果算术、SLA 合规、公开数据边界、链接和双语不变量 | 确定性校验器的输出 |

本仓库到容量评估和证据校验为止。它不声称部署过模型服务，也不声称做过基准测试。

### 2.3 AIConfigurator 提供什么

给定模型、NVIDIA 系统、推理后端、工作负载描述和时延约束，AIConfigurator 可以：

- 判断候选拓扑能否装进 GPU 显存；
- 在适用时搜索张量并行、流水线并行、数据并行、专家并行和 MoE 张量并行；
- 比较 Static、Aggregated 和 Disaggregated 三种服务模式；
- 预测 TTFT、TPOT、请求时延、显存和吞吐；
- 按声明的 TTFT 和 TPOT 上限过滤候选，并按 tokens/s/GPU 排序；Pareto 前沿作为绘图输出给出（第 4.4 节）；
- 按请求率或并发目标计算副本数和总 GPU 数；
- 为受支持的运行时和平台生成候选启动与部署产物。

在普通配置搜索中，它不执行模型、不优化内核、不运行集群，也不会自动发现工作负载。在本仓库中，它输出的模型计算值就是最终评估结果。

### 2.4 本仓库中的可执行资产

| 路径 | 职责约定 |
|---|---|
| [`tools/validate_evidence.py`](tools/validate_evidence.py) | 确定性门禁。重算每个公开文件的 SHA-256 和字节数，检查每份日志的退出码标记，拒绝私有路径，重新推导 H200 的 32/34 卡算术、四卡 MoE 拓扑、三个工作负载行、选中的 16 卡布局和 4.75 倍比值，并比对两份 README 的必需链接、命令块、机制标识和已停用短语。不需要网络或 GPU；退出码即结论 |
| [`tests/test_validate_evidence.py`](tests/test_validate_evidence.py) | 拒绝篡改的证明。把本目录复制到临时位置，每个测试只做一处篡改，并断言校验器以非零退出码和预期信息拒绝 |
| [`tools/publish_run_evidence.py`](tools/publish_run_evidence.py) · [`tools/publish_real_scenario_evidence.py`](tools/publish_real_scenario_evidence.py) | 按允许清单从运行主机复制到 `evidence/runs/<run-id>/`。替换主机身份和绝对路径，记录源文件和公开文件哈希。只有发布新运行时才需要 |
| [`tools/make_report_figures.py`](tools/make_report_figures.py) | 根据已提交源码和 CSV 证据重新生成图 1 和图 3；需要 Windows 字体和 Pillow |
| [`requirements-repro.txt`](requirements-repro.txt) | 复现 Linux 运行所用的三个直接固定版本。传递依赖未锁定；见第 5.4 节 |
| [`evidence/runs/<run-id>/run-manifest.json`](evidence/README.md) | 每次运行的身份、工作负载、精确 argv、阶段状态，以及每个公开文件的源 SHA-256 和公开 SHA-256 |

## 3. 容量规划的输入

容量问题必须表达为四组输入和一个决策目标。

![容量规划问题定义](images/configuration-problem.png)

**图 1：原创解释图。** 模型、工作负载、服务目标、后端和硬件是配置搜索的共同输入。来源依据：[AIConfigurator CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md) 与 [论文第 4 节](https://arxiv.org/html/2601.06288v1)。图片 SHA-256：`42e48e0571826eb2f5f8457fe0d84e5b28df05f4da1acf2b2b0ab2616cdf868b`。

### 3.1 模型输入

| 字段 | 需要的细节 |
|---|---|
| 模型身份 | 精确的 Hugging Face 或本地模型 ID，以及 revision |
| 架构 | Dense 或 MoE、层数、隐藏维度、注意力与专家结构 |
| 精度 | BF16、FP8、FP4、INT8 或其他精确量化配置 |
| 上下文行为 | 原生上下文、RoPE/YaRN 设置、多模态 encoder 输入，以及启用时的 MTP 深度 |

### 3.2 工作负载输入

| 字段 | 需要的细节 |
|---|---|
| 请求形状 | ISL、OSL、适用时的图片尺寸与数量，以及是否可用前缀缓存 |
| 到达需求 | 请求率曲线或并发、峰值持续时间和突发行为 |
| 用户行为 | Thinking/Non-thinking 占比、chat template、采样方式和输出 token 的统计口径 |
| 服务目标 | TTFT、TPOT、端到端时延、goodput 和错误率目标 |

生产分析应使用有代表性的分组，例如正常流量、峰值流量和长上下文尾部流量。单个平均 ISL/OSL 只是一个示例点，不是生产流量分布。

### 3.3 平台输入

| 字段 | 需要的细节 |
|---|---|
| GPU | 精确的 NVIDIA 系统名称和显存容量 |
| 节点拓扑 | 每节点 GPU 数、NVLink/NVSwitch 域和节点间网络 |
| 后端 | TensorRT-LLM、vLLM 或 SGLang，以及精确版本 |
| 性能数据库 | `SILICON`、`HYBRID` 或其他模式，以及精确的数据库版本 |

标题中提到的 Azure 规格与 AIConfigurator 系统配置的对应关系如下。该对应关系比较的是 v0.11.0 的系统 YAML 文件与 Microsoft Learn 的规格页面；它是规格匹配，不是基准测试。

| Azure 规格系列 | Microsoft Learn 给出的 GPU | AIConfigurator v0.11.0 系统配置 | 是否被已公开运行使用 |
|---|---|---|---|
| [ND H100 v5](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ndh100v5-series) | 8 × H100 SXM 80 GB，NVLink 4.0，每 GPU 400 Gb/s InfiniBand | `h100_sxm`：80 GiB、3,350 GB/s、每节点 8 GPU、节点内 450 GB/s、节点间 400 Gb/s | 是，第 6.2 节的全部 H100 结果 |
| [ND H200 v5](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/nd-h200-v5-series) | 8 × H200 141 GB，900 GB/s NVLink，每 GPU 400 Gb/s InfiniBand | `h200_sxm` | 是，第 6.1 节 |
| [NCads H100 v5](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ncadsh100v5-series) | 1 至 2 × H100 NVL 94 GB，PCIe 形态，无 InfiniBand | 无。随附的 `h100_pcie` 配置描述的是 80 GB 的 PCIe 型号，其 YAML 注明未提供该型号的 silicon 性能数据库 | 否。本仓库没有任何公开数字适用于 NC 系列规格 |

### 3.4 搜索与输出

搜索空间可以包括服务模式、TP/PP/DP/EP/ETP、worker 数、副本数、batch size、KV Cache 分配、chunked prefill 和受支持的运行时参数。输出是带预测指标和生成产物的排序候选集，而不是一个脱离上下文的 GPU 数字。

```text
capacity input  = model definition + workload definition + platform definition
candidate       = serving mode + parallelism + workers + batch/runtime settings
capacity output = ranked candidates + predicted metrics + generated artifacts
```

### 3.5 服务模式：Aggregated 与 Disaggregated

服务模式是搜索空间的第一个维度，也是最常让规划者意外的维度，因此有必要准确说明这两种模式是什么。

LLM 推理有两个硬件特征相反的阶段：

| 阶段 | 工作 | 瓶颈 | 计算特征 |
|---|---|---|---|
| Prefill | 处理一个请求的完整输入并产出第一个 token | 通常是算力 | 大矩阵乘；利用率取决于输入长度和批处理 |
| Decode | 为每个活跃序列生成后续 token | 通常是显存带宽 | 每个活跃序列每步产出一个 token；批处理提高 GPU 利用率 |

矛盾由此直接产生：一次很长的 Prefill 会占住 GPU，让正在 Decode 的请求停顿，表现为 TPOT 抖动。

**Aggregated** 在同一个 worker 中运行两个阶段，依靠 continuous batching（in-flight batching）把新的 Prefill 与进行中的 Decode 交错执行。

**Disaggregated** 把两个阶段拆到独立的 worker 池。Prefill worker 处理输入，并把 KV Cache 交给负责 token 生成的 Decode worker。

两种模式计算 GPU 数量的方式不同。一个 Aggregated 副本就是一个 worker。一个 Disaggregated 副本是最小可扩展单元 `xPyD`，即 `x` 个 Prefill worker 加 `y` 个 Decode worker，因此它的 GPU 数是两个池之和，这个单元比 Aggregated worker 更大、更难拆分。它的吞吐由较慢的池决定；第 4.4 节给出配对两个池时上游使用的速率匹配算术和标定系数。实际后果是：`xPyD` 配比失衡时，较快一侧的 GPU 会被浪费。

| 对比项 | Aggregated | Disaggregated |
|---|---|---|
| 架构复杂度 | 较低 | 较高：KV Cache 传输加两池调度 |
| KV Cache 传输 | 无 | 两个池之间必须传输 |
| 独立扩缩容 | 不支持，两个阶段耦合 | 支持，Prefill 与 Decode 分别扩缩 |
| TPOT 稳定性 | 长 Prefill 会干扰 Decode | Decode 池不被打断 |
| 最小部署单元 | 小 worker，易于复制 | 整个 `xPyD` 副本 |
| 池配比调优 | 不涉及 | 必须调，否则较快的池空转 |

两种模式都不是普遍更优。第 6.2 节显示，同一模型、同样的 GPU 数量，只要工作负载特征改变，结论就会反转；这正是服务模式应当是搜索结果而不是既定偏好的原因。

## 4. AIConfigurator 怎样算出评估结果

### 4.1 GPU 工作发生在构建性能数据库时

AIConfigurator 上游的数据采集流程会在目标 GPU 与后端组合上测量 GEMM、注意力、MoE、AllReduce、AllGather、AllToAll 和点对点通信等算子。得到的性能数据被打包，供后续搜索使用。

### 4.2 普通配置搜索在 CPU 上运行

对于受支持的模型/系统/后端组合，用户侧搜索会读取模型元数据，查询打包的性能数据，对受支持的形状做插值，组合出迭代与服务行为，过滤不可行候选，再对其余候选排序。这条路径不加载模型权重。

![AIConfigurator 官方工作流](images/aic-workflow-official.png)

**图 2：取自 arXiv:2601.06288v1 的 AIConfigurator 官方工作流。** 观察从 PerfDatabase 和 TaskRunner，经 InferenceSession 和 Pareto Analyzer，到 Generator 的递进。[公开来源](https://arxiv.org/html/2601.06288v1/AIC_assets/AIC-Workflow.png)。图片 SHA-256：`ee1db977c816218ca0cb6b8e3eff6237c1dd55051d507f0e5579d5b08012bc0f`。

### 4.3 哪些数值是实测，哪些是预测

打包的性能数据库包含上游在指定 GPU 和后端上采集的实测数据。本仓库公开的 TTFT、TPOT、吞吐、显存、副本数和总 GPU 数，是 AIConfigurator 根据这些数据库实测值和声明的输入计算出的输出。这条评估路径不需要模型权重，也不需要目标 GPU。

### 4.4 实际执行路径、目标函数与标定系数

以下陈述读自固定标签 [`v0.11.0`](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0)（commit `614b9c8c8725332533616786e2eb049df48935f0`），包括同一仓库 `aic-core/` 目录下随附的 `aiconfigurator-core` 包；没有读默认分支。本仓库的每次 `cli default` 运行都执行：

```text
aiconfigurator cli default
  -> Task.run()                                        sdk/task_v2.py；autoscale 保持 False，cli/main.py 从不设置它
  -> sweep_agg() / sweep_disagg()                      sdk/sweep.py
  -> predict_agg_worker() / predict_disagg_worker()    sdk/predict.py
  -> AnalyticPredictor                                 sdk/predictor.py；唯一实现
  -> backend.run_agg() / backend.run_static()          aic-core/.../backends/base_backend.py
  -> 逐算子查 PerfDatabase，按步求和
  -> SLA 过滤 -> 按 tokens/s/gpu 排序
```

`AnalyticPredictor` 自述为 "steady-state analytic predictions (zero-queue)"，即稳态、零排队的解析预测。`sweep.py` 的模块文档写明：sweep 返回的是满足 SLA 的候选集而不是 Pareto 前沿，前沿是下游的绘图视图；选优靠排序加分组。这条路径上没有离散事件仿真、排队论求解器或机器学习模型。两种服务模式走不同分支：

| 已公开的行 | 分支 | 逐点预测调用 |
|---|---|---|
| 交互式 Chat 16 卡、Coding Agent 32 卡 | `sweep_agg` | `run_agg`，解析式 in-flight batching 单步模型 |
| Coding Agent 16 卡 | `sweep_disagg` | Prefill 用 `run_static(mode="static_ctx")`，Decode 用 `run_static(mode="static_gen")`，然后做速率匹配 |

**Aggregated 分支。** 对每个枚举出的并行布局、batch size `b` 和分块大小 `ctx_tokens`，`run_agg` 把逐算子时延求和成一个 Prefill 与 Decode 混合步和一个纯 Decode 步，然后：

```text
ttft = (prefill_step_ms x ceil(isl / ctx_tokens) + dispatch_overhead_ms) x queuing_factor(b, steps_to_finish_ctx)
tpot = 混合步与纯 Decode 步时延按步数加权的平均值
仅当 tpot <= TPOT_SLA 且 ttft <= TTFT_SLA 时保留该点                     sweep.py, sweep_agg
保留的点按 tokens/s/gpu 排序
```

`dispatch_overhead_ms`、`queuing_factor` 和吞吐上限是 `base_backend.py` 中的后端钩子；vLLM 与 TensorRT-LLM 子类用下表列出的常数覆盖它们。

**Disaggregated 分支。** 对一个 Prefill worker 数为 `n_p`、Decode worker 数为 `n_d`、单 worker 请求率为 `R_p`、`R_d`、单 worker GPU 数为 `G_p`、`G_d` 的候选，`sweep.py`（`_match_workers`、`_rate_match_dict`、`_find_best_disagg_under_constraint`）计算：

```text
seq_s        = min(0.90 x n_p x R_p, 0.92 x n_d x R_d)
total_gpus   = n_p x G_p + n_d x G_d
tokens/s/gpu = seq_s x OSL / total_gpus

目标：   max tokens/s/gpu
约束：   1.8 x (1.1 x 算子级 Prefill TTFT) < TTFT_SLA
         1.08 x 算子级 Decode TPOT < TPOT_SLA
         total_gpus 属于允许的预算
         权重与 KV Cache 装进 GPU 显存
```

触及已公开各行的每个常数，按所属层分组：

| 层 | 常数 | 源码路径与符号 | 源码怎么说 |
|---|---|---|---|
| Disaggregated 速率匹配 | `0.9`、`0.92` | `sdk/picking.py` `_RATE_MATCHING_PREFILL_DEGRADATION_FACTOR`、`_RATE_MATCHING_DECODE_DEGRADATION_FACTOR`；`sdk/sweep.py` 同值镜像；默认值在 `sdk/task_v2.py` 的 `rate_match_prefill_degradation`、`rate_match_decode_degradation` | Prefill 流水线气泡；Decode batch 槽位未饱和；`task_v2.py` 称其为 "Calibrated against silicon (V1 default)" |
| Disaggregated TTFT 预过滤 | `1.8` | `sdk/picking.py` `_AUTOSCALE_TTFT_CORRECTION_FACTOR`；`sdk/task_v2.py` `autoscale_ttft_correction_factor` | 并发 Prefill 排队，本地并发 15 到 20 时按 `lc/20 + 0.95` 估出 |
| Disaggregated 单阶段时延 | `1.1`、`1.08` | `sdk/task_v2.py` `prefill_latency_correction`、`decode_latency_correction`，传给 `run_static(latency_correction_scale)` | 乘在该阶段每个算子的时延上 |
| Aggregated TTFT，vLLM | `1 + log2(b) / 8`，上限 `2.0` | `aic-core/.../backends/vllm_backend.py` `_ttft_queuing_factor` | 按 silicon 语料标定；"improves MAPE from 26.4% to 18.0%" |
| Aggregated TTFT，vLLM | `0.8 ms x num_layers` | `vllm_backend.py` `_prefill_dispatch_overhead_ms` | 内核测量中不存在的 CPU 侧派发开销 |
| Aggregated 吞吐，vLLM | `min(单步吞吐, b x (OSL - 1) x 1000 / request_latency)` | `vllm_backend.py` `_throughput_cap` | 用 Little 定律封顶无法持续的运行点 |
| Aggregated TTFT，TensorRT-LLM | `min(2 + (steps_to_finish_ctx - 3) / 20, 4)` | `base_backend.py` `_ttft_queuing_factor`，`trtllm_backend.py` 未覆盖 | "Legacy heuristic formula" |
| Aggregated TPOT，TensorRT-LLM | `max(1, num_mix_steps - 3)` | `trtllm_backend.py` `_tpot_mix_steps` | 约三步的流水线排空气泡；"empirical correction" |
| 显存装载，H100 配置 | `mem_bw x 0.8`、`3 us`、`other_mem` 3.5 GB、NCCL 342 到 392 MB | `aic-core/.../systems/h100_sxm.yaml` | YAML 中标注为 "nonofficial correction based on observations" |

`autoscale_ttft_correction_factor` 这个名字有误导性：普通的非 autoscale 搜索同样使用它。`_find_best_disagg_under_constraint` 在比较 SLA 之前执行 `ttft = ttft * 1.8`，Disaggregated 结果表报告的就是这一覆盖后的列。因此，两种模式在面对同一上限之前并没有经过同样的 TTFT 算术：vLLM 的 Aggregated 候选按其单步 TTFT 乘 `1 + log2(b)/8` 再加派发开销过滤，Disaggregated 候选按算子级 Prefill TTFT 的 `1.98 倍` 过滤。第 6.2 节的模式对比，比较的是两套标定过的启发式。

**选中的 16 卡各行与日志、CSV 的对账：**

| 步骤 | 日志行、CSV 字段或算术 |
|---|---|
| 候选数 | [`coding-agent-16gpu.log`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/logs/coding-agent-16gpu.log)：Aggregated 211 个结果，Disaggregated 35 个结果 |
| 被跳过的点 | 所有 `moe_tp=8` 组合：`(moe_intermediate_size=1536 / moe_tp_size=8) % weight_block_size=128 != 0` |
| 选中的 Disaggregated 布局 | `(p)workers=2` × 4 卡（`tp1pp1dp4etp4ep1`，`(p)bs=1`）+ `(d)workers=1` × 8 卡（`tp1pp1dp8etp1ep8`，`(d)bs=13`）= 16 卡 |
| 吞吐 | 1,922.34 tokens/s ÷ 16 = 120.15 tokens/s/gpu；3.85 req/s × 500 OSL |
| 报告的 TTFT | 2,037.14 ms 已包含 1.1 和 1.8 两个系数；2,037.14 / 1.98 = 1,029 ms 是反推得到的算子级估计，不是日志值 |
| 请求时延 | 2,037.14 + 49.874 × 499 = 26,924.27 ms，与 CSV 一致；README 把 TPOT 四舍五入为 49.87 |
| SLA | 通过的原因是 `2037.14 < 4000`；OSL 不参与 TTFT 过滤 |
| Chat 的 Aggregated 行 | CSV 中 `bs=28`、`num_ctx_reqs=1`、`num_gen_reqs=27`，与 vLLM 一次只做一个部分 Prefill 的调度一致；其 466.36 ms TTFT 含约 1.60 的排队系数 `1 + log2(28)/8`，以及 94 层 × 0.8 ms 约 75 ms 的派发开销。两个值都由公式和公开模型配置推导而来，并非日志记录 |
| FP8 回退 | Disaggregated CSV 中的 `(p)fmha=bfloat16` 和 Aggregated CSV 中的 `fmha=bfloat16` 记录了日志警告所述的 BF16 回退 |

**从源码和日志确认的建模局限：**

1. 组合假设：系统时延由算子实测值相加与插值近似得到；算子融合、重叠、争用和调度交互只得到部分体现。
2. 零排队的基础预测器加启发式修正：`AnalyticPredictor` 是稳态模型；排队只通过 Aggregated 分支的 `_ttft_queuing_factor` 和 Disaggregated 分支的 1.8 系数进入，两者都不是排队模型的解。
3. 模式过滤不对称：两个分支在同一上限前施加不同的 TTFT 修正，因此模式排名是两套启发式之间的排名。
4. 有限搜索网格："最优"只是枚举的 TP/DP/ETP/EP/batch/worker 组合中的最优。
5. 被跳过的候选：`sweep_agg` 与 `_get_disagg_worker_candidates` 捕获 `Exception` 后记日志继续；日志显示 8 个 MoE 组合被移除。
6. 数据覆盖缺口：H100/vLLM 0.24.0 没有 FP8 `context_attention` 数据，回退到 BF16 FMHA。
7. 版本分裂：搜索使用 vLLM 性能数据库 0.24.0；未传入 `--generated-config-version`，生成器因此按 Dynamo 1.2.0 的映射默认到 vLLM 0.20.1。
8. `SILICON` 约束的是输入数据的类别，不是逐点的行来源；公开证据包没有记录选中点用到了哪些采样行。
9. Pareto 不是选择器：前沿是绘图视图；选优靠 SLA 过滤加排序分组。
10. 目标函数窄且依赖配置常数：tokens/s/gpu 不含采购价格、功耗、故障、滚动升级容量和运维余量，显存装载边界依赖配置文件中 3.5 GB 的预留常数，而不是实测的分配器占用。

## 5. 完整复现一次 CPU 离线预测

本节从检出到校验完整复现 Qwen3-32B/H200 示例。它使用真实的 AIConfigurator CLI，保存 stdout/stderr，不需要 GPU。目标系统名只用于选择打包好的 H200 性能数据，不会分配 H200。

### 5.1 参考运行的时间线

第一次运行完成了搜索阶段：日志中包含 `Experiment disagg completed with 32 results`。下一步在终端渲染 Pareto 图时在 `plotext.plot_size` 处失败，CLI 以退出码 `1` 退出，没有写出完整可复现的结果包。这次运行是诊断证据，不是正式容量结果。

失败由依赖漂移造成：未固定版本的安装拉取了 `plotext 6.0.0`，而 AIConfigurator 0.11.0 调用的是 5.x API。固定 `plotext==5.3.2` 后，同样的模型、工作负载、后端和 SLA 命令以退出码 `0` 完成；只有这次重跑提供正式结果。

| 阶段 | 实际结果 | 完整 CLI 记录 | 完成标准 |
|---|---|---|---|
| 支持性预检 | PASS，退出码 `0` | [`01-support.log`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/01-support.log) | Aggregated 与 Disaggregated 都报告 `YES` |
| 第一次运行：搜索完成，终端绘图失败 | FAIL，退出码 `1`，归类为 `ENVIRONMENT` | [`02-recommend-plotext6-failure.log`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/02-recommend-plotext6-failure.log) | 日志显示 `Experiment disagg completed with 32 results`，随后在 `plotext.plot_size` 报错 |
| 仅固定依赖 | 固定 `plotext==5.3.2`；模型、工作负载、后端和 SLA 全部不变 | [`requirements-repro.txt`](requirements-repro.txt) | 安装的版本打印为 `5.3.2` |
| 同一命令原样重跑 | PASS，退出码 `0` | [`03-recommend-success.log`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/03-recommend-success.log) | Top 结果为 Aggregated 32 张 H200、Disaggregated 34 张 H200 |

完整的阶段 argv、时间戳、源哈希、公开哈希和脱敏次数在 [`run-manifest.json`](evidence/runs/qwen3-32b-h200-trtllm-50rps/run-manifest.json) 中。

### 5.2 第 0 步：确认执行边界

使用 Linux x86-64、glibc 2.28 或更新版本，以及 Python 3.11。记录的运行使用 Ubuntu 24.04、glibc 2.39 和 Python 3.11.15。安装软件包和解析未缓存的模型元数据时需要网络。不需要 CUDA、模型服务或 GPU 访问。

```bash
uname -m
ldd --version | head -n 1
python3.11 --version
```

输出的大致形式：

```text
x86_64
ldd (Ubuntu GLIBC ...) 2.39
Python 3.11.x
```

**完成标准：** 架构为 `x86_64`，glibc 不低于 2.28，Python 为 3.11。

### 5.3 第 1 步：检出仓库并拉取证据

CSV 证据用 Git LFS 存储。运行校验器前先拉取它。

```bash
git lfs version
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
git -C david-share sparse-checkout set \
  Deep-Learning/OSS-Model-Capacity-Planning-on-NVIDIA-GPUs
git -C david-share lfs pull \
  --include="Deep-Learning/OSS-Model-Capacity-Planning-on-NVIDIA-GPUs/evidence/**"
cd david-share/Deep-Learning/OSS-Model-Capacity-Planning-on-NVIDIA-GPUs
```

**完成标准：** `README.md`、`requirements-repro.txt`、`tools/` 和 `evidence/runs/` 下的三个目录都存在；CSV 包含数据而不是 LFS pointer 文本。

### 5.4 第 2 步：创建固定版本的环境

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --no-input -r requirements-repro.txt
python - <<'PY'
from importlib.metadata import version

for package in ("aiconfigurator", "aiconfigurator-core", "plotext"):
    print(f"{package}={version(package)}")
PY
```

预期版本：

```text
aiconfigurator=0.11.0
aiconfigurator-core=0.11.0
plotext=5.3.2
```

为什么必须固定 `plotext`：不加约束的安装选择了 6.0.0。搜索完成了，但渲染随后失败：

```text
AttributeError: module 'plotext' has no attribute 'plot_size'
EXIT_CODE=1
```

这就是已保存的[`首次失败`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/02-recommend-plotext6-failure.log)记录，不是假设性的排障说明。干净复现从修正后的固定版本开始，不会刻意重现该失败。

只记录了这三个直接固定版本。传递依赖在安装时解析，之后的上游发布可能使它们变化；如果需要完整锁定，请在日志旁保存 `pip freeze`。

**完成标准：** 三个软件包版本与上方代码块逐项一致。

### 5.5 第 3 步：运行支持性预检并保存日志

```bash
set -o pipefail
mkdir -p run-output/logs
support_log=run-output/logs/01-support.log
printf 'START_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$support_log"
aiconfigurator cli support \
  --model-path Qwen/Qwen3-32B-FP8 \
  --system h200_sxm \
  --backend trtllm \
  --no-color 2>&1 | tee -a "$support_log"
support_rc=${PIPESTATUS[0]}
printf 'EXIT_CODE=%s\nEND_UTC=%s\n' \
  "$support_rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$support_log"
test "$support_rc" -eq 0
```

参考 CLI 输出：

```text
Model:           Qwen/Qwen3-32B-FP8
System:          h200_sxm
Backend:         trtllm
Aggregated Support:    YES
Disaggregated Support: YES
EXIT_CODE=0
```

完整内容见[`支持性预检日志`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/01-support.log)。

**完成标准：** 两种支持模式都是 `YES`，捕获的退出码为 `0`。如果支持结果为 `NO`，在此停止；不要把换后端或换数据库模式重新解释为同一次运行。

### 5.6 第 4 步：运行推荐命令并保存日志

```bash
recommend_log=run-output/logs/02-recommend.log
printf 'START_UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$recommend_log"
aiconfigurator cli recommend \
  --model-path Qwen/Qwen3-32B-FP8 \
  --system h200_sxm \
  --backend trtllm \
  --target-request-rate 50 \
  --isl 4000 \
  --osl 1000 \
  --ttft 2000 \
  --tpot 30 \
  --database-mode SILICON \
  --strict-sla \
  --top-n 5 \
  --save-dir ./run-output/results \
  --no-color 2>&1 | tee -a "$recommend_log"
recommend_rc=${PIPESTATUS[0]}
printf 'EXIT_CODE=%s\nEND_UTC=%s\n' \
  "$recommend_rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$recommend_log"
test "$recommend_rc" -eq 0
```

参考 CLI 结果：

```text
Target Load: 50.0 req/s
agg GPUs needed: 32 (replicas: 32)
disagg GPUs needed: 34 (replicas: 17)
Best Experiment Chosen: agg
Request Rate: 50.53 req/s
TTFT: 1114.22ms
TPOT: 29.66ms
EXIT_CODE=0
```

完整的[`成功推荐日志`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/03-recommend-success.log)还保留了每一行 Top-N 和版本告警。搜索使用 TensorRT-LLM 性能数据库 `1.3.0rc10`；生成的配置通过 Dynamo 1.2.0 默认映射到 TensorRT-LLM `1.3.0rc14`，工具报告没有该版本专用的 CLI 模板。在版本对齐且运行时接受它之前，把 YAML 当作候选。

**完成标准：** 命令退出码为 `0`，`agg/` 和 `disagg/` 结果都存在，所选候选满足声明的请求率、TTFT 和 TPOT 约束。

### 5.7 第 5 步：检查生成的证据

AIConfigurator 会在 `run-output/results` 下创建一个模型专属目录。下面的检查会找到该目录，校验两种模式的 Top-1 行，并打印容量算术：

```bash
python - <<'PY'
import csv
from pathlib import Path

root = Path("run-output/results")
expected = {"agg": 32, "disagg": 34}
for mode, expected_gpus in expected.items():
    paths = list(root.rglob(f"{mode}/best_config_topn.csv"))
    assert len(paths) == 1, (mode, paths)
    with paths[0].open(newline="") as handle:
        row = next(csv.DictReader(handle))
    replicas = int(row["replicas_needed"])
    gpus_per_replica = int(row["num_total_gpus"])
    total_gpus = int(row["total_gpus_needed"])
    cluster_rate = float(row["request_rate"]) * replicas
    assert replicas * gpus_per_replica == total_gpus == expected_gpus
    assert cluster_rate >= 50
    assert float(row["ttft"]) <= 2000
    assert float(row["tpot"]) <= 30
    print(
        f"{mode}: GPUs={total_gpus}, replicas={replicas}, "
        f"GPUs/replica={gpus_per_replica}, cluster_req_s={cluster_rate:.2f}, "
        f"TTFT={float(row['ttft']):.2f}ms, TPOT={float(row['tpot']):.2f}ms"
    )
PY
```

预期输出：

```text
agg: GPUs=32, replicas=32, GPUs/replica=1, cluster_req_s=50.53, TTFT=1114.22ms, TPOT=29.66ms
disagg: GPUs=34, replicas=17, GPUs/replica=2, cluster_req_s=51.20, TTFT=537.83ms, TPOT=29.94ms
```

把新文件与已提交的参考证据包比较：

- [`Aggregated Top-N`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/best_config_topn.csv)、[`Pareto 数据`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/pareto.csv)、[`实验配置`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/exp_config.yaml) 和 [`Top-1 候选`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/top1/agg_config.yaml)
- [`Disaggregated Top-N`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/best_config_topn.csv)、[`Pareto 数据`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/pareto.csv)、[`实验配置`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/exp_config.yaml)、[`Prefill 候选`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/top1/prefill_config.yaml) 和 [`Decode 候选`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/top1/decode_config.yaml)

**完成标准：** 脚本打印出两行预期结果，且每个链接的参考文件都能打开。

### 5.8 第 6 步：校验已提交的运行链

```bash
python tools/validate_evidence.py
```

预期终端输出：

```text
RUN qwen3-235b-h100-vllm-50rps PASS files=16
RUN qwen3-235b-h100-vllm-real-workloads PASS files=27
RUN qwen3-32b-h200-trtllm-50rps PASS files=15
README_VALIDATION=PASS LOG_LINKS=9 COMMAND_BLOCKS=10
EVIDENCE_VALIDATION=PASS RUNS=3 PUBLIC_BOUNDARY=PASS
```

校验器重算每个公开文件的 SHA-256，检查每份日志的退出码标记，拒绝私有路径，核对 H200 的 32/34 卡容量算术，确认四卡 MoE 拓扑，检查记录的 CPU 内存峰值，核对真实工作负载的副本算术和 SLA 合规，重新推导 4.75 倍比值，并把第 4.4 节的候选数与选中的 16 卡布局同日志和 CSV 比对。随后检查两份 README 的必需日志链接、相同的命令块、机制标识和已停用短语。

**完成标准：** 最后一行必须严格等于 `EVIDENCE_VALIDATION=PASS RUNS=3 PUBLIC_BOUNDARY=PASS`。

### 5.9 第 7 步：证明校验器能拒绝篡改

```bash
python -m unittest discover -s tests -v
```

测试套件把本目录复制到临时位置，每个测试只做一处篡改，并要求 `validate_evidence.py` 以非零退出码和对应信息拒绝：翻转一个日志字节、伪造 manifest 哈希以掩盖被改动的 CSV 数值、README 中比值漂移、选中布局标识漂移、缺少日志链接、双语命令块漂移、已停用的中文短语，以及日志中的私有路径。未篡改的副本必须仍然通过。不需要 GPU、凭据或网络。

**完成标准：** 全部 9 个测试报告 `ok`，汇总行为 `OK`。

## 6. 完整示例

下面的示例证明同一套规划方法可以表达不同的模型规模、架构、NVIDIA GPU、推理后端和工作负载特征。每个数字都是 AIConfigurator 的预测值，这正是该工具设计要产出的；没有一个是 GPU 基准测试结果。

| 示例 | 模型 | 目标平台 | 后端数据库 | 工作负载 | 主要预测结果 |
|---|---|---|---|---|---|
| Dense 模型示例 | `Qwen/Qwen3-32B-FP8` | H200 SXM | TensorRT-LLM | ISL 4,000；OSL 1,000；TTFT <=2,000 ms；TPOT <=30 ms；50 req/s 采购估算目标 | Aggregated 32 张 H200，Disaggregated 34 张 H200 |
| MoE 工作负载对比 | `Qwen/Qwen3-235B-A22B-FP8` | H100 SXM | vLLM `0.24.0` | 固定 16/32 卡预算；Coding Agent 与 Chat 两种场景 | 同模型同卡数：两种工作负载的每卡吞吐相差 4.75 倍 |

### 6.1 Qwen3-32B-FP8 on H200 SXM

上游的 `support` 和 `recommend` 路径都在 CPU 上完成。在示例工作负载下，Aggregated 的 Top 结果使用 32 个单卡副本；Disaggregated 的 Top 结果使用 17 个副本，每个副本一张 Prefill GPU 加一张 Decode GPU，共 34 张 GPU。

![Qwen3-32B H200 示例](images/qwen3-32b-h200-canary.png)

**图 3：本地 CPU 离线预测，不是 H200 基准测试。** AIConfigurator v0.11.0、Qwen3-32B-FP8、H200 SXM、TensorRT-LLM、50 req/s 采购估算目标。[完整 CLI 日志](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/03-recommend-success.log) · [Aggregated CSV](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/best_config_topn.csv) · [Disaggregated CSV](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/best_config_topn.csv)。图片 SHA-256：`b290bbd126594ca3ac923591b567f6b4cd5e838de6c73ef512405aa3caa08690`。

### 6.2 Qwen3-235B-A22B-FP8 on H100 SXM：工作负载显著改变容量预测

这个示例回答容量规划者真正会问的问题：在固定 GPU 预算下，这个模型能服务多少？它在固定预算下使用两种由作者定义的工作负载场景，而不是一个凭空设定的请求率目标。

| 工作负载场景 | ISL | OSL | 前缀缓存 | TTFT 上限 | TPOT 上限 |
|---|---:|---:|---:|---:|---:|
| 长上下文 Coding Agent | 32,000 | 500 | 28,000（复用率 87.5%） | 4,000 ms | 50 ms |
| 交互式 Chat | 1,000 | 500 | 0 | 500 ms | 50 ms |

Coding Agent 场景模拟的是累积上下文大部分已缓存的 Agent 循环，因此只有很短的尾部需要增量 Prefill。Chat 场景使用公开 AIPerf 示例中的短 ISL/OSL 组合。两者都是为本研究定义的代表性描述，不是来自某个具名客户的采集 trace。

所有运行都使用 `--strict-sla`，因此每个报告的候选都满足两项时延上限。

| 场景 | GPU 预算 | 最佳模式 | 副本布局 | tokens/s/GPU | 集群 req/s | TTFT | TPOT |
|---|---:|---|---|---:|---:|---:|---:|
| Coding Agent | 16 | Disaggregated | 1 × 16 卡副本 | 120.15 | 3.85 | 2,037.14 ms | 49.87 ms |
| Coding Agent | 32 | Aggregated | 8 × 4 卡副本 | 99.75 | 6.40 | 602.91 ms | 48.91 ms |
| 交互式 Chat | 16 | Aggregated | 2 × 8 卡副本 | 570.50 | 18.29 | 466.36 ms | 48.15 ms |

这些预测能够支持、且不超出其证明范围的三条结论：

1. **在这个同模型、同预算的对比中，工作负载输入显著改变容量结果。** 同样 16 卡预算下，Chat 场景预测 570.50 tokens/s/GPU，Coding Agent 场景预测 120.15 tokens/s/GPU，相差 4.75 倍。因此容量结果必须写明其工作负载和 SLA 输入。
2. **推荐的服务模式随声明的工作负载改变。** 在这些输入下，16 卡 Coding Agent 场景中 Disaggregated 预测的每卡吞吐高 1.20 倍，16 卡 Chat 场景中 Aggregated 预测的每卡吞吐高 1.08 倍。服务模式必须保留为搜索变量，而不是固定偏好。
3. **16 卡和 32 卡的 Coding Agent 行不是单变量扩容实验。** 它们分别预测 3.85 和 6.40 集群 req/s、120.15 和 99.75 tokens/s/GPU，但 GPU 预算、服务模式和副本拓扑都变了。这一对比无法分离 GPU 数量对每卡效率的影响。

在同样 16 卡预算下比较两种服务模式，说明了模式为什么不能凭偏好选择。赢家和赢的原因都随工作负载特征改变：

| 工作负载 | 模式 | 副本布局 | tokens/s/GPU | 集群 req/s | TTFT | TPOT |
|---|---|---|---:|---:|---:|---:|
| Chat | Aggregated | 2 × 8 卡 | **570.50** | **18.29** | 466.36 ms | 48.15 ms |
| Chat | Disaggregated | 1 × 16 卡 | 528.54 | 16.91 | **292.60 ms** | **41.86 ms** |
| Coding Agent | Aggregated | 4 × 4 卡 | 99.75 | 3.20 | **602.91 ms** | 48.91 ms |
| Coding Agent | Disaggregated | 1 × 16 卡 | **120.15** | **3.85** | 2,037.14 ms | 49.87 ms |

Chat 场景中，Disaggregated 预测的 TTFT 低 37%，每卡吞吐低 7%。Coding Agent 场景中，它预测的每卡吞吐高 20%，TTFT 更高但仍在 4,000 ms 上限内。这些结果与第 3.5 节的 Prefill/Decode 取舍一致，但不能分离出单一因果机制，因为选中的副本拓扑和调度配置也不同。

容量表的证据：

| 场景 | 完整 CLI 日志 | 候选排序结果 |
|---|---|---|
| Coding Agent，16 卡 | [`coding-agent-16gpu.log`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/logs/coding-agent-16gpu.log) | [Disaggregated CSV](evidence/runs/qwen3-235b-h100-vllm-real-workloads/results/coding-agent-16gpu/disagg/best_config_topn.csv) |
| Coding Agent，32 卡 | [`coding-agent-32gpu.log`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/logs/coding-agent-32gpu.log) | [Aggregated CSV](evidence/runs/qwen3-235b-h100-vllm-real-workloads/results/coding-agent-32gpu/agg/best_config_topn.csv) |
| 交互式 Chat，16 卡 | [`chat-16gpu.log`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/logs/chat-16gpu.log) | [Aggregated CSV](evidence/runs/qwen3-235b-h100-vllm-real-workloads/results/chat-16gpu/agg/best_config_topn.csv) |

阶段命令、argv、源哈希和公开哈希在 [`运行清单`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/run-manifest.json) 中。每个场景都在第 5 节的环境里各自的工作目录中执行；Coding Agent 16 卡的 argv 原样摘自 manifest：

```bash
aiconfigurator cli default \
  --model-path Qwen/Qwen3-235B-A22B-FP8 \
  --total-gpus 16 \
  --system h100_sxm \
  --backend vllm \
  --isl 32000 \
  --osl 500 \
  --prefix 28000 \
  --ttft 4000 \
  --tpot 50 \
  --strict-sla \
  --database-mode SILICON \
  --top-n 3 \
  --save-dir ./results \
  --no-color
```

另外两个场景只改动：32 卡 Coding Agent 运行改为 `--total-gpus 32`；Chat 运行改为 `--isl 1000 --prefix 0 --ttft 500`。`--strict-sla` 只保留同时满足两项时延上限的候选；`--top-n 3` 设定写入 `best_config_topn.csv` 的排序行数。

另一组补充证据包记录了模型的可行性边界和规划器自身的资源开销：

| 步骤 | 结果 | 证据 |
|---|---|---|
| 测试 2 卡预算 | 预期中的边界失败，退出码 `1`；没有候选能装下 | [`01-two-gpu-infeasible.log`](evidence/runs/qwen3-235b-h100-vllm-50rps/logs/01-two-gpu-infeasible.log) |
| 找到最小 worker | 四卡 Aggregated worker，`TP4/PP1/DP1/ETP4/EP1`，退出码 `0` | [`02-four-gpu-worker.log`](evidence/runs/qwen3-235b-h100-vllm-50rps/logs/02-four-gpu-worker.log) · [`Top-N CSV`](evidence/runs/qwen3-235b-h100-vllm-50rps/results/worker-4g/agg/best_config_topn.csv) |
| 测量规划过程的开销 | 12.27 秒墙钟时间，峰值 RSS 496,100 KiB，退出码 `0` | [`04-cpu-memory-profile.log`](evidence/runs/qwen3-235b-h100-vllm-50rps/logs/04-cpu-memory-profile.log) |

这些日志记录的 FP8 context-attention 回退和 0.24.0 与 0.20.1 的版本分裂，在第 4.4 节作为局限 6 和 7 分析；生成的 YAML 在按部署运行时重新生成之前仍是候选。

这些数字没有一个是 Qwen3-235B 的一般容量要求。每个数字都属于一个模型修订系列、目标系统、后端数据库、工作负载特征和 SLA 组合。

## 7. 边界与风险

| 边界 | 含义 |
|---|---|
| 支持矩阵的覆盖随版本而定 | 不支持的组合需要换后端/系统、明确降级到研究模式，或补充新的实测数据 |
| `SILICON` 指的是实测的数据库输入 | 端到端 TTFT、TPOT、显存和吞吐在基准测试前仍是模型计算的输出 |
| 上游已知问题仍指出 vLLM 对齐在进行中 | 把结果当作特定版本的估计 |
| 搜索、生成器和运行时版本可能不同 | 生成的 YAML 在实际运行时接受并提供服务之前只是候选 |
| 一个工作负载点不是流量分布 | 必须为正常、峰值和尾部分组分别重算容量 |
| 预测误差不是运维余量 | 尾时延、突发、故障、启动和升级需要单独预留 |
| Azure 规格覆盖是部分的 | `h100_sxm` 对应 ND H100 v5；NCads H100 v5 使用 H100 NVL 94 GB，v0.11.0 没有它的配置，因此没有任何公开数字适用于 NC 系列规格 |
| 服务模式对比是启发式对启发式 | Aggregated 与 Disaggregated 候选在面对同一上限之前经过不同的 TTFT 修正算术（第 4.4 节） |
| 已提交证据只包含 CPU 离线预测 | 没有任何已提交结果证明 H100/H200 的实机性能或生产容量 |

## 附录 A. 证据与参考资料

### 重建原创图片

制图脚本需要 Python 3.11、Pillow 12.3.0 和 Windows 自带的 Segoe UI 字体。它根据已提交的源码和 CSV 证据重新生成图 1 和图 3。这与第 5 节的 Linux AIConfigurator 环境相互独立。

```powershell
python -m pip install -r requirements.txt
python tools/make_report_figures.py
```

### 已提交证据

- [证据索引](evidence/README.md)
- [Qwen3-32B/H200 完整运行证据包](evidence/runs/qwen3-32b-h200-trtllm-50rps/)
- [Qwen3-235B/H100 补充运行证据包](evidence/runs/qwen3-235b-h100-vllm-50rps/)
- [Qwen3-235B/H100 工作负载对比证据包](evidence/runs/qwen3-235b-h100-vllm-real-workloads/)

校验器、测试、发布脚本和制图脚本及其职责约定见第 2.4 节。

### 公开参考资料

- [AIConfigurator repository](https://github.com/ai-dynamo/aiconfigurator)
- [AIConfigurator v0.11.0 CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md)
- [第 4.4 节读取的 AIConfigurator v0.11.0 源码文件](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0/src/aiconfigurator/sdk)：`sweep.py`、`picking.py`、`task_v2.py`、`predict.py`、`predictor.py`；以及 [`aic-core`](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0/aic-core/src/aiconfigurator_core) 下的 `sdk/backends/base_backend.py`、`sdk/backends/vllm_backend.py`、`sdk/backends/trtllm_backend.py`、`systems/h100_sxm.yaml`、`systems/h100_pcie.yaml`
- [AIConfigurator 论文](https://arxiv.org/abs/2601.06288v1)
- [AIConfigurator 支持矩阵](https://ai-dynamo.org/aiconfigurator/support-matrix/)
- [Qwen3-235B-A22B-FP8 模型配置](https://huggingface.co/Qwen/Qwen3-235B-A22B-FP8/blob/main/config.json)
- Microsoft Learn 规格页面：[ND H100 v5](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ndh100v5-series)、[ND H200 v5](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/nd-h200-v5-series)、[NCads H100 v5](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ncadsh100v5-series)
