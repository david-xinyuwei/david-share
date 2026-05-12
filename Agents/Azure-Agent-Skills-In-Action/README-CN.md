# Azure Agent Skills 实战评测

> 以第三方工程师视角，深度评测微软 Agent Skills 生态——覆盖架构拆解、实战工作流验证、平台粘性分析，以及全部 skill 分类的实测检验。

本仓库对以下两个微软官方仓库做了独立的、全面的工程评测：

- **[microsoft/azure-skills](https://github.com/microsoft/azure-skills)** (v1.1.39) — Azure Skills Plugin，包含 26 个顶层 skill、Azure MCP Server、Foundry MCP。
- **[microsoft/skills](https://github.com/microsoft/skills)** — Agent Skills 总仓库，包含 174 个 skill（Python、.NET、TypeScript、Java、Rust），以及 deep-wiki、azure-skills 等 plugin、自定义 Agent、Prompt 和 MCP 配置。

本 Repo 的目标不是复述官方 README，而是回答一个真实工程团队在大规模采用前会问的问题：

1. **真实架构长什么样？** — 不是营销话术，而是各组件实际如何连接。
2. **部署工作流是否真正有效？** — `prepare → validate → deploy` 声称是硬门控流程，我们做了追踪验证。
3. **平台粘性在哪里？** — 哪些 skill 一旦使用，就难以脱离微软生态？
4. **有什么没覆盖？** — 比如 Office/Word 自动化、非 Azure 云。
5. **团队应该如何选择性采用？** — 不是所有 skill 都需要安装。

## 架构全景

Azure Skills Plugin 不是一个 prompt 包。它是一个三层能力栈，能把通用编码 Agent 变成 Azure 专用操作员。

<div align="center"><img src="images/architecture-overview.png" width="720"/></div>

| 层级 | 组件 | 功能 | 规模 |
|:----:|------|------|:----:|
| **大脑** | 26 个 Azure Skills（31 个 SKILL.md） | 决策树、工作流、Guardrails | 613 个文件 |
| **双手** | Azure MCP Server（`@azure/mcp@latest`） | 跨 40+ Azure 服务的 200+ 结构化工具 | 实时 Azure 操作 |
| **AI 专家** | Foundry MCP（通过 Azure MCP 的 `foundry` 工具入口） | 模型目录、Agent 生命周期、评估 | Foundry 原生 |

**关键发现**：README 中提到的 "Foundry MCP" 并不是 `.mcp.json` 中的独立 MCP server。它通过 Azure MCP Server 的 `foundry` 工具入口暴露。所有插件目录下的 `.mcp.json` 只配置了一个 server：

```json
{
  "mcpServers": {
    "azure": {
      "command": "npx",
      "args": ["-y", "@azure/mcp@latest", "server", "start"]
    }
  }
}
```

来源: [.mcp.json](https://github.com/microsoft/azure-skills/blob/main/.mcp.json)

## 完整 Skill 清单

### Azure Skills Plugin（26 个顶层 skill）

下表列出 `microsoft/azure-skills` 中每个 skill 的文件数（衡量深度/复杂度的代理指标）和核心功能。

| 分类 | Skill | 文件数 | 功能 |
|------|-------|:------:|------|
| **构建与部署** | `azure-prepare` | 164 | 分析工作区、规划架构、生成基础设施代码（Bicep/Terraform/AZD）、编写 `deployment-plan.md` |
| | `azure-validate` | 17 | 部署前验证：配置、RBAC、Managed Identity、构建检查 |
| | `azure-deploy` | 41 | 执行部署并带有错误恢复（`azd up`、`terraform apply`、`az deployment`） |
| | `azure-upgrade` | 31 | 升级计划/层级/SKU，Azure Java SDK 现代化 |
| | `azure-cloud-migrate` | 31 | 跨云迁移：AWS Lambda→Functions、Beanstalk→App Service、Fargate→Container Apps |
| **平台与基础设施** | `azure-compute` | 23 | VM 选型建议、自动缩放、连接故障排查 |
| | `azure-kubernetes` | 11 | AKS 集群规划：Automatic vs Standard、网络、安全 |
| | `airunway-aks-setup` | 11 | AKS 上的 AI Runway：GPU 调度、模型服务、推理部署 |
| | `azure-storage` | 14 | Blob、File Share、Queue、Table、Data Lake；层级比较和生命周期管理 |
| | `azure-messaging` | 1 | Event Hubs 和 Service Bus SDK 问题排查 |
| | `azure-kusto` | 1 | Azure Data Explorer / KQL 查询 |
| **运维与成本** | `azure-diagnostics` | 29 | 生产问题排查：App Service、Container Apps、Functions、AKS、消息服务 |
| | `appinsights-instrumentation` | 13 | 为 Web 应用添加 Application Insights 遥测 |
| | `azure-cost` | 21 | 查询成本、预测支出、优化浪费、发现孤立资源 |
| | `azure-quotas` | 3 | 检查/管理 Azure 配额 |
| | `azure-compliance` | 16 | Azure Quick Review (azqr)、合规扫描、资源图审计 |
| **身份与权限** | `azure-rbac` | 1 | 查找最小权限 RBAC 角色，生成 CLI/Bicep 赋权命令 |
| | `entra-app-registration` | 17 | Entra ID 应用注册、OAuth 2.0、MSAL 集成 |
| | `entra-agent-id` | 7 | 通过 Microsoft Graph 创建 Agent Identity Blueprint，用于 AI Agent OAuth |
| **资源与架构** | `azure-resource-lookup` | 2 | 使用 Resource Graph 跨订阅查找 Azure 资源 |
| | `azure-resource-visualizer` | 4 | 从实时 Azure 资源组生成 Mermaid 架构图 |
| | `azure-enterprise-infra-planner` | 35 | 设计企业级基础设施：Landing Zone、Hub-Spoke、多区域 DR、WAF 对齐 |
| **AI 与 Foundry** | `azure-ai` | 16 | Azure AI Search、Speech、OpenAI、Document Intelligence |
| | `azure-aigateway` | 9 | APIM 作为 AI 网关：语义缓存、Token 限制、内容安全、负载均衡 |
| | `azure-hosted-copilot-sdk` | 6 | 在 Azure 上构建 GitHub Copilot SDK 应用 |
| | `microsoft-foundry` | 89 | Foundry Agent 平台：模型部署、Agent 创建/部署/调用/评估/追踪/排障 |

### microsoft/skills 总仓库（174 个 skill）

更大的 `microsoft/skills` 仓库将 `azure-skills` 作为 plugin 包含，并按语言组织 SDK 级别的 skill：

| 语言 | 数量 | 关键分类 |
|------|:----:|---------|
| **Core** | 10 | Cloud Solution Architect、Copilot SDK、MCP Builder、Skill Creator、Frontend Design Review |
| **Foundry** | 11 | Router、Projects、Resources、Models、Hosted Agents、Toolboxes、Workflows、IQ Knowledge Bases、Memory、Observability、Governance |
| **Python** | 39 | Foundry AI (5)、M365 (1)、AI Services (8)、Data & Storage (7)、Messaging (4)、Entra (2)、Monitoring (4)、Integration (5)、Patterns (3) |
| **.NET** | 29 | Foundry AI (6)、M365 (1)、Data & Storage (6)、Messaging (3)、Entra (3)、Compute & Integration (6)、Monitoring (3) |
| **TypeScript** | 25 | Foundry AI (6)、M365 (1)、Data & Storage (5)、Messaging (3)、Entra & Integration (4)、Monitoring & Frontend (5)、Infrastructure (1) |
| **Java** | 26 | Foundry AI (7)、Communication (5)、Data & Storage (3)、Messaging (3)、Entra (3)、Monitoring & Integration (5) |
| **Rust** | 7 | Entra (4)、Data & Storage (2)、Messaging (1) |

来源: [microsoft/skills README](https://github.com/microsoft/skills) — 2026-05-11 核查。

## 深度拆解：部署工作流

`azure-prepare → azure-validate → azure-deploy` 流水线是 skills 生态中最有"主见"的部分。它在各阶段之间强制设置硬门控。

<div align="center"><img src="images/deploy-workflow.png" width="720"/></div>

### 工作机制

**阶段 1：azure-prepare**（164 个文件——规模最大的 skill）

1. **强制首要动作**：在生成任何代码之前，先将 `.azure/deployment-plan.md` 骨架文件写入磁盘。
2. 分析工作区 → 收集需求 → 选择 recipe（AZD/Bicep/Terraform）→ 规划架构。
3. 生成基础设施代码、Dockerfile、`azure.yaml`。
4. 向用户展示计划 → 获得批准 → 将状态设为 `Ready for Validation`。
5. **硬性规则**：`azure-prepare` 不得执行任何部署命令，只生成制品。

**阶段 2：azure-validate**（17 个文件）

1. 读取 `deployment-plan.md`——如果不存在，立即停止并调用 `azure-prepare`。
2. 运行 recipe 特定的验证命令（如 `azd provision --preview`、`bicep build`、`terraform validate`）。
3. 构建验证——编译/构建项目。
4. 静态 RBAC 角色检查——审查 Bicep/Terraform 中的角色分配是否正确。
5. 在 `deployment-plan.md` 第 7 节记录验证证据。
6. **只有 azure-validate 有权将状态设为 `Validated`**。azure-deploy 被明确禁止这样做。

**阶段 3：azure-deploy**（41 个文件）

1. 检查计划状态 = `Validated` 且验证证据节不为空。
2. 部署前检查清单（Container Apps + ACR RBAC 健康检查）。
3. 执行部署，带有内置的错误恢复机制。
4. 部署后：SQL Managed Identity + EF 迁移。
5. 实时 RBAC 验证。
6. 报告端点 URL（必须带 `https://` 前缀）。

### 这个设计好在哪里

- **计划文件是唯一的事实来源**。三个 skill 都读写 `.azure/deployment-plan.md`，避免了阶段间的状态漂移。
- **验证证据是强制的**。validate skill 必须记录执行了什么命令和结果。deploy 会检查这一节是否为空。
- **破坏性操作需要用户明确批准**（通过 `ask_user` 工具）。
- **SQL Server**：永远不生成 `administratorLogin` 或 `administratorLoginPassword`，无条件使用 Entra-only 认证。
- **专业路由**：如果用户提到 copilot SDK、Azure Functions、APIM 或 durable workflows，azure-prepare 会先路由到专门的 skill。

### 需要注意的地方

- `azure-prepare` 有 164 个文件，功能极其全面但也非常有"主见"。已有部署流水线的团队可能会发现它与现有工作流冲突。
- `@azure/mcp@latest` 版本未锁定。生产环境中建议锁定到具体版本。
- 强制计划文件的方式给简单的一次性部署增加了开销，适合非平凡的多服务 Azure 部署场景。

## 深度拆解：Foundry Agent 生命周期

`microsoft-foundry` skill（89 个文件）覆盖了 AI Agent 开发的完整生命周期：

| 阶段 | 子 Skill | 功能 |
|------|---------|------|
| **Create** | `foundry-agent/create` | 使用 Microsoft Agent Framework、LangGraph 或自定义框架创建新 Agent（Python/C#） |
| **Deploy** | `foundry-agent/deploy` | 容器化 → ACR 推送 → 创建/更新 hosted agent 部署 |
| **Invoke** | `foundry-agent/invoke` | 向 Agent 发送消息，单轮和多轮对话 |
| **Observe** | `foundry-agent/observe` | 批量评估、Prompt 优化、回归检测、CI/CD 监控 |
| **Trace** | `foundry-agent/trace` | 查询 App Insights `customEvents`，将评估结果关联到具体响应 |
| **Troubleshoot** | `foundry-agent/troubleshoot` | 查看 hosted agent 日志、查询遥测数据、诊断故障 |
| **FAOS Optimize** | `foundry-agent/faos-optimize` | 将现有代码转换为 FAOS 优化就绪版本 |
| **Eval Datasets** | `foundry-agent/eval-datasets` | 从生产追踪数据中提取评估数据集，版本管理 |

工作区标准要求一个 `.foundry/` 目录：

```
<agent-root>/
  .foundry/
    agent-metadata.yaml
    agent-metadata.prod.yaml
    datasets/
    evaluators/
    results/
```

**关键设计选择**：Foundry skill 使用 Azure MCP 的 `foundry` 工具作为主要入口。只有在 MCP 工具不可用时才回退到 SDK（`azure-ai-projects`）。

### Foundry Skills：azure-skills vs microsoft/skills

`azure-skills` 中的 `microsoft-foundry` skill（89 个文件）是一个单体编排器。而 `microsoft/skills` 仓库将其重构为 11 个聚焦的、语言无关的子 skill：

| microsoft/skills 子 Skill | 对应 azure-skills 中的 | 新增能力 |
|--------------------------|---------------------|--------|
| `foundry-projects-resources` | `microsoft-foundry` project/create + resource/create | 专用项目创建和资源配置 |
| `foundry-models` | `microsoft-foundry` models/deploy-model | 模型发现、PTU vs 按需付费 |
| `foundry-hosted-agents` | `microsoft-foundry` foundry-agent/deploy | 容器化 Agent 管理 |
| `foundry-toolboxes` | 新增 | MCP 兼容的工具包（preview） |
| `foundry-iq-knowledge-bases` | 新增 | Agentic 检索管道（preview） |
| `foundry-workflows` | 新增 | 多 Agent 编排 |
| `foundry-managed-skills` | 新增 | 将 SKILL.md 作为 Foundry 端资源（preview） |
| `foundry-memory` | 新增 | 长期 Agent 记忆（preview） |
| `foundry-observability` | `microsoft-foundry` foundry-agent/observe + trace | App Insights 中的 OpenTelemetry 追踪 |
| `foundry-governance` | 新增 | 舰队治理、RAI 策略、工具目录 |

如果你在构建 Foundry Agent，`microsoft/skills` 的 Foundry 子 skill 比 `azure-skills` 中的单体 `microsoft-foundry` 提供更精细的控制。

## 深度拆解：成本管理

`azure-cost` skill（21 个文件）分为三个子工作流：

| 子工作流 | 参考文件 | 用途 |
|---------|---------|------|
| **Cost Query** | `cost-query/workflow.md` | 通过 Cost Management REST API 查询历史成本 |
| **Cost Optimization** | `cost-optimization/workflow.md` | 发现孤立资源、VM 调优、Redis/AKS 分析 |
| **Cost Forecast** | `cost-forecast/workflow.md` | 使用 forecast API 预测未来支出 |

**强制规则**：
- 必须先查实际成本数据——不允许估算或假设。
- 展示优化建议时必须同时展示总账单。
- 使用 REST API（`az rest`）查询成本，不要用 `az costmanagement query`。
- 所有 Cost Management API 请求必须包含 `ClientType: GitHubCopilotForAzure` header。
- 遇到 429 响应时，等待最长的 `x-ms-ratelimit-microsoft.costmanagement-*-retry-after` header 值。

## 深度拆解：身份层

身份相关 skill 产生最深的平台粘性：

| Skill | 作用范围 | 关键能力 |
|-------|---------|---------|
| `azure-rbac` | 角色分配 | 查找最小权限角色，生成 CLI/Bicep 赋权命令 |
| `entra-app-registration` | 应用身份 | OAuth 2.0 流程、MSAL、Microsoft Graph 权限、Bicep 应用注册 |
| `entra-agent-id` | Agent 身份 | 通过 Graph API 创建 Agent Identity Blueprint，OAuth Token 交换（fmi_path、OBO、跨租户）、AgentID sidecar |

一旦组织的身份模型建立在 Entra ID + Managed Identity + RBAC + Agent Identity 上，迁移到其他云的身份系统意味着重建整个权限图谱，而不仅仅是更换 SDK 导入语句。

## 平台粘性分析

不是所有粘性都一样。以下是从浅到深的四层模型：

<div align="center"><img src="images/platform-stickiness.png" width="720"/></div>

| 层级 | 粘性程度 | 迁移成本 | 被锁定的内容 |
|:----:|:-------:|:-------:|------------|
| **开发体验** | 低 | 逐文件替换 SDK | Azure SDK import 模式、认证模式、错误处理 |
| **基础设施与部署** | 中等 | 重写 IaC + 部署流水线 | Bicep/Terraform 指向 Azure 服务、azure.yaml、Container Apps/Functions 配置 |
| **AI Runtime** | 高 | 从头重建 | Foundry Agent 运行时、评估流水线、可观测性、Toolboxes、Memory |
| **身份** | 非常高 | 重建组织权限图谱 | Entra ID、RBAC 分配、Managed Identity、Agent Identity、Graph API 权限 |

**粘性链**：Azure SDK skills → azure-prepare/validate/deploy → Entra/RBAC → Monitor/App Insights → Foundry Agent 生命周期 → M365/Teams/Copilot Studio。

一旦整条链落地，微软就从"云资源供应商"变成了客户的**开发、部署、身份、AI、观测、治理、协作入口**——不仅仅是一个云平台。

## 未覆盖的领域

这些 skill 聚焦于 Azure 云开发和 AI Agent 工作流。以下领域明确不在覆盖范围内：

| 类别 | 状态 | 说明 |
|------|:----:|------|
| **Office/Word/Excel 自动化** | 未覆盖 | 没有 DOCX 生成、编辑、排版或修订追踪相关 skill |
| **非 Azure 云** | 未覆盖 | `azure-cloud-migrate` 帮助迁移到 Azure，而非从 Azure 迁出 |
| **移动开发** | 未覆盖 | 没有 iOS/Android/React Native skill |
| **前端框架** | 部分覆盖 | Core skills 中有 `frontend-design-review`，但没有 React/Vue/Angular SDK skill |
| **数据库管理** | 部分覆盖 | Cosmos DB 和 SQL 的部署/RBAC 有覆盖，但查询优化和 schema 设计没有 |
| **网络深度** | 部分覆盖 | `azure-enterprise-infra-planner` 在架构层覆盖 VNet/NSG/防火墙，但不涉及报文级排查 |

`microsoft/skills` 中的 `m365-agents-py/dotnet/ts` skill 是用来构建**运行在 M365/Teams/Copilot Studio 上的 Agent**，不是用来操作 Office 文档。

`azure-ai-translation-document-py` skill 可以翻译 Word/PDF/Excel 文件并保留格式，但这是翻译服务，不是文档自动化工具。

## 安装与验证

### 快速安装（APM——推荐）

```bash
apm install microsoft/azure-skills
```

### VS Code

安装 [Azure MCP Extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azure-mcp-server)——会自动安装配套的 skills extension。

### Copilot CLI

```bash
/plugin marketplace add microsoft/azure-skills
/plugin install azure@azure-skills
```

### Claude Code

```bash
/plugin install azure@claude-plugins-official
```

### 验证（三项检查）

1. **Skills 层**：问 "What Azure services would I need to deploy this project?" → 期望获得结构化的 Azure 指导。
2. **Azure MCP**：问 "List my Azure resource groups." → 期望从你的 Azure 账户获得真实的工具响应。
3. **Foundry MCP**：问 "What AI models are available in Microsoft Foundry?" → 期望获得 Foundry 后端的响应。

### 前置条件

- Azure 账户 + 订阅
- Node.js 18+（需要 `npx`）
- Azure CLI（`az login`）
- Azure Developer CLI（`azd auth login`）用于部署工作流

## 选择性采用最佳实践

> **"加载所有 skill 会导致上下文腐化：注意力稀释、token 浪费、模式混淆。"**
> — microsoft/skills README

不是每个团队都需要每个 skill。以下是选择指南：

| 如果你的团队需要... | 安装这些 Skill | 可以跳过 |
|-------------------|--------------|---------|
| 部署应用到 Azure | `azure-prepare`、`azure-validate`、`azure-deploy` | Foundry skill（除非构建 AI Agent） |
| 在 Foundry 上构建 AI Agent | `microsoft-foundry` + Foundry 子 skill | `azure-cloud-migrate`、`azure-upgrade` |
| 管理成本和合规 | `azure-cost`、`azure-compliance`、`azure-quotas` | `azure-kubernetes`、`airunway-aks-setup` |
| 企业级基础设施 | `azure-enterprise-infra-planner`、`azure-compute` | SDK 级 skill（Python/Java 等） |
| 身份和安全 | `azure-rbac`、`entra-app-registration`、`entra-agent-id` | `azure-ai`、`azure-aigateway` |
| 排查生产问题 | `azure-diagnostics`、`appinsights-instrumentation` | `azure-hosted-copilot-sdk` |

## 实测验证：运行 Azure MCP Server

本仓库中的所有声明都通过实际运行 Azure MCP Server（`@azure/mcp@latest`）并通过 JSON-RPC 调用其工具进行了验证。测试脚本在 `scripts/`，原始输出在 `evaluation/results/`。

### 环境

| 组件 | 版本 |
|------|------|
| Node.js | v22.22.2 |
| npx | 10.9.7 |
| Azure CLI | 已登录（AI GBB - AI Infra 订阅） |
| Azure MCP | `@azure/mcp@latest`（通过 npx 自动下载） |
| 平台 | Ubuntu 24.04 on Azure VM |

### 测试 1：MCP Server 实际暴露了多少工具？

README 声称“200+ 结构化工具覆盖 40+ Azure 服务”。我们调用 `tools/list` 并计数：

> **结果：63 个顶层工具**（不是 200+）。

每个顶层工具（如 `foundry`、`compute`、`storage`）是一个**复合工具**，通过 `learn` 机制暴露多个子命令。例如，`foundry learn` 返回了 **51,578 字符**的 JSON，描述了数十个子命令。所以“200+”指的是所有 63 个顶层工具的子命令总数——而不是 `tools/list` 中的 200 个独立工具。

**实际工具列表（63 个）**：

```
acr, advisor, aks, appconfig, applens, applicationinsights, appservice,
azd, azurebackup, azuremigrate, azureterraform, azureterraformbestpractices,
bicepschema, cloudarchitect, communication, compute, confidentialledger,
containerapps, cosmos, datadog, deploy, deviceregistry, documentation,
eventgrid, eventhubs, extension_azqr, extension_cli_generate, extension_cli_install,
fileshares, foundry, foundryextensions, functionapp, functions,
get_azure_bestpractices, grafana, group_list, group_resource_list,
keyvault, kusto, loadtesting, managedlustre, marketplace, monitor,
mysql, policy, postgres, pricing, quota, redis, resourcehealth, role,
search, servicebus, servicefabric, signalr, speech, sql, storage,
storagesync, subscription_list, virtualdesktop,
wellarchitectedframework, workbooks
```

来源: `scripts/test_mcp_tools.js` → `evaluation/results/mcp_test_results.txt`

### 测试 2：subscription_list — 是否读取真实 Azure 数据？

```
>>> 调用 subscription_list

结果: {"status":200, "subscriptions":[
  {"displayName":"AI GBB - AI Services", "state":"Enabled"},
  {"displayName":"AI GBB - AI Infra", "state":"Enabled"},
  {"displayName":"GBB-Pulse", "state":"Enabled"}
]}
```

**结论**：真实 Azure 数据在 1 秒内返回。MCP server 使用本地 `az login` 凭据。

### 测试 3：group_list — 资源组盘点

使用订阅 ID 调用 `group_list` 返回了 **40+ 个资源组**，包含真实名称和位置（eastus2、southafricanorth 等）。确认 server 可以跨区域枚举 Azure 资源。

来源: `evaluation/results/mcp_test_v3.txt`

### 测试 4：foundry learn — 可用的 Foundry 子命令

使用 `{"command": "learn"}` 调用 `foundry` 返回了 51KB 的 JSON 数组，列出所有可用的 Foundry 子命令：

| 子命令 | 用途 |
|--------|------|
| `model_monitoring_metrics_get` | 获取模型部署的监控指标 |
| `model_similar_models_get` | 查找相似模型 |
| `prompt_optimize` | 使用 Azure OpenAI Prompt Optimizer 优化 prompt |
| `evaluation_agent_batch_eval_create` | 创建 Agent 批量评估 |
| `project_connection_delete` | 删除项目连接 |
| ... 以及更多 | |

**关键发现**：`foundry` 工具是一个**网关工具** — 它不直接执行任何操作。你用 `{"command": "learn"}` 发现子命令，然后用 `{"command": "<子命令>", "parameters": "..."}` 执行。这就是为什么 `.mcp.json` 只列了一个 `azure` server，但 README 声称“Foundry MCP”是单独一层 — 它是 `azure` server 内的一个逻辑层。

来源: `evaluation/results/mcp_test_v3.txt`

### 测试 5：compute learn — VM 管理子命令

使用 `{"command": "learn"}` 调用 `compute` 返回了 42KB 的 JSON 数组：

- `compute_vm_get` — 列出/获取 VM 详情（名称、大小、状态、操作系统）
- `compute_vm_create` — 创建 VM（等同于 `az vm create`）
- `compute_vm_resize` — 调整 VM 大小
- `compute_vmss_*` — 虚拟机规模集操作

来源: `evaluation/results/mcp_foundry_results.txt`

### 测试 6：工具命名规则发现

skill 的 SKILL.md 文件中引用工具时用 `mcp_azure_mcp_` 前缀（如 `mcp_azure_mcp_subscription_list`）。但通过 JSON-RPC 直接调用 server 时，工具名**没有前缀** — 只是 `subscription_list`、`group_list`、`foundry` 等。`mcp_azure_mcp_` 前缀是由宿主（VS Code、Copilot CLI）在工具注册时添加的。

### 实测总结

| 声明 | 验证？ | 实际结果 |
|------|:----:|--------|
| 200+ 结构化工具 | 部分验证 | 63 个顶层工具，每个含多个子命令 |
| 实时 Azure 操作 | ✅ | subscription_list 和 group_list 在 1 秒内返回真实数据 |
| Foundry MCP 作为单独层 | 已澄清 | `azure` server 内的逻辑层，通过 `foundry` 网关工具访问 |
| az login 凭据 | ✅ | Server 使用本地 Azure CLI 会话 |
| SKILL.md 中的工具命名 | 已澄清 | `mcp_azure_mcp_` 前缀由宿主添加，不是 server 本身 |

## 复现本分析

### 克隆源仓库

```bash
git clone --depth=1 https://github.com/microsoft/azure-skills.git /tmp/azure-skills
git clone --depth=1 https://github.com/microsoft/skills.git /tmp/skills
```

### 运行 skill 清单统计

```bash
# 统计所有 SKILL.md 文件
find /tmp/azure-skills/skills -name "SKILL.md" | wc -l
# → 31

# 按 skill 统计文件数（按复杂度排序）
for d in /tmp/azure-skills/skills/*/; do
  echo "$(find "$d" -type f | wc -l) $d"
done | sort -rn

# 总文件数
find /tmp/azure-skills/skills -type f | wc -l
# → 613
```

### 验证 .mcp.json 配置

```bash
cat /tmp/azure-skills/.mcp.json
cat /tmp/azure-skills/.github/plugins/azure-skills/.mcp.json
# 两者都应该只显示一个使用 @azure/mcp@latest 的 "azure" server
```

### 重新生成架构图

```bash
pip install Pillow
python images/generate_diagrams.py
```

## 项目信息

| 字段 | 值 |
|------|---|
| **作者** | 魏新宇 (Xinyu Wei) |
| **日期** | 2026-05-12 |
| **源仓库** | [microsoft/azure-skills](https://github.com/microsoft/azure-skills) v1.1.39、[microsoft/skills](https://github.com/microsoft/skills) |
| **数据核查日期** | 2026-05-11 |
| **许可证** | MIT |

## 相关仓库

[david-share/Agents](https://github.com/david-share/Agents) 下的其他仓库展示了特定 skill 的实战应用：

| 仓库 | 相关 Skills |
|-----|------------|
| [Azure-MCP-Solution](../Azure-MCP-Solution/) | Azure MCP Server 配置和使用模式 |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | `microsoft-foundry` hosted agents + toolboxes |
| [AI-Foundry-Agent-VNET-Deployment](../AI-Foundry-Agent-VNET-Deployment/) | Foundry Agent 私有网络部署 |
| [Foundry-IQ](../Foundry-IQ/) | Foundry IQ 知识库 |
| [Microsoft-Agent-Framework](../Microsoft-Agent-Framework/) | Microsoft Agent Framework 模式 |
| [AOAI-APIM-Gateway-LoadBalancing](../AOAI-APIM-Gateway-LoadBalancing/) | `azure-aigateway` APIM AI 网关场景 |

*Running on Azure*
