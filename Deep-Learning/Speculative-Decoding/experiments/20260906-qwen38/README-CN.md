# Qwen3.8-27B：MTP 与 DFlash 2 实测

同样起草 7 个候选 token，DFlash 2 比模型自带的 MTP 快多少？更快输出的回答，还能答对吗？这次在单张 H100 NVL 上，用同一批代码题和数学题，同时测速度、得分和截断情况。

在三个并发档位、三个随机种子（seed）的九组配对中，DFlash 2 的输出吞吐均高于 MTP7。得分总体接近，但并发 4 的第三次运行里，DFlash 2 的代码题答对 **29/32**，MTP7 为 **31/32**，而且 DFlash 2 做完这一组题更慢。**吞吐优势已经测到，准确率不下降尚未得到证明。**

这是作者在 vLLM 上的部署实测，不是 DFlash 论文的完整复现。正式结果来自同一批 64 题的重复测试；完整题集阶段未执行，详见[测试覆盖](#测试覆盖与未执行项)。

> 作者：魏新宇（Xinyu Wei）

[English](README.md) | [中文](README-CN.md) | [推测解码总览](../../README-CN.md)

[结果](#吞吐与答案质量) · [延迟](#客户端延迟) · [方法](#测试方法) · [覆盖范围](#测试覆盖与未执行项) · [离线复算](#离线复算)

实验日期：2026-09-06。运行标识：`qwen38-quality-20260906`。

---

<a id="s-阶段结果"></a>

## 吞吐与答案质量

使用 32 道 HumanEval+ 代码题和 32 道 MATH-500 数学题，三条路线在并发 1、4、8 下各跑三次，共 27 组。每组都是同一批题，**每类 32 题重复三次，不是 96 道独立题**。

基线不开推测解码；MTP7 和 DFlash 2-7 都起草 7 个候选 token。下表的吞吐和整组耗时分别取三次运行的中位数。得分和截断列的三个数，依次对应 seed **20260906、20260907、20260908**；每个得分的分母都是 32。

![三种路线在并发 1、4、8 下的输出吞吐](images/throughput.png)

*图 1：作者实测。柱形表示三次运行的中位数，误差线表示最小值和最大值，不是置信区间；同一批 64 题，吞吐包含 thinking token。来源：[逐组记录](data/groups.json)。*

<!-- BEGIN RESULT_TABLE -->
### 吞吐与整组耗时

| 并发 | 路线 | 吞吐（tok/s） | 整组耗时（秒） |
| --- | --- | --- | --- |
| 1 | 基线 | 53.40 | 3458.61 |
| 1 | MTP7 | 113.34 | 1591.09 |
| 1 | DFlash 2-7 | 150.51 | 1149.41 |
| 4 | 基线 | 190.08 | 1037.22 |
| 4 | MTP7 | 382.85 | 470.35 |
| 4 | DFlash 2-7 | 451.74 | 377.79 |
| 8 | 基线 | 287.72 | 577.44 |
| 8 | MTP7 | 565.24 | 308.08 |
| 8 | DFlash 2-7 | 741.07 | 249.68 |

### 代码与数学得分

| 并发 | 路线 | 代码答对数 /32 | 数学答对数 /32 |
| --- | --- | --- | --- |
| 1 | 基线 | 29、31、30 | 30、30、30 |
| 1 | MTP7 | 30、31、31 | 30、28、31 |
| 1 | DFlash 2-7 | 30、31、30 | 29、32、30 |
| 4 | 基线 | 31、31、31 | 30、31、30 |
| 4 | MTP7 | 30、30、31 | 29、29、29 |
| 4 | DFlash 2-7 | 31、31、29 | 31、31、30 |
| 8 | 基线 | 31、31、31 | 30、29、30 |
| 8 | MTP7 | 31、31、30 | 29、29、30 |
| 8 | DFlash 2-7 | 31、31、30 | 30、31、30 |

本次所有被评分器判对的回答都正常结束，因此“答对数”和“正常结束且答对数”相同，不重复列两遍。两项原始字段均保留在数据文件中。

<details>
<summary>查看三次运行的截断情况</summary>

| 并发 | 路线 | 代码截断数 | 数学截断数 |
| --- | --- | --- | --- |
| 1 | 基线 | 1、1、2 | 2、1、2 |
| 1 | MTP7 | 2、1、1 | 1、2、1 |
| 1 | DFlash 2-7 | 2、1、2 | 2、0、1 |
| 4 | 基线 | 1、1、1 | 1、0、2 |
| 4 | MTP7 | 2、2、1 | 2、1、2 |
| 4 | DFlash 2-7 | 1、1、3 | 1、1、1 |
| 8 | 基线 | 1、1、1 | 2、2、2 |
| 8 | MTP7 | 1、1、2 | 2、1、1 |
| 8 | DFlash 2-7 | 1、1、2 | 2、1、2 |

达到输出上限的回答仍保留在每次 32 题的分母中。

</details>
<!-- END RESULT_TABLE -->

以上各表由[已保存的汇总](data/summary.json)生成。吞吐按“服务端确认的输出 token 总数 ÷ 整组耗时”计算，**包含 thinking、错答和截断回答**。计时从首个测量请求派发，到最后一个请求的终止事件接收完成；不含模型下载、启动、预热和评分。这不是 GPU 纯解码吞吐。

### 为什么还要看正确答案的交付速度

<!-- BEGIN COUNTEREXAMPLE -->
并发 4 的第三次运行（seed 20260908）出现了一个例外：**DFlash 2 输出 token 更快，但做完同一组题反而更慢。** 下表只统计正常结束且答对的回答，耗时取自这一次运行，不是三次运行的中位数。

| 路线 | 整组耗时（秒） | 代码答对数 /32 | 数学答对数 /32 |
| --- | --- | --- | --- |
| MTP7 | 450.87 | 31 | 29 |
| DFlash 2-7 | 484.07 | 29 | 30 |

DFlash 2 有 3 份代码回答达到输出上限。用“正常结束且答对数 ÷ 整组耗时”衡量正确答案的交付速度，DFlash 2 与 MTP7 的比值为：代码 **0.8713**，数学 **0.9635**。两者都小于 1。这说明 token 吞吐优势不能直接当成正确答案的交付优势；这次差异的原因尚未定位。
<!-- END COUNTEREXAMPLE -->

## 客户端延迟

TTFT 是等待首个输出 token 的时间；TPOT 是首个 token 之后，平均每个输出 token 的交付间隔；回答耗时是从请求派发到接收终止事件的时间。三项都从客户端观察，数值越低越好。

每个配置先分别计算三次运行的 P50，再取三个 P50 的中位数，**不是把所有响应合并后求一次分位数**。缺失或无定义的值不补零。

<!-- BEGIN LATENCY_TABLE -->
### 首 token 等待（TTFT，ms）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 82.727 | 75.127 | 80.286 |
| 4 | 104.008 | 110.259 | 115.994 |
| 8 | 106.598 | 124.699 | 124.781 |

### token 交付间隔（TPOT，ms/token）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 18.567 | 8.011 | 5.875 |
| 4 | 20.104 | 8.549 | 6.739 |
| 8 | 20.845 | 10.041 | 7.892 |

### 单次回答耗时（秒）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 16.359 | 6.236 | 6.185 |
| 4 | 19.035 | 8.661 | 5.237 |
| 8 | 18.457 | 9.915 | 7.742 |

每个配置、每项指标均有 192 份有效响应记录，缺失 0 份。这是重复运行的观测数，不是独立题目数。
<!-- END LATENCY_TABLE -->

<details>
<summary>查看延迟的精确定义</summary>

TTFT 从派发请求计时，到首个非空生成 `token_ids` 事件为止；空的角色事件或 usage 事件不算首 token。TPOT 按 `(last_token_time - first_token_time) / (completion_tokens - 1)` 计算，仅在输出多于一个 token、且 token-ID 覆盖校验通过时有效。

一个推测解码 SSE 块可以包含多个 token，所以这些是客户端接收侧指标，不是 GPU kernel 的执行时间。定义见[配置](evidence/configuration.json)，观测值见[逐组记录](data/groups.json)。

</details>

<a id="已记录的方法"></a>

## 测试方法

三条路线固定目标模型、数值精度、题目、输出预算和采样设置，只切换推测解码配置。参数来自当时保存的[配置](evidence/configuration.json)，实际加载检查记录在[运行证据](evidence/run.json)的 `activation` 中。

| 项目 | 本次设置 |
|---|---|
| 硬件 | 单张 H100 NVL，张量并行度为 1 |
| 目标模型 | Qwen3.8-27B，BF16 |
| MTP | 目标 checkpoint 自带的多 token 预测权重，未另行训练或转换 |
| DFlash 2 | incoai 发布的 Qwen3.8-27B-DFlash2，BF16 |
| 推理引擎 | vLLM 0.28.0，实际加载 Model Runner V2 |
| 候选数量 | 基线为 0；MTP7 和 DFlash 2-7 均为 7 |
| 输出预算 | 每题最多 16,384 个 token，包含 thinking |
| 思考设置 | 开启并保留 thinking，`reasoning_effort="xhigh"` |
| 采样 | temperature 为 1.0，top_p 为 0.95，top_k 为 20 |
| 配对方式 | 并发 1、4、8；seed 为 20260906、20260907、20260908 |

每类 32 个题目 ID 按预先固定的 SHA-256 排序规则选取，不参考回答和分数。三条路线使用相同的逐题 seed，但这不代表每一步随机抽样完全对齐。代码题由 EvalPlus 官方工具评分，数学题由 Math-Verify 官方工具评分。

<details>
<summary>查看固定版本、完整参数与请求样例</summary>

以下链接固定到实际使用的版本，不指向模型仓库当前最新版：

| 对象 | 版本记录 |
|---|---|
| 目标模型 | [Qwen3.8-27B checkpoint](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0) |
| DFlash 2 | [Qwen3.8-27B-DFlash2 checkpoint](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2/tree/dedf8df68adfb1afeaf7b7480c0a0243108177b4)，架构为 `DFlash2DraftModel` |
| vLLM | [0.28.0 固定源码](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a) |
| EvalPlus | [固定源码](https://github.com/evalplus/evalplus/tree/26d6d00bb1fd0fa37f39c99d5290da67891d1c5e)，使用官方 sanitize/evaluate CLI |
| Math-Verify | [固定源码](https://github.com/huggingface/Math-Verify/tree/ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b)，使用官方 `evaluate_model_outputs.py` |

其余参数为 `min_p=0.0`、`presence_penalty=0.0`、`repetition_penalty=1.0`。模板同时设置 `enable_thinking=true` 和 `preserve_thinking=true`；调度上限为 `max_model_len=32768`、`max_num_seqs=16`、`max_num_batched_tokens=16384`。

客户端与服务端同机，经过回环地址按固定顺序、固定并发补位派发。固定客户端并发，不代表 GPU 批次形状相同。归档路线标识分别为 `baseline`、`mtp7`、`dflash2_7`；配置中的基础 seed 为 20260906。

[请求样例](evidence/request-examples.json)保存了第一组基线运行中 `HumanEval/69` 和 `MATH-500/100` 的提示词、完整参数及哈希。`raw_correct` 记录评分器判对数，`normal_correct` 还要求 `finish_reason=stop`；二者在本次 S 阶段恰好一致。离线分析使用已保存的评分，不重新判分。

</details>

<a id="执行覆盖"></a>

## 测试覆盖与未执行项

原计划包含四个阶段。本文的速度和得分表只使用 S 阶段，兼容性检查和贪心诊断不混入正式子集结果。

| 阶段 | 完成组数 | 实际响应数 | 状态 |
|---|---:|---:|---|
| C：兼容性检查 | 6 | 48 | 已完成 |
| G：贪心诊断 | 36 | 144 | 已完成 |
| S：重复子集 | 27 | 1,728 | 已完成 |
| F：完整题集 | 0 | 0 | 未执行 |

总计完成 **69/81 组、1,920/5,904 份响应**。剩余 12 组、3,984 份响应保持 `NOT_RUN`，既不从计划中删除，也不当作答错。运行记录的总体状态因此仍为 `BLOCKED`。

F 原本要让三条路线在并发 1 和 8 下，分别完成全部 164 道 HumanEval+ 和 500 道 MATH-500，每题一次，seed 为 20260906。启动前预计还需约 **37.36 小时**（包含 1.5 倍安全系数），剩余时限只有约 **1.29 小时**，因此没有启动。它不是运行到预算耗尽后才被迫中断。

精确预测值和停止原因保留在[运行证据](evidence/run.json)中，原记录为 `FULL_MATRIX_DOES_NOT_FIT_BILLING_RUNWAY; denominator unchanged`。

<details>
<summary>查看各阶段的测量耗时</summary>

| 阶段 | 测量组耗时合计（秒） |
|---|---:|
| C | 928.51 |
| G | 387.09 |
| S | 27,800.41 |
| F | 0，未执行 |

这里只累加各测量组的耗时，显示到小数点后两位；精确值保留在[运行证据](evidence/run.json)中。这不是 VM 总占用时间，“已完成”也不表示每份答案都正确。

</details>

### 执行时间线

实验结束后，先回收并校验本地证据，再释放 GPU。以下节点来自[运行记录](evidence/run.json)，更早的执行过程保留在[事件日志](evidence/events.jsonl)中。

![最后一次执行与证据回收的记录](images/run-timeline.png)

*图 2：依据本次运行事件、配置和请求样例生成。图中展示执行、全量阶段未启动、证据回收和 GPU 释放的顺序，间距不代表经过的时间。*

<!-- BEGIN RUN_LOG -->
| 节点 | 时间（UTC） |
| --- | --- |
| 最后一次执行开始 | 2026-09-06 06:28:46 |
| 结束执行，全量阶段未启动 | 2026-09-06 15:20:08 |
| 本地证据校验通过 | 2026-09-06 15:22:13 |
| GPU 已释放 | 2026-09-06 15:22:53 |

结束时已完成 **1,920/5,904 份响应**。表内时间显示到秒；完整时间戳、执行状态和释放记录见 [运行证据](evidence/run.json)。
<!-- END RUN_LOG -->

最后一次执行持续约 **8 小时 51 分钟**，包含恢复已有组和测量以外的开销。这个时长、测量组耗时和逐请求延迟不能相加；公开记录不足以重建整个实验的 VM 总占用时间。

<a id="证据与复算边界"></a>

## 证据与代码

| 入口 | 可核对的内容 |
|---|---|
| [执行程序](source/campaign_runner.py) | 当时使用的组派发、计时和实验控制代码 |
| [评分接入](source/scoring.py)、[流式计时](source/stream_metrics.py) | 官方评分与回答如何绑定，token 如何核对，延迟如何计算 |
| [配置](evidence/configuration.json)、[请求样例](evidence/request-examples.json) | 固定参数及两份带哈希的实际请求 |
| [运行记录](evidence/run.json)、[事件日志](evidence/events.jsonl) | 执行状态、加载检查、来源成员哈希及回收顺序 |
| [逐组记录](data/groups.json)、[数值汇总](data/summary.json) | 题目 ID、已存评分、计时、计数和配对结果 |
| [分析程序](analyze_results.py)、[验收程序](validate_report.py) | 重新汇总数字，检查报告和证据是否一致 |

这些源码是实际执行版本的归档，不是从零部署 GPU 的完整安装包。**完整原始回答和 SSE 流仍在作者的私有归档中，没有在此重新分发。** 公开文件不含基础设施定位信息或凭据；归档及成员哈希说明来源，但不能独立证明运行行为。

## 离线复算

在本目录执行，使用 Python 3.10+ 标准库，无需额外依赖、GPU、网络或凭据：

```bash
python validate_report.py
python -m unittest discover -p "test_*.py"
```

验收应输出 `REPORT_GATE=PASS`，测试全部通过，两条命令的退出码都为 0。它们不发起新推理，也不重新评分。需要重新生成数值汇总时，执行：

```bash
python analyze_results.py --groups data/groups.json --output regenerated
```

输出可与[已发布汇总](data/summary.json)对照。程序只读取已保存的评分、计数和计时，不执行生成的答案。从父目录运行的命令见[总览快速开始](../../README-CN.md#快速开始)。

<details>
<summary>重新生成图片和报告</summary>

为分析命令追加 `--figure regenerated/throughput.png` 可生成吞吐图，此项需要 [Matplotlib 3.10.9](requirements-figures.txt)。数值复算本身不需要 Matplotlib。

审阅修改后，`python validate_report.py --refresh --timeline` 会重建报告表格、时间线图片和文件哈希清单。默认验收命令只读，不改写证据。图片字节可能随字体或平台变化。

</details>

## 结论适用到哪里

- 可以说明本次固定配置、固定子集中的性能和得分，不能证明统计显著性、分布等价或正式非劣效。
- 吞吐、客户端延迟、正确答案交付速度是不同指标，不能互相替代，也不能据此推断 GPU kernel 的独立性能。
- 本轮换了模型、checkpoint 和引擎，不能据此认定[旧版 DFlash 的并发故障](../20260905-quality/README-CN.md)已修复。两轮结果独立保留。