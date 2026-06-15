# 自定义 MCP Server 示例

这个示例展示如何先在本地原型化一个确定性 MCP server，再把它注册进 Foundry Toolbox。

## Tools

| Tool | 作用 |
| --- | --- |
| `device_health_check` | 根据 CPU、内存和温度指标判断设备健康状态。 |
| `policy_evaluate` | 根据简单策略返回 allow / deny / needs_approval。 |

## 运行

```bash
python custom_mcp_client.py
```

## 运行日志示例

```text
Tools found: 2
  - device_health_check
  - policy_evaluate

[invoke] device_health_check(cpu_pct=92, mem_pct=70, temp_c=88)
{"status": "critical", "advice": "page on-call"}

[invoke] policy_evaluate(role=engineer, action=delete, sensitivity=internal)
{"decision": "needs_approval", "reason": "write/delete on sensitive data needs approval"}
```
