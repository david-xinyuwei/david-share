# Microsoft Foundry Hosted Agent 进程丢失后如何恢复

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-repository_owned_agent-1363DF)](#一次完整的恢复运行)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_3.13_%2B_.NET_8-0F8B6D)](#故障矩阵)
[![Protocol](https://img.shields.io/badge/protocol-Responses_%2B_Invocations-5F4BB6)](#把同样的接线放进你的-agent)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

本仓库包含真实的 Hosted Agent、客户端、故障运行器和证据。它只回答一个问题：**Agent 进程消失后，同一个已保存响应如何由新进程继续，而且不丢失已经写入检查点的输出？**

**四种打断在演示台上的实录，双倍速，2:52。这段视频是可视化过程；可审计的证据在下文。**

https://github.com/user-attachments/assets/d548d973-57d4-46e5-bfcd-b85142be9a6f

[下载仓库里的副本](https://github.com/david-xinyuwei/david-share/raw/refs/heads/master/Agents/Foundry-Long-Running-Agent-Resilience/media/lra-interruption-demo-2x.mp4?download=1)

> **Author:** 魏新宇（Xinyu Wei）

[English](README.md) | 中文

[四个场景](#在浏览器里看完整过程) · [一次完整运行](#一次完整的恢复运行) · [故障矩阵](#故障矩阵) · [复现](#自己复现) · [接入自己的 Agent](#把同样的接线放进你的-agent) · [证据](#证据与边界) · [官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)

## 先看这里

这里不是“把旧进程重新启动”。客户端只创建一个已保存的后台响应。进程 A 写入检查点后退出。进程 B 带着空的进程内存启动，从持久化存储中找到同一个响应和输入，以 `is_recovery=True` 重新进入处理函数，加载已经保存的响应快照，再从下一个检查点继续。客户端始终轮询原来的响应 ID。

本仓库围绕四种打断组织，[浏览器完整过程](#在浏览器里看完整过程)把它们连起来展示：安全基线、进程硬丢失、调用方断线、等人审批时实例丢失，以及恢复之后临时换目标语言。每个场景跑的都是真实长任务，不是 sleep 循环：Agent 逐段调用 Azure Translator S1，每完成一段就写检查点。录像是这四种打断的可视化过程；下文各节保存每一种打断经机器校验的已提交证据，本 README 里的每个实测时长都来自这些证据文件，而不是来自录像。

紧接着记录的那次运行把这套机制写到每个细节：12 段英文，第 4 段后进程 A 丢失，进程 B 从第 5 段继续，最终返回完整 12 段文档，而且终态是 `completed`。两次运行分别证明不同部分。本机 AgentServer 运行给出操作系统观察到的精确 down 时间；Foundry Version 7 运行证明 Hosted 产品中的替代计算恢复，整次运行耗时 `89.199` 秒。同样的硬退出合同也在本仓库自有 .NET handler 上通过。这些是公共预览能力证据，不是 SLA 或生产就绪声明。

转向 Agent 和审批 Agent 把同一份任务扩成 30 段，承担最后两种打断；详见[同一份任务再经受两种打断](#同一份任务再经受两种打断)。

## 一次完整的恢复运行

### Agent 到底在哪里接入 LRA

| 必需接线 | 本仓库真实代码 | 它改变了什么 |
|---|---|---|
| 导入 AgentServer 恢复 API | [`main.py`](hosted-agent/src/lra-evidence-agent/main.py#L16-L24) | 使用公共 task 和 Responses 软件包 |
| 服务端开启崩溃恢复 | [`ResponsesServerOptions(resilient_background=True)`](hosted-agent/src/lra-evidence-agent/main.py#L49-L52) | 已保存的后台响应可以在进程丢失后重新调用 |
| 开启启动恢复扫描 | [`set_resilient_tasks_enabled(True)`](hosted-agent/src/lra-evidence-agent/main.py#L52) | 新进程启动时扫描可恢复任务 |
| 创建已保存的后台任务 | [`store=True`、`background=True`](hosted-agent/client.py#L197-L223) | 请求和响应身份不依赖原始连接 |
| 载入持久化快照 | [`context.persisted_response`](hosted-agent/src/lra-evidence-agent/main.py#L170-L175) | 恢复后的处理函数从已写入检查点的输出继续 |
| 提交一个持久化边界 | [`yield stream.checkpoint()`](hosted-agent/src/lra-evidence-agent/main.py#L202-L228) | 该调用之前的输出可以跨进程保留 |
| 注入真实硬退出 | [`os._exit(86)`](hosted-agent/src/lra-evidence-agent/main.py#L240-L256) | 进程 A 不做正常清理，直接退出 |
| 始终查询同一任务 | [`state_file` 和 `validate_terminal_response`](hosted-agent/client.py#L339-L387) | 客户端重启不会创建替代任务 |

这里没有一个单独叫 `LRA` 的包。Python 从 `azure-ai-agentserver-*` 导入 resilient task 和 Responses 类：

```python
from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
from azure.ai.agentserver.responses import (
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)

app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(resilient_background=True)
)
set_resilient_tasks_enabled(True)

# 在 response handler 里：
stream = (
    ResponseEventStream(
        response_id=context.response_id,
        response=context.persisted_response,
    )
    if context.is_recovery and context.persisted_response is not None
    else ResponseEventStream(response_id=context.response_id, request=request)
)
# 先输出一个完整、可安全重放的工作单元，然后：
yield stream.checkpoint()
```

.NET 从对应 NuGet namespace 导入类型，并打开相同能力：

```csharp
using Azure.AI.AgentServer.Core;
using Azure.AI.AgentServer.Responses;

var builder = AgentHost.CreateBuilder(args);
builder.AddResponses<LraEvidenceHandler>(
    options => options.ResilientBackground = true);

// 在 CreateAsync 里：
var stream = context.IsRecovery && context.PersistedResponse is not null
    ? new ResponseEventStream(context, context.PersistedResponse)
    : new ResponseEventStream(context, request);
yield return stream.Checkpoint();
```

可部署 Python 包的固定版本见 [`requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt)；.NET 包版本见 [`LraEvidenceAgent.csproj`](dotnet-agent/LraEvidenceAgent.csproj)。

### 真实长任务到底做什么

[`translation_workload.py`](hosted-agent/src/lra-evidence-agent/translation_workload.py) 定义 12 段可公开英文材料。对每一段，[`main.py`](hosted-agent/src/lra-evidence-agent/main.py#L67) 都通过托管身份取得令牌、调用真实 Azure Translator S1 REST endpoint、输出中文结果，然后才执行 `yield stream.checkpoint()`。

故障请求设置 `crash_after_stage=3`，所以进程 A 写完 `translation_section_04` 后调用 `os._exit(86)`。进程 B 从 `persisted_response` 恢复四个输出项；因此 `_output_count` 返回 `4`，循环从 `translation_section_05` 开始，不会再次翻译第 1-4 段。除非同时出现 12 个顺序正确的段记录、源文本哈希、非空译文、两个进程身份、`fresh + recovered` 和原响应的 `completed` 终态，否则验收会拒绝该运行。

最终线上结果不是一个状态字：[破坏后完成的完整译文](evidence/owned-hosted-agent-live-translation-output.md)同时列出 12 段英文输入和 12 段 Translator 原始结果。它证明完成和恢复，不代表人工翻译质量评测。

![进程 A 到进程 B 的精确恢复时间轴，包含实际请求、故障注入、时间戳、检查点连续性和 completed 终态](images/lra-recovery-timeline.png)

图中主时间轴使用下面的本机精确时间，底部同时写明线上 Foundry 证明边界。[打开可缩放 SVG](images/lra-recovery-timeline.svg)或[编辑 Excalidraw 源文件](images/lra-recovery-timeline.excalidraw)。

### 什么时候 down、什么时候恢复、什么时候完成

下表直接来自真实 S1 运行 [`owned-hosted-agent-translation-local.json`](evidence/owned-hosted-agent-translation-local.json)。时间为 UTC+8；JSON 中保留 ISO 时间、完整验收结果和脱敏事件日志。

| 事件 | UTC+8 | 已运行 | 进程 | 发生了什么 | 事件后的持久化状态 |
|---|---|---:|---|---|---|
| 进程 A 启动 | 18:25:29.748 | 0.021 秒 | A | AgentServer 带恢复能力和 Translator 凭据启动 | 还没有请求 |
| 创建响应 | 18:25:31.601 | 1.875 秒 | A | 客户端发送一个 `store=true`、`background=true`、`translator_batch` 请求 | 输入和响应身份已经持久化 |
| 第 4 段检查点 | 18:25:44.638 | 14.911 秒 | A | 第四个真实 S1 结果完成，`stream.checkpoint()` 返回 | 中文结果 1-4 已经持久化 |
| 注入故障 | 18:25:44.638 | 14.911 秒 | A | handler 记录持久化边界后调用 `os._exit(86)` | 检查点保留；进程内存可以丢弃 |
| **进程真正 down** | **18:25:45.176** | **15.452 秒** | A | 操作系统报告退出码 `86` | 当前没有 Agent 进程运行 |
| 进程 B 启动 | 18:25:45.190 | 15.466 秒 | B | 新的空进程打开同一 AgentServer 状态 | 原响应仍然可以查询 |
| **观察到恢复** | **18:25:46.591** | **16.864 秒** | B | handler 以 `recovered` 进入，响应哈希不变 | 从 `translation_section_05` 继续 |
| 恢复后第一个检查点 | 18:25:50.692 | 20.965 秒 | B | 第五个真实 S1 结果写入成功 | 进程 B 正在执行剩余业务工作 |
| handler 完成 | 18:26:11.112 | 41.385 秒 | B | 第 5-12 段完成，12 个输出全部存在 | 响应快照完整 |
| **客户端看到 `completed`** | **18:26:11.276** | **41.556 秒** | B | 原响应到达明确终态 | 完整输出验收通过 |

进程 A 真正 down 后 **1.415 秒观察到 recovered entry**。进程 B 在 down 后 **25.936 秒完成 handler**；客户端在 down 后 26.100 秒看到 `completed`。响应 ID 的 SHA-256 始终是 `9acba831...b393d`，报告中有两个不同的进程实例哈希。

恢复后的任务**确实由进程 B 完成了**。下面这段终端证据由已提交的 JSON 报告自动生成：

```text
RUN owned-agent-real-translation-primary
2026-08-26T10:25:29.748+00:00  PROCESS_A_START
2026-08-26T10:25:31.601+00:00  RESPONSE_CREATED       response_sha256=9acba83102c7a3b4da7da422d5083831235a3a6102a9d65c44679e24ff0b393d
2026-08-26T10:25:44.638+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_04
2026-08-26T10:25:44.638+00:00  FAULT_INJECTED         mode=hard_process_exit exit_code=86
2026-08-26T10:25:45.176+00:00  PROCESS_A_DOWN         exit_code=86
2026-08-26T10:25:45.190+00:00  PROCESS_B_START
2026-08-26T10:25:46.591+00:00  HANDLER_RECOVERED      mode=recovered resume_from=translation_section_05
2026-08-26T10:25:50.692+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_05
2026-08-26T10:26:11.112+00:00  HANDLER_COMPLETED
2026-08-26T10:26:11.276+00:00  RESPONSE_STATUS        status=completed
ASSERT same_response_reused=true
ASSERT process_memory_survived=false
ASSERT checkpointed_response_survived=true
ASSERT all_expected_checkpoints_completed_once=true
ASSERT process_instance_count=2
RESULT PASS
```

源文件是 [`owned-hosted-agent-translation-local-trace.txt`](evidence/owned-hosted-agent-translation-local-trace.txt)；仓库门禁要求 README 中这段日志与源文件逐字一致。

### 线上运行：延迟、接管和完成日志

真实 Foundry Version 7 运行保留了恢复容器日志，但没有保留旧容器的退出行。因此，**49.555 秒是两次成功轮询之间的有界观测窗口，不是精确 hang 时长**。日志仍然直接给出关键链路：一次 timeout、进程 B 从第 5 段进入、恢复后第一个检查点、handler 完成，以及原 response 达到 `completed`。

| 测量项 | 数值 | 含义 |
|---|---:|---|
| 线上整次运行 | 89.199 秒 | 从请求开始到客户端看到 `completed` |
| 实例替换前后的成功轮询间隔 | 49.555 秒 | 包含 timeout、轮询、调度和实例替换；不是精确 hang |
| recovered entry → handler 完成 | 16.511 秒 | 进程 B 完成第 5-12 段 |
| handler 完成 → 客户端看到 `completed` | 4.322 秒 | 最终持久化和轮询延迟 |

```text
RUN owned-agent-live-real-translation foundry_version=7
2026-08-26T10:16:04.612+00:00  REQUEST_STARTED        workload=translator_batch response_sha256=cfc1b7056cf1f2e8bb6fe4587405fc099d89c39b79b31fb90fc44f0be5519e09
2026-08-26T10:16:24.658+00:00  LAST_SUCCESSFUL_POLL   status=in_progress
2026-08-26T10:16:58.207+00:00  CONNECTION_TIMEOUT     detail=TimeoutError phase=replacement_window
2026-08-26T10:17:12.978+00:00  HANDLER_RECOVERED      process=B resume_from=translation_section_05
2026-08-26T10:17:14.213+00:00  POLL_AFTER_TIMEOUT     status=in_progress last_checkpoint=translation_section_04
2026-08-26T10:17:15.859+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_05
2026-08-26T10:17:29.489+00:00  HANDLER_COMPLETED      process=B
2026-08-26T10:17:33.811+00:00  RESPONSE_STATUS        status=completed process_instances=2
BOUNDARY exact_process_a_down_at=NOT_AVAILABLE reason=prior_container_log_not_retained
DURATION successful_poll_gap_seconds=49.555 meaning=timeout_plus_polling_plus_replacement_not_exact_hang
DURATION recovered_to_handler_completed_seconds=16.511
DURATION handler_completed_to_client_completed_seconds=4.322
DURATION total_run_seconds=89.199
ASSERT same_response_reused=true
ASSERT checkpoint_continuity=translation_section_04->translation_section_05
ASSERT all_12_translations_present=true
ASSERT entry_modes=fresh+recovered
ASSERT terminal_status=completed
RESULT PASS
```

源文件是 [`owned-hosted-agent-live-translation-trace.txt`](evidence/owned-hosted-agent-live-translation-trace.txt)。它由[客户端报告](evidence/owned-hosted-agent-live-translation.json)和[脱敏恢复容器事件](evidence/owned-hosted-agent-live-translation-events.jsonl)自动生成；仓库门禁要求 README 中这段日志与源文件逐字一致。

### 为什么任务没停、数据没丢

| 状态 | 保存位置 | 进程 A 丢失时发生了什么 |
|---|---|---|
| Python 局部变量、调用栈、连接、PID | 进程 A 内存 | **全部丢失**，这是预期行为 |
| 任务身份和原始输入 | AgentServer 本地文件任务存储 | 保留下来，进程 B 继续使用 |
| 第 1-4 段中文结果 | Responses 持久化检查点 | 保留下来，进程 B 不再次调用 S1 |
| 剩余第 5-12 段 | 由已保存输出数量和命名任务确定 | 进程 B 从 `translation_section_05` 继续 |
| 响应 ID 和截止时间 | 客户端状态文件 | 新的查询进程仍能读取同一响应 |
| Azure Translator 调用 | 外部只读转换 | 已完成结果写入检查点；最后检查点之后的调用仍可能重复并产生费用 |
| 支付、预订、邮件、写入等操作 | 本任务没有使用 | **本文没有证明**；真实应用仍需幂等和对账 |

这是 at-least-once 恢复。最后一次成功检查点之后的工作可能再次执行。不可逆操作之前要先写入检查点，并给外部操作单独的幂等键。

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="微软官方租约恢复模型：后续进程接管同一条持久化任务记录"></div>

<p align="center"><sub><i>“Lease-based recovery of a resilient work item”</i>，来源：<a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Microsoft Foundry 官方文档</a> © Microsoft，依据 <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> 原样使用，不属于本仓库 MIT License。</sub></p>

## 同一份任务再经受两种打断

进程丢失只是一种打断。真实的长任务还会遇到另外两种：干着干着，提需求的人改主意了；或者任务必须停下来等一个人点头才能继续。本仓库另有两个自有 Agent，把同一份 Translator 任务扩成 30 段，分别放到这两种打断下面跑。代码、部署脚本和运行器在 [`hosted-agent-steering/`](hosted-agent-steering/) 和 [`hosted-agent-approval/`](hosted-agent-approval/)；下面的日志来自从这两个目录原样部署出去的 Agent。

### 恢复之后改主意

转向 Agent（[`main.py`](hosted-agent-steering/src/resilient-steering/main.py)）在 `resilient_background=True` 之外还开了 `steerable_conversations=True`。所谓转向，就是在第一个响应还在跑的时候，往同一个会话再 POST 一个新响应：正在运行的处理函数看到 `context.pending_input_count > 0`，把手上这一段做完，带着已完成的段落发出 `completed`；新响应以 `context.is_steered_turn` 进入，从第 1 段开始翻译新语言——繁体文档不能拿简体段落凑数。

提交的这次运行把两种打断叠在一起：进程 P1 提交 `translation_section_10` 后执行 `os._exit(86)`；网关随即关掉客户端的流；替代进程 P2 在 `translation_section_11` 恢复同一个响应；客户端这时才发出“改成繁体”的请求，P2 把转向后的响应从第 1 段跑到第 30 段，原响应则以 14 段收尾。

```text
RUN owned-agent-live-steering foundry_version=9
2026-09-02T11:41:59.280+00:00  REQUEST_STARTED        response=A target=zh-Hans crash_after_stage=9
2026-09-02T11:42:04.863+00:00  RESPONSE_CREATED       response=A response_sha256=d74fda4d9b75404892324f8a5b52a80cf369a649bbc380b84c9ec1641d93283d
2026-09-02T11:42:04.863+00:00  HANDLER_ENTERED        response=A mode=fresh process=P1
2026-09-02T11:42:17.468+00:00  CHECKPOINT_COMMITTED   response=A checkpoint=translation_section_10 process=P1
2026-09-02T11:42:18.133+00:00  STREAM_CLOSED          response=A committed_sections=10 detail=no_terminal_event_process_gone
2026-09-02T11:42:43.437+00:00  HANDLER_RECOVERED      response=A mode=recovered process=P2 resume_from=translation_section_11
2026-09-02T11:42:43.439+00:00  CHECKPOINT_COMMITTED   response=A checkpoint=translation_section_11 process=P2
2026-09-02T11:42:45.215+00:00  STEER_POSTED           response=B from=zh-Hans to=zh-Hant same_conversation=true original_sections_so_far=14
2026-09-02T11:42:47.830+00:00  RESPONSE_CREATED       response=B response_sha256=89f83641ff214ade2cc9541bbab106594bc3cd34fd8180d5848abcb2d6d2a4d2
2026-09-02T11:42:47.830+00:00  HANDLER_ENTERED        response=B mode=steered process=P2
2026-09-02T11:42:48.791+00:00  CHECKPOINT_COMMITTED   response=B checkpoint=translation_section_01 process=P2 meaning=new_language_starts_at_section_1
2026-09-02T11:43:12.269+00:00  CHECKPOINT_COMMITTED   response=B checkpoint=translation_section_30 process=P2
2026-09-02T11:43:12.659+00:00  RESPONSE_STATUS        response=B status=completed sections=30
2026-09-02T11:43:13.148+00:00  RESPONSE_STATUS        response=A status=completed sections=14
BOUNDARY exact_process_p1_down_at=NOT_AVAILABLE reason=hosted_container_exit_not_observable_by_client observed=stream_close
DURATION stream_close_to_recovered_entry_seconds=25.304 meaning=observation_window_includes_replacement_scheduling_and_reconnect_polling
DURATION steer_posted_to_replacement_completed_seconds=27.444
DURATION total_run_seconds=73.868
ASSERT process_replaced=true
ASSERT checkpoint_continuity=translation_section_10->translation_section_11
ASSERT steered_on_replacement_process=true
ASSERT replacement_starts_at_section_1=true
ASSERT original_sections_kept=14 replacement_sections=30
ASSERT terminal_status=A:completed B:completed
RESULT PASS
```

源文件是 [`owned-steering-live-trace.txt`](evidence/owned-steering-live-trace.txt)，由 [`render_steering_trace.py`](scripts/render_steering_trace.py) 从 [`owned-steering-live.json`](evidence/owned-steering-live.json) 生成；报告本身由 [`run_steering_recovery.py`](hosted-agent-steering/run_steering_recovery.py) 产出并执行验收规则。流关闭到恢复进入之间的 25.304 秒包含重连尝试：进程已经不在时，对该响应发 `stream=true` 的 `GET` 会被拒绝，直到替代进程重新进入，运行器在此期间改为轮询持久化状态。反过来的顺序——先转向、再丢进程——是 **NOT VERIFIED**：在 `azure-ai-agentserver-core` 2.0.0 和 2.1.0 上，替代进程都拒绝了持久化下来的转向输入，响应一直停在 `in_progress`。[`steering-order-boundary.json`](evidence/steering-order-boundary.json) 记录了观察到的原始信息。

### 等人审批，中途实例还丢了

审批 Agent（[`main.py`](hosted-agent-approval/src/resilient-approval-gate/main.py)）走 Invocations 协议，每个任务一条 `@multi_turn_task` 链。`start` 先翻译 10 段样稿，每段用 `await job.flush()` 提交一次，把任务阶段置为 `awaiting_review` 后返回；审稿人看样稿期间，没有任何东西在跑。`approve_review` 重新进入同一条链，从任务存储读回已提交的段落和阶段，接着翻译第 11-30 段，同样每段刷一次。

提交的本机运行在样稿等待审批时丢掉进程：故障请求发出 0.258 秒后，进程 P1 以退出码 86 结束；进程 P2 在同一个任务存储上启动，退出 2.004 秒后就用新的进程哈希应答，样稿仍显示 `awaiting_review`，随后接下审批，完成剩余 20 段。下面的 Foundry 运行在已部署的 Version 4 上做了同样的事；客户端在那里只能看到，故障请求发出 36.121 秒后换了一个进程来应答。

```text
RUN owned-agent-live-approval foundry_version=4
2026-09-02T11:40:43.595+00:00  REQUEST_STARTED        action=start target=zh-Hans sample_size=10
2026-09-02T11:40:51.774+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_01 batch=sample process=P1
2026-09-02T11:41:00.036+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_10 batch=sample process=P1
2026-09-02T11:41:00.037+00:00  REVIEW_GATE_REACHED    sample_sections=10 task_sha256=0a9c04dced7418f27de9e0b0d3ea05c78f21e9d0103bb194cca920e8d1e38a1b waiting_for=human_reviewer
2026-09-02T11:41:00.037+00:00  FAULT_INJECTED         mode=hard_process_exit exit_code=86 while=awaiting_review
2026-09-02T11:41:36.158+00:00  REPLACEMENT_OBSERVED   process=P2 sample_still=awaiting_review
2026-09-02T11:41:36.158+00:00  APPROVAL_SUBMITTED     decision=approve_review landed_on=P2
2026-09-02T11:41:38.580+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_11 batch=remaining process=P2
2026-09-02T11:41:58.844+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_30 batch=remaining process=P2
2026-09-02T11:41:58.844+00:00  TASK_STATUS            status=resolved outcome=completed sections=30
BOUNDARY exact_instance_down_at=NOT_AVAILABLE reason=platform_replaced_the_instance observed=probe_answered_by_new_process
DURATION fault_request_to_replacement_observed_seconds=36.121 meaning=observation_window_not_exact_downtime
DURATION approval_to_completed_seconds=22.686
DURATION total_run_seconds=75.249
ASSERT same_task_identity=true
ASSERT process_replaced=true
ASSERT sample_result_hashes_unchanged=true
ASSERT sample_on_process_p1=true remaining_on_process_p2=true
ASSERT all_sections_present_once=true sections=30
RESULT PASS
```

源文件是 [`owned-approval-live-trace.txt`](evidence/owned-approval-live-trace.txt)；带精确退出和重启时间的本机版本是 [`owned-approval-local-trace.txt`](evidence/owned-approval-local-trace.txt)。两者都由 [`render_approval_trace.py`](scripts/render_approval_trace.py) 从 [`run_approval_recovery.py`](hosted-agent-approval/run_approval_recovery.py) 写出的报告生成，门禁会重新生成并逐字比对。审批 Agent 把 `azure-ai-agentserver-core` 固定在 2.0.0，因为 2.1.0 去掉了这条链用来保存阶段的 `TaskContext.metadata` 命名空间；转向 Agent 固定在 2.1.0。两个 Agent 的故障注入都是只供测试的开关，部署前不显式导出 `LRE_ENABLE_FAULT_INJECTION=true` 就保持关闭。

## 在浏览器里看完整过程

README 首屏的录像于 2026-09-03 在“星辰”演示台上录制，[`demo-portal/`](demo-portal/) 就是从它抽取出来的。录像中，基线、进程崩溃和断线三个场景跑的是检查点 Agent 的 30 段故障注入构建，崩溃点在第 10 段后；审批和转向两个场景跑的就是本仓库的 `lre-approval-gate` 与 `lre-steering-agent`。演示台不落盘这些场景的机器可读运行记录，所以屏幕上的时长只是当天的一次观察，这里有意不把它们当作证据重复。

四种打断各自的代价。本机进程几秒就能重启；在 Foundry 上，平台要先察觉丢失、调度替代计算、再启动新进程，所以录像里同样的打断明显更长：

| # | 场景 | 打断的是什么 | 平台怎么接下去 | 屏幕上看什么 | 已提交证据 |
|---|---|---|---|---|---|
| ① | 基线，不制造打断 | 不打断 | 持久化后台响应，每段落盘一个检查点 | 1 个进程跑完，检查点齐全，终态 completed | [对照运行](evidence/owned-hosted-agent-live.json) |
| ② | 进程崩溃后恢复 | Agent 进程 | 新进程凭租约接管同一条持久化任务 | 进程 A→B 哈希不同、响应 ID 不变、检查点不缺不重 | [本机 1.415 秒](evidence/owned-hosted-agent-translation-local.json) · [Foundry 观测窗口 49.555 秒](evidence/owned-hosted-agent-live-translation-trace.txt) |
| ③ | 客户端断线重连 | 调用方连接 | 后台执行与调用方解耦 | 始终 1 个进程；无人连接期间进度照常推进 | [Agent 全程未停](evidence/owned-hosted-agent-observer.json) |
| ④ | 等审批时实例丢失 | 审批等待中的实例 | 多轮任务链把阶段与样稿写进任务存储 | 样稿哈希不变、审批落到新实例、剩余段在 B 完成 | [本机 2.004 秒](evidence/owned-approval-local-trace.txt) · [Foundry 观测窗口 36.121 秒](evidence/owned-approval-live-trace.txt) |
| ⑤ | 恢复后中途改主意 | 进程 + 目标本身 | 崩溃恢复 + 可转向会话叠加 | A 从断点续跑，B 在同一新进程从第 1 段重译，两者都完成 | [Foundry 观测窗口 25.304 秒](evidence/owned-steering-live-trace.txt) |

[`demo-portal/`](demo-portal/) 是从“星辰”大 Demo 中单独抽出的韧性实验区，不包含与 LRA 无关的聊天、记忆、Toolbox、路由和交易结算功能。[`demo-portal/app.py`](demo-portal/app.py) 里的 FastAPI 编排只调用本仓库这三个 Agent；[`demo-portal/static/app.js`](demo-portal/static/app.js) 提供中英文界面和五个按钮：一条安全基线，加上进程崩溃、客户端断线、等待人工审批时实例崩溃，以及恢复后更换目标语言四种打断。

基线、进程崩溃和断线三个按钮直接使用 [`hosted-agent/`](hosted-agent/) 中原有的 12 段 `lra-evidence-agent`，没有再复制一个 30 段 Agent。服务端和浏览器都从检查点记录里的 `stage_count` 读取总段数；转向和审批场景仍使用各自的 30 段任务。[`test_demo_portal.py`](tests/test_demo_portal.py) 分别用 12 段恢复、6 段转向和 8 段审批验证动态段数，并加入损坏输入，防止固定段数或空的 recovered lane 蒙混过关。

三个 Agent 部署完成后，在仓库根目录启动 Portal：

```powershell
& $python -m pip install --no-input -r demo-portal\requirements.txt
$env:FOUNDRY_PROJECT_ENDPOINT = "<project-endpoint>"
$env:LRA_FAULT_AGENT_NAME = "lra-evidence-agent"
$env:LRA_STEERING_AGENT_NAME = "lre-steering-agent"
$env:LRA_APPROVAL_AGENT_NAME = "lre-approval-gate"
& $python -m uvicorn app:app --app-dir demo-portal --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765/`。安全基线和客户端断线可以使用关闭故障注入的安全版本；另外三条包含进程崩溃的路径必须使用专门的非生产 Agent 版本，并在部署前显式设置 `LRE_ENABLE_FAULT_INJECTION=true`。所有部署脚本默认都是 `false`，不要在面向客户的 Agent 上打开。页面负责把单次运行讲清楚，可复验依据仍是 [`evidence/`](evidence/) 中的 JSON 报告和事件日志。

## 这四个场景到底跑了什么

这条链路里没有语言模型，因此也不存在推理强度设置。这里每个 `azure.yaml` 都声明 `deployments: []`，任何 Agent 中都没有 chat、responses 模型或推理调用。这是有意为之：恢复是靠对比新旧两个进程下每段译文的 SHA-256 哈希来证明的，而采样型模型重放时会给出不同措辞，这个对比就失效了。确定性的翻译服务才能让恢复结论可被证伪。

| 配置项 | 实际部署值 |
|---|---|
| 模型部署 | 无；每个 `azure.yaml` 都是 `deployments: []` |
| 推理强度 | 不适用，因为链路中没有推理模型 |
| 实际干的活 | Azure AI Translator 文本翻译 `v3.0`，源语言固定 `en`，S1 层 |
| 翻译服务认证 | `DefaultAzureCredential` 针对作用域 `https://cognitiveservices.azure.com/.default` 的令牌，加 `Ocp-Apim-Subscription-Region` 头；资源无自定义子域名时再加 `Ocp-Apim-ResourceId` |
| 可选目标语言 | `zh-Hans`、`zh-Hant`、`ja`、`ko`、`fr`、`de`、`es` |
| 托管方式 | Foundry Hosted Agent，`python_3_13`，远端构建，`microsoft.foundry` provider |
| 故障注入 | 由环境变量控制；留在线上的版本均已关闭 |

| # | Agent | 协议与服务端 SDK | 容器规格 | 段数 | Portal 默认参数 |
|---|---|---|---|---|---|
| ① | `lra-evidence-agent` | responses `2.0.0`，core 与 responses `2.1.0b2` | 0.5 vCPU / 1 GiB | 12 | 不注入故障，每段 300 ms |
| ② | `lra-evidence-agent` | responses `2.0.0`，core 与 responses `2.1.0b2` | 0.5 vCPU / 1 GiB | 12 | 第 3 段后崩溃，每段 300 ms |
| ③ | `lra-evidence-agent` | responses `2.0.0`，core 与 responses `2.1.0b2` | 0.5 vCPU / 1 GiB | 12 | 第 3 段后断开 8 秒 |
| ④ | `lre-approval-gate` | invocations `2.0.0`，core `2.0.0` 与 invocations `1.0.0b8` | 1 vCPU / 2 GiB | 30 | 样稿 10 段，每段 300 ms |
| ⑤ | `lre-steering-agent` | responses `2.0.0`，core 与 responses `2.1.0` | 1 vCPU / 2 GiB | 30 | 第 9 段后崩溃，第 4 段后转向 |

录像与这些默认值只有一处不同：①、②、③ 三个场景跑的是 30 段构建，崩溃点在第 10 段后。

Portal 给每次运行设了 300 秒绝对截止、180 秒流超时和 10 秒重连超时并每秒重试一次，因此重连尝试不会在平台完成自己的握手之前就被取消。

这四个场景背后的编排逻辑由 [`tests/test_demo_portal.py`](tests/test_demo_portal.py) 覆盖，全程不需要 Azure。它先断言回环页面与 URL 构造器，再把录制的事件形状回放进线上 Portal 用的同一套验收函数：12 段契约通过，而缺段、重段、只有终态事件但没有第二个进程三种情况均被拒绝；转向路径在动态段数下通过，而续跑留缺口或仍在同一进程时失败关闭；审批路径两阶段通过，而两阶段之间样稿哈希被改时失败关闭。用下面的验收步骤运行它们。

## 故障矩阵

| 场景 / 模式 | 触发方式 | 预期 | 实际结果 | 状态 | 证据 |
|---|---|---|---|---|---|
| 真实 S1 批处理，本机 Agent 进程丢失 | 第 4 段后执行 `os._exit(86)` | 进程 B 从第 5 段继续并完成同一文档 | down 后 1.415 秒进入 recovered；25.936 秒完成全部 12 段 | **PASS** | [报告](evidence/owned-hosted-agent-translation-local.json) · [事件](evidence/owned-hosted-agent-translation-local-events.jsonl) |
| 真实 S1 批处理，Foundry Hosted 进程丢失 | 临时开启故障的 Version 7 执行受保护的 `os._exit(86)` | 替代计算恢复同一个已保存响应 | `89.199` 秒；实例替换 timeout、`fresh + recovered`、两个进程哈希、12 段结果、`completed`；旧容器的精确 down 时间仍只做边界声明 | **PASS** | [直读日志](evidence/owned-hosted-agent-live-translation-trace.txt) · [报告](evidence/owned-hosted-agent-live-translation.json) · [事件](evidence/owned-hosted-agent-live-translation-events.jsonl) · [完整输出](evidence/owned-hosted-agent-live-translation-output.md) |
| Python 快速合同回归 | 确定性检查点后执行 `os._exit(86)` | 新进程恢复同一响应 | down 后 1.435 秒进入 recovered；4.677 秒完成 | **PASS** | [报告](evidence/owned-hosted-agent-local.json) · [事件](evidence/owned-hosted-agent-local-events.jsonl) |
| Foundry 快速合同回归 | 临时 Version 5 执行受保护的 `os._exit(86)` | 替代计算恢复同一个已保存响应 | 实例替换 timeout、`fresh + recovered`、两个进程哈希和 `completed` | **PASS** | [报告](evidence/owned-hosted-agent-live-recovery.json) · [事件](evidence/owned-hosted-agent-live-recovery-events.jsonl) |
| .NET Agent 进程丢失 | 检查点后执行 `Environment.Exit(86)` | 新 CLR 进程恢复同一响应 | 0.606 秒后进入 recovered；down 后 3.917 秒完成 | **PASS** | [报告](evidence/owned-hosted-agent-dotnet.json) · [事件](evidence/owned-hosted-agent-dotnet-events.jsonl) |
| 客户端 / 查询进程重启 | 查询方 A 保存响应 ID 和截止时间后退出 | Agent 继续；查询方 B 读取同一响应 | 无查询方期间仍有持久化进度；查询方 B 看到 `completed` | **PASS** | [报告](evidence/owned-hosted-agent-observer.json) · [事件](evidence/owned-hosted-agent-observer-events.jsonl) |
| 当前安全 Foundry 部署 | Version 9，故障开关关闭 | 测试后仍可正常执行真实 S1 批处理 | 单进程 22.862 秒完成 12 段翻译 | **PASS** | [运行](evidence/owned-hosted-agent-live.json) · [状态](evidence/owned-hosted-agent-status.json) |
| 宿主优雅关闭 | Windows 控制台 shutdown signal | 宿主设置 shutdown、交接任务，后续进程恢复 | Windows 本机运行器未驱动完整宿主 shutdown 生命周期 | **NOT VERIFIED** | [尝试记录](evidence/owned-hosted-agent-graceful-attempt.json) |
| 输出缺失或重复 | 在测试数据中删除或复制已完成输出 | 验收必须失败 | 缺口、重复和只有 `done` 的用例均被拒绝 | **PASS** | [验证器证据](evidence/observation-validation.json) |
| 恢复后换目标语言（转向 Agent） | Version 9 第 10 段后执行受保护的 `os._exit(86)`，P2 恢复后再发转向 | P2 从第 11 段续跑原响应；转向后的响应在 P2 上从第 1 段开始；两者都完成 | 流关闭 25.304 秒后进入 recovered；转向响应在 P2 上进入并完成 30 段；原响应以 14 段完成；共 `73.868` 秒 | **PASS** | [直读日志](evidence/owned-steering-live-trace.txt) · [报告](evidence/owned-steering-live.json) · [事件](evidence/owned-steering-live-events.jsonl) |
| 先转向、再丢进程 | 先发转向，再执行 `os._exit(86)` | P2 恢复原响应并执行转向 | 替代进程拒绝了持久化的转向输入并 fail closed；响应停在 `in_progress`（core 2.0.0 与 2.1.0） | **NOT VERIFIED** | [边界记录](evidence/steering-order-boundary.json) |
| 审批门，本机进程丢失（审批 Agent） | 10 段样稿处于 `awaiting_review` 时执行 `os._exit(86)` | 新进程保留任务身份和样稿哈希；审批落在新进程上；第 11-30 段完成 | 0.258 秒后以 86 退出；2.004 秒后 P2 应答；审批落在 P2；共 30 段；`52.411` 秒 | **PASS** | [直读日志](evidence/owned-approval-local-trace.txt) · [报告](evidence/owned-approval-local.json) · [事件](evidence/owned-approval-local-events.jsonl) |
| 审批门，Foundry 实例丢失 | Version 4 处于 `awaiting_review` 时执行受保护的 `os._exit(86)` | 替代实例保留审批门并接下审批 | 故障请求 36.121 秒后由第二个进程哈希应答；审批落在其上；22.686 秒后完成第 11-30 段；共 `75.249` 秒 | **PASS** | [直读日志](evidence/owned-approval-live-trace.txt) · [报告](evidence/owned-approval-live.json) · [事件](evidence/owned-approval-live-events.jsonl) |

这张表是数据，不是承诺。[`run-contract.json`](evidence/run-contract.json) 声明主运行必须出现的里程碑和状态断言；[`scenario-matrix.json`](evidence/scenario-matrix.json) 声明全部模式。门禁读取这些文件，不把当前 Demo 的事件名写死在验证器里。

SOP-68 Rule 不是自报 PASS：[`scripts\generate_rule_results.py`](scripts/generate_rule_results.py) 实际计算 `RUN-001` 至 `RUN-015`，生成 [`rule-results.json`](evidence/rule-results.json)；仓库门禁重新运行 evaluator，并逐 byte 比较生成结果。

## 自己复现

### 前置条件

| 路径 | 需要 |
|---|---|
| 真实翻译恢复 | Git、Python 3.13、[`requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt) 中的软件包、Azure CLI 登录、Translator S1，以及该资源上的 `Cognitive Services User` |
| Python 快速恢复和查询方重启 | 同一个 Python 环境；不需要 Translator |
| .NET 恢复 | .NET 8 SDK，并能恢复 [`LraEvidenceAgent.csproj`](dotnet-agent/LraEvidenceAgent.csproj) 中固定的预览软件包 |
| 部署到 Foundry | 非生产订阅、Foundry 项目、Azure CLI 2.80+、`azd` 1.27.1+、项目级 `Foundry Project Manager`，以及 Agent 托管身份对 Translator 的访问权限 |
| 转向 Agent 与审批 Agent | 同一套工具，加上 [`hosted-agent-steering/.../requirements.txt`](hosted-agent-steering/src/resilient-steering/requirements.txt) 和 [`hosted-agent-approval/.../requirements.txt`](hosted-agent-approval/src/resilient-approval-gate/requirements.txt) 中固定的版本；本机审批运行还需要 `LRA_TRANSLATOR_RESOURCE_ID` |

Windows PowerShell：

```powershell
git clone --depth 1 --filter=blob:none --sparse `
  https://github.com/david-xinyuwei/david-share.git lra-demo
git -C lra-demo sparse-checkout set `
  Agents/Foundry-Long-Running-Agent-Resilience
Set-Location lra-demo\Agents\Foundry-Long-Running-Agent-Resilience

python -m venv .venv
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install --no-input `
  -r hosted-agent\src\lra-evidence-agent\requirements.txt

# 1. 真实长任务：调用 Azure Translator S1 12 次。
az login
$env:LRA_TRANSLATOR_ENDPOINT = "https://<translator-name>.cognitiveservices.azure.com"
$env:LRA_TRANSLATOR_REGION = "<resource-region>"
& $python hosted-agent\run_local_recovery.py `
  --workload translator_batch `
  --crash-after-stage 3 `
  --stage-delay-ms 1000 `
  --report .demo-state\translation-recovery.json `
  --log-report .demo-state\translation-events.jsonl

# 2. 快速确定性进程丢失回归。
& $python hosted-agent\run_local_recovery.py `
  --report .demo-state\python-recovery.json `
  --log-report .demo-state\python-events.jsonl

# 3. 查询方 A 退出，查询方 B 继续；Agent 进程不退出。
& $python hosted-agent\run_observer_restart.py `
  --report .demo-state\observer-restart.json `
  --log-report .demo-state\observer-events.jsonl

# 4. 编译并硬退出本仓库自有 .NET Agent。
dotnet build dotnet-agent\LraEvidenceAgent.csproj -c Release
$dotnetDir = (Resolve-Path dotnet-agent\bin\Release\net8.0).Path
$dotnetDll = Join-Path $dotnetDir LraEvidenceAgent.dll
& $python hosted-agent\run_local_recovery.py `
  --runtime-label ".NET 8.0" `
  --server-command dotnet $dotnetDll `
  --server-cwd $dotnetDir `
  --report .demo-state\dotnet-recovery.json `
  --log-report .demo-state\dotnet-events.jsonl

# 5. 审批门经受本机进程丢失（Translator 变量沿用第 1 步）。
& $python -m pip install --no-input `
  -r hosted-agent-approval\src\resilient-approval-gate\requirements.txt
$env:LRA_TRANSLATOR_RESOURCE_ID = "<translator-resource-id>"
& $python hosted-agent-approval\run_approval_recovery.py --local `
  --report .demo-state\approval-local.json `
  --log-report .demo-state\approval-local-events.jsonl

# 6. 仓库验收。
& $python -m unittest discover -s tests -v
& $python scripts\validate_repo.py
```

完成标准：每个运行器退出码为 `0`；翻译报告包含 12 个非空结果，并同时包含 `recovery_proven: true`、`fresh + recovered`、两个进程哈希和 `completed`；查询方报告显示两个查询进程、一个 Agent 进程。

Linux/macOS 使用 `.venv/bin/python` 和 `/` 路径分隔符。运行器接收任意 server command，因此 Python 和 .NET 共用同一套验收逻辑，不复制第二份标准。

把安全版本部署到 Foundry：

```powershell
Set-Location hosted-agent
az login
azd auth login
azd ext install microsoft.foundry
azd env new <environment-name> `
  --subscription <subscription-id> `
  --location <supported-region> `
  --no-prompt
azd env set LRA_ENABLE_FAULT_INJECTION false
azd env set LRA_TRANSLATOR_ENDPOINT "https://<translator-name>.cognitiveservices.azure.com"
azd env set LRA_TRANSLATOR_REGION "<resource-region>"
azd provision
azd deploy
azd ai agent show lra-evidence-agent
```

结构化状态和 Portal 显示本仓库自有 Version 9 为 `active` / `Running`、`hosted` / `Hosted`，而且故障注入已关闭。Version 9 安全请求在一个进程中完成全部 12 段真实翻译。安全运行本身不证明线上进程恢复；线上证明来自临时 Version 7，之后由 Version 9 替换。

转向 Agent 和审批 Agent 各自从自己的目录部署：[`hosted-agent-steering/scripts/deploy.sh`](hosted-agent-steering/scripts/deploy.sh) 和 [`hosted-agent-approval/scripts/deploy.sh`](hosted-agent-approval/scripts/deploy.sh)。脚本从环境变量读取订阅、区域、项目 ID、项目端点和 Translator 资源 ID，写入 `azd` 环境，然后执行 `azd provision` 和 `azd deploy`。部署完成后，用 `run_steering_recovery.py --endpoint "<带 API 版本参数的 responses 端点>"` 或 `run_approval_recovery.py --endpoint "<带 API 版本参数的 invocations 端点>"` 加 `--agent-version` 跑线上场景；两者都用 Azure CLI 登录态鉴权，任一验收规则不满足就以非零退出码结束。

## 把同样的接线放进你的 Agent

1. 固定你所用运行时的公共 AgentServer 软件包版本。
2. 在服务端开启 resilient background execution。
3. 请求必须发送 `store=true` 和 `background=true`。
4. 向上游确认成功前，先保存 `response.id`、业务 work ID 和一个绝对截止时间。
5. 一个可以安全重放的工作单元完成后，先提交应用状态，再给响应写检查点。
6. 以 recovered 模式进入时，加载 `persisted_response` 或应用/框架检查点，跳过已经提交的工作。
7. 始终轮询原响应；一次读取超时不能成为创建替代任务的理由。
8. 所有外部操作必须幂等，或能够明确对账。

当进度不能完整放进响应快照，或者审批、工具状态、大文件、支付、预订和写入必须跨进程保留时，使用应用自己的数据库。

## 验收合同

只有同时满足下面条件，才能说“恢复成功”：

- 进程 A 确实在已经记录的检查点之后退出。
- 进程 B 的实例哈希不同，并以 `recovered` 模式进入。
- work ID、输入哈希和响应 ID 哈希不变。
- 恢复后的工作从最后持久化检查点之后开始。
- 每个预期检查点只出现一次，没有缺口或重复。
- 原响应到达明确的 `completed` 终态。
- 外部操作不存在、具备幂等性，或已经单独对账。

一个 `done` 帧、Portal 绿色状态，或者重新跑一个成功请求，都不能证明恢复。

## 证据与边界

| 证据 | 证明什么 |
|---|---|
| [`run-contract.json`](evidence/run-contract.json) | 由场景声明、供通用门禁读取的里程碑和状态断言 |
| [`scenario-matrix.json`](evidence/scenario-matrix.json) | 每个模式的 PASS / NOT VERIFIED 状态 |
| [真实本机翻译报告](evidence/owned-hosted-agent-translation-local.json)、[事件](evidence/owned-hosted-agent-translation-local-events.jsonl)和[轨迹](evidence/owned-hosted-agent-translation-local-trace.txt) | 精确硬退出时间、第 4 段边界、第 5 段恢复、全部 12 段和完成 |
| [线上 Version 7 直读日志](evidence/owned-hosted-agent-live-translation-trace.txt)、[报告](evidence/owned-hosted-agent-live-translation.json)、[事件](evidence/owned-hosted-agent-live-translation-events.jsonl)和[完整输出](evidence/owned-hosted-agent-live-translation-output.md) | 可见的 timeout/恢复/完成链路和完整 Translator 结果 |
| [Python 快速报告](evidence/owned-hosted-agent-local.json)和[事件](evidence/owned-hosted-agent-local-events.jsonl) | 同一恢复合同的确定性回归 |
| [.NET 报告](evidence/owned-hosted-agent-dotnet.json)和[事件](evidence/owned-hosted-agent-dotnet-events.jsonl) | 真实 .NET 预览包执行同一恢复合同 |
| [查询方报告](evidence/owned-hosted-agent-observer.json)和[事件](evidence/owned-hosted-agent-observer-events.jsonl) | 没有查询方连接时，后台工作仍继续 |
| [Version 9 安全运行](evidence/owned-hosted-agent-live.json)和[状态](evidence/owned-hosted-agent-status.json) | 当前正常完成、运行时、协议、状态、故障开关和内容哈希 |
| [UI 来源清单](evidence/ui-evidence.json)、[Version 9 列表图](images/product-ui/portal-owned-agent-list.png)和[Version 9 详情图](images/product-ui/portal-owned-agent-details.png) | 原图/公开图哈希、脱敏项和部署对象证据 |
| [Run bundle](evidence/runs/owned-agent-recovery-validation-20260826/run-manifest.json) | 命令、退出码、日志、状态、UI 和关键代码哈希 |
| [转向直读日志](evidence/owned-steering-live-trace.txt)、[报告](evidence/owned-steering-live.json)和[事件](evidence/owned-steering-live-events.jsonl) | 流关闭、第 11 段恢复进入、转向响应在替代进程上从第 1 段开始、两个终态 |
| [先转向再丢进程的边界记录](evidence/steering-order-boundary.json) | 为什么这个顺序在 core 2.0.0 和 2.1.0 上仍是 NOT VERIFIED |
| [审批本机轨迹](evidence/owned-approval-local-trace.txt)、[报告](evidence/owned-approval-local.json)、[事件](evidence/owned-approval-local-events.jsonl)，以及 [Foundry 轨迹](evidence/owned-approval-live-trace.txt)、[报告](evidence/owned-approval-live.json)、[事件](evidence/owned-approval-live-events.jsonl) | 审批门、`awaiting_review` 期间的退出码 86、替代进程、审批落在其上、第 11-30 段完成 |

链接中的 Portal 截图只证明部署对象、版本、状态和类型；进程恢复行为由 JSON 和日志证明。带登录态的原图和原始标识不会提交到仓库。

本仓库不证明 SLA、多轮可靠性、负载能力、多区域恢复、翻译质量或外部操作的严格一次执行。转向和审批两组运行同样只是单次试验：它们证明的是“恢复后换目标”和“审批悬而未决”这两种情况下的恢复合同，不证明先转向再丢进程的顺序。长期任务韧性处于公共预览；没有针对实际任务完成专项测试前，不建议用于生产。

## 相关工作与许可证

- [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/)
- [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/)
- [长期任务韧性官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
- [包含 Python 和 .NET 的官方 API 参考](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-reference)

项目原创内容使用 [MIT 许可证](LICENSE)。微软官方图依据 CC BY 4.0 使用，不属于 MIT 许可证；详见[第三方声明](THIRD-PARTY-NOTICES.md)。
