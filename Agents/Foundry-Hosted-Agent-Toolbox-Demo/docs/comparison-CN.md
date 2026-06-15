# 横向对比：Hosted Agent + Toolbox vs 其他 Agent Stack

本文是 customer-neutral 的对比，覆盖主要 agent stack。每个条目都映射到同一组架构问题：agent 在哪跑、tool 在哪、versioning 怎么做、auth 怎么跨边界、消费侧的 vendor portability 如何。

参考来源（生产决策前请验证当前版本）：

- Foundry Hosted Agents: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
- Foundry Toolbox: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox
- OpenAI Assistants API: https://platform.openai.com/docs/assistants/overview
- AWS Bedrock Agents: https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html
- Vertex AI Agent Builder: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/overview
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- LangGraph + LangChain Tools: https://langchain-ai.github.io/langgraph/
- Semantic Kernel: https://learn.microsoft.com/en-us/semantic-kernel/
- Model Context Protocol: https://modelcontextprotocol.io/

## 一览矩阵

| 性质 | Foundry Hosted Agent + Toolbox | OpenAI Assistants API | AWS Bedrock Agents | Vertex AI Agent Builder | LangGraph + LangChain Tools | Semantic Kernel + plugins |
| --- | --- | --- | --- | --- | --- | --- |
| Agent 代码在哪跑 | Managed container，per-session sandbox | OpenAI 服务侧 | AWS 服务侧 | Google 服务侧 | 自托管 | 自托管 |
| Caller 协议 | Responses（OpenAI-compatible）+ Invocations + A2A | Threads + runs | Bedrock Agents API | Reasoning Engine API | 自定义（LangServe / FastAPI） | 自定义 |
| Per-agent identity | Microsoft Entra ID 部署时自动签发 | OpenAI API key | IAM role | Service account | 无（你自己接） | 无（你自己接） |
| Tool catalog | Foundry Toolbox（受管 MCP endpoint，版本化） | Per assistant 在 API 中定义 | Action groups + Lambda + KB | Per agent 注册 | LangChain tools registry（in process） | Plugins（in process） |
| Tool transport | MCP（Streamable HTTP, JSON-RPC 2.0） | OpenAI function calling | Action group → Lambda invoke | Function calling + tool API | Native Python objects | Native C#/Python objects |
| 跨 framework tool 复用 | 是（任何 MCP client） | 否（仅 OpenAI Threads） | 否（仅 Bedrock Agents） | 否（仅 Vertex agents） | 有限（LangChain runtime） | 有限（Semantic Kernel runtime） |
| 版本化 tool 清单 | Toolbox versions，不可变，`default_version` 指针 | 平台层无 | Action group versions | 有限 | 无（代码管理） | 无（代码管理） |
| 内置 tool | Code Interpreter、Web Search (Bing)、Azure AI Search、File Search、OpenAPI、A2A、custom MCP | Code Interpreter、File Search | Knowledge Bases、Lambda actions | Vertex Search、Extensions | 无（社区包） | 无（社区 plugin） |
| Approval gating | Per-tool `require_approval` 通过 MCP `_meta` 暴露 | 手动通过 run-step events | 手动 | 手动 | 手动 | 手动 |
| Per-agent identity 进 tool | 是（agent Entra ID + project connections） | 基于 API key | 基于 IAM | 基于 service account | DIY | DIY |
| 有状态 sandbox | `$HOME` + `/files` per session，跨 idle 持久化 | Threads 保留消息，无通用文件系统 | Memory 可配，无文件系统 | 有限 | DIY | DIY |
| 可观测性 | OpenTelemetry 自动注入 Application Insights | OpenAI dashboard | CloudWatch | Cloud Logging / Trace | DIY | DIY |
| 网络隔离 | Private link + VNet for tools（带 caveat） | 公开 endpoint | VPC-aware | VPC SC 支持 | DIY | DIY |
| 部署模型 | `azd deploy` container image | API config | CloudFormation / 控制台 | gcloud / 控制台 | 自己的 CI/CD | 自己的 CI/CD |
| 多云 / 开放消费 | MCP endpoint 对任何 MCP client 开放 | 仅 OpenAI 生态 | 仅 AWS | 仅 GCP | 设计上开放 | 设计上开放 |
| 当前状态 | Public preview | GA | GA | GA | OSS GA | OSS GA |

## 什么时候选什么

### Foundry Hosted Agent + Toolbox

选它当：

- 需要单个受管 agent endpoint 集成多个 Azure 数据面服务。
- 想要中心化、版本化的 tool catalog，被任何说 MCP 的 framework 复用。
- 需要 per-agent Entra identity、RBAC、Application Insights，但不想自己接。
- 场景能容忍一个 container 跳，看重 approval gating、audit、`default_version` 语义。
- 预期 tool 清单演进比 agent 代码快。

避开它当：

- 完全不在 Azure。
- Agent 代码必须在设备上跑或在禁止 push 到 Azure Container Registry 的私有边界内。

### OpenAI Assistants API

选它当：

- 已锁定 OpenAI 生态，只用 OpenAI 内置 tool。
- 想要最简单的 threaded conversation + 受管 message store。
- Tool 清单小且稳定，乐意 per assistant 直接接每个 tool。

避开它当：

- 需要跨 framework tool 复用、版本化 tool catalog、per-agent 企业 identity。
- 需要在自己的计算边界内跑 agent 代码。

### AWS Bedrock Agents

选它当：

- 已锁定 AWS，tool 最自然建模成 Lambda 或 Bedrock Knowledge Base。
- 需要原生 IAM identity、CloudWatch trace、控制台驱动的 action group 创作。
- Agent 边界对齐 AWS account / region 边界。

避开它当：

- 需要可被非-AWS framework 复用的 tool catalog。
- 需要 MCP-aware IDE 和 copilot 的发现能力。

### Vertex AI Agent Builder

选它当：

- 已锁定 GCP，想要与 Vertex Search 和 Reasoning Engine 的第一方集成。
- 需要 GCP IAM 和 VPC SC 跨 agent 与 tool。

避开它当：

- 需要可被非-GCP runtime 消费的开放表面。

### LangGraph + LangChain Tools

选它当：

- 想要完全控制 agent 状态机，包括任意图拓扑、条件边、human-in-the-loop 节点。
- 愿意自托管 runtime（或通过 LangServe / LangSmith），自己 own auth / identity / tool registry。
- 需要快速本地迭代和强 OSS 工具链。

避开它当：

- 需要 per-agent managed identity、中心 tool catalog、平台级 approval gating，且不想自己写。
- 想要稳定的 Responses-protocol endpoint 而不愿自己包 FastAPI/LangServe。

注：LangGraph 可以通过 `langchain_azure_ai.tools.AzureAIProjectToolbox` 消费 Foundry Toolbox（Toolbox docs Step 4）。两者互补，不竞争。

### Semantic Kernel

选它当：

- 团队 .NET-first，想要 plugin 编排和 Microsoft Agent Framework / Copilot Studio / M365 紧密集成。
- 需要原生 function-calling planning + 强类型。

避开它当：

- Runtime 非 .NET 且想要统一 tool plane。

注：Semantic Kernel 与 Microsoft Agent Framework 在收敛；Foundry-hosted 场景的前进路径是 Agent Framework。

### Microsoft Agent Framework（standalone）

用它当：

- 同一份 agent 代码要在本地和 Foundry Hosted Agent 都能跑。
- 想要一等公民的 MCP 支持（`MCPStreamableHTTPTool`）。

来自本 repo `main.py` 和 `scripts/smoke_test.py` 的注意点：

- 框架的 `MCPStreamableHTTPTool` 接受一个 `httpx.AsyncClient`，可以在构造时注入 Toolbox preview header（`Foundry-Features: Toolboxes=V1Preview`）和 bearer token。
- 框架的 hosted runtime（`agent-framework-foundry-hosting`）提供 `ResponsesHostServer`，让 Responses 协议形态在本地和 hosted container 一致。

## 决策路径

按顺序回答；第一个 yes 决定你的栈：

1. Agent 代码必须在设备上或完全离开 Azure？→ 大概率 LangGraph 或 Semantic Kernel 自托管。
2. 锁定 AWS 或 GCP？→ Bedrock Agents 或 Vertex AI Agent Builder。
3. 只需要 OpenAI 内置 tool？→ Assistants API。
4. 需要版本化、MCP-discoverable 的 tool catalog 被多 framework 复用？→ Foundry Hosted Agent + Toolbox。
5. 否则 → Microsoft Agent Framework standalone 或 LangGraph standalone，看你团队已有技能。

## 这份对比不是什么

- 不是 benchmark。没有 latency / throughput / cost 数字；生产决策需要你自己测。
- 不是 feature parity 表。每个平台都有这里没列的 feature。
- 不是终审判决。Preview feature 变化快，承诺前先验证当前状态。
