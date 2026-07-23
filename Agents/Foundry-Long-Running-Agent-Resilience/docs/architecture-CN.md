# 架构与责任边界

## 四层结构

理解这套验证体系的关键，是把四个责任层分开。第一层属于 Microsoft Foundry 当前公开能力；第二层只记录 Private Preview campaign 的可公开观察，不披露其实现。

| 层级 | 责任方 | 可公开核验的职责 | 本 Repo 使用的证据 |
|---|---|---|---|
| Foundry Hosting | Microsoft Foundry | Hosted container 生命周期、独立 Agent identity 与 endpoint、session/conversation 状态、protocol routing | 当前 Microsoft Learn 文档 |
| 长任务能力 | Preview service + workload integration | Campaign 中观察到的 durable task state、可重连事件、recovery entry 与 steering pressure | 作者证明的脱敏 campaign 结果 |
| Workload | Agent application | Checkpoint 含义、approval owner、stage output、安全取消边界与业务完成条件 | Pattern-specific assertion |
| Observer | Validation client | 故障注入、reconnect cursor、终态读取、脱敏与公开边界 | Public validator 与私有证据 commitment |

本 Repo 验证表格后两列，不包含长任务能力的 Private Preview 实现。

## Foundry 公开概念

Hosted Agents 把应用代码运行在 Microsoft 托管、按 session 隔离的计算环境中。公开文档区分以下概念：

- **Session**：计算和状态边界，包括持久化的 `$HOME` 与文件。
- **Conversation**：主要供 Responses protocol 使用的持久化消息与工具调用历史。
- **Responses**：OpenAI-compatible conversation、平台管理的 streaming，以及可选 background execution。
- **Invocations**：任意 request/response contract，由应用自己管理 session 语义、event schema 与 task tracking。
- **Agent identity**：Agent 代码在运行时使用的独立 Microsoft Entra identity。
- **Project managed identity**：平台执行基础设施操作时使用的 project-level identity。

这些公开能力本身不能证明应用在进程故障后能正确恢复；恢复结论必须由 workload 证据支撑。

## Active work 与 suspended work

Long-running 不等于计算一直在运行。

| 工作形态 | 持久化内容 | 唤醒方式 | PASS 标准 |
|---|---|---|---|
| Active research | Phase watermark 与 task/output state | Pending work recovery | 剩余 phase 继续执行，并达到 terminal completion |
| Suspended human approval | Graph checkpoint 与 pending approval | 后续 approval request | Decision 只应用一次，approval 后路径完整结束 |
| Durable workflow | 每个 stage 的 output | Background workflow recovery | 必需 stage output 与最终 round-trip result 存在 |
| Steering | Conversation state 与 queued replacement input | Materially different new turn | 旧 turn 协作结束，新 turn 返回相关的 completed answer |

Suspended approval 可以在没有运行进程的情况下等待很久。连续性来自 durable checkpoint，而不是 process uptime。

## Protocol 责任划分

| 关注点 | Responses | Invocations |
|---|---|---|
| Client contract | OpenAI-compatible `/responses` behavior | 应用定义 request 与 result schema |
| History | 平台管理 conversation history | 应用管理 session/task state |
| 长任务入口 | Background stored response | Custom durable task contract |
| Stream 证据 | 同一 response、output index、terminal response status | 应用 event sequence、recovery marker、terminal task status |
| Reconnect 风险 | 不同 SDK 的 cursor/lifecycle event 可能不同 | 应用必须定义 replay 与 terminal semantics |

因此，本 campaign 使用 protocol-specific evidence，不会要求某个 SDK 的 event 名出现在另一种 protocol 中。

## Campaign 中观察到的运维边界

Private Preview campaign 中曾出现：Agent version 已是 active，但目标环境尚未获得 service-side preview onboarding，因此 durable task operation 仍不可用。产品团队完成 enablement 后，该路径恢复；修复方式不是开启某个无关的 customer-side resource-provider feature。

这是有明确范围的 campaign observation，不是公开自助注册指引。Durable task path 不可用时，应先分别回答四个问题，再考虑修改基础设施：

1. Agent version 是否 active？
2. Protocol endpoint 是否已到达应用？
3. 目标环境是否已启用 durable task/storage capability？
4. Final read 使用的 observer authentication 是否仍有效？

## Trust model（信任模型）

必须把三类结论分开：

1. **Contract validity（契约有效性）**：公开 assertion 满足精确 JSON Schema 与 Python validator。
2. **Artifact integrity（产物完整性）**：Manifest 能发现 committed public artifact 的变化。
3. **Execution provenance（执行来源）**：作者证明这些 assertion 来自私有 authenticated run；每个 scenario 的 commitment 可以与保留的私有 evidence 复核，但公开读者无法独立 replay 这些私有 run。

SHA-256 manifest 能证明第二项，不能单独证明第三项。

## 公开来源

- [Foundry Agent Service 中的 Hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [部署第一个 Hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
