from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_data_location_is_not_source_tree() -> None:
    source = (ROOT / "scripts" / "start-ui.ps1").read_text(encoding="utf-8")

    assert "$env:LOCALAPPDATA" in source
    assert '"runtime\\windows-managed"' not in source
