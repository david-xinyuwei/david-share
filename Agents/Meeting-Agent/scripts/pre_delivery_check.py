"""Validate repository structure required for public customer delivery."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    english_path = ROOT / "README.md"
    chinese_path = ROOT / "README-CN.md"
    assert english_path.is_file() and chinese_path.is_file()
    english = english_path.read_text(encoding="utf-8")
    chinese = chinese_path.read_text(encoding="utf-8")
    assert english.startswith("# Meeting Agent\n")
    assert chinese.startswith("# Meeting Agent\n")
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

    chinese_comment = re.compile(r"^\s*#.*[\u4e00-\u9fff]")
    for source_dir in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        for path in source_dir.rglob("*.py"):
            assert not any(
                chinese_comment.search(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ), f"non-English code comment: {path.relative_to(ROOT)}"

    workflow_path = ROOT.parents[1] / ".github" / "workflows" / "meeting-agent-ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    assert "working-directory: Agents/Meeting-Agent" in workflow
    assert "lfs: true" not in workflow
    assert "persist-credentials: false" in workflow
    assert "python scripts/audit_no_send.py" in workflow
    assert "python scripts/audit_public_content.py" in workflow

    print("PASS: all 8 public pre-delivery structure checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())