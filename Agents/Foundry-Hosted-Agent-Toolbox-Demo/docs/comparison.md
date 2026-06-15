# Comparison: Hosted Agent + Toolbox vs Other Agent Stacks

This document is a customer-neutral comparison of major agent stacks. Each entry maps to the same architectural questions: where the agent runs, where tools live, how versioning works, how auth crosses tool boundaries, and how vendor-portable the consumption surface is.

Sources used (please verify versions for any production decision):

- Foundry Hosted Agents: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
- Foundry Toolbox: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox
- OpenAI Assistants API: https://platform.openai.com/docs/assistants/overview
- AWS Bedrock Agents: https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html
- Vertex AI Agent Builder: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/overview
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- LangGraph + LangChain Tools: https://langchain-ai.github.io/langgraph/
- Semantic Kernel: https://learn.microsoft.com/en-us/semantic-kernel/
- Model Context Protocol: https://modelcontextprotocol.io/

## At-a-Glance Matrix

| Property | Foundry Hosted Agent + Toolbox | OpenAI Assistants API | AWS Bedrock Agents | Vertex AI Agent Builder | LangGraph + LangChain Tools | Semantic Kernel + plugins |
| --- | --- | --- | --- | --- | --- | --- |
| Where agent code runs | Managed container, per-session sandbox | Server-side, OpenAI-managed | Server-side, AWS-managed | Server-side, Google-managed | Wherever you host it | Wherever you host it |
| Caller protocol | Responses (OpenAI-compatible) + Invocations + A2A | Threads + runs | Bedrock Agents API | Reasoning Engine API | Custom (LangServe / FastAPI) | Custom |
| Per-agent identity | Microsoft Entra ID auto-issued at deploy | OpenAI API key | IAM role | Service account | None (your auth) | None (your auth) |
| Tool catalog | Foundry Toolbox (managed MCP endpoint, versioned) | Tools defined per assistant in API | Action groups + Lambda + KB | Tools registered per agent | LangChain tools registry (in process) | Plugins (in process) |
| Tool transport | MCP (Streamable HTTP, JSON-RPC 2.0) | OpenAI function calling | Action group → Lambda invoke | Function calling + tool API | Native Python objects | Native C#/Python objects |
| Cross-framework tool reuse | Yes (any MCP client) | No (OpenAI Threads only) | No (Bedrock Agents only) | No (Vertex agents only) | Limited (LangChain runtime) | Limited (Semantic Kernel runtime) |
| Versioned tool inventory | Toolbox versions, immutable, `default_version` pointer | None at platform level | Action group versions | Limited | None (code-managed) | None (code-managed) |
| Built-in tools | Code Interpreter, Web Search (Bing), Azure AI Search, File Search, OpenAPI, A2A, custom MCP | Code Interpreter, File Search | Knowledge Bases, Lambda actions | Vertex Search, Extensions | None (community packages) | None (community plugins) |
| Approval gating | Per-tool `require_approval` surfaced via MCP `_meta` | Manual via run-step events | Manual | Manual | Manual | Manual |
| Per-agent identity into tools | Yes (agent's Entra ID + project connections) | API-key-based | IAM-based | Service-account-based | DIY | DIY |
| Stateful sandbox | `$HOME` + `/files` per session, persist across idle | Threads keep messages, no general filesystem | Memory configured, no filesystem | Limited | DIY | DIY |
| Observability | OpenTelemetry into Application Insights, auto-injected | OpenAI dashboard | CloudWatch | Cloud Logging / Trace | DIY | DIY |
| Network isolation | Private link + VNet for tools (with caveats) | Public endpoint | VPC-aware | VPC SC supported | DIY | DIY |
| Deployment model | `azd deploy` of container image | API config | CloudFormation / console | gcloud / console | Your CI/CD | Your CI/CD |
| Multi-cloud / open consumption | MCP endpoint is open to any MCP client | OpenAI ecosystem only | AWS only | GCP only | Open by design | Open by design |
| Today's status | Public preview | GA | GA | GA | OSS GA | OSS GA |

## When To Choose Which

### Foundry Hosted Agent + Toolbox

Choose when:

- You need a single managed agent endpoint that integrates with multiple Azure data plane services.
- You want a central, versioned tool catalog usable by any framework that speaks MCP.
- You need per-agent Entra identity, RBAC, and Application Insights without bespoke wiring.
- Your scenario tolerates one container hop and you value approval gating, audit, and `default_version` semantics.
- You expect tool inventory to evolve faster than agent code.

Avoid when:

- You are not using Azure at all.
- You need agent code to run on device or behind a private boundary that prohibits container build / push to Azure Container Registry.

### OpenAI Assistants API

Choose when:

- You are committed to the OpenAI ecosystem and you only need OpenAI's built-in tools.
- You want the simplest possible threaded conversation model with managed message store.
- Your tool inventory is small and stable; you are happy to wire each tool directly per assistant.

Avoid when:

- You need cross-framework tool reuse, versioned tool catalog, or per-agent enterprise identity.
- You need to run agent code in your own compute boundary.

### AWS Bedrock Agents

Choose when:

- You are committed to AWS and your tools are best modeled as Lambda functions or Bedrock Knowledge Bases.
- You want native IAM identity, CloudWatch trace, and console-driven action group authoring.
- Your agent boundary aligns with AWS account and region boundaries.

Avoid when:

- You need a tool catalog reusable from non-AWS frameworks.
- You need MCP-style discovery from MCP-aware IDEs and copilots.

### Vertex AI Agent Builder

Choose when:

- You are committed to GCP and want first-party integration with Vertex Search and the Reasoning Engine.
- You need GCP IAM and VPC SC across the agent and its tools.

Avoid when:

- You require an open consumption surface across non-GCP runtimes.

### LangGraph + LangChain Tools

Choose when:

- You want full control over the agent state machine, including arbitrary graph topologies, conditional edges, and human-in-the-loop nodes.
- You are willing to host the runtime yourself (or via LangServe / LangSmith) and own auth, identity, and tool registry.
- You need rapid local iteration with strong open-source tooling.

Avoid when:

- You need a managed identity per agent, central tool catalog, or platform-level approval gating without writing it yourself.
- You want a stable Responses-protocol endpoint without packaging FastAPI/LangServe yourself.

Note: LangGraph can consume Foundry Toolbox via `langchain_azure_ai.tools.AzureAIProjectToolbox` (Toolbox docs, Step 4). The two are complementary, not competitive.

### Semantic Kernel

Choose when:

- Your team is .NET-first and you want plugin orchestration tightly integrated with Microsoft Agent Framework, Copilot Studio, or M365 surfaces.
- You need native function-calling planning with strong typing.

Avoid when:

- Your runtime is non-.NET and you want a uniform tool plane.

Note: Semantic Kernel and Microsoft Agent Framework converge over time; Agent Framework is the path forward for Foundry-hosted scenarios.

### Microsoft Agent Framework (standalone)

Use when:

- You want the same agent code to run locally and as a Foundry Hosted Agent.
- You want first-class MCP support via `MCPStreamableHTTPTool`.

Notes from this repo's `main.py` and `scripts/smoke_test.py`:

- The framework's `MCPStreamableHTTPTool` accepts an `httpx.AsyncClient` so you can inject the Toolbox preview header (`Foundry-Features: Toolboxes=V1Preview`) and your bearer token at construction time.
- The framework's hosted runtime (`agent-framework-foundry-hosting`) provides `ResponsesHostServer`, which gives you the Responses protocol shape both locally and in the hosted container.

## Decision Worksheet

Answer in order; the first "yes" picks your stack.

1. Do you need to run agent code on device or fully off Azure? → Likely LangGraph or Semantic Kernel self-hosted.
2. Are you locked into AWS or GCP? → Bedrock Agents or Vertex AI Agent Builder.
3. Do you need OpenAI's built-in tools and nothing else? → Assistants API.
4. Do you need a versioned, MCP-discoverable tool catalog reusable from many frameworks? → Foundry Hosted Agent + Toolbox.
5. Otherwise → either Microsoft Agent Framework standalone or LangGraph standalone, depending on your team's existing skills.

## What This Comparison Is Not

- Not a benchmark. No latency, throughput, or cost numbers are claimed; production decisions need your own measurements.
- Not a feature parity table. Each platform has features that do not appear here.
- Not a final verdict. Preview features change quickly; verify current status before committing.
