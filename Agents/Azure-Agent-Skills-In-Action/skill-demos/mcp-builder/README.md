# MCP Builder Skill — Live Demo

> This MCP server was built by an AI agent loaded with the `mcp-builder` skill
> from [microsoft/skills](https://github.com/microsoft/skills).

## What was built

A Python (FastMCP) MCP server that exposes our 63-tool Azure MCP evaluation
results as 5 queryable tools, so any LLM can inspect the evaluation data
through the MCP protocol.

## Tools exposed

| Tool | Description | Annotation |
|------|-------------|------------|
| `eval_summary` | High-level counts (45/9/5/2/2) | readOnly |
| `eval_tool_result` | Detailed result for a specific tool | readOnly |
| `eval_list_tools` | List all 63 tools, filterable by status | readOnly |
| `eval_family_breakdown` | Results grouped by Azure service family | readOnly |
| `eval_blockers` | All non-EXECUTED tools with reasons | readOnly |

## Skill guidance followed

| Phase | What the skill says | What we did |
|-------|-------------------|-------------|
| Phase 1: Research | Understand the API, check if Microsoft already provides a server | Our API = evaluation JSON. No existing server for this data. |
| Phase 1: Framework | Python → FastMCP with `@mcp.tool` decorator | Used `mcp.server.fastmcp.FastMCP` |
| Phase 1: Transport | stdio for local, HTTP for remote | stdio (single-user evaluation tool) |
| Phase 2: Structure | Shared utilities, error handling, response formatting | `_load()` shared loader, JSON responses, actionable error messages |
| Phase 2: Tools | Pydantic-style args, annotations, concise descriptions | Type hints, `readOnlyHint=True`, parameter docstrings |
| Phase 2: Naming | Consistent prefix, action-oriented | `eval_*` prefix for all tools |
| Phase 3: Verify | `python -m py_compile` | ✅ Passed |

## How to run

```bash
# Install dependency
pip install mcp

# Copy evaluation data next to the server
cp evaluation/results/full_value_evaluation.json skill-demos/mcp-builder/evaluation_data.json

# Run with MCP Inspector
npx @modelcontextprotocol/inspector python skill-demos/mcp-builder/evaluation_mcp_server.py

# Or run directly (stdio)
python skill-demos/mcp-builder/evaluation_mcp_server.py
```

## Verdict

The `mcp-builder` skill provides a structured 4-phase workflow that turns
"I want to build an MCP server" into a repeatable engineering process.
The skill's emphasis on tool annotations (`readOnlyHint`), naming conventions,
and actionable error messages directly influenced the server design.
