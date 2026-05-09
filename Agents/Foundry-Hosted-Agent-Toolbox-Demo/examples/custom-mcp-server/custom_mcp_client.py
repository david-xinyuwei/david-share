"""Minimal MCP client that lists and calls the tools exposed by the local
custom MCP server. Use it to confirm the server is up before you register
it into a Foundry Toolbox.
"""
import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def run(endpoint: str) -> None:
    async with streamablehttp_client(endpoint) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            print(f"Tools found: {len(tools_result.tools)}")
            for tool in tools_result.tools:
                description = (tool.description or "").replace("\n", " ")[:100]
                print(f"  - {tool.name}: {description}")

            print("\n[invoke] device_health_check(cpu_pct=92, mem_pct=70, temp_c=88)")
            result = await session.call_tool(
                "device_health_check",
                arguments={"cpu_pct": 92.0, "mem_pct": 70.0, "temp_c": 88.0},
            )
            print(json.dumps([c.model_dump() for c in result.content], indent=2, ensure_ascii=False))

            print("\n[invoke] policy_evaluate(role=engineer, action=delete, sensitivity=internal)")
            result = await session.call_tool(
                "policy_evaluate",
                arguments={"role": "engineer", "action": "delete", "sensitivity": "internal"},
            )
            print(json.dumps([c.model_dump() for c in result.content], indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:9100/mcp")
    args = parser.parse_args()
    asyncio.run(run(args.endpoint))


if __name__ == "__main__":
    main()
