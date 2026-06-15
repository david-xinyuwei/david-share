"""
TRIPLE:
  Skill: agent-framework-azure-ai-py
  Prompt: "Using agent-framework-azure-ai-py skill, write a minimal Python hosted agent that
           uses Agent + MCPStreamableHTTPTool + FoundryChatClient + ResponsesHostServer.
           Include a custom @tool function and FoundryMemoryProvider."
  Deliverable: This file — runnable Python script (minimal agent matching our Foundry Demo)

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/agent-framework-azure-ai-py
"""
import asyncio
import os
from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient, FoundryMemoryProvider
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]


@tool(name="hello", description="A simple greeting tool for testing.")
async def hello_tool(name: str) -> str:
    return f"Hello, {name}! The agent framework is working."


async def main():
    client = FoundryChatClient(
        endpoint=project_endpoint,
        model="gpt-4.1-mini",
        credential=credential,
    )

    # Toolbox MCP (code_interpreter + file_search)
    toolbox = MCPStreamableHTTPTool(
        name="agent-tools",
        url=f"{project_endpoint.rstrip('/')}/toolboxes/agent-tools/mcp?api-version=v1",
        credential=credential,
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
    )

    # Memory (optional — graceful if not configured)
    context_providers = []
    memory_store = os.getenv("MEMORY_STORE_NAME", "").strip()
    if memory_store:
        context_providers.append(FoundryMemoryProvider(
            project_endpoint=project_endpoint, credential=credential,
            memory_store_name=memory_store, scope="default", allow_preview=True,
        ))

    agent = Agent(
        client=client,
        name="minimal-hosted-agent",
        instructions="You are a helpful assistant with code execution and document search capabilities.",
        tools=[toolbox, hello_tool],
        context_providers=context_providers or None,
        default_options={"store": False},
    )

    server = ResponsesHostServer(agent=agent, host="0.0.0.0", port=8088)
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
