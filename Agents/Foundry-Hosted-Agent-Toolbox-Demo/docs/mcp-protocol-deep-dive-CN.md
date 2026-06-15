# MCP 协议详解（本 Repo 视角）

Foundry Toolbox endpoint 走 Model Context Protocol（MCP），传输是 Streamable HTTP。本文以工程师视角解释协议如何工作、Foundry 为什么选它做 toolbox 表面、本 repo 中每个 round-trip 在线上具体长什么样。

参考来源：

- MCP project: https://modelcontextprotocol.io/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Toolbox how-to: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox

## 1. MCP 是什么

MCP 是开放协议，让一个 host（典型是 LLM-powered agent）连接到外部 server，server 暴露 **tools / resources / prompts**。Wire format 是 JSON-RPC 2.0。本 repo 的 transport 是 Streamable HTTP。还有其他 transport（stdio、WebSocket）。

三个 primitive：

| Primitive | 用途 |
| --- | --- |
| Tool | 一个带 input schema 的可调用函数；agent 决定何时调用。 |
| Resource | 一个带 URI 的可读项；agent 或 user 可以请求其内容。 |
| Prompt | server 发布的可重用 prompt template。 |

Foundry Toolbox MCP endpoint 主要暴露 **tools**。它不实现 `prompts/list`（Toolbox docs troubleshooting）。Client 必须传 `load_prompts=False`（或等价）才不会在连接时报 500。

## 2. 为什么 Toolbox 表面选 MCP

三个性质让 MCP 比替代品更合适：

| 需求 | MCP 怎么满足 |
| --- | --- |
| Runtime discovery | `tools/list` 让 agent 在不硬编码定义的情况下抓当前 tool catalog。 |
| Server-side execution | `tools/call` 把执行和 credential 留在 server 里，在 agent identity 边界后面。 |
| 客户端开放 | 任何带 MCP client 的 framework 都能消费同一个 toolbox。 |

对比两个替代：

- **OpenAPI**：schema 丰富但没有原生 discovery，没有"tool vs resource"一等概念。适合声明式 API 集成，不适合演进的 tool catalog。Foundry Toolbox 自带 `OpenAPITool` 把 OpenAPI spec 包装成 tool —— OpenAPI 在 catalog *里面*，不在前面。
- **OpenAI function calling**：在一个进程里 work；不定义远程协议或版本契约。

MCP 保留 discovery + execution 语义，让 Foundry 在它之上叠加 aggregation / versioning / policy。

## 3. Streamable HTTP + JSON-RPC 2.0

### Streamable HTTP

MCP server 暴露单个 HTTP endpoint，接 JSON-RPC frame，可以流式返回（chunked）。Toolbox 文档明确说 **non-streaming `tools/call` 不支持**，会返回 500。调 tool 时一律 `stream=True`（SDK 默认）。

本 repo 用 `mcp.client.streamable_http.streamablehttp_client`（`scripts/verify_toolbox.py`）建 streaming session，用 Microsoft Agent Framework 的 `MCPStreamableHTTPTool`（`main.py`、`scripts/smoke_test.py`）在 agent runtime 包装同一个 transport。

### JSON-RPC 2.0

Wire frame 是标准 JSON-RPC 2.0：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

本 repo 用到的方法：

| Method | 用途 | 在哪用 |
| --- | --- | --- |
| `initialize` | 连接后第一个调用；其他 method 之前必调。 | `verify_toolbox.py`、framework 自动调。 |
| `tools/list` | 列出所有 tool、input schema、`_meta.tool_configuration`。 | `verify_toolbox.py`、framework 启动时。 |
| `tools/call` | 用 arguments 调指定 tool。Streaming。 | Framework 在 agent 发出 function call 时。 |

Toolbox 不实现 `prompts/list` 和 MCP `ping`。调 `send_ping()` 返回 500（Toolbox docs troubleshooting）。Microsoft Agent Framework 的 `MCPStreamableHTTPTool._ensure_connected()` 历史上调 ping；当前版本对 Foundry endpoint 跳过它。

## 4. 必需 header

每个对 Toolbox MCP endpoint 的请求必须带：

| Header | 值 | 原因 |
| --- | --- | --- |
| `Authorization` | `Bearer <token>`，scope 为 `https://ai.azure.com/.default` | Token 绑你的开发者身份（本地）或 agent 身份（hosted）。 |
| `Foundry-Features` | `Toolboxes=V1Preview` | Preview feature flag；不带会失败（Toolbox docs Step 2）。 |
| `Content-Type` | `application/json` | 标准。 |

本 repo 在 `httpx.AsyncClient` headers 里同时配（`main.py`、`scripts/smoke_test.py`）：

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Foundry-Features": "Toolboxes=V1Preview",
}
```

`verify_toolbox.py` 把同样的 header 传给 `streamablehttp_client(url, headers=headers)`。

## 5. Endpoint 形态

两种 endpoint 形式（Toolbox docs Step 2）：

| Endpoint | 形式 | 用途 |
| --- | --- | --- |
| Version-specific | `{project_endpoint}/toolboxes/{name}/versions/{version}/mcp?api-version=v1` | 验证或 canary 一个不可变 version。 |
| Consumer | `{project_endpoint}/toolboxes/{name}/mcp?api-version=v1` | Agent 连接；总是 serve 当前 `default_version`。 |

Version-specific 给 staging 用；consumer 给生产 agent 用，所以 promote `default_version` 不需要 agent 改代码就能切。

`FOUNDRY_` 前缀被平台保留 —— hosted 环境中以 `FOUNDRY_` 开头的环境变量可能被静默覆盖（Toolbox docs troubleshooting）。本 repo 用 `TOOLBOX_MCP_ENDPOINT` 和 `TOOLBOX_NAME` 避坑。

## 6. Tool identity 和命名

Toolbox 在 `tools/list` 里返回每个 tool 带 `name`、`description`、`inputSchema`、`_meta`。命名规则：

- MCP-backed tool 的 name 带 `server_label` 前缀：例如 `myserver.get_info`。点号有意义。
- 一些 agent runtime（如 GitHub Copilot SDK）拒绝 tool name 里的点号；Foundry 的 Copilot SDK bridge 把 `.` 换成 `_`，调用时反向。
- 内置 tool 用默认 name（`code_interpreter`、`web_search`、`azure_ai_search`、`file_search`）。

Tool 参数名重要且区分大小写。Toolbox docs 列了内置 tool 的标准参数：

| Tool | 参数 |
| --- | --- |
| `azure_ai_search` | `{"query": "..."}` |
| `file_search` | `{"queries": ["..."]}` |
| `code_interpreter` | `{"code": "..."}` |
| `web_search` | `{"search_query": "..."}` |
| `a2a` | `{"message": {"parts": [...]}}` |
| `mcp`（custom） | server-defined |

如果给 File Search 传 `query`（应该是 `queries`），调用失败 —— schema 查找精确。

## 7. `_meta` 块和 approval gating

`tools/list` 中每个 tool 条目都带 `_meta.tool_configuration`：

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

`require_approval` 取值：

| 值 | Agent runtime 行为 |
| --- | --- |
| `"never"` | 自由调。 |
| `"always"` | 把待执行 action 呈给 user，等确认，再调。 |

两个重要性质：

- MCP endpoint **不会** 因 `require_approval` 阻塞 `tools/call`。Agent runtime 负责执行。
- 检测在 agent 启动读 `tools/list` 时跑一次。无 per-call overhead。

模式（Toolbox docs 的 LangGraph 例子，对任何 runtime 都适用）：

1. 调 `tools/list`。
2. 构建 `{tool_name: require_approval}` map。
3. 对 `"always"` 的 tool，注入 system prompt 约束或包一层 approval gate。

这种"server 发布意图、runtime 强制"的拆分，让策略由 tool owner 设定、gate 在 user 交互处生效。

## 8. 你会看到的错误

来自 Toolbox docs 和本 repo 经验：

| Code / 现象 | 含义 | 修复 |
| --- | --- | --- |
| `401 Unauthorized` | Scope 错或 token 过期 | 用 `https://ai.azure.com/.default` 刷 token；查 tenant。 |
| `400 invalid_payload: Multiple tools without identifiers` | 同 type 的两个 tool 没名字 | 给每个加唯一 `name`。 |
| `-32006 CONSENT_REQUIRED` | OAuth-backed MCP 需要 user consent | 在浏览器里打开 consent URL；重试。 |
| `500 on prompts/list` | Foundry MCP 不实现 prompts | 设 `load_prompts=False`。 |
| `500 on send_ping` | Foundry MCP 不实现 ping | 别调；或 override 成 no-op。 |
| `500 on non-streaming tools/call` | 必须 streaming | 用 `stream=True`。 |
| `tools/list` 返回 0 | Toolbox 在该 region 未 provision，或远程 MCP/A2A connection 无效 | 等 10 秒重试；验证 connection credential。 |
| Web Search invoke 返回 `DeploymentNotFound` | Preview runtime path 问题 | 用 `direct_web_search`（Responses API path），见 [why-this-architecture-CN.md](why-this-architecture-CN.md) §7。 |

## 9. 本 Repo 的 wire 实况

Agent 启动时（`main.py`）：

```text
POST {toolbox_endpoint} HTTP/1.1
Authorization: Bearer <token>
Foundry-Features: Toolboxes=V1Preview
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}

POST {toolbox_endpoint}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
→ 返回 [{"name":"code_interpreter", "_meta": {...}, ...}]
```

每个 user 请求触发 code 调用时：

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
→ streaming response，content[] 里带结果
```

每个 user 请求触发 direct web search 时：

```text
POST {project_endpoint}/openai/v1/responses HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "model": "<deployment>",
  "tools": [{"type": "web_search"}],
  "input": "Search the web for: ..."
}
→ Responses API output_text，annotations[] 里带 citation
```

两条路径在 `scripts/smoke_test.py` 和 `scripts/http_smoke_test.py` 里都能看到。把它们和本文一起读，就有了 agent 实际运行的完整请求/响应循环。

## 10. MCP 不解决什么

- **它不是 model API**。Agent 仍然要调 model deployment 做推理。
- **它不是 workflow engine**。多步编排带 retry / compensation / durable state，归 Durable Functions / Step Functions / 你自己的状态机。
- **它本身不是 enforcement 边界**。Auth、rate limit、approval gating 必须在 MCP server 里实现（Toolbox 做了）或由 agent runtime 实现。

MCP 是 agent 和 tool catalog 之间的 *connector*。围绕它的 model / planner / governance / durability 是你自己拼装的栈。
