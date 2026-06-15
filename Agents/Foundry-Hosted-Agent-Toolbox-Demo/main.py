import asyncio
import os
from typing import Annotated, Any

import httpx
from agent_framework import Agent, InMemoryHistoryProvider, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import AzureCliCredential, DefaultAzureCredential
from dotenv import load_dotenv


load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def require_project_endpoint() -> str:
    value = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    if not value:
        raise RuntimeError("Missing required environment variable: AZURE_AI_PROJECT_ENDPOINT")
    return value


def build_credential() -> AzureCliCredential | DefaultAzureCredential:
    if os.getenv("AZURE_AUTH_MODE", "").lower() == "cli":
        return AzureCliCredential()
    return DefaultAzureCredential()


def env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer, got {value!r}") from exc


def toolbox_mcp_endpoint(project_endpoint: str, toolbox_name: str) -> str:
    configured_endpoint = os.getenv("TOOLBOX_MCP_ENDPOINT")
    if configured_endpoint:
        return configured_endpoint
    return f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}/mcp?api-version=v1"


def extract_output_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks) or str(response)


def build_direct_web_search_tool(
    credential: AzureCliCredential | DefaultAzureCredential,
    project_endpoint: str,
    model: str,
) -> object:
    @tool(
        name="direct_web_search",
        description=(
            "Search the public web through the Foundry Responses API when current "
            "facts or citations are needed. Use this when the Toolbox web_search "
            "tool is unavailable."
        ),
    )
    async def direct_web_search(
        search_query: Annotated[str, "The web search query to execute."],
    ) -> str:
        token = credential.get_token("https://ai.azure.com/.default").token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Source: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/web-search
        # The Responses API enables web grounding through tools=[{"type": "web_search"}].
        body = {
            "model": model,
            "tools": [{"type": "web_search"}],
            "input": f"Search the web for: {search_query}\nReturn a concise answer with citations.",
        }
        async with httpx.AsyncClient(timeout=180.0) as http_client:
            response = await http_client.post(
                f"{project_endpoint.rstrip('/')}/openai/v1/responses",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
        return extract_output_text(response.json())

    return direct_web_search


def build_direct_image_generate_tool(
    credential: AzureCliCredential | DefaultAzureCredential,
    project_endpoint: str,
    image_deployment: str,
) -> object:
    # Source: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e
    # gpt-image-1 generations endpoint sits at the account-level /openai/v1 path,
    # NOT under /api/projects/<project>. Strip the project segment from the
    # configured project endpoint to derive the account base URL.
    if "/api/projects/" in project_endpoint:
        account_base = project_endpoint.split("/api/projects/", 1)[0]
    else:
        account_base = project_endpoint.rstrip("/")
    image_url = f"{account_base.rstrip('/')}/openai/v1/images/generations"

    @tool(
        name="direct_image_generate",
        description=(
            "Generate an image from a text prompt through the Foundry image API "
            "(gpt-image-1 deployment). Returns a short summary plus the base64 "
            "image length so the agent can confirm the image was produced."
        ),
    )
    async def direct_image_generate(
        prompt: Annotated[str, "The image description prompt."],
        size: Annotated[str, "Image size, e.g. '1024x1024' or '1024x1536'."] = "1024x1024",
    ) -> str:
        token = credential.get_token("https://ai.azure.com/.default").token
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {
            "model": image_deployment,
            "prompt": prompt,
            "n": 1,
            "size": size,
        }
        async with httpx.AsyncClient(timeout=180.0) as http_client:
            response = await http_client.post(image_url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        items = payload.get("data", [])
        if not items:
            return "Image generation returned no data."
        first = items[0]
        b64 = first.get("b64_json") or ""
        url = first.get("url") or ""
        revised = first.get("revised_prompt") or prompt
        return (
            f"Generated 1 image (size={size}). "
            f"Revised prompt: {revised[:200]}. "
            f"b64_json length: {len(b64)} chars. URL: {url or '(inline base64)'}."
        )

    return direct_image_generate


async def main() -> None:
    credential = build_credential()
    project_endpoint = require_project_endpoint()
    model = require_env("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    toolbox_name = require_env("TOOLBOX_NAME")
    toolbox_token = credential.get_token("https://ai.azure.com/.default").token

    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox
    # Microsoft Agent Framework connects to Toolbox through MCPStreamableHTTPTool.
    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=model,
        credential=credential,
        allow_preview=True,
    )

    toolbox_endpoint = toolbox_mcp_endpoint(project_endpoint, toolbox_name)
    toolbox_headers = {
        "Authorization": f"Bearer {toolbox_token}",
        "Foundry-Features": "Toolboxes=V1Preview",
    }

    base_tools: list[object] = []
    if os.getenv("ENABLE_DIRECT_WEB_SEARCH", "true").lower() not in {"0", "false", "no"}:
        base_tools.append(build_direct_web_search_tool(credential, project_endpoint, model))
    image_deployment = os.getenv("AZURE_AI_IMAGE_DEPLOYMENT_NAME", "").strip()
    if image_deployment and os.getenv("ENABLE_DIRECT_IMAGE_GENERATE", "false").lower() in {"1", "true", "yes"}:
        base_tools.append(build_direct_image_generate_tool(credential, project_endpoint, image_deployment))

    # --- Foundry Memory (preview) ---
    # Source: Foundry Blog 2026-04-22: "Memory (preview) — managed long-term memory
    # built directly into Foundry Agent Service."
    # FoundryMemoryProvider gives the agent cross-session memory:
    #   - Agent remembers user preferences, past conversations, key facts
    #   - No external database needed — managed by Foundry
    #   - Scoped per user (isolation_key) for multi-tenant safety
    context_providers = []
    memory_store_name = os.getenv("MEMORY_STORE_NAME", "").strip()
    if memory_store_name:
        try:
            from agent_framework.foundry import FoundryMemoryProvider
            # Memory Store may be in a different project than the hosted agent
            memory_endpoint = os.getenv("MEMORY_PROJECT_ENDPOINT", "").strip() or project_endpoint
            memory_provider = FoundryMemoryProvider(
                project_endpoint=memory_endpoint,
                credential=credential,
                memory_store_name=memory_store_name,
                scope="default",  # In production: use user ID for per-user isolation
                allow_preview=True,
                # Source: https://raw.githubusercontent.com/microsoft/agent-framework/main/python/packages/foundry/agent_framework_foundry/_memory_provider.py
                # The SDK default update_delay is 300 seconds; this demo uses 0 so the proof flow can recall immediately.
                update_delay=max(0, env_int("MEMORY_UPDATE_DELAY_SECONDS", 0)),
            )
            context_providers.append(memory_provider)
            context_providers.append(InMemoryHistoryProvider(load_messages=False))
            print(
                "[Memory] Foundry Memory enabled: "
                f"store={memory_store_name}, update_delay={max(0, env_int('MEMORY_UPDATE_DELAY_SECONDS', 0))}s"
            )
        except Exception as e:
            print(f"[Memory] WARNING: Failed to initialize Foundry Memory: {e}")
            print("[Memory] Agent will run without memory (stateless mode).")

    async def run_server(agent_tools: list[object]) -> None:
        async with Agent(
            client=client,
            name=os.getenv("AGENT_NAME", "hosted-agent-toolbox-demo"),
            instructions=(
                "You are a concise enterprise assistant. Use Toolbox tools for governed shared "
                "capabilities such as code_interpreter. For current public web facts, use "
                "direct_web_search and preserve citations or source URLs when returned. "
                "For image generation, use direct_image_generate when available."
                + ("\n\nYou have long-term memory enabled. Remember important user preferences, "
                   "past conclusions, and key facts across conversations." if memory_store_name else "")
            ),
            tools=agent_tools,
            context_providers=context_providers if context_providers else None,
            # Source: https://raw.githubusercontent.com/microsoft/agent-framework/main/python/samples/02-agents/context_providers/azure_ai_foundry_memory.py
            # The Memory sample uses store=False and InMemoryHistoryProvider(load_messages=False) so recall proves Foundry Memory, not chat history.
            default_options={"store": False},
        ) as agent:
            server = ResponsesHostServer(agent)
            await server.run_async(host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8088")))

    async with httpx.AsyncClient(headers=toolbox_headers, timeout=180.0) as toolbox_http_client:
        toolbox = MCPStreamableHTTPTool(
            name="toolbox",
            url=toolbox_endpoint,
            description=os.getenv("TOOLBOX_DESCRIPTION", "Foundry Toolbox MCP endpoint"),
            load_prompts=False,
            request_timeout=180,
            http_client=toolbox_http_client,
        )
        try:
            await toolbox.__aenter__()
        except Exception as e:
            print(f"[Toolbox] WARNING: Failed to initialize Toolbox MCP at {toolbox_endpoint}: {e}")
            print("[Toolbox] Agent will start without Toolbox MCP tools.")
            await run_server(base_tools)
        else:
            try:
                await run_server([toolbox, *base_tools])
            finally:
                await toolbox.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())
