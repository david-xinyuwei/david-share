# Azure ND/NC H100 上的开源与开放权重模型容量规划

[![AIConfigurator](https://img.shields.io/badge/AIConfigurator-0.11.0-76B900)](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0)
[![Evidence](https://img.shields.io/badge/evidence-CPU--offline%20prediction-087A80)](evidence/)
[![GPU scope](https://img.shields.io/badge/GPU%20scope-H100%20SXM%20%7C%20H200%20SXM-76B900)](https://ai-dynamo.org/aiconfigurator/support-matrix/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB)](requirements-repro.txt)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](../../LICENSE)

> 可复现的 AIConfigurator 容量评估：明确模型、工作负载、服务目标、推理后端和 NVIDIA 平台，在 CPU 上运行官方搜索命令，保存排序后的预测结果和完整证据。

> Author: 魏新宇 (Xinyu Wei)

[English](README.md) | [中文](README-CN.md)

[详细操作](#5-完整复现一次-cpu-离线预测) · [使用的软件](#2-本项目实际使用的软件与方法) · [评估输入](#3-容量评估需要哪些输入) · [示例](#6-完整示例) · [证据](#附录-a-证据与参考资料)

---

## 1. 执行摘要

开源模型和开放权重模型需要多少 GPU，不能只看参数量。模型架构与量化、工作负载特征、时延目标、GPU 拓扑、推理后端和服务模式都会改变答案。

本仓库先把模型、工作负载、目标平台和 SLO 参数固定下来，然后在 CPU 上运行 NVIDIA AIConfigurator 0.11.0 的 `SILICON` 模式。每次运行都保存完整日志、Top-N CSV、Pareto 数据和生成的候选配置，并重算文件哈希和容量算术。这里交付的就是 AIConfigurator 容量预测结果，这正是该工具的用途。

第 6 节的 Qwen 案例说明同一套方法如何处理不同模型和业务场景。它们只是示例，不限定工具的模型范围。在同一模型和 GPU 数量的对比中，工作负载参数会显著改变预测结果：长上下文 Coding Agent 与短上下文 Chat 的每卡吞吐预测相差 4.8 倍。

## 2. 本项目实际使用的软件与方法

### 2.1 已进入本次运行链的软件

| 软件 | 官方地址 | 在本项目中做什么 | 实际使用情况 |
|---|---|---|---|
| NVIDIA AIConfigurator | [GitHub repository](https://github.com/ai-dynamo/aiconfigurator) · [v0.11.0](https://github.com/ai-dynamo/aiconfigurator/tree/v0.11.0) · [CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md) | 性能建模、配置搜索、候选排序和部署配置生成 | 本仓库实际运行的容量评估工具；版本 `0.11.0`，commit `614b9c8c8725332533616786e2eb049df48935f0` |
| vLLM | [GitHub repository](https://github.com/vllm-project/vllm) | 开源推理后端 | 一个本地示例使用其性能数据库；未启动模型服务 |
| TensorRT-LLM | [GitHub repository](https://github.com/NVIDIA/TensorRT-LLM) | NVIDIA 优化的推理后端 | 一个本地示例使用其性能数据库；未启动模型服务 |

AIConfigurator 采用 Apache-2.0 许可证，但其内置性能数据围绕 NVIDIA GPU 和特定推理框架采集，不能把这里的结果直接套用到其他厂商的硬件上。

**方法依据：** [AIConfigurator: Lightning-Fast Configuration Optimization for Multi-Framework LLM Serving, arXiv:2601.06288v1](https://arxiv.org/abs/2601.06288v1) 说明了建模方法、预测准确度、搜索效率和适用范围。

### 2.2 本仓库实际执行的步骤

每组公开结果都按下面五步生成：

| 阶段 | 实际动作 | 输出与证据 |
|---|---|---|
| 1. 固定输入 | 记录模型、ISL/OSL、前缀复用、SLO、目标 GPU、后端版本，以及 GPU 预算或负载目标 | 完整命令行和实验配置 |
| 2. 检查支持情况 | 对需要预检的场景运行官方 `aiconfigurator cli support` | 完整支持性检查日志 |
| 3. 计算容量 | 用 `SILICON` 模式运行官方 `default` 或 `recommend` | Top-N 预测结果、Pareto 数据和生成的候选配置 |
| 4. 整理证据 | 只复制允许公开的日志和机器可读结果，同时记录源文件与公开文件的 SHA-256 | 带版本的运行证据包和 manifest |
| 5. 自动校验 | 重算哈希和容量算术，检查 SLA、私有信息、链接和双语关键事实 | 可重复的校验结果 |

本仓库到容量评估和证据校验为止，不声称部署过模型服务，也不声称跑过 GPU 基准测试。

### 2.3 AIConfigurator 提供什么

输入模型、NVIDIA 系统型号、推理后端、工作负载描述和时延约束后，AIConfigurator 可以：

- 判断候选拓扑能否容纳模型；
- 在适用时搜索张量并行、流水线并行、数据并行、专家并行（EP）和专家张量并行（ETP）；
- 比较 Static、Aggregated 和 Disaggregated 等服务模式；
- 预测 TTFT、TPOT、请求时延、显存和吞吐；
- 在指定约束下对 Pareto 前沿上的候选配置进行排序；
- 按请求率或并发目标计算副本数与总 GPU 数；
- 为支持的运行时和平台生成候选启动脚本与部署配置。

普通配置搜索不会真正运行模型、优化内核、管理集群，也不会自动识别业务负载。本仓库把它输出的预测值作为最终评估结果。

## 3. 容量评估需要哪些输入

容量问题需要同时冻结四组输入和一个决策目标。

![容量规划问题定义](images/configuration-problem.png)

**图 1：原创解释图。** 模型、工作负载、服务目标、后端和硬件共同决定配置搜索。依据：[AIConfigurator CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md) 与 [论文第 4 节](https://arxiv.org/html/2601.06288v1)。图片 SHA-256：`42e48e0571826eb2f5f8457fe0d84e5b28df05f4da1acf2b2b0ab2616cdf868b`。

### 3.1 模型参数

| 字段 | 必须明确的内容 |
|---|---|
| 模型身份 | 精确 Hugging Face ID 或本地模型路径，以及 revision |
| 架构 | Dense 或 MoE、层数、hidden dimensions、Attention 与 expert 结构 |
| 精度 | BF16、FP8、FP4、INT8 或其他精确量化配置 |
| 上下文行为 | 原生 context、RoPE/YaRN、多模态 encoder 输入，以及启用时的 MTP depth |

### 3.2 工作负载参数

| 字段 | 必须明确的内容 |
|---|---|
| 请求长度 | ISL、OSL；多模态请求还需给出图片尺寸和数量；使用 Prefix Cache 时还需给出可复用长度 |
| 到达负载 | 请求率曲线或并发、峰值持续时间和突发行为 |
| 用户行为 | Thinking/Non-thinking 占比、chat template、sampling 和输出 token 的统计方式 |
| 服务目标 | TTFT、TPOT、端到端时延、goodput 和错误率目标 |

生产分析至少要分别评估正常流量、峰值流量和长上下文尾部。单个平均 ISL/OSL 只代表一个典型点，不能代替完整流量分布。

### 3.3 平台参数

| 字段 | 必须明确的内容 |
|---|---|
| GPU | 精确的 NVIDIA 系统型号与显存容量 |
| 节点拓扑 | 每节点 GPU 数、NVLink/NVSwitch domain 和节点间 fabric |
| 后端 | TensorRT-LLM、vLLM 或 SGLang，以及精确版本 |
| 性能数据库 | `SILICON`、`HYBRID` 等模式，以及具体数据库版本 |

### 3.4 搜索空间与输出

搜索空间可包括服务模式、TP/PP/DP/EP/ETP、worker 数、副本数、batch size、KV Cache 分配、chunked prefill 和受支持的运行时参数。输出包含候选配置、预测指标及其排名，不是一个脱离上下文的 GPU 数字。

```text
capacity input  = model definition + workload definition + platform definition
candidate       = serving mode + parallelism + workers + batch/runtime settings
capacity output = ranked candidates + predicted metrics + generated artifacts
```

### 3.5 服务模式：Aggregated 与 Disaggregated 的区别

服务模式是搜索空间中的关键变量，也最容易被误解。两种模式的根本区别如下。

LLM 推理包含两个硬件特征完全相反的阶段：

| 阶段 | 做什么 | 瓶颈 | 计算特征 |
|---|---|---|---|
| Prefill | 对一个请求的完整输入做前向计算并产出第一个 token | 通常是算力 | 大矩阵乘；GPU 利用率取决于请求长度和批处理 |
| Decode | 对每个活跃序列逐步生成后续 token | 通常是显存带宽 | 每个活跃序列每步生成一个 token；需依靠 batch 聚合提高 GPU 利用率 |

矛盾由此产生：一次很长的 Prefill 会占住 GPU，让正在 Decode 的请求排队等待，表现为 TPOT 抖动。

**Aggregated** 让同一个 worker 承担两个阶段，依靠 continuous batching（in-flight batching）把新请求的 Prefill 插入正在进行的 Decode 批次。

**Disaggregated** 把两个阶段拆成独立的 worker 池：Prefill worker 负责处理输入，算完后把 KV Cache 交给 Decode worker，由后者负责 token 生成。

两种模式计算 GPU 数量的方式不同，AIConfigurator 文档给出的算式是：

```text
Aggregated:    gpus/replica = gpus/worker

Disaggregated: gpus/replica = (p)gpus/worker x (p)workers
                            + (d)gpus/worker x (d)workers
```

Disaggregated 的副本是最小可扩展单元 `xPyD`，即 `x` 个 Prefill worker 加 `y` 个 Decode worker。因此它比 Aggregated 的单个 worker 更大，也更难拆分复制。

Disaggregated 的吞吐由两个池中较慢的那个决定。AIConfigurator 在配对两个资源池时，会使用基于 `SILICON` 数据校准的 rate matching 降级系数：

```text
seq/s = min( prefill seq/s x (p)workers x 0.90,
             decode  seq/s x (d)workers x 0.92 )
```

AIConfigurator 源码注释说明，`0.90` 用于估算 Prefill 侧的 pipeline bubble，`0.92` 用于估算 Decode 侧 batch size 未饱和造成的损失。两个系数都可配置。实际含义是：`xPyD` 配比失衡时，较快一侧的 GPU 会空转。

| 对比项 | Aggregated | Disaggregated |
|---|---|---|
| 架构复杂度 | 较低 | 较高：需要 KV Cache 传输和两池调度 |
| KV Cache 传输 | 不需要 | 必须在两个池之间传输 |
| 独立扩缩容 | 不支持，两个阶段绑定 | 支持，Prefill 与 Decode 可分别调整 |
| TPOT 稳定性 | 长 Prefill 会干扰 Decode | Decode 池不被打断 |
| 最小部署单元 | worker 较小，易于复制 | 整个 `xPyD` 副本 |
| 配比调优 | 不涉及 | 必须调，否则较快一侧空转 |

两种模式没有普遍优劣。第 6.2 节的数据显示：同一个模型、同样的 GPU 数量，仅工作负载改变，结论就会反向。所以应根据评估结果选择服务模式，不能事先拍板。

## 4. AIConfigurator 怎样算出评估结果

### 4.1 性能数据库怎样采集

AIConfigurator 的数据采集工具会在指定 GPU 和推理后端上测量 GEMM、Attention、MoE、AllReduce、AllGather、AllToAll 和点对点通信等算子与通信路径的执行时间，再把结果打包成配置搜索所需的性能数据库。

### 4.2 普通配置搜索在 CPU 上运行

对于已有性能数据覆盖的模型、系统型号和后端组合，搜索过程会读取模型元数据，查询打包后的性能数据，对受支持的张量形状做插值，并把单步迭代开销与服务行为组合成端到端预测；随后过滤不可行候选并排序。该路径不会加载模型权重。

![AIConfigurator 官方工作流](images/aic-workflow-official.png)

**图 2：AIConfigurator 官方工作流，取自 arXiv:2601.06288v1。** 图中从 PerfDatabase 与 TaskRunner，经过 InferenceSession 和 Pareto Analyzer，最终进入 Generator。[公开来源](https://arxiv.org/html/2601.06288v1/AIC_assets/AIC-Workflow.png)。图片 SHA-256：`ee1db977c816218ca0cb6b8e3eff6237c1dd55051d507f0e5579d5b08012bc0f`。

### 4.3 哪些数据是实测，哪些数值是预测

AIConfigurator 性能数据库中的基础数据来自指定 GPU 和推理后端。本仓库给出的 TTFT、TPOT、吞吐、显存、副本数和总 GPU 数，则是 AIConfigurator 根据这些基础数据和本次输入参数计算出的评估结果。这条评估路径不需要加载模型权重，也不需要占用目标 GPU。

## 5. 完整复现一次 CPU 离线预测

本节从仓库检出开始，完整复现 Qwen3-32B/H200 示例，直到结果校验结束。全程调用真实 AIConfigurator CLI，并保存 stdout/stderr；不需要 GPU。命令中的 H200 system 只用于选择已打包的 H200 性能数据，不会创建或占用 H200。

### 5.1 先看参考运行的完整过程

首次运行完成了搜索阶段，日志中已经出现 `Experiment disagg completed with 32 results`。随后，程序在把 Pareto 图画到终端时调用 `plotext.plot_size` 失败，CLI 以退出码 `1` 结束，也没有写出完整、可复现的结果包。因此，这次运行只能用来排查故障，不能作为正式容量结果。

根因是依赖版本漂移：未固定版本时安装了 `plotext 6.0.0`，而 AIConfigurator 0.11.0 调用的是 5.x API。把依赖固定为 `plotext==5.3.2` 后，模型、工作负载、后端和 SLA 参数完全不变，原命令以退出码 `0` 跑通；正式结果来自这次重跑。

| 阶段 | 实际结果 | 完整 CLI 记录 | 完成标准 |
|---|---|---|---|
| 支持性预检 | PASS，退出码 `0` | [`01-support.log`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/01-support.log) | Aggregated 和 Disaggregated 都返回 `YES` |
| 第一次运行：搜索完成，终端绘图失败 | FAIL，退出码 `1`，归类为 `ENVIRONMENT` | [`02-recommend-plotext6-failure.log`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/02-recommend-plotext6-failure.log) | 日志里能看到 `Experiment disagg completed with 32 results`，之后在 `plotext.plot_size` 报错 |
| 只改依赖版本 | 固定 `plotext==5.3.2`；模型、工作负载、后端和 SLA 全部不动 | [`requirements-repro.txt`](requirements-repro.txt) | 安装后版本输出为 `5.3.2` |
| 原命令原样重跑 | PASS，退出码 `0` | [`03-recommend-success.log`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/03-recommend-success.log) | Top-1 为 Aggregated 32 张 H200、Disaggregated 34 张 H200 |

[`run-manifest.json`](evidence/runs/qwen3-32b-h200-trtllm-50rps/run-manifest.json) 记录了每个阶段的完整 argv、时间戳、源文件 SHA、公开文件 SHA 和脱敏次数。

### 5.2 第 0 步：确认执行环境

使用 Linux x86-64、glibc 2.28 或更高版本，以及 Python 3.11。参考运行的环境是 Ubuntu 24.04、glibc 2.39、Python 3.11.15。首次安装软件包和解析未缓存的模型元数据时需要网络；不需要 CUDA、模型服务或 GPU。

```bash
uname -m
ldd --version | head -n 1
python3.11 --version
```

输出大致如下：

```text
x86_64
ldd (Ubuntu GLIBC ...) 2.39
Python 3.11.x
```

**完成标准：** 架构为 `x86_64`，glibc 不低于 2.28，Python 为 3.11。

### 5.3 第 1 步：检出仓库并拉取证据文件

CSV 证据由 Git LFS 管理。运行 `tools/validate_evidence.py` 前，必须先拉取 LFS 文件内容。

```bash
git lfs version
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
git -C david-share sparse-checkout set \
  Deep-Learning/OSS-Model-Capacity-Planning-on-NVIDIA-GPUs
git -C david-share lfs pull \
  --include="Deep-Learning/OSS-Model-Capacity-Planning-on-NVIDIA-GPUs/evidence/**"
cd david-share/Deep-Learning/OSS-Model-Capacity-Planning-on-NVIDIA-GPUs
```

**完成标准：** `README.md`、`requirements-repro.txt`、`tools/` 和 `evidence/runs/` 下的三个 run 目录都存在；打开 CSV 时看到实际表格内容，而不是 LFS pointer 文本。

### 5.4 第 2 步：创建固定版本的 Python 环境

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

版本输出必须是：

```text
aiconfigurator=0.11.0
aiconfigurator-core=0.11.0
plotext=5.3.2
```

为什么必须固定 `plotext`：参考运行最初自动安装了 6.0.0。搜索阶段已经完成，但 CLI 在写出完整报告前失败：

```text
AttributeError: module 'plotext' has no attribute 'plot_size'
EXIT_CODE=1
```

这不是假设的故障排查说明，而是已经保存的[`首次失败日志`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/02-recommend-plotext6-failure.log)。干净复现直接使用修正后的依赖，不需要故意重现失败。

**完成标准：** 三个软件包版本与上方输出逐项一致。

### 5.5 第 3 步：执行支持性预检并保存日志

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

参考输出：

```text
Model:           Qwen/Qwen3-32B-FP8
System:          h200_sxm
Backend:         trtllm
Aggregated Support:    YES
Disaggregated Support: YES
EXIT_CODE=0
```

完整输出见[`支持性预检日志`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/01-support.log)。

**完成标准：** 两种服务模式都返回 `YES`，捕获的退出码为 `0`。如果返回 `NO`，应在这里停止；换后端或换数据库模式属于另一组实验，不能冒充同一次复现。

### 5.6 第 4 步：执行容量搜索并保存日志

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

参考结果：

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

完整的[`成功日志`](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/03-recommend-success.log)还保留了所有 Top-N 行和版本告警。本次搜索使用 TensorRT-LLM `1.3.0rc10` 性能数据库；生成配置通过 Dynamo 1.2.0 默认映射到 TensorRT-LLM `1.3.0rc14`，工具还提示缺少该版本专用的 CLI 模板。因此，在对齐版本并让真实运行时成功读取之前，YAML 只能作为候选配置。

**完成标准：** 命令退出码为 `0`，同时生成 `agg/` 和 `disagg/` 结果，所选候选满足请求率、TTFT 与 TPOT 约束。

### 5.7 第 5 步：检查 Top-1 数据与容量算术

AIConfigurator 会在 `run-output/results` 下再生成一层包含模型名的目录。下面的检查会找到这层目录，读取两种模式的 Top-1，并重新计算总 GPU 数：

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

将新结果与仓库中的参考证据逐项比较：

- Aggregated：[`Top-N`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/best_config_topn.csv)、[`Pareto 数据`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/pareto.csv)、[`实验配置`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/exp_config.yaml)、[`Top-1 候选配置`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/top1/agg_config.yaml)
- Disaggregated：[`Top-N`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/best_config_topn.csv)、[`Pareto 数据`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/pareto.csv)、[`实验配置`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/exp_config.yaml)、[`Prefill 候选配置`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/top1/prefill_config.yaml)、[`Decode 候选配置`](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/top1/decode_config.yaml)

**完成标准：** 检查脚本打印出上面两行结果，且所有参考证据链接均可打开。

### 5.8 第 6 步：校验仓库中的完整证据链

```bash
python tools/validate_evidence.py
```

预期终端输出：

```text
RUN qwen3-235b-h100-vllm-50rps PASS files=16
RUN qwen3-235b-h100-vllm-real-workloads PASS files=27
RUN qwen3-32b-h200-trtllm-50rps PASS files=15
README_VALIDATION=PASS LOG_LINKS=9 COMMAND_BLOCKS=8
EVIDENCE_VALIDATION=PASS RUNS=3 PUBLIC_BOUNDARY=PASS
```

校验脚本会重算每个公开文件的 SHA-256，检查日志退出码；发现本地私有路径就报错；同时重算 H200 的 32/34 卡结果，核对四卡 MoE 拓扑、CPU 内存峰值，以及三个工作负载场景的副本数量和 SLA。

**完成标准：** 最后一行必须严格等于 `EVIDENCE_VALIDATION=PASS RUNS=3 PUBLIC_BOUNDARY=PASS`。

## 6. 完整示例

下面的示例说明同一套方法如何处理不同的模型规模、架构、NVIDIA GPU、推理后端和工作负载场景。所有数字都是 AIConfigurator 的预测值，这正是该工具的用途；它们都不是本仓库在 GPU 上测得的结果。

| 示例 | 模型 | 目标平台 | 后端性能数据库 | 工作负载 | 主要预测结果 |
|---|---|---|---|---|---|
| Dense 模型示例 | `Qwen/Qwen3-32B-FP8` | H200 SXM | TensorRT-LLM | ISL 4,000；OSL 1,000；TTFT <=2,000 ms；TPOT <=30 ms；按 50 req/s 做采购估算 | Aggregated 需要 32 张 H200；Disaggregated 需要 34 张 H200 |
| MoE 模型工作负载对比 | `Qwen/Qwen3-235B-A22B-FP8` | H100 SXM | vLLM `0.24.0` | 固定 16/32 卡预算；Coding Agent 与 Chat 两种场景 | 同模型同卡数下，两种工作负载的每卡吞吐相差 4.8 倍 |

### 6.1 Qwen3-32B-FP8 on H200 SXM

AIConfigurator 的 `support` 和 `recommend` 命令都在 CPU 上完成。在示例工作负载下，Aggregated Top-1 使用 32 个单卡副本；Disaggregated Top-1 使用 17 个副本，每个副本由 1 张 Prefill GPU 与 1 张 Decode GPU 组成，共 34 张 GPU。

![Qwen3-32B H200 示例](images/qwen3-32b-h200-canary.png)

**图 3：本地 CPU 离线预测，不是 H200 实机基准测试。** AIConfigurator v0.11.0、Qwen3-32B-FP8、H200 SXM、TensorRT-LLM，按 50 req/s 做采购估算。[完整 CLI 日志](evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/03-recommend-success.log) · [Aggregated CSV](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/agg/best_config_topn.csv) · [Disaggregated CSV](evidence/runs/qwen3-32b-h200-trtllm-50rps/results/disagg/best_config_topn.csv)。图片 SHA-256：`b290bbd126594ca3ac923591b567f6b4cd5e838de6c73ef512405aa3caa08690`。

### 6.2 Qwen3-235B-A22B-FP8 on H100 SXM：工作负载显著影响容量预测

这个示例回答一个直接问题：给定固定 GPU 预算，这个模型能支撑多少业务量。评估采用两种常见工作负载场景，而不是凭空设定一个请求率目标。

| 工作负载场景 | ISL | OSL | Prefix Cache | TTFT 上限 | TPOT 上限 |
|---|---:|---:|---:|---:|---:|
| 长上下文 Coding Agent | 32,000 | 500 | 28,000（复用率 87.5%） | 4,000 ms | 50 ms |
| 交互式 Chat | 1,000 | 500 | 0 | 500 ms | 50 ms |

Coding Agent 场景的典型特征是累积上下文很长，但绝大部分前缀已经缓存，只有少量新增内容需要执行 Prefill。这两组参数用于表示典型场景，不是从某个具名客户的生产 trace 中提取的。

三次运行都启用了 `--strict-sla`，因此表中每个候选都同时满足两项时延约束。

| 场景 | GPU 预算 | 推荐模式 | 副本结构 | tokens/s/GPU | 集群 req/s | TTFT | TPOT |
|---|---:|---|---|---:|---:|---:|---:|
| Coding Agent | 16 | Disaggregated | 1 个 16 卡副本 | 120.15 | 3.85 | 2,037.14 ms | 49.87 ms |
| Coding Agent | 32 | Aggregated | 8 个 4 卡副本 | 99.75 | 6.40 | 602.91 ms | 48.91 ms |
| 交互式 Chat | 16 | Aggregated | 2 个 8 卡副本 | 570.50 | 18.29 | 466.36 ms | 48.15 ms |

这组预测能直接支持三条结论：

1. **在同一个模型、相同 GPU 预算下，工作负载参数会显著改变容量结果。** 同样 16 张卡，Chat 场景预测每卡 570.50 tokens/s，Coding Agent 场景只有 120.15 tokens/s，相差 4.8 倍。因此，发布容量结果时必须同时写明工作负载和 SLA 参数。
2. **推荐的服务模式会随工作负载改变。** 按本次输入，16 卡 Coding Agent 场景中 Disaggregated 的每卡吞吐高 1.20 倍；16 卡 Chat 场景中 Aggregated 的每卡吞吐高 1.08 倍。服务模式必须作为搜索变量，不能预先固定。
3. **16 卡与 32 卡的 Coding Agent 结果不是单变量扩容实验。** 两者预测的集群吞吐分别为 3.85 和 6.40 req/s，每卡吞吐分别为 120.15 和 99.75 tokens/s，但 GPU 预算、服务模式和副本拓扑都发生了变化，不能据此单独推断 GPU 数量对每卡效率的影响。

在同样 16 卡预算下并排比较两种服务模式，可以看到推荐结果会随工作负载改变：

| 工作负载 | 服务模式 | 副本结构 | tokens/s/GPU | 集群 req/s | TTFT | TPOT |
|---|---|---|---:|---:|---:|---:|
| Chat | Aggregated | 2 个 8 卡副本 | **570.50** | **18.29** | 466.36 ms | 48.15 ms |
| Chat | Disaggregated | 1 个 16 卡副本 | 528.54 | 16.91 | **292.60 ms** | **41.86 ms** |
| Coding Agent | Aggregated | 4 个 4 卡副本 | 99.75 | 3.20 | **602.91 ms** | 48.91 ms |
| Coding Agent | Disaggregated | 1 个 16 卡副本 | **120.15** | **3.85** | 2,037.14 ms | 49.87 ms |

Chat 场景中，Disaggregated 预测的 TTFT 低 37%，每卡吞吐低 7%；Coding Agent 场景中，它预测的每卡吞吐高 20%，TTFT 更高但仍在 4,000 ms 限制内。这些结果与第 3.5 节所述 Prefill/Decode 取舍一致，但不能用来证明某一个单独机制，因为两组结果采用的副本拓扑和调度配置也不同。

容量表对应的证据：

| 场景 | 完整 CLI 日志 | 候选排序结果 |
|---|---|---|
| Coding Agent，16 卡 | [`coding-agent-16gpu.log`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/logs/coding-agent-16gpu.log) | [Disaggregated CSV](evidence/runs/qwen3-235b-h100-vllm-real-workloads/results/coding-agent-16gpu/disagg/best_config_topn.csv) |
| Coding Agent，32 卡 | [`coding-agent-32gpu.log`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/logs/coding-agent-32gpu.log) | [Aggregated CSV](evidence/runs/qwen3-235b-h100-vllm-real-workloads/results/coding-agent-32gpu/agg/best_config_topn.csv) |
| 交互式 Chat，16 卡 | [`chat-16gpu.log`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/logs/chat-16gpu.log) | [Aggregated CSV](evidence/runs/qwen3-235b-h100-vllm-real-workloads/results/chat-16gpu/agg/best_config_topn.csv) |

每个阶段的完整命令、argv、源文件 hash 和公开文件 hash 记录在 [`运行清单`](evidence/runs/qwen3-235b-h100-vllm-real-workloads/run-manifest.json)。

另一组补充证据记录了模型的可行性边界和规划器自身的资源开销：

| 步骤 | 结果 | 证据 |
|---|---|---|
| 以 2×H100 为 GPU 预算做可行性测试 | 退出码 `1`；所有候选都因显存不足被淘汰 | [`01-two-gpu-infeasible.log`](evidence/runs/qwen3-235b-h100-vllm-50rps/logs/01-two-gpu-infeasible.log) |
| 查找最小 worker | 四卡 Aggregated worker，`TP4/PP1/DP1/ETP4/EP1`，退出码 `0` | [`02-four-gpu-worker.log`](evidence/runs/qwen3-235b-h100-vllm-50rps/logs/02-four-gpu-worker.log) · [`Top-N CSV`](evidence/runs/qwen3-235b-h100-vllm-50rps/results/worker-4g/agg/best_config_topn.csv) |
| 测量规划进程开销 | 运行 12.27 秒，峰值 RSS 为 496,100 KiB，退出码 `0` | [`04-cpu-memory-profile.log`](evidence/runs/qwen3-235b-h100-vllm-50rps/logs/04-cpu-memory-profile.log) |

日志中有两项会影响结果适用范围的警告。第一，vLLM `0.24.0` 在 H100 SXM 上没有 FP8 `context_attention` 性能数据，因此搜索回退到 BF16 FMHA 数据。第二，运行时没有传入 `--generated-config-version`：搜索使用 vLLM `0.24.0` 性能数据库，生成配置则通过 Dynamo 1.2.0 默认映射到 vLLM `0.20.1`。在按目标版本重新生成之前，这些 YAML 只能作为配置建议。

以上数字都不是 Qwen3-235B 的通用容量要求。它们只适用于当前模型版本、目标 GPU、性能数据库版本、工作负载场景和 SLA 约束。

## 7. 适用范围与风险

| 限制 | 对容量决策的影响 |
|---|---|
| 支持矩阵随版本变化 | 不支持的组合需要更换后端或 NVIDIA 系统型号；如果继续探索，必须明确标注为研究模式，或补充新的实测数据 |
| `SILICON` 使用 AIConfigurator 已采集的 GPU 性能数据 | 本仓库中的 TTFT、TPOT、显存和吞吐仍是模型计算值，不是本次 GPU 实测值 |
| AIConfigurator 的已知问题说明 vLLM 数据仍在完善 | 评估结果只适用于当前列出的版本和数据范围 |
| 搜索数据库、配置生成器和目标运行时版本可能不一致 | 生成的 YAML 只能作为配置建议；本仓库没有验证它能在目标运行时启动 |
| 单个工作负载点不是流量分布 | 正常、峰值和尾部流量分组必须分别重算容量 |
| 预测值不包含运维余量 | 尾时延、突发、故障、启动和升级需要单独预留容量 |
| 已提交证据仅包含 CPU 离线预测 | 已提交结果不能证明 H100/H200 实际性能或生产容量 |

## 附录 A. 证据与参考资料

### 重建原创图片

制图脚本需要 Python 3.11、Pillow 12.3.0，以及 Windows 自带的 Segoe UI 字体。脚本根据已提交源码和 CSV 证据重新生成图 1 和图 3。这个环境与第 5 节的 Linux AIConfigurator 环境相互独立。

```powershell
python -m pip install -r requirements.txt
python tools/make_report_figures.py
```

### 已提交证据

- [证据索引](evidence/README.md)
- [Qwen3-32B/H200 完整运行证据包](evidence/runs/qwen3-32b-h200-trtllm-50rps/)
- [Qwen3-235B/H100 补充运行证据包](evidence/runs/qwen3-235b-h100-vllm-50rps/)
- [Qwen3-235B/H100 工作负载对比证据包](evidence/runs/qwen3-235b-h100-vllm-real-workloads/)
- [证据发布与脱敏追溯工具](tools/publish_run_evidence.py)
- [工作负载对比证据发布工具](tools/publish_real_scenario_evidence.py)
- [确定性证据校验脚本](tools/validate_evidence.py)
- [原创制图脚本](tools/make_report_figures.py)

### 公开参考资料

- [AIConfigurator repository](https://github.com/ai-dynamo/aiconfigurator)
- [AIConfigurator v0.11.0 CLI guide](https://github.com/ai-dynamo/aiconfigurator/blob/v0.11.0/docs/cli_user_guide.md)
- [AIConfigurator paper](https://arxiv.org/abs/2601.06288v1)
- [AIConfigurator support matrix](https://ai-dynamo.org/aiconfigurator/support-matrix/)
