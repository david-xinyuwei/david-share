# Foundry Agent 全生命周期：构建、部署与运营

[![Microsoft Foundry](https://img.shields.io/badge/Microsoft-Foundry-blue)](https://learn.microsoft.com/azure/ai-foundry/)
[![Build 2026](https://img.shields.io/badge/Build-2026-purple)](https://build.microsoft.com)
[![Agent Framework](https://img.shields.io/badge/Agent-Framework-green)](https://github.com/microsoft/agents)
[![Hosted Agents](https://img.shields.io/badge/Hosted%20Agents-GA%20Soon-orange)](#第二幕deploy--从笔记本到生产环境)

基于 Microsoft Build 2026 的 [BRK241](https://build.microsoft.com/en-US/sessions/BRK241) session，系统梳理 agent 全生命周期：如何在本地用任意 framework **构建** agent，如何以 sub-second cold start **部署**为 hosted agent，如何通过 tracing、evaluation、optimization 和 governance **持续运营**。演讲者为 Tina Schuchman（CVP, Microsoft Foundry）和 Jeff Hollan（Partner Director, Microsoft Foundry）。

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB

[English](README.md) | 中文版

---

**Session 录像**: [BRK241 — From prototype to production: Build and run agents at scale](https://build.microsoft.com/en-US/sessions/BRK241)

---

## 目录

- [为什么值得看](#为什么值得看)
- [核心洞察](#核心洞察)
- [Agent 生命周期闭环](#agent-生命周期闭环)
- [平台架构](#平台架构)
- [Demo 场景：自动化光纤故障响应](#demo-场景自动化光纤故障响应)
- [底层是怎么工作的](#底层是怎么工作的)
- [第一幕：Build — 从 Framework 到 Agent](#第一幕build--从-framework-到-agent)
- [第二幕：Deploy — 从笔记本到生产环境](#第二幕deploy--从笔记本到生产环境)
- [第三幕：Operate — 从上线到持续改进](#第三幕operate--从上线到持续改进)
- [Build 2026 关键发布](#build-2026-关键发布)
- [客户部署案例](#客户部署案例)
- [快速开始](#快速开始)
- [关键资源](#关键资源)
- [Running on Azure](#running-on-azure)
- [相关 Repo](#相关-repo)

---

## 为什么值得看

企业做 agent prototype 很容易，真正难的是运行。生产环境里缺的通常不是一个更好的 prompt，而是 identity、sandbox、受治理的 tools、分发渠道、evaluation、monitoring 和持续优化机制。

BRK241 展示的是 Microsoft Foundry 如何补齐这条生产链路：

| 生产问题 | BRK241 中展示的 Foundry 能力 |
|:---------|:------------------------------|
| 开发者能不能继续用自己的本地 framework？ | Microsoft Agent Framework + Foundry Toolkit for VS Code |
| Agent 能不能安全访问企业 tools？ | Toolboxes, MCP, Fabric IQ, Work IQ, Foundry IQ |
| 能不能不用一直 warm server？ | Hosted Agents 的隔离 sandbox、sub-second cold start 和 scale-to-zero |
| 能不能进入用户工作的地方？ | Teams, Microsoft 365 Copilot, Agent Identity |
| 上线后能不能持续观测和改进？ | Tracing, Evaluation, Rubric, Agent Optimizer, Procedural Memory |

BRK241 还给出了生产客户信号：AT&T customer care 信息检索**快 33%**，BMW telemetry analysis **快 12 倍**，Nasdaq 每年节省 **100+ 小时**，以及超过 **80,000 家企业和 digital natives** 正在使用 Azure AI Foundry。这些是 BRK241 session 中报告的案例，不是本 repo 独立复现实测的数据。

---

## 核心洞察

构建一个 agent 已经不是最难的事。真正难的是把一个能跑的 prototype 变成可以托管、扩展、观测、治理、持续改进的生产系统。

> "Agents are teammates, not tools. They build and extend themselves. The hard part isn't building — it's running them at scale."
> — Tina Schuchman, CVP, Microsoft Foundry (BRK241 Slide 2)

Microsoft Foundry 提供了**完整的生命周期闭环**——从本地开发到托管部署再到生产运营——让你在笔记本上搭建的同一个 agent 可以无需重写直接扩展到生产环境。

---

## Agent 生命周期闭环

AI 系统不是"做完一次就上线"的项目，而是持续学习的闭环：

<div align="center"><img src="images/slide-lifecycle-loop.png" width="960"></div>

> Source: BRK241 Slide 5 — Build → Deploy → Operate 循环。Traces、cost signals 和 outcomes 不断被捕获、提炼、反馈到 models、skills、tools、memory 和 outcomes 中。系统运行越久，价值越复利。

| 阶段 | 做什么 | 核心能力 |
|:------|:-------|:---------|
| **Build** | 在本地用任意 framework 开发 agent，接工具、知识、memory | Agent Framework, Foundry Toolkit for VS Code, Toolboxes, Voice Live API |
| **Deploy** | 部署到隔离 sandbox，发布到 Teams/M365/API，设置 routines | Hosted Agents, Routines, Teams publishing, Agent Identity |
| **Operate** | 监控、评估、优化、治理 | Tracing, Evaluation, Rubric, Agent Optimizer, Procedural Memory |

---

## 平台架构

Microsoft Agent Platform 有四层，从 maker surface（高抽象、少控制）到 developer surface（全控制）：

<div align="center"><img src="images/slide-agent-platform.png" width="960"></div>

> Source: BRK241 Slide 3 — "Build in GitHub. Run and optimize in Foundry. Reach users in M365, Teams, and everywhere work gets done."

| 层级 | 作用 | 组件 |
|:------|:-----|:-----|
| **Human + Agent Collaboration** | 用户和 agent 交互的体验层 | Copilot chat, Teams, apps, APIs |
| **Agent Runtime** | Plan → Act → Observe 执行循环，hosting & scaling | Hosted Agents, evaluate & optimize |
| **Intelligence** | 给 agent 提供上下文和能力 | Foundry IQ, Work IQ, Fabric IQ, tools, memory, skills |
| **Trust + Security** | 贯穿全层的企业治理 | Conditional Access, audit logging, data residency, Agent Identity |

---

## Demo 场景：自动化光纤故障响应

Session 用一个端到端场景展示全生命周期：**微软数据中心附近发生光纤中断，系统自动检测、分级、派单、让现场工程师处理，并持续跟踪状态**。

<div align="center"><img src="images/slide-demo-scenario.png" width="960"></div>

> Source: BRK241 Slide 4 — 两个 hosted agents 在 Foundry Agent Service 的安全隔离 sandbox 中协同响应光纤故障。

两个 agent 各自的角色：

| Agent | 角色 | 展示什么 |
|:------|:-----|:---------|
| **`field-ops-agent`** | 现场工程师助手。支持语音查询，如"Quincy North B-side 的 fiber termination spec 是什么？"——先快速回应"Looking that up"，再后台调用 tools 查 site specs、work orders、repair procedures。 | Build: Agent Framework, tools, Toolbox/MCP, voice routing, procedural memory, tracing |
| **`fibey-coordinator`** | 网络运维协调员。监控 telemetry，发现异常，创建工单，派遣现场工程师，必要时升级。不是 chatbot，而是长期运行的"AI teammate"。 | Deploy/Operate: Hosted Agent, routines, persistent state, scale-to-zero, human-in-the-loop, Teams publishing |

---

## 底层是怎么工作的

BRK241 不只是产品功能列表。它展示的是一个 reference pattern：如何把本地 agent 开发循环推进到受治理的生产 runtime。

### 1. Local Agent Harness

开发者先在本地使用自己选择的 framework。Demo 项目里，agent package 包含 `agent.yaml`、`Dockerfile`、evaluation config、procedural memory seed、router agent、worker agent 和 toolbox integration。这个分层很关键：业务逻辑留在代码里，面向平台的 deployment、evaluation、memory 和 tool metadata 放在旁边。

### 2. 受治理的 Tool Access

Agent 不应该在代码里硬编码所有企业连接器。它通过 Toolboxes 和 IQ systems 调用能力。Demo 的 Tool Catalog 展示了混合 tool surface：内置 Code Interpreter、Fabric IQ / OneLake Catalog，以及通过 MCP 接入的 Work IQ。这里就是治理边界：agent 看到的是 callable tools，平台负责 identity、connection 和 audit。

### 3. Hosted Runtime

Hosted Agents 把同一个 agent package 放进 Foundry Agent Service。Session 强调了 isolated sandbox、sub-second cold start 和 scale-to-zero。关键架构变化是：生产 hosting 变成平台能力，而不是每个团队自己维护一个 custom web server。

### 4. Operations Feedback Loop

Agent 部署后，每次 run 都会产生 traces。Evaluation 和 Rubric 把 traces 变成质量信号。Agent Optimizer 根据这些信号提出 prompt 或 skill 改进。Procedural Memory 跨 run 保存可复用 playbooks。这个循环是运营侧的持续改进；先优化 instructions、tools、memory 和 routing，如果瓶颈变成模型行为本身，再进入 BRK231/BRK232 的 post-training loop。

---

## 第一幕：Build — 从 Framework 到 Agent

### 开发者面临的挑战

- 怎么用自己想用的 framework 而不被锁死？
- 怎么把 agent 接入企业知识，而不需要一个六个月的集成项目？
- 怎么给 agent 安全、受治理的工具访问，而不用每次重写集成？

### Microsoft Agent Framework

Stable release 的 [Microsoft Agent Framework](https://github.com/microsoft/agents) 提供 **agent harness** — skills、memory、middleware 和受控执行环境 —— 让你在本地开发、部署到任何地方。它和 GitHub Copilot SDK、Claude Agent SDK 等 coding agent framework 都能集成。

BRK241 对 Agent Framework 的关键解释是：harness 不只是另一层 tool wrapper。Session 描述了一个受控执行环境，agent 可以在平台控制下执行 shell commands，并 read、write、execute code。这样 agent 不再只是固定 tools 的 router，而是可以做调查、写代码、并在 managed workspace 里执行任务。

### Foundry Toolkit for VS Code

GA 的 **Foundry Toolkit for VS Code** 提供覆盖 agent 创建、本地调试、tracing、evaluation 和 model management 的 IDE 内开发体验。

Session 还展示了项目尚不存在时的创建路径：可以从 sample 开始，也可以用 **Generate with Copilot** 根据自然语言 prompt 生成 agent。Toolkit 会把 Foundry best-practice skills 和 deployment metadata 一起接入，让生成的项目直接进入 local debug、tracing、evaluation 和 hosted deployment 流程。本地调试时，**F5** 启动 localhost 上的 agent，通过单个 MCP-compatible endpoint 连接 Toolbox，并允许开发者在 VS Code 内检查 breakpoint 和 streaming events。

Demo 中，Jeff Hollan 在 VS Code 里打开 `field-ops-agent` 项目，通过 Agent Inspector 连接到本地运行在 `localhost:8088` 的 agent，在 Playground 中交互：

<div align="center"><img src="images/demo-vscode-agent-inspector.png" width="960"></div>

> Source: BRK241 demo — VS Code 中的 Agent Inspector 连接到 field-ops-agent。项目包含 `agent.yaml`, `Dockerfile`, `eval.yaml`, `procedural_memory_seed.json`, `worker_agent.py`, `router_agent.py`, `toolbox.py` 等文件。

### Toolboxes 和 MCP 集成

**Foundry Toolboxes** 为 agent 提供受治理的 managed endpoint 来访问企业工具和数据。Demo 中的 Tool Catalog 展示了多种协议的工具：

<div align="center"><img src="images/demo-tool-catalog.png" width="960"></div>

> Source: BRK241 demo — Tool Catalog 显示 Code Interpreter、`sitereliabilityagent`（Fabric IQ / OneLake Catalog）和 `WorkIQTeams`（Model Context Protocol / MCP）。

| Tool | 来源 | 协议 |
|:-----|:-----|:-----|
| Code Interpreter | 内置 | Foundry native |
| Site Reliability Agent | Fabric IQ (OneLake Catalog) | Foundry IQ |
| Work IQ Teams | Microsoft Teams 数据 | MCP |

Toolbox 有两个生产级细节特别重要。**Tool Search** 让 Toolbox 只返回当前任务相关的 tools，减少 context window 浪费，也让 agent 更聚焦。**Guardrails** 可以配置在 tool 边界，比如防止 PII 通过 tool results 泄漏。同一个 tool surface 还可以包含 Content Understanding，把合同、规格书、表格型 PDF 转成 agent 可读的 markdown、figures 或 JSON。

### Voice Live API

**Voice Live API** 和 Foundry Agent Service 直接集成。Demo 中 `field-ops-agent` 支持 voice-first 交互——现场工程师自然语音提问，agent 先快速回复"Looking that up"，后台异步查询 tools。

<div align="center"><img src="images/slide-build-announcements.png" width="960"></div>

> Source: Based on BRK241 Slide 8 — Build 阶段发布：Agent Framework（Stable Release），Coding agent SDK integrations（Stable Release），Foundry Toolkit for VS Code（GA），Toolboxes（GA soon），Voice Live API（GA），Hosted Agents（GA soon）。

---

## 第二幕：Deploy — 从笔记本到生产环境

### 开发者面临的挑战

- 怎么把本地跑的 long-running autonomous agent 推到生产，而不重写 runtime？
- 怎么做到 sub-second cold start 和 proper isolation？
- 怎么让 agent 出现在用户真正工作的地方？
- 怎么让 agent 成为组织里的正式"队友"——有自己的身份、邮箱、Teams presence 和审计记录？

### Hosted Agents in Foundry Agent Service

**Hosted Agents**（GA soon）把你的容器化 agent 运行在隔离的安全 sandbox 中：
- **Sub-second cold start** — 无需预热
- **Scale-to-zero** — 没有 session 活跃时零成本
- **Framework agnostic** — 带你自己的 Python/Node.js agent，用任何 framework 构建
- **Long-running autonomous agents** — agent 可以跨 session 保持状态

Demo 中 `field-ops-agent` 部署为 hosted agent，Foundry Portal 截图显示 Playground、Traces、Monitor、Evaluation、Optimize 各 tab：

<div align="center"><img src="images/demo-foundry-portal-playground.png" width="960"></div>

> Source: BRK241 demo — Foundry Portal 截图显示 `field-ops-live` 作为 hosted agent 运行。UI 中可见的 version 和 date 是 demo 截图里的上下文，不是产品使用要求。左侧面板显示 Agent info、Code asset、Protocols、Guardrail 和 Voice mode。Playground 支持 Chat 和 "Call agent"（语音）两种模式。

BRK241 把 isolation 问题讲得很具体：如果 subcontractor A 和 subcontractor B 都在和同一个 autonomous agent 交互，agent 为 A 写下的文件和中间状态绝不能被 B 看到。Hosted Agents 通过给每个 conversation 或 routine 独立的 workspace session 来解决这个问题，同时保留该 session 的 durable state。

Demo 还通过 Microsoft Agent Framework 的 **Durable Task Scheduler** extension 扩展了这个 long-running pattern。Session 中，agent 等待人工审批时可以进入 idle 状态，不保持活跃 hosted session；Durable Task 负责跟踪 workflow state，审批通过后再恢复 session，并把之前的 investigation files 交还给 agent。这里描述的是 demo architecture pattern，不是产品 SLA。

### Routines

**Routines**（Public Preview）让 agent 从 reactive 变成 proactive。你定义什么时间该发生什么，Foundry 可靠地排队、执行、跟踪每次 run。

<div align="center"><img src="images/demo-routines-heartbeat.png" width="960"></div>

> Source: BRK241 demo — `fibey-coordinator` 的 "Edit heartbeat" routine。可以把 Routine 理解成 agent 的 scheduled task，但它不是普通 cron：Foundry 负责 run tracking 和 session state。截图展示的是每小时 recurring schedule，agent acknowledge、dispatch 后停止等待下一次外部更新。

### 发布到 Teams 和 M365 Copilot

发布到 **Teams** 和 **Microsoft 365 Copilot** 把 agent 推送到用户已经在工作的地方。Identity、permissions、policy 自动流转。

Demo 中 `fibey-coordinator` 在 Microsoft Teams 里以正式队友身份出现，主动推送 incident 状态表：

<div align="center"><img src="images/demo-teams-fibey.png" width="960"></div>

> Source: BRK241 demo — Microsoft Teams 中的 `fibey`。协调员发布结构化 incident 表（P2-High 和 P3-Normal/Low），包含 Incident ID、Site、Status、Type、Priority、Last Updated。底部显示 Singapore South fiber cut 的升级摘要。

### Agent Identity (Entra Agent ID)

Agent 可以拥有自己的 **Entra Agent ID** — 包括邮箱、Teams presence 和审计记录。它们可以主动发起对话、跟进 action items，作为真正的"组织成员"运作。Agent 365 提供端到端治理。

<div align="center"><img src="images/slide-deploy-announcements.png" width="960"></div>

> Source: Based on BRK241 Slide 11 — Deploy 阶段发布：Routines（Public Preview），Publishing to M365 Teams and Copilot（GA soon），Publishing as autopilot agents（Public Preview）。

---

## 第三幕：Operate — 从上线到持续改进

### 开发者面临的挑战

- 怎么跨 agent 监控 cost、performance 和 usage？
- 怎么在规模化时执行 compliance 和 data-access 策略？
- 怎么检测和缓解不安全或失败的行为？
- 怎么持续改进 agent 的质量和成本——而不需要变成 prompt engineering 专家？

### Tracing 和 Evaluation

**Tracing**（GA soon）把每次 model call、tool invocation、sub-agent hop、handoff 都捕获到统一的 OpenTelemetry pipeline 中。**Evaluation** 对 production traces 运行自动化质量检查。

Demo 中 Jeff 用一条 CLI 命令初始化 evaluation：

<div align="center"><img src="images/demo-eval-init.png" width="960"></div>

> Source: BRK241 demo — 终端显示 `azd ai agent eval init`，在 `agent-build-demo-jeffhollan` 项目中 scaffold `eval.yaml`。

关键的运营细节是，`azd ai agent eval init` 不只是生成文件。Demo 叙述中，Foundry 可以在团队还没有 eval dataset 时，利用历史 traces 和 agent 相关信号提出初始 eval dataset。它也可以基于 agent 的实际使用方式推荐 evaluator 组合，例如 tool selection、tool input/output、retrieval quality、fluency 和 custom rubric scoring。

### Rubric

**Rubric**（Public Preview）自动生成 context-aware evaluation criteria 和 weighted scoring。不需要写自定义评估逻辑——你描述"好"的样子，Rubric 从真实生产场景创建评分框架。

BRK241 demo 用 voice-agent feedback 把这个机制讲具体了。生成的 rubric 包括 correct tool use、safety warning、voice-optimized conciseness 等维度。Jeff 把 voice conciseness 的权重从 3 调到 10，作为 developer-controlled rubric tuning 的 demo example，而不是通用推荐值。

### Agent Optimizer

**Agent Optimizer**（Private Preview）分析 production traces 和 evaluation 结果，生成 prompt 和 skill 改进候选。它比较 quality、cost、latency，由开发者决定是否部署——支持 lineage 和 rollback。

Session 中展示的 CLI 入口是 `azd ai agent optimize`。Optimizer 可以把 prompts、skills、tool descriptions，甚至 target model 都作为实验变量；例如 session 提到可以把 GPT 5.5 和 Anthropic Opus 4.8 这类 model choice 放进 optimization search。现场 run 产出了 4 个 candidate，每个 candidate 有不同 trade-off，开发者可以查看 score details，对比 quality/cost/latency，再选择要 promote 的版本。

<div align="center"><img src="images/demo-agent-optimizer.png" width="960"></div>

> Source: BRK241 demo — Foundry Portal 中的 Agent Optimizer 结果。Demo 截图显示 task-weighted average 从 **0.574 提升到 0.639（+11%）**。截图没有展示底层 scenario 数量，所以这里应理解为 stage demo 结果，不是本 repo 独立复现的 benchmark。

这里正好能接上 [BRK232: Foundry Agent Post-Training](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Foundry-Agent-Post-Training-Deep-Dive)。Agent Optimizer 优化的是 prompts、instructions、skills 和 tool configuration。如果瓶颈变成模型行为本身，比如模型只靠 prompting 学不会稳定 tool-calling policy，下一步就是 BRK231/BRK232 的循环：traces → datasets → SFT/RFT/Low-Level Training API → improved model → 再部署回 agent lifecycle。

### Procedural Memory

**Procedural Memory**（Public Preview）让 agent 跨 run 学习 playbooks。不必每次从零开始——agent 积累运维知识（维修流程、升级模式、站点特性），并在后续交互中应用。

<div align="center"><img src="images/slide-operate-announcements.png" width="960"></div>

> Source: Based on BRK241 Slide 14 — Operate 阶段发布：Tracing and evaluation（GA soon），Rubric for custom evaluation（Public Preview），Agent Optimizer（Private Preview），Procedural Memory（Public Preview）。

---

## Build 2026 关键发布

| 发布内容 | 阶段 | 状态 |
|:---------|:------|:------|
| Microsoft Agent Framework — stable agent harness | Build | **Stable Release** |
| Coding agent SDK integrations (GitHub Copilot SDK, Claude Agent SDK) | Build | **Stable Release** |
| Foundry Toolkit for VS Code | Build | **GA** |
| Toolboxes in Foundry | Build | **GA soon** |
| Voice Live API integration with Foundry Agent Service | Build | **GA** |
| Hosted Agents in Foundry Agent Service | Deploy | **GA soon** |
| Routines in Foundry Agent Service | Deploy | **Public Preview** |
| Publishing to Microsoft 365 Teams and Copilot | Deploy | **GA soon** |
| Publishing as autopilot agents | Deploy | **Public Preview** |
| Tracing and evaluation for hosted agents | Operate | **GA soon** |
| Rubric for custom evaluation | Operate | **Public Preview** |
| Agent Optimizer in Foundry Agent Service | Operate | **Private Preview** |
| Procedural Memory in Foundry Agent Service | Operate | **Public Preview** |

> Source: BRK241 Slides 8, 11, 14

---

## 客户部署案例

<div align="center"><img src="images/slide-summary.png" width="960"></div>

> Source: BRK241 Slide 16 — "Build simply. Deploy powerfully. Operate with trust."

| 公司 | 场景 |
|:-----|:-----|
| **Iberdrola** | 跨 14 个国家的 mission-critical energy workflow，要求 identity、memory、security、observability by design |
| **Twilio** | 在 hosted agents 上部署 Twilio Agent Connect |
| **KPMG** | 在 hosted agents 上构建全球 KPMG Workbench，使用 Foundry out-of-the-box tools 和 skills |
| **Citrix** | 用 Hosted Agents 把 AI 带入 virtual desktop 环境，在 Azure 上安全规模化运行 |
| **AT&T** | 客户服务信息检索**快 33%**（BRK241 报告案例） |
| **BMW** | Telemetry 分析**快 12 倍**（BRK241 报告案例） |
| **Nasdaq** | 每年节省 **100+ 小时**（BRK241 报告案例） |

> 超过 **80,000 家企业和 digital natives** 正在使用 Azure AI Foundry。
> — BRK241 Slide 19

---

## 快速开始

### Clone 官方 BRK241 Repo

Session 附带两个可直接部署的 sample agent，含完整 infrastructure-as-code：

```bash
git clone https://github.com/microsoft/Build26-BRK241-from-prototype-to-production-build-and-run-agents-at-scale.git
cd Build26-BRK241-from-prototype-to-production-build-and-run-agents-at-scale
```

**前提条件**：
- 有 [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/) 访问权限的 Azure 订阅
- [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) v1.24+
- Foundry agents 扩展：`azd extension install azure.ai.agents`
- Python 3.12+

### 部署

```bash
# 创建 Foundry project、model deployment 和配套资源
azd provision

# 部署两个 hosted agent
azd deploy
```

单独部署一个 agent：`azd deploy field-ops-agent` 或 `azd deploy fibey-coordinator`。用 `azd down` 清理全部资源。

| Agent | 说明 |
|:------|:-----|
| `field-ops-agent` | 语音现场技术员助手 — tools、MCP Toolbox 连接、可选 Fabric data agent、procedural memory |
| `fibey-coordinator` | 长运行网络运维协调器 — persistent sessions、scale-to-zero、human-in-the-loop 审批、Teams 集成 |

每个 agent 的详细说明、示例 prompt 和可选集成见 [field-ops-agent README](https://github.com/microsoft/Build26-BRK241-from-prototype-to-production-build-and-run-agents-at-scale/blob/main/src/field-ops-agent/README.md) 和 [fibey-coordinator README](https://github.com/microsoft/Build26-BRK241-from-prototype-to-production-build-and-run-agents-at-scale/blob/main/src/fibey-coordinator/README.md)。

### 看 Session 录像

[BRK241 — From prototype to production: build and run agents at scale](https://build.microsoft.com/en-US/sessions/BRK241)

---

## 关键资源

| 资源 | 链接 |
|:-----|:-----|
| BRK241 官方代码 Repo | [github.com/microsoft/Build26-BRK241-...](https://github.com/microsoft/Build26-BRK241-from-prototype-to-production-build-and-run-agents-at-scale) |
| Microsoft Agent Framework | [github.com/microsoft/agents](https://github.com/microsoft/agents) |
| Foundry Agent Service 文档 | [learn.microsoft.com/azure/ai-foundry/agents](https://learn.microsoft.com/azure/ai-foundry/concepts/agents) |
| Hosted Agents 文档 | [learn.microsoft.com/azure/ai-foundry/concepts/hosted-agents](https://learn.microsoft.com/azure/ai-foundry/concepts/hosted-agents) |
| Foundry Toolkit for VS Code | [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.azure-ai-foundry) |
| Azure Developer CLI (azd) | [learn.microsoft.com/azure/developer/azure-developer-cli](https://learn.microsoft.com/azure/developer/azure-developer-cli/) |
| Build 2026 sessions | [build.microsoft.com](https://build.microsoft.com) |

---

## Running on Azure

| 组件 | Azure 服务 | 用途 |
|:-----|:-----------|:-----|
| Agent hosting | Foundry Agent Service (Hosted Agents) | 隔离 sandbox，sub-second cold start，scale-to-zero |
| Model inference | Azure OpenAI Service | GPT-4.1, GPT-4.1 mini, GPT-5.x |
| Enterprise knowledge | Foundry IQ, Fabric IQ, Work IQ | 在组织数据上 ground agent |
| Tool integration | Foundry Toolboxes | Managed MCP endpoints, built-in tools |
| Publishing | Microsoft Teams, M365 Copilot | 面向用户的 agent 分发 |
| Identity & governance | Entra Agent ID, Agent 365, Purview, Defender | 安全、合规、审计 |
| Observability | Foundry Tracing, Evaluation, Application Insights | OpenTelemetry pipeline，质量监控 |
| Optimization | Agent Optimizer, Rubric, Procedural Memory | 持续改进闭环 |

---

## 相关 Repo

| Repository | 描述 |
|:-----------|:-----|
| [Foundry-Agent-Post-Training-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Foundry-Agent-Post-Training-Deep-Dive) | Foundry agent post-training 深度解析：distillation, SFT, RFT, Low-Level Training API (BRK231/BRK232) |
| [Foundry-Hosted-Agent-Toolbox-Demo](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo) | Foundry Hosted Agents + Toolbox 集成实战 Demo |
| [Azure-Agent-Skills-In-Action](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Agent-Skills-In-Action) | 61 个 Azure Agent Skills 端到端验证 |
| [Microsoft-Agent-Framework](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Microsoft-Agent-Framework) | Microsoft Agent Framework 分析与示例 |
