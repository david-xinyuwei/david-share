from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ui_type_requires_runtime_attestation() -> None:
    source = (ROOT / "ui" / "src" / "types.ts").read_text(encoding="utf-8")

    assert 'runtime_attestation: "live-managed" | "test-fixture"' in source
