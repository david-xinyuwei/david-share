from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_contains_clean_setup_and_explicit_live_mode() -> None:
    text = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )

    assert "python -m pip install -e ." in text
    assert "npm --prefix ui ci" in text
    assert "playwright install chromium" in text
    assert "MEETING_AGENT_E2E_MODE=live" in text
