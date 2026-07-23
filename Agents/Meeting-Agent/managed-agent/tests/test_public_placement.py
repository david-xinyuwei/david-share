from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_placement_is_single_repo_subdirectory() -> None:
    text = (ROOT / "README-PUBLIC-NOTE.md").read_text(encoding="utf-8")

    assert "Agents/Meeting-Agent/managed-agent/" in text
    assert "classic implementation remains" in text
