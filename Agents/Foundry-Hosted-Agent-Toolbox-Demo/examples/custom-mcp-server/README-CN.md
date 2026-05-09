# 自定义 MCP Server 示例

最小可跑的 Model Context Protocol server，无外部依赖，暴露两个 deterministic tool。学清楚 wire 形态后再插真后端。

## 你得到什么

| Tool | 做什么 |
| --- | --- |
| `device_health_check(cpu_pct, mem_pct, temp_c)` | 把设备快照分类 `ok | warn | critical`，返回建议。 |
| `policy_evaluate(role, action, sensitivity)` | 一个微型规则引擎，返回 `allow | deny | needs_approval` + 原因。 |

两个 tool 完全 deterministic，demo 可复现。

## 跑 server

```bash
python custom_mcp_server.py
# Streamable HTTP 监听 http://0.0.0.0:9100/mcp，匿名
```

## 用客户端验证

```bash
python custom_mcp_client.py
```

预期输出：

```
Tools found: 2
  - device_health_check: Classify a device's vital metrics into ok | warn | critical. ...
  - policy_evaluate: Decide whether a role may perform an action on a resource of a given ...

[invoke] device_health_check(cpu_pct=92, mem_pct=70, temp_c=88)
[ {"type":"text","text":"{\"status\":\"critical\", ...}"} ]

[invoke] policy_evaluate(role=engineer, action=delete, sensitivity=internal)
[ {"type":"text","text":"{\"decision\":\"needs_approval\", ...}"} ]
```

## 注册到 Foundry Toolbox

Server 对 Foundry 可达后（生产应用稳定 URL；本 demo 只要 project 网络能到都行），把它注册成 MCP tool：

```python
from azure.ai.projects.models import MCPTool

# 来源：https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#model-context-protocol-mcp
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

这个 version 成为 toolbox `default_version` 后，`verify_toolbox.py` 命中 consumer endpoint 会列出新 tool 名为 `customdevice.device_health_check` 和 `customdevice.policy_evaluate`。`main.py` 中的 hosted agent 立刻可以通过 Toolbox MCP 路径调用，**agent 代码不需要改**。

## 生产 checklist

| 项 | 提醒 |
| --- | --- |
| Auth | 把匿名 Streamable HTTP 替换成 bearer / managed-identity，前面挂自己的 gateway。 |
| Approval | Tool 改状态时设 `require_approval="always"`，让 agent 强制弹审批。 |
| 幂等 | MCP tool 调用可能重试；设计 tool 逻辑幂等。 |
| 限流 | Foundry Toolbox 不限流你的 custom server；server 端自己加。 |
| 可观测 | 每个 tool 包结构化日志，方便和 Foundry trace 关联。 |
| 公开端点 | 敏感后端用 private endpoint 或 inbound VNet；见 `docs/production-scale-CN.md` 网络隔离矩阵。 |

## 这个示例不是什么

- 不是生产 server。无 auth / 限流 / 监控。
- 不替代 OpenAPI tool。后端已说 OpenAPI，注册成 `OpenAPITool`，它和 MCP 一样住在 toolbox 里。
- 不是唯一加能力的方式。纯单次调用 helper，`main.py` 里 in-agent `@tool` 模式（见 `direct_image_generate`）可能更简单。
