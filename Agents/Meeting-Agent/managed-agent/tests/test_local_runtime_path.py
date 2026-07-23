from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_runtime_is_outside_source_tree() -> None:
    launcher = (ROOT / "scripts" / "start-ui.ps1").read_text(encoding="utf-8")

    assert 'Join-Path $env:LOCALAPPDATA "ManagedMeetingAgent\\runtime"' in launcher
    assert 'Join-Path $root "runtime\\windows-managed"' not in launcher
