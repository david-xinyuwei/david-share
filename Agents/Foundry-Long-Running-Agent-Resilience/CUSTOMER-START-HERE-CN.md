# 长任务 Agent 韧性：客户快速入口

这是把“进程丢失后继续执行”接入 Microsoft Foundry Hosted Agent 的最短完整路径，覆盖服务端、进度保存方式、Azure 部署、可选的外部状态存储、客户端行为和恢复验收。

**中文** | [English](CUSTOMER-START-HERE.md) | [完整技术证据](README-CN.md)

## 支持的路径

`本仓库的 Hosted Agent -> 已保存的后台响应 -> 阶段检查点 -> 主动终止进程 -> 同一个响应 ID 完成`

现在的可运行主路径完全由本仓库提供：

| 文件 | 作用 |
|---|---|
| [`hosted-agent/azure.yaml`](hosted-agent/azure.yaml) | 把 `lra-evidence-agent` 部署为 Python 3.13、Responses `2.0.0` 协议的 Hosted Agent |
| [`hosted-agent/src/lra-evidence-agent/main.py`](hosted-agent/src/lra-evidence-agent/main.py) | 完整可执行处理函数：五个确定性阶段、每阶段一个检查点，以及一次受控硬退出 |
| [`hosted-agent/client.py`](hosted-agent/client.py) | 创建并保存后台响应、保存响应 ID、轮询同一个 ID；发现缺口、重复、单进程“恢复”或终态不完整时直接失败 |
| [`hosted-agent/run_local_recovery.py`](hosted-agent/run_local_recovery.py) | 启动进程 A、核对退出码 86，再用相同状态目录启动进程 B，并验收完整结果 |

Agent 明确使用 `ResponsesServerOptions(resilient_background=True)`、`set_resilient_tasks_enabled(True)`、`context.persisted_response`、`stream.checkpoint()` 和 `context.exit_for_recovery()`。

微软在 `b9b2cdd` 的 [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) 样例只保留为固定版本的公共 API 参考，不再是本仓库的可执行主路径。它使用的 `2.1.0b2` 依赖**不能**替换成本仓库历史离线检查使用的 `2.0.0`。

### 先选进度保存方式

| 策略 | 要另配进度存储吗 | 适用场景 |
|---|---|---|
| 安全重跑 | 不需要 | 整个处理函数执行成本低，而且可以安全重复 |
| Responses 检查点 | 已完成的响应输出不需要另建数据库 | 进度就是同一个响应中的分段输出 |
| 应用或框架检查点 | 需要 | 业务状态、审批、大文件、写入、付款、预订或工具状态必须保留 |

Foundry 负责持久化任务身份、输入、租约，以及已保存响应中的事件，但不会自动保存任意业务状态。

### 前置条件

| 前置项 | 配置 |
|---|---|
| Azure | 非生产订阅；这个确定性 Agent 需要 Foundry 项目，但不需要模型部署 |
| 权限 | 项目范围的 `Foundry Project Manager`；新建项目还需要资源组范围的 `Owner` |
| 工具 | Python 3.13、Azure CLI 2.80+、Azure Developer CLI（`azd`）1.27.1+、Git |
| 登录 | `az login`、`azd ext install microsoft.foundry`、`azd auth login` |
| 软件包 | [`hosted-agent/src/lra-evidence-agent/requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt) 把 core 和 Responses 固定为 `2.1.0b2` |

### 先在本机证明恢复

从仓库根目录执行：

```powershell
python -m venv .venv-owned-agent
$python = (Resolve-Path .\.venv-owned-agent\Scripts\python.exe).Path
& $python -m pip install -r hosted-agent\src\lra-evidence-agent\requirements.txt
& $python hosted-agent\run_local_recovery.py --python $python
```

只有以下条件同时满足才算通过：进程 A 以退出码 `86` 结束；进程 B 报告 `recovered`；同一个响应中的阶段 `0-4` 各完成一次。[本地证据](evidence/owned-hosted-agent-local.json) 只保存响应 ID 和进程实例 ID 的哈希，不公开原值。

### 部署并运行线上故障测试

该测试会主动结束自己的进程，因此必须使用隔离的非生产项目：

```powershell
Set-Location .\hosted-agent
azd env new <environment-name> `
  --subscription <subscription-id> `
  --location <supported-region> `
  --no-prompt
azd env set LRA_ENABLE_FAULT_INJECTION true
azd env set LRA_STAGE_DELAY_MS 500
azd provision
azd deploy

$agent = azd ai agent show lra-evidence-agent --output json |
  ConvertFrom-Json
python .\client.py `
  --endpoint $agent.agent_endpoints.responses `
  --auth azure-cli `
  --agent-version $agent.version `
  --deployed-content-sha256 $agent.definition.code_configuration.content_hash `
  --work-id owned-agent-live-001 `
  --payload "public-safe live recovery workload" `
  --crash-after-stage 1 `
  --deadline-seconds 360
```

本仓库的实测使用版本 `1`：首次状态为 `in_progress`；进程退出后出现一次读取超时；替代计算资源启动后，同一个响应由两个进程实例接力完成全部五个阶段，总耗时 **57.884 秒**。[线上证据](evidence/owned-hosted-agent-live.json) 只保存哈希，不保存端点、响应、进程、租户或订阅原始标识。

不做故障测试时，运行 `azd env set LRA_ENABLE_FAULT_INJECTION false` 和 `azd deploy`。该设置为 false 时，普通请求不能触发硬退出。

### 仅在需要时配置外部状态

每个业务任务至少保存一条持久化记录：

| 字段 | 用途 |
|---|---|
| `work_id` | 应用自己的稳定任务 ID 和主键 |
| `response_id` 或 `input_id` | 把业务任务映射到 Foundry 中的任务 |
| `completed_phase` | 最后一个已提交结果的阶段 |
| `state_ref` | JSON 状态或指向大文件的地址 |
| `idempotency_key` | 传给下游操作的稳定幂等键 |
| `status` | `running`、`completed`、`failed` 或 `needs_reconciliation` |
| `version` / ETag | 新进程接管后阻止旧进程继续写入 |
| `updated_at` | 审计和超时判断 |

1. 用 `azd env set CHECKPOINT_ENDPOINT <resource-endpoint>` 和 `azd env set CHECKPOINT_DATABASE <database-name>` 设置非敏感值。
2. 在 `azure.yaml` 的 Agent 服务下，用 `environmentVariables` 映射这些名称。
3. 使用所选 SDK 支持的身份认证方式（通常是 `DefaultAzureCredential`）；不要写入连接字符串。
4. 部署后运行 `azd ai agent show` 确认当前版本，在 Foundry 中打开 Hosted Agent 的 **Identity**，并为目标资源分配最小权限。例如，为单个 Blob 作用域授予 `Storage Blob Data Contributor`，或为一个 Cosmos DB 数据库/容器授予对应的数据面角色。
5. 用事务或 ETag 条件同时提交阶段结果与 `completed_phase`。
6. 用 `work_id + phase` 生成下游幂等键。如果目标既不支持幂等，也不能查询结果，就把不确定结果标为 `needs_reconciliation`，不要猜测。
7. `TaskContext.metadata` 只放阶段、幂等键或状态指针；不要存对话历史、模型输出、工具结果和大文件。

可运行的存储逻辑见 [`recovery_contract_demo.py`](scripts/recovery_contract_demo.py)。其中的 SQLite 实现包含租约/版本隔离、阶段结果与检查点原子提交、幂等和冲突重放拒绝。

### 配置调用方

| 动作 | 必须做到 |
|---|---|
| 创建 | 同时发送 `store=true` 和 `background=true`；可按需设置 `stream=true` |
| 保存 | 在向上游调用方确认成功前，保存 `response.id`、自己的 `work_id` 和截止时间 |
| 重连 | 请求 `GET /responses/{response_id}`，或用 `GET /responses/{response_id}?stream=true` 继续读取流 |
| 完成 | 同时要求明确终态和完整预期输出 |
| 创建结果未知 | 不要自动创建第二条响应；远端创建请求与本地保存 ID 不是一个原子事务，必须去重或对账 |

### 验收恢复

在 Linux、WSL2 或容器中，用 `SIMULATE_CRASH_AFTER_STAGE=0 azd ai agent run` 启动固定样例，创建已保存的后台响应；进程退出后，用相同的 `AGENTSERVER_STATE_ROOT` 重启，再查询同一个响应 ID。

所有预期阶段各出现一次，而且响应到达明确终态，才算通过。使用应用自有存储时，要在每个阶段提交前和提交后各注入一次故障：未提交阶段必须可以安全重跑，已提交阶段必须跳过，外部操作不能重复。

该能力处于公共预览，没有生产 SLA。宣称生产就绪前，请阅读[完整证据、故障边界和实测结果](README-CN.md)。
