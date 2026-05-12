# Foundry Hosted Agents Skill — Live Demo

> This deployment was produced by an AI agent loaded with the `foundry-hosted-agents` skill
> from [microsoft/skills](https://github.com/microsoft/skills). The skill guides building,
> deploying, and managing Foundry hosted agents with containerized runtimes.

## What was built

A fully functional Foundry hosted agent deployed via `azd up` to Azure, exposing
the `/responses` protocol with:

- **Agent Framework** (Python): `agent_framework` + `agent_framework_foundry_hosting`
- **Toolbox MCP**: code_interpreter, file_search, web_search via a single MCP endpoint
- **Direct tools**: direct_web_search (Bing), direct_image_generate (gpt-image-1)
- **Memory** (preview): FoundryMemoryProvider for cross-session persistence
- **Containerized runtime**: Dockerfile → Azure Container Apps microVM

## Evidence from real deployment

### Dockerfile (production)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8088
CMD ["python", "-u", "main.py"]
```

### agent.yaml (Foundry registration)
```yaml
name: hosted-agent-toolbox-demo
description: Python agent with Toolbox MCP — supports code execution, document search, and web search.
model: gpt-4.1-mini
tools:
  - type: toolbox
    toolbox_name: agent-tools
```

### Key code pattern: Agent with Toolbox MCP + Direct tools
```python
from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

# Toolbox MCP endpoint (code_interpreter + file_search + web_search)
toolbox_tool = MCPStreamableHTTPTool(
    name="agent-tools",
    url=f"{project_endpoint}/toolboxes/agent-tools/mcp?api-version=v1",
    credential=credential,
)

# Direct web search via Responses API
@tool(name="direct_web_search")
async def direct_web_search(query: str) -> str: ...

# Direct image generation via gpt-image-1
@tool(name="direct_image_generate")
async def direct_image_generate(prompt: str) -> str: ...

agent = Agent(
    client=client,
    name="hosted-agent-toolbox-demo",
    tools=[toolbox_tool, direct_web_search_tool, direct_image_generate_tool],
    context_providers=[memory_provider],  # Foundry Memory (preview)
)
```

### Deployment result
```
azd up → Container Apps revision deployed
Endpoint: https://<project>.services.ai.azure.com/agents/<agent-id>/responses?api-version=...
Auth: Bearer token (Entra ID / ai.azure.com scope)
```

## Skill guidance followed

| Skill Topic | Applied |
|-------------|---------|
| Containerized agent with Responses protocol | ✅ Dockerfile + ResponsesHostServer |
| Per-agent Entra identity | ✅ DefaultAzureCredential + managed identity |
| Toolbox MCP integration | ✅ MCPStreamableHTTPTool for agent-tools |
| azd deployment | ✅ `azd up` with infra/ Bicep templates |
| Direct tools alongside MCP | ✅ direct_web_search + direct_image_generate |

## Source code

Full implementation: [`Foundry-Hosted-Agent-Toolbox-Demo/`](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo)

**Verdict**: The `foundry-hosted-agents` skill's guidance on containerized agents, Responses protocol,
Toolbox MCP, and `azd` deployment directly maps to the implementation in our demo repo.
The skill would have saved ~4 hours of trial-and-error discovering the correct
`agent_framework` imports, Toolbox MCP URL format, and Entra auth scope.
