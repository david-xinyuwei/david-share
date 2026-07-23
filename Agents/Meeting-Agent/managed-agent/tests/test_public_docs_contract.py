from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_docs_describe_one_repo_two_implementations() -> None:
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README-CN.md").read_text(encoding="utf-8")

    assert "same repository, not a second repository" in english
    assert "不是第二个Repo" in chinese
    assert "prompt-style local orchestration" in english
    assert "本机prompt-style编排" in chinese
    assert "managed-agent/" in english
    assert "managed-agent/" in chinese
