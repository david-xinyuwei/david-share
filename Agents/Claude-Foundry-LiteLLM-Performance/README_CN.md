# Claude 5.5 经 LiteLLM 接入 Microsoft Foundry：参数、提示缓存与性能验证

[![Models](https://img.shields.io/badge/models-Opus%20%C2%B7%20Sonnet%20%C2%B7%20Haiku%205.5-0078D4)](#目的)
[![Measured](https://img.shields.io/badge/measured-2026--10--26%20to%2010--27-0078D4)](#实现效果)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml)

作者：魏新宇 · [English](README.md)

## 目的

**要解决的问题。** Claude 请求经过 LiteLLM 后，参数是否传到 Microsoft Foundry，提示缓存是否真正复用，各配置的等待时间、输出速率和费用是多少？这里提供 Opus 5.5、Sonnet 5.5 和 Haiku 5.5 的实测请求、证据校验和复现步骤。被测部署采用 [Hosted on Azure](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)，模型版本 2、GlobalStandard；公开编码题用于固定测试输入，不代表客户生产负载。

**本轮 ACA 已完成：** 已保存 650/650 次请求，624 份正式答案已评分。下面先看性能，再看正确率。[完整结果](docs/results_CN.md#aca-gateway-snapshot)。

**当前测试方法。** Linux VM 客户端 → Azure Container Apps 上的 LiteLLM → Foundry；客户端、网关和 Foundry 资源均位于 East US 2。客户端使用网关入口密钥，LiteLLM 以自己的托管身份调用 Foundry。通过请求顶层 `cache_control` 开启提示缓存。每个模型同一时间只有 1 个请求，测的是单个请求的表现，不是压力测试。

<img src="images/topology-zh.svg" width="900" alt="当前开启缓存的测试路径：Linux VM 客户端经 East US 2 的 Azure Container Apps 上的 LiteLLM 调用三个 Microsoft Foundry Claude 部署。提示缓存在 Foundry 侧；客户端记录时间和原生 usage。" />

原创测试拓扑图，使用未修改的 [Azure 图标](images/icon-sources.json)。

**职责与范围。** LiteLLM 负责转发，提示缓存在上游模型服务侧；本仓库的脚本负责采集和校验。使用者仍须核对自己的网关版本、路由和工作负载。本测试不证明生产容量、历史故障已修复或相对 AWS 的表现。早期直连及跨区域结果单独保留在[结果页](docs/results_CN.md#historical-evidence)。

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

#### Opus 5.5

**各配置的等待时间。**

| 模型 / thinking.type / output_config.effort | 缓存状态 | TTFT P50 / P95（秒） | E2E P50 / P95（秒） | 有效请求数 |
|---|---|---:|---:|---:|
| Opus 5.5<br>`adaptive` / `low` | 首次写入 | 1.19 / 9.06 | 6.94 / 14.4 | 12 |
| Opus 5.5<br>`adaptive` / `low` | 读取命中 | 1.08 / 14.7 | 7.84 / 20.0 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | 首次写入 | 6.92 / 31.5 | 11.6 / 37.2 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | 读取命中 | 7.15 / 29.3 | 11.3 / 35.3 | 12 |
| Opus 5.5<br>`adaptive` / `high` | 首次写入 | 9.13 / 94.5 | 14.0 / 101 | 12 |
| Opus 5.5<br>`adaptive` / `high` | 读取命中 | 7.53 / 228 | 11.7 / 239 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | 首次写入 | 18.9 / 110 | 24.7 / 117 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | 读取命中 | 19.6 / 380 | 24.5 / 389 | 12 |
| Opus 5.5<br>`adaptive` / `max` | 首次写入 | 232 / 1027 | 247 / 1036 | 11 |
| Opus 5.5<br>`adaptive` / `max` | 读取命中 | 236 / 913 | 249 / 922 | 11 |
| Opus 5.5<br>`adaptive` / `default` | 首次写入 | 7.03 / 65.8 | 12.0 / 72.3 | 11 |
| Opus 5.5<br>`adaptive` / `default` | 读取命中 | 8.02 / 28.5 | 15.0 / 34.3 | 11 |

**同一组请求的输出速率与费用。**

| 模型 / thinking.type / output_config.effort | 缓存状态 | 端到端输出速率 P50（tokens/s，含思考） | 平均费用（美元/请求） | 有效请求数 |
|---|---|---:|---:|---:|
| Opus 5.5<br>`adaptive` / `low` | 首次写入 | 103.53 | $0.158921 | 12 |
| Opus 5.5<br>`adaptive` / `low` | 读取命中 | 103.75 | $0.023222 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | 首次写入 | 108.44 | $0.173419 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | 读取命中 | 111.76 | $0.036952 | 12 |
| Opus 5.5<br>`adaptive` / `high` | 首次写入 | 110.21 | $0.200936 | 12 |
| Opus 5.5<br>`adaptive` / `high` | 读取命中 | 110.93 | $0.097379 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | 首次写入 | 112.87 | $0.248050 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | 读取命中 | 114.35 | $0.183598 | 12 |
| Opus 5.5<br>`adaptive` / `max` | 首次写入 | 123.30 | $1.008633 | 11 |
| Opus 5.5<br>`adaptive` / `max` | 读取命中 | 121.91 | $0.785095 | 11 |
| Opus 5.5<br>`adaptive` / `default` | 首次写入 | 109.83 | $0.186835 | 11 |
| Opus 5.5<br>`adaptive` / `default` | 读取命中 | 109.88 | $0.037639 | 11 |

#### Sonnet 5.5

**各配置的等待时间。**

| 模型 / thinking.type / output_config.effort | 缓存状态 | TTFT P50 / P95（秒） | E2E P50 / P95（秒） | 有效请求数 |
|---|---|---:|---:|---:|
| Sonnet 5.5<br>`adaptive` / `low` | 首次写入 | 0.77 / 0.95 | 4.86 / 9.76 | 12 |
| Sonnet 5.5<br>`adaptive` / `low` | 读取命中 | 0.76 / 1.15 | 4.88 / 9.01 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | 首次写入 | 0.81 / 11.0 | 5.67 / 14.4 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | 读取命中 | 0.87 / 16.3 | 6.15 / 19.1 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | 首次写入 | 6.05 / 137 | 10.6 / 140 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | 读取命中 | 7.44 / 119 | 10.7 / 122 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | 首次写入 | 20.7 / 246 | 24.0 / 254 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | 读取命中 | 16.1 / 341 | 19.4 / 354 | 12 |
| Sonnet 5.5<br>`adaptive` / `max` | 首次写入 | 394 / 616 | 397 / 622 | 9 |
| Sonnet 5.5<br>`adaptive` / `max` | 读取命中 | 364 / 743 | 367 / 751 | 9 |
| Sonnet 5.5<br>`adaptive` / `default` | 首次写入 | 6.86 / 86.8 | 10.8 / 90.2 | 12 |
| Sonnet 5.5<br>`adaptive` / `default` | 读取命中 | 5.78 / 152 | 8.39 / 156 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | 首次写入 | 0.78 / 1.08 | 5.14 / 7.88 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | 读取命中 | 0.76 / 0.91 | 4.51 / 8.22 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | 首次写入 | 0.83 / 1.06 | 5.41 / 9.18 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | 读取命中 | 0.79 / 0.93 | 4.60 / 9.87 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | 首次写入 | 0.81 / 1.09 | 5.56 / 11.6 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | 读取命中 | 0.82 / 1.18 | 7.03 / 13.1 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | 首次写入 | 0.79 / 1.15 | 4.88 / 13.6 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | 读取命中 | 0.78 / 1.07 | 5.46 / 10.2 | 12 |

**同一组请求的输出速率与费用。**

| 模型 / thinking.type / output_config.effort | 缓存状态 | 端到端输出速率 P50（tokens/s，含思考） | 平均费用（美元/请求） | 有效请求数 |
|---|---|---:|---:|---:|
| Sonnet 5.5<br>`adaptive` / `low` | 首次写入 | 130.16 | $0.077371 | 12 |
| Sonnet 5.5<br>`adaptive` / `low` | 读取命中 | 123.18 | $0.008869 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | 首次写入 | 124.97 | $0.078745 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | 读取命中 | 124.24 | $0.010499 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | 首次写入 | 141.38 | $0.106288 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | 读取命中 | 138.87 | $0.034861 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | 首次写入 | 148.80 | $0.152607 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | 读取命中 | 149.31 | $0.109698 | 12 |
| Sonnet 5.5<br>`adaptive` / `max` | 首次写入 | 156.49 | $0.804891 | 9 |
| Sonnet 5.5<br>`adaptive` / `max` | 读取命中 | 158.34 | $0.635133 | 9 |
| Sonnet 5.5<br>`adaptive` / `default` | 首次写入 | 140.69 | $0.100876 | 12 |
| Sonnet 5.5<br>`adaptive` / `default` | 读取命中 | 141.88 | $0.035923 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | 首次写入 | 126.13 | $0.077653 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | 读取命中 | 130.11 | $0.008496 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | 首次写入 | 132.11 | $0.077994 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | 读取命中 | 133.30 | $0.009313 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | 首次写入 | 130.38 | $0.079108 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | 读取命中 | 129.14 | $0.011469 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | 首次写入 | 130.06 | $0.078623 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | 读取命中 | 133.11 | $0.010259 | 12 |

#### Haiku 5.5

**各配置的等待时间。**

| 模型 / thinking.type / output_config.effort | 缓存状态 | TTFT P50 / P95（秒） | E2E P50 / P95（秒） | 有效请求数 |
|---|---|---:|---:|---:|
| Haiku 5.5<br>`adaptive` / `low` | 首次写入 | 3.09 / 20.2 | 4.93 / 22.9 | 12 |
| Haiku 5.5<br>`adaptive` / `low` | 读取命中 | 4.25 / 17.6 | 5.75 / 20.7 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | 首次写入 | 6.92 / 13.8 | 8.30 / 15.3 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | 读取命中 | 6.93 / 14.2 | 8.02 / 16.8 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | 首次写入 | 9.07 / 38.5 | 10.8 / 40.3 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | 读取命中 | 12.1 / 29.6 | 14.1 / 34.0 | 12 |
| Haiku 5.5<br>`adaptive` / `xhigh` | 首次写入 | 61.3 / 460 | 63.2 / 463 | 11 |
| Haiku 5.5<br>`adaptive` / `xhigh` | 读取命中 | 53.4 / 235 | 57.0 / 237 | 11 |
| Haiku 5.5<br>`adaptive` / `max` | 首次写入 | 204 / 399 | 206 / 406 | 8 |
| Haiku 5.5<br>`adaptive` / `max` | 读取命中 | 260 / 377 | 262 / 384 | 8 |
| Haiku 5.5<br>`adaptive` / `default` | 首次写入 | 5.49 / 15.5 | 7.40 / 18.4 | 12 |
| Haiku 5.5<br>`adaptive` / `default` | 读取命中 | 6.22 / 11.6 | 8.07 / 14.2 | 12 |
| Haiku 5.5<br>`disabled` / `low` | 首次写入 | 0.48 / 0.83 | 2.29 / 3.37 | 12 |
| Haiku 5.5<br>`disabled` / `low` | 读取命中 | 0.56 / 0.74 | 2.36 / 3.51 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | 首次写入 | 0.54 / 0.73 | 2.42 / 3.47 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | 读取命中 | 0.50 / 0.60 | 2.64 / 4.31 | 12 |
| Haiku 5.5<br>`disabled` / `high` | 首次写入 | 0.49 / 0.72 | 2.67 / 4.51 | 12 |
| Haiku 5.5<br>`disabled` / `high` | 读取命中 | 0.49 / 0.69 | 2.40 / 3.56 | 12 |
| Haiku 5.5<br>`disabled` / `default` | 首次写入 | 0.49 / 0.79 | 2.66 / 3.16 | 12 |
| Haiku 5.5<br>`disabled` / `default` | 读取命中 | 0.45 / 0.59 | 2.41 / 4.38 | 12 |

**同一组请求的输出速率与费用。**

| 模型 / thinking.type / output_config.effort | 缓存状态 | 端到端输出速率 P50（tokens/s，含思考） | 平均费用（美元/请求） | 有效请求数 |
|---|---|---:|---:|---:|
| Haiku 5.5<br>`adaptive` / `low` | 首次写入 | 214.53 | $0.004254 | 12 |
| Haiku 5.5<br>`adaptive` / `low` | 读取命中 | 211.44 | $0.001009 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | 首次写入 | 218.61 | $0.004638 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | 读取命中 | 221.27 | $0.001248 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | 首次写入 | 234.38 | $0.005884 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | 读取命中 | 230.84 | $0.002356 | 12 |
| Haiku 5.5<br>`adaptive` / `xhigh` | 首次写入 | 259.47 | $0.019081 | 11 |
| Haiku 5.5<br>`adaptive` / `xhigh` | 读取命中 | 258.09 | $0.010969 | 11 |
| Haiku 5.5<br>`adaptive` / `max` | 首次写入 | 269.25 | $0.037720 | 8 |
| Haiku 5.5<br>`adaptive` / `max` | 读取命中 | 265.15 | $0.032892 | 8 |
| Haiku 5.5<br>`adaptive` / `default` | 首次写入 | 218.12 | $0.004464 | 12 |
| Haiku 5.5<br>`adaptive` / `default` | 读取命中 | 222.91 | $0.001171 | 12 |
| Haiku 5.5<br>`disabled` / `low` | 首次写入 | 177.01 | $0.003747 | 12 |
| Haiku 5.5<br>`disabled` / `low` | 读取命中 | 183.87 | $0.000406 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | 首次写入 | 172.51 | $0.003759 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | 读取命中 | 175.95 | $0.000443 | 12 |
| Haiku 5.5<br>`disabled` / `high` | 首次写入 | 181.72 | $0.003790 | 12 |
| Haiku 5.5<br>`disabled` / `high` | 读取命中 | 172.20 | $0.000428 | 12 |
| Haiku 5.5<br>`disabled` / `default` | 首次写入 | 174.06 | $0.003728 | 12 |
| Haiku 5.5<br>`disabled` / `default` | 读取命中 | 201.46 | $0.000475 | 12 |

### 完成情况与缓存证据

| 模型 | 已保存／计划请求数（含预热） | 正常结束的请求数 | 截断请求数 | 完整正式配对数（组） | 缓存命中配对数（组） |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 | 150/150 | 149 | 1 | 71 | 70 |
| Sonnet 5.5 | 250/250 | 244 | 6 | 117 | 117 |
| Haiku 5.5 | 250/250 | 243 | 7 | 116 | 115 |

**缓存证据。** 304 组正式配对完整结束，其中 302 组有原生缓存命中。另 2 组跨越停机／恢复间隔，过期后重新写入缓存；它们仍计入请求数、费用和正确率，但不进入缓存命中性能统计。命中配对至少读回前次缓存写入的 100.0%，复用同一响应 message ID 的配对为 0。这证明对应缓存读取，不证明普遍提速。响应报告 `inference_geo: global` 和 East US 2 区域头，不代表固定区域推理承诺。

**费用与边界。** 整轮按记录采用的[标价](coding-matrix/pricing.py)计费共 $76.17，包含预热、缓存写入／读取、输出和截断回答；不含基础设施费用，也不是账单。配对指标排除预热、不完整配对及非命中配对，但不会缩小正确率分母。完整分布与计数保存在[统计结果](evidence/gateway-cache-20261026/interim-facts.json)。

[查看全部 26 格及配对观测](docs/results_CN.md#aca-gateway-snapshot)。

### 参数证据能证明什么

**HTTP 成功不等于任务完成。** 记录到 650 次物理尝试，状态分布为 HTTP 200: 650；重试 0 次。这里包含预热和所有已记录的重试；上面的完成表仍保留截断回答。这是限速后的小规模运行，不是容量或可靠性保证。

| 证据层 | 已有证据 | 不能据此证明什么 |
|---|---|---|
| 客户端请求参数 | [请求记录](evidence/gateway-cache-20261026/responses_opus.jsonl)中的 `request_params`、`request_sha256`，记录在已说明的模型别名转换之前 | 不是网关出站请求的抓包 |
| 上游返回的行为 | [原生 usage 和终态](evidence/gateway-cache-20261026/interim-facts.json)包含缓存读写、思考 token、完整结束和截断 | 不能证明所有被接受的参数都生效，也不能证明 effort 与 token 数严格单调 |
| 网关出站参数 | [2026-10-24 的独立审计](docs/results_CN.md#网关测试)对齐了该批次客户端请求与 provider trace | 当前批次未保留逐请求出站审计，不能拿旧批次补齐 |

| thinking.type | 正式请求数 | 有思考 token 字段／请求数 | 思考 token 大于零的请求数 |
|---|---:|---:|---:|
| `adaptive` | 432 | 432/432 | 353 |
| `between_tools` | 96 | 96/96 | 0 |
| `disabled` | 96 | 96/96 | 0 |

这些是 usage 观察，不是模型排名。本轮没有工具循环，因此 `between_tools` 的零思考 token 不能验证工具调用之间的行为。某条 adaptive 请求为零，也不能单凭这一点判定参数被丢弃。旧直连路径的接受／拒绝探测仍属历史证据，不是当前网关支持矩阵。

### 配置建议与验收观察

| 要检查的设置 | 可复现的配置 | 验收观察与边界 |
|---|---|---|
| 网关透传 | 从 [config.yaml](deploy/config.yaml) 开始：`drop_params: false`，网关与路由重试为零 | 采集同一 call ID 的 [provider trace](deploy/trace_hook.py)。配置文本不等于已透传；矩阵客户端另有 429 重试策略 |
| 提示缓存 | 本矩阵使用顶层 `cache_control`，`type: ephemeral`、`ttl: 1h` | 看原生写入和读取 token 数。本轮未比较不同 TTL 或关闭缓存；生产 TTL 须结合真实会话间隔和写入成本选择 |
| 思考模式与档位 | 使用表中明确的配置，`default` 保留为不传字段 | 对比同条件性能和代码测试结果；这组公开题不能选出生产最优档位 |
| 输出上限与流式响应 | 复现配置为 `max_tokens: 128000`、`stream: true` | 必须检查流终止及 `stop_reason`；该上限仍发生截断，不能把 HTTP 200 或首个事件当成回答完成 |

### 性能之后：代码正确率

**方法。** 对同一批 624 份正式答案评分，只排除预热。使用官方 SWE-bench 5.0.2，固定提交 `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`；由官方 `extract_diff` 提取补丁，没有替模型修答案，也没有新增模型调用。每个配置／重复次数使用独立 run ID；所选 12 道金标准全部通过。[冻结输入、官方报告与验算](evidence/gateway-score-20261027/verification.json)。

合计 245/624 份解决问题（39.26%）；另有 257 份补丁应用失败、108 份测试未通过、14 份截断空回答，均保留在分母中。不同模型的模式／档位组合数量不同，不能当成公平总榜；同条件每格均为 24 份答案。这只是 12 题子集，不是完整 SWE-bench Lite 成绩。

| 模型 | thinking.type | output_config.effort | 已解决／正式答案数 | 解决率（%） |
|---|---|---|---:|---:|
| Opus 5.5 | `adaptive` | `low` | 9/24 | 37.50 |
| Opus 5.5 | `adaptive` | `medium` | 19/24 | 79.17 |
| Opus 5.5 | `adaptive` | `high` | 19/24 | 79.17 |
| Opus 5.5 | `adaptive` | `xhigh` | 21/24 | 87.50 |
| Opus 5.5 | `adaptive` | `max` | 22/24 | 91.67 |
| Opus 5.5 | `adaptive` | `default` | 14/24 | 58.33 |
| Sonnet 5.5 | `adaptive` | `low` | 6/24 | 25.00 |
| Sonnet 5.5 | `adaptive` | `medium` | 5/24 | 20.83 |
| Sonnet 5.5 | `adaptive` | `high` | 8/24 | 33.33 |
| Sonnet 5.5 | `adaptive` | `xhigh` | 18/24 | 75.00 |
| Sonnet 5.5 | `adaptive` | `max` | 18/24 | 75.00 |
| Sonnet 5.5 | `adaptive` | `default` | 9/24 | 37.50 |
| Sonnet 5.5 | `between_tools` | `low` | 4/24 | 16.67 |
| Sonnet 5.5 | `between_tools` | `medium` | 5/24 | 20.83 |
| Sonnet 5.5 | `between_tools` | `high` | 7/24 | 29.17 |
| Sonnet 5.5 | `between_tools` | `default` | 7/24 | 29.17 |
| Haiku 5.5 | `adaptive` | `low` | 2/24 | 8.33 |
| Haiku 5.5 | `adaptive` | `medium` | 5/24 | 20.83 |
| Haiku 5.5 | `adaptive` | `high` | 8/24 | 33.33 |
| Haiku 5.5 | `adaptive` | `xhigh` | 12/24 | 50.00 |
| Haiku 5.5 | `adaptive` | `max` | 14/24 | 58.33 |
| Haiku 5.5 | `adaptive` | `default` | 4/24 | 16.67 |
| Haiku 5.5 | `disabled` | `low` | 3/24 | 12.50 |
| Haiku 5.5 | `disabled` | `medium` | 3/24 | 12.50 |
| Haiku 5.5 | `disabled` | `high` | 1/24 | 4.17 |
| Haiku 5.5 | `disabled` | `default` | 2/24 | 8.33 |

**保留疑义。** 6 条官方 `no_tests_collected` 模糊标记仍保留为未解决。对应日志先收集了 92 项顶层测试，包含嵌套的零收集输出，并出现 `NameError: cached_eval`；没有暗中删除或改判。[六条来源复核](evidence/gateway-score-20261027/ambiguous-review.json)。[环境清单](evidence/gateway-score-20261027/environment.json)是在评分后采集，不冒充运行时遥测。

**证据与复算。** [统计结果](evidence/gateway-cache-20261026/interim-facts.json)、[导出哈希与脱敏范围](evidence/gateway-cache-20261026/_export_manifest.json)、[Opus 记录](evidence/gateway-cache-20261026/responses_opus.jsonl)、[Sonnet 记录](evidence/gateway-cache-20261026/responses_sonnet.jsonl)、[Haiku 记录](evidence/gateway-cache-20261026/responses_haiku.jsonl)。指标投影省略提示与回答正文、思考签名、私有端点和其他响应头，不能用于代码正确率评分。复算命令见[测试页](docs/testing_CN.md#aca-snapshot-replay)。

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
