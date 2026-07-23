from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_source_uses_single_repo_path() -> None:
    text = (ROOT / "README-PUBLIC-NOTE.md").read_text(encoding="utf-8")
    assert "managed-agent/" in text
