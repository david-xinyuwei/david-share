# Foundry Toolboxes Skill — Live Demo

> This Toolbox configuration was guided by the `foundry-toolboxes` skill from
> [microsoft/skills](https://github.com/microsoft/skills).

## What was done

Configured a Foundry Toolbox named `agent-tools` that bundles 3 MCP-compatible tools
into a single endpoint, consumed by our hosted agent via `MCPStreamableHTTPTool`.

## Evidence from real deployment

### Toolbox configuration (via azd infra)

The Toolbox was provisioned as part of the Foundry project infrastructure:

```
Toolbox name: agent-tools
Endpoint: {project_endpoint}/toolboxes/agent-tools/mcp?api-version=v1
Protocol: MCP (JSON-RPC over Streamable HTTP)
Auth: Bearer token (Entra ID, scope: ai.azure.com)
```

### Tools bundled in the Toolbox

| Tool | Type | Description |
|------|------|-------------|
| `code_interpreter` | Built-in | Execute Python in a managed sandbox |
| `file_search` | Built-in | Search uploaded documents via vector store |
| `web_search` | Built-in | Web search via Bing grounding (preview) |

### Live verification (from our demo app server.py)

```python
# Toolbox MCP endpoint queried via JSON-RPC tools/list
resp = httpx.post(
    f"{project_endpoint}/toolboxes/agent-tools/mcp?api-version=v1",
    headers={
        "Authorization": f"Bearer {token}",
        "Foundry-Features": "Toolboxes=V1Preview",
    },
    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
)
# Returns: 3 tools (code_interpreter, file_search, web_search)
```

### Agent consumption pattern

```python
from agent_framework import MCPStreamableHTTPTool

toolbox_tool = MCPStreamableHTTPTool(
    name="agent-tools",
    url=toolbox_mcp_endpoint(project_endpoint, "agent-tools"),
    credential=credential,
    headers={"Foundry-Features": "Toolboxes=V1Preview"},
)
# This single tool object exposes all 3 Toolbox tools to the agent
```

## Skill guidance followed

| Skill Topic | Our Implementation |
|-------------|-------------------|
| Intent-based Toolbox curation | ✅ Grouped code_interpreter + file_search + web_search for a general-purpose agent |
| Single MCP endpoint for multiple tools | ✅ One URL serves all 3 tools |
| Toolbox consumed by any agent | ✅ Both local (main.py) and cloud (Foundry hosted) agents use same Toolbox |
| Auth via Entra ID | ✅ Bearer token with ai.azure.com scope |
| V1Preview feature flag | ✅ `Foundry-Features: Toolboxes=V1Preview` header |

**Verdict**: The `foundry-toolboxes` skill's core value proposition — "curate intent-based
Toolboxes as a single MCP endpoint" — is exactly what we implemented. Without the skill,
an engineer would need to discover the Toolbox MCP URL format, the V1Preview header,
and the MCPStreamableHTTPTool consumption pattern through trial-and-error.
