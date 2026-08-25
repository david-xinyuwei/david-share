# 长任务 Agent 韧性：客户快速入口

这是把“进程丢失后继续执行”接入 Microsoft Foundry Hosted Agent 的最短完整路径，覆盖服务端、进度保存方式、Azure 部署、可选的外部状态存储、客户端行为和恢复验收。

**中文** | [English](CUSTOMER-START-HERE.md) | [完整技术证据](README-CN.md)

## 支持的路径

`已保存的后台响应 -> 可恢复的 Hosted Agent -> 阶段检查点 -> 进程丢失后继续查询同一个响应 ID`

使用微软在 commit `b9b2cdd` 的可部署 [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) 样例，不要从自己拼出的残缺 `azure.yaml` 开始。

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
| Azure | 非生产订阅、Foundry 项目和模型部署 |
| 权限 | 项目范围的 `Foundry Project Manager`；新建项目还需要资源组范围的 `Owner` |
| 工具 | Python 3.13、Azure CLI 2.80+、Azure Developer CLI（`azd`）1.27.1+、Git |
| 登录 | `az login`、`azd ext install microsoft.foundry`、`azd auth login` |
| 软件包 | `pip install azure-ai-agentserver-core==2.1.0b2 azure-ai-agentserver-responses==2.1.0b2` |

固定样例的 [`azure.yaml`](https://github.com/microsoft-foundry/foundry-samples/blob/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming/azure.yaml) 已定义 `host: azure.ai.agent`、Responses 协议 `2.0.0`、Python `3.13` 和项目/模型依赖。

### 配置 Agent 处理函数

直接使用 [`examples/resilient_responses_agent.py`](examples/resilient_responses_agent.py) 中的完整可执行处理函数，只把 `run_stage()` 换成自己的一个完整工作阶段。

| 位置 | 必须设置 | 作用 |
|---|---|---|
| 服务端 | `ResponsesServerOptions(resilient_background=True)` | 让已保存的后台响应可以恢复 |
| 显式启用 | `set_resilient_tasks_enabled(True)` | 明确记录样例选择可恢复任务 |
| 恢复入口 | `context.is_recovery` + `context.persisted_response` | 载入最近一次响应快照 |
| 持久化边界 | 完整阶段后执行 `yield stream.checkpoint()` | 在下一阶段开始前提交已完成输出 |
| 关闭时交接 | `await context.exit_for_recovery()` | 把未完成任务交给后续进程 |

本例中，一个完整输出项对应一个阶段。如果阶段会修改外部系统，还要使用应用存储和幂等机制。

### 运行和部署

1. 运行 `git clone https://github.com/microsoft-foundry/foundry-samples.git`。
2. 运行 `git -C foundry-samples checkout b9b2cdd67efee6287e4b263f83ed45f18fe892be` 固定版本。
3. 进入 `foundry-samples/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming`。
4. 运行 `azd ai agent run` 做本地测试；端点是 `http://localhost:8088`。
5. 创建任务时同时设置 `store=true` 和 `background=true`，保存返回的响应 ID（`response.id`）。
6. 先运行 `azd provision`，再运行 `azd deploy`。
7. 运行 `azd ai agent invoke '{"input":"test recovery","store":true,"background":true}'`。
8. 运行 `azd ai agent monitor --follow` 查看日志。

样例默认模拟三个阶段，本地运行不需要模型凭据。调用真实模型时，替换 `_stage_tokens` 或 `run_stage()`，读取 Hosted Agent 自动注入的 `FOUNDRY_PROJECT_ENDPOINT`；不要把凭据提交到仓库。

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
