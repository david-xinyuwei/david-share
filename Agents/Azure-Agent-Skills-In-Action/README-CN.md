# Agent Skills 实战评测：Azure 是实跑样本

> 一份针对 Microsoft Agent Skills 生态的证据型工程评测。Azure 被选作实跑样本，是因为它有真实 MCP 工具、真实部署门控和可度量工作流；更大的主题是：`SKILL.md` 的 description、instructions、tools、agents、prompts 和 MCP configs 如何把通用 Coding Agent 变成面向任务的专业 Agent。

本仓库通过三个相关 Microsoft 仓库评估 Agent Skills 生态：

- **[microsoft/azure-skills](https://github.com/microsoft/azure-skills)** (v1.1.39) — Azure Skills Plugin，包含 26 个顶层 skill、Azure MCP Server 和 Foundry MCP。
- **[microsoft/skills](https://github.com/microsoft/skills)** — Agent Skills monorepo，包含 174 个跨 Python、.NET、TypeScript、Java、Rust 的 skill，以及 plugins（deep-wiki、azure-skills）、custom agents、prompts 和 MCP configs。
- **[MicrosoftDocs/Agent-Skills](https://github.com/MicrosoftDocs/Agent-Skills)** — 从 Azure Learn 文档生成的 skills：193 个 Azure skill，覆盖 19 个类别。

目标不是复述官方 README，而是展示这些 skills 实际能做什么、几个仓库的边界在哪里，以及真实团队除了 Azure 资源管理之外还能采用什么。

1. **什么东西会吸引 Agent 注意力？** — `description` 字段是第一层路由，不只是展示标签。
2. **哪个仓库覆盖什么？** — `MicrosoftDocs/Agent-Skills`、`microsoft/azure-skills`、`microsoft/skills` 不是一回事。
3. **除了 Azure 管理还能做什么？** — Issues、文档、前端评审、MCP Server、M365 Agent、SDK 代码、Foundry Agent、PPT。
4. **为什么用 Azure 做实跑样本？** — Azure 有具体 MCP Server、真实订阅调用，以及 read-only / side-effect 操作边界。
5. **什么时候才需要 `prepare → validate → deploy`？** — 只有创建或修改资源的部署类 skill 需要这套门控。
6. **团队应该如何选择性采用？** — 全部加载会造成 context rot，只安装当前项目真正需要的 skill。

## 执行摘要 PPT 预览

如果读者只有几分钟，先看这份 deck。它是本仓库最浓缩的执行摘要：14 页 PPTX，使用 `microsoft-docs` skill 生成，每个事实声明都回链到 `learn.microsoft.com` 或 GitHub 来源。可编辑 PPTX 在这里：[`slides/Azure-Agent-Skills-In-Action.pptx`](slides/Azure-Agent-Skills-In-Action.pptx)。

<div align="center"><img src="slides/preview/slide-01.png" width="780"/></div>

<details>
<summary>在 GitHub 中浏览全部 14 页预览</summary>

GitHub Markdown 不能内嵌真正可交互翻页的 PPTX viewer，所以本仓库把 deck 导出成静态 PNG，放在 [`slides/preview/`](slides/preview/) 下。需要重新生成时运行 [`slides/export_slide_preview.sh`](slides/export_slide_preview.sh)。

<div align="center">
  <img src="slides/preview/slide-01.png" width="780"/>
  <img src="slides/preview/slide-02.png" width="780"/>
  <img src="slides/preview/slide-03.png" width="780"/>
  <img src="slides/preview/slide-04.png" width="780"/>
  <img src="slides/preview/slide-05.png" width="780"/>
  <img src="slides/preview/slide-06.png" width="780"/>
  <img src="slides/preview/slide-07.png" width="780"/>
  <img src="slides/preview/slide-08.png" width="780"/>
  <img src="slides/preview/slide-09.png" width="780"/>
  <img src="slides/preview/slide-10.png" width="780"/>
  <img src="slides/preview/slide-11.png" width="780"/>
  <img src="slides/preview/slide-12.png" width="780"/>
  <img src="slides/preview/slide-13.png" width="780"/>
  <img src="slides/preview/slide-14.png" width="780"/>
</div>

</details>

## 先看 Skill Description

对客户来说，理解 skills 最快的方法不是看目录树，而是看 `description` 字段。Agent Skills 规范要求 `description` 同时说明 **这个 skill 做什么** 和 **什么时候使用**；progressive disclosure 机制会在启动时先加载 `name` 和 `description`，只有命中意图后才加载完整 `SKILL.md` 和资源文件。所以 description 是第一层路由入口。

| 客户怎么问 | 能抓住意图的 skill description | 说明了什么 |
|------------|-------------------------------|------------|
| “把这段事故记录整理成 GitHub issue。” | `github-issue-creator`: “Convert raw notes, error logs, or screenshots into structured GitHub issues.” | Skill 可以组织工程流程，不只是调云 API。 |
| “给内部系统写一个 MCP Server。” | `mcp-builder`: “Build MCP servers for LLM tool integration. Python (FastMCP), Node/TypeScript, or C#/.NET.” | Skill 可以教协议实现模式。 |
| “客户 demo 前帮我审一下 UI。” | `frontend-design-review`: “Review and create distinctive frontend interfaces. Design system compliance, quality pillars, accessibility, and creative aesthetics.” | Skill 可以编码产品和设计评审标准。 |
| “给这个 repo 生成 onboarding wiki。” | `deep-wiki`: “AI-powered wiki generator with Mermaid diagrams, source citations, onboarding guides, AGENTS.md, and llms.txt.” | Skill 可以生成文档体系，而不只是代码片段。 |
| “做一个 M365 Agent 应用。” | `m365-agents-py/dotnet/ts`: Microsoft 365 Agents SDK 的 hosting、routing、streaming、Copilot Studio client 模式。 | 生态已经延伸到协作型 Agent 开发，不只是 Azure ops。 |
| “把这个 workload 安全部署到 Azure。” | `azure-prepare`、`azure-validate`、`azure-deploy`: 先计划、再验证、最后部署真实资源。 | Azure 是最适合展示 live guardrail 的样本，因为它有真实副作用。 |

来源：[Agent Skills specification](https://agentskills.io/specification)、[microsoft/skills README](https://github.com/microsoft/skills)，2026-05-13 核查。

<div align="center"><img src="images/skills-ecosystem-map.png" width="960"/></div>

## 仓库边界：名字相似，范围不同

| 仓库 | 真实范围 | 应该怎么理解 | 不是 |
|------|----------|--------------|------|
| [`MicrosoftDocs/Agent-Skills`](https://github.com/MicrosoftDocs/Agent-Skills) | 从 Azure Learn 文档生成的 skills：193 个 Azure skill，覆盖 19 个类别。README 明确说这些 skills 是 specifically designed for Azure cloud development。 | 把 Azure 文档预编译成可加载的 skills。 | 通用 Office / Microsoft 365 / Word / Excel skill catalog。 |
| [`microsoft/azure-skills`](https://github.com/microsoft/azure-skills) | Azure operational plugin：26 个顶层 skill、Azure MCP Server、通过 Azure MCP `foundry` 入口暴露的 Foundry MCP。 | 资源操作和部署门控 plugin。 | 整个 Microsoft skills 生态。 |
| [`microsoft/skills`](https://github.com/microsoft/skills) | 174 个 skill，加上 plugins、custom agents、prompts、MCP configs、测试框架和 docs site。包含同步进来的 `azure-skills` plugin，也包含 SDK、Foundry、deep-wiki、M365 Agent、frontend、MCP-building skills。 | 更大的 Coding Agent skills monorepo。 | 只做“Azure 管理”。 |

从使用和分发角度看，**`microsoft/azure-skills` 是 `microsoft/skills` 的真子集**。但严格说，它不是普通父子源码关系：`microsoft/azure-skills` 是 Azure plugin 的 upstream / canonical source，`microsoft/skills` 里携带的是用于分发和组合的 synced copy。

证据：[`microsoft/skills/.github/plugin/marketplace.json`](https://github.com/microsoft/skills/blob/main/.github/plugin/marketplace.json) 声明 `azure-skills`，并把 `source` 指向 `./.github/plugins/azure-skills`；[`microsoft/skills/.github/CODEOWNERS`](https://github.com/microsoft/skills/blob/main/.github/CODEOWNERS) 把 `.github/plugins/azure-skills/` 标为 “Copilot for Azure skills plugin (synced from upstream)”；[`microsoft/skills/.github/plugins/azure-skills/README.md`](https://github.com/microsoft/skills/blob/main/.github/plugins/azure-skills/README.md) 从 `microsoft/azure-skills` 安装 Azure plugin。

## 宏观视角：这些 skills 到底怎么用

最重要的一点是：**所有 skill 并不共用同一套流程**。Skill 是面向特定任务的 instruction package。有些指导代码生成，有些整理文档，有些抓官方文档，有些调用只读 MCP 工具，只有部署相关 skill 才需要完整的 `prepare → validate → deploy` 门控流程。

| 使用模式 | 典型 Skills | 你怎么问 | Agent 做什么 | 是否需要完整部署门控 |
|----------|--------------|----------|--------------|:------------------:|
| **组织工程工作** | `github-issue-creator`, `deep-wiki`, `microsoft-docs`, `kql` | “创建 issue”“生成 wiki”“做带来源的 deck”“写 KQL” | 把松散输入整理成带来源或模板的结构化产出物 | 否 |
| **生成应用代码** | Python / .NET / TypeScript / Java / Rust SDK skills | “实现这个 SDK 模式” | 生成带认证、重试、遥测和服务约定的代码 | 否 |
| **评审产品界面** | `frontend-design-review`, `github-primer-brand` | “审 UI”“按品牌改页面” | 应用设计规范、可访问性、组件质量和视觉质量检查 | 否 |
| **构建 Agent 产品** | `copilot-sdk`, `m365-agents-*`, `microsoft-foundry`, Foundry 子 skill | “构建/部署/观测这个 Agent” | 指导 Agent app 结构、Toolbox、Memory、评估、追踪和路由 | 视场景而定 |
| **读取云状态** | `subscription_list`, `quota`, `pricing`, `role` 等 Azure MCP 只读工具 | “列订阅”“查配额”“看 RBAC” | 调用只读 MCP 工具，返回结构化 JSON | 否 |
| **部署 Azure 资源** | `azure-prepare`, `azure-validate`, `azure-deploy` | “把这个应用部署到 Azure” | 先写计划、再验证、最后创建或更新真实资源 | 是 |
| **有副作用的操作** | 迁移、通信、删除、创建、更新类操作 | “发送”“迁移”“删除”“创建” | 应要求明确批准，或由评测脚本阻断 | 逐项判断 |

所以下面的部署图**不是所有 skill 的默认用法**。它只适用于会创建或修改 Azure 资源的那一类 skill，是为了控制成本、安全和生产变更风险。

## Azure 证据栈：我们实际跑了什么

本仓库用 Azure 做实跑证据栈，是因为 Azure 有具体 MCP Server、真实资源 API，以及 read-only 和会修改资源的操作边界。这让它非常适合验证 skills 方法论。

Azure Skills Plugin 不是一个 prompt 包。它分三层，把一个通用 Coding Agent 变成 Azure 操作员。

<div align="center"><img src="images/architecture-overview.png" width="960"/></div>

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

更大的 `microsoft/skills` 仓库分发了一个同步进来的 `azure-skills` plugin，并按语言组织 SDK 级别的 skill：

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

## 深度拆解：Azure 部署工作流（仅适用于部署类 skill）

本节讨论的是一个特定使用模式：**创建或修改 Azure 资源**。`azure-prepare → azure-validate → azure-deploy` 流水线是 Azure 部署类 skill 中约束最强的一部分。它强制先写计划、再做验证、最后部署，并在阶段之间设置硬门控，因为部署操作会影响成本、安全和生产可用性。

<div align="center"><img src="images/deploy-workflow.png" width="960"/></div>

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

一旦组织的身份体系建在 Entra ID + Managed Identity + RBAC + Agent Identity 上，要换到别的云就意味着重建整个权限图谱——这可不是换个 import 语句的事。

## 平台粘性分析

不是所有粘性都一样。以下是从浅到深的四层模型：

<div align="center"><img src="images/platform-stickiness.png" width="960"/></div>

| 层级 | 粘性程度 | 迁移成本 | 被锁定的内容 |
|:----:|:-------:|:-------:|------------|
| **开发体验** | 低 | 逐文件替换 SDK | Azure SDK import 模式、认证模式、错误处理 |
| **基础设施与部署** | 中等 | 重写 IaC + 部署流水线 | Bicep/Terraform 指向 Azure 服务、azure.yaml、Container Apps/Functions 配置 |
| **AI Runtime** | 高 | 从头重建 | Foundry Agent 运行时、评估流水线、可观测性、Toolboxes、Memory |
| **身份** | 非常高 | 重建组织权限图谱 | Entra ID、RBAC 分配、Managed Identity、Agent Identity、Graph API 权限 |

**粘性链**：Azure SDK skills → azure-prepare/validate/deploy → Entra/RBAC → Monitor/App Insights → Foundry Agent 生命周期 → M365/Teams/Copilot Studio。

一旦整条链落地，微软就从"云资源供应商"变成了客户的**开发、部署、身份、AI、观测、治理、协作入口**——不仅仅是一个云平台。

## 范围边界

这份评测足够展示 Agent Skills 方法论，但并不等于每一种客户工作流都已经有官方 skill。

| 类别 | 状态 | 说明 |
|------|:----:|------|
| **PPTX 产出** | **已演示** | 我们用 `microsoft-docs` skill 加 `python-pptx` 生成了 14 页 PPTX，每个事实都引用自 learn.microsoft.com。详见[“配套幻灯片”章节](#配套幻灯片使用-microsoft-docs-技能生成)。 |
| **Office Word/Excel/PowerPoint 自动化** | 没有通用 skill set | 当前 repo 里没有通用的“帮我编辑 Word/Excel/PPT 文件”skill。本仓库的 PPTX 是一个被验证过的产出物工作流，不是原生 Office 自动化 skill。 |
| **M365/Teams/Copilot Studio agents** | Agent 应用开发有覆盖 | `m365-agents-py/dotnet/ts` skill 用来构建 M365/Teams/Copilot Studio Agent，不是文档编辑 skill。 |
| **文档翻译** | 部分覆盖 | `azure-ai-translation-document-py` 可以翻译 Word/PDF/Excel 并保留格式，但这是翻译服务，不是通用文档创作。 |
| **非 Azure 云** | 未覆盖 | `azure-cloud-migrate` 帮助迁移到 Azure，而非从 Azure 迁出。 |
| **移动开发** | 未覆盖 | 没有 iOS/Android/React Native skill。 |
| **前端框架** | 部分覆盖 | Core skills 中有 `frontend-design-review`，但没有 React/Vue/Angular SDK skill。 |
| **数据库管理** | 部分覆盖 | Cosmos DB 和 SQL 的部署/RBAC 有覆盖，但查询优化和 schema 设计没有。 |
| **网络深度** | 部分覆盖 | `azure-enterprise-infra-planner` 在架构层覆盖 VNet/NSG/防火墙，但不涉及报文级排查。 |

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

本节中的操作性结论都通过实际运行 Azure MCP Server（`@azure/mcp@latest`）并通过 JSON-RPC 调用其工具进行了验证。测试脚本在 `scripts/`，原始输出在 `evaluation/results/`。

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

**关键发现**：`foundry` 工具是一个**网关工具**。你用 `{"command": "learn"}` 发现子命令，然后用选定的 `command` 加上该命令需要的参数执行。这就是为什么 `.mcp.json` 只列了一个 `azure` server，但 README 声称“Foundry MCP”是单独一层 — 它是 `azure` server 内的一个逻辑层。

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
| Compute VM 列表 | ✅ | `compute_vm_get` 返回真实 VM：`gok-h100-post-training`（Standard_D2ads_v5，southafricanorth） |
| RBAC 执行 | ✅ | `group_resource_list` 对没有 Reader 角色的订阅返回 403 — MCP server 完全遵守 Azure RBAC |

### 核心架构发现：两类工具

通过反复试错测试，我们发现 MCP server 有**两种不同类型的工具**，参数传递方式不同：

| 工具类型 | 示例 | 参数风格 |
|---------|------|--------|
| **简单工具** | `subscription_list`、`group_list`、`group_resource_list` | `arguments` 中扁平传键值对 |
| **复合工具** | `compute`、`foundry`、`pricing`、`quota`、`role`、`monitor` | `arguments` 中使用 `command` + flat command arguments |

复合工具的使用方式：
1. 先用 `{"command": "learn"}` 发现可用子命令
2. 再用 `{"command": "<子命令>", ...requiredArguments}` 执行

这个两步“先学后执行”的模式**在 README 中没有记录**。本 Repo 的全量实跑用真实 Azure 数据验证了直接 JSON-RPC 的调用约定。

测试脚本和原始输出文件在 `scripts/` 和 `evaluation/results/` 中。

## 全量实跑：63 个 Azure MCP 顶层工具

这是本 Repo 最核心的证据。2026-05-12，我们使用 `scripts/run_full_value_evaluation.js` 在真实 Azure 订阅中跑了一轮全量评测：先发现所有 Azure MCP 顶层工具，再对需要的工具调用 `learn` 获取子命令 schema，自动选择安全的 read-only 命令执行，最后把 JSON、CSV 和 Markdown 证据落盘到 `evaluation/results/`。

### 测试环境

| 组件 | 值 |
|------|-----|
| 订阅 | `08f95cfd-...` (ME-MngEnv183724-xinyuwei-1) |
| 权限 | Owner |
| 资源组 | 30+ |
| VM | 8 |
| Cognitive Services 账户 | 19 |
| Log Analytics workspace | 20 |
| Storage 账户 | 10 |
| ML workspace | 8 |
| 测试脚本 | `scripts/run_full_value_evaluation.js` |
| 原始 JSON | `evaluation/results/full_value_evaluation.json` |
| 矩阵 CSV | `evaluation/results/full_value_matrix.csv` |
| Markdown 报告 | `evaluation/results/full_value_summary.md` |

### 结果汇总

| 结果 | 数量 | 含义 |
|------|-----:|------|
| **EXECUTED** | **45** | 安全 read-only 命令返回了真实 Azure 数据、空结果，或 MCP server 的可执行指导。 |
| **SCHEMA_VERIFIED** | **9** | 工具暴露了有效 schema，但安全执行需要本测试环境没有的具体资源输入。 |
| **TOOL_ERROR** | **5** | 工具可调用，但返回服务端/工具链错误；这些作为产品或前置条件问题记录下来。 |
| **BLOCKED_UNSAFE** | **2** | 相关命令有副作用，评测脚本故意不执行。 |
| **FAILED** | **2** | 评测脚本未能为该工具拿到有用的运行结果。 |

**覆盖说明**：63 个工具全部探测，45 个跑通了，54 个拿到了实跑结果或 schema，剩下几个的阻塞原因都记在文档里。

### 本轮实跑证明了什么

| 能力 | 已执行工具 | 证明点 |
|------|------------|--------|
| 订阅与资源盘点 | `subscription_list`, `group_list`, `group_resource_list` | MCP server 通过当前 Azure CLI 登录读取真实 Azure 状态。 |
| 计算与应用平台发现 | `compute_vm_get`, `aks_cluster_get`, `containerapps_list`, `appservice_webapp_get`, `functionapp_get` | Agent 不需要手写一串 `az` 查询，也能检查运行时基础设施。 |
| 成本、配额、价格 | `quota_usage_check`, `pricing_get`, `advisor_recommendation_list` | 对 quota、pricing、optimization 这类高摩擦 API，skill 明显降低查文档成本。 |
| IaC 与架构辅助 | `bicepschema_get`, `azureterraform_azurerm_get`, `azureterraformbestpractices_get`, `cloudarchitect_design` | Agent 能按需拉取 Bicep/Terraform schema 和架构建议。 |
| 治理与身份 | `role_assignment_list`, `policy_assignment_list`, `resourcehealth_availability-status_get` | RBAC、Policy、Resource Health 可以作为结构化证据返回。 |
| Azure 服务发现 | `storage_account_get`, `cosmos_list`, `sql_server_get`, `redis_list`, `search_service_list` | 同一个调用模式可以扫过多个 Azure 服务族。 |
| 开发工作流辅助 | `functions_language_list`, `get_azure_bestpractices_get`, `wellarchitectedframework_serviceguide_get`, `extension_cli_generate` | 它不只是列资源，还能返回工程指导和命令生成能力。 |

### 未完全执行的项目及原因

| 类型 | 工具 | 原因 |
|------|------|------|
| 需要具体资源实例 | `keyvault`, `servicebus`, `servicefabric`, `speech`, `foundryextensions`, `confidentialledger`, `datadog`, `mysql`, `deploy` | schema 有效，但安全执行需要 vault、queue、speech 文件、endpoint、cluster、ledger transaction、Datadog resource、MySQL user 或本地 azd workspace。 |
| 故意不执行 | `communication`, `azuremigrate` | 相关命令可能发送短信或引导环境变更，评测脚本只记录 schema，避免副作用。 |
| 产品/前置条件问题 | `extension_azqr`, `loadtesting`, `marketplace`, `applens`, `foundry` | 工具返回运行时错误或缺少前置工具；例如 `extension_azqr` 需要 PATH 中存在 `azqr`。 |
| 仍需补测试用例 | `applicationinsights`, `extension_cli_install` | 需要更精确的参数或更合适的环境。 |

### 已验证的调用约定

全量实跑还修正了一个直接 JSON-RPC 调用细节：对复合工具，直接调用 Azure MCP Server 时可用 **flat arguments + command**：

```js
send("compute", {
  command: "compute_vm_get",
  subscription: SUB,
  "resource-group": "winvm"
});
```

这和 SKILL.md 中看到的 `mcp_azure_mcp_*` 命名不同。前缀是 VS Code、Copilot CLI 等宿主注册工具时加的；裸 MCP server 暴露的是 `compute`、`quota`、`pricing`、`subscription_list`、`group_list` 这类名字。

## Skills vs 不用 Skills：实跑证明了什么

在决定是否采用这些 skill 之前，工程团队最关心的不是“MCP 能不能调 Azure”，而是：**跟纯 `az` CLI + 一个通用 LLM 比，多得到什么？**

### 具体对比示例

#### 示例 1：列订阅 — 两者都能跑，MCP 返回结构化数据

**不用 skills（az CLI）**：
```bash
$ time az account list --query "[].{name:name,id:id}" -o table
ME-MngEnv183724-xinyuwei-1
AI GBB - AI Services
AI GBB - AI Infra
GBB-Pulse
real    0m0.949s
```

**用 skills（MCP `subscription_list`）**：
```json
{"status":200,"results":{"subscriptions":[
  {"subscriptionId":"08f95cfd-...","displayName":"ME-MngEnv183724-xinyuwei-1","state":"Enabled","tenantId":"9812d5f8-..."}
]}}
```

**结论**：速度一样，但 MCP 返回结构化 JSON，可直接给 LLM 消费。

#### 示例 2：配额查询 — MCP 在复杂度上胜出

**不用 skills（手动调 REST API）**：
```bash
$ az rest --method GET --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Quota/usages?api-version=2023-02-01&\$filter=location%20eq%20'eastus'"
ERROR: Bad Request — 必须查清楚正确的 API 路径、版本、filter 语法
```

**用 skills（MCP `quota_usage_check`）**：
```js
exec("quota", "quota_usage_check", {
  subscription: SUB,
  region: "eastus",
  "resource-types": "Microsoft.CognitiveServices/accounts"
})
// → 18KB JSON：所有模型的 TPM/PTU 配额（gpt-4o、gpt-4o-mini、o1、o3 等）
```

**结论**：MCP 省了 30+ 分钟的 API 研究。Skill 知道正确的 API、版本、filter 格式、资源类型名。

#### 示例 3：用自然语言生成 az CLI — MCP 独有能力

**不用 skills**：必须记住 `az vm list --query "[?powerState=='deallocated']"` 语法和 JMESPath filter。

**用 skills（MCP `extension_cli_generate`）**：
```js
send("extension_cli_generate", {
  intent: "find all VMs that have been deallocated for more than 30 days in subscription " + SUB,
  "cli-type": "az"
})
```

**返回**：
```json
{
  "scenario": "Find all VMs that have been deallocated for more than 30 days...",
  "description": "List all virtual machines in the specified subscription that are in a deallocated state and filter them based on the deallocation duration.",
  "commandSet": [{
    "reason": "List all VMs in the subscription and filter for those that are deallocated.",
    "example": "az vm list --subscription 08f95cfd-... --query '[?powerState==`deallocated`]'",
    "command": "az vm list",
    "arguments": ["--subscription", "--query"]
  }]
}
```

**结论**：这是 skill 层真正增加价值的地方：不用 skill 也不是原则上做不到，但你需要一个懂 Azure CLI 的 LLM，或自己查文档，才能安全地产生同等命令。

### Skill 什么时候有用、什么时候不需要

从 63 个顶层工具实跑总结：

| Skill 占优势的场景 | Skill 帮不上忙的场景 |
|----------------------|----------------------|
| 调用复杂 API（quota、pricing、Resource Graph） | 简单资源列表（`az group list` 就够了） |
| 需要自然语言 → CLI 翻译 | 已经知道准确的 CLI 命令 |
| 需要结构化 JSON 给下游 LLM 处理 | 只要人读的 table 输出 |
| 需要跨服务架构推荐 | 只需单服务信息 |
| 想要 guardrail（如“总是先查实际成本”） | 想对每个参数完全控制 |

完整测试脚本和原始输出在 `scripts/run_full_value_evaluation.js`、`evaluation/results/full_value_evaluation.json`、`evaluation/results/full_value_matrix.csv`、`evaluation/results/full_value_summary.md` 和 `evaluation/cli_baseline/` 中。

## 配套幻灯片（使用 microsoft-docs 技能生成）

[`slides/Azure-Agent-Skills-In-Action.pptx`](slides/Azure-Agent-Skills-In-Action.pptx) 是使用 [microsoft/skills](https://github.com/microsoft/skills) 中的 **microsoft-docs 技能** 生成的 14 页 PPT：每一页上的每一个事实声明都引用自 [learn.microsoft.com](https://learn.microsoft.com)，生成时实时拉取，源 URL 显示在页脚。生成脚本 [`slides/gen_azure_skills_ppt_v2.py`](slides/gen_azure_skills_ppt_v2.py) 嵌入了所有源 URL，演示了该技能“查官方文档、不依靠记忆”的核心原则。

### 生成提示词（可复现）

在 GitHub Copilot 、Claude Code 等 Coding Agent 中加载 `microsoft-docs` 技能，然后使用以下提示词：

> **提示词模板**：
> ```
> 使用 microsoft-docs 技能，生成一份关于 "Azure Agent Skills In Action" 的 14 页执行摘要 PPTX。硬性要求：
>
>   1. 每一页的每一个事实声明必须引用自 learn.microsoft.com URL。
>   2. 使用 microsoft-docs 技能拉取源页面，**不准依赖记忆**。
>   3. 每一页页脚显示准确的源 URL（Consolas 字体，灰色，9pt）。
>   4. 关键定义使用**原文引用**（加引号），不要 paraphrase。
>   5. 使用 python-pptx，16:9 比例（宽 13.333" × 高 7.5"），微软品牌色。
>   6. 页面结构：
>        1.  封面
>        2.  方法论 —— 讲解 microsoft-docs 技能的工作流
>        3.  什么是 Azure MCP Server（/overview 原文）
>        4.  MCP 架构：Hosts/Clients/Servers（/overview#concepts）
>        5.  支持的编辑器和语言（/overview#supported-...）
>        6.  工具分类（/tools/）
>        7.  身份认证：Entra ID + RBAC（原文引用）
>        8.  官方使用场景（/overview#scenarios-...）
>        9.  我们的 63 工具实跑结果
>        10. Azure Skills Plugin（/overview#key-features 原文）
>        11. Python / .NET SDK（/get-started/languages/...）
>        12. How-to 指南目录（/how-to/...）
>        13. 结论：用与不用 microsoft-docs 技能的区别
>        14. 收尾——列出所有引用源 URL
>
>   输出：slides/Azure-Agent-Skills-In-Action.pptx + slides/gen_azure_skills_ppt_v2.py
> ```

该技能强制执行“查官方文档”原则，Agent 在写每一页之前都会通过 `fetch_webpage`（或 `microsoft_docs_search` MCP）拉取每个源 URL。**不用该技能**同样提示词会生成营销话术式内容，无法追溯来源。

GitHub 中的 slide 预览已前移到 README 顶部：[执行摘要 PPT 预览](#执行摘要-ppt-预览)。

### PPT 引用的所有源头（均于 2026-05-12 拉取）

| 页 | 源 URL |
|---:|--------|
| 3, 7, 8, 10 | `learn.microsoft.com/en-us/azure/developer/azure-mcp-server/overview` |
| 4 | `learn.microsoft.com/en-us/azure/developer/azure-mcp-server/overview#concepts` |
| 5 | `learn.microsoft.com/en-us/azure/developer/azure-mcp-server/overview#supported-code-editors-and-tools` |
| 6 | `learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/` |
| 11 | `learn.microsoft.com/en-us/azure/developer/azure-mcp-server/get-started/languages/python` |
| 12 | `learn.microsoft.com/en-us/azure/developer/azure-mcp-server/` |
| 2, 13 | `github.com/microsoft/skills/.github/skills/microsoft-docs/SKILL.md` |

## microsoft/skills — 技能验证矩阵（12 个 Core Skill × 三元组）

我们验证了 [microsoft/skills/.github/skills/](https://github.com/microsoft/skills/tree/main/.github/skills) 下**全部 12 个技能**——**用每个 skill 做一件真实的事，产出一个真实的东西**。下表每行就是一个**三元组**：怎么试 → 提示词关键约束 → 产出物 + 路径。

| # | Skill | 怎么试（一句话） | 提示词关键约束 | 产出物 + 路径 |
|---|-------|------------------|----------------|---------------|
| 1 | **cloud-solution-architect** | 用 7 步 WAF 审查工作流设计了一套生产级 RAG Agent 系统 | "走完所有 7 步；把设计模式映射到 WAF 5 维；输出 ADR" | 含 11 个技术选型、10 个设计模式、3 条 ADR 的架构文档 → [`skill-demos/cloud-solution-architect/architecture-design.md`](skill-demos/cloud-solution-architect/architecture-design.md) |
| 2 | **copilot-sdk** | 构建了带 Responses 协议的多 agent FastAPI 演示应用 | "用 Responses 协议；每个 agent 不同 tool 子集；输出解析链 `output[]→message→content[]→output_text`" | 完整 FastAPI server + 前端 → [`Foundry-Hosted-Agent-Toolbox-Demo/`](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo)；证据 → [`skill-demos/copilot-sdk/`](skill-demos/copilot-sdk/) |
| 3 | **frontend-design-review** | 用 5 维度质量框架审查了 Foundry Demo 的 726 行 `index.html` | "5 维度：Design System / Accessibility / Performance / Responsive / Aesthetics；每维评分；Top 3 可执行修复" | 评分报告（5.7/10），含 6 个 ARIA 缺陷、3 处响应式失败 → [`skill-demos/frontend-design-review/review-report.md`](skill-demos/frontend-design-review/review-report.md) |
| 4 | **github-issue-creator** | 把 6 行原始评测错误日志转为 3 个结构化 issue | "输出模板必须含：Summary / Environment / Reproduction Steps / Expected / Actual / Error Details / Impact / Context；严重度匹配实际影响" | 3 个标准 GitHub issue → [`skill-demos/github-issue-creator/generated-issues.md`](skill-demos/github-issue-creator/generated-issues.md) |
| 5 | **mcp-builder** | 构建 Python FastMCP server 暴露 63 工具实跑数据 | "FastMCP；统一 `eval_*` 前缀；`readOnlyHint: True`；用 `python -m py_compile` 验证" | 5 工具 MCP server（`eval_summary`、`eval_tool_result` 等） → [`skill-demos/mcp-builder/evaluation_mcp_server.py`](skill-demos/mcp-builder/evaluation_mcp_server.py) |
| 6 | **microsoft-docs** | 用 Learn URL 引用的方式重新生成 PPT | "每个声明必须引用 learn.microsoft.com；定义直接引用；每页页脚显示来源 URL" | 14 页 PPT，页脚都有 URL → [`slides/Azure-Agent-Skills-In-Action.pptx`](slides/Azure-Agent-Skills-In-Action.pptx) + 生成脚本 [`slides/gen_azure_skills_ppt_v2.py`](slides/gen_azure_skills_ppt_v2.py) |
| 7 | **skill-creator** | 为 "azure-mcp-evaluation" 方法论创建全新 SKILL.md | "frontmatter 含 name + description + applicability；含 USE FOR / DO NOT USE FOR 区段" | 完整 SKILL.md，含分类规则、调用约定、安全规则 → [`skill-demos/skill-creator/azure-mcp-evaluation-SKILL.md`](skill-demos/skill-creator/azure-mcp-evaluation-SKILL.md) |
| 8 | **applicationinsights-web-ts** | 为 Foundry Demo 仪表盘写 drop-in TypeScript 检测模块 | "用 `@microsoft/applicationinsights-web`（不是 Node 的 OTel 包）；`distributedTracingMode: 2` 关联后端；emit OTel GenAI 语义约定属性" | 含 W3C 追踪 + GenAI agent 追踪的 TS 模块 → [`skill-demos/applicationinsights-web-ts/appInsights.ts`](skill-demos/applicationinsights-web-ts/appInsights.ts) |
| 9 | **continual-learning** | 把本次评测教训沉淀为项目本地 learnings 文件 | "二级记忆（local 用于 repo 约定）；4 类：pattern / mistake / preference / tool_insight；具体到工具/参数/URL" | 含 14 条具体 lesson 的 `.copilot-memory/learnings.md` → [`skill-demos/continual-learning/learnings.md`](skill-demos/continual-learning/learnings.md) |
| 10 | **entra-agent-id** | 用 Graph beta API 写 Python 脚本配置 Entra Agent ID | "仅 Graph `/beta`（preview）；`ClientSecretCredential`（Default 返回 403）；BlueprintPrincipal 步骤强制；sponsor 必须是 User" | 3 步 provision 脚本（Blueprint → BlueprintPrincipal → Agent Identity） → [`skill-demos/entra-agent-id/provision_agent_identity.py`](skill-demos/entra-agent-id/provision_agent_identity.py) |
| 11 | **kql** | 写 7 条 App Insights 生产 agent 监控查询 | "dynamic 字段在 summarize/order/join 前必须 cast；时间用 `ago()`；延迟用 `percentile()` 不用 `avg()`；结果集大小有界" | 7 条 .kql 查询（日志 / 调用 / tool / token / 错误 / 延迟 / 分布式追踪） → [`skill-demos/kql/agent-monitoring.kql`](skill-demos/kql/agent-monitoring.kql) |
| 12 | **podcast-generation** | 用 GPT Realtime Mini 写 Python 脚本生成音频摘要 | "endpoint 不能含 `/openai/v1`；HTTPS→wss；`output_modalities=['audio']`；PCM 固定 24kHz/16-bit/mono；包 RIFF/WAVEfmt 头" | 异步 OpenAI Realtime WebSocket 脚本 → [`skill-demos/podcast-generation/generate_evaluation_podcast.py`](skill-demos/podcast-generation/generate_evaluation_podcast.py) |

加上 4 个 `microsoft-foundry` plugin 子技能：

| # | Skill | 怎么试 | 提示词关键约束 | 产出物 + 路径 |
|---|-------|--------|----------------|---------------|
| 13 | **foundry-hosted-agents** | 用 `azd up` 部署容器化 agent | "Dockerfile 容器化；ResponsesHostServer；每个 agent 独立 Entra 身份；通过 MCPStreamableHTTPTool 消费 Toolbox MCP" | `Foundry-Hosted-Agent-Toolbox-Demo/` 完整部署 → [`skill-demos/foundry-hosted-agents/`](skill-demos/foundry-hosted-agents/) |
| 14 | **foundry-models** | 部署 `gpt-4.1-mini` 按量付费并用 MCP 验证 | "demo 用按量付费；通过 `az cognitiveservices` + MCP `foundry` 工具验证；记录 quota check" | 部署证据 + MCP 验证 → [`skill-demos/foundry-models/`](skill-demos/foundry-models/) |
| 15 | **foundry-toolboxes** | 配置 `agent-tools` Toolbox，将 3 个 MCP 工具打成一个端点 | "单 MCP endpoint URL 模式；必须 `Foundry-Features: Toolboxes=V1Preview` 头；Bearer 用 `ai.azure.com` scope" | Toolbox 配置 + 实际端点 → [`skill-demos/foundry-toolboxes/`](skill-demos/foundry-toolboxes/) |
| 16 | **foundry-memory** | 集成 `FoundryMemoryProvider` 实现跨 session agent 记忆 | "FoundryMemoryProvider 作 context_provider；`scope` 多租户隔离；`allow_preview=True`；`MEMORY_STORE_NAME` 未设置时优雅降级" | 代码 + .env 接线 + 系统提示增强 → [`skill-demos/foundry-memory/`](skill-demos/foundry-memory/) |

> **每个 `skill-demos/<skill>/README.md` 都包含完整可复现的 prompt**，其他工程师拷贝粘贴到自己的 coding agent（加载同一 skill 后）就能复现产出物。

### 加上 7 个 `microsoft-foundry` 子技能

| # | Skill | 怎么试 | 提示词关键约束 | 产出物 + 路径 |
|---|-------|--------|----------------|---------------|
| 17 | **foundry-projects-resources** | 配置 Foundry 项目 + AI Services 账户；MCP `subscription_list` / `group_resource_list` 验证 | "`azd up`（不是手动门户）；连接用 managed identity；项目 endpoint 格式合规" | Bicep 模板 + MCP 验证 → [`skill-demos/foundry-projects-resources/`](skill-demos/foundry-projects-resources/) |
| 18 | **foundry-extensions** | 验证 `foundryextensions` MCP 复合工具；记录哪些子命令需要什么输入 | "走 `learn` 步骤；诚实标 SCHEMA_VERIFIED 还是 EXECUTED" | 评测矩阵记录（SCHEMA_VERIFIED，缺 endpoint）→ [`skill-demos/foundry-extensions/`](skill-demos/foundry-extensions/) |
| 19 | **foundry-workflows** | 设计多 agent 工作流（default/math-only/rag-only），Connected Agents 模式 | "Connected Agents 模式（声明式）；每个 agent 子集通过系统提示强制；按 `agent_id` 路由" | `Foundry-Hosted-Agent-Toolbox-Demo/app/server.py` AGENTS 注册表 → [`skill-demos/foundry-workflows/`](skill-demos/foundry-workflows/) |
| 20 | **foundry-iq-knowledge-bases** | 配置 `file_search` Toolbox 工具，让 agent 基于上传文档 grounding | "用 Foundry 向量存储 API（不直接调 AI Search）；项目 RBAC 控制权限；FILE_SEARCH_VECTOR_STORE_IDS 多源支持" | `main.py` + `.env.example` 接线 → [`skill-demos/foundry-iq-knowledge-bases/`](skill-demos/foundry-iq-knowledge-bases/) |
| 21 | **foundry-managed-skills** | 为 Foundry Skills REST API 上传准备一份可运行时加载的 SKILL.md | "一次作者 + 通过 REST 注册；**不**打包进 Docker；通过 PUT 版本化" | 来自 `skill-creator` demo 的 SKILL.md + cURL 上传模式 → [`skill-demos/foundry-managed-skills/`](skill-demos/foundry-managed-skills/) |
| 22 | **foundry-observability** | 浏览器 ↔ FastAPI ↔ Foundry 全链路 OTel GenAI traces 接入 App Insights，加 7 条 KQL | "OTel GenAI 语义约定；W3C trace context 跨三层；评估与 trace 通过 operation_Id 关联；用 KQL 不用门户" | 三件协同：`applicationinsights-web-ts/appInsights.ts` + `app/server.py` + `kql/agent-monitoring.kql` → [`skill-demos/foundry-observability/`](skill-demos/foundry-observability/) |
| 23 | **foundry-governance** | 用 MCP `role_assignment_list`（28KB EXECUTED）+ `policy_assignment_list`（12KB EXECUTED）审计治理姿态 | "用 Azure MCP 工具（不是裸 REST）；Entra Agent ID → SP → RBAC 链路；记录 AI Gateway 模式" | MCP 实跑结果 + Entra Agent ID 配置链路 → [`skill-demos/foundry-governance/`](skill-demos/foundry-governance/) |

### 加上 5 种语言 38 个 SDK 技能

我们验证了每个 azure-sdk-* plugin 中最基础的 SDK 技能。每种语言都有专门的 skill-demos 目录，含每个验证过的 skill 的三元组表。

| 语言 | 验证技能数 | 产出目录 |
|------|------------|----------|
| **Python** | 10（azure-ai-projects, azure-identity, azure-storage-blob, azure-cosmos, azure-search-documents, azure-servicebus, pydantic-models, agent-framework-azure-ai, fastapi-router, azure-monitor-opentelemetry） | [`skill-demos/sdk-python/`](skill-demos/sdk-python/) |
| **.NET** | 8（azure-ai-openai, azure-ai-projects, azure-identity, azure-search-documents, azure-servicebus, azure-resource-manager-cosmosdb, azure-resource-manager-sql, azure-security-keyvault-keys） | [`skill-demos/sdk-dotnet/`](skill-demos/sdk-dotnet/) |
| **TypeScript** | 8（azure-ai-projects-ts, azure-identity-ts, azure-storage-blob-ts, azure-cosmos-ts, azure-search-documents-ts, azure-servicebus-ts, azure-monitor-opentelemetry-ts, azure-keyvault-secrets-ts） | [`skill-demos/sdk-typescript/`](skill-demos/sdk-typescript/) |
| **Java** | 7（azure-ai-projects-java, azure-identity-java, azure-storage-blob-java, azure-cosmos-java, azure-servicebus-java, azure-security-keyvault-keys-java, azure-eventhub-java） | [`skill-demos/sdk-java/`](skill-demos/sdk-java/) |
| **Rust** | 5（azure-identity-rust, azure-storage-blob-rust, azure-cosmos-rust, azure-keyvault-secrets-rust, azure-eventhub-rust） | [`skill-demos/sdk-rust/`](skill-demos/sdk-rust/) |

**每个 SDK skill 行**都记录了：怎么试的（实际使用 vs 概念port 模式）、提示词关键约束（例："用 `AIProjectClient` 不是 `AzureAIAgentsProvider`"）、产出物（`Foundry-Hosted-Agent-Toolbox-Demo/` 里的实代码引用 或 带 `APPLICABLE-NOT-USED` / `APPLICABLE-FOR-PORT` 诚实标签的模式文档）。

### 总计验证：12 Core + 11 Foundry sub + 38 SDK = **61 个技能**

所有产出物遵循**三元组格式**：怎么试 + 提示词约束 + 产出路径。

### Skill 1: cloud-solution-architect — RAG Agent 架构设计

按照该 skill 的 **7 步架构审查工作流** 设计了一个生产级 RAG Agent 系统。

**技术选型**（Step 3）：

| 领域 | 选择 | 理由 |
|------|------|------|
| 计算（Web） | Azure Container Apps | 可缩容至零，比 AKS 简单 |
| 计算（Worker） | Azure Functions | 事件驱动的文档处理 |
| AI 编排 | Azure AI Foundry (gpt-4.1-mini) | 托管 LLM，内容安全 |
| 向量搜索 | Azure AI Search | 混合向量+关键词，语义排序 |
| 元数据存储 | Cosmos DB (serverless) | 亚 10ms 读取，无最低费用 |
| 消息队列 | Azure Service Bus | 可靠的摄入队列，死信支持 |
| 身份认证 | Entra ID + Managed Identity | 零凭据架构 |

**应用了 10 个设计模式**（Step 4）：Cache-Aside、Queue-Based Load Leveling、Retry、Circuit Breaker、Bulkhead、Claim Check、Gateway Offloading、Health Endpoint Monitoring、Valet Key、External Configuration Store。

**WAF 5 维评估**（Step 6）：可靠性 ✅ 强 | 安全 ✅ 强 | 成本 ✅ 好 | 运营卓越 ✅ 好 | 性能效率 ✅ 好。

**ADR 决策记录**：Container Apps vs AKS、混合搜索 vs 纯向量、Serverless Cosmos vs PostgreSQL。

→ 完整文档：[`skill-demos/cloud-solution-architect/architecture-design.md`](skill-demos/cloud-solution-architect/architecture-design.md)

### Skill 2: github-issue-creator — 从错误日志生成结构化 Issue

**输入**：63 工具实跑中的 6 行原始错误输出。

**输出**：3 个结构化、可分派的 GitHub issue：

| Issue | 摘要 | 严重度 |
|-------|------|--------|
| #1 | `extension_cli_install` 返回 400 — `--cli-type` 参数未在 learn schema 中文档化 | Low |
| #2 | `foundry` 的 `model_similar_models_get` 使用有效 AIServices 账户仍返回通用错误 | Medium |
| #3 | `extension_azqr` 在 `azqr` 二进制不存在时失败，无 fallback | Low |

每个 issue 都遵循模板：Summary → Environment → Steps → Expected → Actual → Error → Impact → Context。

→ 完整文档：[`skill-demos/github-issue-creator/generated-issues.md`](skill-demos/github-issue-creator/generated-issues.md)

### Skill 3: mcp-builder — 暴露评测数据的 MCP Server

按照 skill 的 4 阶段工作流构建了一个 Python FastMCP server：

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("azure-skills-evaluation", version="1.0.0")

@mcp.tool(annotations={"readOnlyHint": True})
def eval_summary() -> str:
    """获取 63 工具 Azure MCP 评测的汇总结果。"""
    return json.dumps(data["summary"], indent=2)
```

**暴露 5 个工具**：`eval_summary`、`eval_tool_result`、`eval_list_tools`、`eval_family_breakdown`、`eval_blockers`——全部标注 `readOnlyHint: True`。

语法验证：`python -m py_compile` ✅

→ 完整代码：[`skill-demos/mcp-builder/evaluation_mcp_server.py`](skill-demos/mcp-builder/evaluation_mcp_server.py)

### Skill 4: frontend-design-review — Foundry Demo 前端审查

用 skill 的 5 维度审查框架审查了 `Foundry-Hosted-Agent-Toolbox-Demo/app/static/index.html`（726 行）：

| 维度 | 评分 | 关键发现 |
|------|-----:|----------|
| 设计系统 | 7/10 | Segoe UI + Microsoft Blue 配色正确，间距不一致 |
| 可访问性 | **4/10** | 无 ARIA 标签、无 landmark、无焦点样式、9px 文字 |
| 性能 | 7/10 | 零外部依赖，但 3 个并行轮询 |
| 响应式 | **2/10** | 固定 320px 网格列，零 media query |
| 美观度 | 8/10 | 专业暗色主题，清晰视觉层级 |
| **总评** | **5.7/10** | |

**Top 3 修复**：(1) 加 ARIA 标签 + landmark，(2) 固定网格改响应式，(3) 轮询改 SSE。

→ 完整报告：[`skill-demos/frontend-design-review/review-report.md`](skill-demos/frontend-design-review/review-report.md)

### Skill 5: skill-creator — 创建全新 SKILL.md

按照 skill-creator 的指导创建了完整的 SKILL.md（含 YAML frontmatter）：

```yaml
---
name: azure-mcp-evaluation
description: >-
  Guide agents through evaluating Azure MCP Server tools against real Azure subscriptions.
  USE FOR: running Azure MCP evaluation harnesses, interpreting MCP tool results...
  DO NOT USE FOR: deploying Azure resources, modifying infrastructure...
compatibility: github-copilot, claude-code, opencode
---
```

包含：分类规则、调用约定、安全规则、输出格式、评测工作流、常用参数。

→ 完整 SKILL.md：[`skill-demos/skill-creator/azure-mcp-evaluation-SKILL.md`](skill-demos/skill-creator/azure-mcp-evaluation-SKILL.md)

### Skill 6: foundry-hosted-agents — 容器化 Agent 部署

通过 `azd up` 部署了 Foundry 托管 agent：

```python
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

agent = Agent(
    client=client,
    name="hosted-agent-toolbox-demo",
    tools=[toolbox_tool, direct_web_search_tool, direct_image_generate_tool],
    context_providers=[memory_provider],
)
```

证据：Dockerfile、agent.yaml、Toolbox MCP 集成、Entra 身份、Container Apps 部署。

→ 完整证据：[`skill-demos/foundry-hosted-agents/deployment-evidence.md`](skill-demos/foundry-hosted-agents/deployment-evidence.md)

### Skill 7: foundry-models — Foundry 模型部署

部署 `gpt-4.1-mini`（按量付费）并通过 MCP 验证：

```bash
az cognitiveservices account deployment list --name toolbox-demo-ais ...
# gpt-4-1-mini    gpt-4.1-mini   2025-04-14
```

同时通过 MCP `foundry` 工具验证 — 记录了 `model_similar_models_get` 即使使用有效参数仍返回通用错误（产品发现）。

→ 完整证据：[`skill-demos/foundry-models/model-deployment-evidence.md`](skill-demos/foundry-models/model-deployment-evidence.md)

### Skill 8: foundry-toolboxes — Toolbox MCP 配置

配置 Toolbox `agent-tools`，将 3 个工具打包到一个 MCP 端点：

| 工具 | 类型 | 描述 |
|------|------|------|
| `code_interpreter` | Built-in | 在托管沙箱中执行 Python |
| `file_search` | Built-in | 通过向量存储搜索上传文档 |
| `web_search` | Built-in | 通过 Bing grounding 搜索（预览） |

通过 `MCPStreamableHTTPTool` 消费，使用 `Foundry-Features: Toolboxes=V1Preview` header。

→ 完整配置：[`skill-demos/foundry-toolboxes/toolbox-configuration.md`](skill-demos/foundry-toolboxes/toolbox-configuration.md)

### Skill 9: foundry-memory — 跨 Session Agent 记忆

集成 `FoundryMemoryProvider` 实现托管的长期记忆：

```python
from agent_framework.foundry import FoundryMemoryProvider
memory_provider = FoundryMemoryProvider(
    project_endpoint=project_endpoint,
    credential=credential,
    memory_store_name=memory_store_name,
    scope="default",
    allow_preview=True,
)
agent = Agent(..., context_providers=[memory_provider])
```

零基础设施——不需要 Redis/Cosmos。`MEMORY_STORE_NAME` 未设置时优雅降级为无状态模式。

→ 完整集成：[`skill-demos/foundry-memory/memory-integration.md`](skill-demos/foundry-memory/memory-integration.md)

### Skill 10: copilot-sdk — 多 Agent 演示应用

构建了完整的 FastAPI Web 应用（`server.py` + `index.html`）：

- **Responses 协议**：`POST /responses` + Bearer 认证到 Foundry 托管 agent
- **多 Agent 人设**：Agent 注册表，每个 agent 配不同工具子集
- **输出解析**：`output[] → message → content[] → output_text` 链
- **语音管线**：浏览器 MediaRecorder → Whisper STT → Agent → 响应
- **图像生成**：直接 Foundry Image API（gpt-image-1）

```python
resp = httpx.post(ep["url"], json={"input": constraint},
                  headers={"Authorization": f"Bearer {_get_token(...)}"})
for item in payload.get("output", []):
    if item.get("type") == "message":
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                text_parts.append(c["text"])
```

→ 完整证据：[`skill-demos/copilot-sdk/application-evidence.md`](skill-demos/copilot-sdk/application-evidence.md)

### Skill 11: applicationinsights-web-ts — 浏览器 RUM + GenAI 追踪

为 Foundry Demo 仪表盘提供的 drop-in TypeScript 模块，包含 W3C 分布式追踪 + OpenTelemetry GenAI 语义约定。

```typescript
import { ApplicationInsights } from "@microsoft/applicationinsights-web";

export const appInsights = new ApplicationInsights({
  config: {
    connectionString: import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING,
    distributedTracingMode: 2, // AI_AND_W3C — 浏览器 ↔ FastAPI 后端关联
    enableAutoRouteTracking: true,
    extensions: [clickPlugin],
  },
});

export function trackAgentInvocation(attrs: AgentSpanAttrs): void {
  appInsights.trackEvent({ name: "gen_ai.agent.invocation" }, {
    "gen_ai.system": "azure_ai_foundry",
    "gen_ai.agent.name": attrs.agentName,
    "gen_ai.usage.total_tokens": attrs.totalTokens ?? 0,
    "duration_ms": attrs.durationMs,
  });
}
```

Skill 强制要求：浏览器使用单独的 App Insights 资源（浏览器端连接字符串公开可见）、W3C trace context、OTel GenAI 语义约定。

→ 完整代码：[`skill-demos/applicationinsights-web-ts/appInsights.ts`](skill-demos/applicationinsights-web-ts/appInsights.ts)

### Skill 12: continual-learning — 项目本地 Learnings 文件

把整次评测的教训提炼为 `.copilot-memory/learnings.md` 格式。Coding Agent 打开本仓库时，hook 会在 session 启动时浮出这些教训。

| 类别 | 示例教训 |
|------|----------|
| `tool_insight` | Composite Azure MCP 工具用 flat args + `command`，**不是** 嵌套 JSON-string `parameters` |
| `tool_insight` | `mcp_azure_mcp_*` 前缀是 host 加的，裸 server 用 plain names |
| `mistake` | PIL 画布 3840px + width="960" = 缩 4 倍 = 字糊 |
| `mistake` | 我们说 PPT 由 `presenter` skill 生成 → 错的，那是 React 演示模式 skill |
| `pattern` | 用 `microsoft-docs` skill：每页页脚必须显示来源 URL |
| `pattern` | 用 `cloud-solution-architect`：必须走完 7 步，跳步 = 服务购物清单 |

→ 完整文件：[`skill-demos/continual-learning/learnings.md`](skill-demos/continual-learning/learnings.md)

### Skill 13: entra-agent-id — 配置 Entra Agent ID

Python 脚本，通过 Microsoft Graph beta API 为 `hosted-agent-toolbox-demo` 配置 Microsoft Entra Agent ID：

```python
# Step 1：Blueprint（application 对象）
POST /beta/applications  with @odata.type=Microsoft.Graph.AgentIdentityBlueprint

# Step 2：BlueprintPrincipal（**强制** — 跳过会让 Step 3 返回 400）
POST /beta/servicePrincipals  with @odata.type=Microsoft.Graph.AgentIdentityBlueprintPrincipal

# Step 3：Agent Identity 实例
POST /beta/servicePrincipals  with @odata.type=Microsoft.Graph.AgentIdentity
```

Skill 强制要求：仅 `/beta` API（preview）、`ClientSecretCredential`（DefaultAzureCredential 返回 403）、sponsor 必须是 User 对象、必须 `OData-Version: 4.0` 头、BlueprintPrincipal 步骤强制不可跳。

→ 完整脚本：[`skill-demos/entra-agent-id/provision_agent_identity.py`](skill-demos/entra-agent-id/provision_agent_identity.py)

### Skill 14: kql — 7 条 App Insights 生产监控查询

7 条 KQL，覆盖日志 tail、agent 调用次数、tool 使用分布、token 消耗、错误率、p50/p95/p99 延迟、分布式追踪关联。

```kql
AppEvents
| where TimeGenerated > ago(24h)
| where Name == "gen_ai.agent.invocation"
| extend agent_name = tostring(Properties["gen_ai.agent.name"])  // skill 规则：dynamic 字段在 summarize-by 前必须 cast
| extend duration_ms = toint(Properties["duration_ms"])
| summarize p50 = percentile(duration_ms, 50), p95 = percentile(duration_ms, 95)
    by agent_name
| order by p95 desc
```

Skill 强制要求：dynamic 字段在 summarize/order/join 前必须 cast；时间用 `ago()` 不要硬编码 UTC；延迟用 `percentile()` 不用 `avg()`；最后 project；结果集大小有界。

→ 完整查询：[`skill-demos/kql/agent-monitoring.kql`](skill-demos/kql/agent-monitoring.kql)

### Skill 15: podcast-generation — GPT Realtime 音频播客

Python 脚本，通过 WebSocket 调用 Azure OpenAI GPT Realtime Mini 生成本次评测的播客版音频：

```python
WS_URL = endpoint.replace("https://", "wss://").rstrip("/") + "/openai/v1"
client = AsyncOpenAI(websocket_base_url=WS_URL, api_key=api_key)

async with client.realtime.connect(model="gpt-realtime-mini") as conn:
    await conn.session.update(session={"output_modalities": ["audio"]})
    await conn.conversation.item.create(item={"type": "message", ...})
    async for event in conn:
        if event.type == "response.output_audio.delta":
            audio_chunks.append(base64.b64decode(event.delta))
        elif event.type == "response.done":
            break

# 把裸 PCM（24kHz/16-bit/mono）包 WAV 头 → 可播放 .wav
```

Skill 强制要求：endpoint **不能**包含 `/openai/v1`、HTTPS→wss、audio-only modality、监听 4 个特定事件类型、PCM 固定 24kHz/16-bit/mono、必须 RIFF/WAVEfmt 头。

→ 完整脚本：[`skill-demos/podcast-generation/generate_evaluation_podcast.py`](skill-demos/podcast-generation/generate_evaluation_podcast.py)

每个产出物都记录了：该 skill 教了什么、我们如何应用、实际产出、以及对 skill 价值的评定。

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
