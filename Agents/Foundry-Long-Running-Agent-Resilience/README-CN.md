# Microsoft Foundry 长任务 Agent：进程死了之后，任务怎么活下来

[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#3-评估方法到底跑了什么)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#4-实测结果)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#23-三种集成层级)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

一个需要跑二十二分钟的 Research 任务，刚跑到第 15 秒、刚完成 18 个阶段里的第 1 个，执行它的进程就被销毁了。没有任何人重新提交。二十一分钟后，同一个任务报告完成——18 个阶段全部产出，12,248 条事件，没有缺口，也没有重复阶段。

其中 95% 的工作，是由一个已经不存在的进程完成的。

这篇文章讲清楚三件事：它为什么能成立、什么信号能证明它、以及哪些看起来非常合理的下意识反应反而会毁掉它。

> **这是什么。** 一次 private preview 评估的实测行为，针对 Microsoft Foundry Hosted Agent 上的长任务执行能力。
> **不是什么。** 这里**不包含 preview SDK 源码、实现代码、部署配方、API schema，也不包含原始 telemetry**——当时该能力仍处于 private preview。文中每个数字都是那次评估的观测值，不是服务级承诺。

> **Author:** 魏新宇 (Xinyu Wei)

[English](README.md) | 中文 | [Hosted agents 概览](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent 快速入门](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## 摘要

长任务 Agent 的失败方式和短调用不一样：**进程没了，但任务本身仍然有效。** 客户端如果把这种情况当成错误、直接重新提交，等于亲手放弃了还活着的任务，为两次运行付费，还可能把同一个外部动作提交两遍。

本次评估的能力，把**逻辑任务**和**执行它的进程**拆开：任务拥有持久身份，输入和进度不随进程消失，替代计算资源从最后一个 checkpoint 重新进入。八个场景覆盖两种语言、两种 protocol、四类中断，全部在被打断之后走到了各自既定的终态。

| 实测项 | 数值 | 意义 |
|---|---|---|
| 进程销毁之后完成的工作占比 | 1,301 秒中的 **95%**，12,248 条事件中的 95% | 进程被销毁不等于任务丢失 |
| 从运行实例丢失到审批决定被接收 | **56 秒**，且原有选项保持不变 | 待决策的人工审批能比持有它的进程活得更久 |
| 正常完成前连续收到的 `HTTP 424` | **29 次** | 重试上限设成 10 次，就会丢掉一次健康的运行 |
| 走到既定终态的场景数 | **8 / 8**，每个场景一次被接受的运行 | 属于能力验证，不是可靠性 benchmark |
| 传输层 sequence 能证明连续性的运行数 | **3 / 4** | 有一个 runtime 重置了计数器；workload output 四次全部成立 |

**这些证据还不能说明什么：** 生产可用性、SLA、负载与并发下的表现、多区域恢复、成本，以及业务正确性。每个场景只跑了一次。它足以支撑立项做受控评估，但不足以作为生产放行依据。

---

## 1. 背景：长任务的第三种结局

短调用只有两种结局，要么返回，要么抛错。跑二十分钟的 Agent 多了第三种：进程消失了，任务却仍然有效。

这个窗口期里有三件事可能发生。运行实例可能停止——崩溃、重新部署、主机替换，或者某个生命周期动作。客户端的流可能中断，而且始终没收到终态事件。用户也可能跑到一半改主意。

这三件事都不是“重试一次请求”能解决的。重试会开启一个**新**任务，同时丢下那个还活着的旧任务。于是你有了两个任务，要为两个付费，第一个已经提交过的外部动作还可能再来一遍。这是这个领域代价最高的一个下意识反应，也是本文后面通篇讲**重新接回**而不是讲重试的原因。

### 这里说的“运行实例”是什么

Hosted Agent 是客户自己的 Agent 代码，以 container image 的形式交付。Foundry 把它跑在按 session 隔离的 VM 沙箱里，并负责它的生命周期。本文所说的**运行实例**，指的就是当时正在运行的那份代码。

它不是需要客户自己运维的 Docker 容器。实例丢失，带走的是进程、内存和已有连接；它不会删掉 Hosted Agent 定义，不会删掉 session，也不会删掉任何记录在进程之外的任务——这个区别，正是整件事成立的前提。

### 平台本身已经提供了什么

公开平台提供的是托管基线：按 session 隔离、跨空闲回收仍然保留的 `$HOME` 和 `/files`、持久化的对话历史、独立的 Microsoft Entra 身份，以及托管的生命周期与可观测性（[来源](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)）。

但这些文档回答不了一个问题：**你自己的 workload，在活跃执行被打断之后能否正确恢复。** 空闲状态还原和活跃任务恢复，是两个不同的命题。本次评估针对的是后者。

| 层次 | 公开文档（2026 年 7 月 21 日） | 本次实测 | 结论边界 |
|---|---|---|---|
| Session 状态 | 空闲计算恢复时还原 `$HOME` 与 `/files` | 活跃任务在注入运行实例丢失后继续 | 空闲还原与实测一致，但不能代替活跃任务恢复的证据 |
| Responses | 平台托管对话历史、streaming lifecycle 和后台轮询 | 同一 response 跨恢复交付 output index 0-17 | 证明的是这一次 response，不是所有 workload 的 SLA |
| Invocations | 应用自行负责 payload、session 语义、task tracking 与轮询 | 观察到显式恢复事件和 phase 1-18 | 应用仍须自己保证 checkpoint 和外部副作用正确 |

---

## 2. 原理：寻址任务，而不是抢救进程

<div align="center"><img src="images/resilience-architecture-cn.png" width="820" alt="六步模型：逻辑任务如何跨越 Hosted Agent 运行实例丢失"></div>

整套机制只建立在一个想法上：**给任务一个比进程活得更久的身份，然后重新进入这个任务，而不是去抢救那个进程。**

落到执行上是七步。客户端启动一个逻辑任务，并保留它的稳定引用。执行开始之前，长任务层先把任务身份、输入，以及后续重新定位所需的租约 metadata 持久化下来。Agent 运行过程中，不断记录有业务含义的进度——phase 编号、watermark、审批状态，或者一个指向外部状态的引用。接着运行实例丢失：进程、内存、socket 全都消失，但那条持久化记录还在。Foundry 提供替代计算资源，同一个逻辑任务带着恢复上下文被重新调用，应用加载自己的 checkpoint 并从一个明确的边界继续，最后客户端重新接回、确认连续性。

把那次 18 阶段的实测运行套进这七步，顺序就变得很具体：第一到第三步覆盖 phase 1，第四步销毁进程，第五、六步跑完 phase 2 到 18，客户端在第七步才重新接回。注意这个**时间点**——任务的恢复，与有没有人在旁边看着无关。重新接回恢复的是观察，不是执行。正因为如此，客户端断流才只是一次断流，而不是一次事故。

### 2.1 四层责任必须分开

分清楚这四层，是设计工作的大头，因为它决定了出问题时你有资格得出什么结论。

| 层次 | 负责什么 | 必须保持有效 | 不能单独证明什么 |
|---|---|---|---|
| Foundry Hosted Agent 平台 | 运行沙箱、endpoint、身份、session 与对话状态、生命周期 | 能够提供替代计算资源，并继续寻址同一 session | 业务进度已经被正确 checkpoint |
| 长任务执行层 | 稳定任务身份、持久化输入、恢复入口、task 与 stream 状态 | 逻辑任务记录跨进程存在 | 外部业务动作可以安全重复 |
| Agent framework 或业务应用 | 有业务含义的 checkpoint、workflow 阶段、审批状态、终态结果 | 足以安全恢复的业务进度 | 客户端一定会正确重连 |
| 客户端与运维 | 稳定任务引用、重连游标、有界轮询、认证刷新 | 断线后仍能观察到同一个逻辑任务 | 传输层报错等于 workload 失败 |

一句话原则：**运行实例状态、业务任务状态、观察者状态，是三个不同的故障域。** 其中一层出问题，绝不能自动升级成另外两层也失败。第 6 章本质上就是把这条原则做成了一张速查表。

### 2.2 恢复是 at-least-once，这部分责任在你

被恢复的 handler 会带着同样的任务身份和输入重新进入。它**不会**重放你代码的执行过程，也不会从中断处续跑某一次模型调用或 tool call。

由此带来一个躲不掉的后果：最后一个持久化 checkpoint 之后做过的工作，可能会再做一遍。Checkpoint 的粒度决定了这个重做窗口有多大，而 idempotency key、compare-and-set 写入、持久化的外部操作 ID，才是阻止“重做”变成“重复下单、重复付款、重复写入”的东西。

所以有必要把话说明白，恢复**不是**这些：不是复活旧 socket；不是确定性重放；不是把原始请求当作新任务重新提交；不能因为 Agent version 显示 `active` 就认为它成立——那只说明控制面接受了一个部署；如果重新进入时无法识别并跳过已经提交的外部副作用，它甚至谈不上安全。

### 2.3 三种集成层级

这套模型与 framework 无关。层级之间的差别，只在于有多少需要你自己接。

| 层级 | 平台负责 | 你仍然要负责 | 适用场景 |
|---|---|---|---|
| Foundry hosting 上的 Microsoft Agent Framework | 基于 Responses 的最高层集成，大部分生命周期行为已经接好 | 配置、framework checkpoint、安全的外部副作用 | 希望尽量少写恢复代码的团队 |
| Responses protocol | OpenAI 兼容协议、对话历史、streaming lifecycle、后台执行、轮询、取消 | 开启恢复能力、保留业务 checkpoint、验证 output 连续性 | 对话型和工具型 Agent |
| Invocations protocol | 只提供传输和底层原语 | session 与 task 语义、事件 schema、checkpoint 映射、轮询、恢复行为 | 结构化 workflow 与自定义协议 |

LangGraph、Microsoft Agent Framework、手写 orchestration 都能接进来。但没有任何一种能替你定义“哪些步骤算已经做完了”。

---

## 3. 评估方法：到底跑了什么

上面所有内容，在经受一次真正的中断之前都只是设计主张。下面是验证方式。

| 维度 | 固定条件 | 为什么重要 |
|---|---|---|
| 执行窗口 | 2026 年 7 月 22-23 日 | 把早期受阻或不完整的尝试挡在最终结果之外 |
| 托管环境 | Canada Central 同一个 Foundry project 中的八个 active Hosted Agent | 保持托管控制面和区域不变 |
| Runtime 与 protocol | Python 与 .NET；Responses 与 Invocations | 检验结论能否跨语言、跨 protocol 成立 |
| 范围 | 每个可运行 sample 的主场景 | 把分母固定为 **8 个场景** |
| 可接受证据 | 完整事件捕获或结构化客户端日志，外加服务端终态 | 断流或“看起来很像”的重跑都不能算通过 |
| 重复次数 | 每个场景一次被接受的端到端运行（**每场景 N=1**） | 属于能力验证，不是可靠性 benchmark |
| 排除变量 | 模型质量、业务正确性、负载、并发、成本、多区域 | 这些维度上没有可用结论 |

只有在中断之后，**完整的既定计划仍然走到终态结果**，场景才算通过。部分恢复不算。重连后卡住不算。新跑一遍产出相似文本，更不算。

| # | Runtime / protocol | 场景与中断 | 必须满足的终态证据 | 结果 |
|---|---|---|---|---|
| 1 | Python / Invocations | Research；运行实例丢失 | 恢复标记、phase 1-18、任务完成 | **PASS** |
| 2 | Python / Responses | Research；运行实例丢失 | 同一 response、output index 0-17、共 18 项 | **PASS** |
| 3 | .NET / Invocations | Research；运行实例丢失 | 恢复标记、phase 1-18、任务完成 | **PASS** |
| 4 | .NET / Responses | Research；运行实例丢失 | 同一 response、output index 0-17、共 18 项 | **PASS** |
| 5 | Python / Invocations | 审批；挂起期间运行实例丢失 | 重启后决定生效，确认号 `TRIP-182336` | **PASS** |
| 6 | Python / Responses | 审批；挂起期间运行实例丢失 | 恢复 lifecycle，确认号 `TRIP-749637` | **PASS** |
| 7 | Python / Responses | 持久化 workflow；主机替换 | French、Spanish、round-trip 输出完整 | **PASS** |
| 8 | Python / Responses | Steering；主动打断 | 第二轮排队、第一轮安全结束、第二轮完成 | **PASS** |

可选的 cancel、delete、deny 分支不在这个矩阵里，本文也没有验证它们。

---

## 4. 实测结果

### 4.1 一次比自己进程活得更久的 21.7 分钟运行

<div align="center"><img src="images/work-distribution-cn.png" width="820" alt="按比例绘制：95% 的耗时和事件发生在运行实例被销毁之后"></div>

Python Invocations 的 Research Agent 在头 15 秒里产出了 599 条事件，跑到 phase 1。随后运行实例被销毁，流断了。

没有任何重新提交。客户端重新接回，收到一个显式的恢复事件，sequence 从 **600** 继续——正好是它停下的位置。接下来的 1,237 秒里，重连后的流又送来 11,649 条事件，覆盖 phase 2 到 18，其中包含 192 条 status 事件和 17 条 phase 事件，最后停在 completed 终态。

汇总起来：1,301 秒，sequence 从 1 到 12,248，没有缺口，也没有重复阶段。换个说法，耗时和事件数在“进程死亡”这一刻，都是按 5 / 95 分开的。上面那张图就是这个比例的等比绘制——它也是反对“直接重新提交”最直观的一个论据。

### 4.2 换一种 protocol，同样的中断

语言和 protocol 都变了，结论没变。

Python Responses 的 Research 运行共记录 11,584 条事件。中断之前：13 秒内 577 条事件，output index 0，570 个文本增量。崩溃流上报告了一个 failed response。经过 **47 秒**的重连间隔，观察到 lifecycle 重放，sequence 从 578 继续，此后 1,140 秒内又来了 11,005 条事件，带着 output index 1 到 17 和 10,918 个文本增量，完成信号在重连后的流上收到。

output index 0 是中断前产出的，1 到 17 是中断后产出的。**没有任何 index 重复，也没有任何 index 缺失。** 对一个 Responses workload 来说，这是能拿到的最强证据，说明它确实还是同一个逻辑 response，而不是一次逼真的新运行——而这恰恰是重新提交的任务过不了的一关。

### 4.3 人还在思考的时候，运行实例死了

<div align="center"><img src="images/approval-recovery-cn.png" width="820" alt="审批场景实测时间线：从运行实例丢失到决定被接收共 56 秒"></div>

这是最容易被低估的一类情况，因为它发生的时候，**根本没有任何东西在执行**。Graph 停在审批点上，在等一个人。

任务在 12:22:54 启动，7 秒后调用航班和酒店工具。12:23:07 针对一个三晚东京行程请求审批，然后停下。等待到第 80 秒、也就是 12:24:27 时，运行实例被销毁。重启之后发送的审批决定在 12:25:23 被接收——距离丢失 **56 秒**。两秒后，Agent 恢复，给出的是**和崩溃前完全相同**的航班与酒店选择；12:25:30 返回确认号 `TRIP-182336`。

待审批状态、工具调用结果，以及当初摆在用户面前的那几个具体选项，全都比那个已经不存在的进程活得更久。同一模式在 Responses protocol 上的第二次运行，也拿到了自己的确认号 `TRIP-749637`。

> 这些是确定性的示例工具。确认号证明的是持久化 graph 状态和“决定只生效一次”，不是真实的航班或酒店预订。

### 4.4 29 次“失败”，其实一次都不是失败

<div align="center"><img src="images/retry-pattern-cn.png" width="820" alt="连续 29 次 HTTP 424 之后正常完成"></div>

主机替换期间，那次持久化 workflow 运行在同一个 response 上**连续 29 次**收到 `HTTP 424 Failed Dependency`。客户端没有重新提交，而是继续轮询，最后所有阶段完整产出：

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

如果客户端把第一个 424 当成终态错误，就会丢掉一次马上就要成功的运行。把重试上限设成看起来很合理的 10 次，结果也一样。这个 response 自始至终都是完好的，被替换的只是它的宿主。

这也是最容易被过度推广的一条结论，所以必须说准确：**这不代表所有 424 都可以重试。** 它只说明，“主机替换、且这个 response 仍然可寻址”这一种情况，值得先分类、再决定要不要放弃。

### 4.5 主动打断

不是所有中断都是故障。第一轮还在生成时，第二轮请求就发过来了。

新输入被接收为 `queued`，而不是被拒绝。第一轮在一个安全边界上协作式收尾，标记为已完成，而不是在生成到一半时被强杀。随后新的一轮经过 7 次 `in_progress` 轮询完成，并正确回答了新问题。也就是说，steering 是一条一等公民路径，而不是“取消 vs 重启”之间的一场竞速。

---

## 5. 最值得迁移的一条结论：别信 sequence 编号

<div align="center"><img src="images/continuity-signals-cn.png" width="820" alt="四次运行对比：传输层 sequence 三次续上，workload output 四次全部成立"></div>

如果这篇文章只能带走一条工程结论，就带走这条。

四次 Research 运行里，有三次在重新接回后 sequence 编号干净地续上了。第四次没有：.NET Responses 的流在重连后**把计数器从 5 重新开始**——但它仍然在同一个 response 上交付了 output index 1 到 17。按 workload 的标准衡量，这次运行恢复得完美无缺；按 sequence 连续性检查衡量，它会被判定为断了。

| 运行 | 中断之前 | 重新接回之后 | 信号 |
|---|---|---|---|
| Invocations / Python | seq 1-599 | seq 600-12,248 | sequence 续上 |
| Responses / Python | output index 0 | output index 1-17 | index 续上 |
| Invocations / .NET | seq 1-738 | seq 739-12,073 | sequence 续上 |
| Responses / .NET | output index 0 | output index 1-17 | index 续上，但 **sequence 从 5 重新计数** |

所以，判断连续性要看 *workload 产出了什么*——output index、phase 编号、持久化状态，而不是看 *传输层怎么给帧编号*。

顺带说一个同类陷阱：单调递增不等于没有缺口。`10, 12` 是单调的，中间却少了一个事件。只断言“递增”的连续性检查，会放过一条悄悄丢了数据的流。

---

## 6. 故障判断与恢复速查表

<div align="center"><img src="images/recovery-decision-guide-cn.png" width="560" alt="恢复前的判断流程：区分运行实例、客户端、主机替换和观察者故障"></div>

下面每一行都遵循同一条纪律：**先读取同一个逻辑任务，判断真正失败的是哪一层，在状态查清之前不创建任何新东西。**

| 现象 | 真正失败的是什么 | 错误反应 | 正确恢复 | 确认方式 |
|---|---|---|---|---|
| 流停止，没有终态事件 | 一个执行进程，不一定是任务本身 | 重新提交任务 | 等平台重新进入，再用同一任务引用和最后持久位置接回 | 恢复标记或 workload output 继续，最后读到显式终态 |
| Workflow 停在审批上，什么都没在跑 | 运行实例；挂起的 workflow 完好 | 从头重建审批请求 | 重启后把决定发给同一个逻辑任务 | 审批后路径以相同选项走到终态 |
| 客户端失去 SSE 或 HTTP 连接 | 只是观察通道 | 认为 Agent 已停止并重新提交 | 从持久化 output 位置重新接回同一任务 | output 与 phase 覆盖继续推进，且无重复业务结果 |
| 同一 response 反复返回 `424` | 暂时什么都没失败，主机正在被替换 | 把第一个 424 当作终态 | 确认属于这种情况后，对同一 response 有界退避轮询 | Response 完成，且所有预期阶段齐全 |
| 终态读取返回 `403` | 你自己的授权，不是 workload | 重跑整个任务 | 刷新观察者认证，重新执行只读查询 | 返回 `200`，状态为 completed |
| 日志在字节或时间上限处停止 | 证据采集 | 用最后一行日志推断任务失败 | 直接查询持久化状态，或重新完整采集 | 终态来自服务端读取，不是日志尾部 |
| 运行中收到新指令 | 什么都没失败，这是 steering 路径 | 强杀当前轮次并让新任务竞速 | 新输入排队，当前轮次在安全边界停止 | 旧轮次协作式结束，新输入走到终态答案 |

---

## 7. 设计建议

这几条可以迁移到本次 preview 之外。

1. **在能叫得出名字的边界上做 checkpoint。** “18 个阶段完成了 7 个”是可恢复的，“跑到中间某处”不是。
2. **给任务一个比进程活得更久的身份。** 恢复是去寻址一个逻辑任务，不是接上一个 socket。
3. **默认按 at-least-once 设计。** 每个外部副作用都要保证：checkpoint 之后重做一次是无害的。
4. **把观察者故障和任务故障分开。** Token 过期是你自己的问题，不是任务的问题。
5. **先分类状态码，再决定动作。** 判定业务失败之前，先对照持久化状态确认。
6. **让终态显式化。** 流“结束了”并不等于有结果。
7. **明确审批决定归谁负责。** 被执行两次，比晚一点执行更糟。
8. **区分挂起任务和活跃任务。** 停在审批点的 graph 没有活跃执行，其计算资源可能被回收；这是预期行为，不是故障。

---

## 8. 证据、边界与采用门槛

### 8.1 这些结论是怎么被挑战的

八次通过很容易被过度解读，所以每条结论在发布之前都先被攻击过一遍。

| 方法 | 要挑战什么 | 用到的证据 | 结论 |
|---|---|---|---|
| 证真 | 同一个逻辑任务是否到达终态？ | 同一任务引用、服务端终态、完整 phase 与 output 覆盖 | 八个场景均得到支持 |
| 证伪 | 会不会只是重跑一次，看起来像恢复？ | 同一 response 上，中断前 output index 0、中断后 1-17 | Responses 场景排除了“新任务重跑”的解释 |
| 穷举 | 是不是只挑了好看的样例？ | 固定八个主场景作为分母 | 8/8 通过；辅助分支明确排除 |
| 反证 | 如果 sequence 连续是必要条件，有效恢复是否都该满足？ | .NET Responses 正常恢复，却把计数器从 5 重启 | “必须依赖 sequence”的通用规则被推翻 |
| 逆推 | 只有终态结果，能否证明发生过恢复？ | 还必须有 checkpoint、注入实例丢失、连接中断和重启后继续 | 仅有终态的证据被判定不足 |
| 类比 | 观测是否与公开平台概念一致？ | 公开的 session 持久化与 protocol 责任边界 | 一致，但始终没有用空闲恢复代替活跃恢复的证据 |
| 一致性 | 结论能否跨 runtime 与 protocol 成立？ | Python / .NET 与 Responses / Invocations 配对 | workload output 连续性成立；传输事件形态不成立 |

### 8.2 数字能追溯到哪里

| 声明 | 来源产物 |
|---|---|
| 事件数量、sequence 区间、耗时 | 逐场景捕获的事件流 |
| Phase 与 output index 覆盖度 | 对这些捕获流的分析 |
| 审批时间线与确认号 | 客户端会话日志 |
| 424 重试行为与阶段输出 | Workflow 客户端日志 |
| Steering 排队行为与终态答案 | Steering 客户端日志 |

原始产物保留在私有边界内，因为其中包含 endpoint、任务标识、环境 metadata 和生成的 payload 文本。本文所有图表都由上述聚合值绘制，不含任何标识信息。

### 8.3 边界

- 文中数字是**一次评估的观测值**，不是 benchmark、保证或 SLA。
- 该能力当时处于 **private preview**，其实现、包、API 和部署配方不在此公开。
- 结果覆盖**八个文档定义的主场景**，每个只跑一次。cancel、delete、deny 分支不计入。
- 验证的是恢复行为，不包括业务领域正确性和模型质量。
- 在依据本文做设计之前，请以[官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)核对当前能力。

### 8.4 宣称“可以上生产”之前

针对某个具体 workload，至少还要完成这些：

- 多轮故障注入，并明确 recovery-time objective 与失败预算；
- 对每个外部写入、审批、支付、预订和 tool side effect 做幂等测试；
- 覆盖并发轮次与替代计算资源的负载与并发测试；
- 明确 timeout、cancel、retention、delete 和 dead-letter policy；
- 监控能够区分运行实例、workload、观察者和认证故障；
- 按目标区域、runtime 和 protocol，重新核对最新官方产品文档。

---

## 相关工作

| Repository | 关系 |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | 更完整的 build、deploy、operate 生命周期 |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted agent 的 tools、memory 与 skills |
| [Foundry-Agent-ModelOps-Governance](../Foundry-Agent-ModelOps-Governance/) | Operational-plane 边界梳理 |

## License

[MIT](LICENSE)
