# Microsoft Foundry 上的 Claude 5.5：思考模式、推理档位、提示缓存、延迟与编码正确率

[![Models](https://img.shields.io/badge/models-Opus%20%C2%B7%20Sonnet%20%C2%B7%20Haiku%205.5-0078D4)](#目的)
[![Measured](https://img.shields.io/badge/measured-2026--10--26%20to%2010--27-0078D4)](#实现效果)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml)

作者：魏新宇 · [English](README.md)

## 目的

**测什么。** 测 Claude Opus 5.5、Sonnet 5.5 和 Haiku 5.5 以 [Hosted on Azure](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options) 方式部署在 Microsoft Foundry 上时的表现：模型版本 2，即 Anthropic 运营、运行在 Azure 基础设施上的服务，部署类型为 GlobalStandard。对每个编码请求，我们测首个可见文字和完整回答各要等多久、写出的代码能否通过题目自带的单元测试、按标价花多少钱。下表中的请求设置会同时改变这几项，有些组合还会直接返回 HTTP 400；只看请求成功看不出这些。

**本轮 ACA 已完成：** 已保存 650/650 次请求，624 份正式答案已评分。下面先看性能，再看正确率。[完整结果](docs/results_CN.md#aca-gateway-snapshot)。

**当前测试方法。** Linux VM 客户端 → Azure Container Apps 上的 LiteLLM → Foundry；客户端、网关和 Foundry 资源均位于 East US 2。客户端使用网关入口密钥，LiteLLM 以自己的托管身份调用 Foundry。通过请求顶层 `cache_control` 开启提示缓存。每个模型同一时间只有 1 个请求，测的是单个请求的表现，不是压力测试。

**历史网关检查（2026-10-24）。** Windows 客户端通过 Japan East 的 Azure Container Apps 上的 LiteLLM，向同一组部署发送五轮对话；LiteLLM 用自己的托管身份转发，设置为不丢弃参数、不重试。那次耗时包含日本到美国东部的网络延迟，不是当前 East US 2 测试的结果。详见[结果页](docs/results_CN.md#网关测试)。

<img src="images/topology-zh.svg" width="900" alt="当前开启缓存的测试路径：Linux VM 客户端经 East US 2 的 Azure Container Apps 上的 LiteLLM 调用三个 Microsoft Foundry Claude 部署。提示缓存在 Foundry 侧；客户端记录时间和原生 usage。" />

图中展示美东二网关路径，不是历史 VM 直连结果的路径。[运行器](gateway-cache/aca_cache_matrix.py)使用[12 道题清单](data/gateway-cache-problems.json)：26 个被接受的模式／档位组合，每题每格原样发送两次，另有 26 个预热请求，已收齐 650 次。请求顶层 `cache_control` 为 `ephemeral`，有效期 `1h`；第1次写入，第2次检查原生缓存读取。这是重复请求，不是连续对话轮次，也不是关闭缓存的对照。完整性能表按请求次序分别列数，并保留全部正式答案的代码测试结果。历史结果保留原日期与调用路径。原创说明图，使用未修改的 [Azure 图标](images/icon-sources.json)。

<a id="historical-settings"></a>

**历史请求设置。** 每个设置的作用（依据 Claude 官方文档），以及保留的旧 VM 直连批次发送了什么；各部署接受哪些取值来自历史参数探测。这些观测不是当前 ACA 测试的结果：

| 设置 | 作用 | 历史观测 |
|---|---|---|
| `thinking.type: "adaptive"` | 模型对每个请求自己决定要不要先思考、思考多久；`output_config.effort` 调节思考多少。这三个模型不传 `thinking` 字段时也是这样 | 三个模型，档位 low 到 max |
| `thinking.type: "between_tools"` | Sonnet 5.5 最低的思考设置：回答前不思考。在工具调用之间写的简短进度仍以 thinking 块返回；不用工具时只返回文字。只接受 `high` 及以下档位 | Sonnet，档位 low、medium、high；不用工具 |
| `thinking.type: "disabled"` | 关闭思考。只有 Haiku 5.5 接受，且只在 `high` 及以下档位；Opus 5.5 关不掉思考 | Haiku，档位 low、medium、high |
| `thinking.display` | 是否返回思考文字。这些模型默认 `"omitted"`：thinking 块的文字为空、只带加密签名，所以回答更早开始流式返回；思考 token 照样计费。`"summarized"` 返回摘要 | 未发送：矩阵中 610 个回答用了思考 token，没有一个流式返回思考文字 |
| `output_config.effort` | 模型在整个回答上投入多少，包括思考：`low`、`medium`、`high`、`xhigh`、`max`。它是行为信号，不是 token 预算。不传时 Opus 和 Haiku 为 `medium`，Sonnet 为 `high` | 每种思考模式接受的全部档位，共 21 格 |
| `max_tokens` | 输出 token 的硬上限，包括思考；回答达到上限时以 `stop_reason: "max_tokens"` 停止。这些模型最大 128,000 | 矩阵用 128,000；1,000,000 返回 HTTP 400 |
| 不传 `cache_control`（默认） | 不缓存：缓存要由请求主动开启。“自动缓存”同样要在顶层传 `cache_control`，“自动”指断点位置由系统决定，不是默认开启。官方文档写明的例外都和工具有关：工具调用循环中随 tool_result 回传的历史不加标记也可能被缓存，服务器工具的结果会自动缓存 | 编码矩阵（1,155 个请求）和缓存测试的基线场景（24 个请求，每轮都重发同样约 15,500 个 token 的前缀）：每个响应的缓存读取和写入都是 0 |
| 顶层 `cache_control` | 自动缓存：断点放在最后一个可缓存块上，随对话增长自动后移 | 缓存测试的大多数场景 |
| 内容块上的 `cache_control` | 显式断点：缓存到该块为止的提示，顺序为 `tools`、`system`、`messages`。每个请求最多 4 个断点；不足 512 个 token 的提示不会被缓存 | 缓存测试：放在仓库文件之后 |
| `cache_control.ttl` | 缓存条目闲置多久后失效：默认 `"5m"`，每次读取都会续期；也可设为 `"1h"`。写入按输入价的 1.25 倍（5 分钟）或 2 倍（1 小时）计费；读取在 Opus 和 Sonnet 上按 0.05 倍，在 Haiku 上按 0.1 倍 | 两种都测了：第 2 轮前空闲 6.5 分钟 |
| 按消息设置 effort | 用只含 effort 的 `system` 消息改变后续轮次的档位，不动顶层字段，缓存前缀因此保持有效。Beta 功能，请求头 `anthropic-beta: mid-conversation-output-config-2026-07-01`；effort 文档列出的支持平台中没有 Foundry | 一个缓存场景；缓存测试的 264 个请求全部返回 HTTP 200 |
| `temperature`、`top_p`、`top_k` | 采样参数。这些模型上任何非默认值都返回 HTTP 400 | 只在探测中发送：试过的每种模式都返回 HTTP 400；矩阵从未发送 |
| `stream` | 为 `true` 时以服务端事件流返回，只有这样才能测首个可见文字的时间 | 计时的请求都是 `true`；`max_tokens: 0` 的预热请求按 API 要求不用流式 |
| 部署类型（创建部署时选择，不是请求参数） | GlobalStandard 的请求可能在资源所在区域以外处理；US Data Zone Standard 把推理留在美国，相当于 Claude API 的 `inference_geo: "us"`。Sonnet 5.5 只支持 GlobalStandard | 只测了 GlobalStandard；矩阵每个响应的 `usage.inference_geo` 都是 `global` |

**表 1：完整思考模式与推理档位矩阵。**

[![表 1：完整思考模式与推理档位矩阵。](images/parameter-support-zh.svg)](images/parameter-support-zh.svg)

`adaptive`、`between_tools`、`disabled` 与六列档位共 54 格，均单独探测；其中 26 格被接受，包括五个不传 effort 的格子。`enabled` 每模型只测一次：`budget_tokens: 1024`，不传 effort；HTTP 400 拒绝的是模式本身，所以六个档位格都标“不支持”。缓存列只写适用性：思考模式使请求被拒时标“不适用”，不是说模型不支持缓存。默认档位来自[effort 文档](https://platform.claude.com/docs/en/build-with-claude/effort)。

历史缓存范围：当时五个被接受的模型／模式行均在 low 档读到缓存；adaptive 在切换到 high 的场景也读到缓存。后续全矩阵的覆盖与结果见独立的 ACA 性能章节。“适用”和“参数被接受”本身不证明缓存性能。历史矩阵固定项为 `max_tokens: 128000`、`stream: true`；`temperature`、`top_p`、`top_k` 不传。不传 thinking 等同 adaptive 来自文档；三个模型同时不传 thinking、effort 的探测均返回 200。

**表 2：完整提示缓存设置。**

[![表 2：完整提示缓存设置。](images/cache-settings-zh.svg)](images/cache-settings-zh.svg)

来源：[探测请求](evidence/coding-matrix-20261026/probe/probe_results.jsonl)、[缓存请求](evidence/coding-matrix-20261026/cache/cache_results.jsonl)及[缓存文档](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)。表 2 每场景重复两次：Opus adaptive、Sonnet between_tools、Haiku disabled，effort low；首轮写入与第 2-4 轮读取分开。读取比例＝读取 tokens ÷（未缓存＋写入＋读取的输入 tokens），按模型／场景／轮次汇总。新对话话题变化，但复用文件。512-token 边界和四断点上限来自文档，并非边界扫描实测。缓存标记均为 `type: ephemeral`；读取按输入价计费：Opus／Sonnet 0.05 倍、Haiku 0.1 倍（文档价格）。这些是历史 VM 直连观察，不能作为后续 ACA 批次的证据。

**未覆盖：** 工具调用（`between_tools` 和进度更新只在使用工具时才起作用）、`display: "summarized"`、US Data Zone 部署，以及 Foundry 模型目录里单独的 `claude-opus-5-5-fast` 模型。

**历史批次按模型汇总。** 已取缔的 VM 直连批次中，每个部署接受什么，以及在这 18 道题上的表现；不是当前 ACA 测试的结果：

| 问题 | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|
| API 接受的思考模式 | 只接受 `adaptive`；`disabled` 和 `between_tools` 返回 400 | `adaptive`；`between_tools` 只接受 low、medium、high | `adaptive`；`disabled` 只接受 low、medium、high |
| 推理档位 / 不传时的默认值 | low 到 max / medium | low 到 max / high | low 到 max / medium |
| 最快一格的首个可见文字 P50 | 0.48 秒（`adaptive` · low） | 0.39 秒（`between_tools` · high） | 0.43 秒（`disabled` · high） |
| 每格通过单元测试的回答数（共 54 个） | 每格都是 54 | 40 到 44 | `adaptive` 24 到 28；`disabled` 17 到 21 |
| 按标价计每 1,000 次请求的费用 | $23.34 到 $355.75 | $13.04 到 $356.49 | $0.69 到 $22.26 |
| 适合的情况（本测试的解读） | 答案必须一次就对。从 `low` 开始：每个档位都 54 个全过，`low` 最快（0.48 秒）也最便宜 | 要接近 Opus 的正确率、价格更低：`between_tools` 的通过数与 `adaptive` 相当，首字不到 0.5 秒，每 1,000 次请求 $13.16–$13.76 | 费用最重要、答错可以重试。保持思考开启：同样的档位下 `adaptive` 比 `disabled` 通过率高 12.3 个百分点 |

**历史结果范围。** 题目是 [Aider polyglot benchmark](https://github.com/Aider-AI/polyglot-benchmark) 收录的 Exercism 公开练习，每次只答一次、不用工具、看不到测试；它们不是你的生产任务。已取缔的批次曾直连 Foundry，每个部署同一时间只有一个请求。其费用和正确率是历史观测，不能证明当前开启缓存的 ACA 路径的表现。费用按标价计算，没有与 Azure 账单核对。

**来源。** 接受哪些取值、HTTP 400 的报错原文来自我们的参数探测（[结果页](docs/results_CN.md#参数探测)）。各设置的作用、默认值、`between_tools` 和 `disabled` 的使用规则，以及 Sonnet 5.5 做智能体编码时把 `max_tokens` 设为 128,000 的建议，来自 Claude 的 [thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) 和 [effort](https://platform.claude.com/docs/en/build-with-claude/effort) 文档；缓存规则和价格倍数来自 [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)；价格来自 [pricing](https://platform.claude.com/docs/en/about-claude/pricing)；托管方式和 Foundry 配置来自 [Claude in Microsoft Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)；均于 2026-10-26 查阅。“适合的情况”一行是我们对这 18 道题的解读，不是通用建议。

## 实现效果

### ACA 网关：性能测试结果

**请求已收齐，不等于全部通过。** 已保留 650/650 次请求：26 次预热、624 份正式答案。运行在 `2026-10-27T08:37:15.795+00:00` 达到 `COMPLETED`；失败和截断仍保留在统计中。[采集验收](evidence/gateway-cache-20261026/collection-status.json)。

**问题与方法。** 编码提示通过 East US 2 的 ACA LiteLLM 网关发送后，原样重复的第二次请求能否读到第一次写入的缓存，观测到的耗时和费用是多少？客户端、网关和 Foundry 资源均在 East US 2；每个模型同时只有一个请求。这是首次写入与重复读取的配对，不是关闭缓存的对照，也不能隔离网关自身开销。

**输入。** [12 道公开的 SWE-bench Lite BM25-13K 题目](data/gateway-cache-problems.json)，来源版本和提示哈希在 [run.json](evidence/gateway-cache-20261026/run.json)。这是选定子集实验，不是完整 SWE-bench 排行榜成绩，也不是客户生产数据。[运行器](gateway-cache/aca_cache_matrix.py)遍历 26 个模式／档位组合，每题每格原样发送两次，每格另有一次预热。固定 `max_tokens: 128000`、`stream: true`、顶层 `cache_control: {"type": "ephemeral", "ttl": "1h"}`。计时从客户端即将发送请求时开始；首字是第一个非空文字增量，不是心跳或思考事件。

**实际请求设置。** 以下字段取自正式请求 `opus|adaptive|low|django__django-12184|r1`，不是预热请求。上面的题单固定了公开输入的重建版本；本指标投影省略提示正文。

```json
{
  "model": "claude-opus-5-5",
  "max_tokens": 128000,
  "stream": true,
  "thinking": {
    "type": "adaptive"
  },
  "output_config": {
    "effort": "low"
  },
  "cache_control": {
    "type": "ephemeral",
    "ttl": "1h"
  }
}
```

运行器在每个题目／配置的 system 前添加确定性组标识，隔离各组缓存。各配置的题目正文相同，但组标识不同；这是受控复用，不是生产缓存命中率估计。

**指标定义。** TTFT 对应 `timing.first_text`，是首段非空可见文字，不是元数据或思考事件；E2E 对应 `timing.end`，到响应流结束。客户端在 HTTP 发送前开始计时，不含取凭据、发送前限速等待及应用或工具执行。端到端输出速率逐请求计算 `usage.output_tokens / timing.end`，包含思考 token，再取 P50；不是中位数相除，也不是纯解码速度。费用含输入、缓存写入／读取和输出，按记录中的标价计算，不含基础设施，也不是账单。

**先看全部配置的性能。** 一组对照是同题、同配置的两次请求：首次实际写入缓存，随后原生命中，且两次回答均完整结束。下表每种缓存状态各取一条请求。P50/P95 使用最近秩法；每组状态最多 12 条，P95 就是最大观测值，不是生产尾延迟保证。`default` 表示未传 effort。比较时须对齐配置；两次生成的输出长度可能不同，耗时或费用差异不能全部归因于缓存。

**请求次序，不是对话轮次。** 第1次是同题首次提交并写缓存；第2次原样重复该提示并读取缓存。没有追加上一轮答案，本矩阵也没有第3、4次请求。表中每个指标都标明对应次序。读取占比按该次序的原生读取 token 合计除以全部输入 token（未缓存＋写入＋读取）。最后一列对每个配置的12题×2次共24份答案评分，包含失败，不只使用性能有效样本。

| 模型 / thinking.type / output_config.effort | 性能有效样本数（次） | TTFT P50 / P95（秒） | E2E P50 / P95（秒） | 端到端输出速率 P50（tokens/s，含思考） | 平均费用（美元/请求） | 输入缓存读取占比（%） | 已解决／评分答案数（第1+2次合计，%） |
|---|---:|---:|---:|---:|---:|---:|---:|
| Opus 5.5<br>`adaptive` / `low` | 第1次: 12<br>第2次: 12 | 第1次: 1.19 / 9.06<br>第2次: 1.08 / 14.7 | 第1次: 6.94 / 14.4<br>第2次: 7.84 / 20.0 | 第1次: 103.53<br>第2次: 103.75 | 第1次: $0.158921<br>第2次: $0.023222 | 第1次: 0.00<br>第2次: 99.98 | 9/24 (37.50%) |
| Opus 5.5<br>`adaptive` / `medium` | 第1次: 12<br>第2次: 12 | 第1次: 6.92 / 31.5<br>第2次: 7.15 / 29.3 | 第1次: 11.6 / 37.2<br>第2次: 11.3 / 35.3 | 第1次: 108.44<br>第2次: 111.76 | 第1次: $0.173419<br>第2次: $0.036952 | 第1次: 0.00<br>第2次: 99.98 | 19/24 (79.17%) |
| Opus 5.5<br>`adaptive` / `high` | 第1次: 12<br>第2次: 12 | 第1次: 9.13 / 94.5<br>第2次: 7.53 / 228 | 第1次: 14.0 / 101<br>第2次: 11.7 / 239 | 第1次: 110.21<br>第2次: 110.93 | 第1次: $0.200936<br>第2次: $0.097379 | 第1次: 0.00<br>第2次: 99.98 | 19/24 (79.17%) |
| Opus 5.5<br>`adaptive` / `xhigh` | 第1次: 12<br>第2次: 12 | 第1次: 18.9 / 110<br>第2次: 19.6 / 380 | 第1次: 24.7 / 117<br>第2次: 24.5 / 389 | 第1次: 112.87<br>第2次: 114.35 | 第1次: $0.248050<br>第2次: $0.183598 | 第1次: 0.00<br>第2次: 99.98 | 21/24 (87.50%) |
| Opus 5.5<br>`adaptive` / `max` | 第1次: 11<br>第2次: 11 | 第1次: 232 / 1027<br>第2次: 236 / 913 | 第1次: 247 / 1036<br>第2次: 249 / 922 | 第1次: 123.30<br>第2次: 121.91 | 第1次: $1.008633<br>第2次: $0.785095 | 第1次: 0.00<br>第2次: 99.98 | 22/24 (91.67%) |
| Opus 5.5<br>`adaptive` / `default` | 第1次: 11<br>第2次: 11 | 第1次: 7.03 / 65.8<br>第2次: 8.02 / 28.5 | 第1次: 12.0 / 72.3<br>第2次: 15.0 / 34.3 | 第1次: 109.83<br>第2次: 109.88 | 第1次: $0.186835<br>第2次: $0.037639 | 第1次: 0.00<br>第2次: 99.98 | 14/24 (58.33%) |
| Sonnet 5.5<br>`adaptive` / `low` | 第1次: 12<br>第2次: 12 | 第1次: 0.77 / 0.95<br>第2次: 0.76 / 1.15 | 第1次: 4.86 / 9.76<br>第2次: 4.88 / 9.01 | 第1次: 130.16<br>第2次: 123.18 | 第1次: $0.077371<br>第2次: $0.008869 | 第1次: 0.00<br>第2次: 99.98 | 6/24 (25.00%) |
| Sonnet 5.5<br>`adaptive` / `medium` | 第1次: 12<br>第2次: 12 | 第1次: 0.81 / 11.0<br>第2次: 0.87 / 16.3 | 第1次: 5.67 / 14.4<br>第2次: 6.15 / 19.1 | 第1次: 124.97<br>第2次: 124.24 | 第1次: $0.078745<br>第2次: $0.010499 | 第1次: 0.00<br>第2次: 99.98 | 5/24 (20.83%) |
| Sonnet 5.5<br>`adaptive` / `high` | 第1次: 12<br>第2次: 12 | 第1次: 6.05 / 137<br>第2次: 7.44 / 119 | 第1次: 10.6 / 140<br>第2次: 10.7 / 122 | 第1次: 141.38<br>第2次: 138.87 | 第1次: $0.106288<br>第2次: $0.034861 | 第1次: 0.00<br>第2次: 99.98 | 8/24 (33.33%) |
| Sonnet 5.5<br>`adaptive` / `xhigh` | 第1次: 12<br>第2次: 12 | 第1次: 20.7 / 246<br>第2次: 16.1 / 341 | 第1次: 24.0 / 254<br>第2次: 19.4 / 354 | 第1次: 148.80<br>第2次: 149.31 | 第1次: $0.152607<br>第2次: $0.109698 | 第1次: 0.00<br>第2次: 99.98 | 18/24 (75.00%) |
| Sonnet 5.5<br>`adaptive` / `max` | 第1次: 9<br>第2次: 9 | 第1次: 394 / 616<br>第2次: 364 / 743 | 第1次: 397 / 622<br>第2次: 367 / 751 | 第1次: 156.49<br>第2次: 158.34 | 第1次: $0.804891<br>第2次: $0.635133 | 第1次: 0.00<br>第2次: 99.98 | 18/24 (75.00%) |
| Sonnet 5.5<br>`adaptive` / `default` | 第1次: 12<br>第2次: 12 | 第1次: 6.86 / 86.8<br>第2次: 5.78 / 152 | 第1次: 10.8 / 90.2<br>第2次: 8.39 / 156 | 第1次: 140.69<br>第2次: 141.88 | 第1次: $0.100876<br>第2次: $0.035923 | 第1次: 0.00<br>第2次: 99.98 | 9/24 (37.50%) |
| Sonnet 5.5<br>`between_tools` / `low` | 第1次: 12<br>第2次: 12 | 第1次: 0.78 / 1.08<br>第2次: 0.76 / 0.91 | 第1次: 5.14 / 7.88<br>第2次: 4.51 / 8.22 | 第1次: 126.13<br>第2次: 130.11 | 第1次: $0.077653<br>第2次: $0.008496 | 第1次: 0.00<br>第2次: 99.98 | 4/24 (16.67%) |
| Sonnet 5.5<br>`between_tools` / `medium` | 第1次: 12<br>第2次: 12 | 第1次: 0.83 / 1.06<br>第2次: 0.79 / 0.93 | 第1次: 5.41 / 9.18<br>第2次: 4.60 / 9.87 | 第1次: 132.11<br>第2次: 133.30 | 第1次: $0.077994<br>第2次: $0.009313 | 第1次: 0.00<br>第2次: 99.98 | 5/24 (20.83%) |
| Sonnet 5.5<br>`between_tools` / `high` | 第1次: 12<br>第2次: 12 | 第1次: 0.81 / 1.09<br>第2次: 0.82 / 1.18 | 第1次: 5.56 / 11.6<br>第2次: 7.03 / 13.1 | 第1次: 130.38<br>第2次: 129.14 | 第1次: $0.079108<br>第2次: $0.011469 | 第1次: 0.00<br>第2次: 99.98 | 7/24 (29.17%) |
| Sonnet 5.5<br>`between_tools` / `default` | 第1次: 12<br>第2次: 12 | 第1次: 0.79 / 1.15<br>第2次: 0.78 / 1.07 | 第1次: 4.88 / 13.6<br>第2次: 5.46 / 10.2 | 第1次: 130.06<br>第2次: 133.11 | 第1次: $0.078623<br>第2次: $0.010259 | 第1次: 0.00<br>第2次: 99.98 | 7/24 (29.17%) |
| Haiku 5.5<br>`adaptive` / `low` | 第1次: 12<br>第2次: 12 | 第1次: 3.09 / 20.2<br>第2次: 4.25 / 17.6 | 第1次: 4.93 / 22.9<br>第2次: 5.75 / 20.7 | 第1次: 214.53<br>第2次: 211.44 | 第1次: $0.004254<br>第2次: $0.001009 | 第1次: 0.00<br>第2次: 99.98 | 2/24 (8.33%) |
| Haiku 5.5<br>`adaptive` / `medium` | 第1次: 12<br>第2次: 12 | 第1次: 6.92 / 13.8<br>第2次: 6.93 / 14.2 | 第1次: 8.30 / 15.3<br>第2次: 8.02 / 16.8 | 第1次: 218.61<br>第2次: 221.27 | 第1次: $0.004638<br>第2次: $0.001248 | 第1次: 0.00<br>第2次: 99.98 | 5/24 (20.83%) |
| Haiku 5.5<br>`adaptive` / `high` | 第1次: 12<br>第2次: 12 | 第1次: 9.07 / 38.5<br>第2次: 12.1 / 29.6 | 第1次: 10.8 / 40.3<br>第2次: 14.1 / 34.0 | 第1次: 234.38<br>第2次: 230.84 | 第1次: $0.005884<br>第2次: $0.002356 | 第1次: 0.00<br>第2次: 99.98 | 8/24 (33.33%) |
| Haiku 5.5<br>`adaptive` / `xhigh` | 第1次: 11<br>第2次: 11 | 第1次: 61.3 / 460<br>第2次: 53.4 / 235 | 第1次: 63.2 / 463<br>第2次: 57.0 / 237 | 第1次: 259.47<br>第2次: 258.09 | 第1次: $0.019081<br>第2次: $0.010969 | 第1次: 0.00<br>第2次: 99.98 | 12/24 (50.00%) |
| Haiku 5.5<br>`adaptive` / `max` | 第1次: 8<br>第2次: 8 | 第1次: 204 / 399<br>第2次: 260 / 377 | 第1次: 206 / 406<br>第2次: 262 / 384 | 第1次: 269.25<br>第2次: 265.15 | 第1次: $0.037720<br>第2次: $0.032892 | 第1次: 0.00<br>第2次: 99.98 | 14/24 (58.33%) |
| Haiku 5.5<br>`adaptive` / `default` | 第1次: 12<br>第2次: 12 | 第1次: 5.49 / 15.5<br>第2次: 6.22 / 11.6 | 第1次: 7.40 / 18.4<br>第2次: 8.07 / 14.2 | 第1次: 218.12<br>第2次: 222.91 | 第1次: $0.004464<br>第2次: $0.001171 | 第1次: 0.00<br>第2次: 99.98 | 4/24 (16.67%) |
| Haiku 5.5<br>`disabled` / `low` | 第1次: 12<br>第2次: 12 | 第1次: 0.48 / 0.83<br>第2次: 0.56 / 0.74 | 第1次: 2.29 / 3.37<br>第2次: 2.36 / 3.51 | 第1次: 177.01<br>第2次: 183.87 | 第1次: $0.003747<br>第2次: $0.000406 | 第1次: 0.00<br>第2次: 99.98 | 3/24 (12.50%) |
| Haiku 5.5<br>`disabled` / `medium` | 第1次: 12<br>第2次: 12 | 第1次: 0.54 / 0.73<br>第2次: 0.50 / 0.60 | 第1次: 2.42 / 3.47<br>第2次: 2.64 / 4.31 | 第1次: 172.51<br>第2次: 175.95 | 第1次: $0.003759<br>第2次: $0.000443 | 第1次: 0.00<br>第2次: 99.98 | 3/24 (12.50%) |
| Haiku 5.5<br>`disabled` / `high` | 第1次: 12<br>第2次: 12 | 第1次: 0.49 / 0.72<br>第2次: 0.49 / 0.69 | 第1次: 2.67 / 4.51<br>第2次: 2.40 / 3.56 | 第1次: 181.72<br>第2次: 172.20 | 第1次: $0.003790<br>第2次: $0.000428 | 第1次: 0.00<br>第2次: 99.98 | 1/24 (4.17%) |
| Haiku 5.5<br>`disabled` / `default` | 第1次: 12<br>第2次: 12 | 第1次: 0.49 / 0.79<br>第2次: 0.45 / 0.59 | 第1次: 2.66 / 3.16<br>第2次: 2.41 / 4.38 | 第1次: 174.06<br>第2次: 201.46 | 第1次: $0.003728<br>第2次: $0.000475 | 第1次: 0.00<br>第2次: 99.98 | 2/24 (8.33%) |

### 完成情况与缓存证据

**缓存证据。** 304 组正式配对完整结束，其中 302 组有原生缓存命中。另 2 组跨越停机／恢复间隔，过期后重新写入缓存；它们仍计入请求数、费用和正确率，但不进入缓存命中性能统计。命中配对至少读回前次缓存写入的 100.0%，复用同一响应 message ID 的配对为 0。这证明对应缓存读取，不证明普遍提速。响应报告 `inference_geo: global` 和 East US 2 区域头，不代表固定区域推理承诺。

**费用与边界。** 整轮按记录采用的[标价](coding-matrix/pricing.py)计费共 $76.17，包含预热、缓存写入／读取、输出和截断回答；不含基础设施费用，也不是账单。配对指标排除预热、不完整配对及非命中配对，但不会缩小正确率分母。完整分布与计数保存在[统计结果](evidence/gateway-cache-20261026/interim-facts.json)。

[查看全部 26 格及配对观测](docs/results_CN.md#aca-gateway-snapshot)。

**证据边界。** 当前批次未保留逐请求出站审计，不能用早期网关日志补齐；参数证据和独立审计见[结果页](docs/results_CN.md#aca-gateway-snapshot)。

### 性能之后：代码正确率

**方法。** 对同一批 624 份正式答案评分，只排除预热。使用官方 SWE-bench 5.0.2，固定提交 `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`；由官方 `extract_diff` 提取补丁，没有替模型修答案，也没有新增模型调用。每个配置／重复次数使用独立 run ID；所选 12 道金标准全部通过。[冻结输入、官方报告与验算](evidence/gateway-score-20261027/verification.json)。

合计 245/624 份解决问题（39.26%）；另有 257 份补丁应用失败、108 份测试未通过、14 份截断空回答，均保留在分母中。不同模型的模式／档位组合数量不同，不能当成公平总榜；同条件每格均为 24 份答案。这只是 12 题子集，不是完整 SWE-bench Lite 成绩。

**保留疑义。** 6 条官方 `no_tests_collected` 模糊标记仍保留为未解决。对应日志先收集了 92 项顶层测试，包含嵌套的零收集输出，并出现 `NameError: cached_eval`；没有暗中删除或改判。[六条来源复核](evidence/gateway-score-20261027/ambiguous-review.json)。[环境清单](evidence/gateway-score-20261027/environment.json)是在评分后采集，不冒充运行时遥测。

**证据与复算。** [统计结果](evidence/gateway-cache-20261026/interim-facts.json)、[导出哈希与脱敏范围](evidence/gateway-cache-20261026/_export_manifest.json)、[Opus 记录](evidence/gateway-cache-20261026/responses_opus.jsonl)、[Sonnet 记录](evidence/gateway-cache-20261026/responses_sonnet.jsonl)、[Haiku 记录](evidence/gateway-cache-20261026/responses_haiku.jsonl)。指标投影省略提示与回答正文、思考签名、私有端点和其他响应头，不能用于代码正确率评分。复算命令见[测试页](docs/testing_CN.md#aca-snapshot-replay)。

**以下仅为历史结果。** 下列 VM 直连测量属于已取缔的方案，尤其是 21 格编码矩阵未发送 `cache_control`，不满足当前 ACA 开启缓存的测试要求。Japan East 网关检查另列日期。这些数字都不是当前 East US 2 ACA 测试的结果。

看结果时会用到的词：

| 术语 | 含义 |
|---|---|
| 格 | 一个模型 × 思考模式 × 推理档位的组合。每格把 18 道题各答 3 次，共 54 个回答 |
| 思考模式、推理档位 | 定义见[历史请求设置表](#historical-settings) |
| 首个可见文字 | 从请求即将发出到收到第一个非空 `text_delta` 的秒数，在 VM 上计时。思考在它之前进行，且思考文字默认不流式返回（`display` 为 omitted），所以这段等待包含全部思考时间 |
| 首个事件 | 收到第一个服务端事件 `message_start` 的秒数 |
| 完整回答 | 收到流结束的秒数，只统计完成的请求 |
| 完成 | HTTP 200、收到 `message_stop`、`stop_reason` 为 `end_turn` 且文字不为空 |
| 通过 | 把回答里的文件覆盖到练习的解答文件上，题目自带的单元测试在离线容器里以 0 退出（Aider 的首次作答规则） |
| 按题目的 95% 区间 | 对 18 道题有放回重抽 5,000 次（种子 20261026）取 2.5% 到 97.5% 分位。同一道题的 3 个回答不独立，所以以题目为单位 |
| 费用 | 标价 × API 返回的 `usage` 中的 token 数，包括缓存写入和读取 |

**各部分在哪里运行。**

| 部分 | 位置 | 说明 |
|---|---|---|
| 客户端：参数探测、编码矩阵、缓存测试 | Linux VM `Standard_D4s_v5`，East US 2 | Ubuntu 24.04，内核 7.0.0-1017-azure，Python 3.12.3，httpx 0.28.1，azure-identity 1.25.1；用 VM 的托管身份取 Entra 令牌；矩阵开始前到端点的 TCP 建连中位数 9.67 毫秒 |
| 模型 | East US 2 的 Foundry 资源 | `claude-opus-5-5` 每分钟 40,000 token；`claude-sonnet-5-5` 和 `claude-haiku-5-5` 各 80,000；版本 2，GlobalStandard，请求可能在 East US 2 以外执行 |
| 单元测试 | 同一台 VM 上的 Docker | `--network none`，1.5 个 CPU，3 GB；工具链与 Aider 评测镜像一致：Python 3.11、Go 1.21.5、Rust、Node 20、OpenJDK 21、CMake 和 Boost |

**编码矩阵每个请求发送的内容。** 每个回答对应一次流式 Messages 请求；这里截短了 `system` 和 `content`：

```json
{
  "model": "claude-sonnet-5-5",
  "max_tokens": 128000,
  "stream": true,
  "thinking": {"type": "between_tools"},
  "output_config": {"effort": "low"},
  "system": "Act as an expert software developer. …",
  "messages": [{"role": "user", "content": "I have *added these files to the chat* so you can go ahead and edit them. …"}]
}
```

各格之间只有 `model`、`thinking.type` 和 `output_config.effort` 不同。没有 `cache_control`、工具，也没有 `temperature`、`top_p` 或 `top_k`。完整的系统提示和一条完整的用户消息见[结果页](docs/results_CN.md#编码矩阵)；18 条全部在 [problems.json](evidence/coding-matrix-20261026/matrix/problems.json)。

**每个指标怎么测、用哪个脚本。**

| 指标 | 起止或算法 | 脚本 |
|---|---|---|
| 接受的取值 | 带上每个取值发一个只需回答一个词的请求，看返回 200 还是 400 | [`probe.py`](coding-matrix/probe.py) |
| 首个可见文字、首个事件、完整回答 | 请求发出 → 第一个 `text_delta`、`message_start`、流结束；在 VM 上计时 | [`claude_api.py`](coding-matrix/claude_api.py) `stream_message` |
| 完成、思考 token、输出 token | 每个流的状态、`stop_reason` 和 `usage` | [`bench.py`](coding-matrix/bench.py) |
| 通过 | 练习自带的单元测试，在 Docker 里离线运行 | [`judge.py`](coding-matrix/judge.py) |
| P50、P95、区间、每 1,000 次费用 | 最近秩分位；按题目自助重抽；平均标价费用 × 1,000 | [`analyze.py`](coding-matrix/analyze.py) |
| 缓存读写、整段对话费用 | 每轮的 `usage`；同样的 token 按不缓存计价作对照 | [`cache_test.py`](coding-matrix/cache_test.py)、[`cache_analyze.py`](coding-matrix/cache_analyze.py) |

**不要把下面三张表当成三个模型的通用排名。** Opus 每一格都把 18 道题全部答对，这次测试分不出它各档位的差别。只有 18 道题，Sonnet 和 Haiku 每格的 95% 区间宽 30 到 44 个百分点（例如 Sonnet `between_tools` · high：54 个通过 44 个，区间 65% 到 94%）。题目都是短小的单文件练习。每行是一个模型加一种思考模式，每列是一个推理档位；*不接受* 表示 API 返回 HTTP 400。P95、完整回答耗时、token 数和每格的区间见[结果页](docs/results_CN.md#每格结果)。

**通过单元测试的回答数（每格 54 个）**

| 模型 · 思考模式 | low | medium | high | xhigh | max |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 · `adaptive` | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 |
| Sonnet 5.5 · `adaptive` | 41/54 | 42/54 | 40/54 | 41/54 | 44/54 |
| Sonnet 5.5 · `between_tools` | 42/54 | 41/54 | 44/54 | 不接受 | 不接受 |
| Haiku 5.5 · `adaptive` | 24/54 | 26/54 | 27/54 | 28/54 | 28/54 |
| Haiku 5.5 · `disabled` | 19/54 | 17/54 | 21/54 | 不接受 | 不接受 |

**首个可见文字 P50（秒）**

| 模型 · 思考模式 | low | medium | high | xhigh | max |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 · `adaptive` | 0.48 | 3.71 | 4.05 | 6.04 | 51.4 |
| Sonnet 5.5 · `adaptive` | 0.46 | 0.50 | 3.25 | 7.44 | 190 |
| Sonnet 5.5 · `between_tools` | 0.42 | 0.44 | 0.39 | 不接受 | 不接受 |
| Haiku 5.5 · `adaptive` | 4.13 | 4.62 | 8.21 | 14.9 | 121 |
| Haiku 5.5 · `disabled` | 0.46 | 0.45 | 0.43 | 不接受 | 不接受 |

**按标价计每 1,000 次请求的费用（美元）**

| 模型 · 思考模式 | low | medium | high | xhigh | max |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 · `adaptive` | $23.34 | $34.52 | $38.75 | $65.36 | $355.75 |
| Sonnet 5.5 · `adaptive` | $13.04 | $13.57 | $18.36 | $31.62 | $356.49 |
| Sonnet 5.5 · `between_tools` | $13.16 | $13.21 | $13.76 | 不接受 | 不接受 |
| Haiku 5.5 · `adaptive` | $1.27 | $1.57 | $2.14 | $4.19 | $22.26 |
| Haiku 5.5 · `disabled` | $0.69 | $0.69 | $0.73 | 不接受 | 不接受 |

值得注意的几点：
- **平台接住了每一个请求。** 矩阵的 1,155 个请求全部返回 HTTP 200，没有 429，也没有 5xx；1,134 个计分请求中 1,130 个完成。另外 4 个里，3 个是 Haiku `adaptive` · max 把 128,000 个输出 token 全部用在思考上（`stop_reason: max_tokens`）；1 个是 Sonnet `adaptive` · max 的流在发出 `message_start` 和两个 ping 后再无数据，直到客户端 600 秒读超时在第 661 秒结束它。
- **不思考时，文字半秒内就开始出现。** Sonnet `between_tools` 和 Haiku `disabled` 共 324 个请求，首个可见文字 P50 为 0.44 秒，P95 为 0.74 秒。全部请求的首个事件 P50 为 0.47 秒，各格在 0.39 到 0.53 秒之间；其余的等待是思考，思考内容不流式返回。effort 为 max 时，首个可见文字 P50 为 51.4 秒（Opus）、190 秒（Sonnet）、121 秒（Haiku）。
- **思考提高了 Haiku 的通过率，没有提高 Sonnet 的。** 在相同的三个档位上，Haiku 用 `adaptive` 通过 47.5%，用 `disabled` 通过 35.2%，高 12.3 个百分点（95% 区间 +2.5 到 +23.5；9 道题更好，2 道更差，7 道持平）。Sonnet 用 `adaptive` 通过 75.9%，用 `between_tools` 通过 78.4%，低 2.5 个百分点（区间 -7.4 到 +1.9）。
- **提高推理档位主要换来更长的时间和更高的费用。** Opus 同样 54 个全过，low 每 1,000 次请求 $23.34，max 要 $355.75。Sonnet 的 8 格每格通过 40 到 44 个，彼此都在对方的区间内。
- **题目本身比设置影响更大。** Sonnet 所有格合计，`java/house` 24 次只过了 1 次，`javascript/promises` 24 次过了 3 次；Haiku 有 6 道题一次都没过。Opus 每道题每次都过。

**四轮编码对话中的提示缓存。** 每段对话都把同样的说明和三个 httpx 源文件（约 15,500 个 token）作为系统提示，再依次问四个问题：`Auth` 子类在请求中怎样起作用、写一个新的 `BearerTokenAuth` 类、为它写 pytest 测试、写提交信息。Opus 用 `adaptive`，Sonnet 用 `between_tools`，Haiku 用 `disabled`，推理档位 low，每个场景重复 2 次。每个场景只改一处；结果是三个模型的范围：

| 场景 | 改了什么 | 结果 |
|---|---|---|
| 自动缓存 | 每轮都带顶层 `cache_control` | 第 2–4 轮有 94–97% 的提示从缓存读取；整段对话比同样 token 不缓存便宜 52–53% |
| 在文件后设断点，开新对话 | 在仓库文件块上放 `cache_control`；再开一段文件相同、问题不同的对话 | 新对话从缓存读取 15,440–15,442 个 token，便宜 76–80% |
| 只用自动缓存，开新对话 | 顶层 `cache_control`；再开一段文件相同的对话 | 读取 0 个 token，又写了一份新缓存：比不缓存贵 20–21% |
| 改顶层推理档位 | 第 3 轮把 effort 从 low 改成 high | 第 3 轮仍有 95–97% 的提示从缓存读取 |
| 按消息改推理档位 | 同样的改动用只含 effort 的 system 消息表达，beta 头 `mid-conversation-output-config-2026-07-01` | 第 3 轮有 95–97% 从缓存读取 |
| 切换思考模式（Sonnet、Haiku） | 第 3 轮从不思考改为 `adaptive` | 第 3 轮读取 0 个 token，重写 16,609–17,138 个；第 4 轮又有 95–96% 从缓存读取 |
| 空闲 6.5 分钟，5 分钟 TTL | 默认 TTL | 第 2 轮读取 0 个 token，重写 16,145–16,158 个 |
| 空闲 6.5 分钟，1 小时 TTL | `"ttl": "1h"` | 第 2 轮读取 15,490–15,493 个 token |
| 预热 | 先发一个 `max_tokens: 0` 的非流式请求，再问第一个问题 | 第一个问题从缓存读取 15,440–15,444 个 token（占其提示的 99.7%） |
| 冷请求与热请求，提示相同 | 五对，只答一个词 | 约 15,500 个 token 时首个可见文字 P50：Opus 1.51 → 1.38 秒，Sonnet 1.03 → 0.89 秒，Haiku 0.75 → 0.71 秒；约 53,300 个 token 时：Sonnet 0.94 → 0.92 秒，Haiku 0.85 → 0.87 秒。热请求的费用是冷请求的 4–8% |

Claude 的 [effort 文档](https://platform.claude.com/docs/en/build-with-claude/effort) 写明：两次请求之间改动顶层 effort 会让缓存断点失效。本测试在自动缓存下，第 3 轮仍然读到了缓存前缀；原因未查明，只能当作 2026-10-26 这些部署上的观察结果。文档说明会保留缓存的按消息改档方式，表现相同。缓存测试的 264 个请求全部返回 HTTP 200。每轮的读取占比和费用见[结果页](docs/results_CN.md#提示缓存)。

**经过 LiteLLM 网关（2026-10-24）。** 更早的一次测试把五轮代码审阅对话经 Japan East 的 Azure Container Apps 上的 LiteLLM 1.106.2 发到同一个 East US 2 资源，共十种配置，推理档位 medium。50 个请求全部完成；网关自己的出站日志显示，每个请求的模型、思考模式、推理档位、`stream`、`max_tokens` 和缓存标记都原样到达 Foundry。首个可见文字 P50 在关闭思考时为 0.78 到 0.95 秒，`adaptive` 时最高 9.32 秒。网关和模型不在同一个区域，这些时间包含日本到美国东部的往返，不能代表网关本身增加的延迟。完整表格见[结果页](docs/results_CN.md#网关测试)。

**每次实测。**

| 运行 | 时间（UTC） | 内容 | 请求数 | 标价费用 | 结果 |
|---|---|---|---:|---:|---|
| `probe` | 2026-10-26 08:11–08:12 | 接受的取值，只需回答一个词 | 102 | $0.05 | 50 个 HTTP 200，52 个 HTTP 400 |
| `smoke` | 2026-10-26 08:35 | 21 格各答一道题，`max_tokens` 32,000 | 21 | $0.14 | 21 个完成 |
| `pilot-32k` | 2026-10-26 08:37–09:04 | `max_tokens` 32,000 的矩阵 | 173 | $5.59 | 已停止：7 个回答用满 32,000 token，4 个触发每分钟输出 token 上限（HTTP 429）；不计入结果 |
| `matrix` | 2026-10-26 09:04–14:11 | 21 格 × 18 题 × 3 次，另有 21 个预热请求 | 1,155 | $55.36 | 1,134 个中 1,130 个完成；没有 429 |
| `cache` | 2026-10-26 13:04–14:57 | 缓存场景 | 264 | $6.70 | 264 个 HTTP 200 |
| `gateway` | 2026-10-24 | 经 LiteLLM 的五轮对话，十种配置 | 50 | $0.79 | 50 个完成 |

2026-10-26 的几次运行按标价共 $67.85。记录在 [`evidence/coding-matrix-20261026/`](evidence/coding-matrix-20261026/)，端点和 VM 名称已替换；2026-10-24 的记录在 [`evidence/`](evidence/)。

**边界。**
- **一个客户端、一个区域、一天、每个部署同一时间一个请求。** 没有并发、压力或长时间测试，也没有 Azure 以外的客户端。
- **公开练习、只答一次、不用工具。** 与 Aider 的评测一样，模型能看到待补全的文件和题目说明，看不到测试。`between_tools` 与 `disabled` 只在工具循环里有区别，本测试没有工具循环。
- **上限与样本量。** Opus 每格 54 个全过；18 道题的区间很宽，两格之间差几个回答属于噪声范围。
- **思考内容的显示。** 矩阵中 610 个请求用了思考 token，流式返回思考文字的有 0 个，所以首个可见文字包含全部思考时间。没有测试 `display: "summarized"`。
- **路由。** GlobalStandard 部署可能在 East US 2 以外处理请求，矩阵的 1,155 个响应里 `usage.inference_geo` 都是 `global`；换客户端位置或部署类型，延迟会不同。
- **费用。** 按 2026-10-26 的标价计算，不是 Azure 账单。
- **网关。** 保留的 2026-10-24 网关结果来自另一个区域，不能代表当前 East US 2 的 ACA 路径。

| 想要 | 去看 |
|---|---|
| 查看每一格、每道题、每条探测报错和每轮缓存 | [实测结果](docs/results_CN.md) |
| 重做测试或运行离线检查 | [复测与核验](docs/testing_CN.md) |
| 核对公开脚本相对实测脚本改了什么 | [来源记录](evidence/coding-matrix-20261026/provenance.json) |

## 操作步骤

| 顺序 | 执行位置 | 操作与完成观察 |
|---|---|---|
| 1 | Azure 配置工作机 | 准备 Foundry 和 ACA LiteLLM，按[网关部署](docs/testing_CN.md#gateway-setup)核对活动镜像与身份 |
| 2 | Linux 测量客户端 | 安装依赖并重建通过哈希校验的输入 |
| 3 | 同一 Linux 客户端 | 配置 HTTPS 网关地址，私下输入入口密钥 |
| 4 | 同一 Linux 客户端 | 运行一组缓存对照，检查原生写入与读取 |
| 5 | 同一 Linux 客户端 | 在新目录运行全部固定配置 |
| 6 | 同一 Linux 客户端 | 分析该目录，保留失败与缺失请求 |

**前提与范围。** 在已有 Linux 客户端使用 Bash、Python 3.12 或 3.13，并准备好 ACA 网关。复现本次位置条件时，客户端、网关和 Foundry 资源均使用 East US 2；GlobalStandard 仍不承诺推理区域。还没有网关时，先完成[网关部署](docs/testing_CN.md#gateway-setup)第 1-4 步，再回到这里。Ingress 必须放行实际测量客户端的出口 /32；配置工作机不同时，单独放行它的 /32。调用 Foundry 的是网关托管身份，客户端只使用入口密钥。模型调用和基础设施会计费；本轮未在全新云环境执行这些重组后的公开命令。

**1. 准备客户端和固定输入。** 从仓库工作副本的父目录开始。已有兼容 Python 环境就复用；下面仅在未激活环境且本地环境不存在时创建环境。

```bash
set -euo pipefail
test -d david-share || git clone --depth 1 --filter=blob:none https://github.com/david-xinyuwei/david-share.git
cd david-share/Agents/Claude-Foundry-LiteLLM-Performance
if [ -z "${VIRTUAL_ENV:-}" ]; then
  test -x .venv/bin/python || python3 -m venv .venv
  source .venv/bin/activate
fi
python -m pip install -r coding-matrix/requirements.txt pyarrow
RUN_ID="aca-$(date -u +%Y%m%d-%H%M%S)"
WORK="$PWD/private/$RUN_ID"
mkdir -p "$WORK"
python -B gateway-cache/build_swebench_problems.py \
  --manifest data/gateway-cache-problems.json --out "$WORK/problems.json"
```

预期 PASS、版本 `8d4bee9605fd8d72f14373a7f64d070c92f575c8` 和 12 道题。构建器在写出 JSON 前检查 parquet、题目顺序、源码提交及提示哈希。不一致就停止，不改用更新的数据集。下载数据及后续响应都保存在已忽略的 `private/` 下。

**2. 配置网关，不填 Foundry 直连端点。** 从 Container Apps 的 Ingress 获取 HTTPS 源地址，不带 `/v1/messages` 或 `/anthropic`。密钥由使用者私下输入，不写进命令、截图或 Git。

```bash
export GATEWAY_URL="https://<your-container-app-fqdn>"
read -r -s -p 'Gateway key (private): ' CLAUDE_GATEWAY_KEY
printf '\n'
export CLAUDE_GATEWAY_KEY
export CLAUDE_GATEWAY_BUDGET_ROOT="$WORK"
```

`deploy/config.yaml` 中的别名为 `opus55-standard`、`sonnet55-standard`、`haiku55-standard`，现有网关适配器将运行器模型名映射到这些别名；不会兜底直连 Foundry。别名不一致时先修正配置。

**3. 先验证一组缓存对照。** 此诊断计划一次预热及两次正式请求。它使用独立种子，不给后续全矩阵的组前缀预热。执行前确认本步骤的模型费用。

```bash
GATE="$WORK/gate"
python -u gateway-cache/aca_cache_matrix.py --run-dir "$GATE" \
  --source coding-matrix --gateway-url "$GATEWAY_URL" --problems "$WORK/problems.json" \
  --probe-summary evidence/coding-matrix-20261026/matrix/probe_summary.json \
  --only-cells 'sonnet|adaptive|low' --only-problems 'django__django-15320' \
  --seed "$RUN_ID-gate" --repeats 2 --max-tokens 128000 --ttl 1h --budget-usd 5
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$GATE" --out "$GATE/facts.json"
python -c 'import json,sys; record=json.load(open(sys.argv[1], encoding="utf-8")); assert record["coverage"]["collection_complete"] and record["cache_hit_pairs"] == 1, record; print("CACHE_PAIR_VERIFIED")' "$GATE/facts.json"
```

预期 CACHE_PAIR_VERIFIED、两份完整正式回答，以及先写后读的原生缓存证据。HTTP 200 不够。401/403 检查入口密钥、Ingress 和网关身份；400 看实际参数错误；429 看返回的限流维度与发送节奏；没有读取时检查前缀、间隔和路由。运行器的 TCP 低于 50 毫秒检查只是启发式条件，不证明地域。失败和请求标识都要保留。

**4. 运行并分析全矩阵。** 仍在同一终端，新建运行目录。冻结的探测清单固定 26 种配置、12 道题、两次正式重复及预热，共 650 个计划请求。新种子改变顺序和组标识，协议与题目正文不变；不要求数字等于已发布结果。示例的 85 美元是停止阈值，不是严格费用上限，因为可能有在途请求。适配器另对 WORK 下已计费用设置 95 美元停止阈值、预留 5 美元，合计 100 美元保护；选择预算前须查当前价格。

```bash
RUN="$WORK/matrix"
printf 'RUN_DIRECTORY=%s\n' "$RUN"
python -u gateway-cache/aca_cache_matrix.py --run-dir "$RUN" \
  --source coding-matrix --gateway-url "$GATEWAY_URL" --problems "$WORK/problems.json" \
  --probe-summary evidence/coding-matrix-20261026/matrix/probe_summary.json \
  --seed "$RUN_ID" --repeats 2 --max-tokens 128000 --ttl 1h --budget-usd 85
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$RUN" --out "$RUN/facts.json"
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$RUN" --out "$RUN/facts.json" --check
unset CLAUDE_GATEWAY_KEY
```

分析器读取本次 RUN，不读取已发布快照。预期 `facts match`；还须检查 facts.json 的 `coverage.collection_complete`、全部 26 格、传输错误、截断和原生缓存配对。BUDGET_STOP 或缺请求不算完成。前台进程可用 Ctrl+C 中断，这不会停止云资源。另开终端，用已输出目录运行 `tail -F <run-directory>/progress.log` 持续查看，或读取该目录的 run.json 看快照。续跑必须保留输入、种子和原运行目录，并先重新私下输入密钥。[新答案评分与独立出站审计](docs/testing_CN.md#fresh-aca-analysis)是另外的阶段，不由 `facts match` 覆盖。

**只想核对已有结果？** 使用[离线复算](docs/testing_CN.md#aca-snapshot-replay)，无需 Azure 凭据或模型调用。部署、重建输入、新采集和离线复算的验收分别记录。
