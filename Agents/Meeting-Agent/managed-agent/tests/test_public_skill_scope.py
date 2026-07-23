import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_snapshot_is_dated() -> None:
    data = json.loads(
        (ROOT / "evidence" / "managed-live" / "toolbox-skill-validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert data["validated_at_utc"]
    assert data["cloud_matches_local_at_validation_time"] is True
