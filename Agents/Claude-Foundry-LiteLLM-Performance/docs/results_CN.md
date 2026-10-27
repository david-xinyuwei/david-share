# 实测结果

[README](../README_CN.md) · [复测与核验](testing_CN.md) · [English](results.md)

先列当前 East US 2 ACA 开启缓存测试的部分快照，包含全部计划配置与缺失范围；随后保留已取缔直连方案的历史编码矩阵、参数探测、缓存测试和 2026-10-24 网关检查。各批次的输入、计数和边界分别说明，不混算。

<a id="aca-gateway-snapshot"></a>

## ACA 网关：部分结果

**这是部分证据，不是全量测试通过。** 快照保存了计划 650 次中的 154 次请求：26 次预热，以及 624 次正式请求中的 128 次。运行文件最后更新于 `2026-10-27T00:07:59.720+00:00`。另有 496 次未包含在这份快照中，不能据此认定它们未执行或失败。

**客户端状态。** 在 `2026-10-26T20:10:18.9885833-07:00` 核验时，Azure 返回客户端 VM 为 `PowerState/deallocated`，已不会继续发送新请求。最终测试结果和停机原因尚未核实；快照里的 `RUNNING` 是当时的状态，不是当前状态。[核验记录](../evidence/gateway-cache-20261026/collection-status.json)。

**问题与方法。** 编码提示通过 East US 2 的 ACA LiteLLM 网关发送后，原样重复的第二次请求能否读到第一次写入的缓存，观测到的耗时和费用是多少？客户端、网关和 Foundry 资源均在 East US 2；每个模型同时只有一个请求。这是首次写入与重复读取的配对，不是关闭缓存的对照，也不能隔离网关自身开销。

**输入。** [12 道公开的 SWE-bench Lite BM25-13K 题目](../data/gateway-cache-problems.json)，来源版本和提示哈希保存在 [run.json](../evidence/gateway-cache-20261026/run.json)。这是作者的延迟与缓存测试，不是 SWE-bench 官方评分，也不是客户生产数据。[输入构建器](../gateway-cache/build_swebench_problems.py)重建提示，[运行器](../gateway-cache/aca_cache_matrix.py)遍历 26 个模式／档位组合，每题每格原样发送两次，每格另有一次预热。固定 `max_tokens: 128000`、`stream: true`、顶层 `cache_control: {"type": "ephemeral", "ttl": "1h"}`。计时从客户端即将发送请求时开始；首字指第一个非空文字增量，不是心跳或思考事件。

实际保存的参数记录（该指标投影不包含提示正文）：

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

| 模型 | 已保存／计划请求数（含预热） | 正常结束的请求数 | 截断请求数 | 完整正式配对数 |
|---|---:|---:|---:|---:|
| Opus 5.5 | 29/150 | 29 | 0 | 11 |
| Sonnet 5.5 | 46/250 | 44 | 2 | 17 |
| Haiku 5.5 | 79/250 | 79 | 0 | 34 |

**已经确认的事实。** 62 个正式配对的两次回答均正常结束。首次请求最多读取 0 个缓存 token；重复请求至少读回前次写入缓存 token 的 100.0%；两次复用同一响应 message ID 的配对有 0 个。这些原生 usage 记录证明对应配对发生了缓存读取，不证明代码正确或普遍提速。响应报告 `inference_geo: global`，返回的区域头为 East US 2，不能把它当成 GlobalStandard 固定区域推理的承诺。

**费用与边界。** 按记录采用的[标价模型](../coding-matrix/pricing.py)，已保存请求共 $13.90，包含预热、缓存写入／读取、输出和截断回答。这不是整轮最终花费或 Azure 账单，不含基础设施费用。尚未取得代码正确率评分。配对统计排除预热及任一回答未完整结束的配对，但上表仍保留这些请求；各格样本数量不同且不完整，不能据此给模型或档位排名。

### 全部计划配置

| 模型 | thinking.type | output_config.effort | 已保存／计划正式请求数 | 截断请求数（含预热） | 完整／计划配对数 |
|---|---|---|---:|---:|---:|
| Opus 5.5 | `adaptive` | `low` | 4/24 | 0 | 2/12 |
| Opus 5.5 | `adaptive` | `medium` | 6/24 | 0 | 3/12 |
| Opus 5.5 | `adaptive` | `high` | 7/24 | 0 | 3/12 |
| Opus 5.5 | `adaptive` | `xhigh` | 0/24 | 0 | 0/12 |
| Opus 5.5 | `adaptive` | `max` | 4/24 | 0 | 2/12 |
| Opus 5.5 | `adaptive` | `default` | 2/24 | 0 | 1/12 |
| Sonnet 5.5 | `adaptive` | `low` | 6/24 | 0 | 3/12 |
| Sonnet 5.5 | `adaptive` | `medium` | 4/24 | 0 | 2/12 |
| Sonnet 5.5 | `adaptive` | `high` | 2/24 | 0 | 1/12 |
| Sonnet 5.5 | `adaptive` | `xhigh` | 4/24 | 0 | 2/12 |
| Sonnet 5.5 | `adaptive` | `max` | 4/24 | 2 | 1/12 |
| Sonnet 5.5 | `adaptive` | `default` | 0/24 | 0 | 0/12 |
| Sonnet 5.5 | `between_tools` | `low` | 4/24 | 0 | 2/12 |
| Sonnet 5.5 | `between_tools` | `medium` | 0/24 | 0 | 0/12 |
| Sonnet 5.5 | `between_tools` | `high` | 6/24 | 0 | 3/12 |
| Sonnet 5.5 | `between_tools` | `default` | 6/24 | 0 | 3/12 |
| Haiku 5.5 | `adaptive` | `low` | 8/24 | 0 | 4/12 |
| Haiku 5.5 | `adaptive` | `medium` | 2/24 | 0 | 1/12 |
| Haiku 5.5 | `adaptive` | `high` | 12/24 | 0 | 6/12 |
| Haiku 5.5 | `adaptive` | `xhigh` | 2/24 | 0 | 1/12 |
| Haiku 5.5 | `adaptive` | `max` | 5/24 | 0 | 2/12 |
| Haiku 5.5 | `adaptive` | `default` | 8/24 | 0 | 4/12 |
| Haiku 5.5 | `disabled` | `low` | 4/24 | 0 | 2/12 |
| Haiku 5.5 | `disabled` | `medium` | 4/24 | 0 | 2/12 |
| Haiku 5.5 | `disabled` | `high` | 10/24 | 0 | 5/12 |
| Haiku 5.5 | `disabled` | `default` | 14/24 | 0 | 7/12 |

### 配对观测，不作排名

各格以最近秩法计算 P50，只统计完整正式配对。两次回答的输出长度可能不同，因此费用差异不能全部归因于缓存。

| 模型／thinking.type／output_config.effort | 完整配对数 | 首字 P50：第 1 次写缓存（秒） | 首字 P50：第 2 次读缓存（秒） | 平均费用：第 1 次（美元） | 平均费用：第 2 次（美元） |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 / adaptive / low | 2 | 1.14 | 1.00 | $0.177282 | $0.022452 |
| Opus 5.5 / adaptive / medium | 3 | 6.50 | 7.57 | $0.163915 | $0.033795 |
| Opus 5.5 / adaptive / high | 3 | 9.13 | 5.06 | $0.192016 | $0.100489 |
| Opus 5.5 / adaptive / xhigh | 0 | 无完整配对 | 无完整配对 | 无完整配对 | 无完整配对 |
| Opus 5.5 / adaptive / max | 2 | 104 | 132 | $1.492552 | $1.258076 |
| Opus 5.5 / adaptive / default | 1 | 1.40 | 1.36 | $0.174700 | $0.019514 |
| Sonnet 5.5 / adaptive / low | 3 | 0.76 | 0.83 | $0.085269 | $0.008851 |
| Sonnet 5.5 / adaptive / medium | 2 | 0.80 | 0.80 | $0.090508 | $0.017633 |
| Sonnet 5.5 / adaptive / high | 1 | 11.7 | 10.8 | $0.100894 | $0.023937 |
| Sonnet 5.5 / adaptive / xhigh | 2 | 25.1 | 16.1 | $0.121516 | $0.063874 |
| Sonnet 5.5 / adaptive / max | 1 | 470 | 364 | $0.792324 | $0.582819 |
| Sonnet 5.5 / adaptive / default | 0 | 无完整配对 | 无完整配对 | 无完整配对 | 无完整配对 |
| Sonnet 5.5 / between_tools / low | 2 | 0.75 | 0.77 | $0.072113 | $0.007486 |
| Sonnet 5.5 / between_tools / medium | 0 | 无完整配对 | 无完整配对 | 无完整配对 | 无完整配对 |
| Sonnet 5.5 / between_tools / high | 3 | 0.84 | 1.02 | $0.070411 | $0.013049 |
| Sonnet 5.5 / between_tools / default | 3 | 0.79 | 0.78 | $0.086894 | $0.011533 |
| Haiku 5.5 / adaptive / low | 4 | 2.70 | 4.08 | $0.004255 | $0.000797 |
| Haiku 5.5 / adaptive / medium | 1 | 13.0 | 7.21 | $0.005672 | $0.001368 |
| Haiku 5.5 / adaptive / high | 6 | 9.07 | 8.85 | $0.005043 | $0.002008 |
| Haiku 5.5 / adaptive / xhigh | 1 | 218 | 201 | $0.030188 | $0.025167 |
| Haiku 5.5 / adaptive / max | 2 | 178 | 262 | $0.034080 | $0.036289 |
| Haiku 5.5 / adaptive / default | 4 | 4.20 | 4.30 | $0.004834 | $0.001172 |
| Haiku 5.5 / disabled / low | 2 | 0.45 | 0.47 | $0.004257 | $0.000442 |
| Haiku 5.5 / disabled / medium | 2 | 0.41 | 0.43 | $0.003510 | $0.000409 |
| Haiku 5.5 / disabled / high | 5 | 0.48 | 0.55 | $0.003986 | $0.000418 |
| Haiku 5.5 / disabled / default | 7 | 0.49 | 0.51 | $0.003417 | $0.000413 |

**证据与复算。** [统计结果](../evidence/gateway-cache-20261026/interim-facts.json)、[导出哈希与脱敏范围](../evidence/gateway-cache-20261026/_export_manifest.json)、[Opus 记录](../evidence/gateway-cache-20261026/responses_opus.jsonl)、[Sonnet 记录](../evidence/gateway-cache-20261026/responses_sonnet.jsonl)、[Haiku 记录](../evidence/gateway-cache-20261026/responses_haiku.jsonl)。指标投影省略提示与回答正文、思考签名、私有端点和其他响应头，不能用于代码正确率评分。复算命令见[测试页](testing_CN.md#aca-snapshot-replay)。

## 编码矩阵

**已取缔的方案，仅保留历史证据。** 本节记录未带 `cache_control` 的 VM 直连编码矩阵，不满足当前开启缓存的 ACA 测试要求，也不是该轮测试的结果。原始记录和数值保持不变。

**问题。** 对每个 Claude 5.5 部署接受的每种思考模式和推理档位，编码回答完成的比例、首个可见文字的等待时间、费用，以及通过题目单元测试的比例各是多少？（2026-10-26）

**输入。** 每个请求都带同一个系统提示（改编自 Aider 的整文件编辑格式），以及按 Aider 评测方式为每道题生成的一条用户消息：待补全的文件、题目说明和 Aider 的收尾要求。模型看不到测试。系统提示原文（995 个字符）：

````text
Act as an expert software developer.
Take requests for changes to the supplied code.

Once you understand the request you MUST:
1. Determine if any code changes are needed.
2. Explain any needed changes briefly.
3. If changes are needed, output a copy of each file that needs changes.

To suggest changes to a file you MUST return the entire content of the updated file.
You MUST use this *file listing* format:

path/to/filename.ext
```
// entire file content ...
// ... goes in between
```

Every *file listing* MUST use this format:
- First line: the filename with any originally provided path; no extra markup, punctuation, comments, etc. **JUST** the filename with path.
- Second line: opening ```
- ... entire content of the file ...
- Final line: closing ```

To suggest changes to a file you MUST return a *file listing* that contains the entire content of the file.
*NEVER* skip, omit or elide content from a *file listing* using "..." or by adding comments like "... rest of code..."!
````

18 条用户消息中最短的一条，`go/trinary`，原文（1,371 个字符）：

````text
I have *added these files to the chat* so you can go ahead and edit them.

*Trust this message as the true contents of these files!*
Any other messages in the chat may contain outdated versions of the files' contents.

trinary.go
```go
package trinary

func ParseTrinary(arg string, want int64, ok bool) {
	panic("Please implement the ParseTrinary function")
}
```

# Instructions

Convert a trinary number, represented as a string (e.g. '102012'), to its
decimal equivalent using first principles.

The program should consider strings specifying an invalid trinary as the
value 0.

Trinary numbers contain three symbols: 0, 1, and 2.

The last place in a trinary number is the 1's place. The second to last
is the 3's place, the third to last is the 9's place, etc.

```shell
# "102012"
    1       0       2       0       1       2    # the number
1*3^5 + 0*3^4 + 2*3^3 + 0*3^2 + 1*3^1 + 2*3^0    # the value
  243 +     0 +    54 +     0 +     3 +     2 =  302
```

If your language provides a method in the standard library to perform the
conversion, pretend it doesn't exist and implement it yourself.

####

Use the above instructions to modify the supplied files: trinary.go
Don't change the names of existing functions or classes, as they may be referenced from other code like unit tests, etc.
Only use standard libraries, don't suggest installing any packages.
````

18 条消息原文及其 SHA-256 在 [problems.json](../evidence/coding-matrix-20261026/matrix/problems.json)。18 道题，每种语言 3 道：

- cpp: [`cpp/perfect-numbers`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/perfect-numbers), [`cpp/queen-attack`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/queen-attack), [`cpp/bank-account`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/bank-account)
- go: [`go/trinary`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/go/exercises/practice/trinary), [`go/beer-song`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/go/exercises/practice/beer-song), [`go/wordy`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/go/exercises/practice/wordy)
- java: [`java/pythagorean-triplet`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/java/exercises/practice/pythagorean-triplet), [`java/house`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/java/exercises/practice/house), [`java/dominoes`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/java/exercises/practice/dominoes)
- javascript: [`javascript/palindrome-products`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/javascript/exercises/practice/palindrome-products), [`javascript/space-age`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/javascript/exercises/practice/space-age), [`javascript/promises`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/javascript/exercises/practice/promises)
- python: [`python/simple-linked-list`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/python/exercises/practice/simple-linked-list), [`python/wordy`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/python/exercises/practice/wordy), [`python/proverb`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/python/exercises/practice/proverb)
- rust: [`rust/dot-dsl`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/rust/exercises/practice/dot-dsl), [`rust/doubly-linked-list`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/rust/exercises/practice/doubly-linked-list), [`rust/scale-generator`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/rust/exercises/practice/scale-generator)

**变量与固定项。** 变量：模型、`thinking.type` 和 `output_config.effort`，即探测接受的 21 种组合。固定项：`max_tokens` 128,000，`stream` 为 true，没有 `cache_control`、工具和采样参数；每格 18 道题 × 3 次；每格一个预热请求，不计分（`Write a Python function add(a, b) that returns the sum of two numbers. Reply with the code only.`）；每个部署同一时间一个请求，三个部署并行；按固定种子交错安排题目和格子的顺序，让某个慢时段对每格的影响相同。客户端把每分钟 token 和输出 token 控制在部署上限的 85% 以内；若出现 429 会按 `Retry-After` 重发，实际一次也没有出现。32,000 token 的试跑在 effort 为 max 时会截断回答，所以矩阵用 128,000，这也是 Claude effort 文档为 Sonnet 5.5 智能体编码给出的值。

### 每格结果

时间单位为秒。首个可见文字统计所有返回了文字的请求；完整回答只统计完成的请求。分位数用最近秩法。

| 格 | 完成 | 首字 P50 | 首字 P95 | 完整回答 P50 | 完整回答 P95 |
|---|---:|---:|---:|---:|---:|
| Opus · `adaptive` · low | 54/54 | 0.48 | 0.98 | 5.58 | 19.6 |
| Opus · `adaptive` · medium | 54/54 | 3.71 | 11.9 | 9.07 | 39.0 |
| Opus · `adaptive` · high | 54/54 | 4.05 | 20.4 | 9.85 | 54.0 |
| Opus · `adaptive` · xhigh | 54/54 | 6.04 | 74.7 | 12.7 | 89.7 |
| Opus · `adaptive` · max | 54/54 | 51.4 | 585 | 59.9 | 621 |
| Sonnet · `adaptive` · low | 54/54 | 0.46 | 0.93 | 5.22 | 17.3 |
| Sonnet · `adaptive` · medium | 54/54 | 0.50 | 0.87 | 5.53 | 17.4 |
| Sonnet · `adaptive` · high | 54/54 | 3.25 | 11.0 | 8.53 | 29.7 |
| Sonnet · `adaptive` · xhigh | 54/54 | 7.44 | 42.0 | 13.2 | 66.7 |
| Sonnet · `adaptive` · max | 53/54 | 190 | 585 | 199 | 616 |
| Sonnet · `between_tools` · low | 54/54 | 0.42 | 0.80 | 5.06 | 17.5 |
| Sonnet · `between_tools` · medium | 54/54 | 0.44 | 0.78 | 5.14 | 19.3 |
| Sonnet · `between_tools` · high | 54/54 | 0.39 | 0.74 | 5.56 | 19.8 |
| Haiku · `adaptive` · low | 54/54 | 4.13 | 18.1 | 6.75 | 31.3 |
| Haiku · `adaptive` · medium | 54/54 | 4.62 | 27.5 | 7.76 | 42.0 |
| Haiku · `adaptive` · high | 54/54 | 8.21 | 41.9 | 11.4 | 56.6 |
| Haiku · `adaptive` · xhigh | 54/54 | 14.9 | 118 | 17.8 | 134 |
| Haiku · `adaptive` · max | 51/54 | 121 | 421 | 125 | 424 |
| Haiku · `disabled` · low | 54/54 | 0.46 | 0.71 | 3.33 | 11.0 |
| Haiku · `disabled` · medium | 54/54 | 0.45 | 0.80 | 3.29 | 11.5 |
| Haiku · `disabled` · high | 54/54 | 0.43 | 0.69 | 3.62 | 12.2 |

| 格 | 思考 token P50 | 输出 token P50 | 每 1,000 次费用（美元） | 通过 | 按题目的 95% 区间 |
|---|---:|---:|---:|---:|---:|
| Opus · `adaptive` · low | 0 | 699 | $23.34 | 54/54 | 100% |
| Opus · `adaptive` · medium | 335 | 1,125 | $34.52 | 54/54 | 100% |
| Opus · `adaptive` · high | 372 | 1,203 | $38.75 | 54/54 | 100% |
| Opus · `adaptive` · xhigh | 656 | 1,579 | $65.36 | 54/54 | 100% |
| Opus · `adaptive` · max | 6,473 | 7,663 | $355.75 | 54/54 | 100% |
| Sonnet · `adaptive` · low | 0 | 820 | $13.04 | 41/54 | 56–94% |
| Sonnet · `adaptive` · medium | 0 | 923 | $13.57 | 42/54 | 61–93% |
| Sonnet · `adaptive` · high | 366 | 1,355 | $18.36 | 40/54 | 56–91% |
| Sonnet · `adaptive` · xhigh | 1,031 | 2,038 | $31.62 | 41/54 | 57–93% |
| Sonnet · `adaptive` · max | 30,403 | 32,129 | $356.49 | 44/54 | 63–96% |
| Sonnet · `between_tools` · low | 0 | 824 | $13.16 | 42/54 | 61–93% |
| Sonnet · `between_tools` · medium | 0 | 875 | $13.21 | 41/54 | 57–91% |
| Sonnet · `between_tools` · high | 0 | 939 | $13.76 | 44/54 | 65–94% |
| Haiku · `adaptive` · low | 786 | 1,709 | $1.27 | 24/54 | 26–65% |
| Haiku · `adaptive` · medium | 956 | 1,926 | $1.57 | 26/54 | 28–69% |
| Haiku · `adaptive` · high | 1,932 | 2,967 | $2.14 | 27/54 | 30–70% |
| Haiku · `adaptive` · xhigh | 3,744 | 4,740 | $4.19 | 28/54 | 30–72% |
| Haiku · `adaptive` · max | 33,505 | 34,821 | $22.26 | 28/54 | 30–74% |
| Haiku · `disabled` · low | 0 | 923 | $0.69 | 19/54 | 19–54% |
| Haiku · `disabled` · medium | 0 | 893 | $0.69 | 17/54 | 15–50% |
| Haiku · `disabled` · high | 0 | 1,019 | $0.73 | 21/54 | 19–61% |

### 未完成的请求

- `haiku|adaptive|max|rust/scale-generator|r1`：499 秒后 `stop_reason` 为 `max_tokens`；输出 128,000 个 token，没有可见文字。
- `haiku|adaptive|max|rust/scale-generator|r2`：497 秒后 `stop_reason` 为 `max_tokens`；输出 128,000 个 token，没有可见文字。
- `haiku|adaptive|max|rust/doubly-linked-list|r3`：491 秒后 `stop_reason` 为 `max_tokens`；输出 128,000 个 token，第 489 秒才出现可见文字。
- `sonnet|adaptive|max|java/house|r2`：第 0.71 秒收到 `message_start`，随后只有两个 ping，再无事件；客户端 600 秒读超时在第 661 秒结束请求。按没有代码计分。

### 按题目

每个模型所有格合计的通过数：Opus 每道题 5 格 × 3 次 = 15 个回答，Sonnet 和 Haiku 8 × 3 = 24 个。

| 题目 | Opus | Sonnet | Haiku |
|---|---:|---:|---:|
| `cpp/perfect-numbers` | 15/15 | 24/24 | 13/24 |
| `cpp/queen-attack` | 15/15 | 21/24 | 1/24 |
| `cpp/bank-account` | 15/15 | 23/24 | 13/24 |
| `go/trinary` | 15/15 | 14/24 | 0/24 |
| `go/beer-song` | 15/15 | 14/24 | 0/24 |
| `go/wordy` | 15/15 | 24/24 | 22/24 |
| `java/pythagorean-triplet` | 15/15 | 24/24 | 24/24 |
| `java/house` | 15/15 | 1/24 | 0/24 |
| `java/dominoes` | 15/15 | 24/24 | 0/24 |
| `javascript/palindrome-products` | 15/15 | 24/24 | 15/24 |
| `javascript/space-age` | 15/15 | 24/24 | 21/24 |
| `javascript/promises` | 15/15 | 3/24 | 0/24 |
| `python/simple-linked-list` | 15/15 | 23/24 | 20/24 |
| `python/wordy` | 15/15 | 24/24 | 19/24 |
| `python/proverb` | 15/15 | 24/24 | 19/24 |
| `rust/dot-dsl` | 15/15 | 16/24 | 1/24 |
| `rust/doubly-linked-list` | 15/15 | 24/24 | 22/24 |
| `rust/scale-generator` | 15/15 | 4/24 | 0/24 |

### 按语言

| 语言 | Opus | Sonnet | Haiku |
|---|---:|---:|---:|
| cpp | 45/45 | 68/72 | 27/72 |
| go | 45/45 | 52/72 | 22/72 |
| java | 45/45 | 49/72 | 24/72 |
| javascript | 45/45 | 51/72 | 36/72 |
| python | 45/45 | 71/72 | 58/72 |
| rust | 45/45 | 44/72 | 23/72 |

### 相同档位下开启与关闭思考

两边都用 low、medium、high 三个可以关闭思考的档位，题目相同，各 162 个回答。区间按题目重抽。

| 模型 | `adaptive` | 关闭思考 | 差（百分点） | 95% 区间 | 更好 / 更差 / 持平的题数 |
|---|---:|---:|---:|---:|---:|
| Sonnet 5.5（`between_tools`） | 75.9% | 78.4% | -2.5 | -7.4 到 +1.9 | 3 / 4 / 11 |
| Haiku 5.5（`disabled`） | 47.5% | 35.2% | +12.3 | +2.5 到 +23.5 | 9 / 2 / 7 |

## 参数探测

**问题。** 每个部署接受哪些思考模式、推理档位、采样参数、输出上限和缓存设置？**输入。** 每个取值和模型发一个流式请求，除非该行另有说明，`max_tokens` 为 1,024，用户消息为 `Reply with exactly one word: OK`；2026-10-26 UTC 08:11 到 08:12 共 102 个请求。单元格是 HTTP 状态，字母对应下方的报错原文。被接受的思考模式和推理档位就是编码矩阵的各格。

| 请求 | Opus | Sonnet | Haiku |
|---|---|---|---|
| effort 设为 `"probe-invalid-value"` | 400 (a) | 400 (a) | 400 (a) |
| `adaptive`，effort low 到 max | 200 | 200 | 200 |
| `adaptive`，不传 effort | 200 | 200 | 200 |
| `disabled`，effort low、medium、high | 400 (b) | 400 (c) | 200 |
| `disabled`，effort xhigh、max | 400 (b) | 400 (c) | 400 (d, e) |
| `disabled`，不传 effort | 400 (b) | 400 (c) | 200 |
| `between_tools`，effort low、medium、high | 400 (f) | 200 | 400 (f) |
| `between_tools`，effort xhigh、max | 400 (f) | 400 (d, e) | 400 (f) |
| `between_tools`，不传 effort | 400 (f) | 200 | 400 (f) |
| 不传 `thinking` | 200 | 200 | 200 |
| `enabled` 加 `budget_tokens` 1,024 | 400 (g) | 400 (g) | 400 (g) |
| `adaptive` + `temperature` 0.5 | 400 (h) | 400 (h) | 400 (h) |
| `adaptive` + `top_p` 0.9 | 400 (i) | 400 (i) | 400 (i) |
| `adaptive` + `top_k` 40 | 400 (j) | 400 (j) | 400 (j) |
| 关闭思考 + `temperature` 0.5 | 未发送：没有关闭思考的模式 | 400 (k) | 400 (k) |
| 关闭思考 + `top_p` 0.9 | 未发送：没有关闭思考的模式 | 400 (l) | 400 (l) |
| 关闭思考 + `top_k` 40 | 未发送：没有关闭思考的模式 | 400 (m) | 400 (m) |
| `max_tokens` 1,000,000 | 400 (n) | 400 (o) | 400 (p) |
| `max_tokens` 32,000 | 200 | 200 | 200 |
| system 块带 `cache_control` 和 `"ttl": "1h"` | 200 | 200 | 200 |
| 顶层 `cache_control` | 200 | 200 | 200 |
| 连续四个 `max_tokens` 32,000 的请求 | 200 | 200 | 200 |

HTTP 400 报错原文：

- (a) `output_config.effort: Input should be 'low', 'medium', 'high', 'xhigh' or 'max'`
- (b) `"thinking.type.disabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort" to control thinking behavior.`
- (c) `To turn thinking off on this model, send "thinking": {"type": "between_tools"} instead of {"type": "disabled"}. The model does not think before responding. The short updates it writes between tool calls come back as thinking blocks.`
- (d) `output_config.effort 'xhigh' is not supported when thinking is disabled on this model. Use effort 'high' or below, or enable thinking.`
- (e) `output_config.effort 'max' is not supported when thinking is disabled on this model. Use effort 'high' or below, or enable thinking.`
- (f) `"thinking.type.between_tools" is not supported for this model.`
- (g) `"thinking.type.enabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort" to control thinking behavior.`
- (h) `` `temperature` may only be set to 1 when thinking is enabled or in adaptive mode. Please consult our documentation at https://platform.claude.com/docs/en/build-with-claude/extended-thinking ``
- (i) `` `top_p` must be greater than or equal to 0.95 or unset when thinking is enabled or in adaptive mode. Please consult our documentation at https://platform.claude.com/docs/en/build-with-claude/extended-thinking ``
- (j) `` `top_k` must be unset when thinking is enabled or in adaptive mode. Please consult our documentation at https://platform.claude.com/docs/en/build-with-claude/extended-thinking ``
- (k) `` `temperature` is deprecated for this model. ``
- (l) `` `top_p` is deprecated for this model. ``
- (m) `` `top_k` is deprecated for this model. ``
- (n) `max_tokens: 1000000 > 128000, which is the maximum allowed number of output tokens for claude-opus-5-5`
- (o) `max_tokens: 1000000 > 128000, which is the maximum allowed number of output tokens for claude-sonnet-5-5`
- (p) `max_tokens: 1000000 > 128000, which is the maximum allowed number of output tokens for claude-haiku-5-5`

**思考内容。** 本次探测中用了思考 token 的请求：Opus `adaptive_max` 30, Opus `adaptive_xhigh` 19, Sonnet `adaptive_max` 29, Haiku `adaptive_max` 30；其余被接受的请求都没有思考。编码矩阵中 610 个请求用了思考 token，没有一个流式返回思考文字：thinking 块只带签名、没有文字，即文档所说的 `omitted` 显示方式。

## 提示缓存

**问题。** 在多轮编码对话中，每次提示有多少从缓存读取、能省多少钱、哪些操作会让缓存失效？（2026-10-26）

**输入。** 系统提示分两块：先是 `Conversation <nonce>. ` 加下面的说明，然后是 `Repository files:` 加三个 httpx 0.28.1 源文件（`_auth.py`、`_config.py`、`_urls.py`；42,058 个字符）。nonce 让每段对话都从冷缓存开始；*新对话* 复用前一段对话的 nonce。五个文件的更大上下文（152,546 个字符）只用于冷热对照。说明原文：

````text
You are a senior Python engineer pairing with a developer on the httpx code base.
The repository files you may read are included below. Answer concisely, show complete code when you write code,
and keep the existing style (type hints, docstrings, naming).
````

四个问题原文，按顺序：

1. In five bullet points, explain how an Auth subclass takes part in sending a request: which methods are called, in what order, and how a response can trigger a retry.
2. Write a new Auth subclass BearerTokenAuth that takes a token-refresh callback, sends 'Authorization: Bearer <token>', and refreshes the token once when the server answers 401. Return the complete class.
3. Write pytest tests for BearerTokenAuth using httpx.MockTransport: one test for a normal request and one for refresh-on-401.
4. Write a git commit message (subject line plus a short body) for the change we made in this session.

新对话的问题：`List the public classes defined in these files, with one line each on what they are for.` 冷热对照的问题：`Reply with the single word OK.`

**固定项。** effort 为 low；除非场景另有改动，Opus 用 `adaptive`，Sonnet 用 `between_tools`，Haiku 用 `disabled`；`max_tokens` 3,000（冷热对照为 256）；每个场景重复 2 次，每种上下文 5 对；客户端把速率控制在部署上限的 85% 以内；每个模型的缓存测试在它的矩阵请求全部结束后才开始。共 264 个请求，全部 HTTP 200，限流 0 次。

| 场景 | 改了什么 |
|---|---|
| `none` | 不带 `cache_control` |
| `auto` | 每轮带顶层 `cache_control`（自动缓存） |
| `auto_second` | `auto` 之后开一段说明和文件相同的新对话，问一个问题 |
| `system_only` | 只在仓库文件块末尾放一个断点 |
| `system_only_second` | `system_only` 之后的新对话，问一个问题 |
| `system_plus_auto` | 仓库断点加顶层自动缓存 |
| `system_plus_auto_second` | `system_plus_auto` 之后的新对话，问一个问题 |
| `effort_switch` | `adaptive`，自动缓存，顶层 effort 依次为 low、low、high、low |
| `effort_switch_message` | 同样的切换改用按消息设置 effort，带 beta 头 |
| `mode_switch` | 自动缓存；思考依次为关、关、`adaptive`、`adaptive`（Sonnet、Haiku） |
| `prewarm` | 先发带仓库断点的非流式 `max_tokens: 0` 请求，再问第一个问题 |
| `idle_5m` | 自动缓存，默认 5 分钟 TTL，第 2 轮前空闲 6.5 分钟 |
| `idle_1h` | 自动缓存，`"ttl": "1h"`，第 2 轮前空闲 6.5 分钟 |
| `ttft_cold_repo` | 冷请求，仓库上下文，只答一个词，五对 |
| `ttft_warm_repo` | 再发一次相同提示 |
| `ttft_cold_large` | 冷请求，更大的上下文（Sonnet、Haiku） |
| `ttft_warm_large` | 再发一次相同提示 |

### 每轮提示从缓存读取的比例

读取 token ÷（未缓存 + 写入 + 读取的输入 token），取各次重复的平均。`—`：该模型没有这个场景。

| 场景 | 轮次 | Opus | Sonnet | Haiku |
|---|---:|---:|---:|---:|
| `none` | 1 | 0.0% | 0.0% | 0.0% |
| `none` | 2 | 0.0% | 0.0% | 0.0% |
| `none` | 3 | 0.0% | 0.0% | 0.0% |
| `none` | 4 | 0.0% | 0.0% | 0.0% |
| `auto` | 1 | 0.0% | 0.0% | 0.0% |
| `auto` | 2 | 96.1% | 95.9% | 95.9% |
| `auto` | 3 | 94.9% | 95.1% | 97.1% |
| `auto` | 4 | 94.3% | 94.7% | 96.0% |
| `auto_second` | 1 | 0.0% | 0.0% | 0.0% |
| `system_only` | 1 | 0.0% | 0.0% | 0.0% |
| `system_only` | 2 | 95.5% | 95.2% | 95.8% |
| `system_only` | 3 | 90.7% | 90.8% | 93.0% |
| `system_only` | 4 | 86.3% | 86.0% | 89.4% |
| `system_only_second` | 1 | 99.8% | 99.8% | 99.8% |
| `system_plus_auto` | 1 | 0.0% | 0.0% | 0.0% |
| `system_plus_auto` | 2 | 96.1% | 95.9% | 95.9% |
| `system_plus_auto` | 3 | 95.0% | 95.6% | 96.8% |
| `system_plus_auto` | 4 | 94.9% | 95.0% | 95.8% |
| `system_plus_auto_second` | 1 | 99.8% | 99.8% | 99.8% |
| `effort_switch` | 1 | 0.0% | 0.0% | 0.0% |
| `effort_switch` | 2 | 96.6% | 95.6% | 96.3% |
| `effort_switch` | 3 | 95.5% | 95.6% | 96.7% |
| `effort_switch` | 4 | 95.1% | 94.6% | 95.0% |
| `effort_switch_message` | 1 | 0.0% | 0.0% | 0.0% |
| `effort_switch_message` | 2 | 96.0% | 96.1% | 96.3% |
| `effort_switch_message` | 3 | 95.1% | 95.8% | 96.8% |
| `effort_switch_message` | 4 | 93.7% | 94.9% | 95.0% |
| `mode_switch` | 1 | — | 0.0% | 0.0% |
| `mode_switch` | 2 | — | 95.5% | 95.7% |
| `mode_switch` | 3 | — | 0.0% | 0.0% |
| `mode_switch` | 4 | — | 94.7% | 96.1% |
| `prewarm` | 1 | 0.0% | 0.0% | 0.0% |
| `prewarm` | 2 | 99.7% | 99.7% | 99.7% |
| `idle_5m` | 1 | 0.0% | 0.0% | 0.0% |
| `idle_5m` | 2 | 0.0% | 0.0% | 0.0% |
| `idle_1h` | 1 | 0.0% | 0.0% | 0.0% |
| `idle_1h` | 2 | 96.0% | 95.4% | 96.3% |
| `ttft_cold_repo` | 1 | 0.0% | 0.0% | 0.0% |
| `ttft_warm_repo` | 1 | 99.9% | 99.9% | 99.9% |
| `ttft_cold_large` | 1 | — | 0.0% | 0.0% |
| `ttft_warm_large` | 1 | — | 100.0% | 100.0% |

### 每段对话相对不缓存的费用变化

场景内各请求的平均标价费用，与同样 token 数按不缓存计价相比。负数表示更便宜。

| 场景 | Opus | Sonnet | Haiku |
|---|---:|---:|---:|
| `none` | -0% | -0% | -0% |
| `auto` | -52% | -53% | -52% |
| `auto_second` | +20% | +21% | +21% |
| `system_only` | -50% | -51% | -51% |
| `system_only_second` | -80% | -76% | -76% |
| `system_plus_auto` | -52% | -54% | -52% |
| `system_plus_auto_second` | -77% | -78% | -78% |
| `effort_switch` | -51% | -51% | -46% |
| `effort_switch_message` | -49% | -52% | -45% |
| `mode_switch` | — | -27% | -27% |
| `prewarm` | -32% | -32% | -30% |
| `idle_5m` | +20% | +20% | +22% |
| `idle_1h` | +4% | +4% | +6% |
| `ttft_cold_repo` | +25% | +25% | +25% |
| `ttft_warm_repo` | -95% | -95% | -90% |
| `ttft_cold_large` | — | +25% | +25% |
| `ttft_warm_large` | — | -95% | -90% |

### 冷请求与热请求

| 模型 | 上下文 | 提示 token | 首字 P50 冷 → 热（秒） | 费用 冷 → 热（美元） |
|---|---|---:|---:|---:|
| Opus 5.5 | 三个文件 | 15,459 | 1.51 → 1.38 | 0.0774 → 0.0032 |
| Sonnet 5.5 | 三个文件 | 15,456 | 1.03 → 0.89 | 0.0387 → 0.0016 |
| Sonnet 5.5 | 五个文件 | 53,313 | 0.94 → 0.92 | 0.1333 → 0.0054 |
| Haiku 5.5 | 三个文件 | 15,458 | 0.75 → 0.71 | 0.0019 → 0.0002 |
| Haiku 5.5 | 五个文件 | 53,313 | 0.85 → 0.87 | 0.0067 → 0.0005 |

每行五对；相差零点一秒左右在单个请求的波动范围内。每轮的 token 数在 [cache_facts.json](../evidence/coding-matrix-20261026/cache/cache_facts.json)，每个请求在 [cache_results.jsonl](../evidence/coding-matrix-20261026/cache/cache_results.jsonl)。

## 网关测试

**问题。** 经过 LiteLLM 网关时，关闭回答前的思考、扩大缓存覆盖范围，是否改变首个可见文字的等待？（2026-10-24）

**拓扑。** Windows 客户端（PowerShell 7.6.7，位置未记录）→ Japan East 的 Azure Container Apps 上的 LiteLLM 1.106.2（1 vCPU、2 GiB、单副本、单 worker，用托管身份）→ East US 2 的 Foundry 资源。网关和模型不在同一区域，所以下面的时间包含日本到美国东部的往返，不能代表网关本身增加的延迟。

### 输入与方法

下面是实际发送的五个问题原文；所有配置使用同一材料和顺序。

1. Explain the request flow from the desktop client to a Claude model on Azure. Which components are shown in the test target architecture, and which are our prototype implementation choices?

2. Using that flow and the supplied code, where could a timeout or incomplete streamed response originate? Separate what these files establish from what would require additional evidence.

3. Continuing your analysis, propose the smallest checks that preserve the client's /v1/messages interface and the three independent model routes. What must be verified before attributing an error to a model?

4. Turn those checks into a concise five-turn validation checklist. Include conversation-history integrity, actual prompt-cache usage, first visible text, full-response completion, and token accounting; do not invent measurements.

5. Review your checklist against the observer code. Which evidence can it already retain, what additional client evidence is needed, and what sensitive information must not be logged? End with the main limits of this small workflow test.

[完整材料与矩阵](../data/matrix.json)

五种合法模型/模式组合，各做两种缓存配置，每组独立五轮。固定 medium、stream=true、max_tokens=4096、无工具、零重试、单请求串行。先执行仅系统前缀阶段，再执行会话缓存阶段；未清缓存，也没有额外预热。两阶段的模型执行顺序均为 Haiku disabled、Sonnet between_tools、Opus adaptive、Sonnet adaptive、Haiku adaptive。后续历史来自各组自己的响应，不保证逐字相同。公开运行器按 matrix.json 中的顺序执行，与这次的执行顺序不同。

### 观察结果

2026-10-24 的原实验 **50/50 正常完成**，按当时记录费率估算的模型费用为 **US$0.79**。首字为发送请求到第一个非空 text_delta；P50 为五轮中位数。

<img src="../images/latency-zh.svg" width="520" alt="每组五次请求的首个可见文字时间分布" />

图由本轮 50 条记录生成：每个圆点是一次请求，横轴为秒；纵向小偏移仅区分轮次，没有数值含义。蓝色为自适应思考，绿色为无前置思考。不是质量排名。 [Source](../evidence/requests.json)

**首个可见文字 P50，单位：秒**

| 模型 / 模式 | 仅系统前缀 | 系统与历史 |
|---|---:|---:|
| Opus 5.5<br>自适应思考 | 9.321 | 7.293 |
| Sonnet 5.5<br>自适应思考 | 8.051 | 1.434 |
| Sonnet 5.5<br>无前置思考 | 0.954 | 0.893 |
| Haiku 5.5<br>自适应思考 | 4.235 | 2.910 |
| Haiku 5.5<br>关闭思考 | 0.810 | 0.781 |

**全部五轮的缓存读取占比，单位：%**

缓存读取占比统计同一配置全部五轮：读取 token 总和 /（未缓存、写入、读取 token 总和）。首轮写入也在分母里，不算命中；新问题和新增历史仍需处理。仅系统前缀只复用固定资料，系统与历史额外启用随会话增长的自动缓存。这里不是末轮命中率，也不是平均每轮百分比。

| 模型 / 模式 | 仅系统前缀 | 系统与历史 |
|---|---:|---:|
| Opus 5.5<br>自适应思考 | 28.27 | 69.25 |
| Sonnet 5.5<br>自适应思考 | 33.52 | 67.68 |
| Sonnet 5.5<br>无前置思考 | 39.96 | 70.68 |
| Haiku 5.5<br>自适应思考 | 32.81 | 71.04 |
| Haiku 5.5<br>关闭思考 | 47.47 | 72.44 |

输出吞吐包含思考，可见输出吞吐扣除 thinking tokens；两者均除以完整耗时，不是独立解码速度。

**完整结束 P50，秒**

| 模型 / 模式 | 仅系统前缀 | 系统与历史 |
|---|---:|---:|
| Opus 5.5<br>自适应思考 | 18.334 | 16.022 |
| Sonnet 5.5<br>自适应思考 | 15.233 | 8.604 |
| Sonnet 5.5<br>无前置思考 | 7.991 | 7.874 |
| Haiku 5.5<br>自适应思考 | 7.160 | 5.917 |
| Haiku 5.5<br>关闭思考 | 3.553 | 3.983 |

**输出 P50，token/秒，含思考**

| 模型 / 模式 | 仅系统前缀 | 系统与历史 |
|---|---:|---:|
| Opus 5.5<br>自适应思考 | 95.78 | 90.86 |
| Sonnet 5.5<br>自适应思考 | 117.84 | 115.29 |
| Sonnet 5.5<br>无前置思考 | 114.76 | 112.64 |
| Haiku 5.5<br>自适应思考 | 183.51 | 172.62 |
| Haiku 5.5<br>关闭思考 | 153.96 | 156.55 |

**可见输出 P50，token/秒**

| 模型 / 模式 | 仅系统前缀 | 系统与历史 |
|---|---:|---:|
| Opus 5.5<br>自适应思考 | 55.50 | 58.30 |
| Sonnet 5.5<br>自适应思考 | 62.56 | 109.48 |
| Sonnet 5.5<br>无前置思考 | 114.76 | 112.64 |
| Haiku 5.5<br>自适应思考 | 96.37 | 111.11 |
| Haiku 5.5<br>关闭思考 | 153.96 | 156.55 |

**模型估算费用，美元**

| 模型 / 模式 | 仅系统前缀 | 系统与历史 |
|---|---:|---:|
| Opus 5.5<br>自适应思考 | 0.258394 | 0.193501 |
| Sonnet 5.5<br>自适应思考 | 0.110115 | 0.081004 |
| Sonnet 5.5<br>无前置思考 | 0.073466 | 0.060174 |
| Haiku 5.5<br>自适应思考 | 0.004840 | 0.003642 |
| Haiku 5.5<br>关闭思考 | 0.002472 | 0.002288 |

关闭模式在无工具任务中均为零 thinking token。Sonnet 的 between_tools 不是所有场景下的完全关闭；Opus 5.5 不支持关闭。P95 在五个样本下等于最大值，不代表生产尾延迟。

更高缓存占比不等于全部首字改善来自缓存：各会话独立生成，历史和 thinking 用量随之变化。Sonnet adaptive 的两组分别只有 3/5 与 2/5 请求产生 thinking。所有计时在客户端，未分离服务端排队、网络和推理计算。

### 分段时间

所有时间从客户端发出请求起算。Headers 是完整响应头到达，First body byte 是响应正文首 byte，不是完整 HTTP 首 byte。First SSE 包括 metadata/heartbeat，不等于可见回答。thinking 事件到达不等于推理开始；omitted 模式可能延后或合并事件。Post-SSE wait 是逐请求相减后取 P50，不是两个 P50 相减。

### 逐轮记录

下列总输入、读取、写入、输出和思考列单位均为 token；总输入等于未缓存 + 读取 + 写入，可见输出等于输出 - 思考。完整回答、请求及事件时间在证据文件内。每组 P95 为五轮中的最大值。

#### Opus 5.5 / 自适应 / 仅系统

`opus-adaptive-system`

产生思考的请求：5/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 1.453 | 1.671 |
| 首个 SSE | 1.455 | 1.671 |
| 首个文本 | 9.321 | 10.988 |
| SSE 后等待 | 8.027 | 9.960 |
| 完整结束 | 18.334 | 20.904 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 9.171 | 17.495 |
| 2 | 10.773 | 18.334 |
| 3 | 7.071 | 15.864 |
| 4 | 9.321 | 18.717 |
| 5 | 10.988 | 20.904 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3838 | 1961 | 0 |
| 3 | 5654 | 1961 | 0 |
| 4 | 7169 | 1961 | 0 |
| 5 | 9071 | 1961 | 0 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 1768 | 797 |
| 2 | 1756 | 959 |
| 3 | 1444 | 503 |
| 4 | 1837 | 783 |
| 5 | 1957 | 845 |

#### Sonnet 5.5 / 自适应 / 仅系统

`sonnet-adaptive-system`

产生思考的请求：3/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 1.187 | 1.621 |
| 首个 SSE | 1.188 | 1.621 |
| 首个文本 | 8.051 | 9.531 |
| SSE 后等待 | 7.029 | 8.248 |
| 完整结束 | 15.233 | 16.571 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 1.622 | 8.757 |
| 2 | 1.073 | 9.777 |
| 3 | 8.051 | 15.233 |
| 4 | 8.616 | 16.051 |
| 5 | 9.531 | 16.571 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3106 | 1961 | 0 |
| 3 | 4212 | 1961 | 0 |
| 4 | 6078 | 1961 | 0 |
| 5 | 7990 | 1961 | 0 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 1038 | 0 |
| 2 | 1048 | 0 |
| 3 | 1795 | 842 |
| 4 | 1847 | 851 |
| 5 | 1995 | 1006 |

#### Sonnet 5.5 / 无前置思考 / 仅系统

`sonnet-between-system`

产生思考的请求：0/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 0.952 | 2.406 |
| 首个 SSE | 0.953 | 2.406 |
| 首个文本 | 0.954 | 2.408 |
| SSE 后等待 | 0.001 | 0.001 |
| 完整结束 | 7.991 | 10.073 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 2.408 | 7.808 |
| 2 | 0.700 | 7.991 |
| 3 | 0.995 | 7.783 |
| 4 | 0.865 | 8.285 |
| 5 | 0.954 | 10.073 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 1960 |
| 2 | 2900 | 1960 | 0 |
| 3 | 3877 | 1960 | 0 |
| 4 | 4892 | 1960 | 0 |
| 5 | 5935 | 1960 | 0 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 831 | 0 |
| 2 | 917 | 0 |
| 3 | 944 | 0 |
| 4 | 978 | 0 |
| 5 | 1144 | 0 |

#### Haiku 5.5 / 自适应 / 仅系统

`haiku-adaptive-system`

产生思考的请求：5/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 0.864 | 1.002 |
| 首个 SSE | 0.865 | 1.003 |
| 首个文本 | 4.235 | 4.436 |
| SSE 后等待 | 3.260 | 3.590 |
| 完整结束 | 7.160 | 7.461 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 4.262 | 7.328 |
| 2 | 4.235 | 7.160 |
| 3 | 3.822 | 6.641 |
| 4 | 2.105 | 4.804 |
| 5 | 4.436 | 7.461 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3622 | 1961 | 0 |
| 3 | 4996 | 1961 | 0 |
| 4 | 6198 | 1961 | 0 |
| 5 | 7070 | 1961 | 0 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 1552 | 791 |
| 2 | 1314 | 680 |
| 3 | 1131 | 549 |
| 4 | 807 | 239 |
| 5 | 1410 | 691 |

#### Haiku 5.5 / 关闭思考 / 仅系统

`haiku-disabled-system`

产生思考的请求：0/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 0.808 | 1.538 |
| 首个 SSE | 0.809 | 1.554 |
| 首个文本 | 0.810 | 1.563 |
| SSE 后等待 | 0.001 | 0.008 |
| 完整结束 | 3.553 | 4.804 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 1.563 | 4.389 |
| 2 | 0.810 | 3.553 |
| 3 | 0.753 | 3.234 |
| 4 | 0.742 | 3.413 |
| 5 | 0.874 | 4.804 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 1960 |
| 2 | 2753 | 1960 | 0 |
| 3 | 3360 | 1960 | 0 |
| 4 | 3910 | 1960 | 0 |
| 5 | 4477 | 1960 | 0 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 684 | 0 |
| 2 | 547 | 0 |
| 3 | 479 | 0 |
| 4 | 502 | 0 |
| 5 | 741 | 0 |

#### Opus 5.5 / 自适应 / 系统与历史

`opus-adaptive-conversation`

产生思考的请求：5/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 1.435 | 1.677 |
| 首个 SSE | 1.436 | 1.678 |
| 首个文本 | 7.293 | 8.749 |
| SSE 后等待 | 6.215 | 7.191 |
| 完整结束 | 16.022 | 18.627 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 7.293 | 16.022 |
| 2 | 8.054 | 18.054 |
| 3 | 6.088 | 13.685 |
| 4 | 4.541 | 13.207 |
| 5 | 8.749 | 18.627 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 3817 | 2014 | 1799 |
| 3 | 5513 | 3813 | 1696 |
| 4 | 6748 | 5509 | 1235 |
| 5 | 8013 | 6744 | 1265 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 1747 | 697 |
| 2 | 1636 | 653 |
| 3 | 1164 | 390 |
| 4 | 1200 | 299 |
| 5 | 1741 | 655 |

#### Sonnet 5.5 / 自适应 / 系统与历史

`sonnet-adaptive-conversation`

产生思考的请求：2/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 1.154 | 1.432 |
| 首个 SSE | 1.155 | 1.433 |
| 首个文本 | 1.434 | 8.586 |
| SSE 后等待 | 0.002 | 7.282 |
| 完整结束 | 8.604 | 17.257 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 1.434 | 7.260 |
| 2 | 1.029 | 8.604 |
| 3 | 0.998 | 8.385 |
| 4 | 6.170 | 13.774 |
| 5 | 8.586 | 17.257 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 2905 | 2014 | 887 |
| 3 | 3905 | 2901 | 1000 |
| 4 | 4954 | 3901 | 1049 |
| 5 | 6559 | 4950 | 1605 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 837 | 0 |
| 2 | 942 | 0 |
| 3 | 980 | 0 |
| 4 | 1540 | 610 |
| 5 | 2021 | 846 |

#### Sonnet 5.5 / 无前置思考 / 系统与历史

`sonnet-between-conversation`

产生思考的请求：0/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 0.879 | 0.984 |
| 首个 SSE | 0.881 | 0.985 |
| 首个文本 | 0.893 | 0.986 |
| SSE 后等待 | 0.001 | 0.012 |
| 完整结束 | 7.874 | 8.552 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 0.986 | 7.066 |
| 2 | 0.749 | 8.552 |
| 3 | 0.830 | 7.874 |
| 4 | 0.937 | 6.643 |
| 5 | 0.893 | 8.524 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 2013 |
| 2 | 2958 | 2013 | 941 |
| 3 | 3972 | 2954 | 1014 |
| 4 | 4930 | 3968 | 958 |
| 5 | 5735 | 4926 | 805 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 889 | 0 |
| 2 | 954 | 0 |
| 3 | 887 | 0 |
| 4 | 740 | 0 |
| 5 | 972 | 0 |

#### Haiku 5.5 / 自适应 / 系统与历史

`haiku-adaptive-conversation`

产生思考的请求：5/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 0.969 | 1.123 |
| 首个 SSE | 0.970 | 1.124 |
| 首个文本 | 2.910 | 4.020 |
| SSE 后等待 | 2.002 | 2.895 |
| 完整结束 | 5.917 | 7.702 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 4.020 | 7.702 |
| 2 | 2.910 | 6.552 |
| 3 | 2.972 | 5.917 |
| 4 | 1.752 | 4.492 |
| 5 | 2.829 | 5.739 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 3557 | 2014 | 1539 |
| 3 | 4748 | 3553 | 1191 |
| 4 | 5787 | 4744 | 1039 |
| 5 | 6545 | 5783 | 758 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 1487 | 687 |
| 2 | 1131 | 403 |
| 3 | 968 | 361 |
| 4 | 693 | 175 |
| 5 | 1044 | 370 |

#### Haiku 5.5 / 关闭思考 / 系统与历史

`haiku-disabled-conversation`

产生思考的请求：0/5。

| 计时点 | P50 秒 | P95 秒 |
|---|---:|---:|
| 响应头 | 0.773 | 1.204 |
| 首个 SSE | 0.778 | 1.205 |
| 首个文本 | 0.781 | 1.216 |
| SSE 后等待 | 0.001 | 0.011 |
| 完整结束 | 3.983 | 4.276 |

| 轮次 | 首字秒 | 总耗时秒 |
|---:|---:|---:|
| 1 | 1.216 | 4.276 |
| 2 | 0.755 | 3.983 |
| 3 | 0.781 | 3.603 |
| 4 | 0.759 | 3.354 |
| 5 | 0.942 | 4.184 |

| 轮次 | 总输入 | 读取 | 写入 |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 2013 |
| 2 | 2867 | 2013 | 850 |
| 3 | 3516 | 2863 | 649 |
| 4 | 4151 | 3512 | 635 |
| 5 | 4754 | 4147 | 603 |

| 轮次 | 输出 | 思考 |
|---:|---:|---:|
| 1 | 798 | 0 |
| 2 | 589 | 0 |
| 3 | 564 | 0 |
| 4 | 538 | 0 |
| 5 | 644 | 0 |

### 边界与来源

这是一次固定资料问答实验，不是客户生产负载。没有答案质量评分、并发压测或其他 effort 档位。关闭 thinking 后的回答更短或推理步骤更少也可能影响结果，尚未证明质量等价。

[Requests and responses](../evidence/requests.json) · [Summary](../evidence/summary.json) · [Provenance and hashes](../evidence/provenance.json)

[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) · [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [LiteLLM v1.106.2 source](https://github.com/BerriAI/litellm/blob/v1.106.2/litellm/llms/anthropic/chat/transformation.py)
