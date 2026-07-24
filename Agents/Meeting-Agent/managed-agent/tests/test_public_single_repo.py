from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_managed_docs_use_single_repo_language() -> None:
    english = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    assert "same repository, not a second repository" in english
    assert not (ROOT / "README.md").exists()
    assert not (ROOT / "README-CN.md").exists()
