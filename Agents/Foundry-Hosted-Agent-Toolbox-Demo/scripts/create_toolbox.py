import argparse
import os

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AzureAISearchTool, CodeInterpreterTool, FileSearchTool, MCPTool, WebSearchTool
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
        raise RuntimeError("Missing required environment variable: AZURE_AI_PROJECT_ENDPOINT or FOUNDRY_PROJECT_ENDPOINT")
    return value


def build_credential() -> AzureCliCredential | DefaultAzureCredential:
    if os.getenv("AZURE_AUTH_MODE", "").lower() == "cli":
        return AzureCliCredential()
    return DefaultAzureCredential()


def build_tools(args: argparse.Namespace) -> list[object]:
    tools: list[object] = []

    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#web-search
    if args.with_web_search:
        tools.append(
            WebSearchTool(
                name="web_search",
                description="Search the public web for current factual information with citations.",
                search_context_size="medium",
            )
        )

    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#code-interpreter
    if args.with_code_interpreter:
        tools.append(
            CodeInterpreterTool(
                name="code_interpreter",
                description="Execute Python code for calculations and data analysis.",
            )
        )

    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#file-search
    if getattr(args, 'with_file_search', False):
        vector_store_ids = os.getenv("FILE_SEARCH_VECTOR_STORE_IDS", "").split(",")
        vector_store_ids = [v.strip() for v in vector_store_ids if v.strip()]
        tools.append(
            FileSearchTool(
                name="file_search",
                description="Search uploaded files in a vector store for relevant passages.",
                vector_store_ids=vector_store_ids if vector_store_ids else [],
            )
        )

    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#azure-ai-search
    search_connection_id = os.getenv("AZURE_AI_SEARCH_CONNECTION_ID")
    search_index = os.getenv("AZURE_AI_SEARCH_INDEX")
    if search_connection_id and search_index:
        tools.append(
            AzureAISearchTool(
                index_name=search_index,
                project_connection_id=search_connection_id,
            )
        )

    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#model-context-protocol-mcp
    mcp_server_url = os.getenv("MCP_SERVER_URL")
    mcp_connection_id = os.getenv("MCP_PROJECT_CONNECTION_ID")
    if mcp_server_url and mcp_connection_id:
        tools.append(
            MCPTool(
                server_label=os.getenv("MCP_SERVER_LABEL", "custom_mcp"),
                server_url=mcp_server_url,
                require_approval=args.mcp_require_approval,
                project_connection_id=mcp_connection_id,
            )
        )

    if not tools:
        raise RuntimeError("No tools selected. Use --with-web-search or configure optional tool env vars.")

    return tools


def endpoint_for(project_endpoint: str, toolbox_name: str, version: str | None = None) -> str:
    base = project_endpoint.rstrip("/")
    if version:
        return f"{base}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1"
    return f"{base}/toolboxes/{toolbox_name}/mcp?api-version=v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Foundry Toolbox version for the Hosted Agent demo.")
    parser.add_argument("--toolbox-name", default=os.getenv("TOOLBOX_NAME", "agent-tools"))
    parser.add_argument("--description", default=os.getenv("TOOLBOX_DESCRIPTION", "Hosted Agent shared tools"))
    parser.add_argument("--with-web-search", action="store_true")
    parser.add_argument("--with-code-interpreter", action="store_true")
    parser.add_argument("--with-file-search", action="store_true")
    parser.add_argument("--set-default", action="store_true", help="Point the toolbox consumer endpoint at the new version.")
    parser.add_argument("--mcp-require-approval", choices=["always", "never"], default="never")
    args = parser.parse_args()

    project_endpoint = require_project_endpoint()
    project = AIProjectClient(endpoint=project_endpoint, credential=build_credential())

    # Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#step-1-create-a-toolbox-version
    # Note: azure-ai-projects 2.1.0 uses create_version(name=...) instead of
    # create_toolbox_version(toolbox_name=...) shown in the Learn docs.
    toolbox_version = project.beta.toolboxes.create_version(
        name=args.toolbox_name,
        description=args.description,
        tools=build_tools(args),
    )

    version = getattr(toolbox_version, "version", None)
    print(f"Created toolbox: {toolbox_version.name}")
    print(f"Version: {version}")
    if args.set_default and version:
        updated = project.beta.toolboxes.update(args.toolbox_name, default_version=str(version))
        print(f"Default version: {updated.get('default_version', version)}")
    if version:
        print(f"Version endpoint: {endpoint_for(project_endpoint, args.toolbox_name, version)}")
    print(f"Consumer endpoint: {endpoint_for(project_endpoint, args.toolbox_name)}")


if __name__ == "__main__":
    main()
