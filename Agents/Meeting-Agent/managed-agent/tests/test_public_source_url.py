from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    "https://github.com/david-xinyuwei/david-share/"
    "tree/master/Agents/Meeting-Agent/managed-agent"
)


def test_public_source_uses_single_repo_path() -> None:
    text = (ROOT / "README-PUBLIC-NOTE.md").read_text(encoding="utf-8")
    assert "managed-agent/" in text


def test_public_docs_link_back_to_product_home_and_ci() -> None:
    english = "\n".join(
        (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md")
        .read_text(encoding="utf-8")
        .splitlines()[:20]
    )
    chinese = "\n".join(
        (ROOT / "docs" / "MANAGED-IMPLEMENTATION-CN.md")
        .read_text(encoding="utf-8")
        .splitlines()[:20]
    )

    assert f"[Product Home]({SOURCE_URL.rsplit('/managed-agent', 1)[0]})" in english
    assert f"[产品首页]({SOURCE_URL.rsplit('/managed-agent', 1)[0]})" in chinese
    assert "managed-meeting-agent-ci.yml/badge.svg?branch=master" in english
    assert "managed-meeting-agent-ci.yml/badge.svg?branch=master" in chinese
