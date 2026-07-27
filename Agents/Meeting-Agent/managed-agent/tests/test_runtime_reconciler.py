import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "reconcile_managed_runtime.py"

specification = importlib.util.spec_from_file_location("runtime_reconciler", MODULE_PATH)
assert specification and specification.loader
reconciler = importlib.util.module_from_spec(specification)
specification.loader.exec_module(reconciler)


def test_compatible_toolbox_requires_search_and_skill() -> None:
    assert reconciler._compatible_toolbox(
        {
            "tools": [{"type": "toolbox_search_preview"}],
            "skills": [{"type": "skill_reference", "name": "meeting-package"}],
        },
        "meeting-package",
    )
    assert not reconciler._compatible_toolbox(
        {
            "tools": [],
            "skills": [{"type": "skill_reference", "name": "meeting-package"}],
        },
        "meeting-package",
    )


def test_desired_definition_uses_official_skill_context_contract() -> None:
    source = {
        "kind": "prompt",
        "harness": "ghcp",
        "model": "gpt-5.4",
        "instructions": "Use the meeting-package Skill.",
        "tools": [
            {
                "type": "mcp",
                "server_label": "managed-meeting-agent",
                "server_url": "https://old.example/mcp",
                "project_connection_id": "old-connection",
                "require_approval": "always",
            }
        ],
    }

    desired = reconciler._desired_definition(
        source,
        toolbox_endpoint="https://example.services.ai.azure.com/toolbox/mcp?api-version=v1",
        connection_name="managed-meeting-agent-toolbox-agentic",
    )

    assert "Do not call tool_search or call_tool" in desired["instructions"]
    assert desired["tools"][0]["project_connection_id"].endswith("-agentic")
    assert desired["tools"][0]["require_approval"] == "never"
    assert source["tools"][0]["require_approval"] == "always"


def test_project_endpoint_rejects_non_foundry_host() -> None:
    try:
        reconciler._project_endpoint(
            {"AZURE_AI_PROJECT_ENDPOINT": "https://external.example/api/projects/demo"}
        )
    except ValueError as error:
        assert "Foundry project URL" in str(error)
    else:
        raise AssertionError("expected external endpoint rejection")