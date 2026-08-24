# Microsoft Foundry 长任务 Agent 韧性：主动注入进程丢失的实测证据

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#3-评估方法到底跑了什么)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#4-实测结果)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#23-三种集成层级)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

一个需要跑二十二分钟的 Research 任务，刚跑到第 15 秒、刚完成 18 个阶段里的第 1 个，我们主动销毁了执行它的进程。没有任何人重新提交。二十一分钟后，同一个任务报告完成——18 个阶段全部产出，12,248 条事件，没有缺口，也没有重复阶段。

这项任务 95% 的实测耗时和事件，都发生在原进程被销毁之后。

**本文中的每一次中断都是我们主动注入的，没有一次是线上事故。** 在连续性有要求的场景里，长任务设计应考虑可能发生的重启、崩溃、OOM 终止或重新部署等进程中断——微软官方文档将这些事件列为韧性（resilience）机制要应对的情形。这不意味着每次运行都会丢失进程；工程上真正要回答的是：如果进程丢失，**任务**能否继续。这正是这八个主动注入场景要测的东西。

这篇文章讲清楚三件事：这些实测运行为什么能完成、哪些信号支持这一结论，以及哪些看似合理的处理方式可能导致任务被放弃或重复执行。

> **这是什么。** Microsoft Foundry Hosted Agent 长任务恢复行为的实测，以及公开安全的可执行检查与证据。该能力现已进入 **公共预览（public preview）**，并有[官方概念文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)。文中八个场景是 7 月在更早的 private preview 构件上运行的，因此每个数字仍是有日期的证据，不是对今天构件的断言。
> **不是什么。** 这里**不包含 Microsoft SDK 源码、完整 Agent 实现、端到端部署配方、私有 API schema 或原始 live telemetry**。本地恢复程序是真实双进程 test fixture，不是 Foundry 服务代码或 live service 证明。官方声明没有 SLA、不建议用于生产——这与第 9.4 节立场一致。

> **Author:** 魏新宇（Xinyu Wei）

[English](README.md) | 中文 | [Hosted agents 概览](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent 快速入门](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-validation.txt
.\.venv\Scripts\python scripts\verify_public_resilience_api.py --quiet
.\.venv\Scripts\python scripts\recovery_contract_demo.py demo
.\.venv\Scripts\python scripts\validate_observations.py self-test
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python scripts\validate_repo.py
```

如果 Windows 尚未启用 long-path support，请先把 monorepo clone 到较短的目录，再创建 `.venv`；否则 Azure SDK 的依赖路径可能超过旧版路径长度限制。

| Surface | 场景类型 | 这条命令能证明什么 | 不能证明什么 |
|---|---|---|---|
| 公共 SDK contract probe | dynamic-runtime | 已安装的固定版本 package 暴露 18 项受检公开符号与校验规则 | Live Hosted Agent 恢复 |
| SQLite 恢复程序 | test-fixture | 可执行参考模型中的真实 OS 进程丢失、lease 过期/接管、generation fence、checkpoint 与幂等行为 | Microsoft Foundry 私有实现 |
| 历史观测 | measured aggregate / architecture-explainer | 从 7 月和 8 月捕获结果中提取的、带日期的公开安全数值 | 可靠性 benchmark、SLA 或可复现 live 部署 |

机器可读数据、结构化日志、hash、复现命令和完整 truth contract 均在[证据索引](evidence/README.md)。

---

## 摘要

长任务暴露在进程生命周期变化中的时间通常比短调用更长。其中一种可能的故障形态是：**执行进程消失了，但逻辑任务仍然有效。** 客户端如果把每次这类中断都当成终态并直接重新提交，就可能放弃仍可寻址的任务、启动第二次运行，并重复执行外部动作。

本文评估的模型，把**逻辑任务**和**执行它的进程**拆开。在八次被接受的运行中，持久任务身份、已持久化输入和已 checkpoint 的进度跨越了注入的进程丢失；替代计算资源从记录的 checkpoint 重新进入任务。八次运行覆盖两种语言、两种 protocol 和四类中断，均走到了各自既定的终态。

| 实测项 | 数值 | 意义 |
|---|---|---|
| 注入进程丢失之后完成的工作占比 | 1,301 秒中的 **95%**，12,248 条事件中的 95% | 在这次运行中，进程丢失没有抹掉已记录的任务 |
| 从运行实例丢失到审批决定被接收 | **56 秒**，且原有选项保持不变 | 在这次运行中，待审批状态跨越了进程替换 |
| 正常完成前连续收到的 `HTTP 424` | **29 次** | 在这次运行中，重试上限 10 次会在任务完成前停止 |
| 走到既定终态的场景数 | **8 / 8**，每个场景一次被接受的运行 | 属于能力验证，不是可靠性 benchmark |
| 重新接回时传输层 sequence 无缺口的运行数 | **3 / 4** | 有一个 runtime 重置了计数器；四次 workload output 均通过验收 |

**这些证据还不能说明什么：** 生产可用性、SLA、负载与并发下的表现、多区域恢复、成本，以及业务正确性。每个场景只跑了一次。它足以支撑立项做受控评估，但不足以作为生产放行依据。

---

## 1. 背景：长任务的第三种结局

短调用通常会在同一个进程生命周期内返回或抛错。更长的运行还可能遇到另一种情况：进程消失了，逻辑任务却仍然有效。

这个窗口期里有三件事可能发生。运行实例可能停止——崩溃、重新部署、主机替换，或者某个生命周期动作。客户端的流可能中断，而且始终没收到终态事件。用户也可能跑到一半改主意。

不加判断地重新提交 create 请求，并不能恢复这几种情况。它会在原任务可能仍可寻址时启动另一个逻辑任务，从而可能带来重叠工作和重复外部动作。本文后面的模式会先判断现有任务的状态；任务仍然有效时重新接回，而 steering、取消或新建任务是另外的决策。

### 这里说的“运行实例”是什么

Hosted Agent 是客户自己的 Agent 代码，以 container image 的形式交付。Foundry 把它跑在按 session 隔离的 VM 沙箱里，并负责它的生命周期。本文所说的**运行实例**，指的就是当时正在运行的那份代码。

它不是需要客户自己运维的 Docker 容器。实例丢失，带走的是进程、内存和已有连接。按照公开文档描述的模型，实例丢失本身不会删除 Hosted Agent 定义、session，或已持久化在进程之外的任务。

### 平台本身已经提供了什么

公开平台提供的是托管基线：按 session 隔离、跨空闲回收仍然保留的 `$HOME` 和 `/files`、持久化的对话历史、独立的 Microsoft Entra 身份，以及托管的生命周期与可观测性（[来源](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)）。

公开文档现在同时描述了空闲状态持久化和韧性执行；但它仍不能替你的应用证明 checkpoint、副作用和 output 验收是否正确。本次评估针对的正是这条应用侧边界。

| 层次 | 公开文档（2026 年 7 月 21 日） | 本次实测 | 结论边界 |
|---|---|---|---|
| Session 状态 | 空闲计算恢复时还原 `$HOME` 与 `/files` | 活跃任务在注入运行实例丢失后继续 | 空闲还原与实测一致，但不能代替活跃任务恢复的证据 |
| Responses | 平台托管对话历史、streaming lifecycle 和后台轮询 | 同一 response 跨恢复交付 output index 0-17 | 支持这一次 response 的连续性结论；不是所有 workload 的 SLA |
| Invocations | 应用自行负责 payload、session 语义、task tracking 与轮询 | 观察到显式恢复事件和 phase 1-18 | 应用仍须自己保证 checkpoint 和外部副作用正确 |

### 为什么本文的恢复模型使用 Hosted Agent

针对这里的选型，Foundry 文档区分 Prompt-based agent 与 Hosted Agent。Prompt-based agent 由配置定义，不承载你自己的容器或代码包；Hosted Agent 则是在托管沙箱里跑**你自己的**代码。

这个区别决定了能否使用应用自行拥有的 handler 重入。本文描述的恢复模型，会用同一个 work identity 和输入**重新进入你的 handler**。Prompt-based agent 不暴露客户自己的应用运行时与 handler，因而无法在其中记录“18 个 phase 里的第 7 个已提交”这类进度，也无法按本文模型重新进入 handler。

微软官方文档现在也把这个结论写明了：**“Run long-lived work resiliently — preserve in-progress agent work across process interruptions and replay streamed results to reconnecting clients”**（有韧性地运行长任务——在进程中断后仍保留执行中的 agent 任务，并向重新连接的客户端重放流式结果）被列为选择 Hosted agent 而非 prompt-based agent 的理由之一（[来源](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)）。

对生产设计的实际含义是：如果 workload 需要应用自行拥有 handler、定制 checkpoint 和副作用控制，那么在这两种选项中应使用 Hosted Agent。这项选择应在架构阶段完成，再配置恢复行为。

---

## 2. 原理：寻址任务，而不是抢救进程

<div align="center"><img src="images/resilience-architecture-cn.png" width="820" alt="概念恢复流程：逻辑任务如何跨越 Hosted Agent 运行实例丢失"></div>

整套机制只建立在一个想法上：**给任务一个比进程活得更久的身份，然后重新进入这个任务，而不是去抢救那个进程。**

下面的概念流程分为七步。客户端启动一个逻辑任务，并保留它的稳定引用。执行开始之前，长任务层先把任务身份、输入，以及后续重新定位所需的租约 metadata 持久化下来。Agent 运行过程中，不断记录有业务含义的进度——phase 编号、watermark、审批状态，或者一个指向外部状态的引用。接着运行实例丢失：进程、内存、socket 全都消失，但那条持久化记录还在。Foundry 提供替代计算资源，同一个逻辑任务带着恢复上下文被重新调用，应用加载自己的 checkpoint 并从一个明确的边界继续，最后客户端重新接回、确认连续性。

把那次 18 阶段的实测运行套进这七步，顺序就变得很具体：第一到第三步覆盖 phase 1，第四步销毁进程，第五、六步跑完 phase 2 到 18，客户端到第七步才重新接回。**在这次运行中，恢复先于客户端重新接回继续推进。** 重新接回恢复的是观察，不是执行。因此，这次客户端断流本身不足以判定任务失败；判断依据来自持久化状态与 workload output。

### 2.1 四层责任必须分开

分清楚这四层，是设计工作的大头，因为它决定了出问题时你有资格得出什么结论。

| 层次 | 负责什么 | 必须保持有效 | 不能单独证明什么 |
|---|---|---|---|
| Foundry Hosted Agent 平台 | 运行沙箱、endpoint、身份、session 与对话状态、生命周期 | 能够提供替代计算资源，并继续寻址同一 session | 业务进度已经被正确 checkpoint |
| 长任务执行层 | 稳定任务身份、持久化输入、恢复入口、task 与 stream 状态 | 逻辑任务记录跨进程存在 | 外部业务动作可以安全重复 |
| Agent framework 或业务应用 | 有业务含义的 checkpoint、workflow 阶段、审批状态、终态结果 | 足以安全恢复的业务进度 | 客户端一定会正确重连 |
| 客户端与运维 | 稳定任务引用、重连游标、有界轮询、认证刷新 | 断线后仍能观察到同一个逻辑任务 | 传输层报错等于 workload 失败 |

一句话原则：**运行实例状态、业务任务状态、观察者状态，是三个不同的故障域。** 其中一层出问题，绝不能自动升级成另外两层也失败。第 6 章本质上就是把这条原则做成了一张速查表。

### 2.2 恢复是 at-least-once；应用必须保证 replay 安全

被恢复的 handler 会带着同样的任务身份和输入重新进入。它**不会**重放你代码的执行过程，也不会从中断处续跑某一次模型调用或 tool call。

这里有一个无法由 runtime 单独消除的设计影响：最后一个持久化 checkpoint 之后做过的工作，可能会再做一遍。Checkpoint 的粒度决定了这个重做窗口有多大，而 idempotency key、compare-and-set 写入、持久化的外部操作 ID，才是阻止“重做”变成“重复下单、重复付款、重复写入”的东西。

所以有必要把话说明白，恢复**不是**这些：不是复活旧 socket；不是确定性重放；不是把原始请求当作新任务重新提交；不能因为 Agent version 显示 `active` 就认为它成立——那只说明控制面接受了一个部署；对于会提交外部副作用的 workload，如果重新进入时无法识别并跳过已提交的副作用，重入就不安全。

### 2.3 三种集成层级

这套模型与 framework 无关。层级之间的差别，只在于有多少需要你自己接。

| 层级 | 平台负责 | 你仍然要负责 | 适用场景 |
|---|---|---|---|
| Foundry hosting 上的 Microsoft Agent Framework | 基于 Responses 的较高层集成，已接入更多生命周期行为 | 配置、framework checkpoint、安全的外部副作用 | 希望使用更多生命周期集成的团队 |
| Responses protocol | OpenAI 兼容协议、对话历史、streaming lifecycle、后台执行、轮询、取消 | 开启恢复能力、保留业务 checkpoint、验证 output 连续性 | 对话型和工具型 Agent |
| Invocations protocol | 只提供传输和底层原语 | session 与 task 语义、事件 schema、checkpoint 映射、轮询、恢复行为 | 结构化 workflow 与自定义协议 |

LangGraph、Microsoft Agent Framework、手写 orchestration 都能接进来。但没有任何一种能替你定义“哪些步骤算已经做完了”。

### 2.4 LRA 核心：持久任务、租约与恢复重入

本节后面的客户端代码**不是** LRA 核心。本文把核心建模为一个 runtime state machine：即使 worker 进程已经消失，它仍然保留逻辑任务的身份与输入。下面的模型不绑定具体方法名或存储 schema；第 2.5.3 节再把这些概念映射到本轮测试的公开 API。

| 核心原语 | 持久化职责 | 故障规则 |
|---|---|---|
| Work record | 稳定的任务与输入身份、持久化输入、状态、retry state、小型 metadata | 替代 worker 收到同一个身份与输入，不创建新任务 |
| Lease | 当前唯一 owner、lease generation 与过期时间 | 活跃 worker 持续续租；进程丢失只会遗弃 lease，不写入虚假终态 |
| Atomic reclaim | 对过期 lease 做 compare-and-set 接管 | 只有一个替代 worker 能推进 lease generation 并重新进入任务 |
| Progress reference | 小型 watermark，或指向 framework/application checkpoint 的引用 | 最后一个已提交 checkpoint 之后的工作可能再次执行 |
| Durable output state | 已 checkpoint 的 response snapshot、stream event 与显式终态 | 观察者从已提交 output 重建；连接关闭本身不等于完成 |

```mermaid
sequenceDiagram
	participant C as 客户端
	participant T as 持久任务存储
	participant A as Worker A
	participant P as Checkpoint/output 存储
	participant R as Recovery scanner
	participant B as Worker B

	C->>T: 创建稳定 work ID 并持久化输入
	T->>A: 原子取得 lease（generation n）
	loop Worker A 存活期间
		A->>T: 续租
		A->>P: 提交一个业务 phase 与 checkpoint
	end
	A--xA: 进程消失，停止续租
	R->>T: 发现已过期的 running lease
	R->>T: Compare-and-set reclaim（generation n+1）
	T->>B: 同一 work ID、输入、metadata、恢复入口
	B->>P: 加载最后一个已提交 checkpoint
	B->>P: 从下一个可安全 replay 的 phase 继续
	B->>T: 写入显式终态
	C->>P: Retrieve 或重新接回同一逻辑 output
```

硬崩溃的进程无法执行清理。在上面的概念模型中，lease 停止续期，后续 scanner 发现它已过期，再由新 worker 带条件地接管同一条记录。模型中的 generation fencing 用于阻止旧 worker 在后续 generation 取得所有权后继续提交。

#### 2.4.1 可执行的 recovery contract 参考实现

原来不可运行的示意代码已删除。[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) 是只使用 Python 标准库的可执行代码：SQLite 持久化任务与输入；Worker A 提交 phase 1 后通过 `os._exit(9)` 退出；lease 过期后，独立的 Worker B 带条件地接管 generation 2，并提交 phase 2-5。程序生成 [JSON summary](evidence/recovery-contract-demo.json) 和 [JSONL 事件日志](evidence/recovery-contract-events.jsonl)；六项单元测试覆盖 lease 计时、既有状态保护、硬退出、旧 generation fence、幂等/冲突 replay 和输入差异行为。

这个程序属于 **test fixture**。它能证明仓库里的参考算法按文档执行；它不是 Microsoft Foundry 服务代码，也不是 live Hosted Agent 证据。

代码实际实现并测试了四个 invariant：

1. **Reclaim 带条件。** 只有 pending 任务，或 lease 已过期的 running 记录才能被接管。
2. **每个持久化写入都受 generation fence 保护。** Store 会核实 owner、generation、status 和 lease 过期时间；每次 phase commit 都会续期参考 lease。
3. **Phase replay 幂等。** 相同 phase key 与结果会被去重；内容冲突时 fail closed。
4. **一个事务负责推进进度。** SQLite 原子记录 phase result、idempotency key、worker generation 与 checkpoint。

LRA runtime 负责把同一个任务重新送进 handler，却无法判断支付、预订、tool call 或 workflow node 是否已经提交。这就是为什么 application checkpoint 与 side-effect ledger 属于恢复契约，但不属于 lease engine 本身。

### 2.5 从 Hosted Agent 配置到一次可恢复调用

这项能力不是在 Portal 里打开一个开关就结束了，四层配置必须同时对齐。四层现在都有公开 surface，但中间两层仍属于 **public preview / experimental** API，应用仍须自己设计 checkpoint 与副作用边界。

| 层次 | 配置 | 开启什么 | 单独做不到什么 |
|---|---|---|---|
| Hosted Agent version | `host: azure.ai.agent` + Responses protocol | 部署客户代码并暴露托管 Responses endpoint | 不能让活跃 handler 自动跨 crash 恢复 |
| Agent 进程（public preview） | Resilient task enablement | 进程丢失后重新调用持久化任务 | 不知道哪个业务步骤已经提交 |
| Handler（public preview） | `TaskContext` + framework checkpoint hook | 定义最后一个持久化 output 边界 | 不能自动保证外部副作用幂等 |
| 客户端 | `store=True`、`background=True`、复用同一 `response.id` | 创建可寻址任务，并允许轮询或重新接回 | 不能用新建 response 代替恢复 |

#### 2.5.1 用 Responses protocol 声明 Hosted Agent

本仓库不提供省略 project、模型、身份和资源值的不完整 `azure.yaml`。应从[官方 Hosted Agent samples 中可部署的 `azure.yaml` 与应用源码](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents)开始，再按当前 sample 与 SDK 版本支持的方式应用 public-preview recovery 配置。

在完整 azd project 中，`azd deploy` 读取真实 service definition，创建 Hosted Agent version，并把 endpoint 路由到声明的 protocol。CPU、内存、镜像或源码打包、模型选择与身份属于 version definition；它们不是 recovery checkpoint。

#### 2.5.2 让 Agent 进程进入恢复模式

本次评估使用的构件，在 Responses host 上增加了一个 **preview recovery opt-in**。对于已存储的 background response，这个开关会把行为从“进程崩溃后标记失败”改成“在下一个进程生命周期重新调用 handler”。另一个 preview steering 开关则允许重叠的新一轮进入队列，并让当前轮次协作式停止。

评估当时，这些构造参数确实不在公共 PyPI 接口中。**本轮测试的公开 package 已提供相关符号。** 对 `azure-ai-agentserver-core` 2.0.0 实测时，resilient task surface 导出了 `task`、`multi_turn_task`、`Task`、`MultiTurnTask`、`TaskContext`、`TaskMetadata`、`RetryPolicy`、`resilient_tasks_enabled`、`set_resilient_tasks_enabled`；Responses package 另外导出了 `ExitForRecoverySignal` 与 `ResponseExitForRecovery`。SDK 在导入时将这些符号标记为 experimental，这与 public preview 状态一致。在依赖任何具体字段之前，请以当前 package 为准。

#### 2.5.3 从业务 checkpoint 恢复

重新调用 handler 只代表“重新进入”，并不代表“从正确位置继续”。在受测 sample 中，handler 收到恢复上下文、加载最后一个 framework snapshot，并且只在完整业务单元已持久化后提交 framework checkpoint。该 sample 把“一个完成 phase”映射成“一个 finalized output item”：进程死在 checkpoint 之前时 phase 再跑一次；死在 checkpoint 之后时，恢复后的 handler 跳过它。

公开 SDK 现在提供了与这些概念对应的字段和方法，并与上文模型相符：

| 本文描述的契约 | 公开 API（实测确认，`azure-ai-agentserver-core` 2.0.0） |
|---|---|
| 持久化的任务身份 | `TaskContext.task_id` |
| 输入身份 | `TaskContext.input_id` |
| 恢复重入，而不是重试 | `TaskContext.entry_mode` 为 `Literal["fresh", "resumed", "recovered"]`，且 `recovery_count` 与 `retry_attempt` 是**两个独立字段** |
| 小体量的持久 checkpoint 索引 | `TaskContext.metadata`（`TaskMetadata`，提供 `get` / `set` / `increment` / `append` / `flush`） |
| 协作式停止与延后 | `TaskContext.shutdown`、`TaskContext.exit_for_recovery()` |
| Steering | `TaskContext.is_steered_turn`、`TaskContext.pending_input_count` |
| 与恢复分开的有界重试预算 | 通过 `@task(retry=...)` 传入的 `RetryPolicy` |

本次恢复重入把两个字段的差异具体呈现出来：替换之后报告的是 `recovery_count=1`、`retry_attempt=0`。这个结果支持把恢复与 handler retry 分开处理；具体计数仍然只是这次运行的观测值。另外，在本轮测试的 package 中，handler 的第一个参数必须命名为 `ctx`，并声明参数化的 `TaskContext[Input]`；参数名不同或裸写 `TaskContext`，都会在装饰阶段被拒绝。

微软官方对这套模型的图示如下。它与本文提前一个月从实测中推导出的循环，以及第 2.4 节的时序图高度一致。

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="微软官方的租约恢复图：work identity 与 input identity，runtime 持久化输入并取得 lease，handler 运行期间 runtime 续租，进程停止后 lease 被放弃，后续进程重新取得任务记录，handler 从头重入后选择重跑或从持久化边界继续"></div>

<p align="center"><sub>微软 <a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Resilience for long-running Microsoft Foundry hosted agents</a> 中的 <i>“Lease-based recovery of a resilient work item”</i>，© Microsoft，依据 <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> 原样使用。该图片<b>不适用</b>本仓库的 MIT License。</sub></p>

应用侧的模式没有变化：

1. 读取稳定的逻辑任务身份和最后一个已提交业务 watermark。
2. 从 framework snapshot 或外部存储重建应用状态。
3. 只执行一个可以安全 replay 的 phase。
4. 持久化该 phase 的 output 与副作用标识。
5. 只有第 4 步成功后，才推进 framework checkpoint。

Replay 窗口内的支付、预订、写入或 tool action，仍然必须采用第 6.4 节的幂等设计。

#### 2.5.4 把任务下发和状态观察分开

标准 Hosted Agent client surface 来自 Foundry project client，但可运行的生产 client 还需要应用自己的真实持久化存储、身份、endpoint 和 workload schema。原代码块引用了未定义依赖，因此已删除，不再把它包装成可运行代码。

本仓库现在只对自己能完整负责的部分做端到端执行：[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) 实现并测试原子 durable ledger；[`validate_observations.py`](scripts/validate_observations.py) 校验调用方提供的 workload 证据，并对未分类状态码 fail closed。真实认证 client 调用应使用[官方 Hosted Agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)与 samples。本仓库不提供虚构 endpoint、身份或持久化参数的环境专用 dispatch client。

把观察能力放到只读应用 adapter 后面，是可维护性和 least-privilege pattern，**不是**安全沙箱或 RBAC 边界。不可信 observer 仍需独立服务与身份。Recovery objective 是 workload 配置，不是固定重试次数；应按健康运行时间和 workload 自己的替换余量设置。平台终态与 workload 完整性仍是两道独立检查。

这个应用模式存在一个公共 API 边界：远端 create 调用与应用持久化记录返回的 response ID 不是一个原子事务；本轮测试的公开 create 调用也不支持按应用自己的 work key 找回 response。进程可能停在远端调用之前，也可能停在远端调用成功、应用尚未记录 response ID 之后。此时应保留这条结果未知的应用状态，不能自动再次 create。普通 transactional outbox 无法判断一次结果未知的远端调用是否成功。生产 dispatcher 需要产品支持的 idempotency / deduplication contract，或针对未决记录与 orphan response 的运维对账路径。本次评估只在 response ID 已持久化后开始观察。

应用已持久化 response ID 与 deadline 后，如果轮询进程消失，新 observer 会从这些应用自有数据 retrieve **同一个 response**。Streaming 本身是公开的 Responses 模式；active-handler crash replay 现在属于单独启用的 **public-preview resilient execution**。本次评估会在可用时持久化传输游标，把新的 `response.in_progress` snapshot 当作 reset point，并根据 finalized item 重建观察者输出。

最重要的是，它**没有**把高位 transport sequence cursor 当成唯一恢复 key：有一次实测的 runtime 在恢复后把 sequence 从 5 重新计数。Sequence number 可以在兼容的 stream lifetime 内优化 replay，但真正的恢复权威是持久化 `response_id` 与 workload state。仍然要按第 5 节验证 finalized output index、phase 和持久化业务状态。

后续的顺序轮次可以设置 `previous_response_id=response_id`。并发排队和协作式 steering 使用 public-preview resilient task surface；`previous_response_id` 本身只负责建立 response chain 连续性。

部署后，一条简洁的操作路径是 `azd ai agent invoke`，它会替普通调用管理 Hosted Agent session 与 Responses conversation。如果系统必须持久化 background response ID、轮询 deadline、dispatch / observe 分离和 workload 终态检查，应使用应用自己实现并测试过的 client。

---

## 3. 评估方法：到底跑了什么

上面所有内容，在经受一次真正的中断之前都只是设计主张。下面是验证方式。

### 当前 public-preview 契约检查

下面的历史战役使用的是 7 月可用的 private-preview 构件。为避免把旧 package surface 当作当前状态，Quick Start 会在干净的 Python 3.13 环境中安装并检查固定版本的公共 packages。`--help` 说明检查范围与退出码。已提交的 [18 项检查证据](evidence/public-sdk-contract.json) 由 `--format json --output` 生成；本地复测应写入已忽略的 `.demo-state` 目录，除非维护者明确刷新 committed evidence 与 manifest。任何断言失败都会返回非零退出码。

固定版本检查对 `azure-ai-agentserver-core` 2.0.0、`azure-ai-agentserver-invocations` 1.0.0 和 `azure-ai-agentserver-responses` 2.0.0 的 **18 项断言全部通过**。检查覆盖 package 版本、recovered entry mode、相互独立的 recovery/retry 计数、work/input identity、metadata checkpoint 操作、协作式 shutdown、exit-for-recovery、steering、Responses recovery signal、retry policy、enablement，以及当前 handler 契约：第一个参数必须命名为 `ctx`，并声明为 `TaskContext[Input]`。

这是**对公共 SDK 契约的真实冒烟测试（smoke test）**，不是 mock，也不等于验证了线上服务的恢复能力。Mock 适合验证应用 checkpoint、幂等与 side-effect watermark；它不能证明 Foundry 已经替换 host 或重新取得 lease。要宣称可以上生产，仍须按第 9.4 节部署 Hosted Agent 并做多轮故障注入。

### 在当前构件上复测（2026 年 8 月）

本轮先在 2022 工作订阅上复测两件事；这个订阅曾在更早的预览期由产品组开通过。后文还会在另一个**从未开通过预览**的订阅上重复已部署场景。

**7 月的阻断在这个订阅上没有再次出现。** 当时战役卡住，是因为 `/tasks` 返回 `404`：该订阅当时不在 private preview 白名单里，而扫描 6,253 个订阅 feature 也找不到可自助开启的开关。8 月复测时，同一个调用返回 `200`，任务列表为空，`/agents` 与 `/assistants` 同样是 `200`。由于这个订阅以前被开通过，后文那个从未开通过的订阅才是更强的可用性检查。

**当前 SDK/runtime 构件复现了这条受测恢复路径。** 跑一个 18 阶段的持久化任务，在 phase 1 提交后用 `os._exit(9)` 硬杀 worker，租约在没有任何清理的情况下被遗弃。随后由一个**独立的操作系统进程**接管：

| 复测观测项 | 数值 |
|---|---|
| 注入进程丢失之前提交的 phase | 18 个中的 1 个 |
| 恢复之后由另一个进程提交的 phase | 18 个中的 17 个 |
| 序列连续性 | 1-18，无缺口，无重复 |
| 跨进程的 work identity 与 input identity | 完全一致 |
| 第二个进程报告的 `entry_mode` | `recovered` |
| 恢复时的 `recovery_count` / `retry_attempt` | `1` / `0` |
| 回收间隔 | 1.93 秒 |

最后一行才是关键。第 5 节当初只能从行为上论证「恢复不是重试」；当前 public-preview API 现在把两者公开为相互独立的计数器，而恢复重入报告的正是预测中的那组数值。

**这次复测不是什么。** 各 phase 的耗时是人为 sleep，链路中也没有模型推理，因此其耗时数据没有任何性能含义。它是在本地双进程测试中，对当前 SDK/runtime 构件的持久任务、租约遗弃、回收与重入路径做演练；它不是线上 Hosted Agent 证据，也**没有**重新测量 7 月那八个场景。那些数字仍然标注为 7 月观测值。

### 在普通订阅上，验证真实部署的 Agent

上面那项检查跑的是 SDK。这一项跑在真实 Hosted Agent 上，因为两者回答的是不同的问题。

官方公开样例库现在提供 `bring-your-own/responses/resilient-streaming` 与 `resilient-steering`，其描述里写明使用 `stream.checkpoint()` 与 `context.persisted_response`。保留 sample handler 逻辑，并采用下文说明的兼容 package pins 后，在曾被开通过的 2022 工作订阅上部署；本次复测**没有新提交白名单申请，也没有注册 feature**。部署耗时 4 分 03 秒，Agent 状态为 `active`。7 月开通前，`/tasks` 曾返回 `404`。

在这个真实 endpoint 上创建一个 stored background response，并**趁它仍处于 `in_progress` 时**，通过重新部署替换掉运行实例。之后再用**同一个 response id** 轮询，得到的是 `completed`，三个阶段的 output item 全部齐备，无缺口、无重复阶段。容器日志显示 runtime 通过 `lease_owner`、`lease_instance_id`、`lease_duration_seconds=60` 等租约字段和带 ETag 保护的 `PATCH` 更新驱动 task store；这些信号与第 2.4 节描述的租约和 compare-and-set 模型一致。

随后对四个官方 resilient 样例做了同样的中断。它们合起来覆盖了 7 月战役测过的那几类场景：

| 复测场景 | 样例 | 中断于 | 结果 |
|---|---|---|---|
| Responses，流式恢复 | `resilient-streaming` | 22.6 秒 | **PASS**——同一 response id，3 个 item，无缺口无重复 |
| Responses，steering | `resilient-steering` | 23.3 秒 | **PASS**——同一 response id 给出完整答案 |
| Invocations，research 恢复 | `resilient-research` | 28.4 秒 | **PASS**——同一 `invocation_id` 走到 `completed` |
| Invocations，审批比实例活得久 | `resilient-approval-gate` | 25.3 秒 | **PASS**——决定虽然是在替换**之后**才发送的，仍然被接收（`202`），任务完成 |

最后一行重现了 7 月的一项观测：实例是在 Agent 停在审批门、**没有应用步骤正在执行**时被替换掉的。随后针对这个「原宿主已经不存在」的任务提交决定，它仍然被接收了。

还有两项检查值得报告，包括那个**没有按预期发生**的。

**同一场景也在一个从未开通过预览的订阅上通过。** 上面那次部署使用的是产品组曾在预览期帮忙开通过的订阅。换到一个**从未开通过**的 2026 工作订阅后，得到相同的验收结果：`azd up` 用时 3 分 29 秒成功，同样的中断之后 response 仍然 `completed`、三个 item 齐全。两个订阅算不上抽样，也不能说明所有 tenant、region 或订阅都已就绪；它只能说明，在这个受测订阅上，使用该场景不要求事先开通过预览。

**这次没有复现那串 `424`。** 第 4.4 节依据的是 7 月主机被替换期间观测到的 29 次连续 `424`。这次在强制替换的窗口内每 0.4 秒轮询同一个 response，得到的是 **26 次轮询、全部 `200`、没有瞬时错误**。由于两次中断路径不同，这个结果不能反驳 7 月的观测。工程建议也继续保持限定：先分类 `424`，再决定是否把它视为终态。数字 29 仍然只是 7 月观测，本次当前构件测试没有复现。

这里还出现了一个 package 版本兼容问题。首次部署在运行时返回 `HTTP 500`，容器日志显示 `resilient_task_handler_failure ... exc_type=AttributeError`，运行的是 `ai-agentserver-core/2.1.0b2`。样例把 `responses` 钉在 `2.0.0b1`，却只对 `core` 要求 `>=2.0.0b10`，于是容器解析到了比 handler 编写时更新的 beta。把版本钉为 `core==2.0.0`、`responses==2.0.0` 和 `invocations==1.0.0` 后，相关 samples 中的已观测故障消失；四个 sample 都使用了这组兼容版本。对于这些 preview sample deployments，精确的兼容版本 pins 避免了原下限允许的 beta 版本偏移。

这些中断都是通过强制替换运行实例造成的——它是平台级事件，但不等同于一次计划外的主机崩溃；样例的各阶段也仍然是模拟的。本轮覆盖四类场景、每类一次被接受的运行——属于当前构件上的能力验证，不是一次新的可靠性 benchmark，也不是把 7 月那套完整矩阵重跑一遍。7 月的 .NET 运行**没有**复测：在本次复测时，公开 C# samples 虽然提供 Hosted Agent，但没有任何一个使用 resilient task，因此那些结果仍然只是 7 月观测值。

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

### 4.1 一次跨越主动注入进程丢失的 21.7 分钟运行

<div align="center"><img src="images/work-distribution-cn.png" width="820" alt="按比例绘制：95% 的耗时和事件发生在注入运行实例丢失之后"></div>

Python Invocations 的 Research Agent 在头 15 秒里产出了 599 条事件，跑到 phase 1。随后我们销毁了运行实例，流断了。

没有任何重新提交。客户端重新接回，收到一个显式的恢复事件，sequence 从 **600** 继续——正好是它停下的位置。接下来的 1,237 秒里，重连后的流又送来 11,649 条事件，覆盖 phase 2 到 18，其中包含 192 条 status 事件和 17 条 phase 事件，最后停在 completed 终态。

汇总起来：1,301 秒，sequence 从 1 到 12,248，没有缺口，也没有重复阶段。换个说法，耗时和事件数在“进程死亡”这一刻，都是按 5 / 95 分开的。上面那张图按比例画出了这个结果，也说明为什么在这次运行中直接重新提交会是错误选择。

### 4.2 换一种 protocol，同样的中断

语言和 protocol 都变了，这次受测的连续性结果仍然成立。

Python Responses 的 Research 运行共记录 11,584 条事件。中断之前：13 秒内 577 条事件，output index 0，570 个文本增量。崩溃流上的 response 处于 `failed` 状态。经过 **47 秒**的重连间隔，观察到 lifecycle 重放，sequence 从 578 继续，此后 1,140 秒内又来了 11,005 条事件，带着 output index 1 到 17 和 10,918 个文本增量，完成信号在重连后的流上收到。

output index 0 是中断前产出的，1 到 17 是中断后产出的。**没有任何 index 重复，也没有任何 index 缺失。** 结合未变化的 response identity，这是支持本次运行继续同一个 stored response、而不是创建新 response 的强证据；它不是对所有 Responses workload 的通用证明。

### 4.3 人工审批等待期间注入运行实例丢失

<div align="center"><img src="images/approval-recovery-cn.png" width="820" alt="审批场景实测时间线：从运行实例丢失到决定被接收共 56 秒"></div>

这类情况容易被忽略，因为当时**没有应用步骤正在执行**。Graph（工作流图）停在审批点上，在等一个人。

任务在 12:22:54 启动，7 秒后调用航班和酒店工具。12:23:07 针对一个三晚东京行程请求审批，然后停下。等待到第 80 秒、也就是 12:24:27 时，我们销毁了运行实例。重启之后发送的审批决定在 12:25:23 被接收——距离丢失 **56 秒**。两秒后，Agent 恢复，给出的是**和中断前完全相同**的航班与酒店选择；12:25:30 返回确认号 `TRIP-182336`。

待审批状态、工具调用结果，以及当初摆在用户面前的那几个具体选项，全都比那个已经不存在的进程活得更久。同一模式在 Responses protocol 上的第二次运行，也拿到了自己的确认号 `TRIP-749637`。

> 这些是确定性的示例工具。确认号支持以下结论：在这些运行中，持久化 Graph 状态与一次审批应用跨越了进程替换；它们不能证明通用的 exactly-once 保证，也不代表真实的航班或酒店预订。

### 4.4 完成前收到的 29 次 `424`

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

如果客户端把第一个 424 当成终态错误，就会在这次运行完成之前放弃它；重试上限设成 10 次也会如此。在这个观测场景中，同一个 response 最终带着全部预期 output 完成，因此这串 `424` 不是终态。

这也是最容易被过度推广的一条结论，所以必须说准确：**这不代表所有 424 都可以重试。** 它只说明，“主机替换、且这个 response 仍然可寻址”这一种情况，值得先分类、再决定要不要放弃。

### 4.5 主动打断

不是所有中断都是故障。第一轮还在生成时，第二轮请求就发过来了。

新输入被接收为 `queued`，而不是被拒绝。第一轮在一个安全边界上协作式收尾，标记为已完成，而不是在生成到一半时被强杀。随后新的一轮经过 7 次 `in_progress` 轮询完成，并给出预期答案。在这次运行中，steering 走的是排队与协作式停止路径，而不是“取消 vs 重启”之间的竞速。

---

## 5. 在受测模型中，传输 sequence 是诊断信号，不是唯一恢复依据

<div align="center"><img src="images/continuity-signals-cn.png" width="820" alt="四次运行对比：传输层 sequence 三次续上，workload output 四次全部成立"></div>

如果这篇文章只能带走一条工程结论，就带走这条。

四次 Research 运行里，有三次在重新接回后 sequence 编号干净地续上了。第四次没有：.NET Responses 的流在重连后**把计数器从 5 重新开始**——但它仍然在同一个 response 上交付了 output index 1 到 17。按照本次评估的 workload 验收标准，这次运行通过；如果只看 sequence 连续性，它会被误判为中断。

| 运行 | 中断之前 | 重新接回之后 | 信号 |
|---|---|---|---|
| Invocations / Python | seq 1-599 | seq 600-12,248 | sequence 续上 |
| Responses / Python | output index 0 | output index 1-17 | index 续上 |
| Invocations / .NET | seq 1-738 | seq 739-12,073 | sequence 续上 |
| Responses / .NET | output index 0 | output index 1-17 | index 续上，但 **sequence 从 5 重新计数** |

因此，这几次运行主要根据 *workload 产出了什么*——output index、phase 编号和持久化状态——做验收。传输层编号只作诊断；其他 protocol 应按自身语义定义验收标准。

顺带说一个同类陷阱：单调递增不等于没有缺口。`10, 12` 是单调的，中间却少了一个事件。只断言“递增”的连续性检查，会放过一条悄悄丢了数据的流。

---

## 6. 可执行 validator、证据与修复

从这里开始，平台能力要靠客户端工程来接住。[`validate_observations.py`](scripts/validate_observations.py) 包含下面讨论的真实可执行检查，其 [JSON self-test report](evidence/observation-validation.json) 同时记录通过与失败路径。历史服务数值保留在公开安全的[聚合证据](evidence/historical-observations.json)中；原始日志因第 9.2 节说明的原因继续留在私有边界。

### 6.1 连续性：同时拒绝缺口和重复

原检查实质上是 `sequence == sorted(sequence)`。它只能证明顺序，不能证明连续。[`validate_observations.py`](scripts/validate_observations.py) 中真实的 `sequence_has_no_gap` 与 `output_coverage_complete` 函数，会逐项检查相邻差值和完整预期 output 区间。

| 反例 | 原排序检查 | 修复后的检查 |
|---|---:|---:|
| 丢事件：`[10, 12]` | `True` | `False` |
| 重复事件：`[10, 10, 11]` | `True` | `False` |
| 干净事件流：`[10, 11, 12]` | `True` | `True` |

同一组可执行检查也能拒绝缺少 index 或重复 index 的“已完成 output item 清单”。输入时必须保证每个已完成 item 只出现一次，不能把每个 streaming delta 都直接喂进去，因为同一个 item 的多个 delta 会合法复用同一个 `output_index`。在这个 helper 中，传输层 sequence 只作诊断证据；验收还会检查 workload index、phase 和持久化业务状态。其他 protocol 应按自身语义定义验收标准。

### 6.2 终态：一个 `done` 帧不能证明成功

本地评估证据中确实有只带 `done` 帧的事件流，但 harness 的通过条件来自显式 invocation 状态与 workload 断言。流关闭可能代表成功、取消、失败，也可能只是观察连接断了。可执行的 `completion_is_proven` 检查同时要求服务状态、显式终态事件和预期 phase 数量。

这是从 harness 的 phase-based run 中提炼出的实现模式，不是通用适配器。Responses 客户端应替换成自己的显式终态事件与 output coverage 规则；单独一个 `{"type": "done"}` 仍然不能证明业务结果成立。

### 6.3 有界重试：把 `424` 和 `403` 分开处理

7 月聚合数据记录了完成前连续 29 次 `424`，但不公开 response identifier。[`validate_observations.py`](scripts/validate_observations.py) 中真实的 `recovery_action` 函数保留 same-work 条件，区分已确认的 host replacement 与 observer auth 过期，遵守调用方 deadline，并在信号不足时 fail closed。已提交的 JSON report 包含已分类和未分类的 `424`/`403` 用例。

决定何时停止的应该是 workload 恢复目标所定义的 deadline，而不是一个随手设定的很小的重试次数。`403` 需要独立分类：先核实观察者身份、scope 和持久化 workload 状态；只有确认凭据过期时才刷新。重新执行只读查询，比重放业务任务更安全。

### 6.4 人工审批：决定与副作用都必须幂等

实测审批运行只跨过一次暂停点，并产生确认号 `TRIP-182336`；结构化公开 aggregate 记录了从实例丢失到决定被接收的 56 秒和终态结果，但不公开私有 session log。

恢复后，同一条审批消息可能再次送达。[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) 中可执行的 SQLite ledger 会原子记录 phase result、idempotency key、generation 与 checkpoint；测试证明相同 replay 被去重，内容冲突时 fail closed。它不会虚构 booking API。生产下游操作仍须遵守同一个 idempotency identity，否则仍可能执行两次。

---

## 7. 故障判断与恢复速查表

<div align="center"><img src="images/recovery-decision-guide-cn.png" width="560" alt="恢复前的判断流程：区分运行实例、客户端、主机替换和观察者故障"></div>

下面每一行只是诊断起点，不是“现象必然对应某个根因”的通用映射。**先读取同一个逻辑任务，用持久化证据判断可能出问题的层次，在状态查清之前不创建新任务。**

| 现象 | 可能的层次 / 需要核实什么 | 不安全的反应 | 更安全的下一步 | 确认方式 |
|---|---|---|---|---|
| 流停止，没有终态事件 | 观察者、网络或 runtime；仅凭断流无法区分 | 重新提交任务 | 查询同一任务；它仍可寻址时，从持久化 output 位置重新接回 | 恢复标记或 workload output 继续，最后读到显式终态 |
| Workflow 停在审批上 | 本次实测中是 runtime 被替换；应先核实挂起任务仍可寻址 | 从头重建审批请求 | 恢复后找到同一任务，再把决定发给它 | 审批后路径以预期选项走到终态 |
| 客户端失去 SSE 或 HTTP 连接 | 可能只是观察通道；应核实持久化服务状态 | 认为 Agent 已停止并重新提交 | 从持久化 output 位置重新接回同一任务 | output 与 phase 覆盖继续推进，且无重复业务结果 |
| 同一 response 反复返回 `424` | 本次实测中是主机替换期间的临时依赖；其他根因仍有可能 | 把所有 424 都当终态或都当可重试 | 先分类；确认 response 仍可寻址后，再对同一 response 做有界退避轮询 | Response 完成，且所有预期阶段齐全 |
| 终态读取返回 `403` | 可能是观察者 authentication 或 authorization；不能据此推断 workload 状态 | 重跑整个任务 | 核实身份与 scope；凭据过期时刷新，再执行只读查询 | 已获授权的读取返回持久化终态 |
| 日志在字节或时间上限处停止 | 证据采集可能不完整；workload 状态仍未知 | 用最后一行日志推断任务失败 | 直接查询持久化状态，或重新完整采集 | 终态来自服务端读取，不是日志尾部 |
| 运行中收到新指令 | 如果启用了 steering，这可能是 steering 路径；应核实 protocol 状态 | 强杀当前轮次并让新任务竞速 | 通过 steering 路径排队，或执行应用已定义的取消策略 | 旧轮次按设计结束，新输入到达预期终态 |

---

## 8. 设计建议

下面是从受测故障形态中提炼的工程建议，不是产品保证。只有在相同假设成立时，才应迁移到本次 preview 之外。

1. **在有持久化记录、可验证的边界上做 checkpoint。** “18 个阶段中的第 7 个已完成”这类持久化标记可以作为恢复点；如果只有“跑到中间某处”而没有可验证 checkpoint，就不足以安全恢复。
2. **给任务一个比进程活得更久的身份。** 恢复是去寻址一个逻辑任务，不是接上一个 socket。
3. **默认按 at-least-once 设计。** 每个外部副作用都要保证：checkpoint 之后重做一次是无害的。
4. **把观察者故障和任务故障分开。** 观察者 token 过期本身不能证明 workload 已经失败。
5. **先分类状态码，再决定动作。** 判定业务失败之前，先对照持久化状态确认。
6. **让终态显式化。** 流“结束了”并不等于有结果。
7. **明确审批决定归谁负责。** 被执行两次，比晚一点执行更糟。
8. **区分挂起任务和活跃任务。** 停在审批点的 Graph 没有活跃应用步骤，其计算资源可能被回收。这可能是正常生命周期行为；判定为故障前应先核实持久化状态。

---

## 9. 证据、边界与采用门槛

### 9.1 这些结论是怎么被挑战的

八次通过很容易被过度解读，所以每条结论在发布之前都先被攻击过一遍。

| 方法 | 要挑战什么 | 用到的证据 | 结论 |
|---|---|---|---|
| 证真 | 同一个逻辑任务是否到达终态？ | 同一任务引用、服务端终态、完整 phase 与 output 覆盖 | 八个场景均得到支持 |
| 证伪 | 会不会只是重跑一次，看起来像恢复？ | 同一 response 上，中断前 output index 0、中断后 1-17 | Responses 场景排除了“新任务重跑”的解释 |
| 穷举 | 是不是只挑了好看的样例？ | 固定八个主场景作为分母 | 8/8 通过；辅助分支明确排除 |
| 反证 | 如果这次 Responses 恢复必须依赖 sequence 连续，被接受的运行是否应满足它？ | .NET Responses 通过 workload 验收，却把计数器从 5 重启 | sequence 连续假设不适用于这次受观测运行 |
| 逆推 | 只有终态结果，能否证明发生过恢复？ | 还必须有 checkpoint、注入实例丢失、连接中断和重启后继续 | 仅有终态的证据被判定不足 |
| 类比 | 观测是否与公开平台概念一致？ | 公开的 session 持久化与 protocol 责任边界 | 一致，但始终没有用空闲恢复代替活跃恢复的证据 |
| 一致性 | 结论能否跨 runtime 与 protocol 成立？ | Python / .NET 与 Responses / Invocations 配对 | workload output 连续性成立；传输事件形态不一致 |

### 9.2 数字能追溯到哪里

| 声明范围 | 公开证据 | 来源边界 |
|---|---|---|
| 7 月与 8 月的数量、区间、耗时、确认号、424 与 steering 数值 | [`historical-observations.json`](evidence/historical-observations.json) | 从捕获运行中提取的公开安全 aggregate；明确 N 和产品状态 |
| 当前公共 SDK 符号与 handler 规则 | [`public-sdk-contract.json`](evidence/public-sdk-contract.json) | 真实 installed-package probe；不是 live recovery |
| Lease、进程丢失、generation fence、checkpoint、幂等 | [`recovery-contract-demo.json`](evidence/recovery-contract-demo.json) + [JSONL events](evidence/recovery-contract-events.jsonl) | 真实本地 test fixture；不是 Foundry 服务代码 |
| 缺口、重复、终态与 424/403 错误路径 | [`observation-validation.json`](evidence/observation-validation.json) | 可执行正向与负向 fixtures |
| 场景 truth label | [`scenario-manifest.json`](evidence/scenario-manifest.json) | 区分 dynamic runtime、test fixture 与 measured architecture explainer |
| 文件完整性与复现命令 | [`manifest.json`](evidence/manifest.json) + [证据索引](evidence/README.md) | SHA-256 覆盖公开 evidence files |

原始 live 产物继续留在私有边界，因为其中包含 endpoint、任务标识、环境 metadata 和生成的 payload 文本。公开 aggregate 只含本文已披露数值；本地 JSONL 使用 synthetic workload，不含服务标识。

### 9.3 边界

- 文中所有数字都是**对应评估**（7 月战役或 8 月复测）**的观测值**，不是 benchmark、保证或 SLA。
- 本次战役进行时，该能力处于 **private preview**；此后已进入 **public preview** 并有[官方概念文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)。本仓库现在公开当前公共 API probe、可执行本地 test fixture、测试和公开安全证据，但不包含 Microsoft SDK 源码、完整部署配方、live service 凭据或私有 raw telemetry。
- 结果覆盖 7 月战役的**八个文档定义的主场景**，每个场景各有一次被接受的运行；以及 8 月复测的**四类场景**，每类场景各有一次被接受的运行。cancel、delete、deny 分支不计入。
- 文中列出的恢复路径只在所述条件下得到观测；没有评估业务领域正确性和模型质量。
- 在依据本文做设计之前，请以[官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)核对当前能力。

### 9.4 宣称“可以上生产”之前

针对某个具体 workload，至少还要完成这些：

- 多轮故障注入，并明确恢复时间目标（recovery-time objective）与失败预算；
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

项目原创内容使用 [MIT](LICENSE)。微软官方图依据 CC BY 4.0 使用，不属于 MIT License；详见 [Third-party notices](THIRD-PARTY-NOTICES.md)。
