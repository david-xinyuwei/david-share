from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ui_attestation_labels_are_distinct() -> None:
    source = (ROOT / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert '"Test fixture"' in source
    assert '"Foundry Prompt Agent · Managed GHCP"' in source
