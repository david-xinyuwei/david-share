# Custom MCP Server Example

This example shows how to prototype a deterministic MCP server before registering it in a Foundry Toolbox.

## Tools

| Tool | Purpose |
| --- | --- |
| `device_health_check` | Classifies device health from CPU, memory, and temperature metrics. |
| `policy_evaluate` | Returns allow / deny / needs_approval for a simple action policy. |

## Run

```bash
python custom_mcp_client.py
```

## Example Output

```text
Tools found: 2
  - device_health_check
  - policy_evaluate

[invoke] device_health_check(cpu_pct=92, mem_pct=70, temp_c=88)
{"status": "critical", "advice": "page on-call"}

[invoke] policy_evaluate(role=engineer, action=delete, sensitivity=internal)
{"decision": "needs_approval", "reason": "write/delete on sensitive data needs approval"}
```
