from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("device-ops")


@mcp.tool()
def device_health_check(cpu_pct: float, mem_pct: float, temp_c: float) -> dict:
    if cpu_pct >= 90 or temp_c >= 85:
        return {"status": "critical", "advice": "page on-call"}
    if cpu_pct >= 75 or mem_pct >= 85 or temp_c >= 75:
        return {"status": "warning", "advice": "reduce workload"}
    return {"status": "healthy", "advice": "continue monitoring"}


@mcp.tool()
def policy_evaluate(role: str, action: str, sensitivity: str) -> dict:
    if action in {"delete", "export"} and sensitivity in {"internal", "restricted"}:
        return {"decision": "needs_approval", "reason": "write/delete on sensitive data needs approval"}
    if role not in {"operator", "engineer", "admin"}:
        return {"decision": "deny", "reason": "unknown role"}
    return {"decision": "allow", "reason": "policy passed"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
