import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_customer_package.py"


def _package_builder():
    specification = importlib.util.spec_from_file_location("customer_package_builder", MODULE_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_customer_package_includes_test_tree() -> None:
    builder = _package_builder()
    packaged_paths = {
        path.relative_to(ROOT).as_posix()
        for path in builder.package_files()
    }

    assert "tests/test_managed_analyzer.py" in packaged_paths
    assert "tests/test_hosted_api.py" in packaged_paths
    assert "tests/e2e_server.py" in packaged_paths
    assert ".agentignore" in packaged_paths
    assert "skills/mind-map-story/SKILL.md" in packaged_paths
    assert (
        "evidence/managed-live-gpt54/presentation-skill-v9-validation.json"
        in packaged_paths
    )
    assert "images/managed-agent-skill-toolbox-sandbox-flow.svg" in packaged_paths
    assert "images/managed-agent-skill-toolbox-sandbox-flow-cn.svg" in packaged_paths
    assert "docs/FOUNDRY-PORTAL-EVIDENCE.md" in packaged_paths
    assert "docs/FOUNDRY-PORTAL-EVIDENCE-CN.md" in packaged_paths
    assert "evidence/managed-live-westus2/sandbox-runtime-observation.json" in packaged_paths
    for filename in (
        "agent-list.png",
        "agent-playground.png",
        "toolbox-skills.png",
        "skill-meeting-package-version-drift.png",
        "skill-mind-map-story.png",
        "skill-presentation-story.png",
        "hand-sandbox-capacity.png",
    ):
        assert f"images/foundry-portal/{filename}" in packaged_paths
    assert not any(".egg-info/" in path for path in packaged_paths)


def test_build_dependencies_are_in_audited_dev_requirements() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    build_dependencies = set(project["build-system"]["requires"])
    development_dependencies = set(
        (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    )

    assert build_dependencies <= development_dependencies


def test_customer_package_rejects_path_like_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    builder = _package_builder()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_customer_package.py",
            "--output-dir",
            str(tmp_path),
            "--name",
            "../outside",
        ],
    )

    with pytest.raises(ValueError, match="Package name"):
        builder.main()

    assert list(tmp_path.iterdir()) == []