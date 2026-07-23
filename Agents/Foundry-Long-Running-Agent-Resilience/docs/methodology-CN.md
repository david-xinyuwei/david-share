# 方法论

## 目标

这套方法只回答一个问题：长时间运行的 Hosted workload 丢失当前进程或连接后，能否从持久化状态恢复同一个逻辑任务，并得到有效的最终结果？

## Recovery pattern 验收顺序

以下顺序适用于 Research durability 与 Graph human approval。Durable workflow 与 steering 使用后文定义的不同 proof contract。

1. 启动经过身份验证的 Hosted workload。
2. 观察 workload 代码产生的真实 checkpoint。
3. 在任务仍在运行时注入进程故障。
4. 观察客户端连接中断或 Host 暂时不可用。
5. 使用原逻辑任务引用和最新 cursor 重连。
6. 观察协议 recovery marker，或同一任务的输出连续性。
7. 要求完整 workload plan 和成功的 terminal state。
8. 私下保存原始证据，再删除身份字段，生成可公开 attestation。

## 为什么 active 不够

Deployment 为 active 只能证明 control plane 接受并启动了 Agent version。它不能证明 workload 创建了 durable state、跨故障恢复、无缺口 replay stream、恢复 human approval，或最终完成。

## 证据层级

| 层级 | 证据 | 能证明什么 |
|---|---|---|
| 1 | Deployment 为 active | Agent version 可以 provision。 |
| 2 | Request accepted | Runtime 接受了任务。 |
| 3 | 观察到 checkpoint | Workload state 已跨过持久化边界。 |
| 4 | 观察到 failure 和 reconnect | 客户端与 Host 经历了预期中断。 |
| 5 | Recovery marker 或同任务连续性 | 持久化任务恢复了，而不是另起一个替代任务。 |
| 6 | 完整计划 + terminal success | 恢复后的 workload 完成了文档定义的主场景。 |

本 Repo 只有达到第 6 层才计为 scenario PASS。

## Pattern-specific 验收

| Pattern | 必须具备的证据 |
|---|---|
| Research | 故障前 checkpoint、connection loss、重连后原逻辑任务、18 个 phase/item、显式 terminal success |
| Graph HITL | Durable pending approval、process replacement、只恢复一次的 decision、approval 后 confirmation 与 terminal success |
| Durable workflow | 所有必需 stage 的 persisted output 与 completed round-trip result |
| Steering | Materially different queued input、旧 turn 协作结束、新 turn 返回相关 completed answer |

Workflow 与 steering PASS 不表示这两个场景执行了 Research 的 crash/reconnect 链路。

## Runtime 差异

Responses 与 Invocations 的证据表面不同。Invocations 可以发出专用 `recovered` event 和任务终止原因；Responses 可能发出 lifecycle reset，也可能表现为更强的可观察不变量：同一个 stored response 从第一个未 checkpoint 的 output index 继续，并最终进入 `completed`。

因此 validator 同时接受 protocol recovery marker 和 same-response output continuity。它不会把某个 SDK 的 event 顺序强套到另一个 runtime。

## Stream continuity 诊断

Public event summarizer 保留有序 phase 与 output-index observation，并分别报告 sequence monotonicity、strict increase、duplicate count 与 gap。Monotonic sequence 仍可能有 gap，因此绝不能把 `monotonic=true` 解读成完整 replay。Terminal completion 还必须带显式 `completed` status。

## Provenance 与 integrity

每个公开 record 都是作者证明的脱敏结果，并包含由保留的私有 source artifact 生成的 commitment。该 commitment 可支持后续私有 drift check，但公开读者无法据此认证或 replay 私有 execution。

Public manifest 负责另一件事：发现 committed 脱敏 record 与 generated matrix 的变化。Contract validity、artifact integrity 与 execution provenance 是三类不同声明。
