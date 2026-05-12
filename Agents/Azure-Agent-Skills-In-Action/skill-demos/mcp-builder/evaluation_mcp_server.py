"""MCP Server built following the mcp-builder skill from microsoft/skills.

This server exposes the Azure Agent Skills evaluation results as MCP tools,
letting any LLM query our 63-tool run data via the MCP protocol.

Skill guidance applied:
- Phase 1: API = our evaluation JSON data
- Phase 2: FastMCP (@mcp.tool decorator), Pydantic schemas, actionable errors
- Phase 3: python -m py_compile verification
- Tool annotations: readOnlyHint=true for all tools
- Naming: consistent prefix (eval_*)
- Concise descriptions + parameter descriptions

Source: https://github.com/microsoft/skills → .github/skills/mcp-builder/SKILL.md
"""

from mcp.server.fastmcp import FastMCP
import json
from pathlib import Path
from typing import Optional

# Initialize server
mcp = FastMCP(
    "azure-skills-evaluation",
    version="1.0.0",
)

# Load evaluation data
DATA_PATH = Path(__file__).parent / "evaluation_data.json"
_data = None


def _load():
    global _data
    if _data is None:
        if DATA_PATH.exists():
            _data = json.loads(DATA_PATH.read_text())
        else:
            # Fallback: embedded summary
            _data = {
                "summary": {"EXECUTED": 45, "SCHEMA_VERIFIED": 9, "TOOL_ERROR": 5, "BLOCKED_UNSAFE": 2, "FAILED": 2},
                "records": [],
            }
    return _data


@mcp.tool(
    annotations={"readOnlyHint": True},
)
def eval_summary() -> str:
    """Get the high-level summary of the 63-tool Azure MCP evaluation run.

    Returns counts by status: EXECUTED, SCHEMA_VERIFIED, TOOL_ERROR, BLOCKED_UNSAFE, FAILED.
    """
    data = _load()
    return json.dumps(data["summary"], indent=2)


@mcp.tool(
    annotations={"readOnlyHint": True},
)
def eval_tool_result(tool_name: str) -> str:
    """Get the detailed evaluation result for a specific Azure MCP tool.

    Args:
        tool_name: The tool name to look up (e.g., 'compute', 'quota', 'foundry').
    """
    data = _load()
    for rec in data.get("records", []):
        if rec["tool"] == tool_name:
            return json.dumps(rec, indent=2)
    return json.dumps({"error": f"Tool '{tool_name}' not found. Use eval_list_tools to see available names."})


@mcp.tool(
    annotations={"readOnlyHint": True},
)
def eval_list_tools(status_filter: Optional[str] = None) -> str:
    """List all 63 evaluated tools, optionally filtered by status.

    Args:
        status_filter: Optional filter — one of EXECUTED, SCHEMA_VERIFIED, TOOL_ERROR, BLOCKED_UNSAFE, FAILED.
    """
    data = _load()
    records = data.get("records", [])
    if status_filter:
        records = [r for r in records if r.get("finalStatus") == status_filter]
    result = [{"tool": r["tool"], "status": r.get("finalStatus", "?"), "family": r.get("family", "?")} for r in records]
    return json.dumps(result, indent=2)


@mcp.tool(
    annotations={"readOnlyHint": True},
)
def eval_family_breakdown() -> str:
    """Get evaluation results grouped by Azure service family.

    Returns a breakdown showing how many tools EXECUTED vs other statuses per family.
    """
    data = _load()
    families = {}
    for rec in data.get("records", []):
        fam = rec.get("family", "Other")
        status = rec.get("finalStatus", "UNKNOWN")
        if fam not in families:
            families[fam] = {}
        families[fam][status] = families[fam].get(status, 0) + 1
    return json.dumps(families, indent=2)


@mcp.tool(
    annotations={"readOnlyHint": True},
)
def eval_blockers() -> str:
    """List all tools that did NOT fully execute, with the reason for each.

    Covers SCHEMA_VERIFIED (missing inputs), TOOL_ERROR, BLOCKED_UNSAFE, and FAILED.
    """
    data = _load()
    blockers = []
    for rec in data.get("records", []):
        if rec.get("finalStatus") not in ("EXECUTED",):
            blockers.append({
                "tool": rec["tool"],
                "status": rec.get("finalStatus"),
                "reason": rec.get("evidence", "")[:200],
                "missing": rec.get("missingRequired", []),
            })
    return json.dumps(blockers, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
