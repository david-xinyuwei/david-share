# MCP Protocol Deep Dive (As Used by This Repo)

The Foundry Toolbox endpoint speaks the Model Context Protocol (MCP) over Streamable HTTP. This document explains, in working-engineer detail, how the protocol works, why it was chosen for the toolbox surface, and what each round-trip in this repo actually does on the wire.

Sources:

- MCP project: https://modelcontextprotocol.io/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Toolbox how-to (Streamable HTTP, headers, listing, calling): https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox

## 1. What MCP Is

MCP is an open protocol that lets a host (typically an LLM-powered agent) connect to external servers that expose **tools**, **resources**, and **prompts**. The wire format is JSON-RPC 2.0. The transport in this repo is Streamable HTTP. Other transports exist (stdio, WebSocket).

Three primitives:

| Primitive | Purpose |
| --- | --- |
| Tool | A callable function with an input schema; the agent decides when to call it. |
| Resource | A readable item identified by a URI; the agent or user can request its contents. |
| Prompt | A reusable prompt template the server publishes. |

The Foundry Toolbox MCP endpoint primarily exposes **tools**. It does not implement `prompts/list` (Toolbox docs troubleshooting table). Clients must pass `load_prompts=False` (or equivalent) to avoid 500 errors on connection.

## 2. Why MCP for the Toolbox Surface

Three properties make MCP a better fit than alternatives:

| Need | Why MCP fits |
| --- | --- |
| Discovery at runtime | `tools/list` lets the agent fetch the current tool catalog without hard-coded definitions. |
| Server-side execution | `tools/call` keeps execution and credentials inside the server, behind the agent identity boundary. |
| Open client side | Any framework with an MCP client can consume the same toolbox. |

Compare with two alternatives:

- **OpenAPI**: rich schema but no native discovery model and no first-class notion of "tool" vs "resource". Good for declarative API integration, less natural for an evolving tool catalog. Foundry's Toolbox includes an `OpenAPITool` that wraps an OpenAPI spec into a tool — OpenAPI sits inside the catalog, not in front of it.
- **OpenAI function calling**: works inside one process; does not define a remote protocol or version contract.

MCP keeps the discovery and execution semantics, while letting Foundry layer aggregation, versioning, and policy on top.

## 3. Streamable HTTP and JSON-RPC 2.0

### Streamable HTTP

The MCP server exposes a single HTTP endpoint that accepts JSON-RPC frames and can stream responses (chunked). The Toolbox documentation explicitly states that **non-streaming `tools/call` is not supported** and returns 500. Always use `stream=True` (the SDK's default) when invoking tools.

The repo uses `mcp.client.streamable_http.streamablehttp_client` (`scripts/verify_toolbox.py`) which sets up the streaming session, and the Microsoft Agent Framework's `MCPStreamableHTTPTool` (`main.py`, `scripts/smoke_test.py`) which wraps the same transport for the agent runtime.

### JSON-RPC 2.0

The wire frame is standard JSON-RPC 2.0:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

Methods used in this repo:

| Method | Purpose | Where used |
| --- | --- | --- |
| `initialize` | First call after connecting; required before any other method. | `verify_toolbox.py`, framework auto-calls. |
| `tools/list` | List all tools, their input schemas, and `_meta.tool_configuration`. | `verify_toolbox.py`, framework on agent startup. |
| `tools/call` | Invoke a specific tool with arguments. Streaming. | Framework when the agent emits a function call. |

The toolbox does not implement `prompts/list` or MCP `ping`. Calling `send_ping()` returns 500 (Toolbox docs troubleshooting). The Microsoft Agent Framework's `MCPStreamableHTTPTool._ensure_connected()` historically called ping; current versions skip it for Foundry endpoints.

## 4. Required Headers

Every request to the Toolbox MCP endpoint must include:

| Header | Value | Why |
| --- | --- | --- |
| `Authorization` | `Bearer <token>` for `https://ai.azure.com/.default` | Token bound to your developer identity (local) or the agent identity (hosted). |
| `Foundry-Features` | `Toolboxes=V1Preview` | Preview feature flag; calls without it fail (Toolbox docs, Step 2). |
| `Content-Type` | `application/json` | Standard. |

The repo wires both as `httpx.AsyncClient` headers (`main.py`, `scripts/smoke_test.py`):

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Foundry-Features": "Toolboxes=V1Preview",
}
```

And `verify_toolbox.py` passes the same headers to `streamablehttp_client(url, headers=headers)`.

## 5. The Endpoint Shape

Two endpoint forms exist (Toolbox docs, Step 2):

| Endpoint | Form | Use |
| --- | --- | --- |
| Version-specific | `{project_endpoint}/toolboxes/{name}/versions/{version}/mcp?api-version=v1` | Validate or canary one immutable version. |
| Consumer | `{project_endpoint}/toolboxes/{name}/mcp?api-version=v1` | Connect agents; always serves the current `default_version`. |

The version-specific form is what you point a verification script at when staging a new release. The consumer form is what production agents use, so promoting `default_version` flips behavior with no code change in the agent.

The "FOUNDRY_" prefix is reserved by the platform — environment variables prefixed with `FOUNDRY_` may be silently overwritten in the hosted environment (Toolbox docs troubleshooting). This repo uses `TOOLBOX_MCP_ENDPOINT` and `TOOLBOX_NAME` to avoid the trap.

## 6. Tool Identity and Naming

The toolbox returns each tool with a `name`, a `description`, an `inputSchema`, and a `_meta` block. Naming rules:

- For MCP-backed tools, names are prefixed with the `server_label`: e.g., `myserver.get_info`. The dot is significant.
- Some agent runtimes (e.g., GitHub Copilot SDK) reject dots in tool names; Foundry's Copilot SDK bridge replaces `.` with `_` and reverses on call.
- Built-in tools use their default names (`code_interpreter`, `web_search`, `azure_ai_search`, `file_search`).

Tool argument names matter and are case-sensitive. The Toolbox docs list canonical argument names per built-in tool:

| Tool | Argument |
| --- | --- |
| `azure_ai_search` | `{"query": "..."}` |
| `file_search` | `{"queries": ["..."]}` |
| `code_interpreter` | `{"code": "..."}` |
| `web_search` | `{"search_query": "..."}` |
| `a2a` | `{"message": {"parts": [...]}}` |
| `mcp` (custom) | server-defined |

If you supply `query` to File Search (which expects `queries`), the call fails — the schema lookup is exact.

## 7. The `_meta` Block and Approval Gating

Each tool entry in `tools/list` includes a `_meta.tool_configuration` block:

```json
{
  "name": "myserver.my_tool",
  "_meta": {
    "tool_configuration": {
      "type": "mcp",
      "server_label": "myserver",
      "server_url": "https://...",
      "require_approval": "always"
    }
  }
}
```

`require_approval` values:

| Value | Agent runtime behavior |
| --- | --- |
| `"never"` | Invoke freely. |
| `"always"` | Surface the pending action to the user; wait for confirmation; then call. |

Two important properties:

- The MCP endpoint **does not block** `tools/call` based on `require_approval`. The agent runtime is responsible for honoring it.
- Detection runs once at startup when the agent reads `tools/list`. There is no per-call overhead.

The pattern (LangGraph example in the Toolbox docs, applicable to any runtime):

1. Call `tools/list`.
2. Build a map `{tool_name: require_approval}`.
3. For tools with `"always"`, inject a system-prompt constraint or wrap the tool with an approval gate.

This split — server publishes intent, runtime enforces — keeps the policy where the tool owner sets it and the gate where the user interacts.

## 8. Errors You Will See

From the Toolbox docs and this repo's experience:

| Code / symptom | Meaning | Fix |
| --- | --- | --- |
| `401 Unauthorized` | Wrong scope or expired token | Refresh token for `https://ai.azure.com/.default`; check tenant. |
| `400 invalid_payload: Multiple tools without identifiers` | Two unnamed tools of the same type | Add a unique `name` to each. |
| `-32006 CONSENT_REQUIRED` | OAuth-backed MCP needs user consent | Open the consent URL in browser; retry. |
| `500 on prompts/list` | Foundry MCP doesn't implement prompts | Set `load_prompts=False`. |
| `500 on send_ping` | Foundry MCP doesn't implement ping | Don't call ping; override to no-op. |
| `500 on non-streaming tools/call` | Streaming required | Use `stream=True`. |
| `tools/list` returns zero | Toolbox not provisioned in region, or remote MCP/A2A connection invalid | Wait 10 seconds and retry; verify connection credentials. |
| `DeploymentNotFound` from `web_search` invoke | Preview runtime path issue | Use `direct_web_search` (Responses API path), see [why-this-architecture.md](why-this-architecture.md) §7. |

## 9. The Wire as Used in This Repo

At agent startup (`main.py`):

```text
POST {toolbox_endpoint} HTTP/1.1
Authorization: Bearer <token>
Foundry-Features: Toolboxes=V1Preview
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}

POST {toolbox_endpoint}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
→ returns [{"name":"code_interpreter", "_meta": {...}, ...}]
```

At each user turn requesting code:

```text
POST {toolbox_endpoint}
{
  "jsonrpc":"2.0",
  "id":N,
  "method":"tools/call",
  "params":{
    "name":"code_interpreter",
    "arguments":{"code":"sum(i*i for i in range(1,6))"}
  }
}
→ streaming response with content[] entries containing the result
```

At each user turn requesting current public web facts (`direct_web_search` path):

```text
POST {project_endpoint}/openai/v1/responses HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "model": "<deployment>",
  "tools": [{"type": "web_search"}],
  "input": "Search the web for: ..."
}
→ Responses API output_text with citations in annotations[]
```

Both paths are visible in `scripts/smoke_test.py` and `scripts/http_smoke_test.py`. Reading those alongside this document gives you the full request/response cycle as the agent runs it.

## 10. What MCP Does Not Solve

- **It is not a model API**. The agent still calls a model deployment for reasoning.
- **It is not a workflow engine**. Multi-step orchestration with retries, compensations, and durable state belongs elsewhere (Durable Functions, Step Functions, your own state machine).
- **It is not an enforcement boundary by itself**. Auth, rate limiting, approval gating must be implemented inside the MCP server (Toolbox does this) or by the agent runtime.

MCP is the *connector* between agent and tool catalog. Everything around it — model, planner, governance, durability — is your stack to assemble.
