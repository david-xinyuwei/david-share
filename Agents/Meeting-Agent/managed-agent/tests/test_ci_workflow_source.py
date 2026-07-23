from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_targets_monorepo_managed_subtree() -> None:
    source_path = ROOT / ".github" / "workflows" / "managed-agent-ci.yml"
    published_path = (
        ROOT.parents[2] / ".github" / "workflows" / "managed-meeting-agent-ci.yml"
    )
    workflow_path = source_path if source_path.is_file() else published_path
    if not workflow_path.is_file():
        pytest.skip("The standalone customer package does not install repository CI.")
    workflow = workflow_path.read_text(encoding="utf-8")

    assert "Agents/Meeting-Agent/managed-agent/**" in workflow
    assert '".github/workflows/managed-meeting-agent-ci.yml"' in workflow
    assert "working-directory: Agents/Meeting-Agent/managed-agent" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8" in workflow
    assert "python scripts/validate_public_tree.py" in workflow
    assert "python -m build --wheel" in workflow
    assert "pip-audit -r requirements-dev.txt" in workflow
    assert "MEETING_AGENT_E2E_MODE=fixture python ../scripts/run_ui_e2e.py" in workflow
    assert "npm audit --omit=dev --audit-level=high" in workflow
