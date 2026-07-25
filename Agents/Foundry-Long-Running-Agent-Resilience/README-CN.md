# Microsoft Foundry 长任务 Agent：恢复过程究竟长什么样

[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#3-实测效果)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#3-实测效果)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#22-两种-protocol两套不同的证据)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

一个跑二十分钟的 Agent，随时可能丢掉自己的容器。这篇文章记录八次实测运行中真实发生的事：恢复花了多久、哪些信号能证明任务还活着，以及哪些"下意识反应"反而把事情搞砸。

> **这篇文章是什么。** 一次 private preview 评估中的实测行为与恢复经验。
> **不是什么。** 这里**不包含 preview SDK 源码、实现代码、部署配方、API schema，也不包含原始 telemetry**——因为长任务能力当时仍处于 private preview。文中数字是那次评估的观测值，不是服务级承诺，也不代表所有区域、模型和拓扑都是同样表现。

> **Author:** 魏新宇 (Xinyu Wei)

[English](README.md) | 中文 | [Hosted agents 概览](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent 快速入门](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## Executive Summary

| 问题 | 实测答案 |
|---|---|
| 容器崩溃后任务还在吗？ | 在。容器在 phase 1 死掉，任务照样跑完了 **phase 2-18**。 |
| 恢复用了多久？ | 从崩溃到重启后审批决定被接收，用了 **56 秒**。 |
| 客户端丢事件了吗？ | 没有。sequence 从 **1 一路到 12,248**，既无缺口也无重放。 |
| 能用 sequence 编号判断任务没断吗？ | **不能。** 有一个 runtime 在重连后把流计数器重新计了。 |
| Deployment 是 active 就说明有韧性吗？ | 不说明。那只能证明控制面接受了一个版本。 |
| 遇到 HTTP 424 该怎么办？ | 对同一个 response 继续轮询。那次 workflow 在连续 **29** 个 424 之后正常完成。 |
| 终态读取返回 403 该怎么办？ | 刷新 observer 认证再读一次。任务其实早就跑完了。 |

**如果只记一句话：** 平台把任务保住了，客户端要做的只是接回同一个逻辑任务，并且看对信号。

---

## 1. 背景：长任务 Agent 的失败方式不一样

一次普通对话调用，要么返回，要么抛错。而一个跑二十分钟的 Agent 多了第三种结局：**进程没了，但任务本身仍然有效。**

这段窗口期里会发生三件事：

1. 容器可能被重启、重新部署或回收。
2. 客户端的流断了，而且没有收到终态事件。
3. 用户可能中途改主意。

这三件事都不是"重试请求"能解决的。重试会开启一个**新**任务，同时把原本还活着的工作丢掉。这是这个领域代价最高的一个错误，也是本文后面通篇讲**重新接回**而不是讲重试的原因。

### 平台公开行为

Microsoft Foundry Hosted Agents 把应用代码运行在微软托管、按 session 隔离的计算环境中。与恢复直接相关的公开行为：

| 概念 | 对恢复意味着什么 |
|---|---|
| Session | 计算与状态的边界。持久化的 `$HOME` 和文件能跨越空闲期存活。 |
| Conversation | 持久化的消息与工具调用历史，主要由 Responses protocol 使用。 |
| 空闲超时 | 长时间无请求时计算会被回收，session 恢复时再还原。 |
| Agent identity | Agent 代码运行时使用的独立 Microsoft Entra 身份。 |

来源：[Foundry Agent Service 中的 Hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)。

这些是平台属性。它们**并不能**证明某个具体 workload 一定能正确恢复——而这恰恰是下面那些实测数据要回答的问题。

---

## 2. 方法：到底跑了什么

![四层责任边界：Foundry 公开托管、preview 长任务能力、workload 证据、观察者证据](images/resilience-architecture-cn.png)

### 2.1 八个场景

![八个场景归为四类证据模式](images/scenario-coverage-cn.png)

| # | Runtime | Protocol | 模式 | 使用的中断方式 |
|---|---|---|---|---|
| 1 | Python | Invocations | Research 持久性 | 运行中容器崩溃 |
| 2 | Python | Responses | Research 持久性 | 运行中容器崩溃 |
| 3 | .NET | Invocations | Research 持久性 | 运行中容器崩溃 |
| 4 | .NET | Responses | Research 持久性 | 运行中容器崩溃 |
| 5 | Python | Invocations | 人工审批 | 审批挂起时崩溃 |
| 6 | Python | Responses | 人工审批 | 审批挂起时崩溃 |
| 7 | Python | Responses | 持久化 workflow | 主机替换 |
| 8 | Python | Responses | 运行中打断 | 主动打断，不是故障 |

### 2.2 两种 Protocol，两套不同的证据

| 关注点 | Responses | Invocations |
|---|---|---|
| 客户端契约 | OpenAI 兼容的 responses 行为 | 应用自定义的请求与结果 schema |
| 历史 | 平台托管的 conversation | 应用自己管理的 session 与 task 状态 |
| 长任务入口 | Background stored response | 自定义 durable task |
| 观察到的恢复信号 | 生命周期事件重放，或 output index 继续 | 显式的恢复事件 |
| 观察到的终态信号 | Response 完成 | done 事件加上任务挂起原因 |

两种 protocol 发出的事件并不相同。任何把某一种 protocol 的事件名写死的恢复判断，在另一种上都会误报失败。

### 2.3 验收标准

只有当中断之后**完整的既定计划走到终态结果**，才算通过。部分恢复、恢复后卡住、或者重新跑一遍产出相似文本，都不算。

---

## 3. 实测效果

### 3.1 运行中崩溃：任务并没有停

![实测恢复时间线：崩溃前 599 个事件，重连后 11,649 个事件](images/recovery-timeline-cn.png)

Python Invocations research 运行：

| 阶段 | 实测值 |
|---|---|
| 崩溃前 | 15 秒内 599 个事件，完成 phase 1，sequence 1-599 |
| 崩溃 | 流中断，客户端看到连接断开 |
| 重新接回 | 收到恢复事件，sequence 从 **600** 继续 |
| 重连之后 | 1,237 秒内 11,649 个事件，phase 2-18 |
| 终态 | 状态为已完成，任务因运行结束而挂起 |
| 总计 | **1,301 秒（21.7 分钟）**，sequence 1 到 12,248 |

重连后的流里带着 **192 个 status 事件和 17 个 phase 事件**。任务是真的在继续，而不是重新开始。

### 3.2 同样的崩溃，换一种 Protocol

Python Responses research 运行，共 11,584 条记录：

| 阶段 | 实测值 |
|---|---|
| 崩溃前 | 577 个事件，13 秒，output index 0，570 个文本增量 |
| 崩溃 | 崩溃流上报告了一个 failed response |
| 重新接回 | 观察到生命周期重放，sequence 从 578 继续 |
| 重连之后 | 11,005 个事件，1,140 秒，output index 1-17，10,918 个文本增量 |
| 终态 | 完成信号在重连后的流上收到 |
| 重连间隔 | **47 秒** |

output index 0 是崩溃前产出的，1-17 是崩溃之后产出的。**没有任何 index 重复，也没有任何 index 缺失**——这是能拿到的最强证据，说明它确实还是同一个逻辑 response。

### 3.3 人在思考的时候崩溃了

这是最容易被低估的一种情况。Graph 停在审批点上，**当时根本没有任何东西在执行**。

| 时间（UTC） | 事件 |
|---|---|
| 12:22:54 | 任务启动 |
| 12:23:01 | 调用航班与酒店查询工具 |
| 12:23:07 | 针对三晚东京行程请求审批 |
| 12:24:27 | 注入容器崩溃 |
| 12:25:23 | 重启后发送审批决定 |
| 12:25:25 | Agent 恢复，给出**与崩溃前完全相同的航班与酒店选择** |
| 12:25:30 | 终态结果：确认号 `TRIP-182336` |

从崩溃到重启后审批决定被接收，**56 秒**；再过 7 秒拿到终态确认。待审批状态、工具调用结果、以及当初提供给用户的那几个选项，全都在一个已经不存在的进程之后活了下来。

同一模式在 Responses protocol 上的第二次运行，也拿到了自己的终态确认号 `TRIP-749637`。

> 这些是确定性的示例工具。确认号证明的是持久化 graph 状态和"决定只生效一次"，而不是真实的航班或酒店预订。

### 3.4 主机替换：29 次"失败"其实都不是失败

持久化 workflow 那次运行，在主机被替换期间**连续 29 次**收到 `HTTP 424 Failed Dependency`。客户端没有重新提交，而是继续轮询同一个 response，最终所有阶段完整产出。

最终持久化输出，原样转录：

```text
[French]
Le rapide renard brun saute par-dessus le chien paresseux.
[Spanish]
El rápido zorro marrón salta por encima del perro perezoso.
[Original English]
The quick brown fox jumps over the lazy dog.
[French]
Le rapide renard brun saute par-dessus le chien paresseux.
[Spanish]
El rápido zorro marrón salta por encima del perro perezoso.
[Round-trip English]
The quick brown fox jumps over the lazy dog.
```

如果客户端把第一个 424 当作终态错误，就会亲手丢掉一次马上就要成功的运行。如果在第十次放弃，结果也一样。

### 3.5 Steering：主动打断

不是所有中断都是故障。第一轮还在生成时，第二轮请求就到了：

| 步骤 | 观察到的现象 |
|---|---|
| 第一轮 | 计数任务，仍在运行 |
| 运行中发出第二轮 | 新问题，状态为 `queued` |
| 第一轮结局 | 协作式结束，标记为已完成 |
| 第二轮结局 | 7 次轮询处于 `in_progress`，随后 `completed` |
| 答案 | 新问题得到了正确回答 |

替换输入是被排队而不是被拒绝，旧的一轮在安全边界上收尾，而不是在生成到一半时被强杀。

---

## 4. 重连时该相信什么

![四次运行的连续性证据，只有 output 覆盖度在全部四次中都成立](images/continuity-evidence-cn.png)

这是本文最值得迁移到别处的一条结论。

| 运行 | 崩溃前 | 重连后 | 连续性信号 |
|---|---|---|---|
| Invocations / Python | seq 1-599 | seq 600-12,248 | sequence 续上 |
| Responses / Python | output index 0 | output index 1-17 | index 续上 |
| Invocations / .NET | seq 1-738 | seq 739-12,073 | sequence 续上 |
| Responses / .NET | output index 0 | output index 1-17 | index 续上，但 **sequence 从 5 重新计数** |

四次运行里有三次 sequence 编号是连续的，第四次不是：.NET Responses 的流在重连后**重置了计数器**，但仍然在同一个 response 上交付了 output index 1-17。

**实用规则：** 判断连续性要看 *workload 产出了什么*（output index、phase 编号、持久化状态），而不是看 *传输层怎么给帧编号*。另外，单调递增也不等于没有缺口——`10, 12` 是单调的，但中间少了一个事件。

---

## 5. 故障与恢复手册

![四类中断，各自的错误反应与正确恢复方式](images/recovery-playbook-cn.png)

### 5.1 运行中容器崩溃

| 项 | 内容 |
|---|---|
| 现象 | 流停止，且没有终态事件 |
| 错误反应 | 重新提交任务 |
| 为什么有害 | 原任务其实还活着，于是你有了两个任务，还要为两个付费 |
| 正确恢复 | 用同一个逻辑任务引用和最后已知的游标重新接回 |
| 确认方式 | 收到恢复标记，或同一任务上的 output index 继续推进 |
| 实测结果 | 重连后 phase 2-18 全部完成 |

### 5.2 等待人工审批时崩溃

| 项 | 内容 |
|---|---|
| 现象 | 什么都没在跑，也没有流可以重连 |
| 错误反应 | 从头重建审批请求 |
| 为什么有害 | 你会丢掉工具调用结果，以及当初摆在用户面前的那几个具体选项 |
| 正确恢复 | 重启之后直接发送决定，让持久化 checkpoint 唤醒 graph |
| 确认方式 | 审批之后的路径被执行，并走到终态确认 |
| 实测结果 | 崩溃 56 秒后决定被接收，选择与崩溃前完全一致 |

### 5.3 主机替换返回 HTTP 424

| 项 | 内容 |
|---|---|
| 现象 | 同一个 response 反复返回 `424 Failed Dependency` |
| 错误反应 | 把 424 当成终态错误 |
| 为什么有害 | Response 本身完好，只是它的宿主正在被替换 |
| 正确恢复 | 带退避地重试同一个 response |
| 确认方式 | Response 报告完成，且所有阶段齐全 |
| 实测结果 | 连续 29 个 424 之后正常完成 |

### 5.4 观察者凭据过期

| 项 | 内容 |
|---|---|
| 现象 | 长任务终态读取返回 `403` |
| 错误反应 | 重跑整个任务 |
| 为什么有害 | 任务早就跑完了，你是在为修自己的 token 而重跑业务 |
| 正确恢复 | 刷新 observer 认证，重新执行那次只读查询 |
| 确认方式 | 返回 `200`，状态为已完成 |
| 实测结果 | 换新 token 后读到完成状态，共 18 个 output item |

### 5.5 证据被截断

| 项 | 内容 |
|---|---|
| 现象 | 保存的日志或流在字节上限处停止 |
| 错误反应 | 断定任务停在最后捕获到的那个事件 |
| 为什么有害 | 会把一次成功的运行误判成失败 |
| 正确恢复 | 直接查询持久化状态，或者重新完整捕获流 |
| 确认方式 | 终态来自服务端读取，而不是从日志尾部推断 |

---

## 6. 设计建议

可以迁移到这次 preview 之外的几点：

1. **在能说清楚的边界上做 checkpoint。** "18 个阶段完成了 7 个"是可恢复的，"跑到中间某处"不是。
2. **给任务一个比进程活得更久的身份。** 恢复是去寻址一个逻辑任务，而不是接上一个 socket。
3. **把观察者故障和任务故障分开。** Token 过期是你自己的问题，不是任务的问题。
4. **把托管层返回的 4xx 当作传输状态，而不是业务结论。** 先对照持久化状态确认，再判定失败。
5. **让终态显式化。** 流"结束了"并不等于有结果。
6. **明确审批决定归谁负责。** 被执行两次，比晚一点执行更糟。
7. **区分挂起任务和活跃任务。** 停在审批点的 graph 不消耗资源，可能被回收，这是预期行为而不是故障。

---

## 7. 边界与限制

- 文中数字是**一次评估的观测值**，不是 benchmark、保证或 SLA。
- 长任务能力当时处于 **private preview**，其实现、包、API 和部署配方不在此公开。
- 结果覆盖**八个文档定义的主场景**，可选的 cancel、delete、deny 分支不计入。
- 验证的是恢复行为，不包括业务领域正确性和模型质量。
- 在依据本文做设计之前，请以[官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)核对当前能力。

## 8. 证据来源

文中每个数字都能追溯到那次评估捕获的原始产物：

| 声明 | 来源产物类型 |
|---|---|
| 事件数量、sequence 区间、耗时 | 逐场景捕获的事件流 |
| Phase 与 output index 覆盖度 | 对这些捕获流的分析 |
| 审批时间线与确认号 | 客户端会话日志 |
| 424 重试行为与阶段输出 | Workflow 客户端日志 |
| Steering 排队与终态答案 | Steering 客户端日志 |

原始产物保留在私有边界内，因为其中包含 endpoint、任务标识、环境 metadata 和生成的 payload 文本。

## 相关工作

| Repository | 关系 |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | 更完整的 build、deploy、operate 生命周期 |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted agent 的 tools、memory 与 skills |
| [Foundry-Agent-ModelOps-Governance](../Foundry-Agent-ModelOps-Governance/) | Operational-plane 边界梳理 |

## License

[MIT](LICENSE)
