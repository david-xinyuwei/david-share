import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_parity_manifest_has_six_shared_and_two_intentional_differences() -> None:
    data = json.loads(
        (ROOT / "evidence" / "managed-live" / "parity-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert data["schema_version"] == 2
    assert len(data["entries"]) == 6
    assert len(data["intentional_differences"]) == 2
