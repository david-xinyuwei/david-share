"""Reconcile the deploy-time Toolbox Skill contract for a Prompt Agent."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FOUNDRY_RESOURCE = "https://ai.azure.com"
FEATURES = "HostedAgents=V1Preview,Toolboxes=V1Preview,Skills=V1Preview"
FOUNDRY_USER_ROLE_ID = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
TOOL_SEARCH_TYPES = {"toolbox_search_preview", "web_search"}
SKILL_CONTEXT_INSTRUCTION = (
    "The meeting-package, mind-map-story, and presentation-story Skill instructions "
    "are already available in your context. Do not call tool_search or call_tool for "
    "these Skills; apply the Skill instructions directly."
)
DEFAULT_SKILL_NAMES = (
    "meeting-package",
    "mind-map-story",
    "presentation-story",
)


class AzRunner:
    def run_json(self, arguments: list[str]) -> dict[str, Any]:
        environment = os.environ.copy()
        environment["AZURE_CORE_NO_COLOR"] = "true"
        completed = subprocess.run(
            ["az", *arguments, "--only-show-errors", "--output", "json"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[:1_000]
            raise RuntimeError(f"Azure CLI operation failed: {detail}")
        if not completed.stdout.strip():
            return {}
        value = json.loads(completed.stdout)
        if not isinstance(value, dict):
            raise RuntimeError("Azure CLI returned a non-object response")
        return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-name", default="true-meeting-managed-agent")
    parser.add_argument("--toolbox-name", default="my-toolbox")
    parser.add_argument(
        "--skill-name",
        action="append",
        dest="skill_names",
        help="Required Toolbox Skill name; repeat for multiple Skills.",
    )
    parser.add_argument("--expected-model", default="Kimi-K2.7-Code")
    args = parser.parse_args()

    values = json.loads(args.env_json.read_text(encoding="utf-8"))
    manifest = reconcile(
        AzRunner(),
        values,
        agent_name=args.agent_name,
        toolbox_name=args.toolbox_name,
        skill_names=tuple(args.skill_names or DEFAULT_SKILL_NAMES),
        expected_model=args.expected_model,
    )
    _atomic_json(args.output, manifest)
    print(json.dumps(manifest))
    return 0


def reconcile(
    runner: AzRunner,
    values: dict[str, str],
    *,
    agent_name: str,
    toolbox_name: str,
    skill_names: tuple[str, ...],
    expected_model: str,
) -> dict[str, Any]:
    project_endpoint = _project_endpoint(values)
    project_id = _required(values, "AZURE_AI_PROJECT_ID")
    subscription_id = _required(values, "AZURE_SUBSCRIPTION_ID")
    if not project_id.startswith(f"/subscriptions/{subscription_id}/"):
        raise ValueError("AZURE_AI_PROJECT_ID does not belong to AZURE_SUBSCRIPTION_ID")

    toolbox_version = _ensure_toolbox_version(
        runner,
        project_endpoint,
        toolbox_name,
        skill_names,
    )
    toolbox_endpoint = (
        f"{project_endpoint}/toolboxes/{toolbox_name}/versions/"
        f"{toolbox_version}/mcp?api-version=v1"
    )
    connection_name = f"{agent_name}-toolbox-agentic"
    _ensure_agentic_connection(
        runner,
        project_id,
        connection_name,
        toolbox_endpoint,
    )

    source_versions = _agent_versions(runner, project_endpoint, agent_name)
    source = source_versions[0]
    desired_definition = _desired_definition(
        source["definition"],
        toolbox_endpoint=toolbox_endpoint,
        connection_name=connection_name,
    )
    if desired_definition.get("model") != expected_model:
        raise RuntimeError(
            f"Managed Agent model is {desired_definition.get('model')!r}, "
            f"expected {expected_model!r}"
        )
    final = next(
        (
            version
            for version in source_versions
            if version.get("status") == "active"
            and version.get("definition") == desired_definition
        ),
        None,
    )
    if final is None:
        final = _data_request(
            runner,
            "post",
            f"{project_endpoint}/agents/{agent_name}/versions?api-version=v1",
            {
                "description": source.get("description"),
                "definition": desired_definition,
            },
        )
    if final.get("status") != "active":
        raise RuntimeError("Reconciled Managed Agent version is not active")
    principal_id = _agent_principal_id(final)
    _ensure_foundry_user(runner, principal_id, project_id)

    return {
        "schema_version": 1,
        "managed_agent_endpoint": f"{project_endpoint}/openai/v1/responses",
        "managed_agent_name": agent_name,
        "managed_agent_version": str(final["version"]),
        "managed_agent_model": expected_model,
        "managed_agent_requires_deck_plan": True,
        "toolbox_name": toolbox_name,
        "toolbox_version": str(toolbox_version),
        "toolbox_skills": list(skill_names),
        "toolbox_endpoint": toolbox_endpoint,
        "toolbox_connection": connection_name,
        "toolbox_connection_auth_type": "AgenticIdentityToken",
        "agent_identity_principal_id": principal_id,
        "agent_identity_role": "Foundry User",
        "agent_identity_role_scope": project_id,
    }


def _project_endpoint(values: dict[str, str]) -> str:
    endpoint = _required(values, "AZURE_AI_PROJECT_ENDPOINT").rstrip("/")
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".services.ai.azure.com")
        or "/api/projects/" not in parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("AZURE_AI_PROJECT_ENDPOINT is not a Foundry project URL")
    return endpoint


def _required(values: dict[str, str], key: str) -> str:
    value = str(values.get(key, "")).strip()
    if not value:
        raise RuntimeError(f"Missing azd environment value: {key}")
    return value


def _data_request(
    runner: AzRunner,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    arguments = [
        "rest",
        "--method",
        method,
        "--resource",
        FOUNDRY_RESOURCE,
        "--url",
        url,
        "--headers",
        f"Foundry-Features={FEATURES}",
        "Content-Type=application/json",
    ]
    if body is not None:
        arguments.extend(("--body", json.dumps(body, separators=(",", ":"))))
    return runner.run_json(arguments)


def _toolbox_versions(
    runner: AzRunner,
    project_endpoint: str,
    toolbox_name: str,
) -> list[dict[str, Any]]:
    response = _data_request(
        runner,
        "get",
        f"{project_endpoint}/toolboxes/{toolbox_name}/versions"
        "?api-version=v1&limit=100&order=desc",
    )
    versions = response.get("data")
    if not isinstance(versions, list) or not versions:
        raise RuntimeError("Managed Agent Toolbox has no versions")
    return sorted(versions, key=_version_number, reverse=True)


def _ensure_toolbox_version(
    runner: AzRunner,
    project_endpoint: str,
    toolbox_name: str,
    skill_names: tuple[str, ...],
) -> str:
    versions = _toolbox_versions(runner, project_endpoint, toolbox_name)
    latest = versions[0]
    if _compatible_toolbox(latest, skill_names):
        return str(latest["version"])

    skills = copy.deepcopy(latest.get("skills") or [])
    present = {
        str(skill.get("name"))
        for skill in skills
        if isinstance(skill, dict) and skill.get("name")
    }
    missing = [name for name in skill_names if name not in present]
    skills.extend(
        {"type": "skill_reference", "name": name}
        for name in missing
    )
    tools = copy.deepcopy(latest.get("tools") or [])
    if not any(
        isinstance(tool, dict) and tool.get("type") in TOOL_SEARCH_TYPES
        for tool in tools
    ):
        tools.append(
            {
                "type": "web_search",
                "name": "web-search",
                "description": "Access current public information with citations",
            }
        )
    created = _data_request(
        runner,
        "post",
        f"{project_endpoint}/toolboxes/{toolbox_name}/versions?api-version=v1",
        {
            "description": "Meeting analysis and presentation Skills with Web Search",
            "tools": tools,
            "skills": skills,
        },
    )
    if not _compatible_toolbox(created, skill_names):
        raise RuntimeError("Created Toolbox version does not satisfy the Skills contract")
    return str(created["version"])


def _compatible_toolbox(
    version: dict[str, Any],
    skill_names: tuple[str, ...],
) -> bool:
    tools = version.get("tools") or []
    skills = version.get("skills") or []
    present = {
        str(skill.get("name"))
        for skill in skills
        if isinstance(skill, dict) and skill.get("name")
    }
    return any(
        isinstance(tool, dict) and tool.get("type") in TOOL_SEARCH_TYPES
        for tool in tools
    ) and set(skill_names) <= present


def _ensure_agentic_connection(
    runner: AzRunner,
    project_id: str,
    connection_name: str,
    toolbox_endpoint: str,
) -> None:
    response = runner.run_json(
        [
            "rest",
            "--method",
            "put",
            "--url",
            f"https://management.azure.com{project_id}/connections/"
            f"{connection_name}?api-version=2025-06-01",
            "--body",
            json.dumps(
                {
                    "properties": {
                        "category": "RemoteTool",
                        "target": toolbox_endpoint,
                        "authType": "AgenticIdentityToken",
                        "audience": FOUNDRY_RESOURCE,
                    }
                },
                separators=(",", ":"),
            ),
        ]
    )
    properties = response.get("properties")
    if not isinstance(properties, dict) or properties.get("authType") != (
        "AgenticIdentityToken"
    ):
        raise RuntimeError("Agentic Toolbox connection was not reconciled")


def _agent_versions(
    runner: AzRunner,
    project_endpoint: str,
    agent_name: str,
) -> list[dict[str, Any]]:
    response = _data_request(
        runner,
        "get",
        f"{project_endpoint}/agents/{agent_name}/versions"
        "?api-version=v1&limit=100&order=desc",
    )
    summaries = response.get("data")
    if not isinstance(summaries, list) or not summaries:
        raise RuntimeError("Managed Agent has no versions")
    versions = [
        _data_request(
            runner,
            "get",
            f"{project_endpoint}/agents/{agent_name}/versions/"
            f"{summary['version']}?api-version=v1",
        )
        for summary in summaries
    ]
    active = [version for version in versions if version.get("status") == "active"]
    if not active:
        raise RuntimeError("Managed Agent has no active version")
    return sorted(active, key=_version_number, reverse=True)


def _desired_definition(
    source: dict[str, Any],
    *,
    toolbox_endpoint: str,
    connection_name: str,
) -> dict[str, Any]:
    definition = copy.deepcopy(source)
    if definition.get("kind") != "prompt" or definition.get("harness") != "ghcp":
        raise RuntimeError("Managed Agent must remain a GHCP Prompt Agent")
    instructions = str(definition.get("instructions") or "").strip()
    if SKILL_CONTEXT_INSTRUCTION not in instructions:
        instructions = f"{instructions}\n\n{SKILL_CONTEXT_INSTRUCTION}".strip()
    definition["instructions"] = instructions
    mcp_tools = [
        tool
        for tool in definition.get("tools") or []
        if isinstance(tool, dict) and tool.get("type") == "mcp"
    ]
    if len(mcp_tools) != 1:
        raise RuntimeError("Managed Agent must expose exactly one Toolbox MCP tool")
    mcp_tools[0].update(
        {
            "server_url": toolbox_endpoint,
            "project_connection_id": connection_name,
            "require_approval": "never",
        }
    )
    return definition


def _agent_principal_id(agent: dict[str, Any]) -> str:
    identity = agent.get("instance_identity")
    if not isinstance(identity, dict):
        raise RuntimeError("Managed Agent version omitted instance_identity")
    principal_id = str(identity.get("principal_id") or "").strip()
    if not principal_id:
        raise RuntimeError("Managed Agent version omitted its identity principal id")
    return principal_id


def _ensure_foundry_user(
    runner: AzRunner,
    principal_id: str,
    project_id: str,
) -> None:
    runner.run_json(
        [
            "role",
            "assignment",
            "create",
            "--assignee-object-id",
            principal_id,
            "--assignee-principal-type",
            "ServicePrincipal",
            "--role",
            FOUNDRY_USER_ROLE_ID,
            "--scope",
            project_id,
        ]
    )


def _version_number(value: dict[str, Any]) -> int:
    try:
        return int(str(value["version"]).removeprefix("v"))
    except (KeyError, ValueError) as error:
        raise RuntimeError("Foundry resource returned an invalid version") from error


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
