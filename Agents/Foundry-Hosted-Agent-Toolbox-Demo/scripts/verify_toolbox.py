import argparse
import asyncio
import os

from azure.identity import AzureCliCredential, DefaultAzureCredential
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


load_dotenv()


def build_credential() -> AzureCliCredential | DefaultAzureCredential:
    if os.getenv("AZURE_AUTH_MODE", "").lower() == "cli":
        return AzureCliCredential()
    return DefaultAzureCredential()


async def verify_toolbox(endpoint: str) -> None:
    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#step-3-verify-tool-availability
    token = build_credential().get_token("https://ai.azure.com/.default").token
    headers = {
        "Authorization": f"Bearer {token}",
        "Foundry-Features": "Toolboxes=V1Preview",
    }

    async with streamablehttp_client(endpoint, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"Tools found: {len(tools)}")
            for tool in tools:
                description = (tool.description or "").replace("\n", " ")[:100]
                print(f"- {tool.name}: {description}")


def main() -> None:
    parser = argparse.ArgumentParser(description="List tools exposed by a Foundry Toolbox MCP endpoint.")
    parser.add_argument("--endpoint", default=os.getenv("TOOLBOX_MCP_ENDPOINT"))
    args = parser.parse_args()

    if not args.endpoint:
        raise RuntimeError("Provide --endpoint or set TOOLBOX_MCP_ENDPOINT in .env")

    asyncio.run(verify_toolbox(args.endpoint))


if __name__ == "__main__":
    main()
