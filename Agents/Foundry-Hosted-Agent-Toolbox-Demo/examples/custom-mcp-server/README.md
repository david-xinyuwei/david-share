# Custom MCP Server Example

A minimal, dependency-free Model Context Protocol server that exposes two custom tools you can register into a Foundry Toolbox. Use this to learn the wire shape before plugging in your real backend.

## What you get

| Tool | What it does |
| --- | --- |
| `device_health_check(cpu_pct, mem_pct, temp_c)` | Classifies a device snapshot into `ok | warn | critical` and returns advice. |
| `policy_evaluate(role, action, sensitivity)` | A tiny rule engine that returns `allow | deny | needs_approval` with a reason. |

Both tools are fully deterministic so the demo is reproducible.

## Run the server

```bash
python custom_mcp_server.py
# Serves on http://0.0.0.0:9100/mcp (Streamable HTTP, anonymous)
```

## Verify with the bundled client

```bash
python custom_mcp_client.py
```

Expected output:

```
Tools found: 2
  - device_health_check: Classify a device's vital metrics into ok | warn | critical. ...
  - policy_evaluate: Decide whether a role may perform an action on a resource of a given ...

[invoke] device_health_check(cpu_pct=92, mem_pct=70, temp_c=88)
[ {"type":"text","text":"{\"status\":\"critical\", ...}"} ]

[invoke] policy_evaluate(role=engineer, action=delete, sensitivity=internal)
[ {"type":"text","text":"{\"decision\":\"needs_approval\", ...}"} ]
```

## Register it into a Foundry Toolbox

After the server is reachable from Foundry (in production you would expose it through a stable URL; for this demo any URL the project can reach over the network), register it as an MCP tool inside the toolbox:

```python
from azure.ai.projects.models import MCPTool

# Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#model-context-protocol-mcp
project.beta.toolboxes.create_toolbox_version(
    toolbox_name="agent-tools",
    description="Includes a custom MCP server.",
    tools=[
        MCPTool(
            server_label="customdevice",
            server_url="https://<your-public-url>/mcp",
            require_approval="never",
            project_connection_id="<your-key-auth-connection-id>",
        ),
    ],
)
```

After this version becomes the toolbox `default_version`, calling `verify_toolbox.py` against the consumer endpoint will list the new tools as `customdevice.device_health_check` and `customdevice.policy_evaluate`. The hosted agent in `main.py` will then be able to call them through the Toolbox MCP path with no code change in the agent itself.

## Production checklist

| Item | Reminder |
| --- | --- |
| Auth | Replace anonymous Streamable HTTP with bearer/managed-identity behind your own gateway. |
| Approval | If a tool can modify state, set `require_approval="always"` so the agent honors it. |
| Idempotency | MCP tool calls may be retried; design tool logic to be idempotent. |
| Rate limit | Foundry Toolbox does not rate-limit your custom server; add it at the server. |
| Observability | Wrap each tool with structured logging so you can correlate to the Foundry trace. |
| Public endpoint | Use a private endpoint or an inbound VNet for sensitive backends; see `docs/production-scale.md` for the network-isolation matrix. |

## What this example is not

- Not a production server. No auth, no rate limiting, no metrics.
- Not a stand-in for OpenAPI tools. If your backend already speaks OpenAPI, register it as `OpenAPITool` instead — it sits inside the toolbox just like MCP.
- Not the only way to add capability. For pure single-call helpers, the direct in-agent `@tool` pattern in `main.py` (see `direct_image_generate`) may be simpler.
