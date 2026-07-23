import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_parity_manifest_has_eight_shared_modules() -> None:
    data = json.loads(
        (ROOT / "evidence" / "managed-live" / "parity-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(data["entries"]) == 8
