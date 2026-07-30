import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "reconcile_managed_runtime.py"

specification = importlib.util.spec_from_file_location("runtime_reconciler", MODULE_PATH)
assert specification and specification.loader
reconciler = importlib.util.module_from_spec(specification)
specification.loader.exec_module(reconciler)

class ToolboxRunner:
    def __init__(self) -> None:
        self.created: dict | None = None

    def run_json(self, arguments: list[str]) -> dict:
        method = arguments[arguments.index("--method") + 1]
        url = arguments[arguments.index("--url") + 1]
        if method == "get" and "/toolboxes/" in url:
            return {
                "data": [
                    {
                        "version": "1",
                        "tools": [],
                        "skills": [
                            {"type": "skill_reference", "name": "meeting-package"}
                        ],
                    }
                ]
            }
        if method == "post" and "/toolboxes/" in url:
            self.created = json.loads(arguments[arguments.index("--body") + 1])
            return {"version": "2", **self.created}
        raise AssertionError(arguments)


class FakeRunner:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    def run_json(self, arguments: list[str]) -> dict:
        method = arguments[arguments.index("--method") + 1]
        if method == "get":
            return {
                "data": [
                    {
                        "version": "1",
                        "tools": [{"type": "toolbox_search_preview"}],
                        "skills": [
                            {"type": "skill_reference", "name": "meeting-package"}
                        ],
                    }
                ]
            }
        body = json.loads(arguments[arguments.index("--body") + 1])
        self.posts.append(body)
        return {"version": "2", **body}


class NewerIncompleteRunner(FakeRunner):
    def run_json(self, arguments: list[str]) -> dict:
        method = arguments[arguments.index("--method") + 1]
        if method == "get":
            return {
                "data": [
                    {
                        "version": "3",
                        "tools": [
                            {"type": "web_search"},
                            {"type": "toolbox_search_preview"},
                        ],
                        "skills": [
                            {"type": "skill_reference", "name": "meeting-package"}
                        ],
                    },
                    {
                        "version": "2",
                        "tools": [{"type": "toolbox_search_preview"}],
                        "skills": [
                            {"type": "skill_reference", "name": "meeting-package"},
                            {"type": "skill_reference", "name": "presentation-story"},
                        ],
                    },
                ]
            }
        body = json.loads(arguments[arguments.index("--body") + 1])
        self.posts.append(body)
        return {"version": "4", **body}


def test_compatible_toolbox_accepts_web_search_and_required_skill_subset() -> None:
    assert reconciler._compatible_toolbox(
        {
            "tools": [{"type": "web_search"}],
            "skills": [
                {"type": "skill_reference", "name": "incident-triage"},
                {"type": "skill_reference", "name": "meeting-package"},
                {"type": "skill_reference", "name": "mind-map-story"},
                {"type": "skill_reference", "name": "presentation-story"},
            ],
        },
        ("meeting-package", "mind-map-story", "presentation-story"),
    )


def test_adds_missing_presentation_skill_in_new_toolbox_version() -> None:
    runner = FakeRunner()

    version = reconciler._ensure_toolbox_version(
        runner,
        "https://example.services.ai.azure.com/api/projects/demo",
        "managed-meeting-agent",
        ("meeting-package", "presentation-story"),
    )

    assert version == "2"
    assert runner.posts[0]["skills"] == [
        {"type": "skill_reference", "name": "meeting-package"},
        {"type": "skill_reference", "name": "presentation-story"},
    ]
    assert not reconciler._compatible_toolbox(
        {
            "tools": [{"type": "toolbox_search_preview"}],
            "skills": [{"type": "skill_reference", "name": "meeting-package"}],
        },
        ("meeting-package", "presentation-story"),
    )


def test_never_rolls_back_to_an_older_compatible_toolbox_version() -> None:
    runner = NewerIncompleteRunner()

    version = reconciler._ensure_toolbox_version(
        runner,
        "https://example.services.ai.azure.com/api/projects/demo",
        "managed-meeting-agent",
        ("meeting-package", "presentation-story"),
    )

    assert version == "4"
    assert runner.posts[0]["tools"] == [
        {"type": "web_search"},
        {"type": "toolbox_search_preview"},
    ]
    assert {skill["name"] for skill in runner.posts[0]["skills"]} == {
        "meeting-package",
        "presentation-story",
    }


def test_desired_definition_uses_official_skill_context_contract() -> None:
    source = {
        "kind": "prompt",
        "harness": "ghcp",
        "model": "Kimi-K2.7-Code",
        "instructions": (
            "Use the meeting-package, mind-map-story, and presentation-story Skills."
        ),
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

    assert "meeting-package, mind-map-story, and presentation-story" in (
        desired["instructions"]
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


def test_reconciler_creates_toolbox_version_with_missing_meeting_skills() -> None:
    runner = ToolboxRunner()

    version = reconciler._ensure_toolbox_version(
        runner,
        "https://example.services.ai.azure.com/api/projects/example",
        "managed-meeting-agent",
        ("meeting-package", "mind-map-story", "presentation-story"),
    )

    assert version == "2"
    assert runner.created is not None
    assert {skill["name"] for skill in runner.created["skills"]} == {
        "meeting-package",
        "mind-map-story",
        "presentation-story",
    }
    assert any(
        tool["type"] == "web_search"
        for tool in runner.created["tools"]
    )


def test_reconciler_source_enables_strict_deck_plan_manifest() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert '"managed_agent_requires_deck_plan": True' in source
    assert '"meeting-package",\n    "mind-map-story",\n    "presentation-story",' in source