"""Minimal custom MCP server example.

Exposes two deterministic tools so customers can see exactly how a custom MCP
server is wired without any external dependencies:

  - ``device_health_check``: classifies a device's vital metrics (cpu / mem /
    temp) into ``ok | warn | critical`` based on fixed thresholds.
  - ``policy_evaluate``: a tiny rule engine that decides whether an action is
    allowed for a given user role and resource sensitivity.

This is exactly the shape Foundry Toolbox would proxy if you registered this
server as an MCP tool through ``MCPTool(server_label=..., server_url=..., project_connection_id=...)``.

Run it locally:

    python custom_mcp_server.py        # serves on http://0.0.0.0:9100/mcp

Then list its tools with the bundled client:

    python custom_mcp_client.py
"""
from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP


server = FastMCP("custom-device-policy", host="0.0.0.0", port=9100)


@server.tool(
    name="device_health_check",
    description=(
        "Classify a device's vital metrics into ok | warn | critical. "
        "Inputs are floats. Thresholds are fixed in code so the demo is reproducible."
    ),
)
def device_health_check(cpu_pct: float, mem_pct: float, temp_c: float) -> dict[str, str | float | list[str]]:
    """Return a deterministic health classification for a device snapshot."""
    issues: list[str] = []
    status = "ok"
    if cpu_pct > 90 or mem_pct > 95 or temp_c > 85:
        status = "critical"
    elif cpu_pct > 75 or mem_pct > 85 or temp_c > 75:
        status = "warn"

    if cpu_pct > 75:
        issues.append(f"high cpu {cpu_pct:.1f}%")
    if mem_pct > 85:
        issues.append(f"high mem {mem_pct:.1f}%")
    if temp_c > 75:
        issues.append(f"high temp {temp_c:.1f}C")

    return {
        "status": status,
        "cpu_pct": cpu_pct,
        "mem_pct": mem_pct,
        "temp_c": temp_c,
        "issues": issues,
        "advice": (
            "no action"
            if status == "ok"
            else "investigate" if status == "warn" else "page on-call"
        ),
    }


@server.tool(
    name="policy_evaluate",
    description=(
        "Decide whether a role may perform an action on a resource of a given "
        "sensitivity level. Returns allow | deny | needs_approval with a reason."
    ),
)
def policy_evaluate(role: str, action: str, sensitivity: str) -> dict[str, str]:
    """A tiny rule engine to demonstrate governance enforcement at the tool layer."""
    role_l = role.strip().lower()
    action_l = action.strip().lower()
    sensitivity_l = sensitivity.strip().lower()

    if role_l == "admin":
        return {"decision": "allow", "reason": "admin role"}
    if action_l == "read" and sensitivity_l in {"public", "internal"}:
        return {"decision": "allow", "reason": "read on non-restricted resource"}
    if action_l == "write" and sensitivity_l == "public":
        return {"decision": "allow", "reason": "write on public resource"}
    if action_l in {"write", "delete"} and sensitivity_l == "internal":
        return {"decision": "needs_approval", "reason": "write/delete on internal needs approval"}
    if sensitivity_l == "restricted":
        return {"decision": "deny", "reason": "restricted resource requires admin role"}
    return {"decision": "deny", "reason": f"no rule matched for role={role_l!r}, action={action_l!r}, sensitivity={sensitivity_l!r}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the custom MCP demo server.")
    parser.add_argument("--transport", default="streamable-http", choices=["streamable-http", "stdio"])
    args = parser.parse_args()
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http")


if __name__ == "__main__":
    main()
