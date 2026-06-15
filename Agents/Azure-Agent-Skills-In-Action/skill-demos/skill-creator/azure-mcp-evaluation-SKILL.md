---
name: azure-mcp-evaluation
description: >-
  Guide agents through evaluating Azure MCP Server tools against real Azure subscriptions.
  USE FOR: running Azure MCP evaluation harnesses, interpreting MCP tool results, classifying
  tool execution outcomes, building evaluation matrices, comparing MCP tools vs raw az CLI.
  DO NOT USE FOR: deploying Azure resources, modifying infrastructure, Foundry agent development,
  or non-Azure MCP servers.
compatibility: github-copilot, claude-code, opencode
---

# Azure MCP Evaluation Guide

## Overview

Evaluate Azure MCP Server tools by running them against a real Azure subscription and
classifying results into actionable categories. This skill enables agents to:

- **Discover** all top-level MCP tools via `tools/list`
- **Learn** composite tool schemas via `{"command": "learn"}`
- **Execute** safe read-only commands against live Azure data
- **Classify** results as EXECUTED / SCHEMA_VERIFIED / TOOL_ERROR / BLOCKED_UNSAFE / FAILED
- **Report** findings as JSON evidence, CSV matrix, and markdown summary

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Node.js | v20+ (for npx) |
| Azure CLI | Logged in (`az login`) with at least Reader on target subscription |
| MCP Server | `npx -y @azure/mcp@latest server start` |
| Protocol | JSON-RPC 2024-11-05 over stdio |

---

## Tool Classification Rules

| Status | Criteria | Action |
|--------|----------|--------|
| **EXECUTED** | HTTP 200 or non-JSON guidance returned | Record as live evidence |
| **SCHEMA_VERIFIED** | Valid schema but missing resource-specific inputs | Record schema; document missing inputs |
| **TOOL_ERROR** | Tool callable but returns 4xx/5xx | Record as product/prerequisite issue |
| **BLOCKED_UNSAFE** | Only destructive commands available | Record schema; do NOT execute |
| **FAILED** | No usable schema or runtime result | Document for manual follow-up |

---

## Calling Convention

### Simple tools (flat args)

```js
send("subscription_list", {})
send("group_list", { subscription: SUB })
```

### Composite tools (learn → execute)

```js
// Step 1: discover commands
send("compute", { command: "learn" })

// Step 2: execute with flat args (NOT JSON-string parameters)
send("compute", {
  command: "compute_vm_get",
  subscription: SUB,
  "resource-group": "mygroup"
})
```

**Important**: The `mcp_azure_mcp_*` prefix seen in SKILL.md files is added by the
agent host (VS Code, Copilot CLI). The raw MCP server uses plain names.

---

## Safety Rules

1. **Never execute commands matching**: create, delete, update, set, send, start, stop, restart, remove, migrate, purge
2. **Always prefer**: list, get, show, query, search, recommendation, limits, status, schema
3. **Block by default**: communication (SMS), azuremigrate (environment changes)
4. **Log everything**: even errors are evidence

---

## Output Format

### JSON (primary evidence)
```json
{
  "tool": "compute",
  "family": "Compute and containers",
  "mode": "learn-then-execute",
  "command": "compute_vm_get",
  "finalStatus": "EXECUTED",
  "runtimeStatus": "SUCCESS",
  "durationMs": 1575,
  "outputLength": 361,
  "evidence": "{...truncated...}"
}
```

### CSV (matrix)
```
tool,family,mode,command,finalStatus,runtimeStatus,durationMs,outputLength,missingRequired
```

### Markdown (human report)
```markdown
| Family | Tool | Mode | Command | Result | Evidence |
```

---

## Evaluation Workflow

1. `initialize` → handshake with MCP server
2. `tools/list` → discover all top-level tools
3. For each tool:
   - If in `directCalls` map → call directly
   - Else → `learn` → parse specs → choose safe command → build args → execute
4. Classify result
5. Write JSON + CSV + Markdown outputs

---

## Common Parameters

| Parameter | Default Value | Used By |
|-----------|---------------|---------|
| `subscription` | Current `az account show` subscription ID | Most tools |
| `resource-group` | First non-empty group | Compute, storage, etc. |
| `region` / `location` | `eastus` | Quota, pricing |
| `resource-type` | `Microsoft.CognitiveServices/accounts` | Terraform, quota |
| `service` | `Virtual Machines` | Pricing |

---

## Source

Methodology derived from hands-on evaluation of the Azure MCP Server
(`@azure/mcp@latest`) against a real Azure subscription with Owner permission.
Full results: [Azure-Agent-Skills-In-Action](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Agent-Skills-In-Action)
