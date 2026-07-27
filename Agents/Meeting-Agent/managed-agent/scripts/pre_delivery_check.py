"""Validate the Managed Meeting Agent customer-delivery structure."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    for required in (
        "docs/MANAGED-IMPLEMENTATION.md",
        "docs/MANAGED-IMPLEMENTATION-CN.md",
        "CUSTOMER-START-HERE.md",
        "CUSTOMER-START-HERE-CN.md",
        "agent.yaml",
        "azure.yaml",
        "instructions.md",
        "scenario-manifest.json",
        "skills/meeting-package/SKILL.md",
        "skills/presentation-story/SKILL.md",
        "skills/presentation-story/deck-contract.yaml",
        "skills/presentation-story/presentation-style.yaml",
        "scripts/reconcile_managed_runtime.py",
        "scripts/start-ui.ps1",
        "evidence-managed-agent.json",
        "evidence/managed-live/artifact-validation.json",
        "evidence/managed-live/toolbox-skill-validation.json",
        "evidence/managed-live-gpt54/dual-input-validation.json",
        "evidence/managed-live-gpt54/large-input-recovery-validation.json",
        "evidence/managed-live-gpt54/runtime-validation.json",
        "evidence/managed-live-gpt54/ui-validation.json",
        "src/meeting_agent/templates/meeting-agent-template.zip",
        "ui/package-lock.json",
    ):
        assert (ROOT / required).is_file(), required
    assert not (ROOT / "scripts" / "start-ui-key.ps1").exists()

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["meeting-agent"] == "meeting_agent.cli:main"
    assert all("==" in dependency for dependency in project["project"]["dependencies"])
    assert all(
        "openai" not in dependency.casefold()
        for dependency in project["project"]["dependencies"]
    )
    for requirements in ("requirements.txt", "requirements-dev.txt"):
        for line in (ROOT / requirements).read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if value and not value.startswith(("#", "-r")):
                assert "==" in value, value

    agent = yaml.safe_load((ROOT / "agent.yaml").read_text(encoding="utf-8"))
    assert agent["kind"] == "prompt"
    assert agent["name"] == "managed-meeting-agent"
    assert agent["model"] == "gpt-5.4"
    instructions = (ROOT / "instructions.md").read_text(encoding="utf-8")
    assert "Do not call tool_search or call_tool" in instructions
    assert (
        ROOT / "skills" / "meeting-package" / "SKILL.md"
    ).read_bytes() == (
        ROOT / "src" / "meeting_agent" / "skills" / "meeting-package" / "SKILL.md"
    ).read_bytes()
    for name in ("SKILL.md", "deck-contract.yaml", "presentation-style.yaml"):
        assert (
            ROOT / "skills" / "presentation-story" / name
        ).read_bytes() == (
            ROOT / "src" / "meeting_agent" / "skills" / "presentation-story" / name
        ).read_bytes()
    deployment = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))
    service = deployment["services"]["managed-meeting-agent"]
    assert service["host"] == "azure.ai.agent"
    prompt = service["config"]["promptAgent"]
    assert all(str(prompt[key]).startswith("${") for key in (
        "modelEndpoint", "projectEndpoint", "resourceGroup", "subscriptionId", "workspace"
    ))

    runtime_paths = [
        *(ROOT / "src").rglob("*.py"),
        *(ROOT / "ui" / "src").rglob("*.ts"),
        *(ROOT / "ui" / "src").rglob("*.tsx"),
        *(ROOT / "ui" / "server").rglob("*.mjs"),
        ROOT / "scripts" / "start-ui.ps1",
    ]
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in runtime_paths)
    assert "AZURE_OPENAI_API_KEY" not in source_text
    assert "AzureOpenAIAnalyzer" not in source_text
    assert "MEETING_AGENT_ANALYZER must be 'managed'" in source_text

    package = json.loads((ROOT / "ui" / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["test"] == "vitest run"
    assert package["scripts"]["build"] == "tsc --noEmit && vite build"
    assert package["scripts"]["test:e2e"] == "playwright test"
    print("PASS: Managed Meeting Agent pre-delivery structure checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
