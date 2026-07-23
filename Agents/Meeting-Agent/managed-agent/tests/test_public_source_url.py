from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    "https://github.com/david-xinyuwei/david-share/"
    "tree/master/Agents/Meeting-Agent/managed-agent"
)


def test_public_source_uses_single_repo_path() -> None:
    text = (ROOT / "README-PUBLIC-NOTE.md").read_text(encoding="utf-8")
    assert "managed-agent/" in text


def test_public_readmes_show_source_and_ci_in_first_screen() -> None:
    english = "\n".join((ROOT / "README.md").read_text(encoding="utf-8").splitlines()[:20])
    chinese = "\n".join(
        (ROOT / "README-CN.md").read_text(encoding="utf-8").splitlines()[:20]
    )

    assert f"[Source]({SOURCE_URL})" in english
    assert f"[源码]({SOURCE_URL})" in chinese
    assert "managed-meeting-agent-ci.yml/badge.svg?branch=master" in english
    assert "managed-meeting-agent-ci.yml/badge.svg?branch=master" in chinese
