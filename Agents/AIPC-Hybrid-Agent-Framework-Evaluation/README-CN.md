# 开源 Agent 框架评估：AIPC 混合计算场景

[![LangChain](https://img.shields.io/badge/LangChain-1.3-1C3C3C?logo=langchain&logoColor=white)](https://docs.langchain.com/oss/python/langchain/overview)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2-2d6a4f?logo=langchain&logoColor=white)](https://docs.langchain.com/oss/python/langgraph/overview)
[![Agent Framework](https://img.shields.io/badge/MAF-1.8-0078D4?logo=microsoft&logoColor=white)](https://github.com/microsoft/agent-framework)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

三个开源 Agent 框架在 AIPC 混合计算场景下的架构级对比——**LangChain**、**LangGraph** 和 **Microsoft Agent Framework (MAF)**。这不是一个“谁更会调 Azure OpenAI”的 API wrapper 对比，而是先看框架本身：执行模型、工作流控制、状态持久化、HITL、本地 runtime、Windows 生产适配、可观测性和部署路径，再映射到 Lenovo Qira 这类 AIPC hybrid 场景。

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

English | [中文版](README-CN.md)

---

## 客户真正关心的问题

Lenovo Qira 这类 AIPC OS agent 要回答的不是“哪个 SDK 能调模型”，而是：

> **如果一个 OS 级 AI assistant 要同时跑本地 skill、本地模型、云端推理、人工审批，并且要能从笔记本休眠/重启/进程崩溃中恢复，应该选哪种 Agent framework？**

所以本 repo 分两层对比：

1. **框架层**：每个框架是什么、内部怎么执行、怎么建 workflow、支持哪些开发语言、开源成熟度如何、生产能力有哪些。
2. **AIPC hybrid runtime 层**：每个框架怎么映射到本地模型、本地工具/skill、云端 fallback、checkpoint、sandbox 和 Windows 部署。

Chat Completions / Responses API 这些 API surface 很重要，但它只是其中一层，不是整个框架的本质。

---

## 宏观框架对比

| 维度 | LangChain | LangGraph | Microsoft Agent Framework (MAF) | 对 AIPC 的意义 |
|------|-----------|-----------|----------------------------------|----------------|
| 官方定位 | 面向 agents 和 LLM app 的 agent engineering platform | 面向 stateful agents 的 low-level orchestration framework | 面向 production-grade agents 和 workflows 的多语言框架 | 先理解 mental model，再谈 API |
| 开源成熟度 | MIT，约 139k GitHub stars，约 3.9k contributors | MIT，约 34.3k stars，约 295 contributors | MIT，约 11.2k stars，约 160 contributors | LangChain 生态最大；MAF 更新、更贴 Microsoft 栈 |
| 主要语言 | Python core；另有 JS/TS 生态 | Python core；另有 LangGraph.js | Python + C#/.NET 同框架支持 | Windows 原生 / .NET 团队更容易接受 MAF |
| 核心抽象 | Agent/tool loop，围绕模型调用组织工具 | StateGraph：节点、边、状态、checkpoint | 双模式：Agent + Workflow，再加 providers、middleware、OTel、hosting | LangGraph/MAF 更容易解释运行时结构 |
| 谁控制执行顺序 | 多数由 LLM 决定工具顺序 | 开发者定义图 | Agent 模式由 LLM 决定；Workflow 模式由开发者定义 | OS agent 往往需要显式控制本地/云端路由 |
| Workflow 能力 | chain / agent loop；复杂 durable workflow 要靠外部实现 | StateGraph + checkpoint + interrupt | WorkflowBuilder + checkpoint/time-travel + Durable hosting 路径 | LangGraph 本地 durable graph 最直接；MAF 是更完整生产栈 |
| 状态恢复 | Agent loop 默认无 durable state | SQLite/Postgres checkpointer 一等支持 | Workflow checkpoint/time-travel；本地 backend 需按场景验证 | 设备重启恢复是 AIPC 的一等需求 |
| HITL | 手工 callback / UI glue | 原生 `interrupt()` | `RequestInfoExecutor` / schema validation | 不能用阻塞式 `input()` 假装审批 |
| 可观测性 | 通常接 LangSmith | LangSmith | 内置 OpenTelemetry，可走 Azure Monitor | 客户级 demo 需要 trace，不只是 console log |
| 本地 runtime | 很容易接 Ollama，但进程生命周期由应用负责 | 同 LangChain provider 层，但有更强 state graph | Ollama provider、Foundry Local、Hyperlight package、.NET path | MAF 的 Windows production surface 最完整，但每个本地 backend 都要实测 |
| 最适合 | 快速原型 + 广泛集成 | local-first stateful workflow | Windows/enterprise production agent platform | 最可能不是单一赢家，而是 LangGraph 做本地 durable runtime，MAF 做企业/云端生产路径 |

来源（2026-06-10 访问）：[LangChain GitHub](https://github.com/langchain-ai/langchain)、[LangGraph GitHub](https://github.com/langchain-ai/langgraph)、[Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)、[MAF Learn](https://learn.microsoft.com/en-us/agent-framework/)。

---

## Live Demo

> `http://linuxworkvm1-work.eastasia.cloudapp.azure.com:8506`

5 个场景 tab：▦ Framework、🖥 Runtime、💥 Recovery、⏸ HITL、📝 Code。

### 哪些是真跑，哪些是架构可视化

| 资产 | 证明什么 | 边界 |
|------|----------|------|
| `scenarios/langchain_travel_agent.py` | LangChain + 本地 Ollama 的 tool-calling loop | 取决于本地模型是否支持 tool calling |
| `scenarios/langgraph_travel_agent.py` | StateGraph、typed state、`interrupt()` 模式 | 本地场景 fixture；持久化路径需按部署环境继续验证 |
| `scenarios/maf_travel_agent.py` | 真实 MAF `OllamaChatClient.as_agent(...)` 路径，接本地 Ollama tools | 证明 Agent/provider 层；WorkflowBuilder checkpoint/HITL 还需单独 proof |
| Portal Framework | 可视化宏观框架差异：开源成熟度、语言、执行控制、状态、workflow model | 对比视图，不是 benchmark |
| Portal Runtime | 映射本地模型、skill/tool、本地状态、HITL、sandbox、cloud fallback、enterprise ops | backend-specific 结论要在目标 Windows AIPC 硬件上烟测 |
| Portal Recovery / HITL | 解释 crash recovery / HITL 应该如何评估 | scripted trace，不是真实 kill/restart |

所以 Portal 更适合作为**架构可视化讲解工具**，真正的 runnable evidence 在 `scenarios/` 脚本里。

---

## 为什么做这个评估

AIPC 需要 agent 在同一个工作流里编排**本地算力**（端侧 SLM + 本地工具）和**云端算力**（Azure OpenAI + 云端 API）。框架在应用和模型之间：

```
应用层 (OS 壳 / UI)
Agent 框架层  ← 我们对比的层
本地算力 (Ollama)  ←→  云端算力 (Azure OpenAI)
```

关键问题：**哪个框架最能处理本地和云端之间的双向交互？** 不只是"能不能调 Ollama"，而是：状态怎么跨本地/云端边界流转、任务怎么按复杂度路由、一边挂了另一边怎么恢复。

---

## 1. 实现原理

### 1.1 LangChain：ReAct 循环

核心是一个 **ReAct（Reason + Act）循环**——模型想、选工具、看结果、再想，直到得出最终答案。

**执行流程**：用户消息 + system prompt + 工具定义 → 发给 LLM → LLM 返回 tool_call 或 final answer → 如果 tool_call 就执行然后把结果追加到消息列表 → 循环。

**架构特性**：
- **执行控制**：LLM 决定——模型选择调哪个工具、什么顺序
- **状态**：临时的——一个 Python 消息列表，默认不持久化
- **并行**：隐式——LLM 一次返回 3 个 tool_call 就一起执行，但开发者没有显式控制
- **错误恢复**：无——进程崩了全丢，从头来

**对 hybrid 计算的意义**：LLM 自己决定用本地工具还是云端工具，开发者无法强制指定执行顺序。简单快速，但放弃了控制权。

### 1.2 LangGraph：状态机图

核心是一个 **有向图的 typed state 变换**——受 Google Pregel 启发，每个节点是一个纯函数，输入当前状态、输出状态增量。

**执行流程**：开发者定义 `StateGraph`（TypedDict 状态 + 节点函数 + 边） → compile 时绑定 checkpointer → 执行时按图遍历，同一深度的节点并行跑 → 每个节点边界 checkpoint → `interrupt()` 暂停图。

**架构特性**：
- **执行控制**：开发者决定——图的拓扑在代码里定义
- **状态**：TypedDict + 每个节点边界 checkpoint（SQLite / Postgres）
- **并行**：显式——从同一个源出发的边并行执行
- **错误恢复**：从最近的 checkpoint 恢复，只重跑失败节点

**对 hybrid 计算的意义**：用 conditional edge 显式路由"简单任务 → 本地 Ollama 节点，复杂任务 → 云端 Azure OpenAI 节点"。SQLite checkpointer 是一等功能，状态不依赖云端就能持久化——设备重启后恢复。

### 1.3 MAF：双模式（Agent + Workflow）

MAF 有两种执行模式：**Agent 模式**（LLM 驱动，类似 LangChain）和 **Workflow 模式**（图编排，类似 LangGraph），再加上 middleware pipeline 和 provider 抽象。

**架构特性**：
- **执行控制**：两种都有——Agent（LLM 决定）或 WorkflowBuilder（开发者决定）
- **状态**：Agent 用 session scope；Workflow 用 superstep checkpoint
- **独有能力**：middleware pipeline、IChatClient provider 抽象、内置 OpenTelemetry、Python + C#/.NET 双语言、Foundry Hosted Agent 云端部署

**对 hybrid 计算的意义**：IChatClient 接口让换模型只改一行代码。MAF 有原生 `OllamaChatClient`，官方 `ollama_agent_basic.py` 示例用 `@tool` + `tools=get_time` 演示了 Ollama tool calling；它还有 `FoundryLocalClient`，可以走 Foundry Local 做本地推理。另一面，`agent-framework-hyperlight` 可以让工具在 Hyperlight-backed sandbox 里隔离执行——这是三框架里唯一的框架级沙箱集成。注意：Ollama tool calling 仍取决于具体模型能力，`qwen3:0.6b` 不能直接假设可用，应实测 `qwen2.5:3b` / `qwen3:4b`。

---

### 1.4 API surface 是子层，不是框架本身

宏观框架讲完之后，再看它们怎么触达 OpenAI-compatible model。这个维度会影响 APIM 路由、hosted tools、reasoning model 和排障，但它不是框架本身。

| 框架 | 默认 mental model | OpenAI / Azure OpenAI API surface | Tool 影响 | 客户应该怎么理解 |
|------|-------------------|-----------------------------------|-----------|------------------|
| LangChain | chat model abstraction + agent/tool loop | `ChatOpenAI` / `AzureChatOpenAI` 常见路径是 Chat Completions；`ChatOpenAI` 可用 `use_responses_api=True` 显式启用 Responses API，也会在设置 `reasoning` 时自动走 Responses API | `bind_tools` 接 Python function tools；显式启用 Responses API 后可用 server-side tools | API path 是 model/client 配置，不是 LangChain 的核心差异 |
| LangGraph | graph runtime；model call 只是图里的一个节点 | 取决于节点里放的 chat model，通常复用 LangChain `ChatOpenAI` / `AzureChatOpenAI` | tool 语义由节点代码和 model client 决定；LangGraph 负责状态、checkpoint、retry | LangGraph 的价值在 durable control flow，不在自己发明新模型 API |
| MAF | production agent/workflow framework + provider clients | `OpenAIChatClient` 走 Responses API，是官方推荐主路径；`OpenAIChatCompletionClient` 走 Chat Completions，用于兼容和简单场景 | Responses client 支持更完整 hosted tools：code interpreter、file search、web search、hosted MCP、image generation；Chat Completions 适合简单和兼容路径 | MAF 的 API 层更显式、更 production-oriented，但它仍只是 runtime stack 的一层 |

来源（2026-06-10 访问）：[LangChain AzureChatOpenAI Responses API 文档](https://docs.langchain.com/oss/python/integrations/chat/azure_chat_openai)、[MAF OpenAI provider 文档](https://learn.microsoft.com/en-us/agent-framework/agents/providers/openai)、[MAF Azure OpenAI provider 文档](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-openai)。

**APIM 提醒**：Chat Completions 和 Responses API 的路由不同。如果 APIM 只转发 `/chat/completions`，Responses client 可能 404；这不是框架坏，而是网关路由没配。

---

## 2. Hybrid 计算核心对比

### 2.0 AIPC runtime stack 映射

Lenovo Qira 关心的是 OS agent 的整条 runtime，不是单点 API：

| AIPC 层 | 作用 | LangChain | LangGraph | MAF |
|---------|------|-----------|-----------|-----|
| 本地模型 runtime | 低延迟、离线、隐私优先任务走本地 SLM | 很容易接 Ollama；进程生命周期应用自己管 | 同 LangChain provider 层，但嵌在 graph node 里 | Ollama provider + Foundry Local 路径；Windows/.NET 路径更完整 |
| 本地工具 / Skill | 调 OS API、本地文件、app skill、设备能力 | Python function / wrapper，简单但多在进程内 | tool 可以做成 graph node，有 typed state 和 retry 边界 | tool 可放在 provider / middleware / workflow 抽象后，和 Microsoft skill/declarative 体系更贴近 |
| 本地状态存储 | 笔记本休眠/重启/进程崩溃后恢复 | 应用自己实现 | SQLite/Postgres checkpointer 最直接 | Workflow checkpoint/time-travel 支持，但本地 backend 要选型验证 |
| 人工审批 | 发邮件/订票/改系统设置前暂停 | 手工 UI/callback | 原生 `interrupt()` | `RequestInfoExecutor` / request-info + schema validation |
| 云端 fallback | 复杂推理升级到云端 LLM | 手写路由 | conditional edge 明确写在图里 | provider/client swap + Foundry hosting 路径清晰 |
| 沙箱执行 | 隔离风险代码和工具 | 外部 wrapper | 外部 wrapper | `agent-framework-hyperlight` 是框架级选项，但要验证硬件/OS 支持 |
| 企业运维 | tracing、部署、认证、治理 | 通常接 LangSmith + 自己运维 | LangSmith + 自己运维 | 内置 OpenTelemetry、Foundry hosting、Azure Functions/A2A、Python + .NET |

因此推荐不一定是“单一赢家”：**LangGraph 适合 local durable orchestration，MAF 适合 Windows/enterprise production integration，LangChain 仍然是最快的集成和原型层。**

### 2.1 本地模型能力

用 Ollama 跑本地模型时，各框架能做什么：

| 能力 | LangChain | LangGraph | MAF |
|------|:---------:|:---------:|:---:|
| Chat completion | ✅ | ✅ | ✅ |
| Structured output (JSON) | ✅ | ✅ | ✅ |
| **Tool calling** | ✅ | ✅ | ✅ 取决于模型 |
| **Streaming** | ✅ | ✅ | ✅ |

MAF 的关键限制不是框架不支持，而是**本地模型是否支持 tool calling**。因此 demo 不能只测 `qwen3:0.6b`，需要至少测一个明确支持 tool calling 的 Ollama 模型（如 `qwen2.5:3b` 或 `qwen3:4b`）。

### 2.2 本地 ↔ 云端路由

| 框架 | 路由机制 | 可见性 | 灵活性 |
|------|---------|:------:|:------:|
| LangChain | 手动 if/else | 低 | 中 |
| LangGraph | conditional edge（在图里显式定义） | ✅ 高 | ✅ 高 |
| MAF | IChatClient 接口切换 | 中 | ✅ 高（最干净的抽象） |

LangGraph 的 conditional edge 最直观——路由规则就写在图定义里，一眼能看出什么条件走本地、什么条件走云端。MAF 的 IChatClient 抽象最干净——换模型改一行，业务代码不动。

### 2.3 状态持久化（设备重启恢复）

| 框架 | 持久化机制 | 本地友好？ |
|------|-----------|:---------:|
| LangChain | ❌ 无 | N/A |
| LangGraph | SQLite checkpointer | ✅✅ 一个 `.db` 文件搞定 |
| MAF Agent | Session scope | ⚠️ 需要按场景选存储 |
| MAF Workflow | Checkpointing + time-travel | ✅ 支持；本地 backend 需实测 |

LangGraph 的 SQLite checkpointer 仍然是最简单、最明确的本地 checkpoint 方案。MAF 也支持 workflow checkpointing / time-travel，但本地只跑时的存储路径需要在 demo 里实测，不应写成“没有”。

### 2.4 Crash Recovery

酒店 API 在天气和机票成功后超时：

| 框架 | 天气+机票结果 | 恢复方式 | 浪费的 API 调用 |
|------|:----------:|---------|:--------------:|
| LangChain | ❌ 丢失 | 从头重跑全部 | 2 次（白调了） |
| LangGraph | ✅ checkpoint 里 | 从最近 checkpoint 恢复，只重试酒店 | 0 |
| MAF Workflow | ✅ superstep 里 | Durable Task replay，跳过已完成步骤 | 0 |

### 2.5 沙箱隔离

| 框架 | 内置沙箱 | 机制 |
|------|:-------:|------|
| LangChain | ❌ | 工具就是主进程里的 Python 函数 |
| LangGraph | ❌ | 同上 |
| MAF | ⚠️ Beta | `agent-framework-hyperlight`——工具在 Hyperlight micro-VM 里跑（1-2ms 冷启动） |

MAF 的 Hyperlight 集成是唯一的框架级沙箱选项，但还是 beta。生产环境三个框架都需要外部沙箱层（MXC / Hyperlight standalone / OS 级容器）。

**运行约束**：Hyperlight 需要 Windows host 具备 WHP / hypervisor 支持。本次 Azure VM 环境里，MXC/Hyperlight 已经走到 VM creation，但失败于 `No hypervisor was found`。因此本 repo 把 Hyperlight 当作架构差异点，而不是 Azure VM 上已验证的结果。

---

## 3. 公平评估

### 各框架最强项

| 框架 | AIPC 最强项 |
|------|------------|
| **LangChain** | **最快原型 + 最全模型生态**——80+ 模型集成，5 行代码建 agent，Ollama 全功能支持（包括 tool calling） |
| **LangGraph** | **最好的本地 runtime**——Ollama 全功能、SQLite 本地持久化、conditional edge 显式路由、interrupt() HITL。为有状态工作流 + 设备重启恢复量身设计。 |
| **MAF** | **最完整的 Windows production runtime**——Ollama provider、Foundry Local、workflow checkpointing/time-travel、OpenTelemetry、middleware、C#/.NET、Foundry hosting，以及三框架里唯一的 Hyperlight 原生沙箱集成 |

### 各框架最弱项（诚实评估）

| 框架 | AIPC 最弱项 |
|------|------------|
| **LangChain** | 无状态持久化、无 crash recovery、无 HITL。对生产 AIPC 来说只能做原型。 |
| **LangGraph** | 无内置 observability（要 LangSmith），只有 Python（没有 C#），无沙箱集成。 |
| **MAF** | 能力最全但也最重：Ollama / Foundry Local / Hyperlight 都是可选包，模型能力和本地 checkpoint backend 需要逐项实测，学习曲线高于 LangChain/LangGraph。 |

### 综合矩阵

| AIPC 需求 | LangChain | LangGraph | MAF |
|:---------|:---------:|:---------:|:---:|
| 完全离线运行 | ✅ | ✅✅ | ✅ Ollama / Foundry Local，取决于模型 |
| 设备重启恢复 | ❌ | ✅✅ SQLite 本地 | ✅ Workflow checkpointing；本地 backend 待实测 |
| 本地/云端路由 | 手动 | ✅✅ Conditional edge | ✅ IChatClient 切换 |
| Crash recovery | ❌ | ✅ | ✅ |
| HITL 审批 | ❌ | ✅ | ✅ + schema 验证 |
| 沙箱隔离 | ❌ 需 wrapper | ❌ 需 wrapper | ✅ `agent-framework-hyperlight` |
| 可观测性 | ❌ | ❌ | ✅✅ 内置 OTel |
| C#/.NET | ❌ | ❌ | ✅✅ |
| 轻量级 | ✅ | ✅ | ⚠️ 较重 |

---

## 4. 架构建议

### 本地优先的 AIPC（离线、轻量、跨平台优先）

```
App UI → LangGraph StateGraph → Ollama (全功能) + Azure OpenAI (conditional edge)
                              → 本地工具 + SQLite checkpoint
```

### 云端优先 + 本地回退（企业、governance、Windows C# 优先）

```
App UI (C#) → MAF WorkflowBuilder → Azure OpenAI / Foundry (云端)
                                   → Ollama / Foundry Local (本地推理，tool calling 取决于模型)
                                   → OpenTelemetry → Azure Monitor
```

### 混合：LangGraph 本地 + MAF 云端

```
本地: LangGraph + Ollama + SQLite (离线 agent，全功能)
       ↕ A2A protocol
云端: MAF Foundry Hosted Agent (复杂推理，OTel 追踪)
```

---

## 5. 术语边界

| 产品 | 是什么 | 和 MAF 的关系 |
|------|--------|--------------|
| **MAF** | 开源编排框架（本评估对象） | — |
| **Foundry Agent Service** | 云端托管 | MAF 可部署上去 |
| **Foundry Local** | 端侧模型推理 runtime | **不是 agent 框架**——只提供本地 LLM serving，不做编排/状态/HITL。可以作为任何框架的模型 backend。注意：部分团队反馈它对端侧设备来说偏重。 |
| **Semantic Kernel / AutoGen** | 上一代 SDK | MAF 继任者 |

---

## 6. 复现 / 目录结构

详见 [README.md (English)](README.md#6-reproducing)。

```
├── README.md / README-CN.md
├── requirements.txt / .env.example
├── scenarios/           # 独立旅行 agent 实现
└── portal/              # 5 场景 × 3 框架 对比 Portal
```

---

## 关联 Repo

- [Microsoft Agent Framework Workflow Demos](../Microsoft-Agent-Framework/)
- [Hyperlight & MXC Sandbox Landscape](../Hyperlight-MXC-Sandbox-Landscape/)
