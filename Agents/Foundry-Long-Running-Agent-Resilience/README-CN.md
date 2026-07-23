# Foundry 长任务 Agent 韧性——Private Preview 笔记

> **仅限文档。** 本页记录一次 Microsoft Foundry Private Preview 小范围评估中可以公开的概念与高层经验。这里刻意**不包含 Preview SDK/package 源码、实现代码、API schema、部署配方、可执行 validator、raw telemetry、service endpoint、resource identifier、credential 或客户 workload 数据**。
>
> 以下观察不是生产认证、服务级承诺或公开产品规格，也不表示所有区域、模型、框架、protocol 和拓扑都具有相同行为。公开支持范围请以最新 [Microsoft Foundry 文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)为准。

> **Author:** 魏新宇（Xinyu Wei）

[English](README.md) | 中文 | [Hosted agents 概览](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent 快速入门](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## Executive Summary

判断长任务 Agent 是否可靠，不能只看 deployment 是否 active。真正有价值的问题是：workload 是否保留了正确状态、能否跨中断恢复、能否重连到原逻辑任务，以及最终是否得到正确的 terminal outcome。

一次小范围 Private Preview campaign 评估了八个文档定义的主场景，覆盖：

- Python 与 .NET workload；
- Responses 与 Invocations protocol；
- Active multi-phase research；
- Suspended human approval；
- Durable multi-stage workflow；
- Active-turn steering。

八个主场景都达到了各自文档定义的验收标准。该结论是**作者对私有评估结果的总结**。Raw evidence 与实现均不公开，因此无法仅凭本 Repo 独立 replay。

## 责任边界

![区分 Foundry 公开 Hosting、Private Preview observation、workload proof 与 observer evidence 的四层结构](images/resilience-architecture-cn.png)

| 层级 | 职责 | 公开边界 |
|---|---|---|
| Foundry Hosting | 公开文档描述的 session/conversation state、identity、endpoint 与 lifecycle behavior | 以最新 Microsoft Learn 文档为准 |
| Private Preview 能力 | 小范围 campaign 中观察到的长任务行为 | 实现与私有 interface 不公开 |
| Workload | Checkpoint 含义、approval owner、stage state、安全取消与 terminal business result | 本文只保留高层 proof pattern |
| Observer | 中断、重连、终态读取与 evidence review | 不发布 raw telemetry 或 identifier |

## Active Work 与 Suspended Work

Long-running 不等于计算一直在运行。

| 工作形态 | 持久化状态 | 唤醒方式 | 证据目标 |
|---|---|---|---|
| Active research | Phase watermark 与 intermediate output | Pending work recovery | 剩余 phase 继续执行，并达到 terminal success |
| Suspended approval | Graph checkpoint 与 pending decision | 后续 approval request | Decision 只应用一次，approval 后路径完整结束 |
| Durable workflow | 每个 stage 的 output | Background workflow recovery | 必需 stage 与最终 round-trip result 存在 |
| Steering | Conversation state 与 queued replacement input | Materially different new turn | 旧 turn 协作结束，queued turn 完成 |

进程可以消失，而 durable state 仍然存在。连续性是状态管理属性，不代表原进程一直存活。

## Protocol 责任划分

| 关注点 | Responses | Invocations |
|---|---|---|
| Client contract | OpenAI-compatible Responses behavior | 应用定义 request 与 result schema |
| History | 平台管理 conversation history | 应用管理 session/task state |
| 长任务形态 | Background stored response | Custom task 与 event contract |
| Reconnect 证据 | 同一 response、output continuity、terminal response state | 应用 event continuity、recovery marker、terminal task state |

Protocol-specific evidence 很重要。某个 SDK 可能暴露 lifecycle event，而另一个 client 在相同 cursor 位置并不重放该 event；更强的跨 runtime 判断是：同一逻辑任务是否继续，并达到有效 terminal state。

## 四类 Proof Pattern

![八个私有评估场景分成四类 proof pattern](images/scenario-coverage-cn.png)

### 1. Research Durability

私有评估使用多阶段、model-backed 的 research workload。验收要求包括：中断前产生 checkpoint、重连原逻辑任务、phase/output 覆盖完整，以及得到显式 terminal success。

### 2. Durable Human Approval

Graph 在敏感动作前暂停。有效结果要求 pending approval 跨进程替换保留、human decision 只应用一次，并且 approval 后路径达到 terminal confirmation。

该场景证明 graph-state durability，不代表真实 airline、hotel、payment 或 reservation-system transaction。

### 3. Durable Workflow

Multi-stage translation workflow 保留了各 stage output，并在 temporary host replacement 后得到最终 round-trip result。该 pattern 证明 durable stage state，不复用 Research 的 crash/reconnect assertion set。

### 4. Active-turn Steering

第一轮仍 active 时，提交 materially different follow-up。有效结果要求新 turn 进入 queue、旧 turn 协作结束，并且 replacement input 得到相关的 completed answer。

Steering 属于 control-flow pattern，不等于 crash recovery。

## 证据层级

![从私有执行到可公开文档的证据流水线](images/evidence-pipeline-cn.png)

对于 recovery-oriented scenario，以下层级可以避免误判：

1. Deployment 为 active。
2. Work 已被接受。
3. 观察到 workload checkpoint。
4. 观察到预期中断与 connection loss。
5. 观察到 recovery 或 same-work continuity。
6. 完整文档场景达到 terminal success。

Agent version active 只能证明 control-plane state，不能证明 workload resilience。

## 运维经验

### 区分 Service Onboarding 与客户配置

在这次小范围 campaign 中，Agent version 可以已经 active，但目标环境尚未获得 long-running data path 所需的 service-side Private Preview onboarding，因此该路径仍不可用。产品团队完成 enablement 后问题消失；开启某个无关的 customer-side resource-provider feature 并不是修复方式。

这是有明确范围的 Private Preview observation，不是公开自助注册指引。

### 区分 Observer Authentication 与 Workload State

Workload 已经完成后，final read 仍可能失败。Observer authentication 过期时，应刷新 observer credential，并只重试只读 final query。不要自动把 workload 改判为失败，也不要为了修复 observer 而重跑 workload。

### 不用单一 Event 名推断连续性

不同 runtime 与 client 可能暴露不同的 reconnect event sequence。应同时检查 durable state、logical-work identity、有序 output、reconnect position 与 terminal outcome。

### 把截断 Stream 当作不完整证据

Log 或 stream 在 byte cap 处停止，不表示 workload 也在那里停止。下结论前应查询 durable state，或者重新保存完整 stream。

## 不公开的内容

以下内容继续保留在私有边界：

- Private Preview SDK 与 package 源码；
- 私有 interface 与 API schema；
- 部署与 enablement 配方；
- Raw event stream 与生成的 payload text；
- Endpoint、resource/work/session/response identifier；
- Tenant、subscription、project、machine、identity 与 credential 细节；
- 内部协作记录与产品团队请求。

## 公开来源

- [Foundry Agent Service 中的 Hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [部署第一个 Hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
- [Microsoft Azure Preview Supplemental Terms](https://azure.microsoft.com/en-us/support/legal/preview-supplemental-terms/)

## License

本文档采用 [MIT License](LICENSE)。
