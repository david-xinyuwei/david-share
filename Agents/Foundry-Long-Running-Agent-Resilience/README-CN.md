# Microsoft Foundry Hosted Agent 进程丢失后如何恢复

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-repository_owned_agent-1363DF)](#一次完整的恢复运行)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_3.13_%2B_.NET_8-0F8B6D)](#故障矩阵)
[![Protocol](https://img.shields.io/badge/protocol-Responses-5F4BB6)](#把同样的接线放进你的-agent)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

本仓库包含真实的 Hosted Agent、客户端、故障运行器和证据。它只回答一个问题：**Agent 进程消失后，同一个已保存响应如何由新进程继续，而且不丢失已经写入检查点的输出？**

> **Author:** 魏新宇（Xinyu Wei）

[English](README.md) | 中文

[一次完整运行](#一次完整的恢复运行) · [故障矩阵](#故障矩阵) · [复现](#自己复现) · [接入自己的 Agent](#把同样的接线放进你的-agent) · [证据](#证据与边界) · [官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)

## 先看这里

这里不是“把旧进程重新启动”。客户端只创建一个已保存的后台响应。进程 A 写入检查点后退出。进程 B 带着空的进程内存启动，从持久化存储中找到同一个响应和输入，以 `is_recovery=True` 重新进入处理函数，加载已经保存的响应快照，再从下一个检查点继续。客户端始终轮询原来的响应 ID。

下面的主证据来自本仓库自有 Python Agent 的一次真实运行。同样的硬退出测试也在本仓库自有 .NET handler 上通过。它们是公共预览能力证据，不是 SLA 或生产就绪声明。

## 一次完整的恢复运行

### Agent 到底在哪里接入 LRA

| 必需接线 | 本仓库真实代码 | 它改变了什么 |
|---|---|---|
| 导入 AgentServer 恢复 API | [`main.py`](hosted-agent/src/lra-evidence-agent/main.py#L13-L20) | 使用公共 task 和 Responses 软件包 |
| 服务端开启崩溃恢复 | [`ResponsesServerOptions(resilient_background=True)`](hosted-agent/src/lra-evidence-agent/main.py#L35-L38) | 已保存的后台响应可以在进程丢失后重新调用 |
| 开启启动恢复扫描 | [`set_resilient_tasks_enabled(True)`](hosted-agent/src/lra-evidence-agent/main.py#L39) | 新进程启动时扫描可恢复任务 |
| 创建已保存的后台任务 | [`store=True`、`background=True`](hosted-agent/client.py#L205-L215) | 请求和响应身份不依赖原始连接 |
| 载入持久化快照 | [`context.persisted_response`](hosted-agent/src/lra-evidence-agent/main.py#L104-L115) | 恢复后的处理函数从已写入检查点的输出继续 |
| 提交一个持久化边界 | [`yield stream.checkpoint()`](hosted-agent/src/lra-evidence-agent/main.py#L143-L166) | 该调用之前的输出可以跨进程保留 |
| 注入真实硬退出 | [`os._exit(86)`](hosted-agent/src/lra-evidence-agent/main.py#L167-L186) | 进程 A 不做正常清理，直接退出 |
| 始终查询同一任务 | [`state_file` 和 `validate_terminal_response`](hosted-agent/client.py#L330-L380) | 客户端重启不会创建替代任务 |

.NET handler 使用同一套契约：[`ResilientBackground`](dotnet-agent/Program.cs#L10-L12)、[`PersistedResponse`](dotnet-agent/Program.cs#L67-L72)、[`stream.Checkpoint()`](dotnet-agent/Program.cs#L101-L107) 和 [`Environment.Exit(86)`](dotnet-agent/Program.cs#L109-L121)。

### 什么时候 down、什么时候恢复、什么时候完成

下表直接来自 [`owned-hosted-agent-local.json`](evidence/owned-hosted-agent-local.json)。时间为 UTC+8；JSON 中保留 ISO 时间和完整脱敏事件日志。

| 事件 | UTC+8 | 已运行 | 进程 | 发生了什么 | 事件后的持久化状态 |
|---|---|---:|---|---|---|
| 进程 A 启动 | 16:55:10.437 | 0.019 秒 | A | AgentServer 开启恢复能力后启动 | 还没有请求 |
| 创建响应 | 16:55:12.272 | 1.854 秒 | A | 客户端发送一个 `store=true`、`background=true` 请求 | 输入和响应身份已经持久化 |
| 写入检查点 | 16:55:13.154 | 2.736 秒 | A | `plan_work` 完成，`stream.checkpoint()` 返回 | 到 `plan_work` 为止的输出已经持久化 |
| 注入故障 | 16:55:13.154 | 2.736 秒 | A | handler 记录边界后调用 `os._exit(86)` | 持久化状态保留；进程内存可以丢弃 |
| **进程真正 down** | **16:55:13.678** | **3.260 秒** | A | 操作系统报告退出码 `86` | 当前没有 Agent 进程运行 |
| 进程 B 启动 | 16:55:13.691 | 3.273 秒 | B | 新的空进程打开同一 AgentServer 状态 | 已保存响应仍可查询 |
| **观察到恢复** | **16:55:15.113** | **4.695 秒** | B | handler 以 `mode=recovered` 进入，响应哈希不变 | 从 `allocate_steps` 继续 |
| 恢复后第一个检查点 | 16:55:15.344 | 4.926 秒 | B | `allocate_steps` 写入成功 | 从进程 A 的最后检查点之后继续推进 |
| handler 完成 | 16:55:18.355 | 7.937 秒 | B | 所有预期检查点输出完成 | 响应快照完整 |
| **客户端看到 `completed`** | **16:55:18.649** | **8.231 秒** | B | 原响应到达明确终态 | 验收通过 |

进程 A 真正 down 后 **1.435 秒观察到 recovered entry**；down 后 **4.677 秒完成**。响应 ID 的 SHA-256 始终是 `b8af93f3...e42e1`，同时出现两个不同的进程实例哈希。

### 为什么任务没停、数据没丢

| 状态 | 保存位置 | 进程 A 丢失时发生了什么 |
|---|---|---|
| Python 局部变量、调用栈、连接、PID | 进程 A 内存 | **全部丢失**，这是预期行为 |
| 任务身份和原始输入 | AgentServer 本地文件任务存储 | 保留下来，进程 B 继续使用 |
| 到 `plan_work` 为止的完成输出 | Responses 持久化检查点 | 保留下来，进程 B 不重复执行 |
| 剩余工作 | 由命名检查点契约确定 | 进程 B 从 `allocate_steps` 继续 |
| 响应 ID 和截止时间 | 客户端状态文件 | 新的查询进程仍能读取同一响应 |
| 支付、预订、邮件、写入等外部操作 | 本确定性任务没有使用 | **本文没有证明**；真实应用仍需幂等和对账 |

这是 at-least-once 恢复。最后一次成功检查点之后的工作可能再次执行。不可逆操作之前要先写入检查点，并给外部操作单独的幂等键。

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="微软官方租约恢复模型：后续进程接管同一条持久化任务记录"></div>

<p align="center"><sub><i>“Lease-based recovery of a resilient work item”</i>，来源：<a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Microsoft Foundry 官方文档</a> © Microsoft，依据 <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> 原样使用，不属于本仓库 MIT License。</sub></p>

## 故障矩阵

| 场景 / 模式 | 触发方式 | 预期 | 实际结果 | 状态 | 证据 |
|---|---|---|---|---|---|
| Python Agent 进程丢失 | 检查点后执行 `os._exit(86)` | 新进程恢复同一响应 | 1.435 秒后进入 recovered；down 后 4.677 秒完成 | **PASS** | [报告](evidence/owned-hosted-agent-local.json) · [事件](evidence/owned-hosted-agent-local-events.jsonl) |
| Foundry Hosted Agent 进程丢失 | 临时开启故障的 Version 5 执行受保护的 `os._exit(86)` | 替代计算恢复同一个已保存响应 | 客户端先遇到实例替换 timeout，之后看到 `fresh + recovered`、两个进程哈希和 `completed`；旧容器日志未保留，因此不伪造精确 down 时间 | **PASS** | [报告](evidence/owned-hosted-agent-live-recovery.json) · [恢复容器事件](evidence/owned-hosted-agent-live-recovery-events.jsonl) |
| .NET Agent 进程丢失 | 检查点后执行 `Environment.Exit(86)` | 新 CLR 进程恢复同一响应 | 0.606 秒后进入 recovered；down 后 3.917 秒完成 | **PASS** | [报告](evidence/owned-hosted-agent-dotnet.json) · [事件](evidence/owned-hosted-agent-dotnet-events.jsonl) |
| 客户端 / 查询进程重启 | 查询方 A 保存响应 ID 和截止时间后退出 | Agent 继续；查询方 B 读取同一响应 | 无查询方期间仍有持久化进度；查询方 B 看到 `completed` | **PASS** | [报告](evidence/owned-hosted-agent-observer.json) · [事件](evidence/owned-hosted-agent-observer-events.jsonl) |
| 宿主优雅关闭 | Windows 控制台 shutdown signal | 宿主设置 shutdown、交接任务，后续进程恢复 | Windows 本机运行器未驱动完整宿主 shutdown 生命周期 | **NOT VERIFIED** | [尝试记录](evidence/owned-hosted-agent-graceful-attempt.json) |
| 输出缺失或重复 | 在测试数据中删除或复制已完成输出 | 验收必须失败 | 缺口、重复和只有 `done` 的用例均被拒绝 | **PASS** | [验证器证据](evidence/observation-validation.json) |

这张表是数据，不是承诺。[`run-contract.json`](evidence/run-contract.json) 声明主运行必须出现的里程碑和状态断言；[`scenario-matrix.json`](evidence/scenario-matrix.json) 声明全部模式。门禁读取这些文件，不把当前 Demo 的事件名写死在验证器里。

## 自己复现

### 前置条件

| 路径 | 需要 |
|---|---|
| Python 恢复和查询方重启 | Git、Python 3.13、[`requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt) 中的软件包 |
| .NET 恢复 | .NET 8 SDK，并能恢复 [`LraEvidenceAgent.csproj`](dotnet-agent/LraEvidenceAgent.csproj) 中固定的预览软件包 |
| 部署到 Foundry | 非生产订阅、Foundry 项目、Azure CLI 2.80+、`azd` 1.27.1+、项目级 `Foundry Project Manager` |

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

# 1. Python 进程硬退出，进程 B 恢复同一响应。
& $python hosted-agent\run_local_recovery.py `
  --report .demo-state\python-recovery.json `
  --log-report .demo-state\python-events.jsonl

# 2. 查询方 A 退出，查询方 B 继续；Agent 进程不退出。
& $python hosted-agent\run_observer_restart.py `
  --report .demo-state\observer-restart.json `
  --log-report .demo-state\observer-events.jsonl

# 3. 编译并硬退出本仓库自有 .NET Agent。
dotnet build dotnet-agent\LraEvidenceAgent.csproj -c Release
$dotnetDir = (Resolve-Path dotnet-agent\bin\Release\net8.0).Path
$dotnetDll = Join-Path $dotnetDir LraEvidenceAgent.dll
& $python hosted-agent\run_local_recovery.py `
  --runtime-label ".NET 8.0" `
  --server-command dotnet $dotnetDll `
  --server-cwd $dotnetDir `
  --report .demo-state\dotnet-recovery.json `
  --log-report .demo-state\dotnet-events.jsonl

# 4. 仓库验收。
& $python -m unittest discover -s tests -v
& $python scripts\validate_repo.py
```

完成标准：每个运行器退出码为 `0`；Python 和 .NET 报告同时包含 `recovery_proven: true`、`fresh + recovered`、两个进程哈希和 `completed`；查询方报告显示两个查询进程、一个 Agent 进程。

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
azd provision
azd deploy
azd ai agent show lra-evidence-agent
```

结构化状态和 Portal 现在都显示本仓库自有 Version 6 为 `active` / `Running`、`hosted` / `Hosted`，而且故障注入已关闭。Version 6 安全请求已经完成；这证明故障测试后的部署和正常执行。安全运行本身不证明线上进程恢复；该证明来自矩阵中的 Version 5。

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
| [Python 报告](evidence/owned-hosted-agent-local.json)和[事件](evidence/owned-hosted-agent-local-events.jsonl) | 精确的硬退出时间线、状态存活、恢复进入和完成 |
| [.NET 报告](evidence/owned-hosted-agent-dotnet.json)和[事件](evidence/owned-hosted-agent-dotnet-events.jsonl) | 真实 .NET 预览包执行同一恢复合同 |
| [查询方报告](evidence/owned-hosted-agent-observer.json)和[事件](evidence/owned-hosted-agent-observer-events.jsonl) | 没有查询方连接时，后台工作仍继续 |
| [Version 6 状态](evidence/owned-hosted-agent-status.json) | 脱敏的部署版本、运行时、协议、状态、故障开关和内容哈希 |
| [UI 来源清单](evidence/ui-evidence.json) | 原图/公开图哈希、脱敏项以及截图不能证明什么 |
| [Run bundle](evidence/runs/owned-agent-recovery-validation-20260826/run-manifest.json) | 命令、退出码、日志、状态、UI 和关键代码哈希 |

<div align="center"><img src="images/product-ui/portal-owned-agent-list.png" width="820" alt="脱敏的 Microsoft Foundry Portal Agent 列表：lra-evidence-agent Version 6 为 Running 和 Hosted"></div>

<div align="center"><img src="images/product-ui/portal-owned-agent-details.png" width="820" alt="脱敏的 Microsoft Foundry Portal 详情页：lra-evidence-agent Version 6，Kind 为 hosted"></div>

截图只证明部署对象、版本、状态和类型；进程恢复行为由 JSON 和日志证明。带登录态的原图和原始标识不会提交到仓库。

本仓库不证明 SLA、多轮可靠性、负载能力、多区域恢复、模型质量或外部操作的严格一次执行。长期任务韧性处于公共预览；没有针对实际任务完成专项测试前，不建议用于生产。

## 相关工作与许可证

- [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/)
- [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/)
- [长期任务韧性官方文档](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
- [包含 Python 和 .NET 的官方 API 参考](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-reference)

项目原创内容使用 [MIT 许可证](LICENSE)。微软官方图依据 CC BY 4.0 使用，不属于 MIT 许可证；详见[第三方声明](THIRD-PARTY-NOTICES.md)。
