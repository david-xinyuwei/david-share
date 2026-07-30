"""Validate repository structure required for public customer delivery."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
README_TITLE = "# Managed Meeting by Prompt Agent and Managed Agent\n"


def main() -> int:
    english_path = ROOT / "README.md"
    chinese_path = ROOT / "README-CN.md"
    assert english_path.is_file() and chinese_path.is_file()
    english = english_path.read_text(encoding="utf-8")
    chinese = chinese_path.read_text(encoding="utf-8")
    assert english.startswith(README_TITLE)
    assert chinese.startswith(README_TITLE)
    english_first = english.splitlines()[:15]
    chinese_first = chinese.splitlines()[:15]
    assert english_first[2].startswith("[![Python 3.11+")
    assert chinese_first[2].startswith("[![Python 3.11+")
    assert english_first[9] == "> Author: Xinyu Wei"
    assert chinese_first[9] == "> 作者：魏新宇"
    source_url = "https://github.com/david-xinyuwei/david-share/tree/master/Agents/Meeting-Agent"
    assert f"[Source]({source_url})" in english_first[11]
    assert f"[源码]({source_url})" in chinese_first[11]
    legacy_terms = ("Yun" + "shang", "云" + "上", "xinyuwei" + "-david")
    assert not any(term.casefold() in (english + chinese).casefold() for term in legacy_terms)
    assert "Example Output" in english and "运行日志" in chinese
    assert "Xinyu Wei" in english and "魏新宇" in chinese

    ascii_art = "\u250c\u2510\u2514\u2518\u251c\u2524\u2500\u2502"
    assert not any(character in english + chinese for character in ascii_art)

    for requirements_path in (ROOT / "requirements.txt", ROOT / "requirements-dev.txt"):
        for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith(("#", "-r")):
                assert "==" in line, f"dependency is not pinned: {line}"

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["name"] == "meeting-agent"
    assert project["project"]["scripts"]["meeting-agent"] == "meeting_agent.cli:main"
    assert all("==" in dependency for dependency in project["project"]["dependencies"])

    assert (ROOT / "main.py").is_file()
    assert not (ROOT / "azure.yaml").exists()
    assert not (ROOT / "agent.yaml").exists()
    assert not (ROOT / "scripts" / "deploy-and-start.ps1").exists()
    assert not (ROOT / "scripts" / "deploy-and-start.sh").exists()
    assert (ROOT / "scripts" / "start-ui-key.ps1").is_file()
    assert (ROOT / "src" / "meeting_agent" / "skills" / "meeting-package" / "SKILL.md").is_file()
    template_path = ROOT / "src" / "meeting_agent" / "templates" / "meeting-agent-template.pptx"
    assert template_path.is_file() and template_path.stat().st_size > 20_000
    assert (ROOT / "examples" / "meeting-record-foundry-workshop.json").is_file()
    assert (ROOT / "media" / "meeting-agent-demo-1.6x.mp4").stat().st_size > 20_000_000
    assert (ROOT / "images" / "meeting-agent-demo-preview.gif").stat().st_size < 10_000_000
    assert (ROOT / "evidence" / "meeting-agent-demo-video.json").is_file()

    package = json.loads((ROOT / "ui" / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["build"] == "tsc --noEmit && vite build"
    assert package["scripts"]["test"] == "vitest run"
    assert package["scripts"]["test:e2e"] == "playwright test"
    assert "mermaid" not in package["dependencies"]
    assert (ROOT / "ui" / "package-lock.json").is_file()
    assert (ROOT / "ui" / "server" / "index.mjs").is_file()
    assert (ROOT / "ui" / "src" / "App.tsx").is_file()

    chinese_comment = re.compile(r"^\s*#.*[\u4e00-\u9fff]")
    for source_dir in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in source_dir.rglob("*.py"):
            assert not any(
                chinese_comment.search(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ), f"non-English code comment: {path.relative_to(ROOT)}"

    workflow_path = ROOT.parents[1] / ".github" / "workflows" / "meeting-agent-ci.yml"
    if workflow_path.is_file():
        workflow = workflow_path.read_text(encoding="utf-8")
        workflow_data = yaml.safe_load(workflow)
        web_steps = workflow_data["jobs"]["web-ui"]["steps"]
        assert all(
            isinstance(step, dict) and ("uses" in step or "run" in step)
            for step in web_steps
        )
        assert "working-directory: Agents/Meeting-Agent" in workflow
        assert workflow.count("lfs: true") == 2
        assert "persist-credentials: false" not in workflow
        assert "python scripts/audit_no_send.py" in workflow
        assert "python scripts/audit_public_content.py" in workflow
        assert 'python-version: ["3.11", "3.12", "3.13"]' in workflow
        assert "npm ci --no-audit --no-fund" in workflow
        assert "npm run build" in workflow
        assert "python ../scripts/run_ui_e2e.py" in workflow
    else:
        manifest = json.loads((ROOT / "PACKAGE-MANIFEST.json").read_text(encoding="utf-8"))
        packaged_paths = {entry["path"] for entry in manifest["files"]}
        assert manifest["excluded_runtime_and_secrets"] is True
        assert manifest["file_count"] == len(packaged_paths)
        assert not any(path.startswith("tests/") for path in packaged_paths)
        assert {
            "CUSTOMER-START-HERE.md",
            "CUSTOMER-START-HERE-CN.md",
            "evidence/meeting-agent-demo-video.json",
            "images/meeting-agent-demo-preview.gif",
            "media/meeting-agent-demo-1.6x.mp4",
            "scripts/start-ui.ps1",
            "scripts/start-ui-key.ps1",
            "ui/package-lock.json",
        } <= packaged_paths

    print("PASS: all 12 public pre-delivery structure checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())