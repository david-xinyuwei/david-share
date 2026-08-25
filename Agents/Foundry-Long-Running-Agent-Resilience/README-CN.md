# Microsoft Foundry 长任务 Agent 韧性：主动注入进程丢失的实测证据

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#评估到底跑了什么)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#实测结果)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#三种接入方式)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

本仓库回答一个问题：**运行长任务的进程突然消失后，任务能否从已保存的进度继续，而不是从头再来？** 这里提供 8 次故障注入结果、公共 SDK 检查、本地双进程演示、自动化测试和可复核证据。

该能力处于**公共预览**。所有中断都是主动注入，不是线上事故；结果只适用于文中 2026 年 7 月和 8 月的测试条件，不代表 SLA 或生产就绪。

> **Author:** 魏新宇（Xinyu Wei）

[English](README.md) | 中文

[在你自己的 Agent 里使用](#在你自己的-agent-里使用) · [实测场景](#评估到底跑了什么) · [恢复模型](#深入理解恢复如何工作) · [快速开始](#快速开始) · [证据](#证据与边界) · [官方产品文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)

---

## 在你自己的 Agent 里使用

先确定你想做哪件事：

| 你的目标 | 去哪里 | 需要 Azure 订阅吗 |
|---|---|---|
| 在自己电脑上亲眼看到进程被杀掉、同一个任务继续跑完 | [运行本地恢复实验](#运行本地恢复实验)，一条命令，约一分钟 | 不需要 |
| 把恢复能力写进自己的 Hosted Agent 代码 | 本节的六个步骤 | 只在部署时需要 |
| 复现文中实测的 Foundry 行为 | [在真实 Hosted Agent 上复现](#在真实-hosted-agent-上复现) | 需要，用非生产测试订阅 |

没有名字叫 `Resilience` 的包。恢复任务 API 位于 `azure-ai-agentserver-core` 包的 `azure.ai.agentserver.core.tasks` 模块；Responses 的恢复信号位于 `azure-ai-agentserver-responses`。按微软当前官方 sample 固定的版本安装：

`pip install azure-ai-agentserver-core==2.1.0b2 azure-ai-agentserver-responses==2.1.0b2`

然后把你的长任务写成一个任务处理函数。下面这段代码从 [`examples/resilience_handler.py`](examples/resilience_handler.py) 原样摘取，仓库检查脚本会逐字比对两处，防止它们不一致。你自己的业务逻辑替换返回值部分，其余部分才是让恢复成为可能的关键：

```python
from typing import Any, TypedDict

from azure.ai.agentserver.core.tasks import RetryPolicy, TaskContext, task


class WorkInput(TypedDict):
    payload: str


@task(name="resilience-api-usage", timeout=None, retry=RetryPolicy())
async def resilience_api_usage(ctx: TaskContext[WorkInput]) -> dict[str, Any]:
    if ctx.shutdown.is_set():
        return await ctx.exit_for_recovery()

    completed = int(ctx.metadata.get("completed_phases", 0) or 0)
    return {
        "task_id": ctx.task_id,
        "input_id": ctx.input_id,
        "entry_mode": ctx.entry_mode,
        "recovery_count": ctx.recovery_count,
        "retry_attempt": ctx.retry_attempt,
        "completed_phases": completed,
        "payload_length": len(ctx.input["payload"]),
    }
```

**光有这段代码不够。** 把它复制进项目不会自动获得恢复能力，还差三件事：

| 还需要什么 | 谁提供 | 缺了会怎样 |
|---|---|---|
| 在 Hosted Agent 上启用可恢复任务（公共预览） | 平台侧配置；代码里可用 `resilient_tasks_enabled()` 自查当前是否已启用 | 进程丢失后这次调用直接失败，不会在新进程里重新进入 |
| 一个你自己的进度存储，且能确认写入成功 | **你自己准备**，Foundry 不替你存业务进度。本仓库本地演示用 SQLite，微软官方 sample 也用独立的进度存储 | 重新进入后不知道做到第几步，只能从头再跑 |
| 客户端保存同一个 response / invocation ID 和 deadline | 你的调用方代码 | 断线后只能新建任务，拿不回原来那次的结果 |

`ctx.metadata` 只适合放少量进度标记，不是业务数据存储。本仓库离线检查的 core 2.0.0 中，`flush()` 返回并不等于写入已确认（[原因](#本仓库可直接运行不只是说明文档)）。四层配置各自负责什么，见[启用恢复需要配置四层](#启用恢复需要配置四层)。

接入自己的代码时，按下面六步：

1. **从微软官方 Hosted Agent sample 开始**，保留它固定的 package 版本，这样部署配置、身份和 endpoint 都是真实可用的，不用自己编。
2. **声明处理函数**：定义带类型的输入，用 `@task` 装饰，如上例；如果任务跨多轮对话，改用 `@multi_turn_task`。
3. **读出"我现在在哪一步"**：`ctx.entry_mode` 告诉你这次是首次执行还是恢复后重入，`ctx.task_id` 和 `ctx.input_id` 让不同进程认出同一个任务，`recovery_count` 和 `retry_attempt` 把"进程丢失"和"重试"分开计数。
4. **每完成一个阶段就保存业务进度**，写入能够确认写入成功的存储；已经记录过的阶段直接跳过。不要把 `ctx.metadata.flush()` 当成写入已确认，原因见[固定版本 SDK 的限制](#本仓库可直接运行不只是说明文档)。
5. **让付款、预订、写入和工具调用可以安全重做**（幂等），因为[最后一个进度点之后的工作可能被执行第二次](#恢复后最后一个进度点之后的工作可能重做)。
6. **在客户端保存 response 或 invocation ID 以及 deadline**，断线后继续查询同一个 ID，不要创建新任务。

验证方式和本仓库一致：在任务跑到一半时杀掉进程，只有业务输出完整、并且任务给出明确终态时，才算这次运行通过。

---

## Foundry 提供什么，应用负责什么

| Foundry / AgentServer 提供 | 应用负责 |
|---|---|
| 托管运行环境、endpoint、身份、会话和监控 | 业务输入输出格式、超时和完成标准 |
| 保存任务与输入；进程丢失后重新调用同一任务 | 记录业务进度，决定从哪里继续 |
| 保存 response 历史；支持后台轮询和断线后继续读取 | 防止支付、预订、写入或工具调用被重复执行（保证幂等） |
| 提供替代计算资源 | 保存稳定的任务标识，并处理重连和读取权限 |

**运行实例**只是当前执行代码的那一个进程。进程消失会丢失内存和连接，但不会丢失保存在进程之外的任务和进度（[官方说明](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)）。

官方文档说明平台负责什么；本仓库验证应用能否正确保存进度、防止重复执行，并在重连后确认结果完整。

**这项韧性到底解决什么问题**

它不是让两个 Agent 同时执行同一任务的 active-active 双活，而是提供**任务级恢复**：运行进程退出后，平台在替代计算资源上重新调用同一条任务记录，应用再从已经持久化的业务进度继续。

| 没有任务级恢复 | 使用任务级恢复 |
|---|---|
| 进程退出后，内存状态丢失；客户端可能重新创建第二个任务 | 替代进程重新进入同一个任务 ID，并读取原输入 |
| 客户端断线后，不知道任务是否还在运行 | 客户端保存 response/invocation ID，并继续查询同一任务 |
| 等待人工审批的任务容易被误判为已经丢失 | 已保存的任务与审批状态仍可查询 |
| 付款、预订、写入或工具调用重做时可能重复执行 | 应用通过进度点和幂等标识识别已经完成的操作 |

下文数据证明这项能力在受测场景中成立，但它不是可靠性百分比或 SLA。要形成生产信心，仍需针对自己的任务做多轮故障注入。

## 本仓库验证了什么

本次 18 阶段实测来自微软在 **2026 年 7 月 private preview 期间提供的 `resilient-research` 样例**，不是本仓库自造的任务。它是一个通用的深度研究简报任务：调用方提供一个研究主题，当次测试的具体主题和模型生成正文不公开。这个样例按固定计划分 18 个阶段完成研究：

- 第 1-4 阶段：拆解研究问题，梳理基础文献、关键研究者和历史背景；
- 第 5-9 阶段：分析最新进展、方法争议、证据质量、相关领域和未解决问题；
- 第 10-15 阶段：评估应用与采用情况、资金趋势、伦理、替代方案、风险和发展前景；
- 第 16-18 阶段：汇总结论，提出具体建议，并给出下一步路线图。

每个阶段都会调用一次模型生成该部分内容；阶段完成后，应用保存“已经完成到第几个阶段”。[当前公开的 `resilient-research` 样例](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/invocations/resilient-research) 仍属于同一类多阶段深度研究任务，但计划和默认配置已经变化。**18 是 7 月那次样例运行的阶段数，不是当前产品要求。**

它也不是 public preview 唯一的韧性样例。微软当前公开目录还提供 Invocations 的 [`resilient-approval-gate`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/invocations/resilient-approval-gate)，以及 Responses 的 [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) 和 [`resilient-steering`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-steering)。

一个研究任务预先划分为 18 个阶段，预计运行约 22 分钟。第 15 秒，第 1 个阶段完成后，我们强制结束进程 A。任务没有重新提交。进程 B 找到同一条任务记录，读取已经保存的第 1 阶段进度，继续完成第 2-18 阶段。最终，**计划中的 18 个阶段全部完成**。整次运行共记录 12,248 条事件，事件序号从 1 连续到 12,248，没有缺号，也没有重复编号。

测试的问题只有一个：进程消失后，**同一个任务**能否继续并产出完整结果。下表中的数字是观测值，不是产品评分。

| 验证内容 | 结果 | 说明 |
|---|---|---|
| 长任务恢复 | **计划中的 18 个阶段全部完成**；共记录 12,248 条事件，事件序号从 1 连续到 12,248，没有缺号或重复编号 | 进程 A 和进程 B 先后完成同一条任务记录 |
| 等待人工审批时恢复 | 从进程丢失到决定被接收 **56 秒** | 本次运行中，待审批状态和原有选项都保留下来 |
| 主机替换期间轮询 | 完成前连续收到 **29 次 `HTTP 424`** | 本次运行中，固定重试 10 次会过早放弃 |
| 场景覆盖 | **8 / 8** 到达各自终态；每个场景只跑 1 次 | 证明功能可行，不代表可靠性水平 |
| 研究任务输出 | **4 / 4** 输出完整 | 其中 1 次传输编号重置，说明验收不能只看编号 |

这些结果**不能**证明生产可用性、SLA、负载与并发能力、多区域恢复、成本或业务正确性。本仓库也不提供 Microsoft SDK 源码、完整 Agent、私有 API、原始线上日志或通用部署配方。

### 恢复模型速览

下图是**微软官方原图**，展示公开的租约恢复机制，不代表微软公开了内部服务结构。

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="微软官方的基于租约恢复模型：任务和输入身份、运行时持久化输入并取得租约、handler 运行期间续租、进程停止并放弃租约、后续进程重新取得任务记录，handler 从头重入并选择重跑或从持久化边界恢复"></div>

<p align="center"><sub><i>“Lease-based recovery of a resilient work item”</i>，来源：<a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Resilience for long-running Microsoft Foundry hosted agents</a> © Microsoft，依照 <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> 使用，未经修改。该图片<b>不属于</b>本仓库 MIT License 的授权范围。</sub></p>

### 本仓库可直接运行，不只是说明文档

| 文件或目录 | 作用 |
|---|---|
| [`examples/resilience_handler.py`](examples/resilience_handler.py) | 真实的 typed `@task` 处理函数，直接 import 并读取公共恢复上下文。 |
| [`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py) | 通过真实 decorator 加载该 handler，并生成动态 JSON 证据；执行 `--check` 不需要 Azure endpoint。 |
| [`scripts/recovery_contract_demo.py`](scripts/recovery_contract_demo.py) | 在本机演示真实的进程中断与恢复：进程 A 被强制退出后，进程 B 接管同一个任务并从已保存的进度继续；SQLite 负责保存进度并防止重复提交。 |
| [`scripts/verify_public_resilience_api.py`](scripts/verify_public_resilience_api.py) | 检查当前安装的 Azure SDK 是否包含本文依赖的 18 项公开接口与处理规则。 |
| [`scripts/validate_observations.py`](scripts/validate_observations.py) | 检查运行记录是否有事件缺口、重复结果或缺少明确终态；遇到无法确认含义的 `424` / `403` 时停止并报错。 |
| [`scripts/validate_repo.py`](scripts/validate_repo.py) | 一键检查中英文结构、证据文件与校验值、代码和测试是否完整；任何一项不通过都会返回错误。 |
| [`tests/`](tests/) | 12 项自动化测试，覆盖正常恢复、异常输入、时序问题、重复执行和拒绝路径。 |
| [`evidence/`](evidence/) | 保存可供程序读取的实验结果、事件日志、证据分类和 SHA-256 校验清单，便于复核与复现。 |

下面每个文件都直接使用了公共 SDK，或有意不使用：

| 代码位置 | 直接使用的 SDK 能力 |
|---|---|
| [`examples/resilience_handler.py`](examples/resilience_handler.py) | import `RetryPolicy`、`TaskContext` 和 `task`；注册 `@task(name="resilience-api-usage")`；读取任务/输入 ID、`ctx.metadata`、进入模式和恢复/重试次数；收到关闭信号时调用 `ctx.exit_for_recovery()` |
| [`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py) | import 该 handler，通过真实 decorator 完成注册，并写出 `resilience-sdk-usage.json` |
| [`scripts/verify_public_resilience_api.py`](scripts/verify_public_resilience_api.py) | import 同一组任务类型，以及 `TaskMetadata` 和 Responses 恢复信号；检查当前安装包是否提供本文依赖的接口 |
| [`scripts/recovery_contract_demo.py`](scripts/recovery_contract_demo.py) | **不 import Azure SDK**；它只用 SQLite 和两个本地进程验证恢复算法 |
| [微软官方可部署的 `resilient-research` 处理函数](https://github.com/microsoft-foundry/foundry-samples/blob/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/invocations/resilient-research/src/resilient-research/agent.py#L246-L285) | 在完整 sample 中使用 `@multi_turn_task`、`TaskContext`、`ctx.metadata` 和流式事件存储 |

`--check` 只证明当前软件包可以 import，且真实装饰器接受并注册了这个带类型标注的处理函数。它**不会**执行处理函数正文，也不能证明线上恢复；正文只有进入 Hosted Agent runtime 后才会执行。

**固定版本 SDK 的限制：** 在 core 2.0.0 中，`await ctx.metadata.flush()` 返回并不等于“持久化已经确认成功”，因为底层存储回调失败时只记录日志，不会把异常抛回处理函数。因此，这个示例只读取 `metadata`，不把 `flush()` 写成已确认持久化的进度点。生产代码需要能够确认写入成功的持久化路径，或准备运维对账；当前微软公开 sample 也使用独立的进度存储保存进行中的正文。

---

## 深入理解：恢复如何工作

要实现恢复，**任务 ID、输入和已完成进度必须保存在当前执行进程之外**。这样，原进程退出后，替代进程仍能找到同一条任务记录，读取最近一次保存的进度，并继续未完成的阶段。

恢复流程分为三步：

1. 执行开始前，平台保存任务 ID 和输入。
2. 每完成一个可以确认的业务阶段，应用就在执行进程之外保存“最新完成到哪个阶段”。
3. 原进程退出后，替代进程读取同一条任务记录，从下一个未完成阶段继续。

客户端重连只负责继续读取状态和结果，不会触发任务恢复。实测中，客户端重连之前，进程 B 已经开始继续执行。

### 先说明三个概念

- **任务记录：** 保存在执行进程之外，用同一个任务 ID 标识同一个任务；替代进程接手后，任务 ID 不变。
- **进度点（checkpoint）：** 应用已经确认完成并保存的最新业务阶段。
- **状态读取端（observer）：** 负责查询状态和读取结果的客户端或运维程序；它断开后，任务仍可继续运行。

### 恢复后，最后一个进度点之后的工作可能重做

恢复时，系统会重新调用处理函数（handler）的入口，而不是从中断的代码位置、模型调用、工具调用或旧连接处继续。因此，最近一次已保存进度之后的工作可能再次执行。

应用必须识别已经完成的付款、预订、写入或工具调用，并跳过重复操作。恢复不会创建一个新任务；Agent 显示 `active` 只代表部署成功，不代表恢复已经发生。

### 三种接入方式

三种接入方式的区别，是应用需要自己负责多少。

| 层级 | 平台负责 | 你仍然要负责 | 适用场景 |
|---|---|---|---|
| Foundry 上的 Microsoft Agent Framework | 在 Responses 之上的更高层封装，生命周期大多已代为处理 | 配置、保存进度、防止外部操作重复 | 希望少写生命周期代码的团队 |
| Responses protocol | 对话历史、流式输出、后台执行、轮询和取消 | 开启恢复、保存进度、检查输出完整 | 对话型和工具型 Agent |
| Invocations protocol | 传输和基础接口 | 自己定义任务、事件、进度、轮询和恢复 | 结构化流程和自定义协议 |

无论使用哪种框架，应用都必须定义“哪些步骤已经完成”。

### 官方恢复机制与本地示例

官方文档说明任务如何被保存、租约如何过期、另一个进程如何接管，以及应用为什么要保存进度。本仓库用 SQLite 做了一个可运行示例；其中的版本保护和原子提交是**示例自己的设计**，不代表 Foundry 内部实现。

| 关注点 | 官方公开契约 | 本仓库可执行参考实现 |
|---|---|---|
| 任务和输入 | 平台保存任务身份与输入 | SQLite 保存任务记录和输入校验值 |
| 接管条件 | 进程停止续租后，另一个进程可以接管 | 保存 owner、过期时间和版本号；只允许符合条件的接管 |
| 业务进度 | handler 重新进入后，由应用读取已保存进度 | 在一个事务中同时保存阶段结果和进度点 |
| 防止重复 | 应用负责避免外部操作重复 | 相同结果自动去重；内容冲突立即报错 |
| 查看输出 | 客户端可以断线后继续读取，但传输位置不是业务进度 | 检查事件是否连续、输出是否齐全、终态是否明确 |

#### 本地恢复演示程序

[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) 只使用 Python 标准库。进程 A 完成第 1 阶段后通过 `os._exit(9)` 退出；租约过期后，进程 B 接管并完成第 2-5 阶段。程序生成 [JSON 结果](evidence/recovery-contract-demo.json) 和 [JSONL 事件日志](evidence/recovery-contract-events.jsonl)。

它测试四条规则：只能接管未运行或租约已过期的任务；旧进程不能在接管后继续写；重复提交相同结果会去重、冲突结果会报错；阶段结果与进度在同一个事务中保存。

这是本仓库的**本地测试程序**，不是 Foundry 服务代码，也不能单独证明线上恢复。

### 启用恢复需要配置四层

要让一次调用能够恢复，需要四层同时配好；其中进程和处理函数两层仍是**公共预览中的实验性接口**。

| 层次 | 需要配置 | 能做什么 | 仍需应用负责 |
|---|---|---|---|
| Hosted Agent version | `host: azure.ai.agent` + Responses protocol | 部署代码并提供 endpoint | 这一步本身不负责崩溃恢复 |
| Agent 进程 | 启用 Resilient task（可恢复任务） | 进程丢失后重新调用同一任务 | 不知道业务做到哪一步 |
| Handler | `TaskContext` + framework checkpoint | 读取和保存业务进度 | 不能自动防止外部操作重复 |
| 客户端 | `store=True`、`background=True`、保存同一 `response.id` | 后台运行、轮询和重连 | 不能新建 response 来冒充恢复 |

#### 从官方 Responses 样例开始

不要从缺少 project、模型和身份的不完整 `azure.yaml` 开始。直接使用[官方可部署 sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents)，再按 sample 当前版本开启恢复。`azd deploy` 负责部署；它不会替应用保存业务进度。

#### 开启进程恢复

开启预览恢复后，已保存的后台 response 不会因进程丢失直接失败，而会在新进程中重新调用处理函数。公开软件包已提供相应接口，但仍标记为实验性；完整清单见 [SDK 检查报告](evidence/public-sdk-contract.json)。

#### 从已保存的业务进度继续

重新进入 handler 后，应用要读取最后一个进度点。进程死在进度点之前，该阶段可能重做；进度点之后已经保存的阶段应被跳过。

| 应用需要知道什么 | 公开 API（`azure-ai-agentserver-core` 2.0.0） |
|---|---|
| 当前是哪一个任务和输入 | `TaskContext.task_id`、`TaskContext.input_id` |
| 这是首次进入还是恢复进入 | `TaskContext.entry_mode` |
| 恢复与普通重试分别发生了几次 | `recovery_count`、`retry_attempt` |
| 保存少量进度信息 | `TaskContext.metadata` |

本次恢复报告 `recovery_count=1`、`retry_attempt=0`。

应用只需遵守四步：读取任务身份和已保存进度；重建状态；执行一个可安全重复的阶段；保存结果和外部操作标识后，再推进 checkpoint。支付、预订、写入和工具调用仍须[防止重复](#审批决定和外部操作都要防重复)。

#### 分开处理任务创建与状态查询

本仓库测试本地进度存储和结果校验。真实认证调用使用[官方 Hosted Agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)；本仓库不虚构你的 endpoint、身份、存储或业务格式。

| 问题 | 应用应怎么做 |
|---|---|
| 创建请求后、保存 response ID 前进程崩溃 | 结果未知时不要自动重建任务。远端 create 与本地保存 ID 不是一个原子事务，当时测试的 API 也不支持按应用自己的任务标识反查；生产系统需要去重能力或人工对账。 |
| 轮询进程崩溃 | 预先保存 `response_id` 和 deadline；新进程继续读取**同一个 response**。 |
| 从哪里继续读取 | 以 `response_id` 和业务状态为准，不以传输编号为准；一次实测的编号曾从 5 重新开始。 |
| 后续轮次 | `previous_response_id` 只连接顺序轮次；并发排队和 steering 需要 resilient-task 接口。 |
| 谁可以读取 | 只读 adapter **不是**权限隔离机制（安全沙箱或 RBAC 边界）。不可信读取端需要独立服务和身份；平台显示完成后，仍要检查业务结果。 |

普通调用可用 `azd ai agent invoke`。需要保存后台任务 ID、重启轮询或检查业务终态时，使用应用自己测试过的 client。

---

## 评估：到底跑了什么

上面所有内容，在经受一次主动注入的中断之前都只是设计主张。下面是验证方式。

### 当前 public-preview 契约检查

7 月测试使用的是 private preview 构件，因此“快速开始”还会在干净的 Python 3.13 环境中检查当前公开软件包。固定版本的 `core` 2.0.0、`invocations` 1.0.0 和 `responses` 2.0.0 共 **18 / 18 项通过**；版本与每项检查见 [JSON 报告](evidence/public-sdk-contract.json)。

这只能证明已安装的公共接口符合预期，不能证明线上恢复。任何一项失败都会返回非零退出码。

### 在当前构件上复测（2026 年 8 月）

当前公开构件上，曾开通过预览的订阅对 `/tasks`、`/agents` 和 `/assistants` 都返回 `200`。随后运行一个 18 阶段的本地任务：进程 A 在第 1 阶段后被强制退出，进程 B 接管同一任务：

| 复测观测项 | 数值 |
|---|---|
| 注入进程丢失之前提交的阶段 | 18 个中的 1 个 |
| 恢复之后由另一个进程提交的阶段 | 18 个中的 17 个 |
| 序列连续性 | 1-18，无缺口，无重复 |
| 跨进程的任务身份与输入身份 | 完全一致 |
| 第二个进程报告的 `entry_mode` | `recovered` |
| 恢复时的 `recovery_count` / `retry_attempt` | `1` / `0` |
| 接管间隔 | 1.93 秒 |

`recovery_count=1`、`retry_attempt=0` 说明恢复与 handler 重试是两件事。各阶段只用了人为等待，没有模型推理，因此 1.93 秒不是性能数据。这仍是本地双进程测试，不是线上 Hosted Agent 证据。

### 在普通订阅上，验证真实部署的 Agent

下一项使用官方韧性样例部署真实 Hosted Agent，并在任务仍在运行时替换运行实例。本次没有申请新白名单或注册功能开关。

| 复测场景 | 样例 | 中断于 | 结果 |
|---|---|---|---|
| Responses，流式恢复 | `resilient-streaming` | 22.6 秒 | **PASS**——同一 response id，3 个 item，无缺口无重复 |
| Responses，steering | `resilient-steering` | 23.3 秒 | **PASS**——同一 response id 给出完整答案 |
| Invocations，research 恢复 | `resilient-research` | 28.4 秒 | **PASS**——同一 `invocation_id` 走到 `completed` |
| Invocations，替换实例期间等待审批 | `resilient-approval-gate` | 25.3 秒 | **PASS**——替换完成后发送的决定仍被接收（`202`），任务完成 |

三点需要单独说明：

- 同一 streaming 场景也在一个从未开通过预览的订阅上通过（`azd up` 3 分 29 秒）。这只代表该订阅，不代表所有订阅或区域。
- 7 月的 `424` 现象没有复现：本轮 26 次轮询全部是 `200`。两次中断路径不同，因此两个结果都只适用于各自运行。
- 新的线上复现应使用官方 sample 当前固定的 `core==2.1.0b2` 和 `responses==2.1.0b2`；本仓库的 2.0.0 只用于历史离线检查。

这些是强制替换运行实例，不是计划外主机崩溃。四类当前 sample 各跑 1 次；7 月的 .NET 场景没有重跑。

7 月 22-23 日的矩阵在 Canada Central 的同一个 project 中运行，覆盖 Python/.NET 与 Responses/Invocations；每个主场景只跑 1 次（**N=1**）。只有同一任务在中断后产出完整结果并到达明确终态才算通过；部分恢复、重连后卡住或重新跑一个相似任务都不算。

| # | Runtime / protocol | 场景与中断 | 必须满足的终态证据 | 结果 |
|---|---|---|---|---|
| 1 | Python / Invocations | Research；运行实例丢失 | 恢复标记、phase 1-18、任务完成 | **PASS** |
| 2 | Python / Responses | Research；运行实例丢失 | 同一 response、output index 0-17、共 18 项 | **PASS** |
| 3 | .NET / Invocations | Research；运行实例丢失 | 恢复标记、phase 1-18、任务完成 | **PASS** |
| 4 | .NET / Responses | Research；运行实例丢失 | 同一 response、output index 0-17、共 18 项 | **PASS** |
| 5 | Python / Invocations | 审批；挂起期间运行实例丢失 | 重启后决定生效，确认号 `TRIP-182336` | **PASS** |
| 6 | Python / Responses | 审批；挂起期间运行实例丢失 | 恢复 lifecycle，确认号 `TRIP-749637` | **PASS** |
| 7 | Python / Responses | 持久化工作流；主机替换 | 法语、西班牙语、回译输出完整 | **PASS** |
| 8 | Python / Responses | Steering；主动打断 | 第二轮排队、第一轮安全结束、第二轮完成 | **PASS** |

可选的 cancel、delete、deny 分支不在这个矩阵里，本文也没有验证它们。

---

## 实测结果

### 一次跨越主动注入进程丢失的 21.7 分钟运行

Python Invocations 运行在 15 秒内完成第 1 阶段并产生 599 条事件，随后进程被强制终止。没有重新提交；重连后，同一任务从第 600 条事件继续，并完成第 2-18 阶段。

整次运行用时 1,301 秒，**计划中的 18 个阶段全部完成**。共记录 12,248 条事件，事件序号从 1 连续到 12,248，没有缺号或重复编号。约 95% 的耗时和事件发生在进程丢失之后；这是工作分布，不是成功率。

### 换一种 protocol，同样的中断

`Python / Responses` 运行在中断前产出第 0 项结果。经过 **47 秒**重连，同一个 response 继续产出第 1-17 项并完成。

全程共 11,584 条事件，没有缺失或重复的 output index。这支持“本次运行继续了同一个 response”，但不代表所有 Responses 任务都有相同行为。

### 人工审批等待期间注入运行实例丢失

<div align="center"><img src="images/approval-recovery-cn.png" width="820" alt="审批场景实测时间线：从运行实例丢失到决定被接收共 56 秒"></div>

工作流当时停在审批点，**没有应用步骤正在运行**。12:24:27 替换运行实例后，审批决定在 **56 秒**后被接收；Agent 保留了原来的选项并返回 `TRIP-182336`。同一模式的 Responses 运行返回 `TRIP-749637`。

> 这些是确定性的示例工具。确认号支持以下结论：在这些运行中，持久化 Graph 状态与一次审批应用跨越了进程替换；它们不能证明通用的 exactly-once 保证，也不代表真实的航班或酒店预订。

### 完成前收到的 29 次 `424`

主机替换期间，同一个 response **连续 29 次**返回 `HTTP 424 Failed Dependency`，之后仍完成了预期的法语、西班牙语和回译结果。固定重试 10 次会过早放弃。

这**不代表所有 `424` 都能重试**。只有确认正在替换主机、且原 response 仍可查询时，才应先判断状态，再决定是否停止。

### 主动打断

第一轮仍在生成时，第二轮请求被接收为 `queued`。第一轮在最近一个已保存的完整步骤之后停止；第二轮经过 7 次 `in_progress` 轮询后完成。这是协作式 steering，不是取消和重启之间的竞速。

---

## 验收看任务结果，不只看传输编号

四次研究任务中，三次传输编号在重连后继续递增；一次 `.NET / Responses` 运行**从 5 重新编号**，但同一个 response 仍交付了第 1-17 项完整输出。

| 运行方式 | 中断前 | 重连后 | 结论 |
|---|---|---|---|
| Invocations / Python | 编号 1-599 | 编号 600-12,248 | 编号连续 |
| Responses / Python | output 0 | output 1-17 | 输出完整 |
| Invocations / .NET | 编号 1-738 | 编号 739-12,073 | 编号连续 |
| Responses / .NET | output 0 | output 1-17 | 输出完整，但传输编号从 5 重新开始 |

验收应检查 output index、阶段编号和已保存状态。传输编号只用于诊断；而且“递增”也不等于“无缺口”——`10, 12` 仍然缺少 11。

---

## 自动检查与客户端规则

[`validate_observations.py`](scripts/validate_observations.py) 把下面的规则做成了可执行检查；[JSON 报告](evidence/observation-validation.json) 同时记录通过与失败用例。

### 同时拒绝缺口和重复

`sequence == sorted(sequence)` 只能证明顺序，不能发现缺口或重复。正确检查要逐项比较相邻编号，并核对完整的预期输出范围。

| 反例 | 原排序检查 | 修复后的检查 |
|---|---:|---:|
| 丢事件：`[10, 12]` | `True` | `False` |
| 重复事件：`[10, 10, 11]` | `True` | `False` |
| 干净事件流：`[10, 11, 12]` | `True` | `True` |

对输出编号也采用同样规则：缺少或重复都失败。只输入已经完成的结果项；同一个结果项的多个流式增量会共用同一编号，不能当成重复结果。

### 一个 `done` 帧不能证明成功

流结束可能代表成功、取消、失败，也可能只是连接断开。`completion_is_proven` 同时要求服务状态、明确终态和预期阶段数；单独一个 `{"type": "done"}` 不算成功。

### 把 `424` 和 `403` 分开处理

`424` 只有在“同一任务仍可查询且已确认正在替换主机”时才继续有界轮询；信号不足就停止。`403` 应先检查读取身份和权限，确认凭据过期后再刷新。停止时间由任务 deadline 决定，不要用随手设定的固定次数。

### 审批决定和外部操作都要防重复

恢复后，同一条审批消息可能再次送达。本地 SQLite 记录阶段结果、去重标识和进度：相同消息再次到达时跳过，内容冲突时立即报错。真实支付、预订或写入接口也必须识别同一个去重标识，否则仍可能执行两次。

---

## 快速开始

**需要：** Git 和 Python 3.13。本地实验不需要 Azure 订阅或凭据。Windows 请放在 `$HOME\lra-work` 这类短路径下；命令可直接用于 PowerShell、Bash 或 zsh。如果系统只有 `python3`，把命令中的 `python` 换成 `python3`。

### 运行本地恢复实验

```console
git clone --depth 1 --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git lra-demo
git -C lra-demo sparse-checkout set Agents/Foundry-Long-Running-Agent-Resilience
cd lra-demo/Agents/Foundry-Long-Running-Agent-Resilience

python scripts/recovery_contract_demo.py demo --summary-file .demo-state/summary.json --events-file .demo-state/events.jsonl
```

**完成标准：** 命令正常结束（exit code `0`）；结果中有 `"passed": true`、`worker_a_exit_code: 9`、`entry_modes: ["fresh", "recovered"]` 和阶段 `1-5`。这表示进程 A 被真实终止后，另一个进程 B 接手并完成任务。

### 测试与仓库检查

Windows PowerShell：

```powershell
python -m venv .venv
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install --no-input -r requirements-validation.txt
& $python examples\resilience_sdk_usage.py --check
& $python scripts\verify_public_resilience_api.py --quiet
& $python scripts\validate_observations.py self-test
& $python -m unittest discover -s tests -v
& $python scripts\validate_repo.py
```

Linux / macOS：

```bash
python3 -m venv .venv
PYTHON=.venv/bin/python
"$PYTHON" -m pip install --no-input -r requirements-validation.txt
"$PYTHON" examples/resilience_sdk_usage.py --check
"$PYTHON" scripts/verify_public_resilience_api.py --quiet
"$PYTHON" scripts/validate_observations.py self-test
"$PYTHON" -m unittest discover -s tests -v
"$PYTHON" scripts/validate_repo.py
```

**完成标准：** 看到 `PASS: imported azure.ai.agentserver.core.tasks`、`18/18 checks passed`、`Ran 12 tests ... OK` 和 `PASS: bilingual parity ... Data/Log Rich ... Code/Test Rich`。这些命令只检查 SDK 和本仓库，不会调用线上 Hosted Agent。

### 在真实 Hosted Agent 上复现

本地命令只证明本仓库的恢复逻辑可运行，**不能证明 Foundry 线上服务**。线上复现请从微软官方样例开始：

1. 安装 Azure CLI 与 `azd`，登录非生产测试订阅；
2. 获取官方 [`resilient-streaming` Hosted Agent 样例](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming)；
3. 按样例自己的部署与调用说明操作。本文核验的 commit [`3d734b9`](https://github.com/microsoft-foundry/foundry-samples/blob/3d734b93b66f163bea9886d73c6808adc32e68fc/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming/src/resilient-streaming/requirements.txt) 使用 `core==2.1.0b2` 和 `responses==2.1.0b2`；**不要**改成本仓库历史离线检查使用的 2.0.0；
4. 在 background response 仍为 `in_progress` 时替换运行实例；
5. 继续查询同一个 response ID，确认所有预期输出都存在。

**完成标准：** 同一个 response ID 恢复，预期输出完整，并有明确终态。只有 Portal 图表或一个 `completed` 字符串不够。

---

## 故障判断与恢复速查表

<div align="center"><img src="images/recovery-decision-guide-cn.png" width="560" alt="恢复前的判断流程：区分运行实例、客户端、主机替换和观察者故障"></div>

下面每一行只是诊断起点，不表示“某个现象必然对应某个原因”。**先读取同一条任务记录，再根据已保存的状态判断问题出在哪一层；状态没有查清之前，不要创建新任务。**

| 现象 | 先确认 | 不要做 | 更安全的做法 |
|---|---|---|---|
| 流停止，没有终态 | 查询同一个任务；问题可能在客户端、网络或运行实例 | 重新提交 | 任务仍存在时重新接回，并检查输出完整和明确终态 |
| 任务停在审批 | 确认挂起任务仍然存在 | 重建审批 | 找回同一任务，再发送决定 |
| 同一 response 反复返回 `424` | 确认正在替换主机，且 response 仍可查询 | 把所有 `424` 都当成终态或都当成可重试 | 对同一 response 做有上限的退避轮询 |
| 读取返回 `403` | 检查读取身份和权限 | 重跑任务 | 只在确认凭据过期后刷新，再重试读取 |
| 日志突然结束 | 直接查询服务端保存的状态 | 用最后一行判断失败 | 重新采集，或直接读取终态 |
| 运行中收到新指令 | 检查是否启用了 steering | 强杀当前轮次并启动新任务 | 通过 steering 排队，或使用已定义的取消策略 |

---

## 设计建议

下面是工程建议，不是产品保证：

1. **在可核实的位置保存进度。** “18 个阶段完成到第 7 个”有用；“大概跑到中间”没用。
2. **把任务 ID 和已完成进度保存在执行进程之外。** 替代进程必须能找到同一条任务记录，并从最近的进度点继续。
3. **按可能重复执行来设计。** 付款、审批、写入和工具调用再次发生时必须安全。
4. **把读取故障和任务故障分开，并要求明确终态。**
5. **先对照已保存状态判断错误码，再决定动作。**
6. **区分挂起和运行中任务。** 等待审批时释放计算资源，不等于任务丢失。

---

## 证据与边界

### 这些结论是怎么被挑战的

| 方法 | 证据 | 结论 |
|---|---|---|
| 同一任务还是重新跑的？ | 同一 response 在中断前产出 0，中断后产出 1-17 | 排除“新任务重跑” |
| 是否只挑了好看的样例？ | 预先固定 8 个主场景 | 8/8 通过；排除项明确列出 |
| 恢复是否必须依赖编号连续？ | 一次 .NET 运行从 5 重新编号，但结果完整 | 验收应看任务结果 |
| 只有终态能否证明恢复？ | 还要求进度点、注入中断、断线和中断后继续 | 只有 `completed` 不够 |

### 数字能追溯到哪里

| 声明范围 | 公开证据 | 来源边界 |
|---|---|---|
| 7 月与 8 月的数量、区间、耗时、确认号、424 与 steering 数值 | [`historical-observations.json`](evidence/historical-observations.json) | 从实测运行中提取、已脱敏的汇总数据；标明 N 和产品状态 |
| 当前公共 SDK 符号与 handler 规则 | [`public-sdk-contract.json`](evidence/public-sdk-contract.json) | 真实的已安装包探测；不是线上恢复 |
| 直接 import SDK 并注册 `@task` | [`resilience-sdk-usage.json`](evidence/resilience-sdk-usage.json) | 由示例自己的 `--check` 生成；不代表 handler 正文已执行，也不是线上恢复 |
| 租约、进程丢失、版本保护、进度点和防重复 | [`recovery-contract-demo.json`](evidence/recovery-contract-demo.json) + [JSONL 事件](evidence/recovery-contract-events.jsonl) | 真实的本地测试程序；不是 Foundry 服务代码 |
| 缺口、重复、终态与 424/403 错误路径 | [`observation-validation.json`](evidence/observation-validation.json) | 可执行的正向与负向测试用例 |
| 场景类型标注 | [`scenario-manifest.json`](evidence/scenario-manifest.json) | 区分动态运行、测试程序与实测架构说明三类内容 |
| 文件完整性与复现命令 | [`manifest.json`](evidence/manifest.json) + [证据索引](evidence/README.md) | SHA-256 覆盖公开证据文件 |

原始线上材料包含 endpoint、任务标识、环境信息和生成文本，因此不公开。公开证据只保留本文已披露的数值；本地 JSONL 使用合成数据。

### 边界

- 所有数字都是 7 月或 8 月某次运行的观测值，不是 benchmark、保证或 SLA。
- 7 月 8 个主场景和 8 月 4 类样例都只跑 1 次；cancel、delete、deny 没有测试。
- 能力已从 private preview 进入 public preview。设计前请查看[最新官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)。

### 宣称“可以上生产”之前

针对具体任务，至少还要完成：

- 多轮故障注入，并明确恢复时间目标和失败预算；
- 对每个写入、审批、支付、预订和工具调用做防重复测试；
- 做负载、并发和重叠轮次测试；
- 明确超时、取消、保留、删除和失败任务处理策略；
- 监控能够区分运行实例、任务、读取端和身份故障；
- 按目标区域、运行时和协议核对最新官方文档。

---

## 相关工作

| Repository | 关系 |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | 更完整的 build、deploy、operate 生命周期 |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted agent 的 tools、memory 与 skills |
| [Foundry-Agent-ModelOps-Governance](../Foundry-Agent-ModelOps-Governance/) | Operational-plane 边界梳理 |

## License

项目原创内容使用 [MIT](LICENSE)。微软官方图依据 CC BY 4.0 使用，不属于 MIT License；详见 [Third-party notices](THIRD-PARTY-NOTICES.md)。
