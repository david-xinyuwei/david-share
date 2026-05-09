import asyncio
import os
import sys
from pathlib import Path

import httpx
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential, DefaultAzureCredential
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import build_credential, build_direct_web_search_tool, require_env, toolbox_mcp_endpoint


load_dotenv()


async def run() -> None:
    credential: AzureCliCredential | DefaultAzureCredential = build_credential()
    project_endpoint = require_env("FOUNDRY_PROJECT_ENDPOINT")
    model = require_env("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    toolbox_name = require_env("TOOLBOX_NAME")
    token = credential.get_token("https://ai.azure.com/.default").token

    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=model,
        credential=credential,
        allow_preview=True,
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Foundry-Features": "Toolboxes=V1Preview",
    }
    async with httpx.AsyncClient(headers=headers, timeout=180.0) as http_client:
        toolbox = MCPStreamableHTTPTool(
            name="toolbox",
            url=toolbox_mcp_endpoint(project_endpoint, toolbox_name),
            description=os.getenv("TOOLBOX_DESCRIPTION", "Foundry Toolbox MCP endpoint"),
            load_prompts=False,
            request_timeout=180,
            http_client=http_client,
        )
        async with toolbox:
            agent = Agent(
                client=client,
                name="hosted-agent-toolbox-smoke-test",
                instructions=(
                    "Use toolbox code_interpreter for arithmetic. Use direct_web_search for current "
                    "public web facts. Answer concisely."
                ),
                tools=[toolbox, build_direct_web_search_tool(credential, project_endpoint, model)],
                default_options={"store": False},
            )

            web_result = await agent.run(
                "Use direct_web_search to search for Microsoft Learn Azure AI Foundry Toolbox "
                "and summarize what it is in one sentence."
            )
            print("WEB_RESULT_START")
            print(web_result.text)
            print("WEB_RESULT_END")

            code_result = await agent.run("Use code_interpreter to calculate sum(i*i for i in range(1, 6)).")
            print("CODE_RESULT_START")
            print(code_result.text)
            print("CODE_RESULT_END")


if __name__ == "__main__":
    asyncio.run(run())
